"""Normalización: teléfonos a E.164, correos, dominios, NIT y nombres de empresa comparables."""
from __future__ import annotations

import re
import unicodedata
from typing import Optional
from urllib.parse import urlparse

import phonenumbers

DOMINIOS_GENERICOS = {
    "gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "yahoo.es", "live.com", "icloud.com",
    "hotmail.es", "outlook.es", "msn.com", "aol.com", "protonmail.com", "une.net.co", "etb.net.co",
}
SUFIJOS_LEGALES = [
    r"\bS\.?A\.?S\.?\b", r"\bS\.?A\.?\b", r"\bLTDA\.?\b", r"\bLIMITADA\b", r"\bE\.?U\.?\b", r"\bS\.?C\.?A\.?\b",
    r"\bS\.? EN C\.?\b", r"\bZOMAC\b", r"\bBIC\b", r"\bC\.?I\.?A\.?\b", r"\bY CIA\b", r"\b&\s*CIA\b", r"\bINC\.?\b",
    r"\bLLC\b", r"\bS\.? DE R\.?L\.?\b", r"\bDE C\.?V\.?\b", r"\bLTDA\b", r"\bEIRELI\b", r"\bME\b", r"\bEPP\b",
    r"\bSOCIEDAD POR ACCIONES SIMPLIFICADA\b", r"\bSOCIEDAD ANONIMA\b", r"\bENTIDAD SIN ANIMO DE LUCRO\b",
    r"\bE\.?S\.?P\.?\b", r"\bI\.?P\.?S\.?\b", r"\bIPS\b", r"\bEPS\b",
]
PALABRAS_VACIAS = {"DE", "DEL", "LA", "LAS", "EL", "LOS", "Y", "E", "EN", "CON", "PARA", "POR", "THE", "AND", "OF"}
VALORES_NULOS = {"", "NO PROVISTO", "NO DEFINIDO", "N/A", "NA", "NULL", "NONE", "SIN DATO", "SIN DATOS", "0", "-", "NO APLICA", "NO REGISTRA"}


def sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def limpio(valor) -> str:
    if valor is None:
        return ""
    s = str(valor).strip()
    return "" if s.upper() in VALORES_NULOS else s


def nombre_normalizado(nombre: str) -> str:
    """Mayúsculas, sin tildes, sin sufijos legales ni puntuación. Para comparar, no para mostrar."""
    s = sin_tildes(limpio(nombre)).upper()
    s = s.replace("&", " Y ")
    for suf in SUFIJOS_LEGALES:
        s = re.sub(suf, " ", s)
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    palabras = [p for p in s.split() if p not in PALABRAS_VACIAS]
    return " ".join(palabras)


def nit_normalizado(valor) -> Optional[str]:
    """Deja solo dígitos y quita el dígito de verificación cuando viene pegado (NIT colombiano de 10 dígitos)."""
    s = re.sub(r"\D", "", limpio(valor))
    if not s:
        return None
    if len(s) == 10 and s[0] in "89":   # NIT de persona jurídica (9) + DV
        s = s[:9]
    if len(s) < 6:
        return None
    return s


# Indicativo de fijo en Colombia (numeración 2021: 60 + indicativo + 7 dígitos) por departamento.
INDICATIVO_CO = {
    "1": ["BOGOTA", "DISTRITO CAPITAL", "CUNDINAMARCA"],
    "2": ["VALLE DEL CAUCA", "VALLE", "CAUCA", "NARINO"],
    "4": ["ANTIOQUIA", "CHOCO", "CORDOBA"],
    "5": ["ATLANTICO", "BOLIVAR", "MAGDALENA", "CESAR", "LA GUAJIRA", "GUAJIRA", "SUCRE", "SAN ANDRES"],
    "6": ["CALDAS", "RISARALDA", "QUINDIO"],
    "7": ["SANTANDER", "NORTE DE SANTANDER", "ARAUCA"],
    "8": ["BOYACA", "TOLIMA", "HUILA", "META", "CAQUETA", "CASANARE", "AMAZONAS", "GUAVIARE", "GUAINIA", "VAUPES", "VICHADA", "PUTUMAYO"],
}


