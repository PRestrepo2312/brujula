"""RNT: Registro Nacional de Turismo. Negocios (alojamiento, agencias, gastronomía…); nunca viviendas turísticas ni guías."""
from __future__ import annotations

from typing import Iterator

from .base import Conector, Registro, registro_desde
from .datos_gov import Socrata, como_sql, filtro_ciudad

DATASET = "thwd-ivmp"


class ConectorRNT(Conector):
    clave = "rnt"
    nombre = "Registro Nacional de Turismo"
    descripcion = "Hoteles, agencias de viajes y otros prestadores turísticos inscritos en el RNT (datos.gov.co), con teléfono y correo."
    ayuda_sector = "Tipo de prestador (hotel, agencia…), opcional"
    pais = "CO"
    tipo = "registro"
    licencia = "CC BY-SA 4.0, datos.gov.co, MinCIT"
    url = f"https://www.datos.gov.co/resource/{DATASET}.json"

    def buscar(self, *, ciudad: str = "", sector: str = "", limite: int = 500) -> Iterator[Registro]:
        where = ["categoria not like 'VIVIENDAS%'", "categoria not like 'GUIAS%'", "upper(estado_rnt) like 'ACTIV%'",
                 "(num_celular IS NOT NULL OR n_m_tel_fono IS NOT NULL OR correo_establecimiento like '%@%')"]
        if ciudad:
            where.append(filtro_ciudad(ciudad, "municipio", "cod_mun"))
        if sector:
            where.append(f"upper(categoria) like '%{como_sql(sector.upper())}%'")
        api = Socrata()
        for f in api.filas(DATASET, where=" AND ".join(where), order="codigo_rnt", limite=limite):
            r = registro_desde(
                f, nombre=f.get("razon_social_establecimiento", ""), identificacion=f.get("nit"),
                sector="turismo", subsector=f.get("categoria", ""), ciudad=f.get("municipio", ""),
                departamento=f.get("departamento", ""), direccion=f.get("direcci_n_comercial_establecimiento", ""),
                telefonos=(f.get("num_celular"), f.get("n_m_tel_fono")), correos=(f.get("correo_establecimiento"), f.get("correo_prestador")),
                empleados=f.get("num_emp1"),
                senales={"rnt": {"subcategoria": f.get("sub_categoria", ""), "habitaciones": f.get("habitaciones"), "anio": f.get("ano")}},
                fuente_registro=f.get("codigo_rnt", ""),
            )
            if r and r.tiene_contacto:
                yield r
