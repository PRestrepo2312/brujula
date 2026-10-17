"""Perfil de cliente ideal (ICP): reglas duras + Jev (TypeSafe) para la probabilidad. Umbrales: 0,7 pasa; 0,4 a 0,7 revisar; menos descarta.

Jev no escribe texto: responde preguntas tipadas con probabilidades. Se usa por OpenRouter
(POST https://openrouter.ai/api/alpha/decisions). Si no hay clave, se puntúa solo con reglas.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from .config import RAIZ, config
from .models import Lead

UMBRAL_PASA = 0.70
UMBRAL_REVISAR = 0.40


@dataclass
class ICP:
    nombre: str = "Pymes de servicios en Colombia"
    descripcion: str = ("Pymes de servicios que reciben clientes por teléfono o WhatsApp y hoy dependen de pauta: "
                        "clínicas e IPS privadas, colegios y academias, hoteles y agencias de viajes.")
    paises: list[str] = field(default_factory=lambda: ["CO"])
    sectores: list[str] = field(default_factory=lambda: ["salud", "educacion", "turismo"])   # valor de Lead.sector
    palabras_sector: list[str] = field(default_factory=list)   # para fuentes con sector libre (SECOP, OSM)
    ciudades: list[str] = field(default_factory=list)          # vacío = todas
    excluir_palabras: list[str] = field(default_factory=lambda: ["FUNDACION", "ASOCIACION", "COOPERATIVA", "JUNTA", "ALCALDIA", "GOBERNACION", "MINISTERIO", "UNIVERSIDAD NACIONAL"])
    requiere_canal: bool = True
    empleados_min: int | None = None
    empleados_max: int | None = None
    segmentos: dict[str, str] = field(default_factory=lambda: {
        "salud": "Clínica, IPS, laboratorio, consultorio odontológico o centro médico privado que agenda pacientes.",
        "educacion": "Colegio, academia, instituto o centro de formación privado que matricula estudiantes.",
        "turismo": "Hotel, hostal, agencia de viajes, operador turístico o restaurante que recibe reservas.",
        "otro": "Cualquier otro negocio.",
    })

    @classmethod
    def cargar(cls, ruta: str | Path | None = None) -> "ICP":
        ruta = Path(ruta) if ruta else RAIZ / "icp.json"
        if ruta.exists():
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            return cls(**{k: v for k, v in datos.items() if k in cls.__dataclass_fields__})
        return cls()

    def guardar(self, ruta: str | Path | None = None) -> Path:
        ruta = Path(ruta) if ruta else RAIZ / "icp.json"
        ruta.write_text(json.dumps(self.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
        return ruta


def puntuar_reglas(lead: Lead, icp: ICP) -> tuple[float, dict]:
    """Puntuación determinista 0 a 1 y detalle legible."""
    detalle = {}
    puntos = 0.0
    if lead.pais in icp.paises:
        puntos += 0.15
        detalle["pais"] = "ok"
    else:
        return 0.0, {"pais": "fuera del ICP"}
    nombre = (lead.nombre_norm or lead.razon_social).upper()
    if any(p in nombre for p in icp.excluir_palabras):
        return 0.05, {"excluido": "palabra excluida en el nombre"}
    sector = (lead.sector or "").lower()
    if sector in icp.sectores:
        puntos += 0.45
        detalle["sector"] = sector
    elif icp.palabras_sector and any(p.lower() in f"{sector} {lead.subsector}".lower() for p in icp.palabras_sector):
        puntos += 0.35
        detalle["sector"] = "por palabra clave"
    else:
        detalle["sector"] = "no coincide"
    if not icp.ciudades or lead.ciudad in [c.upper() for c in icp.ciudades]:
        puntos += 0.15
        detalle["ciudad"] = "ok"
    else:
        detalle["ciudad"] = "fuera"
    if lead.telefono or lead.correo:
        puntos += 0.15
        detalle["canal"] = ",".join(lead.canales or [])
    elif icp.requiere_canal:
        detalle["canal"] = "sin canal"
    if lead.empleados is not None:
        if (icp.empleados_min is None or lead.empleados >= icp.empleados_min) and (icp.empleados_max is None or lead.empleados <= icp.empleados_max):
            puntos += 0.10
            detalle["tamano"] = "ok"
        else:
            detalle["tamano"] = "fuera de rango"
    else:
        puntos += 0.05
        detalle["tamano"] = "sin dato"
    return round(min(puntos, 1.0), 3), detalle


def puntuar_jev(leads: list[Lead], icp: ICP) -> list[tuple[float, dict] | None]:
    """Una pregunta noul (encaja), una choice (segmento) y un score (madurez) por lead, en paralelo por HTTP."""
    if not config.jev_disponible:
        return [None] * len(leads)
    salida: list[tuple[float, dict] | None] = []
    with httpx.Client(timeout=60, headers={"Authorization": f"Bearer {config.openrouter_api_key}", "Content-Type": "application/json"}) as http:
        for lead in leads:
            estado = {
                "empresa": lead.razon_social, "sector_fuente": f"{lead.sector} {lead.subsector}".strip(), "ciudad": lead.ciudad,
                "pais": lead.pais, "canales": lead.canales, "empleados": lead.empleados, "senales": list((lead.senales or {}).keys()),
                "sitio_web": lead.sitio_web or "", "perfil_buscado": icp.descripcion,
            }
            cuerpo = {
                "model": config.jev_model,
                "state": estado,
                "questions": {
                    "encaja": {"type": "noul", "instructions": "La empresa encaja con el perfil buscado.",
                               "criteria": {"true": "Es una empresa del tipo descrito en perfil_buscado y atiende clientes por teléfono o mensajes.",
                                            "false": "No es del tipo descrito, es una entidad pública, una persona natural o un negocio sin atención a clientes."}},
                    "segmento": {"type": "choice", "instructions": "Segmento de la empresa.", "criteria": icp.segmentos},
                    "madurez": {"type": "score", "instructions": "Madurez digital aparente de la empresa.",
                                "criteria": ["Sin presencia digital", "Tiene teléfono o correo", "Tiene sitio web", "Tiene sitio web y varios canales"]},
                },
            }
            try:
                r = http.post("https://openrouter.ai/api/alpha/decisions", json=cuerpo)
                r.raise_for_status()
                d = r.json()
                resp = d.get("answers", d)
                p = float(resp["encaja"].get("noul", 0.0))
                seg = resp.get("segmento", {})
                costo = float((d.get("usage") or {}).get("cost") or 0.0)
                salida.append((round(p, 3), {"jev": True, "segmento": seg.get("choice"), "segmento_confianza": seg.get("confidence"),
                                              "madurez": (resp.get("madurez") or {}).get("score"), "costo_usd": costo}))
            except Exception as e:  # noqa: BLE001
                salida.append((0.0, {"jev": False, "error": str(e)[:200]}))
    return salida


def estado_por_puntaje(p: float) -> str:
    if p >= UMBRAL_PASA:
        return "pasa"
    if p >= UMBRAL_REVISAR:
        return "revisar"
    return "descarta"


def puntuar(leads: list[Lead], icp: ICP, usar_jev: bool = True) -> dict:
    """Asigna icp_score, icp_estado e icp_detalle. Jev manda si está disponible; las reglas siempre se guardan."""
    jev = puntuar_jev(leads, icp) if usar_jev else [None] * len(leads)
    cuenta = {"pasa": 0, "revisar": 0, "descarta": 0, "jev": 0, "costo_jev_usd": 0.0}
    for lead, j in zip(leads, jev):
        pr, dr = puntuar_reglas(lead, icp)
        detalle = {"reglas": dr, "puntaje_reglas": pr}
        p = pr
        if j is not None and j[1].get("jev"):
            p = round(0.7 * j[0] + 0.3 * pr, 3)
            detalle.update(j[1])
            cuenta["jev"] += 1
            cuenta["costo_jev_usd"] += j[1].get("costo_usd", 0.0)
        lead.icp_score = p
        lead.icp_estado = estado_por_puntaje(p)
        lead.icp_detalle = detalle
        if lead.icp_estado == "pasa" and lead.estado == "nuevo":
            lead.estado = "listo"
        cuenta[lead.icp_estado] += 1
    return cuenta
