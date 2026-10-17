"""Modelo de datos. Un lead es una empresa (nunca una persona natural). Cada intento de contacto lleva su costo.

Todo cuelga de una Empresa (la cuenta que usa Brújula): leads, lotes, costos, bajas, bitácora y notificaciones.
La empresa 1 es la de demostración (JFB Devs) y existe siempre.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel

EMPRESA_DEMO = 1


def ahora() -> datetime:
    return datetime.utcnow()


class Empresa(SQLModel, table=True):
    """La cuenta que usa Brújula: su ICP, sus canales, su Dapta y a quién notificar."""

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str
    slug: str = Field(index=True, unique=True)
    correo_notificaciones: str = ""
    dapta_api_key: str = ""                            # clave MCP propia; vacía = usa la del servidor
    dapta_agent_id: str = ""
    dapta_sequence_id: str = ""
    icp: dict = Field(default_factory=dict, sa_column=Column(JSON))        # criterios estructurados (ver icp.ICP)
    icp_texto: str = ""                                                    # lo que escribió la empresa en español
    config: dict = Field(default_factory=dict, sa_column=Column(JSON))     # canales, presupuesto_lote, remitente, notificar_por
    creado_en: datetime = Field(default_factory=ahora)


class Fuente(SQLModel, table=True):
    """De dónde salen los leads. costo_fijo_usd se prorratea entre los leads que trae."""

    id: Optional[int] = Field(default=None, primary_key=True)
    clave: str = Field(index=True, unique=True)      # reps, men, rnt, secop, osm, csv, denue, cnpj, nyc
    nombre: str
    pais: str = "CO"
    tipo: str = "registro"                            # registro | mapa | web | archivo | catalogo
    licencia: str = ""
    url: str = ""
    contacta: bool = True                             # False = solo encontrar (otros países)
    costo_fijo_usd: float = 0.0
    creado_en: datetime = Field(default_factory=ahora)


class Lead(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    empresa_id: int = Field(default=EMPRESA_DEMO, index=True)
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
    senales: dict = Field(default_factory=dict, sa_column=Column(JSON))
    tamano: str = ""
    empleados: Optional[int] = None
    fuente_clave: str = Field(index=True)
    fuente_registro: str = ""
    fuentes_todas: list = Field(default_factory=list, sa_column=Column(JSON))
    icp_score: Optional[float] = Field(default=None, index=True)
    icp_estado: str = Field(default="pendiente", index=True)   # pendiente | pasa | revisar | descarta
    icp_detalle: dict = Field(default_factory=dict, sa_column=Column(JSON))
    dedupe_clave: Optional[str] = Field(default=None, index=True)
    duplicado_de: Optional[int] = Field(default=None, index=True)
    estado: str = Field(default="nuevo", index=True)   # nuevo | listo | contactado | respondio | calificado | no_calificado | baja | descartado
    costo_encontrar_usd: float = 0.0
    creado_en: datetime = Field(default_factory=ahora)
    actualizado_en: datetime = Field(default_factory=ahora)
    crudo: dict = Field(default_factory=dict, sa_column=Column(JSON))


class Lote(SQLModel, table=True):
    """Un lote de contacto. La brújula decide el reparto y lo explica."""

    id: Optional[int] = Field(default=None, primary_key=True)
    empresa_id: int = Field(default=EMPRESA_DEMO, index=True)
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
    empresa_id: int = Field(default=EMPRESA_DEMO, index=True)
    lead_id: int = Field(index=True, foreign_key="lead.id")
    lote_id: Optional[int] = Field(default=None, index=True, foreign_key="lote.id")
    canal: str = Field(index=True)                     # correo | voz | whatsapp
    proveedor: str = ""                                # resend | ses | dapta | meta | simulado
    estado: str = Field(default="programado", index=True)
    costo_usd: float = 0.0
    duracion_seg: int = 0
    ref_externa: Optional[str] = Field(default=None, index=True)
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
    empresa_id: int = Field(default=EMPRESA_DEMO, index=True)
    lead_id: int = Field(index=True, foreign_key="lead.id")
    intento_id: Optional[int] = Field(default=None, foreign_key="intento.id")
    resultado: str = Field(default="pendiente", index=True)   # pendiente | calificado | no_calificado
    costo_usd: float = 0.0
    ref_externa: Optional[str] = None
    datos: dict = Field(default_factory=dict, sa_column=Column(JSON))
    creado_en: datetime = Field(default_factory=ahora)


class Costo(SQLModel, table=True):
    """Bitácora de costos que no cuelgan de un intento: descarga, Jev, Bedrock, cómputo, número."""

    id: Optional[int] = Field(default=None, primary_key=True)
    empresa_id: int = Field(default=EMPRESA_DEMO, index=True)
    concepto: str
    fuente_clave: str = ""
    canal: str = ""
    usd: float = 0.0
    cantidad: float = 1.0
    creado_en: datetime = Field(default_factory=ahora)


class Exclusion(SQLModel, table=True):
    """Bajas (por empresa) y RNE de la CRC (global, empresa_id 0)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    empresa_id: int = Field(default=0, index=True)
    valor: str = Field(index=True)                     # E.164 o correo en minúsculas
    origen: str = "baja"                               # baja | rne | manual
    creado_en: datetime = Field(default_factory=ahora)


class Bitacora(SQLModel, table=True):
    """Todo lo que explica una decisión: overrides, repartos, errores, webhooks."""

    id: Optional[int] = Field(default=None, primary_key=True)
    empresa_id: int = Field(default=EMPRESA_DEMO, index=True)
    tipo: str = Field(index=True)
    mensaje: str
    datos: dict = Field(default_factory=dict, sa_column=Column(JSON))
    creado_en: datetime = Field(default_factory=ahora)


class Notificacion(SQLModel, table=True):
    """Lo que la empresa quiere saber sin mirar el tablero: respondió, calificó, salió un lote, pidió baja."""

    id: Optional[int] = Field(default=None, primary_key=True)
    empresa_id: int = Field(default=EMPRESA_DEMO, index=True)
    tipo: str = Field(index=True)                      # respondio | calificado | lote | baja | busqueda | error
    mensaje: str
    lead_id: Optional[int] = Field(default=None, index=True)
    leida: bool = Field(default=False, index=True)
    enviada_correo: bool = False
    creado_en: datetime = Field(default_factory=ahora)
