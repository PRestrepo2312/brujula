"""Modelo de datos. Un lead es una empresa (nunca una persona natural). Cada intento de contacto lleva su costo."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


def ahora() -> datetime:
    return datetime.utcnow()


class Fuente(SQLModel, table=True):
    """De dónde salen los leads. costo_fijo_usd se prorratea entre los leads que trae."""

    id: Optional[int] = Field(default=None, primary_key=True)
    clave: str = Field(index=True, unique=True)      # reps, men, rnt, secop, osm, denue, cnpj, nyc
    nombre: str
    pais: str = "CO"
    tipo: str = "registro"                            # registro | mapa | web | catalogo
    licencia: str = ""
    url: str = ""
    contacta: bool = True                             # False = solo encontrar (otros países)
    costo_fijo_usd: float = 0.0
    creado_en: datetime = Field(default_factory=ahora)


class Lead(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    pais: str = Field(default="CO", index=True)
    identificacion: Optional[str] = Field(default=None, index=True)   # NIT sin dígito de verificación, RFC, CNPJ
    razon_social: str = Field(index=True)
    nombre_norm: str = Field(default="", index=True)
    sector: str = ""                                   # CIIU, categoría o texto de la fuente
    subsector: str = ""
    ciudad: str = Field(default="", index=True)
    departamento: str = ""
    direccion: str = ""
    telefono: Optional[str] = Field(default=None, index=True)        # E.164
    telefono_tipo: str = ""                            # celular | fijo
    correo: Optional[str] = Field(default=None, index=True)
    sitio_web: Optional[str] = None
    dominio: Optional[str] = Field(default=None, index=True)
    canales: list = Field(default_factory=list, sa_column=Column(JSON))   # ["voz", "correo", "whatsapp"]
    senales: dict = Field(default_factory=dict, sa_column=Column(JSON))   # {"contrato_secop": {...}, "empresa_nueva": ...}
    tamano: str = ""                                   # micro | pequeña | mediana | grande | ""
    empleados: Optional[int] = None
    fuente_clave: str = Field(index=True)
    fuente_registro: str = ""                          # id del registro en la fuente
    fuentes_todas: list = Field(default_factory=list, sa_column=Column(JSON))  # claves de todas las fuentes donde apareció
    icp_score: Optional[float] = Field(default=None, index=True)
    icp_estado: str = Field(default="pendiente", index=True)   # pendiente | pasa | revisar | descarta
    icp_detalle: dict = Field(default_factory=dict, sa_column=Column(JSON))
    dedupe_clave: Optional[str] = Field(default=None, index=True)
    duplicado_de: Optional[int] = Field(default=None, index=True)
    estado: str = Field(default="nuevo", index=True)   # nuevo | listo | contactado | respondio | calificado | no_calificado | baja | descartado
    costo_encontrar_usd: float = 0.0                   # descargar + enriquecer + puntuar, prorrateado
    creado_en: datetime = Field(default_factory=ahora)
    actualizado_en: datetime = Field(default_factory=ahora)
    crudo: dict = Field(default_factory=dict, sa_column=Column(JSON))


class Lote(SQLModel, table=True):
    """Un lote de contacto. La brújula decide el reparto y lo explica."""

    id: Optional[int] = Field(default=None, primary_key=True)
    creado_en: datetime = Field(default_factory=ahora)
    reparto: dict = Field(default_factory=dict, sa_column=Column(JSON))   # {"reps|voz": 20, "rnt|correo": 30}
    explicacion: str = ""
    modo: str = "manual"                               # manual | brujula
    fuera_ventana: bool = False
    override_motivo: str = ""
    override_usuario: str = ""


class Intento(SQLModel, table=True):
    """Un intento de contacto por un canal, con su costo real."""

    id: Optional[int] = Field(default=None, primary_key=True)
    lead_id: int = Field(index=True, foreign_key="lead.id")
    lote_id: Optional[int] = Field(default=None, index=True, foreign_key="lote.id")
    canal: str = Field(index=True)                     # correo | voz | whatsapp
    proveedor: str = ""                                # resend | ses | dapta | meta | simulado
    estado: str = Field(default="programado", index=True)  # programado | enviado | entregado | abierto | contestado | no_contesta | buzon | fallido | respondio | baja
    costo_usd: float = 0.0
    duracion_seg: int = 0
    ref_externa: Optional[str] = Field(default=None, index=True)   # id de la llamada o del correo
    mensaje: str = ""
    respuesta: str = ""
    clasificacion: str = ""                            # interesado | no_interesado | despues | equivocado | baja | ""
    fuera_ventana: bool = False
    enviado_en: Optional[datetime] = None
    respondido_en: Optional[datetime] = None
    creado_en: datetime = Field(default_factory=ahora)
    detalle: dict = Field(default_factory=dict, sa_column=Column(JSON))


class Calificacion(SQLModel, table=True):
    """Lo que dice el agente calificador de Dapta de un lead que respondió."""

    id: Optional[int] = Field(default=None, primary_key=True)
    lead_id: int = Field(index=True, foreign_key="lead.id")
    intento_id: Optional[int] = Field(default=None, foreign_key="intento.id")
    resultado: str = Field(default="pendiente", index=True)   # pendiente | calificado | no_calificado
    costo_usd: float = 0.0
    ref_externa: Optional[str] = None
    datos: dict = Field(default_factory=dict, sa_column=Column(JSON))
    creado_en: datetime = Field(default_factory=ahora)


class Costo(SQLModel, table=True):
    """Bitácora de costos que no cuelgan de un intento: descarga, Jev, cómputo, número."""

    id: Optional[int] = Field(default=None, primary_key=True)
    concepto: str
    fuente_clave: str = ""
    canal: str = ""
    usd: float = 0.0
    cantidad: float = 1.0
    creado_en: datetime = Field(default_factory=ahora)


class Exclusion(SQLModel, table=True):
    """Bajas y números o correos excluidos (RNE de la CRC o petición del lead)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    valor: str = Field(index=True, unique=True)        # E.164 o correo en minúsculas
    origen: str = "baja"                               # baja | rne | manual
    creado_en: datetime = Field(default_factory=ahora)


class Bitacora(SQLModel, table=True):
    """Todo lo que explica una decisión: overrides, repartos, errores."""

    id: Optional[int] = Field(default=None, primary_key=True)
    tipo: str = Field(index=True)                      # override | reparto | error | info
    mensaje: str
    datos: dict = Field(default_factory=dict, sa_column=Column(JSON))
    creado_en: datetime = Field(default_factory=ahora)
