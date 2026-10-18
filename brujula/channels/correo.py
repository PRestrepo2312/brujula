"""Canal correo: Resend (gratis hasta 3.000/mes, con apertura y clic por webhook). Sin clave, simula.

La respuesta se registra con un clic: "Sí, me interesa", "No, gracias" o "Baja". Cada enlace lleva un token del intento.
"""
from __future__ import annotations

import secrets

import httpx

from ..config import config
from ..mensajes import asunto_correo, cuerpo_correo, html_correo, idioma_de
from ..models import Intento, Lead
from .base import Canal, Resultado


class CanalCorreo(Canal):
    clave = "correo"
    nombre = "Correo"

    @property
    def real(self) -> bool:
        return config.correo_real

    def enviar(self, lead: Lead, intento: Intento) -> Resultado:
        token = intento.detalle.get("token") or secrets.token_urlsafe(12)
        base = config.public_base_url.rstrip("/")
        urls = {v: f"{base}/r/{token}?v={v}" for v in ("si", "no", "baja")}
        from ..empresas import perfil_de
        idioma = idioma_de(lead, intento.empresa_id)
        perfil = perfil_de(intento.empresa_id)
        texto, _ = cuerpo_correo(lead, urls["si"], urls["no"], urls["baja"], idioma=idioma, perfil=perfil)
        redactado = (intento.detalle or {}).get("texto")
        if redactado and "{url_si}" in redactado:
            texto = redactado.replace("{url_si}", urls["si"]).replace("{url_no}", urls["no"]).replace("{url_baja}", urls["baja"])
        asunto = asunto_correo(lead, idioma)
        detalle = {"token": token, "asunto": asunto, "idioma": idioma}
        destino, nota = lead.correo, ""
        if config.modo_prueba:
            # Desvío: el correo lleva el pitch de la empresa real, pero va a un correo verificado del equipo. Nunca al correo del lead.
            destino = config.destino_prueba("correo", lead.id or 0)
            if not destino:
                return Resultado(estado="omitido", costo_usd=0.0, proveedor="bloqueado", mensaje=texto, detalle={**detalle, "motivo": "modo prueba: sin CORREOS_PRUEBA"})
            detalle["desvio"] = {"original": lead.correo, "destino": destino}
            nota = f"Prueba: este correo iba para {lead.correo}"
        # El HTML con la marca (botones en vez de enlaces sueltos) se arma siempre a partir del texto, sea plantilla o redacción del agente.
        html = html_correo(texto, urls["si"], urls["no"], urls["baja"], nota=nota, idioma=idioma, perfil=perfil)
        if nota:
            texto = f"[{nota}]\n\n{texto}"
        if not self.real:
            return Resultado(estado="enviado", costo_usd=config.tarifas.correo, ref_externa=f"sim_{token}", proveedor="simulado",
                             mensaje=texto, detalle=detalle)
        if config.email_provider == "ses":
            return self._enviar_ses(destino, asunto, texto, html, urls, detalle)
        if config.email_provider == "brevo":
            ok, ref, err = enviar_transaccional(destino, asunto, texto, html, {"List-Unsubscribe": f"<{urls['baja']}>"})
            return Resultado(estado="enviado" if ok else "fallido", costo_usd=config.tarifas.correo if ok else 0.0, ref_externa=ref or None,
                             proveedor="brevo", mensaje=texto, detalle={**detalle, **({"error": err} if err else {})})
        cuerpo = {
            "from": config.email_from, "to": [destino], "subject": asunto, "text": texto, "html": html,
            "headers": {"List-Unsubscribe": f"<{urls['baja']}>"},
            "tags": [{"name": "intento", "value": str(intento.id or 0)}],
        }
        try:
            r = httpx.post("https://api.resend.com/emails", json=cuerpo, timeout=30,
                           headers={"Authorization": f"Bearer {config.resend_api_key}"})
            if r.status_code >= 300:
                return Resultado(estado="fallido", costo_usd=0.0, proveedor="resend", mensaje=texto, detalle={**detalle, "error": r.text[:300]})
            return Resultado(estado="enviado", costo_usd=config.tarifas.correo, ref_externa=r.json().get("id"), proveedor="resend",
                             mensaje=texto, detalle=detalle)
        except httpx.HTTPError as e:
            return Resultado(estado="fallido", proveedor="resend", mensaje=texto, detalle={**detalle, "error": str(e)[:300]})

    def _enviar_ses(self, destino: str, asunto: str, texto: str, html: str, urls: dict, detalle: dict) -> Resultado:   # noqa: D102
        """Amazon SES (exige identidad verificada; en el sandbox también el destinatario). Los eventos llegan por SNS a /webhook/ses."""
        try:
            import boto3
            ses = boto3.client("sesv2", region_name=config.aws_region)
            r = ses.send_email(
                FromEmailAddress=config.email_from, Destination={"ToAddresses": [destino]},
                Content={"Simple": {"Subject": {"Data": asunto, "Charset": "UTF-8"},
                                    "Body": {"Text": {"Data": texto, "Charset": "UTF-8"}, "Html": {"Data": html, "Charset": "UTF-8"}},
                                    "Headers": [{"Name": "List-Unsubscribe", "Value": f"<{urls['baja']}>"}]}},
                EmailTags=[{"Name": "canal", "Value": "correo"}],
            )
            return Resultado(estado="enviado", costo_usd=config.tarifas.correo, ref_externa=r.get("MessageId"), proveedor="ses", mensaje=texto, detalle=detalle)
        except Exception as e:  # noqa: BLE001
            return Resultado(estado="fallido", proveedor="ses", mensaje=texto, detalle={**detalle, "error": str(e)[:300]})


