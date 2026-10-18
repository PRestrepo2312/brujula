"""Tablero, API JSON y webhooks de Brújula (FastAPI + Jinja2). Todo está aislado por empresa."""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlmodel import func, select

from .. import agente, auth, empresas, metrics, notificaciones, pipeline, storage
from ..compliance import ahora_local, anotar, cargar_rne_csv, proxima_ventana, ventana_permitida
from ..config import config
from ..db import crear_tablas, sesion
from ..icp import ICP
from ..ingest import buscar as buscar_fuentes, ingerir_csv
from ..models import Bitacora, Calificacion, Intento, Lead, Lote
from ..sources import CONECTORES

app = FastAPI(title="Brújula", docs_url="/api/docs", openapi_url="/api/openapi.json",
              description="API de Brújula: empresas, ICP con agente, fuentes, leads, lotes, métricas, notificaciones, archivos y webhooks. Un front separado consume estas rutas con un JWT de Cognito.")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in config.cors_origins.split(",")], allow_methods=["*"], allow_headers=["*"])
plantillas = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
crear_tablas()
cognito = auth.Cognito()

# Front Angular compilado: en la imagen Docker queda en /app/front_dist; en desarrollo, en front/dist tras `npm run build`.
_RAIZ = Path(__file__).resolve().parents[2]
FRONT = next((p for p in (_RAIZ / "front_dist", _RAIZ / "front" / "dist" / "front" / "browser") if (p / "index.html").exists()), None)


# ---------------- Modelos de entrada ----------------

class LoteEntrada(BaseModel):
    n: int | None = None
    modo: str = "brujula"
    reparto: dict[str, int] | None = None
    usuario: str = ""
    motivo_override: str = ""


class RevisionEntrada(BaseModel):
    decision: str   # aprobar | descartar


class ArchivoEntrada(BaseModel):
    nombre: str
    content_type: str = "text/csv"


class ProcesarEntrada(BaseModel):
    clave: str
    tipo: str        # leads_csv | rne
    pais: str = "CO"


class TextoEntrada(BaseModel):
    texto: str


class BusquedaEntrada(BaseModel):
    fuentes: list[str] = ["reps", "rnt", "men"]
    ciudad: str = "BOGOTA"
    sector: str = ""
    limite: int = 100
    parametros: dict[str, dict] | None = None     # ciudad/sector propios de una fuente: {"denue": {"ciudad": "09"}, "cnpj": {"sector": "…"}}


class EmpresaEntrada(BaseModel):
    nombre: str
    correo_notificaciones: str = ""
    icp_texto: str = ""


class EmpresaCambio(BaseModel):
    nombre: str | None = None
    correo_notificaciones: str | None = None
    icp_texto: str | None = None
    dapta_api_key: str | None = None
    dapta_agent_id: str | None = None
    dapta_sequence_id: str | None = None
    config: dict | None = None


class RegistroEntrada(BaseModel):
    empresa: str
    email: str
    clave: str
    icp_texto: str = ""
    nit: str = ""
    rues: dict | None = None      # lo que trajo /api/nit, para guardarlo en el perfil sin volver a consultar


class UsuarioEntrada(BaseModel):
    email: str
    empresa_id: int
    rol: str = "usuario"


class RespuestaEntrada(BaseModel):
    lead_id: int
    texto: str
    canal: str = "whatsapp"


# ---------------- Sesión y empresa ----------------

@app.middleware("http")
async def exigir_login(request: Request, call_next):
    """Con Cognito activo: todo exige usuario salvo las rutas públicas (enlaces del correo, webhooks, salud, cron con clave)."""
    ruta = request.url.path
    usuario = auth.usuario_desde(request, cognito)
    request.state.usuario = usuario
    if cognito.activo and usuario is None and not auth.es_publica(ruta):
        if ruta.startswith("/api/"):
            return JSONResponse({"error": "autenticación requerida: Bearer JWT de Cognito"}, status_code=401)
        return RedirectResponse(f"/login?next={ruta}", status_code=303)
    return await call_next(request)


def usuario_de(request: Request) -> dict:
    return getattr(request.state, "usuario", None) or {"email": "local", "empresa_id": 1, "rol": "superadmin"}


def empresa_de(request: Request) -> int:
    """La empresa del usuario; solo el superadmin de la plataforma puede mirar otra con ?empresa=ID."""
    u = usuario_de(request)
    if u.get("rol") == "superadmin":
        q = request.query_params.get("empresa")
        if q and q.isdigit():
            return int(q)
    return int(u.get("empresa_id") or 1)


def es_admin(request: Request) -> bool:
    """Administrador de su empresa (crea usuarios de su empresa) o superadmin de la plataforma."""
    return usuario_de(request).get("rol") in ("admin", "superadmin")


