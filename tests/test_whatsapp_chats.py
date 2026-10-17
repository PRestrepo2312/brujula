from sqlmodel import select

from brujula.config import config
from brujula.db import sesion
from brujula.models import Intento, Lead
from brujula.pipeline import sincronizar_chats

EMP = 880


class MCPFalso:
    """Dos conversaciones de WhatsApp como las entrega Dapta (más una del playground, que se ignora)."""

    def conversaciones(self, agent_id, limit=50):
        return {"conversations": [
            {"id": "conv-1", "channel_type": "meta_whatsapp", "channel_identifier": "CO.3001112233772233", "created_at": "2026-10-17T21:43:21+00:00", "last_message_content": "¿Reciben clientes?"},
            {"id": "conv-2", "channel_type": "meta_whatsapp", "channel_identifier": "CO.9999999999", "created_at": "2026-10-17T21:50:00+00:00"},
            {"id": "conv-pg", "channel_type": "playground", "channel_identifier": "x"},
        ]}

    def conversacion(self, cid):
        if cid == "conv-1":
            return {"messages": [{"direction": "inbound", "content": "Hola, sí me interesa la demostración, agendemos"}, {"direction": "outbound", "content": "..."}],
                    "summary": {"credits_total": 80, "booked": True}}
        return {"messages": [{"direction": "inbound", "content": "no me escriban más, baja"}], "summary": {"credits_total": 40}}


def test_chats_de_whatsapp_se_vuelven_respuestas():
    object.__setattr__(config, "dapta_text_agent_id", "agente-texto")
    with sesion() as s:
        s.add(Lead(empresa_id=EMP, razon_social="CLINICA UNO SAS", telefono="+573001112233", pais="CO", fuente_clave="reps", canales=["voz", "whatsapp"], estado="contactado"))
        s.commit()
    r = sincronizar_chats(EMP, mcp=MCPFalso())
    assert r == {"conversaciones": 2, "nuevas": 2, "actualizadas": 2}
    with sesion() as s:
        its = {it.ref_externa: it for it in s.exec(select(Intento).where(Intento.empresa_id == EMP, Intento.canal == "whatsapp")).all()}
        l1 = s.get(Lead, its["conv-1"].lead_id)
        assert l1.razon_social == "CLINICA UNO SAS" and l1.estado == "respondio"            # emparejado por los dígitos del identificador
        assert its["conv-1"].estado == "contestado" and its["conv-1"].clasificacion == "interesado" and its["conv-1"].costo_usd == 0.08
        l2 = s.get(Lead, its["conv-2"].lead_id)
        assert l2.fuente_clave == "whatsapp" and l2.estado == "baja" and its["conv-2"].clasificacion == "baja"   # lead 'WhatsApp entrante'
    assert sincronizar_chats(EMP, mcp=MCPFalso())["nuevas"] == 0                              # idempotente
    object.__setattr__(config, "dapta_text_agent_id", "")
