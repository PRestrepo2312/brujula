"""Interfaz de un conector de fuente y el registro normalizado que entrega."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Optional

from ..normalize import (ciudad_normalizada, correo_normalizado, dominio_de, limpio, nit_normalizado,
                         nombre_normalizado, telefono_e164)


@dataclass
class Registro:
    """Una empresa tal como la entrega una fuente, ya normalizada."""

    razon_social: str
    pais: str = "CO"
    identificacion: Optional[str] = None
    sector: str = ""
    subsector: str = ""
    ciudad: str = ""
    departamento: str = ""
    direccion: str = ""
    telefono: Optional[str] = None
    telefono_tipo: str = ""
    correo: Optional[str] = None
    sitio_web: Optional[str] = None
    tamano: str = ""
    empleados: Optional[int] = None
    senales: dict = field(default_factory=dict)
    fuente_registro: str = ""
    crudo: dict = field(default_factory=dict)

    @property
    def dominio(self) -> Optional[str]:
        return dominio_de(self.sitio_web, self.correo)

    @property
    def nombre_norm(self) -> str:
        return nombre_normalizado(self.razon_social)

    @property
    def canales(self) -> list[str]:
        c = []
        if self.telefono:
            c.append("voz")
            if self.telefono_tipo == "celular":
                c.append("whatsapp")
        if self.correo:
            c.append("correo")
        return c

    @property
    def tiene_contacto(self) -> bool:
        return bool(self.telefono or self.correo)


def registro_desde(fila: dict, *, nombre: str, pais: str = "CO", identificacion=None, sector="", subsector="", ciudad="",
                   departamento="", direccion="", telefonos=(), correos=(), sitio_web=None, tamano="", empleados=None,
                   senales=None, fuente_registro="") -> Optional[Registro]:
    """Arma un Registro a partir de los valores crudos. Devuelve None si no hay nombre."""
    nombre = limpio(nombre)
    if not nombre:
        return None
    # Todos los números válidos de todos los campos; el celular manda (sirve para voz y WhatsApp).
    encontrados: list[tuple[str, str]] = []
    for t in telefonos:
        e, tipo_t = telefono_e164(t, pais, departamento=limpio(departamento), ciudad=limpio(ciudad))
        if e and e not in [x[0] for x in encontrados]:
            encontrados.append((e, tipo_t))
    encontrados.sort(key=lambda x: 0 if x[1] == "celular" else 1)
    tel, tipo = encontrados[0] if encontrados else (None, "")
    correo = None
    for c in correos:
        correo = correo_normalizado(c)
        if correo:
            break
    emp = None
    try:
        emp = int(float(empleados)) if empleados not in (None, "") else None
    except (TypeError, ValueError):
        emp = None
    return Registro(
        razon_social=nombre, pais=pais, identificacion=nit_normalizado(identificacion) if pais == "CO" else (limpio(identificacion) or None),
        sector=limpio(sector), subsector=limpio(subsector), ciudad=ciudad_normalizada(ciudad), departamento=ciudad_normalizada(departamento),
        direccion=limpio(direccion), telefono=tel, telefono_tipo=tipo, correo=correo, sitio_web=limpio(sitio_web) or None,
        tamano=limpio(tamano).lower(), empleados=emp, senales=senales or {}, fuente_registro=str(fuente_registro), crudo=fila,
    )


class Conector:
    """Una fuente. Subclases definen clave, nombre, pais, tipo, licencia, url y buscar()."""

    clave = ""
    nombre = ""
    pais = "CO"
    tipo = "registro"           # registro | mapa | web | catalogo
    licencia = ""
    url = ""
    contacta = True             # False: solo encontrar (otros países)
    costo_fijo_usd = 0.0        # p. ej. un token o una cuota mensual prorrateada
    # Para la pantalla de búsqueda: qué es la fuente y qué significan "ciudad" y "sector" en ella.
    descripcion = ""
    usa_ciudad = True
    usa_sector = True
    ayuda_ciudad = "Ciudad de Colombia"
    ayuda_sector = "Palabra del sector (opcional)"
    idioma = "es"               # idioma por defecto de los mensajes a los leads de esta fuente

    def buscar(self, *, ciudad: str = "", sector: str = "", limite: int = 500) -> Iterator[Registro]:
        raise NotImplementedError

    def describir(self) -> dict:
        return {"clave": self.clave, "nombre": self.nombre, "pais": self.pais, "tipo": self.tipo, "licencia": self.licencia,
                "url": self.url, "contacta": self.contacta, "descripcion": self.descripcion, "usa_ciudad": self.usa_ciudad,
                "usa_sector": self.usa_sector, "ayuda_ciudad": self.ayuda_ciudad, "ayuda_sector": self.ayuda_sector, "idioma": self.idioma}
