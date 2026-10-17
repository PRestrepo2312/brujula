"""Motor y sesiones de base de datos (SQLite por defecto; Postgres si DATABASE_URL lo dice)."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from .config import RAIZ, config

if config.database_url.startswith("sqlite:///"):
    ruta = config.database_url.replace("sqlite:///", "", 1)
    if not Path(ruta).is_absolute():
        ruta = str(RAIZ / ruta)
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{ruta}", connect_args={"check_same_thread": False})
else:
    engine = create_engine(config.database_url, pool_pre_ping=True)


def crear_tablas() -> None:
    from . import models  # noqa: F401  (registra los modelos)

    SQLModel.metadata.create_all(engine)


@contextmanager
def sesion():
    with Session(engine) as s:
        yield s
