"""Primer mensaje por canal, en el idioma del lead. Corto, honesto, con la señal del lead y la baja en el mismo mensaje.

El idioma sale de la fuente del lead (CO y MX en español, BR en portugués, US en inglés) o del que la empresa fije por fuente
en su configuración. Las plantillas están en los tres idiomas; con agente de texto, él redacta directamente en ese idioma.
"""
from __future__ import annotations

from .models import Lead

IDIOMAS = {"es": "Español", "pt": "Português", "en": "English"}
IDIOMA_POR_PAIS = {"CO": "es", "MX": "es", "BR": "pt", "US": "en"}

REMITENTE = "el equipo Brújula"
PROPOSITO = ("estamos probando una herramienta que ayuda a negocios como el suyo a atender y calificar a los clientes que "
             "escriben o llaman, sin perder ninguno")

SENALES = {
    "es": {"contrato_secop": "vimos que ganaron un contrato público hace poco",
           "registro_reciente_secop": "vimos que se registraron hace poco como proveedores",
           "empresa_nueva": "vimos que la empresa es reciente",
           "salud": "atienden pacientes que llaman o escriben para pedir cita",
           "educacion": "reciben familias que preguntan por matrículas",
           "turismo": "reciben reservas y preguntas por teléfono y WhatsApp",
           "": "atienden clientes por teléfono o mensajes"},
    "pt": {"contrato_secop": "vimos que ganharam um contrato público há pouco",
           "registro_reciente_secop": "vimos que se cadastraram há pouco como fornecedores",
           "empresa_nueva": "vimos que a empresa é recente",
           "salud": "atendem pacientes que ligam ou escrevem para marcar consulta",
           "educacion": "recebem famílias perguntando sobre matrículas",
           "turismo": "recebem reservas e perguntas por telefone e WhatsApp",
           "": "atendem clientes por telefone ou mensagens"},
    "en": {"contrato_secop": "we saw you recently won a public contract",
           "registro_reciente_secop": "we saw you recently registered as a supplier",
           "empresa_nueva": "we saw the company is new",
           "salud": "you see patients who call or message to book appointments",
           "educacion": "you hear from families asking about enrollment",
           "turismo": "you take bookings and questions by phone and WhatsApp",
           "": "you serve customers by phone or messages"},
}

TEXTOS = {
    "es": {
        "asunto": "{nombre}: ¿cuántos clientes se pierden por no contestar a tiempo?",
        "hola": "Hola, equipo de {nombre}.",
        "presentacion": f"Les escribe {REMITENTE}: {PROPOSITO}. Les escribimos porque {{senal}}.",
        "pregunta": "¿Les sirve una llamada de 5 minutos para mostrarles cómo funciona?",
        "si": "Sí, me interesa", "no": "No, gracias",
        "baja_texto": "Si no quieren recibir más mensajes nuestros, este enlace los da de baja de inmediato",
        "pie": "Equipo Brújula. Si no quieren recibir más mensajes nuestros,", "pie_enlace": "este enlace los da de baja", "pie_fin": "de inmediato.",
        "whatsapp": "Hola, equipo de {nombre}. Les escribe el equipo Brújula: {proposito}. ¿Les sirve una llamada de 5 minutos? Responda SÍ o NO. Para no recibir más mensajes responda BAJA.",
    },
    "pt": {
        "asunto": "{nombre}: quantos clientes se perdem por não responder a tempo?",
        "hola": "Olá, equipe da {nombre}.",
        "presentacion": "Aqui é a equipe Brújula: estamos testando uma ferramenta que ajuda negócios como o seu a atender e qualificar os clientes que escrevem ou ligam, sem perder nenhum. Escrevemos porque {senal}.",
        "pregunta": "Uma ligação de 5 minutos para mostrar como funciona ajudaria?",
        "si": "Sim, tenho interesse", "no": "Não, obrigado",
        "baja_texto": "Se não quiserem receber mais mensagens nossas, este link cancela o envio imediatamente",
        "pie": "Equipe Brújula. Se não quiserem receber mais mensagens nossas,", "pie_enlace": "este link cancela o envio", "pie_fin": "imediatamente.",
        "whatsapp": "Olá, equipe da {nombre}. Aqui é a equipe Brújula: estamos testando uma ferramenta que ajuda negócios como o seu a atender e qualificar os clientes que escrevem ou ligam. Uma ligação de 5 minutos ajudaria? Responda SIM ou NÃO. Para não receber mais mensagens responda SAIR.",
    },
    "en": {
        "asunto": "{nombre}: how many customers are lost by not answering in time?",
        "hola": "Hello, {nombre} team.",
        "presentacion": "This is the Brújula team: we are testing a tool that helps businesses like yours answer and qualify the customers who write or call, without losing any. We are reaching out because {senal}.",
        "pregunta": "Would a 5-minute call to show you how it works be useful?",
        "si": "Yes, I'm interested", "no": "No, thanks",
        "baja_texto": "If you don't want to hear from us again, this link unsubscribes you immediately",
        "pie": "Brújula team. If you don't want to hear from us again,", "pie_enlace": "this link unsubscribes you", "pie_fin": "immediately.",
        "whatsapp": "Hello, {nombre} team. This is the Brújula team: we are testing a tool that helps businesses like yours answer and qualify the customers who write or call. Would a 5-minute call be useful? Reply YES or NO. To stop receiving messages reply STOP.",
    },
}

