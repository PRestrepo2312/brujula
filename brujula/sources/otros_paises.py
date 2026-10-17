"""Conectores de otros países. Encuentran y normalizan; no se contacta fuera de Colombia en la demo."""
from __future__ import annotations

from typing import Iterator

import httpx

from ..config import config
from .base import Conector, Registro, registro_desde
from .datos_gov import Socrata, como_sql


class ConectorDENUE(Conector):
    """México: DENUE del INEGI. Token gratuito. Busca por palabra y entidad federativa (00 = todas)."""

    clave = "denue"
    nombre = "DENUE (INEGI), México"
    descripcion = "Establecimientos de México del DENUE (INEGI), con teléfono y correo. Solo encontrar: desde Brújula no se contacta fuera de Colombia."
    ayuda_ciudad = "Entidad federativa de México"
    ayuda_sector = "Giro o palabra del negocio (clínica dental, hotel…)"
    pais = "MX"
    tipo = "registro"
    licencia = "Términos de libre uso del INEGI"
    url = "https://www.inegi.org.mx/servicios/api_denue.html"
    contacta = False

    def buscar(self, *, ciudad: str = "", sector: str = "", limite: int = 500) -> Iterator[Registro]:
        if not config.denue_token:
            raise SystemExit("DENUE: falta DENUE_TOKEN en .env (se obtiene gratis en inegi.org.mx).")
        palabra = sector or "todos"
        entidad = ciudad or "00"          # aquí "ciudad" es la clave de entidad federativa (09 = CDMX)
        inicio, paso = 1, 100
        traidos = 0
        with httpx.Client(timeout=90) as http:
            while traidos < limite:
                fin = inicio + paso - 1
                u = f"https://www.inegi.org.mx/app/api/denue/v1/consulta/BuscarEntidad/{palabra}/{entidad}/{inicio}/{fin}/{config.denue_token}"
                r = http.get(u)
                if r.status_code != 200:
                    return
                try:
                    filas = r.json() if r.content else []
                except ValueError:
                    # El INEGI responde 200 con texto plano cuando la clave no sirve: "No autorizado. Utilice una clave válida."
                    raise RuntimeError(f"DENUE: {r.text.strip()[:120]}") from None
                if not filas:
                    return
                for f in filas:
                    reg = registro_desde(
                        f, nombre=f.get("Razon_social") or f.get("Nombre", ""), pais="MX", identificacion=None,
                        sector=f.get("Clase_actividad", ""), ciudad=f.get("Ubicacion", ""), direccion=" ".join(x for x in (f.get("Tipo_vialidad"), f.get("Calle"), f.get("Num_Exterior")) if x),
                        telefonos=(f.get("Telefono"),), correos=(f.get("Correo_e"),), sitio_web=f.get("Sitio_internet"),
                        tamano=f.get("Estrato", ""), fuente_registro=f.get("Id", ""),
                    )
                    if reg and reg.tiene_contacto:
                        yield reg
                        traidos += 1
                        if traidos >= limite:
                            return
                inicio += paso


class ConectorCNPJ(Conector):
    """Brasil: datos abiertos del CNPJ por BrasilAPI (sin clave), a partir de una lista de CNPJ."""

    clave = "cnpj"
    nombre = "CNPJ (Receita Federal) vía BrasilAPI, Brasil"
    descripcion = "Empresas de Brasil por su CNPJ (datos abiertos de la Receita Federal vía BrasilAPI). Solo encontrar. Los CNPJ salen de una consulta por CNAE en Base dos Dados."
    usa_ciudad = False
    ayuda_sector = "CNPJ separados por coma"
    idioma = "pt"
    pais = "BR"
    tipo = "registro"
    licencia = "Datos abiertos de la Receita Federal"
    url = "https://brasilapi.com.br/api/cnpj/v1/"
    contacta = False

    def buscar(self, *, ciudad: str = "", sector: str = "", limite: int = 500) -> Iterator[Registro]:
        # "sector" trae CNPJs separados por coma (de una consulta previa en Base dos Dados / BigQuery).
        cnpjs = [c.strip() for c in sector.split(",") if c.strip()][:limite]
        if not cnpjs:
            raise SystemExit("CNPJ: pegue los CNPJ separados por coma en el campo de la fuente (salen de una consulta por CNAE en Base dos Dados).")
        with httpx.Client(timeout=60, headers={"User-Agent": "Brujula/0.1"}) as http:
            for c in cnpjs:
                r = http.get(self.url + "".join(ch for ch in c if ch.isdigit()))
                if r.status_code != 200:
                    continue
                d = r.json()
                tel = d.get("ddd_telefone_1") or d.get("ddd_telefone_2")
                reg = registro_desde(
                    d, nombre=d.get("nome_fantasia") or d.get("razao_social", ""), pais="BR", identificacion=d.get("cnpj"),
                    sector=d.get("cnae_fiscal_descricao", ""), ciudad=d.get("municipio", ""), departamento=d.get("uf", ""),
                    telefonos=(tel,), correos=(d.get("email"),), tamano=d.get("porte", ""),
                    senales={"inicio_actividad": d.get("data_inicio_atividade")}, fuente_registro=d.get("cnpj", ""),
                )
                if reg and reg.tiene_contacto:
                    yield reg


class ConectorNYC(Conector):
    """EE. UU.: licencias de negocios de la Ciudad de Nueva York (Socrata), con teléfono de contacto."""

    clave = "nyc"
    nombre = "Licencias de negocios, Nueva York"
    descripcion = "Negocios con licencia en la ciudad de Nueva York (NYC Open Data), con teléfono. Solo encontrar."
    ayuda_ciudad = "Borough (Manhattan, Brooklyn, Queens…), opcional"
    ayuda_sector = "Categoría del negocio en inglés (restaurant, laundry…), opcional"
    idioma = "en"
    pais = "US"
    tipo = "registro"
    licencia = "NYC Open Data"
    url = "https://data.cityofnewyork.us/resource/w7w3-xahh.json"
    contacta = False

    def buscar(self, *, ciudad: str = "", sector: str = "", limite: int = 500) -> Iterator[Registro]:
        api = Socrata("data.cityofnewyork.us")
        where = ["license_status='Active'", "contact_phone IS NOT NULL"]
        if sector:
            where.append(f"upper(business_category) like '%{como_sql(sector.upper())}%'")
        if ciudad:
            where.append(f"upper(address_borough) like '%{como_sql(ciudad.upper())}%'")
        for f in api.filas("w7w3-xahh", where=" AND ".join(where), order="license_creation_date DESC", limite=limite):
            reg = registro_desde(
                f, nombre=f.get("business_name", ""), pais="US", sector=f.get("business_category", ""),
                ciudad=f.get("address_borough") or f.get("address_city", ""), departamento="NY",
                direccion=" ".join(x for x in (f.get("address_building"), f.get("address_street_name")) if x),
                telefonos=(f.get("contact_phone"),), fuente_registro=f.get("license_nbr", ""),
            )
            if reg and reg.tiene_contacto:
                yield reg
