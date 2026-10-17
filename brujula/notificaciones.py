"""Notificaciones para la empresa: bandeja en la app y correo (SES) cuando está configurado y hay remitente verificado."""
from __future__ import annotations

from sqlmodel import select

from .config import config
from .db import sesion
from .models import Empresa, Notificacion


def notificar(empresa_id: int, tipo: str, mensaje: str, lead_id: int | None = None) -> Notificacion:
    with sesion() as s:
        e = s.get(Empresa, empresa_id)
        n = Notificacion(empresa_id=empresa_id, tipo=tipo, mensaje=mensaje, lead_id=lead_id)
        quiere_correo = bool(e and e.correo_notificaciones and "correo" in (e.config or {}).get("notificar_por", ["app", "correo"]))
        if quiere_correo and config.email_provider == "ses":
            n.enviada_correo = _correo(e.correo_notificaciones, f"Brújula: {tipo}", mensaje)
        s.add(n)
        s.commit()
        s.refresh(n)
        return n


def _correo(destino: str, asunto: str, texto: str) -> bool:
    try:
        import boto3
        ses = boto3.client("sesv2", region_name=config.aws_region)
        ses.send_email(FromEmailAddress=config.email_from, Destination={"ToAddresses": [destino]},
                       Content={"Simple": {"Subject": {"Data": asunto, "Charset": "UTF-8"}, "Body": {"Text": {"Data": texto, "Charset": "UTF-8"}}}})
        return True
    except Exception:  # noqa: BLE001
        return False


def listar(empresa_id: int, solo_no_leidas: bool = False, limite: int = 50) -> list[Notificacion]:
    with sesion() as s:
        st = select(Notificacion).where(Notificacion.empresa_id == empresa_id)
        if solo_no_leidas:
            st = st.where(Notificacion.leida.is_(False))
        return list(s.exec(st.order_by(Notificacion.id.desc()).limit(limite)))


def marcar_leida(empresa_id: int, notificacion_id: int | None = None) -> int:
    with sesion() as s:
        st = select(Notificacion).where(Notificacion.empresa_id == empresa_id, Notificacion.leida.is_(False))
        if notificacion_id:
            st = st.where(Notificacion.id == notificacion_id)
        n = 0
        for x in s.exec(st):
            x.leida = True
            s.add(x)
            n += 1
        s.commit()
        return n
