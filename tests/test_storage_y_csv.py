from fastapi.testclient import TestClient

from brujula import storage
from brujula.ingest import ingerir_csv
from brujula.web.app import app


def test_almacen_local_y_exportacion():
    alm = storage.Almacen()
    assert not alm.en_nube
    firma = alm.url_subida("lista.csv")
    assert firma["metodo"] == "POST" and firma["clave"].startswith("subidas/")
    alm.guardar(firma["clave"], b"a,b\n1,2\n", "text/csv")
    assert alm.existe(firma["clave"]) and alm.leer(firma["clave"]).startswith(b"a,b")
    r = storage.exportar("leads")
    assert r["clave"].endswith("_leads.csv") and r["url"].startswith("/api/archivos/local/")


def test_csv_propio_normaliza_y_deduplica():
    csv = ("Empresa;NIT;Teléfono;Correo;Ciudad\n"
           "Clinica Odontologica Sonrisas SAS;900555666-1;3101234567;info@sonrisas.co;Bogotá\n"
           "CLINICA ODONTOLOGICA SONRISAS S.A.S.;;(601) 2345678;;Bogota\n"
           "Sin contacto;;;;Cali\n").encode("utf-8")
    r = ingerir_csv(csv, "lista.csv")
    assert r["fuente"] == "csv" and r["nuevos"] == 2 and r["dedupe"]["duplicados"] == 1


def test_api_archivos_flujo_local():
    c = TestClient(app)
    firma = c.post("/api/archivos/url-subida", json={"nombre": "rne.csv"}).json()
    assert firma["metodo"] == "POST"
    r = c.post("/api/archivos/subir-local", data={"clave": firma["clave"]}, files={"archivo": ("rne.csv", b"numero\n+573009990000\n", "text/csv")})
    assert r.status_code == 200
    r = c.post("/api/archivos/procesar", json={"clave": firma["clave"], "tipo": "rne"})
    assert r.json()["excluidos_cargados"] == 1
    r = c.get("/api/exportar/intentos")
    assert r.status_code == 200 and r.json()["tipo"] == "intentos"
    assert c.get("/api/lotes").status_code == 200 and c.get("/api/icp").status_code == 200
