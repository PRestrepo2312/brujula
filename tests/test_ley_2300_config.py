from brujula import agente, pipeline


def test_empresa_puede_desactivar_horario_legal(monkeypatch):
    """Con respetar_ley_2300 = False el lote no pide motivo fuera de la ventana; con True, sí."""
    monkeypatch.setattr(pipeline, "ventana_permitida", lambda *a, **k: (False, "domingo"))
    base = {"canales": ["voz", "correo"], "presupuesto_lote": 5, "notificar_por": ["app"]}
    monkeypatch.setattr(pipeline, "config_de", lambda emp: {**base, "respetar_ley_2300": True})
    r = pipeline.preparar_lote(n=1, empresa_id=990)
    assert r.get("fuera_ventana") is True and "No se puede contactar" in r["error"]
    monkeypatch.setattr(pipeline, "config_de", lambda emp: {**base, "respetar_ley_2300": False})
    r = pipeline.preparar_lote(n=1, empresa_id=990)
    assert "No se puede contactar" not in r.get("error", "")      # sigue sin leads en esta empresa, pero el horario ya no bloquea


def test_llm_sin_claves_usa_reglas():
    """Sin Bedrock (BEDROCK=0 en las pruebas) ni OpenRouter, el agente de texto cede a las reglas."""
    l = agente.LLM()
    assert l.motor == "reglas" and l.preguntar("sistema", "usuario") == (None, agente.Uso())
    icp, info = agente.interpretar_icp("clínicas odontológicas en Bogotá con más de 10 empleados")
    assert info["motor"] == "reglas" and "salud" in icp.sectores


def test_festivos_de_colombia_de_cualquier_anio():
    """Calendario oficial: 18 festivos, con Ley Emiliani y los que dependen de la Pascua; nunca se contacta en ellos."""
    from datetime import date, datetime
    from zoneinfo import ZoneInfo
    from brujula.compliance import festivos, ventana_permitida
    f = festivos(2026)
    assert len(f) == 18
    assert {date(2026, 4, 2), date(2026, 4, 3), date(2026, 5, 18), date(2026, 6, 8), date(2026, 6, 15), date(2026, 11, 16)} <= f
    assert date(2027, 10, 18) in festivos(2027)                       # 12 de octubre de 2027 cae martes: pasa al lunes 18
    ok, razon = ventana_permitida(datetime(2026, 11, 16, 10, 0, tzinfo=ZoneInfo("America/Bogota")))
    assert not ok and "festivo" in razon
