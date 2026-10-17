"""Canales de contacto. Cada uno envía un intento y devuelve estado, costo y referencia externa."""
from __future__ import annotations

from .base import Canal, Resultado
from .correo import CanalCorreo
from .voz_dapta import CanalVozDapta
from .whatsapp import CanalWhatsApp

CANALES: dict[str, type[Canal]] = {c.clave: c for c in (CanalCorreo, CanalVozDapta, CanalWhatsApp)}


def canal(clave: str) -> Canal:
    try:
        return CANALES[clave]()
    except KeyError:
        raise SystemExit(f"Canal desconocido: {clave}. Disponibles: {', '.join(CANALES)}")


__all__ = ["CANALES", "Canal", "Resultado", "canal"]
