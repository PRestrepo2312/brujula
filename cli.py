"""Línea de comandos de Brújula.

  python cli.py fuentes                         lista las fuentes
  python cli.py fetch reps --ciudad BOGOTA --limite 200
  python cli.py dedupe                          deduplica toda la base
  python cli.py score [--sin-jev]               puntúa el ICP de los leads pendientes
  python cli.py descubrir [--dominio www.datos.gov.co]
  python cli.py stats                           cifras de la base
  python cli.py lote --n 20 [--override "motivo"]   prepara y envía un lote (la brújula reparte)
  python cli.py sync                            pasa a Dapta los que respondieron y lee las llamadas
  python cli.py simular                         inventa resultados sobre intentos simulados (demo sin credenciales)
  python cli.py metricas                        las tres métricas por fuente y canal
  python cli.py prueba --n 50                   set de 50 empresas con duplicados trampa: precisión de la deduplicación
  python cli.py dapta-setup                     crea el agente de voz y la secuencia en Dapta (guarda data/dapta.json)
  python cli.py rne archivo.csv                 carga números o correos excluidos (RNE de la CRC)
  python cli.py web [--puerto 8000]             tablero y webhooks
"""
from __future__ import annotations

import argparse
import json
import sys

from sqlmodel import func, select

from brujula.db import crear_tablas, sesion
from brujula.models import Lead


def cmd_fuentes(_):
    from brujula.sources import CONECTORES
    for c in CONECTORES.values():
        d = c().describir()
        print(f"{d['clave']:7} {d['pais']:3} {d['tipo']:9} {'contacta' if d['contacta'] else 'solo encontrar':15} {d['nombre']}")


def cmd_fetch(a):
    from brujula.ingest import ingerir
    r = ingerir(a.fuente, ciudad=a.ciudad, sector=a.sector, limite=a.limite)
    print(json.dumps(r, ensure_ascii=False))


def cmd_dedupe(_):
    from brujula.dedupe import deduplicar
    print(json.dumps(deduplicar(), ensure_ascii=False))


def cmd_score(a):
    from brujula.icp import ICP, puntuar
    icp = ICP.cargar(a.icp)
    with sesion() as s:
        q = select(Lead).where(Lead.duplicado_de.is_(None))
        if not a.todos:
            q = q.where(Lead.icp_estado == "pendiente")
        leads = list(s.exec(q.limit(a.limite)))
        r = puntuar(leads, icp, usar_jev=not a.sin_jev)
        for l in leads:
            s.add(l)
        s.commit()
    print(json.dumps({"icp": icp.nombre, "puntuados": len(leads), **r}, ensure_ascii=False))


def cmd_descubrir(a):
    from brujula.sources.discover import descubrir
    res = descubrir(a.dominio)
    print(f"{len(res)} datasets con columnas de contacto en {a.dominio}")
    for d in res[: a.limite]:
        print(f"  {d['id']} | tel={'si' if d['tiene_tel'] else 'no'} mail={'si' if d['tiene_mail'] else 'no'} | {d['nombre'][:70]} | {d['entidad'][:40]}")


def cmd_lote(a):
    from brujula.pipeline import ejecutar_lote, preparar_lote
    reparto = json.loads(a.reparto) if a.reparto else None
    r = preparar_lote(n=a.n, modo=("manual" if reparto else "brujula"), reparto=reparto, usuario=a.usuario, motivo_override=a.override)
    print(json.dumps(r, ensure_ascii=False))
    if "lote_id" in r and not a.solo_preparar:
        print(json.dumps(ejecutar_lote(r["lote_id"]), ensure_ascii=False))


def cmd_sync(_):
    from brujula.pipeline import pasar_a_dapta_los_que_respondieron, sincronizar_dapta
    print(json.dumps({"calificador": pasar_a_dapta_los_que_respondieron(), "dapta": sincronizar_dapta()}, ensure_ascii=False))


def cmd_simular(_):
    from brujula.pipeline import simular_resultados
    print(json.dumps(simular_resultados(), ensure_ascii=False))


def cmd_metricas(_):
    from brujula.metrics import calcular
    print(json.dumps(calcular(), ensure_ascii=False, indent=1))


