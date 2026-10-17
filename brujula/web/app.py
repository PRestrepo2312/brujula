"""Tablero y webhooks de Brújula (FastAPI + Jinja2)."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import func, select

from .. import metrics, pipeline
from ..compliance import ahora_local, proxima_ventana, ventana_permitida
from ..db import crear_tablas, sesion
from ..icp import ICP
from ..models import Bitacora, Intento, Lead, Lote

app = FastAPI(title="Brújula", docs_url="/api/docs")
plantillas = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
crear_tablas()


def ctx(request: Request, **extra) -> dict:
    ok, razon = ventana_permitida()
    return {"request": request, "ventana_ok": ok, "ventana_razon": razon, "ahora": ahora_local().strftime("%a %d %b, %H:%M"),
            "proxima": proxima_ventana().strftime("%a %d %b, %H:%M"), **extra}


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
def lote_nuevo(n: int = Form(20), modo: str = Form("brujula"), usuario: str = Form(""), motivo_override: str = Form("")):
    r = pipeline.preparar_lote(n=n, modo=modo, usuario=usuario, motivo_override=motivo_override)
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


@app.get("/api/metricas")
def api_metricas():
    return metrics.calcular()


@app.get("/api/leads")
def api_leads(limite: int = 200):
    with sesion() as s:
        filas = s.exec(select(Lead).where(Lead.duplicado_de.is_(None)).order_by(Lead.icp_score.desc()).limit(limite)).all()
    return [{k: v for k, v in l.model_dump().items() if k != "crudo"} for l in filas]


@app.get("/api/estado")
def api_estado():
    with sesion() as s:
        n = s.exec(select(func.count(Lead.id))).one()
    ok, razon = ventana_permitida()
    return {"leads": n, "ventana_ok": ok, "razon": razon, "ahora": ahora_local().isoformat()}
