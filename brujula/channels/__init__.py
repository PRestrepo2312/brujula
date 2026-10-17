"""Canales de contacto. Cada uno envía un intento y devuelve estado, costo y referencia externa."""
from __future__ import annotations

from .base import Canal, Resultado
from .correo import CanalCorreo
from .voz_dapta import CanalVozDapta
from .whatsapp import CanalWhatsApp

CANALES: dict[str, type[Canal]] = {c.clave: c for c in (CanalCorreo, CanalVozDapta, CanalWhatsApp)}


def canal(clave: str, empresa_id: int = 1) -> Canal:
    try:
        cls = CANALES[clave]
    except KeyError:
        raise SystemExit(f"Canal desconocido: {clave}. Disponibles: {', '.join(CANALES)}")
    return cls(empresa_id=empresa_id) if clave == "voz" else cls()


__all__ = ["CANALES", "Canal", "Resultado", "canal"]
