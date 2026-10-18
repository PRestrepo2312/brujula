from __future__ import annotations

from dataclasses import dataclass, field

from ..models import Intento, Lead


@dataclass
class Resultado:
    estado: str                      # enviado | programado | omitido | fallido
    costo_usd: float = 0.0
    ref_externa: str | None = None
    proveedor: str = ""
    mensaje: str = ""
    detalle: dict = field(default_factory=dict)


class Canal:
    clave = ""
    nombre = ""

    @property
    def real(self) -> bool:
        """True si envía de verdad; False si simula (sin credenciales)."""
        return False

    def enviar(self, lead: Lead, intento: Intento) -> Resultado:
        raise NotImplementedError
