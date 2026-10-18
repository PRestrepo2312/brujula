"""Asistente de inicio por chat: en cuatro turnos deja listo cómo se presenta la empresa, su cliente ideal y cuánto le cuesta hoy un lead por pauta.

El front guarda el estado ({paso, datos}) y lo reenvía en cada turno; el servidor decide el siguiente paso, consulta el RUES, lee la página,
pide la propuesta al agente de texto y al final guarda todo en la empresa. Sin agente de texto, la propuesta sale de reglas.
"""
from __future__ import annotations

import re

from . import agente, empresas, perfil

PASOS = ("empresa", "sitio", "propuesta", "pauta", "listo")
ACEPTA = re.compile(r"\b(as[ií]\s*est[aá]\s*bien|ok|okey|bien|listo|perfecto|dale|s[ií]|de acuerdo|correcto|me gusta|d[eé]jalo|apru[eé]bo)\b", re.I)
NO_TIENE = re.compile(r"\b(no\s+tengo|no\s+tenemos|sin\s+p[aá]gina|ninguna|no\s+hay|todav[ií]a\s+no|a[uú]n\s+no)\b", re.I)
NO_SABE = re.compile(r"\b(no\s+s[eé]|ni\s+idea|no\s+tengo\s+el\s+dato|no\s+lo\s+s[eé]|no\s+pauto|no\s+hago\s+pauta|no\s+invierto)\b", re.I)


def _nit_en(texto: str) -> str:
    m = re.search(r"\b(\d{3}[\d.\-]{5,12})\b", texto)
    digitos = re.sub(r"\D", "", m.group(1)) if m else ""
    return digitos if 8 <= len(digitos) <= 10 else ""


def _url_en(texto: str) -> str:
    m = re.search(r"((?:https?://)?(?:www\.)?[a-z0-9][a-z0-9\-]*(?:\.[a-z0-9\-]+)+(?:/\S*)?)", texto, re.I)
    return m.group(1) if m else ""


def _usd_en(texto: str) -> float | None:
    """Un monto en dólares; si habla de pesos o es muy grande, lo convierte a USD a 4.000 pesos por dólar (aproximado, se le dice)."""
    t = texto.lower().replace("usd", " usd ")
    m = re.search(r"(\d[\d.,]*)", t)
    if not m:
        return None
    crudo = m.group(1)
    if crudo.count(".") > 1 or (crudo.count(".") == 1 and len(crudo.split(".")[-1]) == 3):
        crudo = crudo.replace(".", "")
    crudo = crudo.replace(",", ".")
    try:
        n = float(crudo)
    except ValueError:
        return None
    if "peso" in t or "cop" in t or "$" in t and n >= 1000 or n >= 1000:
        return round(n / 4000.0, 2)
    return round(n, 2)


def _texto_propuesta(p: dict) -> str:
    partes = [f"Qué ofrece: {p.get('que_ofrece') or '(sin propuesta)'}", f"A quién: {p.get('a_quien') or '(por definir)'}"]
    if p.get("diferencial"):
        partes.append(f"Qué lo distingue: {p['diferencial']}")
    partes += [f"Quién firma: {p.get('remitente') or '(el equipo)'}", f"Su cliente ideal: {p.get('icp_texto') or '(por definir)'}"]
    return "\n".join("• " + x for x in partes)


