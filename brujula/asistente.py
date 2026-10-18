"""Los dos chats de Brújula.

1. Asistente de inicio (`responder`): en cuatro turnos deja listo cómo se presenta la empresa, su cliente ideal y cuánto le cuesta
   hoy un lead por pauta; si ya había algo guardado, arranca mostrándolo y pregunta qué cambiar. Al final ofrece buscar de una vez.
2. Asistente de búsqueda (`responder_busqueda`): a partir del cliente ideal propone en qué fuentes públicas y en qué ciudades buscar;
   la persona corrige conversando (otra ciudad, otro sector, otras fuentes) y confirma; la brújula corre la búsqueda y cuenta lo que trajo.

El front guarda el estado ({paso, datos}) y lo reenvía en cada turno; el servidor decide. Sin agente de texto, las propuestas salen de reglas.
En cualquier momento la persona puede cambiar de empresa: otro NIT, otra página o "empezar de nuevo" reinician la conversación.
"""
from __future__ import annotations

import re

from . import agente, empresas, ingest, metrics, notificaciones, perfil, pipeline
from .config import config
from .sources import CONECTORES

PASOS = ("empresa", "sitio", "propuesta", "pauta", "buscar", "listo")
ACEPTA = re.compile(r"\b(as[ií]\s*est[aá]\s*bien|ok|okey|bien|listo|perfecto|dale|s[ií]|de acuerdo|correcto|me gusta|d[eé]jalo|apru[eé]bo)\b", re.I)
PERO = re.compile(r"\b(pero|cambi\w*|quit\w*|mejor|agreg\w*|a[ñn]ad\w*|pon\w*|sin|no|falta\w*|corrij\w*|corrig\w*)\b", re.I)
NO_TIENE = re.compile(r"\b(no\s+tengo|no\s+tenemos|sin\s+p[aá]gina|ninguna|no\s+hay|todav[ií]a\s+no|a[uú]n\s+no)\b", re.I)
NO_SABE = re.compile(r"\b(no\s+s[eé]|ni\s+idea|no\s+tengo\s+el\s+dato|no\s+lo\s+s[eé]|no\s+pauto|no\s+hago\s+pauta|no\s+invierto)\b", re.I)
DESPUES = re.compile(r"\b(despu[eé]s|luego|ahora\s+no|todav[ií]a\s+no|m[aá]s\s+tarde|no)\b", re.I)
REINICIA = re.compile(r"\b(empezar\s+de\s+nuevo|volver\s+a\s+empezar|reinici\w*|otra\s+empresa|cambiar\s+(?:de\s+)?empresa|desde\s+el\s+principio|borr\w*\s+todo)\b", re.I)
SI_BUSCA = re.compile(r"^\W*(s[ií]|busca\w*|dale|claro|hazlo|de\s+una|ok|okey|listo|va|adelante|empieza|arranca|as[ií])\b", re.I)
CONTACTA = re.compile(r"\b(contact\w*|ll[aá]m\w*|escr[ií]b\w*|env[ií]\w*|lote|arma\w*)\b", re.I)

FUENTE_POR_SECTOR = {"salud": "reps", "educacion": "men", "turismo": "rnt"}
TODAS_CO = ("reps", "men", "rnt", "secop", "rues")   # lo que entra con "todas las fuentes" (OSM queda fuera: pide el tipo de negocio en inglés)
ALIAS_FUENTE = {"reps": "reps", "men": "men", "rnt": "rnt", "secop": "secop", "rues": "rues", "osm": "osm", "openstreetmap": "osm",
                "denue": "denue", "cnpj": "cnpj", "nyc": "nyc"}
RELLENO = {"en", "y", "e", "o", "tambien", "mejor", "solo", "la", "las", "el", "los", "de", "del", "ciudad", "ciudades", "agrega", "agregue", "agregame",
           "suma", "sume", "quita", "quite", "sin", "ademas", "por", "favor", "busca", "buscar", "busque", "si", "ponme", "pon", "incluye", "incluya", "a"}


def _sin_tildes(s: str) -> str:
    return s.translate(str.maketrans("ÁÉÍÓÚáéíóúÑñ", "AEIOUaeiouNn"))