def cmd_prueba(a):
    from brujula.testset import generar
    print(json.dumps(generar(a.n), ensure_ascii=False))


def cmd_dapta_setup(a):
    from brujula.dapta_setup import configurar
    print(json.dumps(configurar(crear_agente=not a.sin_agente, crear_secuencia=not a.sin_secuencia), ensure_ascii=False, indent=1))


def cmd_rne(a):
    from brujula.compliance import cargar_rne_csv
    print(json.dumps({"excluidos_cargados": cargar_rne_csv(a.archivo)}))


def cmd_web(a):
    import uvicorn
    uvicorn.run("brujula.web.app:app", host="0.0.0.0", port=a.puerto, reload=False)


def cmd_stats(_):
    with sesion() as s:
        total = s.exec(select(func.count(Lead.id))).one()
        principales = s.exec(select(func.count(Lead.id)).where(Lead.duplicado_de.is_(None))).one()
        por_fuente = s.exec(select(Lead.fuente_clave, func.count(Lead.id)).where(Lead.duplicado_de.is_(None)).group_by(Lead.fuente_clave)).all()
        por_estado = s.exec(select(Lead.icp_estado, func.count(Lead.id)).where(Lead.duplicado_de.is_(None)).group_by(Lead.icp_estado)).all()
        con_tel = s.exec(select(func.count(Lead.id)).where(Lead.duplicado_de.is_(None), Lead.telefono.is_not(None))).one()
        con_mail = s.exec(select(func.count(Lead.id)).where(Lead.duplicado_de.is_(None), Lead.correo.is_not(None))).one()
    print(json.dumps({"leads": total, "principales": principales, "duplicados": total - principales, "con_telefono": con_tel,
                      "con_correo": con_mail, "por_fuente": dict(por_fuente), "por_icp": dict(por_estado)}, ensure_ascii=False, indent=1))


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fuentes").set_defaults(f=cmd_fuentes)
    f = sub.add_parser("fetch"); f.add_argument("fuente"); f.add_argument("--ciudad", default=""); f.add_argument("--sector", default=""); f.add_argument("--limite", type=int, default=200); f.set_defaults(f=cmd_fetch)
    sub.add_parser("dedupe").set_defaults(f=cmd_dedupe)
    sc = sub.add_parser("score"); sc.add_argument("--icp", default=None); sc.add_argument("--sin-jev", action="store_true"); sc.add_argument("--todos", action="store_true"); sc.add_argument("--limite", type=int, default=5000); sc.set_defaults(f=cmd_score)
    d = sub.add_parser("descubrir"); d.add_argument("--dominio", default="www.datos.gov.co"); d.add_argument("--limite", type=int, default=40); d.set_defaults(f=cmd_descubrir)
    sub.add_parser("stats").set_defaults(f=cmd_stats)
    lo = sub.add_parser("lote"); lo.add_argument("--n", type=int, default=20); lo.add_argument("--reparto", default=None, help='JSON {"reps|voz": 5, "rnt|correo": 10}'); lo.add_argument("--usuario", default=""); lo.add_argument("--override", default="", help="motivo para contactar fuera de la ventana legal"); lo.add_argument("--solo-preparar", action="store_true"); lo.set_defaults(f=cmd_lote)
    sub.add_parser("sync").set_defaults(f=cmd_sync)
    sub.add_parser("simular").set_defaults(f=cmd_simular)
    sub.add_parser("metricas").set_defaults(f=cmd_metricas)
    pr = sub.add_parser("prueba"); pr.add_argument("--n", type=int, default=50); pr.set_defaults(f=cmd_prueba)
    ds = sub.add_parser("dapta-setup"); ds.add_argument("--sin-agente", action="store_true"); ds.add_argument("--sin-secuencia", action="store_true"); ds.set_defaults(f=cmd_dapta_setup)
    rn = sub.add_parser("rne"); rn.add_argument("archivo"); rn.set_defaults(f=cmd_rne)
    w = sub.add_parser("web"); w.add_argument("--puerto", type=int, default=8000); w.set_defaults(f=cmd_web)
    a = p.parse_args(argv)
    crear_tablas()
    a.f(a)


if __name__ == "__main__":
    main()
