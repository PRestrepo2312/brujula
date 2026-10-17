"""Canal correo: Resend (gratis hasta 3.000/mes, con apertura y clic por webhook). Sin clave, simula.

La respuesta se registra con un clic: "Sí, me interesa", "No, gracias" o "Baja". Cada enlace lleva un token del intento.
"""
from __future__ import annotations

import secrets

import httpx

from ..config import config
from ..mensajes import asunto_correo, cuerpo_correo
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
        texto, html = cuerpo_correo(lead, urls["si"], urls["no"], urls["baja"])
        asunto = asunto_correo(lead)
        detalle = {"token": token, "asunto": asunto}
        if not self.real:
            return Resultado(estado="enviado", costo_usd=config.tarifas.correo, ref_externa=f"sim_{token}", proveedor="simulado",
                             mensaje=texto, detalle=detalle)
        if config.email_provider == "ses":
            return self._enviar_ses(lead, asunto, texto, html, urls, detalle)
        cuerpo = {
            "from": config.email_from, "to": [lead.correo], "subject": asunto, "text": texto, "html": html,
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

    def _enviar_ses(self, lead: Lead, asunto: str, texto: str, html: str, urls: dict, detalle: dict) -> Resultado:
        """Amazon SES (exige identidad verificada y salida del sandbox). Los eventos llegan por SNS a /webhook/ses."""
        try:
            import boto3
            ses = boto3.client("sesv2", region_name=config.aws_region)
            r = ses.send_email(
                FromEmailAddress=config.email_from, Destination={"ToAddresses": [lead.correo]},
                Content={"Simple": {"Subject": {"Data": asunto, "Charset": "UTF-8"},
                                    "Body": {"Text": {"Data": texto, "Charset": "UTF-8"}, "Html": {"Data": html, "Charset": "UTF-8"}},
                                    "Headers": [{"Name": "List-Unsubscribe", "Value": f"<{urls['baja']}>"}]}},
                EmailTags=[{"Name": "canal", "Value": "correo"}],
            )
            return Resultado(estado="enviado", costo_usd=config.tarifas.correo, ref_externa=r.get("MessageId"), proveedor="ses", mensaje=texto, detalle=detalle)
        except Exception as e:  # noqa: BLE001
            return Resultado(estado="fallido", proveedor="ses", mensaje=texto, detalle={**detalle, "error": str(e)[:300]})
