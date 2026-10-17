"""Canal WhatsApp: solo si hay una línea con plantilla aprobada (Meta o el sandbox de Dapta). Sin eso, simula y lo dice."""
from __future__ import annotations

import secrets

from ..config import config
from ..mensajes import idioma_de, whatsapp_texto
from ..models import Intento, Lead
from .base import Canal, Resultado


class CanalWhatsApp(Canal):
    clave = "whatsapp"
    nombre = "WhatsApp"

    @property
    def real(self) -> bool:
        return False   # se activa cuando exista línea y plantilla aprobada

    def enviar(self, lead: Lead, intento: Intento) -> Resultado:
        texto = whatsapp_texto(lead, idioma_de(lead, intento.empresa_id))
        return Resultado(estado="enviado", costo_usd=config.tarifas.whatsapp_conversacion_co, ref_externa=f"sim_{secrets.token_hex(6)}",
                         proveedor="simulado", mensaje=texto, detalle={"nota": "sin línea de WhatsApp aprobada: envío simulado"})
