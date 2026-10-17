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
    "notificar_por": ["app", "correo"],
    "remitente": "",
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
