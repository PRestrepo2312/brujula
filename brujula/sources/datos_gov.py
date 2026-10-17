"""Cliente mínimo de la API Socrata (datos.gov.co y portales de EE. UU.). Sin clave; con token opcional para más cuota."""
from __future__ import annotations

from typing import Iterator

import httpx

from ..config import config

PAGINA = 1000


class Socrata:
    def __init__(self, dominio: str = "www.datos.gov.co"):
        self.base = f"https://{dominio}"
        cab = {"User-Agent": "Brujula/0.1 (hackathon 30X; datos abiertos)"}
        if config.socrata_app_token:
            cab["X-App-Token"] = config.socrata_app_token
        self.http = httpx.Client(base_url=self.base, headers=cab, timeout=90)

    def filas(self, dataset: str, *, select: str | None = None, where: str | None = None, order: str | None = None,
              limite: int = 500) -> Iterator[dict]:
        """Itera filas paginando con $limit/$offset."""
        traidas = 0
        offset = 0
        while traidas < limite:
            n = min(PAGINA, limite - traidas)
            params = {"$limit": n, "$offset": offset}
            if select:
                params["$select"] = select
            if where:
                params["$where"] = where
            if order:
                params["$order"] = order
            r = self.http.get(f"/resource/{dataset}.json", params=params)
            r.raise_for_status()
            lote = r.json()
            if not lote:
                return
            for fila in lote:
                yield fila
            traidas += len(lote)
            offset += len(lote)
            if len(lote) < n:
                return

    def contar(self, dataset: str, where: str | None = None) -> int:
        params = {"$select": "count(*) as n"}
        if where:
            params["$where"] = where
        r = self.http.get(f"/resource/{dataset}.json", params=params)
        r.raise_for_status()
        return int(r.json()[0]["n"])


def como_sql(texto: str) -> str:
    """Escapa comillas simples para SoQL."""
    return texto.replace("'", "''")


# Ciudades principales: código DIVIPOLA y un fragmento sin tildes para buscar en columnas de texto
# (SoQL no quita tildes: "BOGOTÁ, D.C." no contiene "BOGOTA", pero sí "BOGOT").
CIUDADES = {
    "BOGOTA": ("11001", "BOGOT"), "MEDELLIN": ("05001", "MEDELL"), "CALI": ("76001", "CALI"), "BARRANQUILLA": ("08001", "BARRANQUILLA"),
    "CARTAGENA": ("13001", "CARTAGENA"), "BUCARAMANGA": ("68001", "BUCARAMANGA"), "IBAGUE": ("73001", "IBAGU"), "PEREIRA": ("66001", "PEREIRA"),
    "MANIZALES": ("17001", "MANIZALES"), "CUCUTA": ("54001", "CUTA"), "SANTA MARTA": ("47001", "SANTA MARTA"), "VILLAVICENCIO": ("50001", "VILLAVICENCIO"),
    "PASTO": ("52001", "PASTO"), "MONTERIA": ("23001", "MONTER"), "NEIVA": ("41001", "NEIVA"), "ARMENIA": ("63001", "ARMENIA"),
    "POPAYAN": ("19001", "POPAY"), "VALLEDUPAR": ("20001", "VALLEDUPAR"), "SINCELEJO": ("70001", "SINCELEJO"), "TUNJA": ("15001", "TUNJA"),
    "SOLEDAD": ("08758", "SOLEDAD"), "SOACHA": ("25754", "SOACHA"), "BELLO": ("05088", "BELLO"), "ENVIGADO": ("05266", "ENVIGADO"), "ITAGUI": ("05360", "ITAG"),
}


def filtro_ciudad(ciudad: str, columna_texto: str, columna_codigo: str | None = None) -> str | None:
    """Condición SoQL para una ciudad: por código DIVIPOLA si la columna existe, si no por fragmento de texto."""
    if not ciudad:
        return None
    clave = ciudad.strip().upper()
    for k, (codigo, frag) in CIUDADES.items():
        if clave == k or clave == frag:
            if columna_codigo:
                return f"({columna_codigo}='{codigo}' OR {columna_codigo}='{int(codigo)}' OR upper({columna_texto}) like '%{frag}%')"
            return f"upper({columna_texto}) like '%{frag}%'"
    return f"upper({columna_texto}) like '%{como_sql(clave)}%'"
