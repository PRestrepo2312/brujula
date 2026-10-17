"""El agente: Bedrock (Claude) para lo lento y creativo, Jev (TypeSafe) para lo rápido y repetitivo, reglas de respaldo siempre.

- interpretar_icp: el texto en español de la empresa se vuelve criterios estructurados (ICP).
- redactar_mensaje: el primer mensaje de un lead, con su señal, corto y con la baja.
- explicar: una frase para humanos sobre una decisión de la brújula.
- clasificar_respuesta: interesado | no_interesado | despues | equivocado | baja, con Jev; palabras clave si no hay Jev.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx

from .config import config
from .icp import ICP
from .models import Lead

CIUDADES = ["BOGOTA", "MEDELLIN", "CALI", "BARRANQUILLA", "CARTAGENA", "BUCARAMANGA", "IBAGUE", "PEREIRA", "MANIZALES", "CUCUTA", "SANTA MARTA",
            "VILLAVICENCIO", "PASTO", "MONTERIA", "NEIVA", "ARMENIA", "POPAYAN", "VALLEDUPAR", "SINCELEJO", "TUNJA", "SOLEDAD", "SOACHA", "BELLO", "ENVIGADO", "ITAGUI"]
SECTORES_PALABRAS = {
    "salud": ["clinic", "odont", "dental", "salud", "ips", "medic", "laboratorio", "fisioterap", "estetic", "consultorio", "hospital", "optic", "veterinar"],
    "educacion": ["colegio", "academia", "instituto", "educa", "escuela", "universidad", "formacion", "curso", "jardin", "kinder"],
    "turismo": ["hotel", "hostal", "agencia de viaje", "turis", "restauran", "reserva", "tour", "hospeda", "alojamiento", "rent"],
    "inmobiliario": ["inmobiliar", "finca raiz", "arriend", "vivienda", "constructor"],
    "automotor": ["concesionario", "taller", "automotor", "vehicul", "carro", "moto"],
    "servicios": ["servicio", "consultor", "asesor", "agencia", "estudio", "empresa"],
}


@dataclass
class Uso:
    tokens_entrada: int = 0
    tokens_salida: int = 0

    @property
    def costo_usd(self) -> float:
        return round((self.tokens_entrada + self.tokens_salida) / 1e6 * config.tarifas.llm_millon_tokens, 6)


class Bedrock:
    """Cliente mínimo de Bedrock (API converse). Si la cuenta no tiene acceso, disponible = False y mandan las reglas."""

    def __init__(self):
        self.modelo = config.bedrock_model
        self._cliente = None
        self.disponible = bool(config.bedrock_model) and config.bedrock_habilitado

    def _c(self):
        if self._cliente is None:
            import boto3
            self._cliente = boto3.client("bedrock-runtime", region_name=config.aws_region)
        return self._cliente

    def preguntar(self, sistema: str, usuario: str, max_tokens: int = 600) -> tuple[str | None, Uso]:
        if not self.disponible:
            return None, Uso()
        try:
            r = self._c().converse(modelId=self.modelo, system=[{"text": sistema}], messages=[{"role": "user", "content": [{"text": usuario}]}],
                                   inferenceConfig={"maxTokens": max_tokens, "temperature": 0.2})
            texto = "".join(p.get("text", "") for p in r["output"]["message"]["content"])
            u = r.get("usage", {})
            return texto, Uso(int(u.get("inputTokens", 0)), int(u.get("outputTokens", 0)))
        except Exception as e:  # noqa: BLE001
            self.disponible = False
            self.error = str(e)[:200]
            return None, Uso()


class OpenRouterLLM:
    """Plan B mientras la cuenta de AWS no tenga Bedrock: el mismo Amazon Nova (u otro) por OpenRouter, con la clave de Jev."""

    def __init__(self):
        self.modelo = config.llm_openrouter_model
        self.disponible = bool(config.openrouter_api_key and self.modelo)
        self.error = ""

    def preguntar(self, sistema: str, usuario: str, max_tokens: int = 600) -> tuple[str | None, Uso]:
        if not self.disponible:
            return None, Uso()
        try:
            r = httpx.post("https://openrouter.ai/api/v1/chat/completions", timeout=60,
                           headers={"Authorization": f"Bearer {config.openrouter_api_key}", "HTTP-Referer": config.public_base_url, "X-Title": "Brujula"},
                           json={"model": self.modelo, "temperature": 0.2, "max_tokens": max_tokens,
                                 "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}]})
            if r.status_code >= 300:
                self.error = f"OpenRouter {r.status_code}: {r.text[:160]}"
                if r.status_code in (401, 402, 403, 404):      # clave, créditos o modelo: no insistir
                    self.disponible = False
                return None, Uso()
            d = r.json()
            texto = d["choices"][0]["message"]["content"]
            u = d.get("usage") or {}
            return texto, Uso(int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0)))
        except Exception as e:  # noqa: BLE001
            self.error = str(e)[:200]
            return None, Uso()


class LLM:
    """Bedrock si la cuenta lo permite; si no, OpenRouter; si no hay ninguno, mandan las reglas y las plantillas."""

    def __init__(self):
        self.bedrock = Bedrock()
        self.openrouter = OpenRouterLLM()
        self._probado = False

    def _probar(self) -> None:
        """Una sola prueba corta a Bedrock: una cuenta nueva responde 'Operation not allowed' hasta que AWS la verifica."""
        if not self._probado and self.bedrock.disponible:
            self._probado = True
            self.bedrock.preguntar("Responde solo OK.", "OK", max_tokens=5)

    @property
    def disponible(self) -> bool:
        self._probar()
        return self.bedrock.disponible or self.openrouter.disponible

    @property
    def motor(self) -> str:
        self._probar()
        if self.bedrock.disponible:
            return f"bedrock:{self.bedrock.modelo}"
        if self.openrouter.disponible:
            return f"openrouter:{self.openrouter.modelo}"
        return "reglas"

    @property
    def error(self) -> str:
        return getattr(self.bedrock, "error", "") or self.openrouter.error

    def preguntar(self, sistema: str, usuario: str, max_tokens: int = 600) -> tuple[str | None, Uso]:
        if self.bedrock.disponible:
            texto, uso = self.bedrock.preguntar(sistema, usuario, max_tokens)
            if texto is not None:
                return texto, uso
        if self.openrouter.disponible:
            return self.openrouter.preguntar(sistema, usuario, max_tokens)
        return None, Uso()


_llm: LLM | None = None


def llm() -> LLM:
    global _llm
    if _llm is None:
        _llm = LLM()
    return _llm


def bedrock() -> LLM:
    """Nombre histórico: el agente de texto, sea Bedrock, OpenRouter o reglas."""
    return llm()


def _json_de(texto: str) -> dict | None:
    m = re.search(r"\{.*\}", texto, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


# ---------------- ICP ----------------

def interpretar_icp_reglas(texto: str) -> ICP:
    t = texto.lower()
    sectores = [s for s, palabras in SECTORES_PALABRAS.items() if any(p in t for p in palabras)] or ["salud", "educacion", "turismo"]
    ciudades = [c for c in CIUDADES if c.lower() in t.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")]
    emp_min = emp_max = None
    m = re.search(r"m[aá]s de (\d+)\s*(empleados|personas|trabajadores)", t)
    if m:
        emp_min = int(m.group(1))
    m = re.search(r"menos de (\d+)\s*(empleados|personas|trabajadores)", t)
    if m:
        emp_max = int(m.group(1))
    m = re.search(r"entre (\d+) y (\d+)\s*(empleados|personas|trabajadores)", t)
    if m:
        emp_min, emp_max = int(m.group(1)), int(m.group(2))
    palabras = [p for p in re.findall(r"[a-záéíóúñ]{5,}", t) if p not in ("quiero", "empresas", "negocios", "clientes", "bogota", "colombia", "tengan", "reciban")]
    return ICP(nombre=texto[:60].strip() or "ICP", descripcion=texto.strip(), sectores=sectores, ciudades=ciudades,
               palabras_sector=palabras[:8], empleados_min=emp_min, empleados_max=emp_max)


def interpretar_icp(texto: str) -> tuple[ICP, dict]:
    """Devuelve el ICP y cómo se obtuvo ({"motor": "bedrock:…"|"openrouter:…"|"reglas", "costo_usd": ...})."""
    base = interpretar_icp_reglas(texto)
    b = bedrock()
    sistema = ("Conviertes la descripción del cliente ideal de una pyme en criterios estructurados para buscar empresas en registros públicos de Colombia. "
               "Responde SOLO un JSON con: nombre (corto), descripcion (una frase), sectores (lista entre: salud, educacion, turismo, inmobiliario, automotor, servicios, otro), "
               "palabras_sector (lista de palabras clave para buscar en el nombre o actividad), ciudades (lista en MAYÚSCULAS sin tildes, vacía si no dice), "
               "empleados_min y empleados_max (enteros o null), excluir_palabras (lista en MAYÚSCULAS de tipos de entidad que no quiere, p. ej. FUNDACION), "
               "segmentos (objeto nombre->descripción de 2 a 4 segmentos del ICP más 'otro').")
    texto_r, uso = b.preguntar(sistema, texto, max_tokens=700)
    datos = _json_de(texto_r) if texto_r else None
    if not datos:
        return base, {"motor": "reglas", "costo_usd": 0.0, "nota": getattr(b, "error", "")}
    campos = {k: v for k, v in datos.items() if k in ICP.__dataclass_fields__}
    icp = ICP(**{**base.__dict__, **campos})
    icp.descripcion = icp.descripcion or texto.strip()
    icp.excluir_palabras = sorted(set((icp.excluir_palabras or []) + ICP().excluir_palabras))
    return icp, {"motor": b.motor, "costo_usd": uso.costo_usd, "tokens": uso.tokens_entrada + uso.tokens_salida}


# ---------------- Mensajes ----------------

IDIOMA_REDACCION = {"es": "en español de Colombia", "pt": "em português do Brasil", "en": "in US English"}


def redactar_mensaje(lead: Lead, canal: str, icp: ICP | None = None, idioma: str = "es") -> tuple[str, dict]:
    """Texto del primer mensaje en el idioma pedido (es, pt, en). El agente lo personaliza con la señal; sin agente, plantilla en ese idioma."""
    from .mensajes import TEXTOS, cuerpo_correo, nombre_bonito, senal_en_palabras, whatsapp_texto
    idioma = idioma if idioma in TEXTOS else "es"
    b = bedrock()
    if canal == "whatsapp" or not b.disponible:
        if canal == "correo":
            return cuerpo_correo(lead, "{url_si}", "{url_no}", "{url_baja}", idioma=idioma)[0], {"motor": "plantilla", "costo_usd": 0.0, "idioma": idioma}
        return whatsapp_texto(lead, idioma), {"motor": "plantilla", "costo_usd": 0.0, "idioma": idioma}
    t = TEXTOS[idioma]
    sistema = (f"Redactas el primer mensaje de contacto comercial de Brújula a una empresa, escrito {IDIOMA_REDACCION[idioma]}, honesto y corto (máximo 90 palabras). "
               "Reglas: saluda al equipo de {empresa}; menciona la señal; explica en una frase qué hacemos (ayudamos a negocios a atender y calificar a los clientes que llaman o escriben, sin perder ninguno); "
               f"pide una llamada de 5 minutos; al final, en tres líneas aparte, pon literalmente '{t['si']}: {{url_si}}', '{t['no']}: {{url_no}}' y "
               "'{url_baja}' precedido de una frase corta para darse de baja (esas marcas se convierten en botones). Nada de promesas ni precios. "
               "Responde solo con el mensaje, en el idioma indicado.")
    usuario = json.dumps({"empresa": nombre_bonito(lead.razon_social), "ciudad": lead.ciudad.title(), "sector": lead.sector, "senal": senal_en_palabras(lead, idioma),
                          "perfil": (icp.descripcion if icp else ""), "idioma": idioma}, ensure_ascii=False)
    texto, uso = b.preguntar(sistema, usuario, max_tokens=350)
    if not texto or "{url_si}" not in texto or "{url_baja}" not in texto:
        return cuerpo_correo(lead, "{url_si}", "{url_no}", "{url_baja}", idioma=idioma)[0], {"motor": "plantilla", "costo_usd": 0.0, "idioma": idioma}
    return texto.strip(), {"motor": b.motor, "costo_usd": uso.costo_usd, "idioma": idioma}


# ---------------- Explicaciones ----------------

def explicar(contexto: dict, respaldo: str) -> str:
    b = bedrock()
    texto, _ = b.preguntar("Explica en una sola frase, en español sencillo y sin tecnicismos, para el dueño de una pyme, la decisión descrita en el JSON. Sin adjetivos de venta.",
                           json.dumps(contexto, ensure_ascii=False), max_tokens=120)
    return texto.strip() if texto else respaldo


# ---------------- Respuestas ----------------

PALABRAS_BAJA = ("baja", "no me escrib", "no me llam", "dejen de", "quitar", "eliminar", "stop", "spam")
PALABRAS_SI = ("sí", "si ", "me interesa", "claro", "dale", "cuando", "agend", "llam", "ok")
PALABRAS_DESPUES = ("después", "despues", "luego", "más adelante", "otro momento", "próxima", "proxima")
PALABRAS_NO = ("no me interesa", "no gracias", "no, gracias", "no por ahora", "ya tenemos", "no necesit")
PALABRAS_EQUIVOCADO = ("número equivocado", "numero equivocado", "no es la empresa", "no trabajo", "se equivoc")


def clasificar_respuesta_reglas(texto: str) -> str:
    t = (texto or "").lower()
    if any(p in t for p in PALABRAS_BAJA):
        return "baja"
    if any(p in t for p in PALABRAS_EQUIVOCADO):
        return "equivocado"
    if any(p in t for p in PALABRAS_NO):
        return "no_interesado"
    if any(p in t for p in PALABRAS_DESPUES):
        return "despues"
    if any(p in t for p in PALABRAS_SI):
        return "interesado"
    return "no_interesado"


def clasificar_respuesta(texto: str) -> tuple[str, dict]:
    """Jev (choice con probabilidades) si hay clave; si no, palabras clave."""
    if not config.jev_disponible or not texto:
        return clasificar_respuesta_reglas(texto), {"motor": "reglas"}
    cuerpo = {"model": config.jev_model, "state": {"respuesta_del_lead": texto},
              "questions": {"clase": {"type": "choice", "instructions": "Qué responde la empresa al primer contacto comercial.",
                                      "criteria": {"interesado": "Acepta una llamada o demostración o pide más información.",
                                                   "no_interesado": "Rechaza la propuesta sin pedir que dejen de contactarla.",
                                                   "despues": "Pide que la contacten en otro momento.",
                                                   "equivocado": "Dice que no es la empresa o la persona correcta.",
                                                   "baja": "Pide que no la vuelvan a contactar."}}}}
    try:
        r = httpx.post("https://openrouter.ai/api/alpha/decisions", json=cuerpo, timeout=30,
                       headers={"Authorization": f"Bearer {config.openrouter_api_key}"})
        r.raise_for_status()
        d = r.json()
        resp = (d.get("answers") or d).get("clase", {})
        clase = resp.get("choice") or clasificar_respuesta_reglas(texto)
        return clase, {"motor": "jev", "confianza": resp.get("confidence"), "probabilidades": resp.get("probabilities"), "costo_usd": float((d.get("usage") or {}).get("cost") or 0.0)}
    except Exception as e:  # noqa: BLE001
        return clasificar_respuesta_reglas(texto), {"motor": "reglas", "error": str(e)[:120]}
