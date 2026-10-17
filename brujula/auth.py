"""Autenticación con Amazon Cognito: login por la página alojada de Cognito (flujo de código), JWT en la API y cookie firmada en el tablero.

Sin COGNITO_* en el entorno, el servidor corre abierto (desarrollo local) y el tablero lo muestra.
"""
from __future__ import annotations

import secrets
import time
from urllib.parse import urlencode

import httpx
import jwt
from itsdangerous import BadSignature, URLSafeTimedSerializer

from .config import config

COOKIE = "brujula_sesion"
DURACION_SESION_SEG = 12 * 3600
PUBLICAS = ("/login", "/callback", "/logout", "/healthz", "/r/", "/webhook/", "/cron/", "/api/docs", "/api/openapi.json", "/api/registro", "/static/", "/app")


def validar_clave(clave: str) -> str | None:
    """La política del User Pool: 12 caracteres o más, con mayúscula, minúscula y número. Devuelve el problema o None."""
    if len(clave) < 12:
        return "la clave debe tener 12 caracteres o más"
    if not any(c.isupper() for c in clave) or not any(c.islower() for c in clave) or not any(c.isdigit() for c in clave):
        return "la clave debe tener mayúscula, minúscula y número"
    return None


class Cognito:
    def __init__(self, pool_id: str = "", client_id: str = "", client_secret: str = "", dominio: str = "", region: str = ""):
        self.pool_id = pool_id or config.cognito_user_pool_id
        self.client_id = client_id or config.cognito_client_id
        self.client_secret = client_secret or config.cognito_client_secret
        self.dominio = (dominio or config.cognito_domain).replace("https://", "").rstrip("/")
        self.region = region or config.aws_region
        self._jwks = None

    @property
    def activo(self) -> bool:
        return bool(self.pool_id and self.client_id and self.dominio)

    @property
    def issuer(self) -> str:
        return f"https://cognito-idp.{self.region}.amazonaws.com/{self.pool_id}"

    def url_login(self, redirect_uri: str, state: str) -> str:
        q = {"client_id": self.client_id, "response_type": "code", "scope": "openid email profile", "redirect_uri": redirect_uri, "state": state}
        return f"https://{self.dominio}/login?{urlencode(q)}"

    def url_logout(self, logout_uri: str) -> str:
        return f"https://{self.dominio}/logout?{urlencode({'client_id': self.client_id, 'logout_uri': logout_uri})}"

    def canjear_codigo(self, code: str, redirect_uri: str) -> dict:
        datos = {"grant_type": "authorization_code", "client_id": self.client_id, "code": code, "redirect_uri": redirect_uri}
        auth = (self.client_id, self.client_secret) if self.client_secret else None
        r = httpx.post(f"https://{self.dominio}/oauth2/token", data=datos, auth=auth, timeout=20,
                       headers={"Content-Type": "application/x-www-form-urlencoded"})
        r.raise_for_status()
        return r.json()

    def verificar(self, token: str) -> dict:
        """Valida firma (JWKS del pool), vencimiento, emisor y cliente. Acepta id_token o access_token."""
        if self._jwks is None:
            self._jwks = jwt.PyJWKClient(f"{self.issuer}/.well-known/jwks.json", cache_keys=True)
        clave = self._jwks.get_signing_key_from_jwt(token)
        claims = jwt.decode(token, clave.key, algorithms=["RS256"], issuer=self.issuer, options={"verify_aud": False})
        uso = claims.get("token_use")
        cliente = claims.get("aud") if uso == "id" else claims.get("client_id")
        if cliente != self.client_id:
            raise jwt.InvalidTokenError("el token no es de este cliente")
        return claims


def _firmador() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config.session_secret, salt="brujula-sesion")


def crear_cookie(claims: dict) -> str:
    emp, rol = _empresa_y_rol(claims)
    return _firmador().dumps({"email": claims.get("email") or claims.get("username") or claims.get("sub"), "sub": claims.get("sub"),
                              "empresa_id": emp, "rol": rol, "t": int(time.time())})


def leer_cookie(valor: str | None) -> dict | None:
    if not valor:
        return None
    try:
        return _firmador().loads(valor, max_age=DURACION_SESION_SEG)
    except BadSignature:
        return None


def firmar_estado(siguiente: str) -> str:
    return _firmador().dumps({"n": siguiente or "/", "r": secrets.token_hex(4)})


def leer_estado(valor: str) -> str:
    try:
        return _firmador().loads(valor, max_age=600).get("n", "/")
    except BadSignature:
        return "/"


def es_publica(ruta: str) -> bool:
    # "/" solo redirige (al front o al login); "/app" es el front Angular, que pide su propio JWT a Cognito.
    return ruta == "/" or any(ruta.startswith(p) for p in PUBLICAS)


def _empresa_y_rol(claims: dict) -> tuple[int, str]:
    try:
        emp = int(claims.get("custom:empresa_id") or claims.get("empresa_id") or 1)
    except (TypeError, ValueError):
        emp = 1
    rol = claims.get("custom:rol") or claims.get("rol") or "usuario"
    return emp, rol


def usuario_desde(request, cognito: Cognito) -> dict | None:
    """Usuario autenticado: Bearer JWT (API) o cookie de sesión (tablero). Modo abierto si Cognito no está configurado.

    Trae empresa_id y rol (admin ve todas las empresas; usuario solo la suya)."""
    if not cognito.activo:
        return {"email": "local", "modo": "abierto", "empresa_id": 1, "rol": "superadmin"}   # en local, quien corre el servidor es la plataforma
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        try:
            c = cognito.verificar(auth[7:].strip())
            emp, rol = _empresa_y_rol(c)
            return {"email": c.get("email") or c.get("username") or c.get("sub"), "sub": c.get("sub"), "modo": "jwt", "empresa_id": emp, "rol": rol}
        except Exception:  # noqa: BLE001
            return None
    sesion = leer_cookie(request.cookies.get(COOKIE))
    if sesion:
        return {"empresa_id": 1, "rol": "usuario", **sesion, "modo": "cookie"}
    return None