def _remitente() -> tuple[str, str]:
    """EMAIL_FROM 'Brujula <hola@x.co>' → (nombre, dirección); Brevo los pide por separado."""
    from email.utils import parseaddr
    nombre, direccion = parseaddr(config.email_from)
    return (nombre or "Brújula", direccion or config.email_from)


def enviar_transaccional(destino: str, asunto: str, texto: str, html: str = "", cabeceras: dict | None = None) -> tuple[bool, str, str]:
    """Un correo del sistema (bienvenida, notificación a la empresa, aviso) por el proveedor configurado, SIN desvío de modo prueba:
    va al destinatario real. Devuelve (ok, referencia, error). Los correos a leads siguen pasando por Correo.enviar, que sí desvía."""
    if not config.correo_real:
        return False, "", "correo no configurado"
    try:
        if config.email_provider == "brevo":
            nombre, direccion = _remitente()
            cuerpo: dict = {"sender": {"name": nombre, "email": direccion}, "to": [{"email": destino}], "subject": asunto, "textContent": texto}
            if html:
                cuerpo["htmlContent"] = html
            if cabeceras:
                cuerpo["headers"] = cabeceras
            r = httpx.post("https://api.brevo.com/v3/smtp/email", json=cuerpo, timeout=30, headers={"api-key": config.brevo_api_key, "accept": "application/json"})
            if r.status_code >= 300:
                return False, "", r.text[:300]
            return True, str((r.json() or {}).get("messageId", "")), ""
        if config.email_provider == "ses":
            import boto3
            ses = boto3.client("sesv2", region_name=config.aws_region)
            body = {"Text": {"Data": texto, "Charset": "UTF-8"}}
            if html:
                body["Html"] = {"Data": html, "Charset": "UTF-8"}
            r = ses.send_email(FromEmailAddress=config.email_from, Destination={"ToAddresses": [destino]},
                               Content={"Simple": {"Subject": {"Data": asunto, "Charset": "UTF-8"}, "Body": body}})
            return True, str(r.get("MessageId", "")), ""
        cuerpo = {"from": config.email_from, "to": [destino], "subject": asunto, "text": texto}
        if html:
            cuerpo["html"] = html
        r = httpx.post("https://api.resend.com/emails", json=cuerpo, timeout=30, headers={"Authorization": f"Bearer {config.resend_api_key}"})
        if r.status_code >= 300:
            return False, "", r.text[:300]
        return True, str(r.json().get("id", "")), ""
    except Exception as e:  # noqa: BLE001
        return False, "", str(e)[:300]
