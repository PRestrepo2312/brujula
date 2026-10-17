"""Cumplimiento: ventana de la Ley 2300 de 2023, lista de exclusión (RNE de la CRC y bajas) y reglas de datos.

Ley 2300: lunes a viernes de 7:00 a. m. a 7:00 p. m., sábados de 8:00 a. m. a 3:00 p. m., nunca domingos ni festivos.
La ley protege a consumidores; Brújula la aplica también a empresas por diseño. Contactar fuera de la ventana
exige un override explícito (quién, motivo), que queda en la bitácora.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlmodel import select

from .config import config
from .db import sesion
from .models import Bitacora, Exclusion, Lead

# Festivos nacionales de Colombia que caen cerca del evento (completar con el calendario oficial para producción).
FESTIVOS = {date(2026, 10, 12), date(2026, 11, 2), date(2026, 11, 16), date(2026, 12, 8), date(2026, 12, 25), date(2027, 1, 1), date(2027, 1, 11)}
VENTANAS = {0: (time(7, 0), time(19, 0)), 1: (time(7, 0), time(19, 0)), 2: (time(7, 0), time(19, 0)), 3: (time(7, 0), time(19, 0)),
            4: (time(7, 0), time(19, 0)), 5: (time(8, 0), time(15, 0))}   # 6 = domingo: nunca


def ahora_local() -> datetime:
    return datetime.now(ZoneInfo(config.tz))


def ventana_permitida(momento: datetime | None = None) -> tuple[bool, str]:
    m = momento or ahora_local()
    if m.date() in FESTIVOS:
        return False, "festivo: la Ley 2300 no permite contacto"
    v = VENTANAS.get(m.weekday())
    if not v:
        return False, "domingo: la Ley 2300 no permite contacto"
    ini, fin = v
    if ini <= m.time() <= fin:
        return True, f"dentro de la ventana ({ini:%H:%M} a {fin:%H:%M})"
    return False, f"fuera de la ventana ({ini:%H:%M} a {fin:%H:%M})"


def proxima_ventana(momento: datetime | None = None) -> datetime:
    """Próximo instante en que se puede contactar."""
    m = momento or ahora_local()
    for dias in range(0, 8):
        d = m.date() if dias == 0 else date.fromordinal(m.date().toordinal() + dias)
        if d in FESTIVOS:
            continue
        v = VENTANAS.get(d.weekday())
        if not v:
            continue
        ini, fin = v
        if dias == 0:
            if m.time() < ini:
                return m.replace(hour=ini.hour, minute=ini.minute, second=0, microsecond=0)
            if m.time() <= fin:
                return m
            continue
        return datetime.combine(d, ini, tzinfo=m.tzinfo)
    return m


def normal(valor: str) -> str:
    return (valor or "").strip().lower()


def esta_excluido(*valores: str | None, empresa_id: int = 1) -> bool:
    """Excluido si está en el RNE (global, empresa 0) o en las bajas de la empresa."""
    vals = [normal(v) for v in valores if v]
    if not vals:
        return False
    with sesion() as s:
        return s.exec(select(Exclusion).where(Exclusion.valor.in_(vals), Exclusion.empresa_id.in_([0, empresa_id]))).first() is not None


def registrar_exclusion(valor: str, origen: str = "baja", empresa_id: int = 1) -> None:
    v = normal(valor)
    if not v:
        return
    emp = 0 if origen == "rne" else empresa_id
    with sesion() as s:
        if not s.exec(select(Exclusion).where(Exclusion.valor == v, Exclusion.empresa_id == emp)).first():
            s.add(Exclusion(empresa_id=emp, valor=v, origen=origen))
            s.commit()


def cargar_rne_csv(ruta: str | Path) -> int:
    """Carga un CSV con números o correos excluidos (una columna, o la primera columna). Formato del RNE de la CRC."""
    n = 0
    with open(ruta, encoding="utf-8", newline="") as f:
        for fila in csv.reader(f):
            if not fila:
                continue
            v = fila[0].strip()
            if v and not v.lower().startswith(("numero", "número", "telefono", "correo", "email")):
                registrar_exclusion(v, "rne")
                n += 1
    return n


def verificar_lead(lead: Lead, canal: str) -> tuple[bool, str]:
    """Qué impide contactar a un lead por un canal. Solo empresas, con canal y sin exclusión; en modo prueba, solo canales con desvío."""
    from .config import config
    if config.modo_prueba and not config.destino_prueba(canal):
        return False, f"modo prueba: sin destino de desvío para {canal}"
    if lead.pais == "CO" and lead.identificacion and lead.identificacion[0] not in "89":
        return False, "la identificación no es de persona jurídica"
    if canal in ("voz", "whatsapp") and not lead.telefono:
        return False, "sin teléfono"
    if canal == "whatsapp" and lead.telefono_tipo != "celular":
        return False, "el teléfono no es celular"
    if canal == "correo" and not lead.correo:
        return False, "sin correo"
    if esta_excluido(lead.telefono, lead.correo, empresa_id=lead.empresa_id):
        return False, "en lista de exclusión (RNE o baja)"
    if lead.estado in ("baja", "descartado"):
        return False, f"estado {lead.estado}"
    return True, "ok"


def anotar(tipo: str, mensaje: str, empresa_id: int = 1, **datos) -> None:
    with sesion() as s:
        s.add(Bitacora(empresa_id=empresa_id, tipo=tipo, mensaje=mensaje, datos=datos))
        s.commit()
