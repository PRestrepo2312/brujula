from brujula import asistente, empresas, perfil
from brujula.icp import ICP


def test_asistente_cuatro_turnos_y_guarda(monkeypatch):
    e = empresas.crear("Clínica Sonrisas", "hola@sonrisas.co", "", ICP().__dict__)
    monkeypatch.setattr(perfil, "buscar_nit", lambda nit: {"nit": nit, "razon_social": "CLINICA SONRISAS SAS", "sigla": "", "ciudad": "BOGOTA", "sector": "salud",
                                                           "ciiu": "8622", "matricula": "20240115", "estado": "ACTIVA", "tipo": "SAS", "representante": "X"})
    monkeypatch.setattr(perfil, "leer_sitio", lambda url: {"url": url, "estado": 200, "titulo": "Clínica Sonrisas", "descripcion": "Odontología en Chapinero", "texto": "…"})
    monkeypatch.setattr(perfil, "sugerir", lambda nombre, rues=None, sitio=None, notas="": (
        {"nombre": nombre, "que_ofrece": "llenamos la agenda con pacientes nuevos" + (" (ajustado)" if notas else ""), "a_quien": "clínicas",
         "diferencial": "", "remitente": f"el equipo de {nombre}", "icp_texto": "Clínicas odontológicas en Bogotá"}, {"motor": "reglas"}))
    r0 = asistente.responder(e.id, "", None)
    assert r0["paso"] == "empresa" and "NIT" in r0["respuesta"]
    r1 = asistente.responder(e.id, "Clínica Sonrisas, NIT 900.123.456", r0)
    assert r1["paso"] == "sitio" and "CLINICA SONRISAS SAS" in r1["respuesta"] and r1["datos"]["nit"] == "900123456"
    r2 = asistente.responder(e.id, "www.sonrisas.co", r1)
    assert r2["paso"] == "propuesta" and "Leí su página" in r2["respuesta"] and "llenamos la agenda" in r2["respuesta"]
    r3 = asistente.responder(e.id, "mejor diga que atendemos por WhatsApp", r2)
    assert r3["paso"] == "propuesta" and "(ajustado)" in r3["respuesta"]
    r4 = asistente.responder(e.id, "así está bien", r3)
    assert r4["paso"] == "pauta" and "pauta" in r4["respuesta"]
    r5 = asistente.responder(e.id, "como 90.000 pesos", r4)
    assert r5["listo"] and r5["guardado"]["costo_lead_pauta_usd"] == 22.5
    p = empresas.perfil_de(e.id)
    assert p["completo"] and p["que_ofrece"].startswith("llenamos la agenda") and p["nit"] == "900123456"
    assert empresas.config_de(e.id)["costo_lead_pauta_usd"] == 22.5
    assert "Bogot" in (empresas.obtener(e.id).icp_texto or "")


def test_montos_en_pauta():
    assert asistente._usd_en("25 dólares") == 25.0 and asistente._usd_en("USD 3,5") == 3.5
    assert asistente._usd_en("80.000 pesos") == 20.0 and asistente._usd_en("120000") == 30.0
    assert asistente._usd_en("no sé") is None