SIGLAS = {"SAS", "S.A.S", "S.A.S.", "LTDA", "LTDA.", "S.A", "S.A.", "SA", "EU", "E.U.", "IPS", "EPS", "ARL", "CIA", "CIA.", "LLC", "INC", "INC.", "ME", "EPP", "EIRELI"}
MINUSCULAS = {"Y", "E", "DE", "DEL", "LA", "LAS", "LOS", "EL", "EN", "POR", "PARA", "DA", "DO", "DAS", "DOS", "OF", "AND", "THE"}


def _t(idioma: str) -> dict:
    return TEXTOS.get(idioma) or TEXTOS["es"]


def idioma_de(lead: Lead, empresa_id: int | None = None) -> str:
    """Idioma del mensaje: el que la empresa fijó para la fuente del lead; si no, el del país del lead."""
    if empresa_id is not None:
        from .empresas import config_de
        fijado = (config_de(empresa_id).get("idiomas") or {}).get(lead.fuente_clave)
        if fijado in IDIOMAS:
            return fijado
    return IDIOMA_POR_PAIS.get((lead.pais or "CO").upper(), "es")


def nombre_bonito(razon_social: str) -> str:
    """Razón social legible: Título, con siglas societarias en mayúscula y conectores en minúscula."""
    palabras = []
    for i, p in enumerate((razon_social or "").split()):
        u = p.upper()
        if u in SIGLAS:
            palabras.append(u)
        elif u in MINUSCULAS and i > 0:
            palabras.append(u.lower())
        else:
            palabras.append(p.capitalize())
    return " ".join(palabras)


def senal_en_palabras(lead: Lead, idioma: str = "es") -> str:
    s = lead.senales or {}
    frases = SENALES.get(idioma) or SENALES["es"]
    for clave in ("contrato_secop", "registro_reciente_secop", "empresa_nueva"):
        if clave in s:
            return frases[clave]
    return frases.get(lead.sector or "", frases[""])


def asunto_correo(lead: Lead, idioma: str = "es") -> str:
    return _t(idioma)["asunto"].format(nombre=nombre_bonito(lead.razon_social))


