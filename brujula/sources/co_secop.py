"""SECOP II, proveedores registrados (Colombia Compra Eficiente). Solo personas jurídicas; nunca los datos del representante legal."""
from __future__ import annotations

from typing import Iterator

from .base import Conector, Registro, registro_desde
from .datos_gov import Socrata, como_sql, filtro_ciudad

DATASET = "qmzu-gj57"
CONTRATOS = "jbjy-vk9h"


class ConectorSECOP(Conector):
    clave = "secop"
    nombre = "SECOP II, proveedores registrados"
    pais = "CO"
    tipo = "registro"
    licencia = "CC BY-SA 4.0, datos.gov.co, Colombia Compra Eficiente"
    url = f"https://www.datos.gov.co/resource/{DATASET}.json"

    def buscar(self, *, ciudad: str = "", sector: str = "", limite: int = 500) -> Iterator[Registro]:
        # NIT que empieza por 8 o 9 = persona jurídica en Colombia; así no se cuelan personas naturales marcadas "OTRO".
        where = ["pais='CO'", "upper(tipo_empresa) not like '%PERSONA NATURAL%'", "esta_activa='Si'", "nit like '8%' OR nit like '9%'",
                 "correo like '%@%'", "telefono like '3%' OR telefono like '60%' OR telefono like '+57%'"]
        where = [f"({w})" for w in where]
        if ciudad:
            where.append(filtro_ciudad(ciudad, "municipio"))
        if sector:
            where.append(f"upper(descripcion_categoria_principal) like '%{como_sql(sector.upper())}%'")
        api = Socrata()
        for f in api.filas(DATASET, where=" AND ".join(where), order="fecha_creacion DESC", limite=limite):
            senales = {}
            if (f.get("fecha_creacion") or "") >= "2025-01-01":
                senales["registro_reciente_secop"] = {"fecha": f.get("fecha_creacion", "")[:10]}
            r = registro_desde(
                f, nombre=f.get("nombre", ""), identificacion=f.get("nit"),
                sector=f.get("descripcion_categoria_principal", ""), subsector=f.get("tipo_empresa", ""),
                ciudad=f.get("municipio", ""), departamento=f.get("departamento", ""), direccion=f.get("direccion", ""),
                telefonos=(f.get("telefono"),), correos=(f.get("correo"),), sitio_web=f.get("sitio_web"),
                tamano=f.get("tama_o_entidad", ""), senales=senales, fuente_registro=f.get("codigo", ""),
            )
            if r and r.tiene_contacto:
                yield r

    @staticmethod
    def contratos_recientes(nit: str, desde: str = "2026-01-01") -> list[dict]:
        """Señal de compra: contratos adjudicados a ese NIT desde una fecha."""
        api = Socrata()
        where = f"documento_proveedor='{como_sql(nit)}' AND fecha_de_firma >= '{desde}'"
        try:
            return list(api.filas(CONTRATOS, select="id_contrato,nombre_entidad,valor_del_contrato,fecha_de_firma,objeto_del_contrato",
                                  where=where, order="fecha_de_firma DESC", limite=5))
        except Exception:
            return []
