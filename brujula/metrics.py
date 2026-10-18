"""Las tres métricas con su nombre, por fuente y por canal, y el embudo del evento.

- Costo por lead encontrado (por fuente): descargar, enriquecer y puntuar ÷ leads del perfil que salieron de esa fuente.
- CPL (por canal, y por fuente × canal): todo lo gastado ÷ leads que respondieron.
- CPLQ: lo mismo ÷ leads que Dapta calificó.
- Speed-to-lead: minutos entre encontrar el lead y el primer intento.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlmodel import select

from .db import sesion
from .models import Calificacion, Costo, Intento, Lead

RESPONDIO = {"respondio", "contestado"}
NO_ENVIADO = ("programado", "fallido", "omitido", "cancelado")   # intentos que no llegaron a nadie: no cuentan como contacto
CLASIF_RESPUESTA = {"interesado", "no_interesado", "despues", "equivocado"}


def _div(a: float, b: float) -> float | None:
    return round(a / b, 4) if b else None


def calcular(empresa_id: int = 1) -> dict:
    with sesion() as s:
        leads = s.exec(select(Lead).where(Lead.duplicado_de.is_(None), Lead.empresa_id == empresa_id)).all()
        intentos = s.exec(select(Intento).where(Intento.empresa_id == empresa_id)).all()
        calis = s.exec(select(Calificacion).where(Calificacion.empresa_id == empresa_id)).all()
        costos = s.exec(select(Costo).where(Costo.empresa_id == empresa_id)).all()
    lead_por_id = {l.id: l for l in leads}
    calificados = {c.lead_id for c in calis if c.resultado == "calificado"}
    no_calificados = {c.lead_id for c in calis if c.resultado == "no_calificado"}
    costo_cali = defaultdict(float)
    for c in calis:
        costo_cali[c.lead_id] += c.costo_usd

    # --- por fuente: encontrar ---
    fuentes = defaultdict(lambda: {"encontrados": 0, "del_perfil": 0, "con_telefono": 0, "con_correo": 0, "costo_encontrar_usd": 0.0})
    for l in leads:
        f = fuentes[l.fuente_clave]
        f["encontrados"] += 1
        f["del_perfil"] += 1 if l.icp_estado == "pasa" else 0
        f["con_telefono"] += 1 if l.telefono else 0
        f["con_correo"] += 1 if l.correo else 0
        f["costo_encontrar_usd"] += l.costo_encontrar_usd
    for c in costos:
        if c.concepto in ("jev", "enriquecer") and c.fuente_clave in fuentes:
            fuentes[c.fuente_clave]["costo_encontrar_usd"] += c.usd
    for k, f in fuentes.items():
        f["costo_encontrar_usd"] = round(f["costo_encontrar_usd"], 4)
        f["costo_por_lead_encontrado"] = _div(f["costo_encontrar_usd"], f["del_perfil"])

    # --- por canal y por fuente × canal: contactar ---
    def vacio():
        return {"intentos": 0, "enviados": 0, "respondieron": 0, "interesados": 0, "bajas": 0, "calificados": 0, "no_calificados": 0,
                "costo_usd": 0.0, "speed_min": [], "fuera_ventana": 0}
    canales = defaultdict(vacio)
    cruces = defaultdict(vacio)
    leads_resp_por_canal = defaultdict(set)
    leads_resp_por_cruce = defaultdict(set)
    for it in intentos:
        l = lead_por_id.get(it.lead_id)
        if not l:
            continue
        for d, llave in ((canales, it.canal), (cruces, f"{l.fuente_clave}|{it.canal}")):
            x = d[llave]
            x["intentos"] += 1
            x["enviados"] += 1 if it.estado not in NO_ENVIADO else 0
            x["costo_usd"] += it.costo_usd
            x["fuera_ventana"] += 1 if it.fuera_ventana else 0
            if it.estado in RESPONDIO or it.clasificacion in CLASIF_RESPUESTA:
                (leads_resp_por_canal if d is canales else leads_resp_por_cruce)[llave].add(it.lead_id)
            if it.clasificacion == "interesado":
                x["interesados"] += 1
            if it.clasificacion == "baja" or it.estado == "baja":
                x["bajas"] += 1
            if it.enviado_en and l.creado_en:
                x["speed_min"].append(max(0.0, (it.enviado_en - l.creado_en).total_seconds() / 60.0))
    for d, resp in ((canales, leads_resp_por_canal), (cruces, leads_resp_por_cruce)):
        for llave, x in d.items():
            ids = resp.get(llave, set())
            x["respondieron"] = len(ids)
            x["calificados"] = len(ids & calificados)
            x["no_calificados"] = len(ids & no_calificados)
            x["costo_usd"] = round(x["costo_usd"] + sum(costo_cali[i] for i in ids), 4)
            x["cpl"] = _div(x["costo_usd"], x["respondieron"])
            x["cplq"] = _div(x["costo_usd"], x["calificados"])
            x["tasa_respuesta"] = _div(x["respondieron"], x["enviados"])
            x["tasa_calificacion"] = _div(x["calificados"], x["respondieron"])
            sp = x.pop("speed_min")
            x["speed_to_lead_min"] = round(sum(sp) / len(sp), 1) if sp else None

    # --- embudo ---
    contactados = {it.lead_id for it in intentos if it.estado not in NO_ENVIADO}
    respondieron = set().union(*leads_resp_por_canal.values()) if leads_resp_por_canal else set()
    embudo = {
        "encontrados": len(leads), "del_perfil": sum(1 for l in leads if l.icp_estado == "pasa"),
        "a_revisar": sum(1 for l in leads if l.icp_estado == "revisar"), "contactados": len(contactados),
        "respondieron": len(respondieron), "calificados": len(calificados), "no_calificados": len(no_calificados),
        "costo_total_usd": round(sum(it.costo_usd for it in intentos) + sum(c.usd for c in costos) + sum(costo_cali.values()), 4),
    }
    embudo["cpl_global"] = _div(embudo["costo_total_usd"], embudo["respondieron"])
    embudo["cplq_global"] = _div(embudo["costo_total_usd"], embudo["calificados"])

    # --- recomendación en una frase ---
    rec = recomendacion(cruces)
    # Brújula contra pauta: lo que la empresa dice que le cuesta hoy un lead por pauta (lo escribe ella en el asistente; no inventamos referencias).
    from .empresas import config_de
    pauta = config_de(empresa_id).get("costo_lead_pauta_usd")
    comparacion = None
    try:
        pauta = float(pauta) if pauta is not None else None
    except (TypeError, ValueError):
        pauta = None
    if pauta:
        brujula = embudo.get("cplq_global") or embudo.get("cpl_global")
        comparacion = {"pauta_usd": pauta, "brujula_usd": brujula, "base": "calificado" if embudo.get("cplq_global") else ("respuesta" if embudo.get("cpl_global") else None),
                       "veces": round(pauta / brujula, 1) if brujula else None}
    return {"calculado_en": datetime.utcnow().isoformat(timespec="seconds"), "embudo": embudo, "fuentes": dict(fuentes),
            "canales": dict(canales), "cruces": dict(cruces), "recomendacion": rec, "comparacion_pauta": comparacion}


def recomendacion(cruces: dict) -> str:
    con_cplq = [(k, v) for k, v in cruces.items() if v.get("cplq")]
    if len(con_cplq) >= 2:
        con_cplq.sort(key=lambda kv: kv[1]["cplq"])
        mejor, peor = con_cplq[0], con_cplq[-1]
        veces = peor[1]["cplq"] / mejor[1]["cplq"] if mejor[1]["cplq"] else 0
        return (f"Mejor por lead calificado: {mejor[0].replace('|', ' + ')} (USD {mejor[1]['cplq']:.2f}). "
                f"{peor[0].replace('|', ' + ')} cuesta {veces:.1f} veces más (USD {peor[1]['cplq']:.2f}): el siguiente lote va al mejor.")
    con_cpl = [(k, v) for k, v in cruces.items() if v.get("cpl")]
    if len(con_cpl) >= 2:
        con_cpl.sort(key=lambda kv: kv[1]["cpl"])
        return (f"Aún sin calificaciones. Por lead que respondió, lo más barato es {con_cpl[0][0].replace('|', ' + ')} "
                f"(USD {con_cpl[0][1]['cpl']:.2f}) y lo más caro {con_cpl[-1][0].replace('|', ' + ')} (USD {con_cpl[-1][1]['cpl']:.2f}).")
    return "Todavía no hay respuestas suficientes para comparar canales: el reparto sigue los valores iniciales."
