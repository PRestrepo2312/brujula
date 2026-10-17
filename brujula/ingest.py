"""Ingesta: corre un conector, guarda los registros como leads de una empresa, registra el costo de encontrar y deduplica."""
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


def ingerir(clave: str, *, ciudad: str = "", sector: str = "", limite: int = 500, segundos_computo: float | None = None,
            conector_listo=None, empresa_id: int = 1) -> dict:
    c = conector_listo or conector(clave)
    asegurar_fuente(c)
    inicio = datetime.utcnow()
    nuevos = 0
    repetidos_misma_fuente = 0
    leads_nuevos: list[Lead] = []
    with sesion() as s:
        existentes = {r for r in s.exec(select(Lead.fuente_registro).where(Lead.fuente_clave == clave, Lead.empresa_id == empresa_id)).all() if r}
        for reg in c.buscar(ciudad=ciudad, sector=sector, limite=limite):
            if reg.fuente_registro and reg.fuente_registro in existentes:
                repetidos_misma_fuente += 1
                continue
            lead = Lead(
                empresa_id=empresa_id, pais=reg.pais, identificacion=reg.identificacion, razon_social=reg.razon_social, nombre_norm=reg.nombre_norm,
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
            s.add(Costo(empresa_id=empresa_id, concepto="descarga", fuente_clave=clave, usd=round(usd, 6), cantidad=nuevos))
            por_lead = usd / nuevos
            for l in leads_nuevos:
                l.costo_encontrar_usd = round(por_lead, 6)
                s.add(l)
        s.commit()
    dd = deduplicar(ids, empresa_id=empresa_id) if ids else {"revisados": 0, "duplicados": 0}
    return {"fuente": clave, "nuevos": nuevos, "ya_estaban": repetidos_misma_fuente, "dedupe": dd, "segundos": round(seg, 1)}


def ingerir_csv(datos: bytes, nombre_archivo: str = "lista.csv", pais: str = "CO", empresa_id: int = 1) -> dict:
    """Lista propia de la pyme: misma normalización, deduplicación y costo que una fuente pública."""
    from .sources.csv_propio import ConectorCSV
    c = ConectorCSV(datos, pais=pais)
    r = ingerir("csv", limite=100000, conector_listo=c, empresa_id=empresa_id)
    r["archivo"] = nombre_archivo
    return r


def buscar(empresa_id: int, fuentes: list[str], ciudad: str = "", sector: str = "", limite: int = 200, puntuar_icp: bool = True,
           parametros: dict[str, dict] | None = None) -> dict:
    """Lo que hace el botón Buscar del front: corre varias fuentes, deduplica y puntúa el ICP de la empresa.

    parametros permite ciudad/sector distintos por fuente (p. ej. la entidad federativa para DENUE o los CNPJ para Brasil)."""
    from .empresas import icp_de
    from .icp import puntuar
    resultados = []
    for clave in fuentes:
        propios = (parametros or {}).get(clave) or {}
        try:
            resultados.append(ingerir(clave, ciudad=propios.get("ciudad", ciudad), sector=propios.get("sector", sector), limite=limite, empresa_id=empresa_id))
        except SystemExit as e:
            resultados.append({"fuente": clave, "error": str(e)})
        except Exception as e:  # noqa: BLE001
            resultados.append({"fuente": clave, "error": str(e)[:200]})
    cuenta = {}
    if puntuar_icp:
        icp = icp_de(empresa_id)
        with sesion() as s:
            leads = list(s.exec(select(Lead).where(Lead.empresa_id == empresa_id, Lead.duplicado_de.is_(None), Lead.icp_estado == "pendiente")))
            cuenta = puntuar(leads, icp)
            for l in leads:
                s.add(l)
            s.commit()
    return {"fuentes": resultados, "icp": cuenta, "nuevos": sum(r.get("nuevos", 0) for r in resultados)}