def cuerpo_correo(lead: Lead, url_si: str, url_no: str, url_baja: str, idioma: str = "es") -> tuple[str, str]:
    """Devuelve (texto plano, html). El HTML lleva la marca y botones; el texto plano lleva los mismos enlaces."""
    t = _t(idioma)
    nombre = nombre_bonito(lead.razon_social)
    senal = senal_en_palabras(lead, idioma)
    texto = (f"{t['hola'].format(nombre=nombre)}\n\n"
             f"{t['presentacion'].format(senal=senal)}\n\n"
             f"{t['pregunta']}\n"
             f"{t['si']}: {url_si}\n{t['no']}: {url_no}\n\n"
             f"{t['baja_texto']}: {url_baja}")
    return texto, html_correo(texto, url_si, url_no, url_baja, idioma=idioma)


def html_correo(texto: str, url_si: str, url_no: str, url_baja: str, nota: str = "", idioma: str = "es") -> str:
    """HTML con la marca de Brújula a partir del texto plano: las líneas con enlaces se vuelven botones y pie."""
    import html as _h
    t = _t(idioma)
    marcas = (url_si, url_no, url_baja, "{url_si}", "{url_no}", "{url_baja}")
    parrafos = []
    for bloque in texto.split("\n\n"):
        lineas = [l for l in bloque.split("\n") if l.strip() and not any(m in l for m in marcas)]
        if lineas:
            parrafos.append("<br>".join(_h.escape(l) for l in lineas))
    cuerpo = "".join(f'<p style="margin:0 0 14px;font-size:15px;line-height:1.55;color:#3B3A52">{p}</p>' for p in parrafos)
    nota_html = f'<p style="margin:0 0 14px;font-size:12px;color:#7A7891"><i>{_h.escape(nota)}</i></p>' if nota else ""
    return (
        '<!doctype html><html><body style="margin:0;padding:0;background:#FAF8F3;font-family:\'Segoe UI\',Arial,sans-serif">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#FAF8F3;padding:24px 12px"><tr><td align="center">'
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border:1px solid #E6E1D8;border-radius:12px">'
        '<tr><td style="background:#2E2A5A;padding:14px 24px;color:#ffffff;font-size:12px;letter-spacing:0.18em;font-weight:bold;border-radius:12px 12px 0 0">'
        '<span style="color:#E3661B">&#9679;</span>&nbsp; BR&Uacute;JULA</td></tr>'
        f'<tr><td style="padding:24px 24px 6px">{nota_html}{cuerpo}</td></tr>'
        '<tr><td style="padding:4px 24px 22px">'
        f'<a href="{url_si}" style="display:inline-block;background:#E3661B;color:#ffffff;padding:11px 18px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:14px">{_h.escape(t["si"])}</a>'
        f'&nbsp;&nbsp;<a href="{url_no}" style="display:inline-block;border:1px solid #2E2A5A;color:#2E2A5A;padding:10px 18px;border-radius:8px;text-decoration:none;font-size:14px">{_h.escape(t["no"])}</a>'
        '</td></tr>'
        '<tr><td style="padding:14px 24px 20px;border-top:1px solid #E6E1D8;font-size:12px;color:#7A7891;line-height:1.5">'
        f'{_h.escape(t["pie"])} <a href="{url_baja}" style="color:#7A7891">{_h.escape(t["pie_enlace"])}</a> {_h.escape(t["pie_fin"])}'
        '</td></tr></table></td></tr></table></body></html>'
    )


def variables_voz(lead: Lead) -> dict:
    """Variables que el agente de voz de Dapta puede leer durante la llamada (el agente habla español)."""
    return {
        "empresa": nombre_bonito(lead.razon_social),
        "ciudad": lead.ciudad.title(),
        "sector": lead.sector or "servicios",
        "senal": senal_en_palabras(lead, "es"),
        "contact_email": lead.correo or "",
    }


def whatsapp_texto(lead: Lead, idioma: str = "es") -> str:
    return _t(idioma)["whatsapp"].format(nombre=nombre_bonito(lead.razon_social), proposito=PROPOSITO)
