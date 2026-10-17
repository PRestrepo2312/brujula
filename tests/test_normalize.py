from brujula.normalize import ciudad_normalizada, correo_normalizado, dominio_de, nit_normalizado, nombre_normalizado, telefono_e164, telefonos_co


def test_nombre_normalizado_quita_sufijos_y_tildes():
    assert nombre_normalizado("Clínica La Sabana S.A.S.") == "CLINICA SABANA"
    assert nombre_normalizado("COLEGIO DEL BOSQUE BILINGÜE") == "COLEGIO BOSQUE BILINGUE"
    assert nombre_normalizado("Aviatur S.A.") == nombre_normalizado("AVIATUR SA")


def test_nit_quita_digito_de_verificacion():
    assert nit_normalizado("900123456-7") == "900123456"
    assert nit_normalizado("9001234567") == "900123456"
    assert nit_normalizado("No Provisto") is None


def test_telefonos_colombia_repara_fijos_y_prefiere_celular():
    tels = telefonos_co("5330539-3134241468 EXT 42", departamento="Bogotá D.C.")
    assert tels[0] == ("+573134241468", "celular")
    assert ("+5760" + "15330539", "fijo") in tels
    assert telefono_e164("2329622", "CO", departamento="BOGOTA")[0] == "+576012329622"
    assert telefono_e164("4263111", "CO", departamento="ANTIOQUIA")[0] == "+576044263111"
    assert telefono_e164("No Provisto", "CO") == (None, "")


def test_correo_y_dominio():
    assert correo_normalizado(" Info@Clinica.COM ") == "info@clinica.com"
    assert dominio_de("www.clinica.com") == "clinica.com"
    assert dominio_de(None, "x@gmail.com") is None
    assert dominio_de(None, "x@clinica.com.co") == "clinica.com.co"


def test_ciudad():
    assert ciudad_normalizada("Bogotá, D.C.") == "BOGOTA"
    assert ciudad_normalizada("MEDELLiN") == "MEDELLIN"