def es_superadmin(request: Request) -> bool:
    """Superadmin de la plataforma: ve todas las empresas, las crea y crea usuarios en cualquiera."""
    return usuario_de(request).get("rol") == "superadmin"


def ctx(request: Request, **extra) -> dict:
    ok, razon = ventana_permitida()
    usuario = usuario_de(request)
    emp = empresas.obtener(empresa_de(request))
    return {"request": request, "ventana_ok": ok, "ventana_razon": razon, "ahora": ahora_local().strftime("%a %d %b, %H:%M"),
            "proxima": proxima_ventana().strftime("%a %d %b, %H:%M"), "usuario": usuario, "login_activo": cognito.activo,
            "empresa": emp, **extra}


@app.get("/login")
def login(request: Request, next: str = "/"):
    if not cognito.activo:
        return RedirectResponse("/", status_code=303)
    redirect_uri = f"{config.public_base_url.rstrip('/')}/callback"
    return RedirectResponse(cognito.url_login(redirect_uri, auth.firmar_estado(next)), status_code=303)


@app.get("/callback")
def callback(request: Request, code: str = "", state: str = ""):
    if not cognito.activo or not code:
        return RedirectResponse("/", status_code=303)
    redirect_uri = f"{config.public_base_url.rstrip('/')}/callback"
    tokens = cognito.canjear_codigo(code, redirect_uri)
    claims = cognito.verificar(tokens["id_token"])
    resp = RedirectResponse(auth.leer_estado(state), status_code=303)
    resp.set_cookie(auth.COOKIE, auth.crear_cookie(claims), max_age=auth.DURACION_SESION_SEG, httponly=True, secure=config.public_base_url.startswith("https"), samesite="lax")
    return resp


@app.get("/logout")
def logout():
    resp = RedirectResponse(cognito.url_logout(config.public_base_url.rstrip("/") + "/login") if cognito.activo else "/", status_code=303)
    resp.delete_cookie(auth.COOKIE)
    return resp


@app.get("/api/yo")
def api_yo(request: Request):
    u = usuario_de(request)
    return {"usuario": u, "login_activo": cognito.activo, "empresa_id": empresa_de(request), "admin": es_admin(request)}


# ---------------- Front Angular (servido por la misma aplicación en /app) ----------------

@app.get("/")
def raiz(request: Request):
    """Con el front compilado, la raíz es la aplicación Angular; el tablero del servidor queda en /tablero."""
    if FRONT is not None:
        return RedirectResponse("/app/")
    if cognito.activo and getattr(request.state, "usuario", None) is None:
        return RedirectResponse("/login?next=/tablero", status_code=303)
    return tablero(request)


@app.get("/app/config.json")
def app_config():
    """Configuración que lee el front al arrancar: la API es el mismo origen y Cognito es el del servidor."""
    base = config.public_base_url.rstrip("/")
    return JSONResponse({"apiUrl": "", "frontUrl": f"{base}/app",
                         "cognito": {"domain": config.cognito_domain, "clientId": config.cognito_client_id,
                                     "userPoolId": config.cognito_user_pool_id, "region": os.environ.get("AWS_REGION", "us-east-1")}},
                        headers={"Cache-Control": "no-store"})


@app.get("/app")
def app_sin_barra():
    return RedirectResponse("/app/")


@app.get("/app/{ruta:path}")
def app_front(ruta: str):
    """Archivos del front; cualquier ruta que no sea un archivo devuelve index.html (rutas del router de Angular)."""
    if FRONT is None:
        return JSONResponse({"error": "front no compilado: ejecute `npm run build` en front/"}, status_code=404)
    destino = (FRONT / ruta).resolve() if ruta else None
    if destino is not None and destino.is_file() and FRONT in destino.parents:
        con_hash = "-" in destino.stem and destino.suffix in (".js", ".css")   # main-XXXX.js, chunk-XXXX.js, styles-XXXX.css
        return FileResponse(str(destino), headers={"Cache-Control": "public, max-age=31536000, immutable" if con_hash else "no-cache"})
    return FileResponse(str(FRONT / "index.html"), headers={"Cache-Control": "no-cache"})


# ---------------- Tablero HTML del servidor ----------------

@app.get("/tablero", response_class=HTMLResponse)
def tablero(request: Request):
    emp_id = empresa_de(request)
    m = metrics.calcular(emp_id)
    with sesion() as s:
        lotes = s.exec(select(Lote).where(Lote.empresa_id == emp_id).order_by(Lote.id.desc()).limit(8)).all()
        bitacora = s.exec(select(Bitacora).where(Bitacora.empresa_id == emp_id).order_by(Bitacora.id.desc()).limit(12)).all()
    return plantillas.TemplateResponse("tablero.html", ctx(request, m=m, lotes=lotes, bitacora=bitacora, icp=empresas.icp_de(emp_id), m_json=json.dumps(m)))


