"""RUES (Confecámaras): registro mercantil de todas las cámaras de comercio. Sin teléfono ni correo: sirve para encontrar
empresas recién matriculadas (señal "empresa nueva") y para enriquecer por NIT el sector (CIIU) de leads de otras fuentes."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterator

from .base import Conector, Registro, registro_desde
from .datos_gov import Socrata, como_sql

DATASET = "c82u-588k"

# Sector de Brújula → divisiones CIIU (dos primeros dígitos del código de actividad principal).
CIIU_POR_SECTOR = {
    "salud": ("86",), "educacion": ("85",), "turismo": ("55", "79"), "inmobiliario": ("68",), "automotor": ("45",),
    "software": ("62", "63"), "servicios": ("69", "70", "71", "73", "74", "82"), "restaurantes": ("56",), "construccion": ("41", "42", "43"),
    "comercio": ("46", "47"), "transporte": ("49", "52"),
}
SECTOR_POR_CIIU = {c: s for s, cs in CIIU_POR_SECTOR.items() for c in cs}


class ConectorRUES(Conector):
    clave = "rues"
    nombre = "RUES (Confecámaras), empresas recién matriculadas"
    descripcion = ("Registro mercantil de las cámaras de comercio (datos.gov.co): razón social, NIT, CIIU y fecha de matrícula de las empresas "
                   "matriculadas en los últimos 12 meses. Sin teléfono ni correo: encuentra empresas nuevas y enriquece por NIT las de otras fuentes.")
    pais = "CO"
    tipo = "registro"
    licencia = "CC BY-SA 4.0, datos.gov.co, Confecámaras"
    url = f"https://www.datos.gov.co/resource/{DATASET}.json"
    contacta = False
    ayuda_ciudad = "Cámara de comercio (Bogotá, Medellín, Cali, Barranquilla…)"
    ayuda_sector = "Sector (salud, educacion, turismo, software…) o división CIIU (86, 85, 55…)"

    def buscar(self, *, ciudad: str = "", sector: str = "", limite: int = 500) -> Iterator[Registro]:
        api = Socrata()
        desde = (date.today() - timedelta(days=365)).strftime("%Y%m%d")
        where = [f"fecha_matricula >= '{desde}'", "fecha_cancelacion IS NULL", "nit IS NOT NULL", "organizacion_juridica NOT LIKE '%NATURAL%'"]
        if ciudad:
            where.append(f"upper(camara_comercio) LIKE '%{como_sql(ciudad.upper())}%'")
        s = sector.strip().lower()
        if s:
            prefijos = CIIU_POR_SECTOR.get(s) or ((s,) if s.isdigit() else ())
            if prefijos:
                where.append("(" + " OR ".join(f"cod_ciiu_act_econ_pri LIKE '{p}%'" for p in prefijos) + ")")
            else:
                where.append(f"upper(razon_social) LIKE '%{como_sql(s.upper())}%'")
        hoy = date.today()
        for f in api.filas(DATASET, where=" AND ".join(where), order="fecha_matricula DESC", limite=limite):
            ciiu = (f.get("cod_ciiu_act_econ_pri") or "")[:4]
            fm = f.get("fecha_matricula") or ""
            senales = {"empresa_nueva": {"matricula": fm, "camara": f.get("camara_comercio", "")}}
            if (f.get("ultimo_ano_renovado") or "") == str(hoy.year):
                senales["renovada"] = hoy.year
            r = registro_desde(
                f, nombre=f.get("razon_social", ""), identificacion=f.get("nit"), sector=SECTOR_POR_CIIU.get(ciiu[:2], "otro"), subsector=f"CIIU {ciiu}" if ciiu else "",
                ciudad=(f.get("camara_comercio") or "").split(" PARA ")[0].split(" DE ")[-1], departamento="",
                tamano=f.get("categoria_matricula", ""), senales=senales, fuente_registro=f.get("matricula", ""),
            )
            if r:
                yield r
