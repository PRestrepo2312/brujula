from brujula import asistente, empresas, ingest, perfil, pipeline
from brujula.icp import ICP


def _busqueda_falsa(llamadas):
    def buscar(emp, fuentes, ciudad="", sector="", limite=200, puntuar_icp=True, parametros=None):
        llamadas.append((list(fuentes), ciudad))
        return {"fuentes": [{"fuente": f, "nuevos": 3} for f in fuentes], "icp": {"pasa": 2, "revisar": 1}, "nuevos": 3 * len(fuentes)}
    return buscar


def test_asistente_cuatro_turnos_guarda_y_ofrece_buscar(monkeypatch):
    e = empresas.crear("Clínica Sonrisas", "hola@sonrisas.co", "", ICP().__dict__)
    monkeypatch.setattr(perfil, "buscar_nit", lambda nit: {"nit": nit, "razon_social": "CLINICA SONRISAS SAS", "sigla": "", "ciudad": "BOGOTA", "sector": "salud",
                                                           "ciiu": "8622", "matricula": "20240115", "estado": "ACTIVA", "tipo": "SAS", "representante": "X"})
    monkeypatch.setattr(perfil, "leer_sitio", lambda url: {"url": url, "estado": 200, "titulo": "Clínica Sonrisas", "descripcion": "Odontología en Chapinero", "texto": "…"})
    monkeypatch.setattr(perfil, "sugerir", lambda nombre, rues=None, sitio=None, notas="", **kw: (
        {"nombre": nombre, "que_ofrece": "llenamos la agenda con pacientes nuevos" + (" (ajustado)" if notas else ""), "a_quien": "clínicas",
         "diferencial": "", "remitente": f"el equipo de {nombre}", "icp_texto": "Clínicas odontológicas en Bogotá"}, {"motor": "reglas"}))
    llamadas = []
    monkeypatch.setattr(ingest, "buscar", _busqueda_falsa(llamadas))
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
    assert r5["paso"] == "buscar" and not r5.get("listo") and r5["guardado"]["costo_lead_pauta_usd"] == 22.5 and "REPS" in r5["respuesta"]
    p = empresas.perfil_de(e.id)
    assert p["completo"] and p["que_ofrece"].startswith("llenamos la agenda") and p["nit"] == "900123456"
    assert empresas.config_de(e.id)["costo_lead_pauta_usd"] == 22.5
    assert "Bogot" in (empresas.obtener(e.id).icp_texto or "")
    r6 = asistente.responder(e.id, "sí", r5)   # busca de una vez con el plan propuesto
    assert r6["listo"] and r6["resultado"]["nuevos"] == 3 and llamadas == [(["reps"], "BOGOTA")]
    # Segunda visita: arranca con lo guardado y, sin cambios, vuelve a ofrecer la búsqueda.
    s0 = asistente.responder(e.id, "", None)
    assert s0["paso"] == "propuesta" and "Ya tengo guardado" in s0["respuesta"] and "llenamos la agenda" in s0["respuesta"] and "USD 22.50" in s0["respuesta"]
    s1 = asistente.responder(e.id, "así está bien", s0)
    assert s1["paso"] == "buscar" and "Todo sigue igual" in s1["respuesta"]
    s2 = asistente.responder(e.id, "después", s1)
    assert s2["listo"]


def test_asistente_busqueda_propone_corrige_y_busca(monkeypatch):
    e = empresas.crear("Acme", "a@a.co", "Clínicas odontológicas en Bogotá", ICP(descripcion="Clínicas odontológicas en Bogotá", sectores=["salud"], ciudades=["BOGOTA"]).__dict__)
    llamadas = []
    monkeypatch.setattr(ingest, "buscar", _busqueda_falsa(llamadas))
    r0 = asistente.responder_busqueda(e.id, "", None)
    assert r0["paso"] == "plan" and "REPS" in r0["respuesta"] and "Bogota" in r0["respuesta"] and r0["datos"]["fuentes"] == ["reps"]
    r1 = asistente.responder_busqueda(e.id, "también en Medellín", r0)
    assert r1["datos"]["ciudades"] == ["BOGOTA", "MEDELLIN"]
    r2 = asistente.responder_busqueda(e.id, "reps y men", r1)
    assert r2["datos"]["fuentes"] == ["reps", "men"]
    r3 = asistente.responder_busqueda(e.id, "sí", r2)
    assert r3["listo"] and r3["resultado"]["nuevos"] == 12 and [c for _, c in llamadas] == ["BOGOTA", "MEDELLIN"]
    assert "contacta" in r3["respuesta"] and "70 %" in r3["respuesta"]   # ofrece el lote y dice el umbral
    # "contacta" arma y envía un lote como el botón de Lotes
    monkeypatch.setattr(pipeline, "preparar_lote", lambda **kw: {"lote_id": 9, "reparto": {"reps|correo": 3}, "explicacion": "Reparto inicial.", "intentos": 3, "omitidos": {}, "fuera_ventana": False})
    monkeypatch.setattr(pipeline, "ejecutar_lote", lambda lote_id: {"lote_id": lote_id, "resultado": {"correo:enviado:resend": 3}})
    rc = asistente.responder_busqueda(e.id, "contacta a las que encajan", r3, usuario="prueba@x.co")
    assert rc["listo"] and rc["lote"]["lote_id"] == 9 and "Lote 9" in rc["respuesta"] and "Salud (REPS) + correo 3" in rc["respuesta"]
    monkeypatch.setattr(pipeline, "preparar_lote", lambda **kw: {"error": "No se puede contactar ahora: domingo.", "fuera_ventana": True})
    rf = asistente.responder_busqueda(e.id, "contacta", rc)
    assert "No se puede contactar ahora" in rf["respuesta"] and "contacto automático" in rf["respuesta"]
    r4 = asistente.responder_busqueda(e.id, "fuentes", r3)
    assert "SECOP" in r4["respuesta"] and r4["paso"] == "plan"
    r5 = asistente.responder_busqueda(e.id, "mejor hoteles y agencias de viajes en Cartagena", r4)   # otro cliente ideal: fuentes nuevas
    assert "rnt" in r5["datos"]["fuentes"] and "reps" not in r5["datos"]["fuentes"] and r5["datos"]["ciudades"] == ["CARTAGENA"] and "Registro Nacional de Turismo" in r5["respuesta"]
    r6 = asistente.responder_busqueda(e.id, "todas las fuentes de colombia.", r5)
    assert r6["datos"]["fuentes"] == ["reps", "men", "rnt", "secop", "rues"] and r6["paso"] == "plan"
    r7 = asistente.responder_busqueda(e.id, "solo empresas de servicios con más de 1000 empleados", r6)   # sector sin fuente propia: explica por qué solo SECOP
    assert r7["datos"]["fuentes"] == ["secop"] and "única fuente pública" in r7["respuesta"] and "empleados" in r7["respuesta"]


