import os
import tempfile

# Base de datos temporal para las pruebas, antes de importar brujula.
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "prueba.db")
os.environ["DAPTA_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""
os.environ["RESEND_API_KEY"] = ""
os.environ["TZ"] = "America/Bogota"

import pytest  # noqa: E402

from brujula.db import crear_tablas  # noqa: E402


@pytest.fixture(autouse=True, scope="session")
def _tablas():
    crear_tablas()
