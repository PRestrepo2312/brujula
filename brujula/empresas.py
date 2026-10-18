"""Empresas (cuentas): la de demostración siempre existe; cada una tiene su ICP, sus canales y su Dapta."""
from __future__ import annotations

import re

from sqlmodel import select

from .config import config
from .db import sesion
from .icp import ICP
from .models import EMPRESA_DEMO, Empresa

CONFIG_DEFECTO = {
    "canales": ["voz", "correo"],
    "presupuesto_lote": 20,
    "contacto_automatico": False,  # True = el cron de la ventana legal arma y envía lotes solo; False = solo cuando la persona lo pide (Lotes o el chat)
    "umbral_contacto": 0.7,        # encaje mínimo para entrar en un lote (0.7 = lo que la brújula considera "encaja"; la empresa puede subirlo)
    "notificar_por": ["app", "correo"],
    "remitente": "",
    "respetar_ley_2300": True,     # False = la empresa asume la responsabilidad de contactar fuera del horario legal (queda en la bitácora)
    "idiomas": {},                 # idioma de los mensajes por fuente, p. ej. {"nyc": "en"}; sin valor, el del país de la fuente
    "perfil": {},                  # perfil comercial: nombre, que_ofrece, a_quien, diferencial, remitente, sitio_web, nit (lo que dicen los mensajes)
}

# La empresa de demostración habla como Brújula; cualquier otra habla de sí misma (su perfil lo llena el asistente de inicio).
PERFIL_DEMO = {
    "nombre": "Brújula",
    "que_ofrece": "estamos probando una herramienta que ayuda a negocios como el suyo a atender y calificar a los clientes que escriben o llaman, sin perder ninguno",
    "a_quien": "pymes de servicios que reciben clientes por teléfono o WhatsApp: clínicas, colegios, hoteles y agencias",
    "diferencial": "mide cuánto cuesta cada cliente calificado por fuente y canal",
    "remitente": "el equipo Brújula",
}


def perfil_de(empresa_id: int) -> dict:
    """Perfil comercial con el que la empresa se presenta en correos, WhatsApp y llamadas. completo=False si aún no lo llenó."""
    e = obtener(empresa_id)
    guardado = dict(((e.config or {}).get("perfil") or {}) if e else {})
    if empresa_id == EMPRESA_DEMO and not guardado.get("que_ofrece"):
        guardado = {**PERFIL_DEMO, **guardado}
    nombre = (guardado.get("nombre") or (e.nombre if e else "") or "la empresa").strip()
    que_ofrece = (guardado.get("que_ofrece") or "").strip()
    return {
        "nombre": nombre,
        "que_ofrece": que_ofrece or f"{nombre} ofrece sus servicios a empresas como la suya",
        "a_quien": (guardado.get("a_quien") or "").strip(),
        "diferencial": (guardado.get("diferencial") or "").strip(),
        "remitente": (guardado.get("remitente") or f"el equipo de {nombre}").strip(),
        "sitio_web": (guardado.get("sitio_web") or "").strip(),
        "nit": (guardado.get("nit") or "").strip(),
        "completo": bool(que_ofrece),
    }


def slug_de(nombre: str) -> str:
    from .normalize import sin_tildes
    s = re.sub(r"[^a-z0-9]+", "-", sin_tildes(nombre).lower()).strip("-")
    return s[:40] or "empresa"


def asegurar_demo() -> Empresa:
    with sesion() as s:
        e = s.get(Empresa, EMPRESA_DEMO)
        if not e:
            e = Empresa(id=EMPRESA_DEMO, nombre="JFB Devs (demostración)", slug="jfb-devs", correo_notificaciones="",
                        icp=ICP().__dict__, icp_texto=ICP().descripcion, config=dict(CONFIG_DEFECTO))
            s.add(e)
            s.commit()
            s.refresh(e)
        if s.get_bind().dialect.name == "postgresql":
            # La demo se inserta con id fijo: la secuencia de PostgreSQL debe quedar por encima para que la siguiente empresa no choque.
            from sqlalchemy import text
            s.exec(text("SELECT setval(pg_get_serial_sequence('empresa', 'id'), GREATEST((SELECT MAX(id) FROM empresa), 1))"))
            s.commit()
        return e


def obtener(empresa_id: int) -> Empresa | None:
    with sesion() as s:
        return s.get(Empresa, empresa_id)


def listar() -> list[Empresa]:
    with sesion() as s:
        return list(s.exec(select(Empresa).order_by(Empresa.id)))


def crear(nombre: str, correo_notificaciones: str = "", icp_texto: str = "", icp: dict | None = None) -> Empresa:
    base = slug_de(nombre)
    with sesion() as s:
        slug = base
        n = 2
        while s.exec(select(Empresa).where(Empresa.slug == slug)).first():
            slug = f"{base}-{n}"
            n += 1
        e = Empresa(nombre=nombre, slug=slug, correo_notificaciones=correo_notificaciones, icp=icp or ICP().__dict__,
                    icp_texto=icp_texto or ICP().descripcion, config=dict(CONFIG_DEFECTO))
        s.add(e)
        s.commit()
        s.refresh(e)
        return e


def actualizar(empresa_id: int, **campos) -> Empresa | None:
    permitidos = {"nombre", "correo_notificaciones", "dapta_api_key", "dapta_agent_id", "dapta_sequence_id", "icp", "icp_texto", "config"}
    with sesion() as s:
        e = s.get(Empresa, empresa_id)
        if not e:
            return None
        for k, v in campos.items():
            if k in permitidos and v is not None:
                if k == "config":
                    v = {**(e.config or {}), **v}
                setattr(e, k, v)
        s.add(e)
        s.commit()
        s.refresh(e)
        return e


def icp_de(empresa_id: int) -> ICP:
    e = obtener(empresa_id)
    if e and e.icp:
        return ICP(**{k: v for k, v in e.icp.items() if k in ICP.__dataclass_fields__})
    return ICP()


def guardar_icp(empresa_id: int, icp: ICP, texto: str | None = None) -> ICP:
    actualizar(empresa_id, icp=icp.__dict__, icp_texto=texto)
    return icp


def config_de(empresa_id: int) -> dict:
    e = obtener(empresa_id)
    return {**CONFIG_DEFECTO, **((e.config or {}) if e else {})}


def dapta_de(empresa_id: int) -> dict:
    """Claves de Dapta de la empresa; si no tiene, las del servidor (la demo)."""
    from .channels.voz_dapta import ids_dapta
    e = obtener(empresa_id)
    base = {"api_key": config.dapta_api_key, **ids_dapta()}
    if e:
        if e.dapta_api_key:
            base["api_key"] = e.dapta_api_key
        if e.dapta_agent_id:
            base["agent_id"] = e.dapta_agent_id
        if e.dapta_sequence_id:
            base["sequence_id"] = e.dapta_sequence_id
    return base


def publico(e: Empresa) -> dict:
    """Lo que se devuelve al front: nunca la clave de Dapta, solo si está puesta."""
    d = e.model_dump()
    d["dapta_api_key"] = "configurada" if e.dapta_api_key else ""
    d["config"] = {**CONFIG_DEFECTO, **(e.config or {})}
    return d