def responder(empresa_id: int, mensaje: str, estado: dict | None) -> dict:
    """Un turno del asistente. Devuelve la respuesta, el estado nuevo y, al final, lo guardado."""
    estado = estado or {}
    paso = estado.get("paso") if estado.get("paso") in PASOS else "empresa"
    datos = dict(estado.get("datos") or {})
    m = (mensaje or "").strip()
    e = empresas.obtener(empresa_id)
    nombre_empresa = (e.nombre if e else "") or "su empresa"

    if paso == "empresa":
        if not m:
            return {"respuesta": f"Hola, soy la brújula de {nombre_empresa}. Voy a dejar listo cómo se presenta su empresa en los correos, los mensajes y las llamadas, "
                                 "y a quién debe buscar. Primero: ¿cómo se llama su empresa y cuál es su NIT, si lo tiene a mano?", "paso": "empresa", "datos": datos}
        nit = _nit_en(m)
        nombre = re.sub(r"\b(nit|n\.i\.t\.?)\b[:\s]*", "", m, flags=re.I)
        nombre = re.sub(r"\d[\d.\-]{5,}", "", nombre).strip(" ,.-:;") or datos.get("nombre") or nombre_empresa
        rues = perfil.buscar_nit(nit) if nit else None
        if rues and (not nombre or nombre == nombre_empresa):
            nombre = (rues.get("sigla") or rues.get("razon_social") or nombre).title()
        datos.update({"nombre": nombre, "nit": nit, "rues": rues})
        if rues:
            r = (f"Lo encontré en el registro mercantil: {rues['razon_social']}, cámara de {rues['ciudad'].title()}, sector {rues['sector']}, "
                 f"matrícula {rues['matricula'][:4]}-{rues['matricula'][4:6]}-{rues['matricula'][6:8]} ({rues['estado'].lower()}). ")
        elif nit:
            r = "Ese NIT no aparece en el RUES; seguimos con el nombre que me dio. "
        else:
            r = f"Perfecto, {nombre}. "
        return {"respuesta": r + "¿Tiene página web? Pégueme la dirección y la leo; si no, escriba 'no tengo'.", "paso": "sitio", "datos": datos}

    if paso == "sitio":
        url = "" if NO_TIENE.search(m) else _url_en(m)
        sitio = perfil.leer_sitio(url) if url else None
        if sitio and sitio.get("error"):
            sitio = None
        datos["sitio_web"] = url
        datos["sitio"] = {k: sitio.get(k) for k in ("url", "titulo", "descripcion", "texto")} if sitio else None
        sug, info = perfil.sugerir(datos.get("nombre", nombre_empresa), datos.get("rues"), datos.get("sitio"), datos.get("notas", ""))
        datos["propuesta"] = sug
        datos["motor"] = info.get("motor", "")
        r = (f"Leí su página ({sitio['titulo']}). " if sitio and sitio.get("titulo") else ("No pude leer esa página; me apoyo en el registro. " if url else ""))
        r += "Esta es mi propuesta de cómo presentarse y a quién buscar:\n\n" + _texto_propuesta(sug) + "\n\n¿La dejamos así o le cambio algo? Escriba 'así está bien' o dígame qué corregir."
        return {"respuesta": r, "paso": "propuesta", "datos": datos, "propuesta": sug}

    if paso == "propuesta":
        if ACEPTA.search(m) and len(m) <= 60:
            return {"respuesta": "Perfecto. Última pregunta, para medir el ahorro: ¿cuánto le cuesta hoy conseguir un cliente por pauta (Meta o Google)? "
                                 "Un número aproximado en dólares o en pesos, o 'no sé'.", "paso": "pauta", "datos": datos}
        datos["notas"] = (datos.get("notas", "") + "\n" + m).strip()
        sug, info = perfil.sugerir(datos.get("nombre", nombre_empresa), datos.get("rues"), datos.get("sitio"), datos["notas"])
        datos["propuesta"] = sug
        return {"respuesta": "Con eso, queda así:\n\n" + _texto_propuesta(sug) + "\n\n¿Así está bien o le cambio algo más?", "paso": "propuesta", "datos": datos, "propuesta": sug}

    if paso == "pauta":
        usd = None if NO_SABE.search(m) else _usd_en(m)
        datos["costo_lead_pauta_usd"] = usd
        guardado = guardar(empresa_id, datos)
        r = "Listo. Guardé cómo se presenta, su cliente ideal"
        r += f" y el costo por pauta (USD {usd:.2f} por lead" + ("; lo convertí de pesos a 4.000 por dólar" if usd and re.search(r"peso|cop|\d{4,}", m.lower()) else "") + ")." if usd else "."
        r += " Ya puede buscar empresas; el tablero le mostrará cuánto cuesta cada cliente calificado con Brújula" + (" frente a la pauta." if usd else ".")
        return {"respuesta": r, "paso": "listo", "datos": datos, "listo": True, "guardado": guardado}

    return {"respuesta": "Ya quedó todo guardado. Puede volver a empezar cuando quiera desde Configuración.", "paso": "listo", "datos": datos, "listo": True}


def guardar(empresa_id: int, datos: dict) -> dict:
    """Perfil comercial, cliente ideal y costo por pauta en la empresa."""
    sug = datos.get("propuesta") or {}
    rues = datos.get("rues") or {}
    cfg = empresas.config_de(empresa_id)
    perfil_nuevo = {**(cfg.get("perfil") or {}),
                    "nombre": datos.get("nombre") or sug.get("nombre") or "", "nit": datos.get("nit") or rues.get("nit") or "",
                    "sitio_web": datos.get("sitio_web") or "", "que_ofrece": sug.get("que_ofrece", ""), "a_quien": sug.get("a_quien", ""),
                    "diferencial": sug.get("diferencial", ""), "remitente": sug.get("remitente", ""),
                    "razon_social": rues.get("razon_social", ""), "ciudad": rues.get("ciudad", ""), "sector": rues.get("sector", ""), "ciiu": rues.get("ciiu", "")}
    icp_texto = (sug.get("icp_texto") or "").strip()
    cambios = {"config": {**cfg, "perfil": perfil_nuevo, "costo_lead_pauta_usd": datos.get("costo_lead_pauta_usd")}}
    if datos.get("nombre"):
        cambios["nombre"] = datos["nombre"]
    if icp_texto:
        icp, _ = agente.interpretar_icp(icp_texto)
        cambios["icp_texto"] = icp_texto
        cambios["icp"] = icp.__dict__
    empresas.actualizar(empresa_id, **cambios)
    return {"perfil": perfil_nuevo, "icp_texto": icp_texto, "costo_lead_pauta_usd": datos.get("costo_lead_pauta_usd")}
