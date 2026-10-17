from datetime import datetime
from zoneinfo import ZoneInfo

from brujula.bandit import Brazo, repartir
from brujula.compliance import proxima_ventana, ventana_permitida

BOG = ZoneInfo("America/Bogota")


def test_ventana_ley_2300():
    assert ventana_permitida(datetime(2026, 10, 16, 10, 0, tzinfo=BOG))[0]          # viernes 10 a. m.
    assert not ventana_permitida(datetime(2026, 10, 16, 19, 30, tzinfo=BOG))[0]     # viernes 7:30 p. m.
    assert ventana_permitida(datetime(2026, 10, 17, 9, 0, tzinfo=BOG))[0]           # sábado 9 a. m.
    assert not ventana_permitida(datetime(2026, 10, 17, 15, 30, tzinfo=BOG))[0]     # sábado 3:30 p. m.
    assert not ventana_permitida(datetime(2026, 10, 18, 11, 0, tzinfo=BOG))[0]      # domingo
    assert not ventana_permitida(datetime(2026, 11, 2, 11, 0, tzinfo=BOG))[0]       # festivo
    prox = proxima_ventana(datetime(2026, 10, 18, 11, 0, tzinfo=BOG))
    assert prox.weekday() == 0 and prox.hour == 7                                   # lunes 7 a. m.


def test_bandit_reparte_todo_y_explora():
    brazos = [Brazo("reps", "voz", intentos=20, exitos=6, costo_usd=6.0, disponibles=50),
              Brazo("reps", "correo", intentos=100, exitos=3, costo_usd=0.01, disponibles=50),
              Brazo("rnt", "voz", intentos=0, exitos=0, costo_usd=0.0, disponibles=50)]
    reparto, exp = repartir(brazos, 40, semilla=1)
    assert sum(reparto.values()) == 40
    assert all(v >= 1 for v in reparto.values())
    assert min(reparto.values()) >= round(40 * 0.15)
    assert "Reparto" in exp


def test_bandit_respeta_disponibles():
    brazos = [Brazo("reps", "voz", disponibles=3), Brazo("men", "correo", disponibles=2)]
    reparto, _ = repartir(brazos, 50)
    assert reparto == {"reps|voz": 3, "men|correo": 2} or sum(reparto.values()) == 5
