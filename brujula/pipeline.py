"""Orquestación: preparar un lote (manual o con la brújula), ejecutarlo por canal, registrar respuestas y sincronizar con Dapta."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlmodel import select

from .bandit import Brazo, repartir
from .channels import canal as canal_de
from .compliance import anotar, esta_excluido, registrar_exclusion, ventana_permitida, verificar_lead
from .config import config
from .db import sesion
from .models import Calificacion, Intento, Lead, Lote

CANALES_ACTIVOS = ("voz", "correo")   # whatsapp entra cuando exista línea aprobada


def _brazos(s) -> list[Brazo]:
    leads = s.exec(select(Lead).where(Lead.duplicado_de.is_(None), Lead.icp_estado == "pasa", Lead.estado == "listo")).all()
    intentos = s.exec(select(Intento)).all()
    lead_por_id = {l.id: l for l in s.exec(select(Lead).where(Lead.duplicado_de.is_(None))).all()}
    calificados = {c.lead_id for c in s.exec(select(Calificacion).where(Calificacion.resultado == "calificado")).all()}
    hay_calificaciones = bool(calificados)
    brazos: dict[str, Brazo] = {}
    for l in leads:
        for c in CANALES_ACTIVOS:
            if c in (l.canales or []):
                b = brazos.setdefault(f"{l.fuente_clave}|{c}", Brazo(l.fuente_clave, c))
                b.disponibles += 1
    for it in intentos:
        l = lead_por_id.get(it.lead_id)
        if not l or it.canal not in CANALES_ACTIVOS:
            continue
        b = brazos.setdefault(f"{l.fuente_clave}|{it.canal}", Brazo(l.fuente_clave, it.canal))
        if it.estado in ("programado", "fallido"):
            continue
        b.intentos += 1
        b.costo_usd += it.costo_usd
        exito = (it.lead_id in calificados) if hay_calificaciones else (it.estado in ("respondio", "contestado") or it.clasificacion in ("interesado", "no_interesado", "despues"))
        b.exitos += 1 if exito else 0
    return list(brazos.values())


def preparar_lote(n: int = 20, modo: str = "brujula", reparto: dict[str, int] | None = None, usuario: str = "",
                  motivo_override: str = "") -> dict:
    """Crea el lote y sus intentos (programados). Respeta la ventana legal salvo override explícito con motivo."""
    permitido, razon = ventana_permitida()
    fuera = not permitido
    if fuera and not motivo_override:
        return {"error": f"No se puede contactar ahora: {razon}. Para hacerlo igual, pase un motivo de override.", "fuera_ventana": True}
    with sesion() as s:
        brazos = _brazos(s)
        if modo == "brujula" or not reparto:
            reparto, explicacion = repartir(brazos, n)
        else:
            explicacion = "Reparto manual: " + ", ".join(f"{k} {v}" for k, v in reparto.items())
        if not reparto:
            return {"error": "No hay leads listos con canal disponible. Corra fetch y score primero."}
        lote = Lote(reparto=reparto, explicacion=explicacion, modo=modo, fuera_ventana=fuera, override_motivo=motivo_override, override_usuario=usuario)
        s.add(lote)
        s.commit()
        s.refresh(lote)
        creados = 0
        omitidos = defaultdict(int)
        for clave, cupo in reparto.items():
            fuente, canal = clave.split("|", 1)
            leads = s.exec(select(Lead).where(Lead.duplicado_de.is_(None), Lead.icp_estado == "pasa", Lead.estado == "listo",
                                              Lead.fuente_clave == fuente).order_by(Lead.icp_score.desc(), Lead.id)).all()
            for l in leads:
                if cupo <= 0:
                    break
                if canal not in (l.canales or []):
                    continue
                ok, por_que = verificar_lead(l, canal)
                if not ok:
                    omitidos[por_que] += 1
                    continue
                s.add(Intento(lead_id=l.id, lote_id=lote.id, canal=canal, estado="programado", fuera_ventana=fuera))
                l.estado = "contactado"
                l.actualizado_en = datetime.utcnow()
                s.add(l)
                cupo -= 1
                creados += 1
        s.commit()
        if fuera:
            anotar("override", f"Lote {lote.id} fuera de la ventana de la Ley 2300", lote_id=lote.id, usuario=usuario, motivo=motivo_override, contactos=creados, razon=razon)
        anotar("reparto", explicacion, lote_id=lote.id, reparto=reparto, modo=modo)
        return {"lote_id": lote.id, "reparto": reparto, "explicacion": explicacion, "intentos": creados, "omitidos": dict(omitidos),
                "fuera_ventana": fuera, "ventana": razon}


def ejecutar_lote(lote_id: int) -> dict:
    """Envía los intentos programados del lote por su canal y guarda estado, costo y referencia."""
    canales = {}
    resumen = defaultdict(int)
    with sesion() as s:
        intentos = s.exec(select(Intento).where(Intento.lote_id == lote_id, Intento.estado == "programado")).all()
        for it in intentos:
            l = s.get(Lead, it.lead_id)
            c = canales.setdefault(it.canal, canal_de(it.canal))
            r = c.enviar(l, it)
            it.estado = r.estado
            it.costo_usd = r.costo_usd
            it.ref_externa = r.ref_externa
            it.proveedor = r.proveedor
            it.mensaje = r.mensaje
            it.detalle = {**(it.detalle or {}), **r.detalle}
            it.enviado_en = datetime.utcnow() if r.estado != "fallido" else None
            s.add(it)
            resumen[f"{it.canal}:{r.estado}:{r.proveedor}"] += 1
        s.commit()
    return {"lote_id": lote_id, "resultado": dict(resumen)}


def registrar_respuesta_token(token: str, valor: str) -> dict:
    """Clic en el correo: si | no | baja."""
    with sesion() as s:
        it = s.exec(select(Intento).where(Intento.canal == "correo")).all()
        it = next((x for x in it if (x.detalle or {}).get("token") == token), None)
        if not it:
            return {"error": "token desconocido"}
        l = s.get(Lead, it.lead_id)
        it.respondido_en = datetime.utcnow()
        if valor == "si":
            it.estado, it.clasificacion = "respondio", "interesado"
            l.estado = "respondio"
        elif valor == "no":
            it.estado, it.clasificacion = "respondio", "no_interesado"
            l.estado = "respondio"
        else:
            it.estado, it.clasificacion = "baja", "baja"
            l.estado = "baja"
            registrar_exclusion(l.correo or "", "baja")
            if l.telefono:
                registrar_exclusion(l.telefono, "baja")
        s.add(it)
        s.add(l)
        s.commit()
        return {"lead_id": l.id, "empresa": l.razon_social, "valor": valor}


def registrar_evento_correo(ref_externa: str, tipo: str) -> bool:
    """Eventos de Resend: email.delivered, email.opened, email.clicked, email.bounced."""
    mapa = {"email.delivered": "entregado", "email.opened": "abierto", "email.clicked": "abierto", "email.bounced": "fallido", "email.complained": "baja"}
    nuevo = mapa.get(tipo)
    if not nuevo:
        return False
    with sesion() as s:
        it = s.exec(select(Intento).where(Intento.ref_externa == ref_externa)).first()
        if not it:
            return False
        orden = ["programado", "enviado", "entregado", "abierto", "respondio"]
        if it.estado in ("respondio", "baja"):
            return True
        if nuevo == "baja":
            it.estado = "baja"
            l = s.get(Lead, it.lead_id)
            registrar_exclusion(l.correo or "", "baja")
        elif nuevo == "fallido" or orden.index(nuevo) > orden.index(it.estado if it.estado in orden else "programado"):
            it.estado = nuevo
        s.add(it)
        s.commit()
        return True


def pasar_a_dapta_los_que_respondieron() -> dict:
    """Los que respondieron por correo o WhatsApp entran al calificador de Dapta (la secuencia del agente)."""
    voz = canal_de("voz")
    enviados, omitidos = 0, 0
    with sesion() as s:
        leads = s.exec(select(Lead).where(Lead.estado == "respondio", Lead.telefono.is_not(None))).all()
        for l in leads:
            ya = s.exec(select(Calificacion).where(Calificacion.lead_id == l.id)).first()
            if ya or esta_excluido(l.telefono):
                omitidos += 1
                continue
            it = Intento(lead_id=l.id, canal="voz", estado="programado", detalle={"motivo": "calificacion"})
            s.add(it)
            s.commit()
            s.refresh(it)
            r = voz.enviar(l, it)
            it.estado, it.costo_usd, it.ref_externa, it.proveedor, it.mensaje = r.estado, r.costo_usd, r.ref_externa, r.proveedor, r.mensaje
            it.detalle = {**it.detalle, **r.detalle}
            it.enviado_en = datetime.utcnow()
            s.add(it)
            s.add(Calificacion(lead_id=l.id, intento_id=it.id, resultado="pendiente", ref_externa=r.ref_externa, datos={"via": r.proveedor}))
            s.commit()
            enviados += 1
    return {"enviados_a_dapta": enviados, "omitidos": omitidos, "modo": "real" if voz.real else "simulado"}


def sincronizar_dapta(limite: int = 200) -> dict:
    """Lee las llamadas del agente de Dapta y actualiza intentos (estado, duración, costo real) y calificaciones."""
    from .channels.voz_dapta import CanalVozDapta
    voz = CanalVozDapta()
    if not voz.real:
        return {"error": "Dapta no configurado (clave, agente o secuencia)."}
    agente = voz.ids["agent_id"]
    llamadas = voz.mcp.llamadas(agente, limit=limite)
    filas = llamadas.get("calls") or llamadas.get("rows") or []
    actualizados, nuevas_cali = 0, 0
    with sesion() as s:
        for c in filas:
            tel = c.get("to_number") or c.get("phone") or c.get("contact_phone") or ""
            if not tel:
                continue
            it = s.exec(select(Intento).where(Intento.canal == "voz", Intento.ref_externa == tel).order_by(Intento.id.desc())).first()
            if not it:
                l = s.exec(select(Lead).where(Lead.telefono == tel)).first()
                if not l:
                    continue
                it = Intento(lead_id=l.id, canal="voz", estado="programado", ref_externa=tel, proveedor="dapta")
                s.add(it)
                s.commit()
                s.refresh(it)
            razon = (c.get("disconnect_reason") or c.get("disconnection_reason") or "").lower()
            dur = int(c.get("duration_seconds") or c.get("duration") or 0)
            if "voicemail" in razon:
                it.estado = "buzon"
            elif dur > 0 or "user_hangup" in razon or "agent_hangup" in razon:
                it.estado = "contestado"
            else:
                it.estado = "no_contesta"
            it.duracion_seg = dur
            it.costo_usd = voz.costo_llamada(c)
            it.detalle = {**(it.detalle or {}), "call_id": c.get("call_id") or c.get("id"), "razon": razon, "resumen": c.get("call_summary") or c.get("summary", "")}
            it.enviado_en = it.enviado_en or datetime.utcnow()
            an = c.get("call_analysis") or c.get("custom_analysis_data") or {}
            exito = c.get("call_successful")
            if isinstance(an, dict) and an:
                it.clasificacion = "interesado" if str(an.get("interesado", "")).lower() in ("true", "si", "sí", "yes") else it.clasificacion
                if str(an.get("baja", "")).lower() in ("true", "si", "sí", "yes"):
                    it.clasificacion = "baja"
                    l = s.get(Lead, it.lead_id)
                    l.estado = "baja"
                    registrar_exclusion(l.telefono or "", "baja")
                    s.add(l)
            if it.estado == "contestado":
                l = s.get(Lead, it.lead_id)
                if l.estado in ("contactado", "listo"):
                    l.estado = "respondio"
                    s.add(l)
                cali = s.exec(select(Calificacion).where(Calificacion.lead_id == it.lead_id)).first()
                if exito is not None:
                    res = "calificado" if exito else "no_calificado"
                    if not cali:
                        cali = Calificacion(lead_id=it.lead_id, intento_id=it.id, ref_externa=it.detalle.get("call_id"))
                        nuevas_cali += 1
                    cali.resultado = res
                    cali.datos = an if isinstance(an, dict) else {"analisis": an}
                    s.add(cali)
                    l.estado = res
                    s.add(l)
            s.add(it)
            actualizados += 1
        s.commit()
    return {"llamadas_leidas": len(filas), "intentos_actualizados": actualizados, "calificaciones_nuevas": nuevas_cali}


def simular_resultados(semilla: int = 7) -> dict:
    """Solo para demos sin credenciales: inventa respuestas y calificaciones plausibles sobre los intentos simulados."""
    import random
    rnd = random.Random(semilla)
    tasas = {"correo": (0.08, 0.35), "voz": (0.30, 0.45), "whatsapp": (0.15, 0.40)}   # (responde, califica si respondió)
    n_resp, n_cali = 0, 0
    with sesion() as s:
        intentos = s.exec(select(Intento).where(Intento.proveedor == "simulado", Intento.estado.in_(["enviado", "programado"]))).all()
        for it in intentos:
            pr, pc = tasas.get(it.canal, (0.1, 0.3))
            l = s.get(Lead, it.lead_id)
            if it.canal == "voz":
                contesto = rnd.random() < 0.55
                it.estado = "contestado" if contesto else ("buzon" if rnd.random() < 0.3 else "no_contesta")
                it.duracion_seg = rnd.randint(40, 240) if contesto else 0
                it.costo_usd = (-(-it.duracion_seg // 60)) * config.tarifas.voz_minuto_contestado if contesto else (config.tarifas.voz_buzon if it.estado == "buzon" else config.tarifas.voz_no_contesta)
                responde = contesto and rnd.random() < (pr / 0.55)
            else:
                responde = rnd.random() < pr
            if responde:
                it.estado = "respondio" if it.canal != "voz" else it.estado
                it.clasificacion = "interesado" if rnd.random() < 0.6 else "no_interesado"
                it.respondido_en = datetime.utcnow()
                l.estado = "respondio"
                n_resp += 1
                if rnd.random() < pc:
                    s.add(Calificacion(lead_id=l.id, intento_id=it.id, resultado="calificado", costo_usd=0.0 if it.canal == "voz" else 2 * config.tarifas.voz_minuto_contestado, datos={"simulado": True}))
                    l.estado = "calificado"
                    n_cali += 1
                elif it.clasificacion == "interesado":
                    s.add(Calificacion(lead_id=l.id, intento_id=it.id, resultado="no_calificado", costo_usd=0.0 if it.canal == "voz" else 2 * config.tarifas.voz_minuto_contestado, datos={"simulado": True}))
                    l.estado = "no_calificado"
            s.add(it)
            s.add(l)
        s.commit()
    return {"simulados": len(intentos), "respondieron": n_resp, "calificados": n_cali}
