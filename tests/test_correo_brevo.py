"""Brevo como proveedor de correos del sistema: la petición lleva la clave en la cabecera api-key y el remitente partido en nombre y dirección."""
from brujula import notificaciones
from brujula.channels import correo
from brujula.config import config


class _Resp:
    status_code = 201
    text = ""

    def json(self):
        return {"messageId": "<m-1@brevo>"}


def test_enviar_transaccional_por_brevo(monkeypatch):
    for k, v in {"email_provider": "brevo", "brevo_api_key": "clave-prueba", "email_from": "Brujula <hola@brujula.test>"}.items():
        object.__setattr__(config, k, v)
    capturado = {}

    def post(url, json=None, timeout=None, headers=None):
        capturado.update({"url": url, "json": json, "headers": headers})
        return _Resp()
    try:
        monkeypatch.setattr(correo.httpx, "post", post)
        ok, ref, err = correo.enviar_transaccional("alguien@empresa.co", "Hola", "texto plano", "<p>html</p>")
        assert ok and ref == "<m-1@brevo>" and err == ""
        assert capturado["url"] == "https://api.brevo.com/v3/smtp/email" and capturado["headers"]["api-key"] == "clave-prueba"
        assert capturado["json"]["sender"] == {"name": "Brujula", "email": "hola@brujula.test"} and capturado["json"]["to"] == [{"email": "alguien@empresa.co"}]
        assert capturado["json"]["htmlContent"] == "<p>html</p>" and capturado["json"]["textContent"] == "texto plano"
        assert config.correo_real
    finally:
        object.__setattr__(config, "email_provider", "resend"); object.__setattr__(config, "brevo_api_key", "")


def test_notificacion_va_al_correo_real_sin_desvio(monkeypatch):
    """Las notificaciones a la empresa no pasan por el desvío del modo prueba: van al correo de la empresa."""
    from brujula import empresas
    from brujula.icp import ICP
    e = empresas.crear("Empresa Avisos", "duena@empresa.co", "", ICP().__dict__)
    for k, v in {"email_provider": "brevo", "brevo_api_key": "clave-prueba"}.items():
        object.__setattr__(config, k, v)
    try:
        enviados = []
        monkeypatch.setattr(correo, "enviar_transaccional", lambda destino, asunto, texto, html="", cabeceras=None: (enviados.append((destino, asunto)) or (True, "x", "")))
        n = notificaciones.notificar(e.id, "busqueda", "Búsqueda en REPS: 12 empresas nuevas")
        assert n.enviada_correo and enviados == [("duena@empresa.co", "Brújula: Búsqueda terminada")]
    finally:
        for k, v in {"email_provider": "resend", "brevo_api_key": ""}.items():
            object.__setattr__(config, k, v)
