"""Configuración desde variables de entorno (.env). Todo lo que cueste dinero tiene su tarifa aquí."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
load_dotenv(RAIZ / ".env")


def _env(nombre: str, defecto: str = "") -> str:
    return os.environ.get(nombre, defecto).strip()


@dataclass(frozen=True)
class Tarifas:
    """USD por unidad. Fuente: docs.dapta.ai (1.000 créditos = USD 1) y listas públicas de Meta, Resend y OpenRouter."""

    voz_minuto_contestado: float = 0.333   # 333 créditos por minuto, redondeado hacia arriba
    voz_no_contesta: float = 0.045          # 45 créditos por intento
    voz_buzon: float = 0.075                # 75 créditos
    voz_numero_mes: float = 28.0            # número colombiano en Dapta (28.000 créditos/mes), se prorratea
    whatsapp_conversacion_co: float = 0.026  # 26 créditos por mensaje de marketing a Colombia (líneas legacy)
    whatsapp_respuesta_agente: float = 0.040  # 40 créditos por respuesta del agente de texto
    correo: float = 0.0001                  # SES; Resend es gratis hasta 3.000/mes
    jev_millon_tokens: float = 0.042        # entrada; salida gratis
    llm_millon_tokens: float = 1.0          # modelo pequeño para redactar el mensaje (estimado)
    computo_hora: float = 0.05              # servidor pequeño


@dataclass(frozen=True)
class Config:
    database_url: str = field(default_factory=lambda: _env("DATABASE_URL", "sqlite:///data/brujula.db"))
    tz: str = field(default_factory=lambda: _env("TZ", "America/Bogota"))
    dapta_api_key: str = field(default_factory=lambda: _env("DAPTA_API_KEY"))
    dapta_mcp_url: str = field(default_factory=lambda: _env("DAPTA_MCP_URL", "https://mcp.dapta.ai/mcp"))
    dapta_agent_id: str = field(default_factory=lambda: _env("DAPTA_AGENT_ID"))
    dapta_sequence_id: str = field(default_factory=lambda: _env("DAPTA_SEQUENCE_ID"))
    openrouter_api_key: str = field(default_factory=lambda: _env("OPENROUTER_API_KEY"))
    jev_model: str = field(default_factory=lambda: _env("JEV_MODEL", "typesafe/jev-1.14"))
    resend_api_key: str = field(default_factory=lambda: _env("RESEND_API_KEY"))
    email_provider: str = field(default_factory=lambda: _env("EMAIL_PROVIDER", "resend"))   # resend | ses
    aws_region: str = field(default_factory=lambda: _env("AWS_REGION", "us-east-1"))
    email_from: str = field(default_factory=lambda: _env("EMAIL_FROM", "Brújula <hola@example.com>"))
    cron_key: str = field(default_factory=lambda: _env("CRON_KEY"))
    export_bucket: str = field(default_factory=lambda: _env("EXPORT_BUCKET"))
    cors_origins: str = field(default_factory=lambda: _env("CORS_ORIGINS", "*"))
    cognito_user_pool_id: str = field(default_factory=lambda: _env("COGNITO_USER_POOL_ID"))
    cognito_client_id: str = field(default_factory=lambda: _env("COGNITO_CLIENT_ID"))
    cognito_client_secret: str = field(default_factory=lambda: _env("COGNITO_CLIENT_SECRET"))
    cognito_domain: str = field(default_factory=lambda: _env("COGNITO_DOMAIN"))           # p. ej. brujula.auth.us-east-1.amazoncognito.com
    session_secret: str = field(default_factory=lambda: _env("SESSION_SECRET") or os.urandom(32).hex())
    public_base_url: str = field(default_factory=lambda: _env("PUBLIC_BASE_URL", "http://localhost:8000"))
    socrata_app_token: str = field(default_factory=lambda: _env("SOCRATA_APP_TOKEN"))
    denue_token: str = field(default_factory=lambda: _env("DENUE_TOKEN"))
    tarifas: Tarifas = field(default_factory=Tarifas)

    @property
    def jev_disponible(self) -> bool:
        return bool(self.openrouter_api_key)

    @property
    def dapta_disponible(self) -> bool:
        return bool(self.dapta_api_key)

    @property
    def correo_real(self) -> bool:
        return bool(self.resend_api_key) if self.email_provider == "resend" else self.email_provider == "ses"


config = Config()