@app.get("/leads", response_class=HTMLResponse)
def leads(request: Request, estado: str = "", fuente: str = "", q: str = ""):
    emp_id = empresa_de(request)
    with sesion() as s:
        st = select(Lead).where(Lead.duplicado_de.is_(None), Lead.empresa_id == emp_id)
        if estado:
            st = st.where(Lead.icp_estado == estado) if estado in ("pasa", "revisar", "descarta", "pendiente") else st.where(Lead.estado == estado)
        if fuente:
            st = st.where(Lead.fuente_clave == fuente)
        if q:
            st = st.where(Lead.razon_social.contains(q.upper()))
        filas = s.exec(st.order_by(Lead.icp_score.desc(), Lead.id).limit(300)).all()
        fuentes = [r for r in s.exec(select(Lead.fuente_clave).where(Lead.empresa_id == emp_id).distinct()).all()]
    return plantillas.TemplateResponse("leads.html", ctx(request, leads=filas, fuentes=fuentes, estado=estado, fuente=fuente, q=q))


@app.get("/lead/{lead_id}", response_class=HTMLResponse)
def lead_detalle(request: Request, lead_id: int):
    emp_id = empresa_de(request)
    with sesion() as s:
        l = s.get(Lead, lead_id)
        if not l or l.empresa_id != emp_id:
            return RedirectResponse("/leads", status_code=303)
        intentos = s.exec(select(Intento).where(Intento.lead_id == lead_id).order_by(Intento.id)).all()
        dup = s.exec(select(Lead).where(Lead.duplicado_de == lead_id)).all()
    return plantillas.TemplateResponse("lead.html", ctx(request, l=l, intentos=intentos, duplicados=dup))


def _revisar(lead_id: int, decision: str, emp_id: int) -> bool:
    with sesion() as s:
        l = s.get(Lead, lead_id)
        if not l or l.empresa_id != emp_id:
            return False
        if decision == "aprobar":
            l.icp_estado, l.estado = "pasa", "listo"
        else:
            l.icp_estado, l.estado = "descarta", "descartado"
        l.icp_detalle = {**(l.icp_detalle or {}), "revision_humana": decision}
        s.add(l)
        s.commit()
        return True


@app.post("/lead/{lead_id}/revision")
def lead_revision(request: Request, lead_id: int, decision: str = Form(...)):
    _revisar(lead_id, decision, empresa_de(request))
    return RedirectResponse(f"/lead/{lead_id}", status_code=303)


@app.post("/lote/nuevo")
def lote_nuevo(request: Request, n: int = Form(20), modo: str = Form("brujula"), usuario: str = Form(""), motivo_override: str = Form("")):
    emp_id = empresa_de(request)
    quien = usuario_de(request).get("email") if cognito.activo else usuario
    r = pipeline.preparar_lote(n=n, modo=modo, usuario=quien or usuario, motivo_override=motivo_override, empresa_id=emp_id)
    if "error" in r:
        return RedirectResponse(f"/?aviso={r['error']}", status_code=303)
    pipeline.ejecutar_lote(r["lote_id"])
    return RedirectResponse(f"/?lote={r['lote_id']}", status_code=303)


@app.post("/sincronizar")
def sincronizar(request: Request):
    emp_id = empresa_de(request)
    return JSONResponse({"calificador": pipeline.pasar_a_dapta_los_que_respondieron(emp_id), "dapta": pipeline.sincronizar_dapta(empresa_id=emp_id)})


@app.post("/simular")
def simular(request: Request):
    return JSONResponse(pipeline.simular_resultados(empresa_id=empresa_de(request)))


@app.get("/r/{token}", response_class=HTMLResponse)
def respuesta_correo(request: Request, token: str, v: str = "no"):
    r = pipeline.registrar_respuesta_token(token, v if v in ("si", "no", "baja") else "no")
    return plantillas.TemplateResponse("gracias.html", ctx(request, r=r, v=v))


# ---------------- Webhooks ----------------

@app.post("/webhook/dapta")
async def webhook_dapta(request: Request):
    """Análisis post-llamada del agente de voz. Se guarda crudo y se concilia con sincronizar."""
    cuerpo = await request.json()
    with sesion() as s:
        s.add(Bitacora(tipo="webhook_dapta", mensaje="análisis post-llamada", datos=cuerpo if isinstance(cuerpo, dict) else {"cuerpo": cuerpo}))
        s.commit()
    try:
        pipeline.sincronizar_dapta(limite=50)
        pipeline.sincronizar_chats()
    except Exception as e:  # noqa: BLE001
        with sesion() as s:
            s.add(Bitacora(tipo="error", mensaje=f"sincronizar tras webhook: {e}"[:400]))
            s.commit()
    return {"ok": True}


@app.post("/webhook/resend")
async def webhook_resend(request: Request):
    cuerpo = await request.json()
    tipo = cuerpo.get("type", "")
    ref = (cuerpo.get("data") or {}).get("email_id", "")
    ok = pipeline.registrar_evento_correo(ref, tipo) if ref else False
    return {"ok": ok}