def _nit_en(texto: str) -> str:
    m = re.search(r"\b(\d{3}[\d.\-]{5,12})\b", texto)
    digitos = re.sub(r"\D", "", m.group(1)) if m else ""
    return digitos if 8 <= len(digitos) <= 10 else ""


def _url_en(texto: str) -> str:
    """Una dirección web; exige un dominio con letras al final para no confundir un NIT con puntos (900.123.456) con una página."""
    m = re.search(r"((?:https?://)?(?:www\.)?[a-z0-9][a-z0-9\-]*(?:\.[a-z0-9\-]+)*\.[a-z]{2,}(?:/\S*)?)", texto, re.I)
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
    ejemplo = (f"Así empezaría el correo: \"Hola, equipo de [empresa]. Les escribe {p.get('remitente') or 'el equipo'}: {p.get('que_ofrece') or '…'}. "
               "Les escribimos porque [la señal de esa empresa].\"")
    return "\n".join("• " + x for x in partes) + "\n\n" + ejemplo


# ---------------------------------------------------------------------------------------------------------------------
# Asistente de inicio
# ---------------------------------------------------------------------------------------------------------------------

def _saludo_con_lo_guardado(empresa_id: int, e) -> dict | None:
    """Si la empresa ya tiene perfil, el chat arranca mostrándolo (contexto) en vez de preguntar todo otra vez."""
    cfg = empresas.config_de(empresa_id)
    p = cfg.get("perfil") or {}
    if not (p.get("que_ofrece") or p.get("nombre")):
        return None
    propuesta = {"nombre": p.get("nombre") or e.nombre, "que_ofrece": p.get("que_ofrece", ""), "a_quien": p.get("a_quien", ""),
                 "diferencial": p.get("diferencial", ""), "remitente": p.get("remitente", ""), "icp_texto": (e.icp_texto or "") if e else ""}
    pauta = cfg.get("costo_lead_pauta_usd")
    datos = {"nombre": propuesta["nombre"], "nit": p.get("nit", ""), "rues": None, "sitio_web": p.get("sitio_web", ""), "sitio": None,
             "propuesta": propuesta, "costo_lead_pauta_usd": pauta, "sin_cambios": True}
    r = f"Hola de nuevo. Ya tengo guardado cómo se presenta {propuesta['nombre']}:\n\n" + _texto_propuesta(propuesta)
    if pauta:
        r += f"\n\n• Costo por lead con pauta: USD {float(pauta):.2f}"
    r += "\n\n¿Lo dejamos así o le cambio algo? Si es otra empresa, escríbame su nombre o su NIT."
    return {"respuesta": r, "paso": "propuesta", "datos": datos, "propuesta": propuesta}


def _ofrecer_busqueda(empresa_id: int, datos: dict, antes: str) -> dict:
    """Cierra el inicio ofreciendo buscar de una vez con el plan del asistente de búsqueda."""
    plan = responder_busqueda(empresa_id, "", None)
    datos["buscar"] = plan["datos"]
    return {"respuesta": antes + " ¿Busco ya empresas con esto?\n\n" + plan["respuesta"].split("\n\n", 1)[-1], "paso": "buscar", "datos": datos}


