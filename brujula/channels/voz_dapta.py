"""Canal voz: el agente de voz de Dapta llama por una secuencia. El contacto se adjunta por MCP; la secuencia la activa la persona en el panel.

El costo real se concilia después desde los registros de llamada (créditos de Dapta). Al programar se anota el costo
esperado de un intento sin respuesta; al sincronizar se reemplaza por el real.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..config import RAIZ, config
from ..dapta_mcp import REGLAS_LEY_2300, DaptaError, DaptaMCP

DIAS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def duracion_seg(llamada: dict) -> int:
    """Duración en segundos: Dapta la entrega en duration_ms (a veces duration_seconds o duration)."""
    try:
        d = int(llamada.get("duration_seconds") or llamada.get("duration") or 0)
        return d or int(llamada.get("duration_ms") or 0) // 1000
    except (TypeError, ValueError):
        return 0


def inicio_llamada(llamada: dict):
    """start_timestamp (época en ms o s), start_time o created_at (ISO) → datetime UTC sin zona, como enviado_en."""
    from datetime import datetime, timezone
    v = llamada.get("start_timestamp") or llamada.get("start_time") or llamada.get("created_at")
    if v is None:
        return None
    try:
        if isinstance(v, (int, float)) or str(v).isdigit():
            n = float(v)
            return datetime.fromtimestamp(n / 1000.0 if n > 1e11 else n, tz=timezone.utc).replace(tzinfo=None)
        t = str(v).replace("Z", "").replace("+00:00", "")
        return datetime.fromisoformat(t[:26]).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None
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
        self.desviadas = 0      # modo prueba: una sola llamada de prueba por lote (una instancia del canal por lote)

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
        texto = json.dumps(variables, ensure_ascii=False)
        telefono = lead.telefono
        detalle: dict = {"variables": variables}
        if config.modo_prueba:
            # Desvío: el agente llama con el nombre y las señales de la empresa real, pero al número de prueba. Nunca al número del lead.
            telefono = config.destino_prueba("voz")
            if not telefono:
                return Resultado(estado="omitido", costo_usd=0.0, proveedor="bloqueado", mensaje=texto, detalle={**detalle, "motivo": "modo prueba: sin TELEFONO_PRUEBA"})
            if self.desviadas >= 1:
                return Resultado(estado="omitido", costo_usd=0.0, proveedor="bloqueado", mensaje=texto, detalle={**detalle, "motivo": "modo prueba: una sola llamada de prueba por lote"})
            self.desviadas += 1
            detalle["desvio"] = {"original": lead.telefono, "destino": telefono}
        if not self.real:
            return Resultado(estado="programado", costo_usd=config.tarifas.voz_no_contesta, ref_externa=f"sim_{telefono}", proveedor="simulado", mensaje=texto, detalle=detalle)
        try:
            r = self.mcp.adjuntar_contactos(self.ids["sequence_id"], [{"phone_number": telefono, "name": lead.razon_social.title(), "variables": variables}])
            ok = bool(r.get("verified", True)) if isinstance(r, dict) else True
            return Resultado(estado="programado" if ok else "fallido", costo_usd=config.tarifas.voz_no_contesta, ref_externa=telefono, proveedor="dapta",
                             mensaje=texto, detalle={**detalle, "dapta": r if isinstance(r, dict) else {"texto": str(r)[:300]}})
        except DaptaError as e:
            return Resultado(estado="fallido", proveedor="dapta", mensaje=texto, detalle={**detalle, "error": str(e)[:400]})

    # --- override de horario: la secuencia de Dapta tiene su propio horario (Ley 2300) y también hay que abrirlo ---
    def abrir_ventana_hoy(self, hasta: str = "11:59 PM") -> dict:
        """Override por usuario: abre el horario de la secuencia hoy (hora Bogotá) para que llame ya; restaurar_ventana_legal lo devuelve."""
        from copy import deepcopy
        from ..compliance import ahora_local
        reglas = deepcopy(REGLAS_LEY_2300)
        hoy = DIAS[ahora_local().weekday()]
        reglas["schedule"][hoy] = {"enabled": True, "timeSlots": [{"startTime": "06:00 AM", "endTime": hasta}]}
        return self.mcp.reglas_secuencia(self.ids["sequence_id"], reglas)

    def restaurar_ventana_legal(self) -> dict:
        return self.mcp.reglas_secuencia(self.ids["sequence_id"], REGLAS_LEY_2300)

    # --- conciliación con los registros de llamada ---
    def costo_llamada(self, llamada: dict) -> float:
        """Créditos reales si vienen; si no, por duración y resultado según la tabla de Dapta."""
        cc = llamada.get("call_cost")
        if isinstance(cc, str):      # list_calls lo manda como texto JSON
            try:
                cc = json.loads(cc)
            except ValueError:
                cc = {}
        cred = llamada.get("credits") or ((cc or {}).get("credits") if isinstance(cc, dict) else None)
        if cred:
            try:
                return round(float(cred) / 1000.0, 4)
            except (TypeError, ValueError):
                pass
        dur = duracion_seg(llamada)
        razon = (llamada.get("disconnect_reason") or llamada.get("disconnection_reason") or "").lower()
        if "voicemail" in razon:
            return config.tarifas.voz_buzon
        if dur <= 0:
            return config.tarifas.voz_no_contesta
        minutos = -(-dur // 60)
        return round(minutos * config.tarifas.voz_minuto_contestado, 4)