@app.post("/webhook/ses")
async def webhook_ses(request: Request):
    """Eventos de Amazon SES vía SNS (Delivery, Open, Click, Bounce, Complaint). Confirma la suscripción sola."""
    import httpx
    crudo = await request.body()
    try:
        msg = json.loads(crudo)
    except json.JSONDecodeError:
        return {"ok": False}
    if msg.get("Type") == "SubscriptionConfirmation" and msg.get("SubscribeURL"):
        httpx.get(msg["SubscribeURL"], timeout=20)
        return {"ok": True, "suscrito": True}
    try:
        ev = json.loads(msg.get("Message", "{}"))
    except json.JSONDecodeError:
        ev = {}
    tipo = (ev.get("eventType") or ev.get("notificationType") or "").lower()
    ref = (ev.get("mail") or {}).get("messageId", "")
    mapa = {"delivery": "email.delivered", "open": "email.opened", "click": "email.clicked", "bounce": "email.bounced", "complaint": "email.complained"}
    ok = pipeline.registrar_evento_correo(ref, mapa.get(tipo, "")) if ref else False
    return {"ok": ok}


@app.post("/cron/lote")
def cron_lote(request: Request, n: int | None = None):
    """Lo llama EventBridge cada hora dentro de la ventana legal: la brújula reparte y envía el siguiente lote de cada empresa."""
    if config.cron_key and request.headers.get("x-cron-key") != config.cron_key:
        return JSONResponse({"error": "clave de cron inválida"}, status_code=401)
    salida = {}
    for e in empresas.listar():
        r = pipeline.preparar_lote(n=n, modo="brujula", empresa_id=e.id)
        if "lote_id" in r:
            r["envio"] = pipeline.ejecutar_lote(r["lote_id"])
        salida[e.id] = r
    return salida


@app.post("/cron/sincronizar")
def cron_sincronizar(request: Request):
    if config.cron_key and request.headers.get("x-cron-key") != config.cron_key:
        return JSONResponse({"error": "clave de cron inválida"}, status_code=401)
    return {e.id: {"calificador": pipeline.pasar_a_dapta_los_que_respondieron(e.id), "dapta": pipeline.sincronizar_dapta(empresa_id=e.id),
                   "whatsapp": pipeline.sincronizar_chats(empresa_id=e.id)} for e in empresas.listar()}


@app.get("/healthz")
def healthz():
    return {"ok": True}


# ---------------- API JSON (la consume el front) ----------------

@app.get("/api/estado")
def api_estado(request: Request):
    emp_id = empresa_de(request)
    with sesion() as s:
        n = s.exec(select(func.count(Lead.id)).where(Lead.empresa_id == emp_id)).one()
    ok, razon = ventana_permitida()
    b = agente.llm()
    from ..channels.voz_dapta import CanalVozDapta
    return {"leads": n, "ventana_ok": ok, "razon": razon, "ahora": ahora_local().isoformat(), "proxima_ventana": proxima_ventana().isoformat(),
            "respetar_ley_2300": bool(empresas.config_de(emp_id).get("respetar_ley_2300", True)),
            "perfil_completo": empresas.perfil_de(emp_id)["completo"],
            "agente": {"bedrock": b.bedrock.disponible, "llm": b.motor, "llm_error": b.error, "jev": config.jev_disponible,
                       "dapta_voz_real": CanalVozDapta(emp_id).real, "correo_real": config.correo_real},
            "modo_prueba": {"activo": config.modo_prueba, "telefono": config.telefono_prueba, "correos": config.correos_prueba}}


@app.get("/api/metricas")
def api_metricas(request: Request):
    return metrics.calcular(empresa_de(request))


@app.get("/api/fuentes")
def api_fuentes():
    return [c().describir() for c in CONECTORES.values()]


@app.post("/api/buscar")
def api_buscar(request: Request, entrada: BusquedaEntrada):
    """Encontrar: corre las fuentes elegidas, deduplica y puntúa el ICP de la empresa."""
    emp_id = empresa_de(request)
    fuentes = [f for f in entrada.fuentes if f in CONECTORES and f != "csv"]
    r = buscar_fuentes(emp_id, fuentes, ciudad=entrada.ciudad, sector=entrada.sector, limite=max(1, min(entrada.limite, 500)), parametros=entrada.parametros)
    notificaciones.notificar(emp_id, "busqueda", f"Búsqueda en {', '.join(fuentes)} ({entrada.ciudad or 'todas las ciudades'}): {r['nuevos']} empresas nuevas")
    return r


