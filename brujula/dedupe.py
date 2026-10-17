"""Deduplicación: NIT > dominio propio > teléfono > nombre parecido en la misma ciudad.

La misma clínica puede venir de REPS, de la Cámara de Comercio y de OpenStreetMap. Queda una sola vez:
el primer registro es el principal y los demás se marcan duplicado_de, aportando los datos que falten.
"""
from __future__ import annotations

from typing import Iterable

from rapidfuzz import fuzz
from sqlmodel import select

from .db import sesion
from .models import Lead

UMBRAL_NOMBRE = 92


def clave_fuerte(lead: Lead) -> str | None:
    if lead.identificacion:
        return f"id:{lead.pais}:{lead.identificacion}"
    if lead.dominio:
        return f"dom:{lead.dominio}"
    if lead.telefono:
        return f"tel:{lead.telefono}"
    return None


def _fusionar(principal: Lead, otro: Lead) -> None:
    """El principal se queda con lo que no tenía: contacto, señales, fuentes."""
    for campo in ("identificacion", "telefono", "correo", "sitio_web", "dominio", "direccion", "sector", "ciudad", "departamento", "tamano"):
        if not getattr(principal, campo) and getattr(otro, campo):
            setattr(principal, campo, getattr(otro, campo))
    if not principal.telefono_tipo and otro.telefono_tipo:
        principal.telefono_tipo = otro.telefono_tipo
    if otro.empleados and not principal.empleados:
        principal.empleados = otro.empleados
    canales = set(principal.canales or []) | set(otro.canales or [])
    principal.canales = sorted(canales)
    senales = dict(principal.senales or {})
    senales.update(otro.senales or {})
    principal.senales = senales
    fuentes = list(principal.fuentes_todas or [principal.fuente_clave])
    for f in (otro.fuentes_todas or [otro.fuente_clave]):
        if f not in fuentes:
            fuentes.append(f)
    principal.fuentes_todas = fuentes


def deduplicar(ids: Iterable[int] | None = None, empresa_id: int = 1) -> dict:
    """Recorre los leads de una empresa (por id; todos los principales si no se pasan) y marca duplicados. Devuelve cifras."""
    with sesion() as s:
        # Índice con lo que ya está en la base (principales), en orden de llegada: el más antiguo manda.
        existentes = s.exec(select(Lead).where(Lead.duplicado_de.is_(None), Lead.empresa_id == empresa_id).order_by(Lead.id)).all()
        quiero = set(ids) if ids is not None else {e.id for e in existentes}
        candidatos = [e for e in existentes if e.id in quiero]
        # El índice solo tiene leads ya "asentados": los principales que no están en revisión. Los candidatos entran al
        # índice a medida que se procesan (del más antiguo al más nuevo); si no, el primero se marcaría duplicado del segundo.
        por_clave: dict[str, Lead] = {}
        por_ciudad: dict[str, list[Lead]] = {}
        for e in existentes:
            if e.id in quiero:
                continue
            for k in claves_todas(e):
                por_clave.setdefault(k, e)
            por_ciudad.setdefault(e.ciudad, []).append(e)
        vistos = 0
        duplicados = 0
        fusionados_desde: dict[int, int] = {}
        for lead in candidatos:
            vistos += 1
            principal = None
            for k in claves_todas(lead):
                if k in por_clave and por_clave[k].id != lead.id:
                    principal = por_clave[k]
                    break
            if principal is None and lead.nombre_norm:
                for e in por_ciudad.get(lead.ciudad, []):
                    if e.id == lead.id or not e.nombre_norm:
                        continue
                    if fuzz.token_set_ratio(e.nombre_norm, lead.nombre_norm) >= UMBRAL_NOMBRE:
                        principal = e
                        break
            if principal is not None and principal.id != lead.id:
                _fusionar(principal, lead)
                lead.duplicado_de = principal.id
                lead.estado = "descartado"
                lead.dedupe_clave = clave_fuerte(principal) or f"nom:{principal.nombre_norm}"
                duplicados += 1
                fusionados_desde[principal.id] = fusionados_desde.get(principal.id, 0) + 1
                s.add(principal)
                s.add(lead)
                for k in claves_todas(principal):
                    por_clave.setdefault(k, principal)
                continue
            lead.dedupe_clave = clave_fuerte(lead) or (f"nom:{lead.nombre_norm}" if lead.nombre_norm else None)
            for k in claves_todas(lead):
                por_clave.setdefault(k, lead)
            por_ciudad.setdefault(lead.ciudad, []).append(lead)
            s.add(lead)
        s.commit()
        return {"revisados": vistos, "duplicados": duplicados, "principales_con_fusion": len(fusionados_desde)}


def claves_todas(lead: Lead) -> list[str]:
    claves = []
    if lead.identificacion:
        claves.append(f"id:{lead.pais}:{lead.identificacion}")
    if lead.dominio:
        claves.append(f"dom:{lead.dominio}")
    if lead.telefono:
        claves.append(f"tel:{lead.telefono}")
    return claves
