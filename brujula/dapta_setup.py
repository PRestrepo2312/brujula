"""Crea en Dapta el agente de voz calificador y la secuencia con el horario de la Ley 2300. Guarda los ids en data/dapta.json."""
from __future__ import annotations

import json
from pathlib import Path

from .config import RAIZ, config
from .dapta_mcp import REGLAS_LEY_2300, DaptaMCP

VOZ_BOGOTA = "custom_voice_b7f9d4e2175e188767738b4a1c"   # "Angie vendedora Colombiana" (catálogo de Dapta)

INSTRUCCIONES = """Eres Angie, asistente comercial de {{remitente}}. Llamas a empresas colombianas para hacer un primer contacto corto, en nombre de {{remitente}}, y saber si les interesa lo que ofrece: {{propuesta}}.

Reglas:
- Habla en español de Colombia, con respeto y sin presionar. Máximo 3 minutos.
- Preséntate: "Hola, le habla Angie, del equipo de {{remitente}}. ¿Hablo con alguien de {{empresa}}?"
- Di por qué llamas: "Los llamamos porque {{senal}}, y {{propuesta}}."
- Pregunta, en este orden: 1) ¿Hoy cómo resuelven eso? 2) ¿Les está costando tiempo o clientes? 3) ¿Les interesaría una conversación de 15 minutos esta semana para ver si les sirve? Si sí, pregunta el mejor día y hora y el correo para enviar la invitación.
- Si la persona pide no ser contactada, agradece, confirma que no volverán a llamar y termina la llamada.
- Si contesta un buzón, no dejes mensaje.
- Nunca inventes precios ni promesas. Si preguntan de dónde salió el contacto, di que de registros públicos de empresas.
- Termina siempre agradeciendo el tiempo."""

VARIABLES_POST_LLAMADA = [
    {"name": "interesado", "type": "boolean", "description": "La persona aceptó una demostración o pidió más información."},
    {"name": "recibe_clientes_por", "type": "string", "description": "Canales por los que la empresa recibe clientes: telefono, whatsapp, redes, web u otro."},
    {"name": "pierde_contactos", "type": "boolean", "description": "La persona reconoció que se les quedan llamadas o mensajes sin contestar."},
    {"name": "mejor_momento", "type": "string", "description": "Día y hora propuestos para la demostración, si los dio."},
    {"name": "correo_demo", "type": "string", "description": "Correo al que pidió la invitación, si lo dio."},
    {"name": "baja", "type": "boolean", "description": "La persona pidió no ser contactada de nuevo."},
    {"name": "persona_correcta", "type": "boolean", "description": "Contestó alguien de la empresa con capacidad de decidir o de pasar el contacto."},
]


def configurar(crear_agente: bool = True, crear_secuencia: bool = True) -> dict:
    from datetime import date
    mcp = DaptaMCP()
    salida = {}
    archivo = RAIZ / "data" / "dapta.json"
    previo = json.loads(archivo.read_text(encoding="utf-8")) if archivo.exists() else {}
    agent_id = config.dapta_agent_id or previo.get("agent_id", "")
    # El webhook post-llamada exige https: en local se omite y se fija al desplegar (los resultados también se leen por list_calls).
    webhook = f"{config.public_base_url.rstrip('/')}/webhook/dapta" if config.public_base_url.startswith("https://") else None
    if crear_agente and not agent_id:
        r = mcp.crear_agente_voz(
            agent_name="Brújula · calificador",
            agent_purpose="103",
            company_name="Brújula (equipo JFB Devs, Hackathon 30X)",
            company_description="Herramienta que encuentra empresas en fuentes públicas, las contacta y mide el costo por lead calificado por canal.",
            instructions=INSTRUCCIONES,
            voice_language="es-419",
            identity_name="Angie",
            voice=VOZ_BOGOTA,
            post_call_analysis_data=VARIABLES_POST_LLAMADA,
            dapta_webhook=webhook,
            voicemail_option={"action": {"type": "hangup"}},
            enable_voicemail_detection=True,
            analysis_summary_prompt="Resume en dos frases, en español, qué dijo la empresa y si quiere una demostración.",
            analysis_successful_prompt="La llamada fue exitosa si la persona aceptó una demostración o pidió más información (interesado = true).",
        )
        agent_id = r.get("agent_id") or (r.get("agent") or {}).get("agent_id") or (r.get("agent") or {}).get("id", "")
        salida["agente"] = {"agent_id": agent_id, "verified": r.get("verified"), "not_verified": r.get("not_verified")}
    elif agent_id and webhook:
        # El agente ya existe (p. ej. se creó en local): se le fija el webhook de la URL pública del despliegue.
        r = mcp.actualizar_agente(agent_id, dapta_webhook=webhook)
        salida["webhook"] = {"agent_id": agent_id, "dapta_webhook": webhook, "verified": r.get("verified"), "not_verified": r.get("not_verified")}
    seq_id = config.dapta_sequence_id or previo.get("sequence_id", "")
    if crear_secuencia and agent_id and not seq_id:
        r = mcp.crear_secuencia("Brújula · primer contacto", agent_id, "Leads de fuentes públicas que encajan con el ICP. Horario Ley 2300.")
        seq_id = r.get("sequence_id") or (r.get("sequence") or {}).get("id") or (r.get("sequence") or {}).get("sequence_id", "")
        salida["secuencia"] = {"sequence_id": seq_id, "verified": r.get("verified")}
        if seq_id:
            salida["reglas"] = mcp.reglas_secuencia(seq_id, REGLAS_LEY_2300, start_date=date.today().isoformat())
    datos = {"agent_id": agent_id, "sequence_id": seq_id, "workspace": (mcp.whoami().get("workspace") or {}).get("id", "")}
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    salida["guardado_en"] = str(archivo)
    salida["ids"] = datos
    return salida
