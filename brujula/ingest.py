"""Ingesta: corre un conector, guarda los registros como leads, registra el costo de encontrar y deduplica."""
from __future__ import annotations

from datetime import datetime

from sqlmodel import select

from .config import config
from .db import sesion
from .dedupe import deduplicar
from .models import Costo, Fuente, Lead
from .sources import conector


def asegurar_fuente(c) -> Fuente:
    with sesion() as s:
        f = s.exec(select(Fuente).where(Fuente.clave == c.clave)).first()
        if not f:
            f = Fuente(clave=c.clave, nombre=c.nombre, pais=c.pais, tipo=c.tipo, licencia=c.licencia, url=c.url,
                       contacta=c.contacta, costo_fijo_usd=c.costo_fijo_usd)
            s.add(f)
            s.commit()
            s.refresh(f)
        return f


def ingerir(clave: str, *, ciudad: str = "", sector: str = "", limite: int = 500, segundos_computo: float | None = None) -> dict:
    c = conector(clave)
    asegurar_fuente(c)
    inicio = datetime.utcnow()
    nuevos = 0
    repetidos_misma_fuente = 0
    leads_nuevos: list[Lead] = []
    with sesion() as s:
        existentes = {r for r in s.exec(select(Lead.fuente_registro).where(Lead.fuente_clave == clave)).all() if r}
        for reg in c.buscar(ciudad=ciudad, sector=sector, limite=limite):
            if reg.fuente_registro and reg.fuente_registro in existentes:
                repetidos_misma_fuente += 1
                continue
            lead = Lead(
                pais=reg.pais, identificacion=reg.identificacion, razon_social=reg.razon_social, nombre_norm=reg.nombre_norm,
                sector=reg.sector, subsector=reg.subsector, ciudad=reg.ciudad, departamento=reg.departamento, direccion=reg.direccion,
                telefono=reg.telefono, telefono_tipo=reg.telefono_tipo, correo=reg.correo, sitio_web=reg.sitio_web, dominio=reg.dominio,
                canales=reg.canales, senales=reg.senales, tamano=reg.tamano, empleados=reg.empleados, fuente_clave=clave,
                fuente_registro=reg.fuente_registro, fuentes_todas=[clave], crudo=reg.crudo,
            )
            s.add(lead)
            leads_nuevos.append(lead)
            existentes.add(reg.fuente_registro)
            nuevos += 1
        s.commit()
        for l in leads_nuevos:
            s.refresh(l)
        ids = [l.id for l in leads_nuevos]
        # Costo de encontrar: cómputo prorrateado (las fuentes son gratis; el tiempo de máquina no).
        seg = segundos_computo if segundos_computo is not None else (datetime.utcnow() - inicio).total_seconds()
        usd = config.tarifas.computo_hora * seg / 3600.0
        if nuevos:
            s.add(Costo(concepto="descarga", fuente_clave=clave, usd=round(usd, 6), cantidad=nuevos))
            por_lead = usd / nuevos
            for l in leads_nuevos:
                l.costo_encontrar_usd = round(por_lead, 6)
                s.add(l)
        s.commit()
    dd = deduplicar(ids) if ids else {"revisados": 0, "duplicados": 0}
    return {"fuente": clave, "nuevos": nuevos, "ya_estaban": repetidos_misma_fuente, "dedupe": dd, "segundos": round(seg, 1)}
