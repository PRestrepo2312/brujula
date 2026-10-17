import os
import tempfile

# Base de datos temporal para las pruebas, antes de importar brujula.
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "prueba.db")
os.environ["DAPTA_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""
os.environ["RESEND_API_KEY"] = ""
os.environ["EMAIL_PROVIDER"] = "resend"   # sin clave = correo simulado; las pruebas nunca llaman a SES
os.environ["TZ"] = "America/Bogota"
os.environ["MODO_PRUEBA"] = "0"          # las pruebas no dependen del .env de la máquina
os.environ["TELEFONO_PRUEBA"] = ""
os.environ["CORREOS_PRUEBA"] = ""

import pytest  # noqa: E402

from brujula.db import crear_tablas  # noqa: E402


@pytest.fixture(autouse=True, scope="session")
def _tablas():
    crear_tablas()