@app.post("/api/asistente/buscar")
def api_asistente_buscar(request: Request, entrada: AsistenteEntrada):
    """Buscar conversando: la brújula propone fuentes y ciudades a partir del cliente ideal, la persona corrige y confirma, y se corre la búsqueda."""
    return asistente.responder_busqueda(empresa_de(request), entrada.mensaje, entrada.estado)


@app.get("/api/leads")
def api_leads(request: Request, estado: str = "", fuente: str = "", q: str = "", limite: int = 200, pagina: int = 1, orden: str = "encaje"):
    """orden: encaje (mejor puntaje contra el cliente ideal), calientes (calificados, luego respondieron, luego contactados) o recientes (últimos agregados)."""
    from sqlalchemy import case
    emp_id = empresa_de(request)
    with sesion() as s:
        st = select(Lead).where(Lead.duplicado_de.is_(None), Lead.empresa_id == emp_id)
        if estado:
            st = st.where(Lead.icp_estado == estado) if estado in ("pasa", "revisar", "descarta", "pendiente") else st.where(Lead.estado == estado)
        if fuente:
            st = st.where(Lead.fuente_clave == fuente)
        if q:
            st = st.where(Lead.razon_social.contains(q.upper()))
        if orden == "calientes":
            calor = case({"calificado": 0, "respondio": 1, "contactado": 2, "listo": 3, "nuevo": 4}, value=Lead.estado, else_=5)
            st = st.order_by(calor, Lead.actualizado_en.desc(), Lead.icp_score.desc())
        elif orden == "recientes":
            st = st.order_by(Lead.creado_en.desc(), Lead.id.desc())
        else:
            st = st.order_by(Lead.icp_score.desc(), Lead.id)
        filas = s.exec(st.offset((pagina - 1) * limite).limit(limite)).all()
    return [{k: v for k, v in l.model_dump().items() if k != "crudo"} for l in filas]


@app.get("/api/lead/{lead_id}")
def api_lead(request: Request, lead_id: int):
    emp_id = empresa_de(request)
    with sesion() as s:
        l = s.get(Lead, lead_id)
        if not l or l.empresa_id != emp_id:
            return JSONResponse({"error": "no existe"}, status_code=404)
        intentos = s.exec(select(Intento).where(Intento.lead_id == lead_id).order_by(Intento.id)).all()
        calis = s.exec(select(Calificacion).where(Calificacion.lead_id == lead_id)).all()
        dup = s.exec(select(Lead.id, Lead.razon_social, Lead.fuente_clave).where(Lead.duplicado_de == lead_id)).all()
    return {"lead": {k: v for k, v in l.model_dump().items() if k != "crudo"}, "intentos": [i.model_dump() for i in intentos],
            "calificaciones": [c.model_dump() for c in calis], "duplicados": [{"id": d[0], "razon_social": d[1], "fuente": d[2]} for d in dup]}


@app.post("/api/lead/{lead_id}/revision")
def api_lead_revision(request: Request, lead_id: int, entrada: RevisionEntrada):
    ok = _revisar(lead_id, entrada.decision, empresa_de(request))
    return {"ok": ok, "lead_id": lead_id, "decision": entrada.decision}


@app.get("/api/lead/{lead_id}/mensaje")
def api_lead_mensaje(request: Request, lead_id: int, canal: str = "correo", idioma: str = ""):
    """Vista previa del primer mensaje que redactaría el agente para este lead, en el idioma de su fuente o en el que se pida (es, pt, en)."""
    from ..mensajes import IDIOMAS, idioma_de
    emp_id = empresa_de(request)
    with sesion() as s:
        l = s.get(Lead, lead_id)
        if not l or l.empresa_id != emp_id:
            return JSONResponse({"error": "no existe"}, status_code=404)
    idioma = idioma if idioma in IDIOMAS else idioma_de(l, emp_id)
    texto, info = agente.redactar_mensaje(l, canal, empresas.icp_de(emp_id), idioma=idioma, perfil=empresas.perfil_de(emp_id))
    return {"lead_id": lead_id, "canal": canal, "idioma": idioma, "texto": texto, **info}


@app.post("/api/respuesta")
def api_respuesta(request: Request, entrada: RespuestaEntrada):
    """Registra una respuesta libre (WhatsApp, llamada manual): el agente la clasifica."""
    emp_id = empresa_de(request)
    with sesion() as s:
        l = s.get(Lead, entrada.lead_id)
        if not l or l.empresa_id != emp_id:
            return JSONResponse({"error": "no existe"}, status_code=404)
    return pipeline.registrar_respuesta_texto(entrada.lead_id, entrada.texto, entrada.canal)


@app.post("/api/lote")
def api_lote(request: Request, entrada: LoteEntrada):
    emp_id = empresa_de(request)
    quien = usuario_de(request).get("email") if cognito.activo else entrada.usuario
    r = pipeline.preparar_lote(n=entrada.n, modo=entrada.modo, reparto=entrada.reparto, usuario=quien or entrada.usuario,
                               motivo_override=entrada.motivo_override, empresa_id=emp_id)
    if "lote_id" in r:
        r["envio"] = pipeline.ejecutar_lote(r["lote_id"])
    return r


