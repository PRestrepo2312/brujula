"""Set de prueba de 50 empresas: mide la deduplicación y el filtro del ICP con casos trampa (duplicados disfrazados)."""
from __future__ import annotations

import json
import random
import re

from sqlmodel import select

from .config import RAIZ
from .db import sesion
from .dedupe import deduplicar
from .models import Lead
from .normalize import nombre_normalizado


def _disfrazar(nombre: str, rnd: random.Random) -> str:
    opciones = [
        lambda n: n.replace("SAS", "S.A.S.") if "SAS" in n else n + " S.A.S.",
        lambda n: n.lower().title(),
        lambda n: re.sub(r"\s+", "  ", n),
        lambda n: n.replace("CLINICA", "CLÍNICA").replace("COLEGIO", "Colegio"),
        lambda n: n + " PRINCIPAL",
    ]
    return rnd.choice(opciones)(nombre)


def generar(n: int = 50, semilla: int = 30) -> dict:
    """Toma n empresas reales ya encontradas y crea duplicados disfrazados (sin NIT, nombre cambiado, teléfono con formato distinto)."""
    rnd = random.Random(semilla)
    with sesion() as s:
        base = s.exec(select(Lead).where(Lead.duplicado_de.is_(None), Lead.icp_estado == "pasa").order_by(Lead.id).limit(n)).all()
        if len(base) < 5:
            return {"error": "faltan leads: corra fetch y score primero"}
        muestra = []
        ids_trampa = []
        for l in base:
            muestra.append({"id": l.id, "razon_social": l.razon_social, "nit": l.identificacion, "ciudad": l.ciudad, "fuente": l.fuente_clave})
            if rnd.random() < 0.4:
                trampa = Lead(
                    pais=l.pais, identificacion=None, razon_social=_disfrazar(l.razon_social, rnd), nombre_norm="",
                    sector=l.sector, ciudad=l.ciudad, departamento=l.departamento, telefono=l.telefono if rnd.random() < 0.6 else None,
                    telefono_tipo=l.telefono_tipo, correo=l.correo if rnd.random() < 0.5 else None, dominio=l.dominio if rnd.random() < 0.5 else None,
                    canales=l.canales, fuente_clave="prueba", fuente_registro=f"trampa-{l.id}", fuentes_todas=["prueba"], crudo={"trampa_de": l.id},
                )
                trampa.nombre_norm = nombre_normalizado(trampa.razon_social)
                s.add(trampa)
                s.commit()
                s.refresh(trampa)
                ids_trampa.append((trampa.id, l.id))
        ruta = RAIZ / "data" / "prueba_50.json"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps({"empresas": muestra, "trampas": ids_trampa}, ensure_ascii=False, indent=1), encoding="utf-8")
    r = deduplicar([t for t, _ in ids_trampa])
    with sesion() as s:
        aciertos = 0
        for t, orig in ids_trampa:
            lt = s.get(Lead, t)
            if lt.duplicado_de == orig:
                aciertos += 1
    return {"empresas": len(muestra), "trampas": len(ids_trampa), "duplicados_detectados": r["duplicados"], "aciertos": aciertos,
            "precision_dedupe": round(aciertos / len(ids_trampa), 3) if ids_trampa else None, "archivo": str(ruta)}
