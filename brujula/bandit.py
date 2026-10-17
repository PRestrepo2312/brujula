"""La brújula: un bandido multibrazo (Thompson sampling) sobre brazos fuente × canal.

Recompensa: leads calificados por dólar. Mientras no haya calificaciones, usa respuestas por dólar.
Cada brazo lleva una Beta(alfa, beta): alfa = 1 + éxitos, beta = 1 + fracasos, con priors declarados.
El reparto del siguiente lote es proporcional a la muestra de cada brazo dividida por su costo medio por intento.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .config import config

# Priors (lo que creemos antes de tener datos): tasa esperada de éxito y costo por intento, por canal.
PRIORS = {
    "voz": {"exitos": 2.0, "fracasos": 8.0, "costo": config.tarifas.voz_no_contesta * 0.7 + config.tarifas.voz_minuto_contestado * 0.3 * 2},
    "correo": {"exitos": 1.0, "fracasos": 24.0, "costo": config.tarifas.correo},
    "whatsapp": {"exitos": 2.0, "fracasos": 13.0, "costo": config.tarifas.whatsapp_conversacion_co},
}


@dataclass
class Brazo:
    fuente: str
    canal: str
    intentos: int = 0
    exitos: int = 0
    costo_usd: float = 0.0
    disponibles: int = 0          # leads listos con ese canal en esa fuente

    @property
    def clave(self) -> str:
        return f"{self.fuente}|{self.canal}"

    def alfa_beta(self) -> tuple[float, float]:
        p = PRIORS.get(self.canal, {"exitos": 1.0, "fracasos": 9.0})
        return p["exitos"] + self.exitos, p["fracasos"] + max(0, self.intentos - self.exitos)

    def costo_medio(self) -> float:
        p = PRIORS.get(self.canal, {"costo": 0.05})
        if self.intentos:
            # mezcla el prior con lo observado para no dividir por casi cero al principio
            return (p["costo"] * 5 + self.costo_usd) / (5 + self.intentos)
        return max(p["costo"], 0.0001)

    def costo_por_exito(self, p: float) -> float:
        """Costo esperado de conseguir un éxito: intentos hasta un éxito más la llamada de calificación de Dapta
        cuando el canal no califica en el mismo contacto (correo y WhatsApp sí la necesitan; la voz califica en la llamada)."""
        intentos_por_exito = 1.0 / max(p, 1e-4)
        extra = 0.0 if self.canal == "voz" else 2 * config.tarifas.voz_minuto_contestado
        return intentos_por_exito * self.costo_medio() + extra


def repartir(brazos: list[Brazo], n: int, semilla: int | None = None, muestras: int = 12) -> tuple[dict[str, int], str]:
    """Devuelve {clave_brazo: cuántos leads} y una explicación en una frase."""
    rnd = random.Random(semilla)
    activos = [b for b in brazos if b.disponibles > 0]
    if not activos or n <= 0:
        return {}, "No hay leads disponibles para repartir."
    # Éxitos por dólar con muestreo de Thompson (promedio de pocas muestras: explora, pero el reparto se puede explicar).
    valor = {}
    for b in activos:
        a, be = b.alfa_beta()
        p = sum(rnd.betavariate(a, be) for _ in range(muestras)) / muestras
        valor[b.clave] = 1.0 / b.costo_por_exito(p)
    total = sum(valor.values())
    reparto = {}
    restante = n
    # Piso de exploración: ningún canal con leads disponibles se queda sin al menos el 15 % del lote.
    piso = max(1, round(n * 0.15))
    for b in sorted(activos, key=lambda x: -valor[x.clave]):
        cuota = max(piso, round(n * valor[b.clave] / total)) if total else piso
        cuota = min(cuota, b.disponibles, restante)
        reparto[b.clave] = cuota
        restante -= cuota
        if restante <= 0:
            break
    # Si sobró por los mínimos, se lo lleva el mejor con cupo.
    for b in sorted(activos, key=lambda x: -valor[x.clave]):
        if restante <= 0:
            break
        extra = min(restante, b.disponibles - reparto.get(b.clave, 0))
        if extra > 0:
            reparto[b.clave] = reparto.get(b.clave, 0) + extra
            restante -= extra
    mejor = max(activos, key=lambda x: valor[x.clave])
    partes = ", ".join(f"{k.replace('|', ' + ')} {v}" for k, v in reparto.items())
    con_datos = [b for b in activos if b.intentos]
    if con_datos:
        exp = (f"Reparto {partes}. Manda {mejor.clave.replace('|', ' + ')}: {mejor.exitos} éxitos en {mejor.intentos} intentos "
               f"a USD {mejor.costo_medio():.3f} por intento, el menor costo esperado por lead calificado.")
    else:
        exp = (f"Reparto {partes}. Todavía sin resultados: deciden los priors (el correo es casi gratis pero necesita la llamada "
               f"de Dapta para calificar; la voz califica en la misma llamada). Cada canal recibe al menos el 15 % para explorar.")
    return reparto, exp
