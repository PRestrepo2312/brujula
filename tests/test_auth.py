from fastapi.testclient import TestClient

from brujula import auth
from brujula.web.app import app


def test_modo_abierto_sin_cognito():
    c = TestClient(app)
    yo = c.get("/api/yo").json()
    assert yo["login_activo"] is False and yo["admin"] is True and yo["usuario"]["modo"] == "abierto" and yo["empresa_id"] == 1
    assert c.get("/login", follow_redirects=False).status_code == 303


def test_urls_y_cookies_de_cognito():
    cg = auth.Cognito(pool_id="us-east-1_abc", client_id="cli123", dominio="https://brujula.auth.us-east-1.amazoncognito.com/", region="us-east-1")
    assert cg.activo
    u = cg.url_login("https://x.awsapprunner.com/callback", "estado")
    assert u.startswith("https://brujula.auth.us-east-1.amazoncognito.com/login?") and "client_id=cli123" in u and "response_type=code" in u
    assert cg.issuer == "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_abc"
    galleta = auth.crear_cookie({"email": "persona@correo.com", "sub": "1"})
    assert auth.leer_cookie(galleta)["email"] == "persona@correo.com"
    assert auth.leer_cookie("manipulada") is None
    assert auth.leer_estado(auth.firmar_estado("/leads")) == "/leads"
    assert auth.es_publica("/r/abc") and auth.es_publica("/webhook/dapta") and not auth.es_publica("/api/leads") and not auth.es_publica("/tablero")
    assert auth.es_publica("/") and auth.es_publica("/app/leads/5")   # la raíz solo redirige; el front Angular trae su propio JWT


def test_validar_clave_politica_del_pool():
    assert auth.validar_clave("Corta1A") and auth.validar_clave("todominusculas12") and auth.validar_clave("SINNUMEROSAQUIAA")
    assert auth.validar_clave("ClaveSegura2026") is None
