"""REPS: Registro Especial de Prestadores de Servicios de Salud (MinSalud). Solo IPS privadas, nunca profesionales independientes."""
from __future__ import annotations

from typing import Iterator

from .base import Conector, Registro, registro_desde
from .datos_gov import Socrata, filtro_ciudad

DATASET = "c36g-9fc2"


class ConectorREPS(Conector):
    clave = "reps"
    nombre = "REPS, prestadores de salud (IPS privadas)"
    descripcion = "IPS privadas del Registro Especial de Prestadores de Salud (datos.gov.co): clínicas, consultorios y laboratorios con teléfono y correo."
    usa_sector = False
    pais = "CO"
    tipo = "registro"
    licencia = "CC BY-SA 4.0, datos.gov.co, MinSalud"
    url = f"https://www.datos.gov.co/resource/{DATASET}.json"

    def buscar(self, *, ciudad: str = "", sector: str = "", limite: int = 500) -> Iterator[Registro]:
        where = ["claseprestador like 'Instituciones%'", "naturalezajuridica='Privada'",
                 "(t_lefonosede IS NOT NULL OR email_sede like '%@%' OR telefonoprestador IS NOT NULL OR email_prestador like '%@%')"]
        if ciudad:
            where.append(filtro_ciudad(ciudad, "municipiosededesc", "municipiosede"))
        api = Socrata()
        vistos: set[str] = set()
        for f in api.filas(DATASET, where=" AND ".join(where), order="codigoprestador", limite=limite * 2):
            # Un prestador puede tener varias sedes: una por empresa (la primera sede), las demás solo si cambian de ciudad.
            llave = f"{f.get('codigoprestador')}|{f.get('municipiosededesc')}"
            if llave in vistos:
                continue
            vistos.add(llave)
            r = registro_desde(
                f, nombre=f.get("nombreprestador", ""), identificacion=f.get("numeroidentificacion"),
                sector="salud", subsector=f.get("claseprestador", ""), ciudad=f.get("municipiosededesc", ""),
                departamento=f.get("departamentodededesc", ""), direccion=f.get("direcci_nsede", ""),
                telefonos=(f.get("t_lefonosede"), f.get("telefonoprestador")), correos=(f.get("email_sede"), f.get("email_prestador")),
                senales={"habilitado_reps": {"sede": f.get("nombresede", ""), "corte": f.get("fecha_corte_reps", "")}},
                fuente_registro=f.get("codigohabilitacionsede", f.get("codigoprestador", "")),
            )
            if r and r.tiene_contacto:
                yield r
                limite -= 1
                if limite <= 0:
                    return