def responder(empresa_id: int, mensaje: str, estado: dict | None, usuario: str = "") -> dict:
    """Un turno del asistente de inicio. Devuelve la respuesta, el estado nuevo y, al final, lo guardado."""
    estado = estado or {}
    paso = estado.get("paso") if estado.get("paso") in PASOS else "empresa"
    datos = dict(estado.get("datos") or {})
    m = (mensaje or "").strip()
    e = empresas.obtener(empresa_id)
    nombre_empresa = (e.nombre if e else "") or "su empresa"

    if m and REINICIA.search(m):
        resto = REINICIA.sub("", m).strip(" ,.:;-")
        if resto:
            return responder(empresa_id, resto, {"paso": "empresa"})
        return {"respuesta": "Listo, empezamos de cero. ¿Cómo se llama su empresa y cuál es su NIT, si lo tiene a mano?", "paso": "empresa", "datos": {}}

    if paso == "empresa":
        if not m:
            return _saludo_con_lo_guardado(empresa_id, e) or {
                "respuesta": f"Hola, soy la brújula de {nombre_empresa}. Voy a dejar listo cómo se presenta su empresa en los correos, los mensajes y las llamadas, "
                             "y a quién debe buscar. Primero: ¿cómo se llama su empresa y cuál es su NIT, si lo tiene a mano?", "paso": "empresa", "datos": {}}
        nit = _nit_en(m)
        nombre = re.sub(r"\b(nit|n\.i\.t\.?)\b[:\s]*", "", m, flags=re.I)
        nombre = re.sub(r"\d[\d.\-]{5,}", "", nombre).strip(" ,.-:;") or datos.get("nombre") or nombre_empresa
        rues = perfil.buscar_nit(nit) if nit else None
        if rues and (not nombre or nombre == nombre_empresa):
            # No escribió un nombre nuevo: el del registro mercantil, sin la forma jurídica (PANEL ROCK COLOMBIA S A S → Panel Rock Colombia).
            nombre = perfil.nombre_comercial(rues.get("razon_social", ""), rues.get("sigla", "")) or nombre
        datos = {"nombre": nombre, "nit": nit, "rues": rues}   # empresa nueva: nada de la anterior
        if rues:
            r = (f"Lo encontré en el registro mercantil: {rues['razon_social']}, cámara de {rues['ciudad'].title()}, sector {rues['sector']}, "
                 f"matrícula {rues['matricula'][:4]}-{rues['matricula'][4:6]}-{rues['matricula'][6:8]} ({rues['estado'].lower()}). Se presentará como {nombre}. ")
        elif nit:
            r = "Ese NIT no aparece en el RUES; seguimos con el nombre que me dio. "
        else:
            r = f"Perfecto, {nombre}. "
        return {"respuesta": r + "¿Tiene página web? Pégueme la dirección y la leo; si no, escriba 'no tengo'.", "paso": "sitio", "datos": datos}

    if paso == "sitio":
        if _nit_en(m) and not _url_en(m) and not NO_TIENE.search(m):
            return responder(empresa_id, m, {"paso": "empresa", "datos": {"nombre": datos.get("nombre")}})   # mandó el NIT tarde
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
        if _nit_en(m) and not _url_en(m):
            return responder(empresa_id, m, {"paso": "empresa"})   # otro NIT = otra empresa
        url = _url_en(m)
        if url and len(m.replace(url, "").strip(" ,.:;-")) <= 15:
            return responder(empresa_id, m, {"paso": "sitio", "datos": {k: datos.get(k) for k in ("nombre", "nit", "rues", "notas")}})   # otra página
        prop = datos.get("propuesta") or {}
        if ACEPTA.search(m) and len(m) <= 60 and not PERO.search(m):
            if not (prop.get("icp_texto") or "").strip():
                datos["pidio_icp"] = True
                return {"respuesta": "Antes de seguir me falta su cliente ideal: ¿a quién le vende? Sector, tamaño y ciudades, en sus palabras.",
                        "paso": "propuesta", "datos": datos}
            if datos.get("sin_cambios"):
                return _ofrecer_busqueda(empresa_id, datos, "Todo sigue igual.")
            if datos.get("costo_lead_pauta_usd") is not None:   # ya sabía la pauta: guardo y ofrezco buscar
                datos["guardado"] = guardar(empresa_id, datos)
                return _ofrecer_busqueda(empresa_id, datos, "Guardé los cambios.")
            return {"respuesta": "Perfecto. Última pregunta, para medir el ahorro: ¿cuánto le cuesta hoy conseguir un cliente por pauta (Meta o Google)? "
                                 "Un número aproximado en dólares o en pesos, o 'no sé'.", "paso": "pauta", "datos": datos}
        datos["notas"] = (datos.get("notas", "") + "\n" + m).strip()
        datos["sin_cambios"] = False
        sug, info = perfil.sugerir(datos.get("nombre", nombre_empresa), datos.get("rues"), datos.get("sitio"), datos["notas"], actual=prop)
        if not (sug.get("icp_texto") or "").strip() and datos.get("pidio_icp"):
            sug["icp_texto"] = m   # sin agente de texto, su cliente ideal es lo que acaba de decir
        datos["propuesta"] = sug
        datos["motor"] = info.get("motor", "")
        return {"respuesta": "Con eso, queda así:\n\n" + _texto_propuesta(sug) + "\n\n¿Así está bien o le cambio algo más?", "paso": "propuesta", "datos": datos, "propuesta": sug}

    if paso == "pauta":
        usd = None if NO_SABE.search(m) else _usd_en(m)
        datos["costo_lead_pauta_usd"] = usd
        datos["guardado"] = guardar(empresa_id, datos)
        r = "Listo. Guardé cómo se presenta, su cliente ideal"
        r += f" y el costo por pauta (USD {usd:.2f} por lead" + ("; lo convertí de pesos a 4.000 por dólar" if usd and re.search(r"peso|cop|\d{4,}", m.lower()) else "") + ")." if usd else "."
        r += " El tablero le mostrará cuánto cuesta cada cliente calificado con Brújula" + (" frente a la pauta." if usd else ".")
        return {**_ofrecer_busqueda(empresa_id, datos, r), "guardado": datos["guardado"]}

    if paso == "buscar":
        if DESPUES.search(m) and len(m) <= 30:
            return {"respuesta": "Cuando quiera, en Buscar lo hacemos conversando. Ya puede ver lo guardado en Configuración.", "paso": "listo", "datos": datos, "listo": True}
        rb = responder_busqueda(empresa_id, m, {"paso": datos.get("paso_busqueda") or "plan", "datos": datos.get("buscar") or {}}, usuario=usuario)
        datos["buscar"], datos["paso_busqueda"] = rb["datos"], rb["paso"]
        return {**rb, "paso": "buscar", "datos": datos, "listo": bool(rb.get("listo"))}

    if m:
        return responder(empresa_id, m, {"paso": "empresa"})   # ya terminó y escribe de nuevo: otra vuelta
    return {"respuesta": "Ya quedó todo guardado. Si quiere ajustar algo, escríbame el nombre o el NIT y empezamos de nuevo.", "paso": "listo", "datos": datos, "listo": True}


