"""Canal WhatsApp. El primer mensaje saliente exige una plantilla aprobada por Meta en la línea conectada a Dapta: hasta tenerla, se simula y
lo dice. Las conversaciones entrantes sí son reales: las atiende el agente de texto de Dapta y pipeline.sincronizar_chats las trae como respuestas."""
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
                         proveedor="simulado", mensaje=texto, detalle={"nota": "sin plantilla de WhatsApp aprobada por Meta: envío simulado"})
