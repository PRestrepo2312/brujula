"""MEN: establecimientos educativos. Solo colegios privados (NO_OFICIAL) del último año publicado."""
from __future__ import annotations

from typing import Iterator

from .base import Conector, Registro, registro_desde
from .datos_gov import Socrata, filtro_ciudad

DATASET = "cfw5-qzt5"


class ConectorMEN(Conector):
    clave = "men"
    nombre = "MEN, colegios privados"
    descripcion = "Colegios privados del Ministerio de Educación (datos.gov.co), con teléfono y correo del colegio."
    usa_sector = False
    pais = "CO"
    tipo = "registro"
    licencia = "CC BY-SA 4.0, datos.gov.co, MinEducación"
    url = f"https://www.datos.gov.co/resource/{DATASET}.json"

    def buscar(self, *, ciudad: str = "", sector: str = "", limite: int = 500) -> Iterator[Registro]:
        api = Socrata()
        ultimo = api.filas(DATASET, select="max(a_o) as y", limite=1)
        anio = next(iter(ultimo), {}).get("y", "2025")
        where = [f"a_o='{anio}'", "sector='NO_OFICIAL'", "(telefono IS NOT NULL OR email like '%@%')"]
        if ciudad:
            where.append(filtro_ciudad(ciudad, "municipio", "cod_dane_municipio"))
        for f in api.filas(DATASET, where=" AND ".join(where), order="codigo_dane", limite=limite):
            matricula = f.get("total_matricula")
            r = registro_desde(
                f, nombre=f.get("nombre_establecimiento", ""), identificacion=None,
                sector="educacion", subsector=f.get("caracter", ""), ciudad=f.get("municipio", ""),
                departamento=f.get("departamento", ""), direccion=f.get("direccion", ""),
                telefonos=(f.get("telefono"),), correos=(f.get("email"),), sitio_web=f.get("web"),
                senales={"matricula": {"estudiantes": matricula, "anio": anio}},
                fuente_registro=f.get("codigo_dane", ""),
            )
            if r and r.tiene_contacto:
                yield r
