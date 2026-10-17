"""Descubridor de fuentes: busca en catálogos Socrata datasets con columnas de teléfono o correo."""
from __future__ import annotations

import httpx

CATALOGO = "https://api.us.socrata.com/api/catalog/v1"
PALABRAS_TEL = ("telefono", "teléfono", "celular", "phone", "tel_fono")
PALABRAS_MAIL = ("correo", "email", "e-mail", "mail")


def descubrir(dominio: str = "www.datos.gov.co", palabras: tuple[str, ...] = ("empresas", "establecimientos", "comerciantes", "prestadores", "turismo", "colegios", "proveedores", "directorio"),
              limite_por_palabra: int = 100) -> list[dict]:
    """Devuelve datasets (id, nombre, entidad, tiene_tel, tiene_mail) cuyas columnas sugieren contacto."""
    vistos: dict[str, dict] = {}
    with httpx.Client(timeout=90, headers={"User-Agent": "Brujula/0.1"}) as http:
        for p in palabras:
            r = http.get(CATALOGO, params={"domains": dominio, "q": p, "only": "datasets", "limit": limite_por_palabra})
            if r.status_code != 200:
                continue
            for d in r.json().get("results", []):
                res = d["resource"]
                cols = [c.lower() for c in res.get("columns_name", [])]
                tel = any(x in c for c in cols for x in PALABRAS_TEL)
                mail = any(x in c for c in cols for x in PALABRAS_MAIL)
                if (tel or mail) and res["id"] not in vistos:
                    vistos[res["id"]] = {"id": res["id"], "nombre": res["name"], "entidad": res.get("attribution", ""),
                                         "actualizado": (res.get("updatedAt") or "")[:10], "tiene_tel": tel, "tiene_mail": mail,
                                         "url": f"https://{dominio}/resource/{res['id']}.json", "palabra": p}
    return sorted(vistos.values(), key=lambda x: (not x["tiene_tel"], not x["tiene_mail"], x["nombre"]))