@app.get("/api/lotes")
def api_lotes(request: Request, limite: int = 50):
    with sesion() as s:
        lotes = s.exec(select(Lote).where(Lote.empresa_id == empresa_de(request)).order_by(Lote.id.desc()).limit(limite)).all()
    return [l.model_dump() for l in lotes]


@app.get("/api/bitacora")
def api_bitacora(request: Request, limite: int = 100, tipo: str = ""):
    with sesion() as s:
        st = select(Bitacora).where(Bitacora.empresa_id == empresa_de(request)).order_by(Bitacora.id.desc()).limit(limite)
        if tipo:
            st = st.where(Bitacora.tipo == tipo)
        return [b.model_dump() for b in s.exec(st).all()]


@app.get("/api/icp")
def api_icp(request: Request):
    emp = empresas.obtener(empresa_de(request))
    return {"icp": empresas.icp_de(empresa_de(request)).__dict__, "texto": emp.icp_texto if emp else ""}


@app.put("/api/icp")
def api_icp_guardar(request: Request, entrada: dict):
    icp = ICP(**{k: v for k, v in entrada.items() if k in ICP.__dataclass_fields__})
    empresas.guardar_icp(empresa_de(request), icp, entrada.get("texto"))
    return icp.__dict__


@app.post("/api/icp/interpretar")
def api_icp_interpretar(request: Request, entrada: TextoEntrada):
    """El agente convierte el texto de la empresa en criterios; se guarda como ICP de la empresa."""
    icp, info = agente.interpretar_icp(entrada.texto)
    empresas.guardar_icp(empresa_de(request), icp, entrada.texto)
    return {"icp": icp.__dict__, **info}


@app.post("/api/puntuar")
def api_puntuar(request: Request, todos: bool = False):
    """Puntúa el ICP de los leads pendientes (o todos) con el ICP actual de la empresa."""
    from ..icp import puntuar
    emp_id = empresa_de(request)
    icp = empresas.icp_de(emp_id)
    with sesion() as s:
        st = select(Lead).where(Lead.empresa_id == emp_id, Lead.duplicado_de.is_(None))
        if not todos:
            st = st.where(Lead.icp_estado == "pendiente")
        leads = list(s.exec(st))
        r = puntuar(leads, icp)
        for l in leads:
            s.add(l)
        s.commit()
    return {"puntuados": len(leads), **r}


@app.post("/api/sincronizar")
def api_sincronizar(request: Request):
    emp_id = empresa_de(request)
    return {"calificador": pipeline.pasar_a_dapta_los_que_respondieron(emp_id), "dapta": pipeline.sincronizar_dapta(empresa_id=emp_id),
            "whatsapp": pipeline.sincronizar_chats(empresa_id=emp_id)}


@app.post("/api/simular")
def api_simular(request: Request):
    return pipeline.simular_resultados(empresa_id=empresa_de(request))


# ---------------- Empresa, usuarios y notificaciones ----------------

@app.get("/api/empresa")
def api_empresa(request: Request):
    e = empresas.obtener(empresa_de(request))
    return empresas.publico(e) if e else JSONResponse({"error": "no existe"}, status_code=404)


@app.put("/api/empresa")
def api_empresa_cambiar(request: Request, entrada: EmpresaCambio):
    emp_id = empresa_de(request)
    antes = bool(empresas.config_de(emp_id).get("respetar_ley_2300", True))
    e = empresas.actualizar(emp_id, **entrada.model_dump(exclude_none=True))
    if not e:
        return JSONResponse({"error": "no existe"}, status_code=404)
    salida = empresas.publico(e)
    despues = bool(empresas.config_de(emp_id).get("respetar_ley_2300", True))
    if despues != antes:
        # Potestad de la empresa: queda en la bitácora con el usuario y se aplica al horario de la secuencia de Dapta.
        salida["ley_2300"] = pipeline.aplicar_horario_dapta(emp_id, despues, usuario_de(request).get("email", ""))
    return salida


@app.get("/api/empresas")
def api_empresas(request: Request):
    if not es_superadmin(request):
        return JSONResponse({"error": "solo el superadmin de la plataforma"}, status_code=403)
    return [empresas.publico(e) for e in empresas.listar()]


@app.post("/api/empresas")
def api_empresa_crear(request: Request, entrada: EmpresaEntrada):
    if not es_superadmin(request):
        return JSONResponse({"error": "solo el superadmin de la plataforma"}, status_code=403)
    icp, info = agente.interpretar_icp(entrada.icp_texto) if entrada.icp_texto else (ICP(), {"motor": "defecto"})
    e = empresas.crear(entrada.nombre, entrada.correo_notificaciones, entrada.icp_texto, icp.__dict__)
    return {**empresas.publico(e), "icp_motor": info.get("motor")}