def guardar(empresa_id: int, datos: dict) -> dict:
    """Perfil comercial, cliente ideal y costo por pauta en la empresa."""
    sug = datos.get("propuesta") or {}
    rues = datos.get("rues") or {}
    cfg = empresas.config_de(empresa_id)
    del_registro = {"razon_social": rues.get("razon_social", ""), "ciudad": rues.get("ciudad", ""), "sector": rues.get("sector", ""), "ciiu": rues.get("ciiu", "")} if rues else {}
    perfil_nuevo = {**(cfg.get("perfil") or {}),
                    "nombre": datos.get("nombre") or sug.get("nombre") or "", "nit": datos.get("nit") or rues.get("nit") or "",
                    "sitio_web": datos.get("sitio_web") or "", "que_ofrece": sug.get("que_ofrece", ""), "a_quien": sug.get("a_quien", ""),
                    "diferencial": sug.get("diferencial", ""), "remitente": sug.get("remitente", ""), **del_registro}
    icp_texto = (sug.get("icp_texto") or "").strip()
    cambios = {"config": {**cfg, "perfil": perfil_nuevo, "costo_lead_pauta_usd": datos.get("costo_lead_pauta_usd")}}
    if datos.get("nombre"):
        cambios["nombre"] = datos["nombre"]
    e = empresas.obtener(empresa_id)
    if icp_texto and icp_texto != ((e.icp_texto if e else "") or ""):
        icp, _ = agente.interpretar_icp(icp_texto)
        cambios["icp_texto"] = icp_texto
        cambios["icp"] = icp.__dict__
    empresas.actualizar(empresa_id, **cambios)
    return {"perfil": perfil_nuevo, "icp_texto": icp_texto, "costo_lead_pauta_usd": datos.get("costo_lead_pauta_usd")}


# ---------------------------------------------------------------------------------------------------------------------
# Asistente de búsqueda
# ---------------------------------------------------------------------------------------------------------------------

