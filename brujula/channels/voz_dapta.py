"""Canal voz: el agente de voz de Dapta llama por una secuencia. El contacto se adjunta por MCP; la secuencia la activa la persona en el panel.

El costo real se concilia después desde los registros de llamada (créditos de Dapta). Al programar se anota el costo
esperado de un intento sin respuesta; al sincronizar se reemplaza por el real.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..config import RAIZ, config
from ..dapta_mcp import DaptaError, DaptaMCP
from ..mensajes import variables_voz
from ..models import Intento, Lead
from .base import Canal, Resultado

ARCHIVO_DAPTA = RAIZ / "data" / "dapta.json"


def ids_dapta() -> dict:
    """agent_id y sequence_id: del .env o de data/dapta.json (lo escribe `cli.py dapta-setup`)."""
    d = {"agent_id": config.dapta_agent_id, "sequence_id": config.dapta_sequence_id}
    if (not d["agent_id"] or not d["sequence_id"]) and Path(ARCHIVO_DAPTA).exists():
        g = json.loads(Path(ARCHIVO_DAPTA).read_text(encoding="utf-8"))
        d["agent_id"] = d["agent_id"] or g.get("agent_id", "")
        d["sequence_id"] = d["sequence_id"] or g.get("sequence_id", "")
    return d


class CanalVozDapta(Canal):
    clave = "voz"
    nombre = "Voz (agente Dapta)"

    def __init__(self, empresa_id: int = 1):
        from ..empresas import dapta_de
        d = dapta_de(empresa_id)
        self.api_key = d.get("api_key", "")
        self.ids = {"agent_id": d.get("agent_id", ""), "sequence_id": d.get("sequence_id", "")}
        self._mcp: DaptaMCP | None = None

    @property
    def real(self) -> bool:
        return bool(self.api_key and self.ids["sequence_id"])

    @property
    def mcp(self) -> DaptaMCP:
        if self._mcp is None:
            self._mcp = DaptaMCP(api_key=self.api_key)
        return self._mcp

    def enviar(self, lead: Lead, intento: Intento) -> Resultado:
        variables = variables_voz(lead)
        if not self.real:
            return Resultado(estado="programado", costo_usd=config.tarifas.voz_no_contesta, ref_externa=f"sim_{lead.telefono}",
                             proveedor="simulado", mensaje=json.dumps(variables, ensure_ascii=False), detalle={"variables": variables})
        try:
            r = self.mcp.adjuntar_contactos(self.ids["sequence_id"], [{"phone_number": lead.telefono, "name": lead.razon_social.title(), "variables": variables}])
            ok = bool(r.get("verified", True)) if isinstance(r, dict) else True
            return Resultado(estado="programado" if ok else "fallido", costo_usd=config.tarifas.voz_no_contesta, ref_externa=lead.telefono,
                             proveedor="dapta", mensaje=json.dumps(variables, ensure_ascii=False), detalle={"variables": variables, "dapta": r if isinstance(r, dict) else {"texto": str(r)[:300]}})
        except DaptaError as e:
            return Resultado(estado="fallido", proveedor="dapta", mensaje=json.dumps(variables, ensure_ascii=False), detalle={"error": str(e)[:400]})

    # --- conciliación con los registros de llamada ---
    def costo_llamada(self, llamada: dict) -> float:
        """Créditos reales si vienen; si no, por duración y resultado según la tabla de Dapta."""
        cred = llamada.get("credits") or (llamada.get("call_cost") or {}).get("credits")
        if cred:
            try:
                return round(float(cred) / 1000.0, 4)
            except (TypeError, ValueError):
                pass
        dur = int(llamada.get("duration_seconds") or llamada.get("duration") or 0)
        razon = (llamada.get("disconnect_reason") or llamada.get("disconnection_reason") or "").lower()
        if "voicemail" in razon:
            return config.tarifas.voz_buzon
        if dur <= 0:
            return config.tarifas.voz_no_contesta
        minutos = -(-dur // 60)
        return round(minutos * config.tarifas.voz_minuto_contestado, 4)