@app.post("/api/registro")
def api_registro(entrada: RegistroEntrada):
    """Registro propio (público): crea la empresa y su primer usuario como admin de esa empresa, con clave definitiva, y entra de inmediato.
    La empresa y el rol los fija el servidor con APIs de administrador de Cognito; el cliente no puede escribirlos."""
    if not cognito.activo:
        return JSONResponse({"error": "Cognito no está configurado"}, status_code=400)
    email = entrada.email.strip().lower()
    nombre = " ".join(entrada.empresa.split())
    if "@" not in email or "." not in email.split("@")[-1]:
        return JSONResponse({"error": "correo inválido"}, status_code=400)
    if len(nombre) < 2:
        return JSONResponse({"error": "el nombre de la empresa es muy corto"}, status_code=400)
    problema = auth.validar_clave(entrada.clave)
    if problema:
        return JSONResponse({"error": problema}, status_code=400)
    import boto3
    c = boto3.client("cognito-idp", region_name=config.aws_region)
    try:
        c.admin_get_user(UserPoolId=cognito.pool_id, Username=email)
        return JSONResponse({"error": "ese correo ya tiene cuenta: entre con su clave o use 'Olvidé mi clave'"}, status_code=409)
    except c.exceptions.UserNotFoundException:
        pass
    texto_icp = entrada.icp_texto.strip()
    icp, _info = agente.interpretar_icp(texto_icp) if texto_icp else (ICP(), {"motor": "defecto"})
    e = empresas.crear(nombre, email, texto_icp, icp.__dict__)
    rues = entrada.rues or {}
    if entrada.nit.strip() or rues:
        perfil_inicial = {"nombre": nombre, "nit": (entrada.nit or rues.get("nit") or "").strip(), "ciudad": rues.get("ciudad", ""), "sector": rues.get("sector", ""),
                          "razon_social": rues.get("razon_social", ""), "ciiu": rues.get("ciiu", "")}
        empresas.actualizar(e.id, config={**empresas.config_de(e.id), "perfil": perfil_inicial})
    try:
        c.admin_create_user(UserPoolId=cognito.pool_id, Username=email, MessageAction="SUPPRESS",
                            UserAttributes=[{"Name": "email", "Value": email}, {"Name": "email_verified", "Value": "true"},
                                            {"Name": "custom:empresa_id", "Value": str(e.id)}, {"Name": "custom:rol", "Value": "admin"}])
        c.admin_set_user_password(UserPoolId=cognito.pool_id, Username=email, Password=entrada.clave, Permanent=True)
    except Exception as ex:  # noqa: BLE001
        return JSONResponse({"error": f"Cognito: {str(ex)[:200]}"}, status_code=400)
    anotar("registro", f"Empresa {e.id} '{nombre}' registrada por {email} (admin)", e.id, email=email)
    return {"ok": True, "empresa_id": e.id, "email": email}


class NitEntrada(BaseModel):
    nit: str


class SitioEntrada(BaseModel):
    url: str


class SugerenciaEntrada(BaseModel):
    nombre: str = ""
    rues: dict | None = None
    sitio: dict | None = None
    notas: str = ""


class AsistenteEntrada(BaseModel):
    mensaje: str = ""
    estado: dict | None = None


@app.post("/api/asistente")
def api_asistente(request: Request, entrada: AsistenteEntrada):
    """Asistente de inicio por chat: cómo se presenta la empresa, su cliente ideal y el costo por pauta, en cuatro turnos."""
    from .. import asistente
    return asistente.responder(empresa_de(request), entrada.mensaje, entrada.estado)


@app.post("/api/nit")
def api_nit(entrada: NitEntrada):
    """Público (sirve en el registro): la empresa en el RUES por NIT, para llenar nombre, ciudad y sector sin escribirlos."""
    from .. import perfil
    datos = perfil.buscar_nit(entrada.nit)
    if not datos:
        return JSONResponse({"error": "ese NIT no aparece en el RUES; puede escribir los datos a mano"}, status_code=404)
    return datos


@app.post("/api/empresa/sitio")
def api_empresa_sitio(request: Request, entrada: SitioEntrada):
    """Lee la página principal de la empresa (título, descripción, texto) para que el agente proponga el perfil."""
    from .. import perfil
    r = perfil.leer_sitio(entrada.url)
    if r.get("error"):
        return JSONResponse(r, status_code=400)
    return {**r, "texto": r["texto"][:600]}


