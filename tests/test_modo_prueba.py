import pytest

from brujula.channels.correo import CanalCorreo
from brujula.channels.voz_dapta import CanalVozDapta
from brujula.compliance import verificar_lead
from brujula.config import config
from brujula.models import Intento, Lead

CAMPOS = ("solo_prueba", "telefono_prueba", "correos_prueba")


@pytest.fixture
def fijar():
    """Config es un dataclass congelado: se cambia con object.__setattr__ y se restaura al salir."""
    original = {k: getattr(config, k) for k in CAMPOS}

    def _fijar(**valores):
        for k, v in valores.items():
            object.__setattr__(config, k, v)
    yield _fijar
    _fijar(**original)


def _lead(tel: str) -> Lead:
    return Lead(empresa_id=1, razon_social="COLEGIO DE PRUEBA", telefono=tel, telefono_tipo="celular", correo="rectoria@colegio.co",
                pais="CO", fuente_clave="men", sector="colegio", ciudad="BOGOTA", canales=["voz", "correo"], identificacion="9001234567")


def _intento(canal: str) -> Intento:
    return Intento(empresa_id=1, lead_id=0, canal=canal)


def test_modo_prueba_desvia_llamada_y_correo(fijar):
    """El lead real conserva nombre y pitch; la llamada va al número de prueba y el correo a un correo verificado."""
    fijar(solo_prueba=True, telefono_prueba="+573001112233", correos_prueba=["equipo@prueba.co"])
    lead = _lead("+573009998877")
    assert verificar_lead(lead, "voz")[0] and verificar_lead(lead, "correo")[0]
    voz = CanalVozDapta()
    r = voz.enviar(lead, _intento("voz"))
    assert r.estado == "programado" and r.ref_externa.endswith("+573001112233")
    assert r.detalle["desvio"] == {"original": "+573009998877", "destino": "+573001112233"}
    assert r.detalle["variables"]["empresa"].lower().startswith("colegio de prueba")
    assert voz.enviar(lead, _intento("voz")).estado == "omitido"            # una sola llamada de prueba por lote
    c = CanalCorreo().enviar(lead, _intento("correo"))
    assert c.estado == "enviado" and c.detalle["desvio"]["destino"] == "equipo@prueba.co"
    assert "iba para rectoria@colegio.co" in c.mensaje


def test_modo_prueba_sin_destino_omite(fijar):
    fijar(solo_prueba=True, telefono_prueba="", correos_prueba=[])
    ok, por_que = verificar_lead(_lead("+573009998877"), "voz")
    assert not ok and "modo prueba" in por_que
    assert CanalVozDapta().enviar(_lead("+573009998877"), _intento("voz")).estado == "omitido"
    assert CanalCorreo().enviar(_lead("+573009998877"), _intento("correo")).estado == "omitido"


def test_sin_modo_prueba_no_desvia(fijar):
    fijar(solo_prueba=False, telefono_prueba="", correos_prueba=[])
    assert verificar_lead(_lead("+573009998877"), "voz")[0]
    r = CanalVozDapta().enviar(_lead("+573009998877"), _intento("voz"))
    assert "desvio" not in r.detalle and r.ref_externa == "sim_+573009998877"
