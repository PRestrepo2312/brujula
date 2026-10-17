from datetime import datetime, timedelta

from brujula.channels.voz_dapta import DIAS, CanalVozDapta
from brujula.compliance import ahora_local, anotar
from brujula.dapta_mcp import REGLAS_LEY_2300
from brujula.pipeline import restaurar_ventana_dapta_si_vencio


class MCPFalso:
    def __init__(self):
        self.llamadas = []

    def reglas_secuencia(self, sequence_id, patch, start_date=None):
        self.llamadas.append((sequence_id, patch))
        return {"verified": True}


def _voz():
    v = CanalVozDapta()
    v.ids = {"agent_id": "a", "sequence_id": "seq"}
    v._mcp = MCPFalso()
    return v


def test_override_abre_solo_hoy_y_restaura():
    v = _voz()
    v.abrir_ventana_hoy()
    seq, reglas = v._mcp.llamadas[-1]
    hoy = DIAS[ahora_local().weekday()]
    assert seq == "seq" and reglas["schedule"][hoy] == {"enabled": True, "timeSlots": [{"startTime": "06:00 AM", "endTime": "11:59 PM"}]}
    otros = [d for d in DIAS if d != hoy]
    assert all(reglas["schedule"][d] == REGLAS_LEY_2300["schedule"][d] for d in otros)
    assert REGLAS_LEY_2300["schedule"][hoy] != reglas["schedule"][hoy] or hoy == "Sun"   # la constante no se modifica
    v.restaurar_ventana_legal()
    assert v._mcp.llamadas[-1][1] == REGLAS_LEY_2300


def test_restaura_solo_cuando_vence():
    v = _voz()
    emp = 77
    assert restaurar_ventana_dapta_si_vencio(v, emp) is False                 # sin override, nada
    anotar("override_dapta", "abierto", emp, hasta=(datetime.utcnow() + timedelta(hours=2)).isoformat())
    assert restaurar_ventana_dapta_si_vencio(v, emp) is False and not v._mcp.llamadas   # todavía no vence
    anotar("override_dapta", "abierto", emp, hasta=(datetime.utcnow() - timedelta(minutes=1)).isoformat())
    assert restaurar_ventana_dapta_si_vencio(v, emp) is True and v._mcp.llamadas[-1][1] == REGLAS_LEY_2300
    assert restaurar_ventana_dapta_si_vencio(v, emp) is False                 # ya cerrado: no repite