def _ciudades_en(texto: str) -> list[str]:
    t = _sin_tildes(texto.upper())
    return [c for c in agente.CIUDADES if re.search(r"\b" + re.escape(c) + r"\b", t)]


def _fuentes_para(icp) -> tuple[list[str], dict]:
    """Qué fuentes públicas de Colombia sirven para ese cliente ideal: REPS para salud, MEN para educación, RNT para turismo y SECOP para el resto."""
    fuentes, parametros = [], {}
    for s in icp.sectores or []:
        f = FUENTE_POR_SECTOR.get(s)
        if f and f not in fuentes:
            fuentes.append(f)
    otros = [s for s in (icp.sectores or []) if s not in FUENTE_POR_SECTOR]
    if otros or not fuentes:
        fuentes.append("secop")
        parametros["secop"] = {"sector": (icp.palabras_sector or otros or [""])[0]}
    return fuentes, parametros


def _nombre_fuente(clave: str) -> str:
    c = CONECTORES.get(clave)
    return c.nombre.split(",")[0] if c else clave


def _texto_plan(icp, fuentes: list[str], ciudades: list[str], parametros: dict) -> str:
    donde = " y ".join(c.title() for c in ciudades) if ciudades else "todo el país"
    partes = [_nombre_fuente(f) + (f" (actividad: {parametros[f]['sector']})" if (parametros.get(f) or {}).get("sector") else "") for f in fuentes]
    notas = []
    if fuentes == ["secop"]:
        notas.append("Para ese sector la única fuente pública con teléfono y correo es SECOP (empresas registradas como proveedoras del Estado): "
                     "REPS, MEN y RNT solo cubren salud, educación y turismo, y el RUES trae empresas recién matriculadas pero sin contacto.")
    if icp.empleados_min or icp.empleados_max:
        notas.append("El número de empleados solo lo publica el RNT; en las demás fuentes el encaje se apoya en sector, ciudad y canal de contacto.")
    texto = f"Su cliente ideal: {icp.descripcion}\n\nLe propongo buscar en {', '.join(partes)}, en {donde}."
    if notas:
        texto += "\n\n" + " ".join(notas)
    return texto + ("\n\n¿Busco así? Diga 'sí', o cámbieme la ciudad, el sector o la fuente. "
                    "'Todas las fuentes' usa REPS, MEN, RNT, SECOP y RUES a la vez; 'fuentes' las describe una por una.")


def _texto_fuentes() -> str:
    lineas = [f"• {c.nombre} [{c.pais}], {'contacta' if c.contacta else 'solo encontrar'}. {c.descripcion[:110].rstrip('. ')}."
              for k, c in CONECTORES.items() if k != "csv"]
    return "Las fuentes que conozco:\n" + "\n".join(lineas) + "\n\nDígame cuáles quiere, por ejemplo 'reps y men en Cali'."


def buscar_ahora(empresa_id: int, fuentes: list[str], ciudades: list[str], parametros: dict, limite: int = 80) -> dict:
    """Corre la búsqueda como lo haría el botón de Buscar: por ciudad (hasta tres), deduplica y puntúa contra el cliente ideal."""
    cuenta = {"nuevos": 0, "pasa": 0, "revisar": 0}
    por_fuente: dict[str, int] = {}
    errores: list[str] = []
    for ciudad in (ciudades or [""])[:3]:
        r = ingest.buscar(empresa_id, fuentes, ciudad=ciudad, limite=limite, parametros=parametros)
        cuenta["nuevos"] += r.get("nuevos", 0)
        cuenta["pasa"] += (r.get("icp") or {}).get("pasa", 0)
        cuenta["revisar"] += (r.get("icp") or {}).get("revisar", 0)
        for f in r.get("fuentes", []):
            por_fuente[f.get("fuente", "")] = por_fuente.get(f.get("fuente", ""), 0) + (f.get("nuevos") or 0)
            if f.get("error"):
                errores.append(f"{_nombre_fuente(f.get('fuente', ''))}: {str(f['error'])[:80]}")
    notificaciones.notificar(empresa_id, "busqueda", f"Búsqueda desde el chat en {', '.join(fuentes)} ({', '.join(ciudades) or 'todas las ciudades'}): {cuenta['nuevos']} empresas nuevas")
    return {**cuenta, "por_fuente": por_fuente, "errores": errores, "fuentes": fuentes, "ciudades": ciudades}


