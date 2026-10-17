"""Registro de fuentes. Cada conector devuelve leads normalizados; el pipeline los guarda y deduplica."""
from __future__ import annotations

from .base import Conector, Registro
from .co_reps import ConectorREPS
from .co_men import ConectorMEN
from .co_rnt import ConectorRNT
from .co_secop import ConectorSECOP
from .osm import ConectorOSM
from .otros_paises import ConectorDENUE, ConectorCNPJ, ConectorNYC

CONECTORES: dict[str, type[Conector]] = {
    c.clave: c for c in (ConectorREPS, ConectorMEN, ConectorRNT, ConectorSECOP, ConectorOSM, ConectorDENUE, ConectorCNPJ, ConectorNYC)
}


def conector(clave: str) -> Conector:
    try:
        return CONECTORES[clave]()
    except KeyError:
        raise SystemExit(f"Fuente desconocida: {clave}. Disponibles: {', '.join(CONECTORES)}")


__all__ = ["CONECTORES", "Conector", "Registro", "conector"]
