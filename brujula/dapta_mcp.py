"""Cliente del MCP de Dapta (HTTP streamable, JSON-RPC). Las escrituras siguen el patrón preview -> commit del servidor."""
from __future__ import annotations

import json
from typing import Any

import httpx

from .config import config


class DaptaError(RuntimeError):
    pass


class DaptaMCP:
    def __init__(self, api_key: str | None = None, url: str | None = None):
        self.key = api_key or config.dapta_api_key
        self.url = url or config.dapta_mcp_url
        if not self.key:
            raise DaptaError("Falta DAPTA_API_KEY en .env")
        self.sesion_id: str | None = None
        self._n = 0
        self.http = httpx.Client(timeout=180)
        self._inicializar()

    def _rpc(self, metodo: str, params: dict | None = None, con_id: bool = True) -> dict | None:
        self._n += 1
        cuerpo: dict[str, Any] = {"jsonrpc": "2.0", "method": metodo}
        if con_id:
            cuerpo["id"] = self._n
        if params is not None:
            cuerpo["params"] = params
        cab = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", "x-api-key": self.key}
        if self.sesion_id:
            cab["Mcp-Session-Id"] = self.sesion_id
        r = self.http.post(self.url, content=json.dumps(cuerpo), headers=cab)
        if r.status_code == 401:
            raise DaptaError("Dapta MCP: clave rechazada (401)")
        r.raise_for_status()
        sid = r.headers.get("Mcp-Session-Id")
        if sid:
            self.sesion_id = sid
        if not con_id:
            return None
        if "text/event-stream" in r.headers.get("Content-Type", ""):
            msgs = [json.loads(l[5:].strip()) for l in r.text.splitlines() if l.startswith("data:")]
            for m in msgs:
                if m.get("id") == self._n:
                    return m
            return msgs[-1] if msgs else None
        return r.json() if r.text.strip() else None

    def _inicializar(self) -> None:
        self._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "brujula", "version": "0.1"}})
        self._rpc("notifications/initialized", {}, con_id=False)

    def tool(self, nombre: str, **args) -> Any:
        """Llama una herramienta y devuelve su contenido ya decodificado (JSON si lo es)."""
        res = self._rpc("tools/call", {"name": nombre, "arguments": args})
        if res is None:
            raise DaptaError(f"{nombre}: sin respuesta")
        if "error" in res:
            raise DaptaError(f"{nombre}: {res['error']}")
        out = res.get("result", {})
        textos = [p.get("text", "") for p in out.get("content", []) if p.get("type") == "text"]
        texto = "\n".join(textos)
        if out.get("isError"):
            raise DaptaError(f"{nombre}: {texto[:500]}")
        try:
            return json.loads(texto)
        except json.JSONDecodeError:
            return texto

    @staticmethod
    def _token(previo: Any) -> str:
        """Saca el preview_token de una respuesta de preview, esté donde esté."""
        def buscar(o):
            if isinstance(o, dict):
                if "preview_token" in o and isinstance(o["preview_token"], str):
                    return o["preview_token"]
                for v in o.values():
                    t = buscar(v)
                    if t:
                        return t
            elif isinstance(o, list):
                for v in o:
                    t = buscar(v)
                    if t:
                        return t
            return None
        t = buscar(previo)
        if not t:
            raise DaptaError(f"la vista previa no trajo preview_token: {str(previo)[:400]}")
        return t

    # --- lecturas ---
    def whoami(self) -> dict:
        return self.tool("whoami")

    def balance(self) -> dict:
        return self.tool("get_my_balance")

    def agentes(self) -> list[dict]:
        return self.tool("list_agents").get("agents", [])

    def secuencias(self) -> list[dict]:
        return self.tool("list_sequences").get("sequences", [])

    def voces(self, idioma: str = "es") -> list[dict]:
        return [v for v in self.tool("list_voices").get("voices", []) if v.get("language", "").startswith(idioma)]

    def llamadas(self, agent_id: str, limit: int = 100, **filtros) -> dict:
        return self.tool("list_calls", agent_id=agent_id, limit=limit, **filtros)

    def llamada(self, call_id: str) -> dict:
        return self.tool("get_call", call_id=call_id)

    def leads_calificados(self, agent_id: str, limit: int = 200) -> dict:
        return self.tool("find_qualified_leads", agent_id=agent_id, limit=limit)

    def contactos_secuencia(self, sequence_id: str, status: str | None = None, limit: int = 100, page: int = 1) -> dict:
        args = {"sequence_id": sequence_id, "limit": limit, "page": page}
        if status:
            args["status"] = status
        return self.tool("list_sequence_contacts", **args)

    def intentos_contacto(self, sequence_id: str, phone: str) -> dict:
        return self.tool("get_sequence_contact_attempts", sequence_id=sequence_id, phone=phone)

    # --- escrituras (preview -> commit) ---
    def crear_agente_voz(self, **campos) -> dict:
        return self.tool("create_voice_agent", **campos)

    def actualizar_agente(self, agent_id: str, **campos) -> dict:
        """Cambia campos del agente de voz (p. ej. dapta_webhook) con el ciclo preview → commit."""
        previo = self.tool("preview_update_voice_agent", agent_id=agent_id, **campos)
        return self.tool("commit_update_voice_agent", preview_token=self._token(previo))

    def crear_secuencia(self, nombre: str, agent_id: str, descripcion: str = "") -> dict:
        previo = self.tool("preview_create_sequence", name=nombre, agent_id=agent_id, description=descripcion or None)
        return self.tool("commit_create_sequence", preview_token=self._token(previo))

    def reglas_secuencia(self, sequence_id: str, patch: dict, start_date: str | None = None) -> dict:
        previo = self.tool("preview_update_sequence_rules", sequence_id=sequence_id, rules_patch=patch, start_date=start_date)
        return self.tool("commit_update_sequence_rules", preview_token=self._token(previo))

    def adjuntar_contactos(self, sequence_id: str, contactos: list[dict]) -> dict:
        previo = self.tool("preview_attach_sequence_contacts", sequence_id=sequence_id, contacts=contactos)
        return self.tool("commit_attach_sequence_contacts", preview_token=self._token(previo))


REGLAS_LEY_2300 = {
    "timeZone": "America/Bogota",
    "attemptsPerDay": 1,
    "maxAttempts": 2,
    "schedule": {
        "Mon": {"enabled": True, "timeSlots": [{"startTime": "07:00 AM", "endTime": "07:00 PM"}]},
        "Tue": {"enabled": True, "timeSlots": [{"startTime": "07:00 AM", "endTime": "07:00 PM"}]},
        "Wed": {"enabled": True, "timeSlots": [{"startTime": "07:00 AM", "endTime": "07:00 PM"}]},
        "Thu": {"enabled": True, "timeSlots": [{"startTime": "07:00 AM", "endTime": "07:00 PM"}]},
        "Fri": {"enabled": True, "timeSlots": [{"startTime": "07:00 AM", "endTime": "07:00 PM"}]},
        "Sat": {"enabled": True, "timeSlots": [{"startTime": "08:00 AM", "endTime": "03:00 PM"}]},
        "Sun": {"enabled": False, "timeSlots": []},
    },
}
