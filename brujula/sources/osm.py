"""OpenStreetMap vía Overpass (licencia ODbL): negocios con teléfono, WhatsApp, correo o web dentro de una ciudad."""
from __future__ import annotations

from typing import Iterator

import httpx

from .base import Conector, Registro, registro_desde

ESPEJOS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter", "https://overpass.private.coffee/api/interpreter"]
CIUDADES = {  # bbox sur, oeste, norte, este
    "BOGOTA": (4.45, -74.25, 4.85, -73.95),
    "MEDELLIN": (6.15, -75.65, 6.35, -75.50),
    "CALI": (3.33, -76.60, 3.52, -76.45),
    "BARRANQUILLA": (10.90, -74.90, 11.05, -74.75),
    "CARTAGENA": (10.35, -75.55, 10.48, -75.42),
    "BUCARAMANGA": (7.05, -73.17, 7.17, -73.08),
}
ETIQUETAS_SECTOR = {
    "salud": '["healthcare"]', "clinica": '["amenity"~"clinic|dentist|doctors|hospital"]', "educacion": '["amenity"~"school|college|kindergarten|language_school"]',
    "turismo": '["tourism"~"hotel|hostel|guest_house|apartment"]', "restaurante": '["amenity"~"restaurant|cafe"]', "oficina": '["office"]',
    "tienda": '["shop"]', "": '["name"]',
}


class ConectorOSM(Conector):
    clave = "osm"
    nombre = "OpenStreetMap (Overpass)"
    descripcion = "Negocios con teléfono o sitio web en el mapa colaborativo OpenStreetMap; útil para sectores que no están en un registro público."
    ayuda_sector = "Tipo de negocio en inglés (clinic, dentist, hotel, gym…)"
    pais = "CO"
    tipo = "mapa"
    licencia = "ODbL, OpenStreetMap contributors"
    url = "https://overpass-api.de/"

    def buscar(self, *, ciudad: str = "", sector: str = "", limite: int = 500) -> Iterator[Registro]:
        bbox = CIUDADES.get((ciudad or "BOGOTA").upper())
        if not bbox:
            raise SystemExit(f"OSM: ciudad sin bbox configurado: {ciudad}. Disponibles: {', '.join(CIUDADES)}")
        filtro = ETIQUETAS_SECTOR.get(sector.lower(), f'["name"~"{sector}",i]') if sector else '["name"]'
        s, w, n, e = bbox
        q = (f'[out:json][timeout:90];(nwr{filtro}["phone"]({s},{w},{n},{e});nwr{filtro}["contact:phone"]({s},{w},{n},{e});'
             f'nwr{filtro}["contact:whatsapp"]({s},{w},{n},{e}););out tags center {limite};')
        datos = None
        ultimo = ""
        for espejo in ESPEJOS:
            try:
                r = httpx.post(espejo, data={"data": q}, headers={"User-Agent": "Brujula/0.1 (hackathon 30X)"}, timeout=150)
                if r.status_code == 200:
                    datos = r.json()
                    break
                ultimo = f"{espejo}: HTTP {r.status_code}"
            except httpx.HTTPError as ex:
                ultimo = f"{espejo}: {ex}"
                continue
        if not datos:
            print(f"OSM sin datos ({ultimo})", file=__import__('sys').stderr)
            return
        for el in datos.get("elements", []):
            t = el.get("tags", {})
            nombre = t.get("name")
            if not nombre:
                continue
            tel = t.get("phone") or t.get("contact:phone") or t.get("contact:mobile")
            wa = t.get("contact:whatsapp")
            r = registro_desde(
                t, nombre=nombre, sector=t.get("healthcare") or t.get("amenity") or t.get("tourism") or t.get("shop") or t.get("office") or "",
                ciudad=(ciudad or "BOGOTA"), direccion=" ".join(x for x in (t.get("addr:street"), t.get("addr:housenumber")) if x),
                telefonos=(tel, wa), correos=(t.get("email"), t.get("contact:email")), sitio_web=t.get("website") or t.get("contact:website"),
                senales={"osm": {"tipo": el.get("type"), "lat": (el.get("center") or el).get("lat"), "lon": (el.get("center") or el).get("lon")}},
                fuente_registro=f"{el.get('type')}/{el.get('id')}",
            )
            if r and r.tiene_contacto:
                if wa and r.telefono:
                    r.telefono_tipo = "celular"
                yield r