def _texto_resultado(r: dict, cfg: dict) -> str:
    partes = [f"{_nombre_fuente(f)} {n}" for f, n in r["por_fuente"].items()]
    t = f"Listo. Empresas nuevas: {r['nuevos']}" + (f" ({', '.join(partes)})" if partes else "")
    t += f". Encajan con su cliente ideal: {r['pasa']}; por revisar: {r['revisar']}."
    if r["errores"]:
        t += " Fallaron: " + "; ".join(r["errores"]) + "."
    if r["nuevos"] == 0:
        t += " Puede que ya las tuviera todas o que no haya en esa ciudad: pruebe otra ciudad u otra fuente."
    t += "\n\nVéalas en Leads. Si quiere otra búsqueda, dígame otra ciudad, otro sector u otra fuente."
    umbral = int(round(float(cfg.get("umbral_contacto") or 0.7) * 100))
    canales = " y ".join(metrics.NOMBRE_CANAL.get(c, c) for c in (cfg.get("canales") or ["voz", "correo"]))
    if cfg.get("contacto_automatico"):
        t += (f"\n\nEl contacto automático está activo: en cada hora del horario legal la brújula arma un lote con las de mejor encaje "
              f"(mínimo {umbral} %), hasta {cfg.get('presupuesto_lote', 20)} por lote, por {canales}. Si quiere uno ahora, diga 'contacta'.")
    else:
        t += (f"\n\n¿Quiere que contacte ya a las que encajan? Diga 'contacta' y armo un lote con las de mejor encaje (mínimo {umbral} %), "
              f"hasta {cfg.get('presupuesto_lote', 20)} contactos por {canales}. Para que la brújula lo haga sola en cada ventana legal, "
              "active el contacto automático en Configuración.")
    return t


def contactar_ahora(empresa_id: int, usuario: str = "") -> dict:
    """Lo mismo que el botón de Lotes: un lote repartido por la brújula entre las que encajan, enviado de una vez."""
    r = pipeline.preparar_lote(modo="brujula", usuario=usuario, empresa_id=empresa_id)
    if "lote_id" in r:
        r["envio"] = pipeline.ejecutar_lote(r["lote_id"])
    return r


def _texto_lote(r: dict) -> str:
    if "error" in r:
        t = r["error"]
        if r.get("fuera_ventana"):
            t += (" Puede desactivar el horario de la Ley 2300 en Configuración bajo su responsabilidad, o activar el contacto automático "
                  "y la brújula lo hará sola en la próxima ventana legal.")
        return t
    reparto = ", ".join(f"{metrics.nombre_cruce(k)} {v}" for k, v in (r.get("reparto") or {}).items())
    t = f"Lote {r['lote_id']} en marcha: {r['intentos']} contactos ({reparto}). {r.get('explicacion', '')}".strip()
    res = (r.get("envio") or {}).get("resultado") or {}
    if res:
        t += " Envío: " + ", ".join(f"{k.replace(':', ' ')} {v}" for k, v in res.items()) + "."
    if r.get("omitidos"):
        t += " Omitidos: " + ", ".join(f"{k} {v}" for k, v in r["omitidos"].items()) + "."
    if config.modo_prueba:
        t += " Modo prueba: las llamadas salen al número de prueba y los correos a los del equipo, con los datos reales de cada empresa."
    if r.get("fuera_ventana"):
        t += " Salió fuera del horario legal con constancia en la bitácora."
    return t + "\n\nSiga el avance en Lotes; las respuestas llegan a Leads y a Notificaciones."


