"""Tablero y webhooks de Brújula (FastAPI + Jinja2)."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlmodel import func, select

from .. import auth, metrics, pipeline, storage
from ..compliance import ahora_local, cargar_rne_csv, proxima_ventana, ventana_permitida
from ..config import config
from ..db import crear_tablas, sesion
from ..icp import ICP
from ..ingest import ingerir_csv
from ..models import Bitacora, Calificacion, Intento, Lead, Lote

app = FastAPI(title="Brújula", docs_url="/api/docs", openapi_url="/api/openapi.json",
              description="API de Brújula: fuentes, leads, lotes, métricas, archivos y webhooks. Un front separado consume estas rutas con un JWT de Cognito.")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in config.cors_origins.split(",")], allow_methods=["*"], allow_headers=["*"])
plantillas = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
crear_tablas()
cognito = auth.Cognito()


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
    return {"usuario": request.state.usuario, "login_activo": cognito.activo}


class LoteEntrada(BaseModel):
    n: int = 20
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


def ctx(request: Request, **extra) -> dict:
    ok, razon = ventana_permitida()
    usuario = getattr(request.state, "usuario", None) or {}
    return {"request": request, "ventana_ok": ok, "ventana_razon": razon, "ahora": ahora_local().strftime("%a %d %b, %H:%M"),
            "proxima": proxima_ventana().strftime("%a %d %b, %H:%M"), "usuario": usuario, "login_activo": cognito.activo, **extra}


@app.get("/", response_class=HTMLResponse)
def tablero(request: Request):
    m = metrics.calcular()
    with sesion() as s:
        lotes = s.exec(select(Lote).order_by(Lote.id.desc()).limit(8)).all()
        bitacora = s.exec(select(Bitacora).order_by(Bitacora.id.desc()).limit(12)).all()
    return plantillas.TemplateResponse("tablero.html", ctx(request, m=m, lotes=lotes, bitacora=bitacora, icp=ICP.cargar(), m_json=json.dumps(m)))


@app.get("/leads", response_class=HTMLResponse)
def leads(request: Request, estado: str = "", fuente: str = "", q: str = ""):
    with sesion() as s:
        st = select(Lead).where(Lead.duplicado_de.is_(None))
        if estado:
            st = st.where(Lead.icp_estado == estado) if estado in ("pasa", "revisar", "descarta", "pendiente") else st.where(Lead.estado == estado)
        if fuente:
            st = st.where(Lead.fuente_clave == fuente)
        if q:
            st = st.where(Lead.razon_social.contains(q.upper()))
        filas = s.exec(st.order_by(Lead.icp_score.desc(), Lead.id).limit(300)).all()
        fuentes = [r[0] for r in s.exec(select(Lead.fuente_clave).distinct()).all()]
    return plantillas.TemplateResponse("leads.html", ctx(request, leads=filas, fuentes=fuentes, estado=estado, fuente=fuente, q=q))


@app.get("/lead/{lead_id}", response_class=HTMLResponse)
def lead_detalle(request: Request, lead_id: int):
    with sesion() as s:
        l = s.get(Lead, lead_id)
        intentos = s.exec(select(Intento).where(Intento.lead_id == lead_id).order_by(Intento.id)).all()
        dup = s.exec(select(Lead).where(Lead.duplicado_de == lead_id)).all()
    return plantillas.TemplateResponse("lead.html", ctx(request, l=l, intentos=intentos, duplicados=dup))


@app.post("/lead/{lead_id}/revision")
def lead_revision(lead_id: int, decision: str = Form(...)):
    with sesion() as s:
        l = s.get(Lead, lead_id)
        if decision == "aprobar":
            l.icp_estado, l.estado = "pasa", "listo"
        else:
            l.icp_estado, l.estado = "descarta", "descartado"
        l.icp_detalle = {**(l.icp_detalle or {}), "revision_humana": decision}
        s.add(l)
        s.commit()
    return RedirectResponse(f"/lead/{lead_id}", status_code=303)


@app.post("/lote/nuevo")
def lote_nuevo(request: Request, n: int = Form(20), modo: str = Form("brujula"), usuario: str = Form(""), motivo_override: str = Form("")):
    quien = (getattr(request.state, "usuario", None) or {}).get("email") if cognito.activo else usuario
    r = pipeline.preparar_lote(n=n, modo=modo, usuario=quien or usuario, motivo_override=motivo_override)
    if "error" in r:
        return RedirectResponse(f"/?aviso={r['error']}", status_code=303)
    pipeline.ejecutar_lote(r["lote_id"])
    return RedirectResponse(f"/?lote={r['lote_id']}", status_code=303)


@app.post("/sincronizar")
def sincronizar():
    r1 = pipeline.pasar_a_dapta_los_que_respondieron()
    r2 = pipeline.sincronizar_dapta()
    return JSONResponse({"calificador": r1, "dapta": r2})


@app.post("/simular")
def simular():
    return JSONResponse(pipeline.simular_resultados())


@app.get("/r/{token}", response_class=HTMLResponse)
def respuesta_correo(request: Request, token: str, v: str = "no"):
    r = pipeline.registrar_respuesta_token(token, v if v in ("si", "no", "baja") else "no")
    return plantillas.TemplateResponse("gracias.html", ctx(request, r=r, v=v))


@app.post("/webhook/dapta")
async def webhook_dapta(request: Request):
    """Análisis post-llamada del agente de voz. Se guarda crudo y se concilia con sincronizar."""
    cuerpo = await request.json()
    with sesion() as s:
        s.add(Bitacora(tipo="webhook_dapta", mensaje="análisis post-llamada", datos=cuerpo if isinstance(cuerpo, dict) else {"cuerpo": cuerpo}))
        s.commit()
    try:
        pipeline.sincronizar_dapta(limite=50)
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
def cron_lote(request: Request, n: int = 20):
    """Lo llama EventBridge cada hora dentro de la ventana legal: la brújula reparte y envía el siguiente lote."""
    from ..config import config as cfg
    if cfg.cron_key and request.headers.get("x-cron-key") != cfg.cron_key:
        return JSONResponse({"error": "clave de cron inválida"}, status_code=401)
    r = pipeline.preparar_lote(n=n, modo="brujula")
    if "lote_id" in r:
        r["envio"] = pipeline.ejecutar_lote(r["lote_id"])
    return r


@app.post("/cron/sincronizar")
def cron_sincronizar(request: Request):
    from ..config import config as cfg
    if cfg.cron_key and request.headers.get("x-cron-key") != cfg.cron_key:
        return JSONResponse({"error": "clave de cron inválida"}, status_code=401)
    return {"calificador": pipeline.pasar_a_dapta_los_que_respondieron(), "dapta": pipeline.sincronizar_dapta()}


@app.get("/healthz")
def healthz():
    return {"ok": True}


# ---------------- API JSON (la consume el tablero de un front separado) ----------------

@app.get("/api/metricas")
def api_metricas():
    return metrics.calcular()


@app.get("/api/leads")
def api_leads(estado: str = "", fuente: str = "", q: str = "", limite: int = 200, pagina: int = 1):
    with sesion() as s:
        st = select(Lead).where(Lead.duplicado_de.is_(None))
        if estado:
            st = st.where(Lead.icp_estado == estado) if estado in ("pasa", "revisar", "descarta", "pendiente") else st.where(Lead.estado == estado)
        if fuente:
            st = st.where(Lead.fuente_clave == fuente)
        if q:
            st = st.where(Lead.razon_social.contains(q.upper()))
        filas = s.exec(st.order_by(Lead.icp_score.desc(), Lead.id).offset((pagina - 1) * limite).limit(limite)).all()
    return [{k: v for k, v in l.model_dump().items() if k != "crudo"} for l in filas]


@app.get("/api/lead/{lead_id}")
def api_lead(lead_id: int):
    with sesion() as s:
        l = s.get(Lead, lead_id)
        if not l:
            return JSONResponse({"error": "no existe"}, status_code=404)
        intentos = s.exec(select(Intento).where(Intento.lead_id == lead_id).order_by(Intento.id)).all()
        calis = s.exec(select(Calificacion).where(Calificacion.lead_id == lead_id)).all()
        dup = s.exec(select(Lead.id, Lead.razon_social, Lead.fuente_clave).where(Lead.duplicado_de == lead_id)).all()
    return {"lead": {k: v for k, v in l.model_dump().items() if k != "crudo"}, "intentos": [i.model_dump() for i in intentos],
            "calificaciones": [c.model_dump() for c in calis], "duplicados": [{"id": d[0], "razon_social": d[1], "fuente": d[2]} for d in dup]}


@app.post("/api/lead/{lead_id}/revision")
def api_lead_revision(lead_id: int, entrada: RevisionEntrada):
    lead_revision(lead_id, entrada.decision)
    return {"ok": True, "lead_id": lead_id, "decision": entrada.decision}


@app.post("/api/lote")
def api_lote(entrada: LoteEntrada):
    r = pipeline.preparar_lote(n=entrada.n, modo=entrada.modo, reparto=entrada.reparto, usuario=entrada.usuario, motivo_override=entrada.motivo_override)
    if "lote_id" in r:
        r["envio"] = pipeline.ejecutar_lote(r["lote_id"])
    return r


@app.get("/api/lotes")
def api_lotes(limite: int = 50):
    with sesion() as s:
        lotes = s.exec(select(Lote).order_by(Lote.id.desc()).limit(limite)).all()
    return [l.model_dump() for l in lotes]


@app.get("/api/bitacora")
def api_bitacora(limite: int = 100, tipo: str = ""):
    with sesion() as s:
        st = select(Bitacora).order_by(Bitacora.id.desc()).limit(limite)
        if tipo:
            st = st.where(Bitacora.tipo == tipo)
        return [b.model_dump() for b in s.exec(st).all()]


@app.get("/api/icp")
def api_icp():
    return ICP.cargar().__dict__


@app.put("/api/icp")
def api_icp_guardar(entrada: dict):
    icp = ICP(**{k: v for k, v in entrada.items() if k in ICP.__dataclass_fields__})
    icp.guardar()
    return icp.__dict__


@app.post("/api/sincronizar")
def api_sincronizar():
    return {"calificador": pipeline.pasar_a_dapta_los_que_respondieron(), "dapta": pipeline.sincronizar_dapta()}


@app.post("/api/simular")
def api_simular():
    return pipeline.simular_resultados()


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
def api_procesar(entrada: ProcesarEntrada):
    """Procesa un archivo ya subido: leads_csv (lista propia de la pyme) o rne (lista de exclusión de la CRC)."""
    alm = storage.Almacen()
    if not alm.existe(entrada.clave):
        return JSONResponse({"error": "la clave no existe en el almacén"}, status_code=404)
    datos = alm.leer(entrada.clave)
    if entrada.tipo == "leads_csv":
        return ingerir_csv(datos, entrada.clave.rsplit("/", 1)[-1], pais=entrada.pais)
    if entrada.tipo == "rne":
        import tempfile
        with tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False) as f:
            f.write(datos)
            ruta = f.name
        return {"excluidos_cargados": cargar_rne_csv(ruta)}
    return JSONResponse({"error": "tipo desconocido: leads_csv | rne"}, status_code=400)


@app.get("/api/exportar/{tipo}")
def api_exportar(tipo: str):
    """Genera el CSV (leads | intentos | bitacora), lo guarda y devuelve la URL de descarga con vencimiento."""
    try:
        return storage.exportar(tipo)
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


@app.get("/api/estado")
def api_estado():
    with sesion() as s:
        n = s.exec(select(func.count(Lead.id))).one()
    ok, razon = ventana_permitida()
    return {"leads": n, "ventana_ok": ok, "razon": razon, "ahora": ahora_local().isoformat()}
