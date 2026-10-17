from fastapi.testclient import TestClient

from brujula import agente, empresas, notificaciones
from brujula.web.app import app


def test_icp_por_reglas_desde_texto():
    icp = agente.interpretar_icp_reglas("Quiero clínicas odontológicas en Bogotá y Medellín con más de 10 empleados que agenden por WhatsApp")
    assert "salud" in icp.sectores and "BOGOTA" in icp.ciudades and "MEDELLIN" in icp.ciudades and icp.empleados_min == 10


def test_clasificacion_de_respuestas_por_reglas():
    assert agente.clasificar_respuesta_reglas("No me vuelvan a escribir, dejen de molestar") == "baja"
    assert agente.clasificar_respuesta_reglas("Sí, me interesa, llámenme mañana") == "interesado"
    assert agente.clasificar_respuesta_reglas("No gracias, ya tenemos") == "no_interesado"
    assert agente.clasificar_respuesta_reglas("Mejor después, en noviembre") == "despues"


def test_empresas_icp_y_notificaciones():
    demo = empresas.asegurar_demo()
    assert demo.id == 1
    e = empresas.crear("Clínica Prueba", "admin@clinica.test", "clínicas en Cali")
    assert e.id != 1 and e.slug.startswith("clinica-prueba")
    icp = agente.interpretar_icp_reglas("colegios privados en Cali")
    empresas.guardar_icp(e.id, icp, "colegios privados en Cali")
    assert empresas.icp_de(e.id).sectores == ["educacion"] and empresas.icp_de(e.id).ciudades == ["CALI"]
    n = notificaciones.notificar(e.id, "busqueda", "prueba")
    assert n.id and notificaciones.listar(e.id, solo_no_leidas=True)[0].mensaje == "prueba"
    assert notificaciones.marcar_leida(e.id) == 1


def test_api_empresa_icp_y_admin():
    c = TestClient(app)
    assert c.get("/api/yo").json()["admin"] is True
    r = c.post("/api/icp/interpretar", json={"texto": "hoteles y agencias de viajes en Cartagena"})
    assert r.status_code == 200 and "turismo" in r.json()["icp"]["sectores"] and r.json()["motor"] in ("reglas", "bedrock")
    assert c.get("/api/icp").json()["icp"]["ciudades"] == ["CARTAGENA"]
    r = c.post("/api/empresas", json={"nombre": "Hotel Demo", "correo_notificaciones": "x@hotel.test", "icp_texto": "hoteles en Santa Marta"})
    assert r.status_code == 200 and r.json()["dapta_api_key"] == ""
    nueva = r.json()["id"]
    assert c.get(f"/api/empresa?empresa={nueva}").json()["nombre"] == "Hotel Demo"
    assert c.get(f"/api/metricas?empresa={nueva}").json()["embudo"]["encontrados"] == 0
    assert c.get("/api/fuentes").status_code == 200 and c.get("/api/notificaciones").status_code == 200
    assert c.get("/api/estado").json()["agente"]["jev"] is False