def responder_busqueda(empresa_id: int, mensaje: str, estado: dict | None, usuario: str = "") -> dict:
    """Un turno del asistente de búsqueda: propone fuentes y ciudades, acepta cambios, corre la búsqueda cuando la persona confirma
    y, después, ofrece contactar a las que encajan."""
    estado = estado or {}
    datos = dict(estado.get("datos") or {})
    m = (mensaje or "").strip()
    icp = empresas.icp_de(empresa_id)
    cfg = empresas.config_de(empresa_id)

    if estado.get("paso") == "hecho" and m and (CONTACTA.search(m) or (SI_BUSCA.search(m) and len(m) <= 30 and not PERO.search(m))):
        r = contactar_ahora(empresa_id, usuario)
        return {"respuesta": _texto_lote(r), "paso": "hecho", "datos": datos, "listo": True, "lote": r}

    def plan(antes: str = "") -> dict:
        fuentes, parametros = _fuentes_para(icp)
        fuentes = datos.get("fuentes") or fuentes
        ciudades = list(icp.ciudades or [])
        datos.update({"fuentes": fuentes, "parametros": parametros, "ciudades": ciudades})
        return {"respuesta": antes + _texto_plan(icp, fuentes, ciudades, parametros), "paso": "plan", "datos": datos}

    if not m:
        return plan("Busquemos empresas. ")
    if len(m) <= 25 and re.search(r"\bfuentes?\b", m, re.I):
        return {"respuesta": _texto_fuentes(), "paso": "plan", "datos": datos}
    claves = [ALIAS_FUENTE[w] for w in re.findall(r"[a-z]+", _sin_tildes(m.lower())) if w in ALIAS_FUENTE and ALIAS_FUENTE[w] in CONECTORES]
    ciudades = _ciudades_en(m)
    if re.search(r"\btodas?\b", m, re.I) and (re.search(r"\bfuentes?\b|\bcolombia\b|\bregistros?\b", m, re.I) or len(m) <= 12) and len(m) <= 80:
        datos["fuentes"] = [k for k in TODAS_CO if k in CONECTORES]   # "todas las fuentes (de Colombia)" / "todas"
        if ciudades:
            icp.ciudades = ciudades
            empresas.actualizar(empresa_id, icp=icp.__dict__)
        return plan("Entendido, todas las fuentes de Colombia (el RUES no trae contacto, sirve para ver quién se matriculó hace poco). ")
    if claves:
        datos["fuentes"] = list(dict.fromkeys(claves))
        if ciudades:
            icp.ciudades = ciudades
            empresas.actualizar(empresa_id, icp=icp.__dict__)
        return plan("Entendido. ")
    if SI_BUSCA.search(m) and len(m) <= 30 and not PERO.search(m):
        if not datos.get("fuentes"):
            plan()
        r = buscar_ahora(empresa_id, datos["fuentes"], datos.get("ciudades") or [], datos.get("parametros") or {})
        return {"respuesta": _texto_resultado(r, cfg), "paso": "hecho", "datos": datos, "listo": True, "resultado": r}
    t = _sin_tildes(m.lower())
    for c in ciudades:
        t = t.replace(c.lower(), " ")
    resto = [w for w in re.findall(r"[a-z]+", t) if w not in RELLENO]
    if ciudades and not resto:
        suma = bool(re.search(r"tambi|agreg|sum|incluy|pon", m.lower()))
        icp.ciudades = list(dict.fromkeys((list(icp.ciudades or []) if suma else []) + ciudades))
        empresas.actualizar(empresa_id, icp=icp.__dict__)
        return plan("Cambio la ciudad. ")
    # Lo demás es una descripción nueva (o un ajuste) de a quién busca: la interpreta el agente y se guarda como cliente ideal.
    e = empresas.obtener(empresa_id)
    reemplaza = len(m) > 50 or not (e and e.icp_texto) or re.match(r"\W*(mejor|cambi\w*|en\s+vez|solo|s[oó]lo|ahora|quiero|busco|busca)\b", m, re.I)
    texto = m if reemplaza else f"{e.icp_texto}. Ajuste: {m}"
    icp, info = agente.interpretar_icp(texto)
    empresas.actualizar(empresa_id, icp=icp.__dict__, icp_texto=(icp.descripcion if info.get("motor", "reglas") != "reglas" else texto))
    datos.pop("fuentes", None)
    return plan("Entendido, actualicé su cliente ideal. ")
