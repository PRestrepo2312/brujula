"""Archivos: S3 con URL prefirmadas (subidas con PUT, descargas con GET y vencimiento) y modo local sin bucket.

El bucket es privado. El navegador sube directo a S3 con la URL prefirmada; el servidor solo firma y luego procesa la clave.
"""
from __future__ import annotations

import csv
import io
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import select

from .config import RAIZ, config
from .db import sesion
from .models import Bitacora, Intento, Lead

LOCAL = RAIZ / "data" / "archivos"
VENCIMIENTO_SEG = 900


def _nombre_seguro(nombre: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", nombre)[:80] or "archivo"


class Almacen:
    def __init__(self):
        self.bucket = config.export_bucket
        self.s3 = None
        if self.bucket:
            import boto3
            self.s3 = boto3.client("s3", region_name=config.aws_region)

    @property
    def en_nube(self) -> bool:
        return self.s3 is not None

    def clave_subida(self, nombre: str) -> str:
        dia = datetime.now(timezone.utc).strftime("%Y%m%d")
        return f"subidas/{dia}/{uuid.uuid4().hex[:8]}_{_nombre_seguro(nombre)}"

    def url_subida(self, nombre: str, content_type: str = "text/csv") -> dict:
        """URL prefirmada para subir con PUT (15 minutos). Sin bucket, el servidor recibe el archivo en /api/archivos/subir-local."""
        clave = self.clave_subida(nombre)
        if self.en_nube:
            url = self.s3.generate_presigned_url("put_object", Params={"Bucket": self.bucket, "Key": clave, "ContentType": content_type},
                                                 ExpiresIn=VENCIMIENTO_SEG)
            return {"metodo": "PUT", "url": url, "clave": clave, "expira_seg": VENCIMIENTO_SEG, "content_type": content_type}
        return {"metodo": "POST", "url": "/api/archivos/subir-local", "clave": clave, "expira_seg": None, "content_type": content_type}

    def guardar(self, clave: str, datos: bytes, content_type: str = "application/octet-stream") -> str:
        if self.en_nube:
            self.s3.put_object(Bucket=self.bucket, Key=clave, Body=datos, ContentType=content_type)
        else:
            ruta = LOCAL / clave
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_bytes(datos)
        return clave

    def leer(self, clave: str) -> bytes:
        if self.en_nube:
            return self.s3.get_object(Bucket=self.bucket, Key=clave)["Body"].read()
        return (LOCAL / clave).read_bytes()

    def url_descarga(self, clave: str) -> str:
        """URL prefirmada de descarga (15 minutos). Sin bucket, ruta local del servidor."""
        if self.en_nube:
            return self.s3.generate_presigned_url("get_object", Params={"Bucket": self.bucket, "Key": clave}, ExpiresIn=VENCIMIENTO_SEG)
        return f"/api/archivos/local/{clave}"

    def existe(self, clave: str) -> bool:
        if self.en_nube:
            try:
                self.s3.head_object(Bucket=self.bucket, Key=clave)
                return True
            except Exception:  # noqa: BLE001
                return False
        return (LOCAL / clave).exists()


def exportar_leads_csv() -> bytes:
    """Todos los leads principales con su ICP, canales, estado y costo de encontrar."""
    salida = io.StringIO()
    w = csv.writer(salida)
    w.writerow(["id", "pais", "identificacion", "razon_social", "sector", "subsector", "ciudad", "telefono", "telefono_tipo", "correo", "sitio_web",
                "canales", "fuente", "fuentes_todas", "icp_score", "icp_estado", "estado", "costo_encontrar_usd", "senales"])
    with sesion() as s:
        for l in s.exec(select(Lead).where(Lead.duplicado_de.is_(None)).order_by(Lead.id)):
            w.writerow([l.id, l.pais, l.identificacion or "", l.razon_social, l.sector, l.subsector, l.ciudad, l.telefono or "", l.telefono_tipo,
                        l.correo or "", l.sitio_web or "", "|".join(l.canales or []), l.fuente_clave, "|".join(l.fuentes_todas or []),
                        l.icp_score if l.icp_score is not None else "", l.icp_estado, l.estado, l.costo_encontrar_usd, "|".join((l.senales or {}).keys())])
    return salida.getvalue().encode("utf-8-sig")


def exportar_intentos_csv() -> bytes:
    salida = io.StringIO()
    w = csv.writer(salida)
    w.writerow(["id", "lead_id", "lote_id", "canal", "proveedor", "estado", "clasificacion", "costo_usd", "duracion_seg", "fuera_ventana", "enviado_en", "respondido_en", "ref_externa"])
    with sesion() as s:
        for it in s.exec(select(Intento).order_by(Intento.id)):
            w.writerow([it.id, it.lead_id, it.lote_id or "", it.canal, it.proveedor, it.estado, it.clasificacion, it.costo_usd, it.duracion_seg,
                        it.fuera_ventana, it.enviado_en.isoformat() if it.enviado_en else "", it.respondido_en.isoformat() if it.respondido_en else "", it.ref_externa or ""])
    return salida.getvalue().encode("utf-8-sig")


def exportar_bitacora_csv() -> bytes:
    salida = io.StringIO()
    w = csv.writer(salida)
    w.writerow(["id", "creado_en", "tipo", "mensaje", "datos"])
    with sesion() as s:
        for b in s.exec(select(Bitacora).order_by(Bitacora.id)):
            w.writerow([b.id, b.creado_en.isoformat(), b.tipo, b.mensaje, b.datos])
    return salida.getvalue().encode("utf-8-sig")


def exportar(tipo: str) -> dict:
    """Genera el CSV, lo guarda (S3 o local) y devuelve la URL de descarga con vencimiento."""
    generadores = {"leads": exportar_leads_csv, "intentos": exportar_intentos_csv, "bitacora": exportar_bitacora_csv}
    if tipo not in generadores:
        raise ValueError(f"exportación desconocida: {tipo}")
    datos = generadores[tipo]()
    clave = f"exportaciones/{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{tipo}.csv"
    almacen = Almacen()
    almacen.guardar(clave, datos, "text/csv")
    return {"tipo": tipo, "clave": clave, "bytes": len(datos), "url": almacen.url_descarga(clave), "expira_seg": VENCIMIENTO_SEG if almacen.en_nube else None}


def ruta_local(clave: str) -> Path:
    ruta = (LOCAL / clave).resolve()
    if LOCAL.resolve() not in ruta.parents:
        raise ValueError("clave fuera del almacén local")
    return ruta