@app.post("/api/empresa/sugerir")
def api_empresa_sugerir(request: Request, entrada: SugerenciaEntrada):
    """Propuesta guiada del perfil comercial y del cliente ideal a partir del RUES, la página y las notas; la persona corrige y guarda."""
    from .. import perfil
    sitio = entrada.sitio
    if sitio and sitio.get("url") and not sitio.get("texto"):
        sitio = {**sitio, **{k: v for k, v in perfil.leer_sitio(sitio["url"]).items() if k == "texto"}}
    sugerido, info = perfil.sugerir(entrada.nombre, entrada.rues, sitio, entrada.notas)
    return {"sugerencia": sugerido, **info}


@app.post("/api/usuarios")
def api_usuario_crear(request: Request, entrada: UsuarioEntrada):
    """Crea un usuario en Cognito con su empresa y rol. Un admin solo agrega gente a su propia empresa (usuario o admin);
    el superadmin a cualquier empresa. Cognito le envía la contraseña temporal por correo."""
    if not es_admin(request):
        return JSONResponse({"error": "solo administradores"}, status_code=403)
    if not cognito.activo:
        return JSONResponse({"error": "Cognito no está configurado"}, status_code=400)
    empresa_id, rol = entrada.empresa_id, entrada.rol
    if not es_superadmin(request):
        empresa_id = empresa_de(request)
        if rol not in ("usuario", "admin"):
            rol = "usuario"
    elif rol not in ("usuario", "admin", "superadmin"):
        rol = "usuario"
    import boto3
    c = boto3.client("cognito-idp", region_name=config.aws_region)
    try:
        c.admin_create_user(UserPoolId=cognito.pool_id, Username=entrada.email,
                            UserAttributes=[{"Name": "email", "Value": entrada.email}, {"Name": "email_verified", "Value": "true"},
                                            {"Name": "custom:empresa_id", "Value": str(empresa_id)}, {"Name": "custom:rol", "Value": rol}],
                            DesiredDeliveryMediums=["EMAIL"])
        anotar("usuario", f"Usuario {entrada.email} creado con rol {rol} por {usuario_de(request).get('email')}", empresa_id, rol=rol)
        return {"ok": True, "email": entrada.email, "empresa_id": empresa_id, "rol": rol}
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": str(e)[:300]}, status_code=400)


@app.get("/api/notificaciones")
def api_notificaciones(request: Request, no_leidas: bool = False, limite: int = 50):
    return [n.model_dump() for n in notificaciones.listar(empresa_de(request), no_leidas, limite)]


@app.post("/api/notificaciones/leer")
def api_notificaciones_leer(request: Request, id: int | None = None):
    return {"marcadas": notificaciones.marcar_leida(empresa_de(request), id)}


# ---------------- Archivos: S3 con URL prefirmadas (o local sin bucket) ----------------

@app.post("/api/archivos/url-subida")
def api_url_subida(entrada: ArchivoEntrada):
    """Devuelve la URL prefirmada (PUT, 15 min) y la clave. El navegador sube directo a S3; luego llama a /api/archivos/procesar."""
    return storage.Almacen().url_subida(entrada.nombre, entrada.content_type)


@app.post("/api/archivos/subir-local")
async def api_subir_local(clave: str = Form(...), archivo: UploadFile = File(...)):
    """Solo sin bucket: recibe el archivo en el servidor bajo la clave acordada."""
    datos = await archivo.read()
    storage.Almacen().guardar(clave, datos, archivo.content_type or "application/octet-stream")
    return {"clave": clave, "bytes": len(datos)}


@app.post("/api/archivos/procesar")
def api_procesar(request: Request, entrada: ProcesarEntrada):
    """Procesa un archivo ya subido: leads_csv (lista propia de la empresa) o rne (lista de exclusión de la CRC)."""
    alm = storage.Almacen()
    if not alm.existe(entrada.clave):
        return JSONResponse({"error": "la clave no existe en el almacén"}, status_code=404)
    datos = alm.leer(entrada.clave)
    if entrada.tipo == "leads_csv":
        return ingerir_csv(datos, entrada.clave.rsplit("/", 1)[-1], pais=entrada.pais, empresa_id=empresa_de(request))
    if entrada.tipo == "rne":
        import tempfile
        with tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False) as f:
            f.write(datos)
            ruta = f.name
        return {"excluidos_cargados": cargar_rne_csv(ruta)}
    return JSONResponse({"error": "tipo desconocido: leads_csv | rne"}, status_code=400)


@app.get("/api/exportar/{tipo}")
def api_exportar(request: Request, tipo: str):
    """Genera el CSV (leads | intentos | bitacora), lo guarda y devuelve la URL de descarga con vencimiento."""
    try:
        return storage.exportar(tipo, empresa_de(request))
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.get("/api/archivos/local/{clave:path}")
def api_archivo_local(clave: str):
    try:
        ruta = storage.ruta_local(clave)
    except ValueError:
        return JSONResponse({"error": "clave inválida"}, status_code=400)
    if not ruta.exists():
        return JSONResponse({"error": "no existe"}, status_code=404)
    return FileResponse(str(ruta), filename=ruta.name)
