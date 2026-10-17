"""Primer mensaje por canal. Corto, honesto, con la señal del lead y la baja en el mismo mensaje."""
from __future__ import annotations

from .models import Lead

REMITENTE = "el equipo Brújula"
PROPOSITO = ("estamos probando una herramienta que ayuda a negocios como el suyo a atender y calificar a los clientes que "
             "escriben o llaman, sin perder ninguno")


def senal_en_palabras(lead: Lead) -> str:
    s = lead.senales or {}
    if "contrato_secop" in s:
        return "vimos que ganaron un contrato público hace poco"
    if "registro_reciente_secop" in s:
        return "vimos que se registraron hace poco como proveedores"
    if "empresa_nueva" in s:
        return "vimos que la empresa es reciente"
    if lead.sector == "salud":
        return "atienden pacientes que llaman o escriben para pedir cita"
    if lead.sector == "educacion":
        return "reciben familias que preguntan por matrículas"
    if lead.sector == "turismo":
        return "reciben reservas y preguntas por teléfono y WhatsApp"
    return "atienden clientes por teléfono o mensajes"


def asunto_correo(lead: Lead) -> str:
    return f"{nombre_bonito(lead.razon_social)}: ¿cuántos clientes se pierden por no contestar a tiempo?"


def cuerpo_correo(lead: Lead, url_si: str, url_no: str, url_baja: str) -> tuple[str, str]:
    """Devuelve (texto plano, html). El HTML lleva la marca y botones; el texto plano lleva los mismos enlaces."""
    nombre = nombre_bonito(lead.razon_social)
    senal = senal_en_palabras(lead)
    texto = (f"Hola, equipo de {nombre}.\n\n"
             f"Les escribe {REMITENTE}: {PROPOSITO}. Les escribimos porque {senal}.\n\n"
             f"¿Les sirve una llamada de 5 minutos para mostrarles cómo funciona?\n"
             f"Sí, me interesa: {url_si}\nNo, gracias: {url_no}\n\n"
             f"Si no quieren recibir más mensajes nuestros, este enlace los da de baja de inmediato: {url_baja}")
    return texto, html_correo(texto, url_si, url_no, url_baja)


SIGLAS = {"SAS", "S.A.S", "S.A.S.", "LTDA", "LTDA.", "S.A", "S.A.", "SA", "EU", "E.U.", "IPS", "EPS", "ARL", "CIA", "CIA."}
MINUSCULAS = {"Y", "E", "DE", "DEL", "LA", "LAS", "LOS", "EL", "EN", "POR", "PARA"}


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


def html_correo(texto: str, url_si: str, url_no: str, url_baja: str, nota: str = "") -> str:
    """HTML con la marca de Brújula a partir del texto plano: las líneas con enlaces se vuelven botones y pie."""
    import html as _h
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
        f'<a href="{url_si}" style="display:inline-block;background:#E3661B;color:#ffffff;padding:11px 18px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:14px">S&iacute;, me interesa</a>'
        f'&nbsp;&nbsp;<a href="{url_no}" style="display:inline-block;border:1px solid #2E2A5A;color:#2E2A5A;padding:10px 18px;border-radius:8px;text-decoration:none;font-size:14px">No, gracias</a>'
        '</td></tr>'
        '<tr><td style="padding:14px 24px 20px;border-top:1px solid #E6E1D8;font-size:12px;color:#7A7891;line-height:1.5">'
        f'Equipo Br&uacute;jula. Si no quieren recibir m&aacute;s mensajes nuestros, <a href="{url_baja}" style="color:#7A7891">este enlace los da de baja</a> de inmediato.'
        '</td></tr></table></td></tr></table></body></html>'
    )


def variables_voz(lead: Lead) -> dict:
    """Variables que el agente de voz de Dapta puede leer durante la llamada."""
    return {
        "empresa": nombre_bonito(lead.razon_social),
        "ciudad": lead.ciudad.title(),
        "sector": lead.sector or "servicios",
        "senal": senal_en_palabras(lead),
        "contact_email": lead.correo or "",
    }


def whatsapp_texto(lead: Lead) -> str:
    return (f"Hola, equipo de {nombre_bonito(lead.razon_social)}. Les escribe {REMITENTE}: {PROPOSITO}. "
            f"¿Les sirve una llamada de 5 minutos? Responda SÍ o NO. Para no recibir más mensajes responda BAJA.")