def test_nombre_comercial_sin_forma_juridica():
    assert perfil.nombre_comercial("PANEL ROCK COLOMBIA S A S") == "Panel Rock Colombia"
    assert perfil.nombre_comercial("CLINICA SONRISAS SAS") == "Clinica Sonrisas"
    assert perfil.nombre_comercial("INVERSIONES DE LA ROSA Y CIA LTDA") == "Inversiones de la Rosa"
    assert perfil.nombre_comercial("Gi Group Colombia S.A.S.") == "Gi Group Colombia"
    assert perfil.nombre_comercial("", "ACME") == "Acme"


def test_asistente_nit_solo_toma_nombre_del_rues_y_cambia_de_empresa(monkeypatch):
    e = empresas.crear("JFB Devs (demostración)", "x@x.co", "", ICP().__dict__)
    monkeypatch.setattr(perfil, "buscar_nit", lambda nit: {"nit": nit, "razon_social": "PANEL ROCK COLOMBIA S A S", "sigla": "", "ciudad": "BOGOTA", "sector": "construccion",
                                                           "ciiu": "4111", "matricula": "20020201", "estado": "ACTIVA", "tipo": "SAS", "representante": "X"})
    monkeypatch.setattr(perfil, "leer_sitio", lambda url: {"error": "x"})
    monkeypatch.setattr(perfil, "sugerir", lambda nombre, rues=None, sitio=None, notas="", **kw: (
        {"nombre": nombre, "que_ofrece": "paneles", "a_quien": "constructoras", "diferencial": "", "remitente": f"el equipo de {nombre}", "icp_texto": "Constructoras en Bogotá"}, {"motor": "reglas"}))
    r1 = asistente.responder(e.id, "830097622-9", {"paso": "empresa"})
    assert r1["datos"]["nombre"] == "Panel Rock Colombia" and r1["datos"]["nit"] == "8300976229" and "Panel Rock Colombia" in r1["respuesta"]
    r2 = asistente.responder(e.id, "no tengo", r1)
    assert r2["paso"] == "propuesta" and "el equipo de Panel Rock Colombia" in r2["respuesta"] and "Así empezaría el correo" in r2["respuesta"]
    r3 = asistente.responder(e.id, "Otra Marca, NIT 900.111.222", r2)   # otro NIT en plena propuesta: otra empresa
    assert r3["paso"] == "sitio" and r3["datos"]["nombre"] == "Otra Marca" and r3["datos"]["nit"] == "900111222"
    r4 = asistente.responder(e.id, "empezar de nuevo", r3)
    assert r4["paso"] == "empresa" and not r4["datos"]
    assert asistente._url_en("NIT 900.123.456") == "" and asistente._url_en("panelrockcolombia.com") == "panelrockcolombia.com"


def test_asistente_pide_cliente_ideal_si_falta(monkeypatch):
    e = empresas.crear("Acme", "a@a.co", "", ICP().__dict__)
    monkeypatch.setattr(perfil, "buscar_nit", lambda nit: None)
    monkeypatch.setattr(perfil, "leer_sitio", lambda url: {"error": "x"})
    monkeypatch.setattr(perfil, "sugerir", lambda nombre, rues=None, sitio=None, notas="", **kw: (
        {"nombre": nombre, "que_ofrece": "x", "a_quien": "", "diferencial": "", "remitente": "el equipo de Acme", "icp_texto": ""}, {"motor": "reglas"}))
    r1 = asistente.responder(e.id, "Acme", {"paso": "empresa"})
    r2 = asistente.responder(e.id, "no tengo", r1)
    r3 = asistente.responder(e.id, "así está bien", r2)
    assert r3["paso"] == "propuesta" and "cliente ideal" in r3["respuesta"]
    r4 = asistente.responder(e.id, "Constructoras medianas en Bogotá y Medellín", r3)
    assert r4["paso"] == "propuesta" and "Constructoras medianas" in r4["respuesta"]
    r5 = asistente.responder(e.id, "sí, pero quite el diferencial", r4)   # un "sí" con reparos no es aceptar
    assert r5["paso"] == "propuesta"
    r6 = asistente.responder(e.id, "así está bien", r5)
    assert r6["paso"] == "pauta"


def test_montos_en_pauta():
    assert asistente._usd_en("25 dólares") == 25.0 and asistente._usd_en("USD 3,5") == 3.5
    assert asistente._usd_en("80.000 pesos") == 20.0 and asistente._usd_en("120000") == 30.0
    assert asistente._usd_en("no sé") is None
