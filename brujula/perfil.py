"""Perfil comercial guiado: el NIT en el RUES, la lectura del sitio web y una sugerencia de qué ofrece, a quién y cuál es su cliente ideal.

Es lo que hace el asistente de inicio: la empresa escribe su NIT y su página, Brújula trae lo que hay en registros públicos y en la
página, y el agente de texto propone el perfil y el cliente ideal; la persona corrige y confirma.
"""
from __future__ import annotations

import html
import json
import re

import httpx

from . import agente
from .sources.co_rues import DATASET as RUES
from .sources.co_rues import SECTOR_POR_CIIU
from .sources.datos_gov import Socrata


def buscar_nit(nit: str) -> dict | None:
    """La empresa en el RUES (Confecámaras) por NIT, con o sin dígito de verificación."""
    digitos = re.sub(r"\D", "", nit or "")
    if len(digitos) < 8:
        return None
    candidatos = [digitos] + ([digitos[:-1]] if len(digitos) == 10 else [])
    api = Socrata()
    for n in candidatos:
        filas = list(api.filas(RUES, where=f"nit='{n}'", order="fecha_matricula DESC", limite=3))
        if filas:
            f = filas[0]
            ciiu = (f.get("cod_ciiu_act_econ_pri") or "")[:4]
            return {"nit": n, "razon_social": f.get("razon_social", ""), "sigla": f.get("sigla", ""),
                    "ciudad": (f.get("camara_comercio") or "").split(" PARA ")[0].split(" DE ")[-1], "camara": f.get("camara_comercio", ""),
                    "ciiu": ciiu, "sector": SECTOR_POR_CIIU.get(ciiu[:2], "otro"), "matricula": f.get("fecha_matricula", ""),
                    "estado": f.get("estado_matricula", ""), "tipo": f.get("organizacion_juridica", ""), "representante": f.get("representante_legal", "")}
    return None


def leer_sitio(url: str) -> dict:
    """Título, descripción y texto visible de la página principal (un GET, 15 s, sin JavaScript)."""
    u = (url or "").strip()
    if not u:
        return {"error": "sin dirección"}
    if not u.lower().startswith("http"):
        u = "https://" + u
    try:
        r = httpx.get(u, timeout=15, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (compatible; Brujula/1.0; +https://github.com/PRestrepo2312/brujula)"})
    except httpx.HTTPError as e:
        return {"url": u, "error": f"no se pudo leer la página: {str(e)[:120]}"}
    cuerpo = r.text[:400_000]
    titulo = re.search(r"<title[^>]*>(.*?)</title>", cuerpo, re.S | re.I)
    desc = (re.search(r'<meta[^>]+name=["\']description["\'][^>]*content=["\']([^"\']*)', cuerpo, re.I)
            or re.search(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*name=["\']description', cuerpo, re.I)
            or re.search(r'<meta[^>]+property=["\']og:description["\'][^>]*content=["\']([^"\']*)', cuerpo, re.I))
    texto = re.sub(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", cuerpo, flags=re.S | re.I)
    texto = html.unescape(re.sub(r"<[^>]+>", " ", texto))
    texto = re.sub(r"\s+", " ", texto).strip()
    limpio = lambda m: html.unescape(re.sub(r"\s+", " ", m.group(1))).strip() if m else ""   # noqa: E731
    return {"url": str(r.url), "estado": r.status_code, "titulo": limpio(titulo)[:160], "descripcion": limpio(desc)[:400], "texto": texto[:4000]}


def sugerir(nombre: str, rues: dict | None = None, sitio: dict | None = None, notas: str = "") -> tuple[dict, dict]:
    """Qué ofrece, a quién, diferencial, cómo firmar y cliente ideal. Con agente de texto, lo redacta a partir del RUES, la página y
    las notas; sin agente, arma lo básico con el título, la descripción y el sector del RUES."""
    rues = rues or {}
    sitio = sitio or {}
    base = {
        "nombre": nombre or rues.get("sigla") or rues.get("razon_social", "").title(),
        "que_ofrece": (sitio.get("descripcion") or sitio.get("titulo") or "").strip(),
        "a_quien": "",
        "diferencial": "",
        "remitente": f"el equipo de {nombre}" if nombre else "",
        "icp_texto": (f"Empresas de {rues['sector']} en {rues['ciudad'].title()}" if rues.get("sector") and rues.get("ciudad") else ""),
    }
    b = agente.llm()
    if not b.disponible:
        return base, {"motor": "reglas"}
    sistema = ("Ayudas a una pyme a presentarse en un primer mensaje comercial y a describir su cliente ideal. Con los datos del registro mercantil, "
               "el texto de su página web y las notas de la persona, responde SOLO un JSON con: "
               "que_ofrece (una frase en primera persona del plural, sin el nombre de la empresa, que complete 'Les escribe el equipo de X: ...'; "
               "concreta, sin adjetivos de venta, máximo 25 palabras), "
               "a_quien (a qué tipo de empresas o personas le vende, una frase), diferencial (qué la distingue, una frase, o vacío si no se sabe), "
               "remitente (cómo firmar, p. ej. 'el equipo de X' o 'Ana, de X'), "
               "icp_texto (su cliente ideal en español, una o dos frases con sector, tamaño y ciudades, como para buscarlo en registros públicos de empresas), "
               "sectores (lista entre: salud, educacion, turismo, inmobiliario, automotor, servicios, software, comercio, otro), ciudades (lista en MAYÚSCULAS sin tildes). "
               "Si la página no es de esa empresa o está vacía, apóyate en el registro y las notas. Español de Colombia.")
    usuario = json.dumps({"nombre": nombre, "registro_mercantil": {k: rues.get(k) for k in ("razon_social", "sigla", "ciudad", "sector", "ciiu", "tipo", "matricula")},
                          "pagina": {k: sitio.get(k) for k in ("url", "titulo", "descripcion")}, "texto_pagina": (sitio.get("texto") or "")[:3000],
                          "notas": notas[:1000]}, ensure_ascii=False)
    texto, uso = b.preguntar(sistema, usuario, max_tokens=600)
    datos = agente._json_de(texto) if texto else None
    if not datos:
        return base, {"motor": "reglas", "nota": b.error}
    sugerido = {**base, **{k: v for k, v in datos.items() if k in ("que_ofrece", "a_quien", "diferencial", "remitente", "icp_texto") and isinstance(v, str)}}
    sugerido["sectores"] = [s for s in (datos.get("sectores") or []) if isinstance(s, str)]
    sugerido["ciudades"] = [c for c in (datos.get("ciudades") or []) if isinstance(c, str)]
    return sugerido, {"motor": b.motor, "costo_usd": uso.costo_usd}
