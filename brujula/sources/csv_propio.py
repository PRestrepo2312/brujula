"""Lista propia de la pyme (CSV): la misma normalización y deduplicación que las fuentes públicas.

Columnas aceptadas (cualquier orden, con o sin tildes): nombre | razon_social | empresa, nit | identificacion, telefono | celular,
correo | email, ciudad | municipio, departamento, sector, web | sitio_web, direccion. Las filas sin nombre o sin contacto se ignoran.
"""
from __future__ import annotations

import csv
import io
from typing import Iterator

from ..normalize import sin_tildes
from .base import Conector, Registro, registro_desde

ALIAS = {
    "nombre": ("nombre", "razon_social", "razonsocial", "empresa", "establecimiento", "name", "company"),
    "nit": ("nit", "identificacion", "id", "rfc", "cnpj"),
    "telefono": ("telefono", "celular", "movil", "phone", "tel"),
    "correo": ("correo", "email", "e-mail", "mail"),
    "ciudad": ("ciudad", "municipio", "city"),
    "departamento": ("departamento", "estado", "region", "state"),
    "sector": ("sector", "actividad", "categoria", "ciiu"),
    "web": ("web", "sitio_web", "sitio", "website", "url"),
    "direccion": ("direccion", "address"),
}


def _mapear(cabeceras: list[str]) -> dict[str, str]:
    norm = {sin_tildes(c).strip().lower().replace(" ", "_"): c for c in cabeceras}
    salida = {}
    for campo, alias in ALIAS.items():
        for a in alias:
            if a in norm:
                salida[campo] = norm[a]
                break
    return salida


class ConectorCSV(Conector):
    clave = "csv"
    nombre = "Lista propia (CSV)"
    descripcion = "Su propia lista de empresas en CSV (nombre, nit, teléfono, correo, ciudad, sector, web): misma normalización y deduplicación."
    usa_ciudad = False
    usa_sector = False
    pais = "CO"
    tipo = "archivo"
    licencia = "Datos del cliente"
    url = ""

    def __init__(self, datos: bytes | None = None, pais: str = "CO"):
        self.datos = datos
        self.pais = pais

    def buscar(self, *, ciudad: str = "", sector: str = "", limite: int = 100000) -> Iterator[Registro]:
        if self.datos is None:
            raise SystemExit("CSV: faltan los datos del archivo")
        texto = self.datos.decode("utf-8-sig", errors="replace")
        muestra = texto[:4096]
        try:
            dialecto = csv.Sniffer().sniff(muestra, delimiters=",;\t|")
        except csv.Error:
            dialecto = csv.excel
        lector = csv.DictReader(io.StringIO(texto), dialect=dialecto)
        mapa = _mapear(lector.fieldnames or [])
        if "nombre" not in mapa:
            raise SystemExit(f"CSV: no encuentro la columna del nombre. Cabeceras: {lector.fieldnames}")
        n = 0
        for i, f in enumerate(lector, start=2):
            g = lambda campo: f.get(mapa.get(campo, ""), "") if campo in mapa else ""  # noqa: E731
            r = registro_desde(
                dict(f), nombre=g("nombre"), pais=self.pais, identificacion=g("nit"), sector=g("sector"), ciudad=g("ciudad") or ciudad,
                departamento=g("departamento"), direccion=g("direccion"), telefonos=(g("telefono"),), correos=(g("correo"),),
                sitio_web=g("web") or None, fuente_registro=f"fila-{i}",
            )
            if r and r.tiene_contacto:
                yield r
                n += 1
                if n >= limite:
                    return
