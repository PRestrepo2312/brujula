from sqlmodel import select

from brujula.db import sesion
from brujula.dedupe import deduplicar
from brujula.icp import ICP, puntuar
from brujula.models import Intento, Lead
from brujula.normalize import nombre_normalizado
from brujula.pipeline import ejecutar_lote, preparar_lote, registrar_respuesta_token


def _lead(nombre, **k):
    l = Lead(razon_social=nombre, nombre_norm=nombre_normalizado(nombre), fuente_clave=k.pop("fuente", "reps"), ciudad="BOGOTA", sector="salud", **k)
    l.canales = [c for c, v in (("voz", l.telefono), ("correo", l.correo)) if v]
    return l


def test_dedupe_por_nit_dominio_y_nombre():
    with sesion() as s:
        a = _lead("CLINICA LA SABANA SAS", identificacion="900111222", telefono="+576011111111", correo="info@sabana.com", dominio="sabana.com")
        b = _lead("Clínica La Sabana S.A.S.", identificacion="900111222", fuente="rnt", correo="reservas@sabana.com")       # mismo NIT
        c = _lead("LA SABANA CLINICA", fuente="osm", telefono="+573001112233", sitio_web="https://www.sabana.com", dominio="sabana.com")  # mismo dominio
        d = _lead("CLINICA LA SABANA", fuente="men")   # mismo nombre y ciudad, sin claves fuertes
        e = _lead("COLEGIO ANDINO", identificacion="800999888", correo="x@andino.edu.co", dominio="andino.edu.co")
        for l in (a, b, c, d, e):
            s.add(l)
        s.commit()
        ids = [a.id, b.id, c.id, d.id, e.id]
    r = deduplicar(ids)
    assert r["duplicados"] == 3
    with sesion() as s:
        p = s.get(Lead, ids[0])
        assert p.duplicado_de is None
        assert p.telefono == "+576011111111" and p.correo == "info@sabana.com"
        assert set(p.fuentes_todas) == {"reps", "rnt", "osm", "men"}
        assert "voz" in p.canales and "correo" in p.canales
        assert s.get(Lead, ids[4]).duplicado_de is None


def test_icp_reglas_y_lote_simulado():
    icp = ICP()
    with sesion() as s:
        leads = s.exec(select(Lead).where(Lead.duplicado_de.is_(None))).all()
        puntuar(leads, icp, usar_jev=False)
        for l in leads:
            s.add(l)
        s.commit()
        assert all(l.icp_estado in ("pasa", "revisar", "descarta") for l in leads)
    r = preparar_lote(n=5, modo="brujula", usuario="prueba", motivo_override="prueba automática")
    assert "lote_id" in r and r["intentos"] >= 1
    e = ejecutar_lote(r["lote_id"])
    assert sum(e["resultado"].values()) == r["intentos"]
    with sesion() as s:
        it = s.exec(select(Intento).where(Intento.canal == "correo")).first()
        if it:
            token = it.detalle["token"]
            assert registrar_respuesta_token(token, "si")["valor"] == "si"
            assert s.get(Lead, it.lead_id) is not None