def _indicativo(departamento: str, ciudad: str) -> Optional[str]:
    zona = f"{sin_tildes(departamento)} {sin_tildes(ciudad)}".upper()
    if "BOGOT" in zona:
        return "1"
    for ind, nombres in INDICATIVO_CO.items():
        if any(n in zona for n in nombres):
            return ind
    return None


def telefonos_co(valor, departamento: str = "", ciudad: str = "") -> list[tuple[str, str]]:
    """Todos los números colombianos válidos dentro de un texto ('5330539-3134241468 EXT 42'), celulares primero.

    Repara fijos antiguos de 7 dígitos con el indicativo del departamento (Bogotá 601, Antioquia 604, Valle 602…).
    """
    s = limpio(valor)
    if not s:
        return []
    s = re.sub(r"(?i)\b(ext|extension|extensión|opc|opcion|opción)\b.*$", "", s)   # corta extensiones
    grupos = re.findall(r"\d{7,}", re.sub(r"[^\d;/,|\-\s()+]", " ", s))
    vistos: list[tuple[str, str]] = []
    ind = _indicativo(departamento, ciudad)
    for g in grupos:
        d = g
        if d.startswith("0057") or d.startswith("57") and len(d) in (12, 13):
            d = d[-10:]
        if len(d) == 7 and ind:
            d = "60" + ind + d
        elif len(d) == 8 and d[0] in "12345678" and ind is None:
            d = "60" + d
        elif len(d) == 8 and d[0] in "12345678":
            d = "60" + d
        if len(d) != 10:
            continue
        if d[0] == "3":
            tipo = "celular"
        elif d.startswith("60"):
            tipo = "fijo"
        else:
            continue
        try:
            n = phonenumbers.parse("+57" + d, "CO")
        except phonenumbers.NumberParseException:
            continue
        if not phonenumbers.is_valid_number(n):
            continue
        e = phonenumbers.format_number(n, phonenumbers.PhoneNumberFormat.E164)
        if e not in [v[0] for v in vistos]:
            vistos.append((e, tipo))
    vistos.sort(key=lambda x: 0 if x[1] == "celular" else 1)
    return vistos


def telefono_e164(valor, pais: str = "CO", departamento: str = "", ciudad: str = "") -> tuple[Optional[str], str]:
    """Devuelve (E.164, tipo). tipo: celular | fijo | ''. Prefiere el celular si hay varios."""
    s = limpio(valor)
    if not s:
        return None, ""
    if pais == "CO":
        tels = telefonos_co(s, departamento, ciudad)
        return tels[0] if tels else (None, "")
    candidatos = re.split(r"[;/,|]|\s{2,}| - ", s)
    for c in candidatos:
        c = c.strip()
        if not c:
            continue
        try:
            n = phonenumbers.parse(c, pais)
        except phonenumbers.NumberParseException:
            continue
        if not phonenumbers.is_valid_number(n):
            continue
        tipo_num = phonenumbers.number_type(n)
        tipo = "celular" if tipo_num in (phonenumbers.PhoneNumberType.MOBILE, phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE) else "fijo"
        return phonenumbers.format_number(n, phonenumbers.PhoneNumberFormat.E164), tipo
    return None, ""


def correo_normalizado(valor) -> Optional[str]:
    s = limpio(valor).lower()
    m = re.search(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", s)
    return m.group(0) if m else None


def dominio_de(sitio_web=None, correo=None) -> Optional[str]:
    """Dominio propio de la empresa. Ignora dominios de correo genéricos."""
    web = limpio(sitio_web)
    if web:
        if not re.match(r"^https?://", web, re.I):
            web = "http://" + web
        host = (urlparse(web).hostname or "").lower()
        host = re.sub(r"^www\.", "", host)
        if host and "." in host:
            return host
    mail = correo_normalizado(correo)
    if mail:
        dom = mail.split("@", 1)[1]
        if dom not in DOMINIOS_GENERICOS:
            return dom
    return None


def ciudad_normalizada(valor) -> str:
    s = sin_tildes(limpio(valor)).upper()
    s = re.sub(r"[^A-Z ]+", " ", s)
    s = re.sub(r"\b(D\s*C|DISTRITO CAPITAL)\b", "", s)
    return " ".join(s.split())
