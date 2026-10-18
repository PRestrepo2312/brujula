"""Notificaciones para la empresa: bandeja en la app y correo por el proveedor configurado (Brevo, SES o Resend).

Son correos internos (a la empresa que usa Brújula): van al destinatario real, sin el desvío del modo prueba, que solo aplica a los leads."""
from __future__ import annotations

from sqlmodel import select

from .config import config
from .db import sesion
from .models import Empresa, Notificacion

TITULOS = {"busqueda": "Búsqueda terminada", "lote": "Lote enviado", "respuesta": "Un lead respondió", "calificado": "Lead calificado",
           "registro": "Bienvenido a Brújula", "alerta": "Aviso de Brújula"}


def notificar(empresa_id: int, tipo: str, mensaje: str, lead_id: int | None = None) -> Notificacion:
    with sesion() as s:
        e = s.get(Empresa, empresa_id)
        n = Notificacion(empresa_id=empresa_id, tipo=tipo, mensaje=mensaje, lead_id=lead_id)
        quiere_correo = bool(e and e.correo_notificaciones and "correo" in (e.config or {}).get("notificar_por", ["app", "correo"]))
        if quiere_correo and config.correo_real:
            n.enviada_correo = _correo(e.correo_notificaciones, f"Brújula: {TITULOS.get(tipo, tipo)}", mensaje, tipo=tipo)
        s.add(n)
        s.commit()
        s.refresh(n)
        return n


def _correo(destino: str, asunto: str, texto: str, tipo: str = "") -> bool:
    from .channels.correo import enviar_transaccional
    from .mensajes import html_aviso
    base = config.public_base_url.rstrip("/")
    html = html_aviso(TITULOS.get(tipo, "Aviso de Brújula"), [texto], f"{base}/app/notificaciones", "Ver en Brújula",
                      pie="Recibe este correo porque su empresa pidió avisos por correo en Configuración.")
    ok, _ref, _err = enviar_transaccional(destino, asunto, texto, html)
    return ok


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
