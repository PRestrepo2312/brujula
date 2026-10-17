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
    return f"{lead.razon_social.title()}: ¿cuántos clientes se pierden por no contestar a tiempo?"


def cuerpo_correo(lead: Lead, url_si: str, url_no: str, url_baja: str) -> tuple[str, str]:
    """Devuelve (texto plano, html)."""
    nombre = lead.razon_social.title()
    senal = senal_en_palabras(lead)
    texto = (f"Hola, equipo de {nombre}.\n\n"
             f"Les escribe {REMITENTE}: {PROPOSITO}. Les escribimos porque {senal}.\n\n"
             f"¿Les sirve una llamada de 5 minutos para mostrarles cómo funciona?\n"
             f"Sí, me interesa: {url_si}\nNo, gracias: {url_no}\n\n"
             f"Si no quieren recibir más mensajes nuestros, este enlace los da de baja de inmediato: {url_baja}\n\n"
             f"Datos de contacto tomados de registros públicos de empresas (datos.gov.co).")
    html = (f"<p>Hola, equipo de <b>{nombre}</b>.</p>"
            f"<p>Les escribe {REMITENTE}: {PROPOSITO}. Les escribimos porque {senal}.</p>"
            f"<p>¿Les sirve una llamada de 5 minutos para mostrarles cómo funciona?</p>"
            f"<p><a href=\"{url_si}\" style=\"background:#E3661B;color:#fff;padding:10px 16px;border-radius:6px;text-decoration:none\">Sí, me interesa</a>"
            f"&nbsp;&nbsp;<a href=\"{url_no}\" style=\"color:#2E2A5A\">No, gracias</a></p>"
            f"<p style=\"color:#7A7891;font-size:12px\">Si no quieren recibir más mensajes nuestros, <a href=\"{url_baja}\">este enlace los da de baja</a> de inmediato. "
            f"Datos de contacto tomados de registros públicos de empresas (datos.gov.co).</p>")
    return texto, html


def variables_voz(lead: Lead) -> dict:
    """Variables que el agente de voz de Dapta puede leer durante la llamada."""
    return {
        "empresa": lead.razon_social.title(),
        "ciudad": lead.ciudad.title(),
        "sector": lead.sector or "servicios",
        "senal": senal_en_palabras(lead),
        "contact_email": lead.correo or "",
    }


def whatsapp_texto(lead: Lead) -> str:
    return (f"Hola, equipo de {lead.razon_social.title()}. Les escribe {REMITENTE}: {PROPOSITO}. "
            f"¿Les sirve una llamada de 5 minutos? Responda SÍ o NO. Para no recibir más mensajes responda BAJA.")
