from brujula.mensajes import asunto_correo, cuerpo_correo, html_correo, idioma_de, nombre_bonito, whatsapp_texto
from brujula.models import Lead


def _lead(pais: str, fuente: str) -> Lead:
    return Lead(empresa_id=1, razon_social="CLINICA DEL NORTE SAS", pais=pais, fuente_clave=fuente, sector="salud", ciudad="BOGOTA",
                telefono="+573001112233", correo="info@clinica.co")


def test_idioma_por_pais_de_la_fuente():
    assert idioma_de(_lead("CO", "reps")) == "es" and idioma_de(_lead("MX", "denue")) == "es"
    assert idioma_de(_lead("BR", "cnpj")) == "pt" and idioma_de(_lead("US", "nyc")) == "en"


def test_plantillas_en_tres_idiomas():
    for idioma, pedazo, boton in (("es", "Hola, equipo de", "Sí, me interesa"), ("pt", "Olá, equipe da", "Sim, tenho interesse"), ("en", "Hello, Clinica", "Yes, I'm interested")):
        texto, html = cuerpo_correo(_lead("CO", "reps"), "http://a/si", "http://a/no", "http://a/baja", idioma=idioma)
        assert pedazo in texto and boton in texto and "http://a/baja" in texto
        assert boton.replace("'", "&#x27;") in html and "BRÚJULA" in html and "http://a/si" in html
        assert "Clinica del Norte SAS" in asunto_correo(_lead("CO", "reps"), idioma)
    assert "Responda SIM ou NÃO" in whatsapp_texto(_lead("BR", "cnpj"), "pt")
    assert nombre_bonito("HOTEL DE LA MONTAÑA LTDA") == "Hotel de la Montaña LTDA"


def test_mensaje_habla_por_la_empresa_que_usa_brujula():
    perfil = {"nombre": "Clínica Sonrisas", "que_ofrece": "llenamos la agenda de clínicas odontológicas con pacientes nuevos", "remitente": "Ana, de Clínica Sonrisas"}
    texto, html = cuerpo_correo(_lead("CO", "reps"), "http://a/si", "http://a/no", "http://a/baja", perfil=perfil)
    assert "Les escribe Ana, de Clínica Sonrisas: llenamos la agenda" in texto and "Brújula" not in texto
    assert "CLÍNICA SONRISAS" in html and "Clínica Sonrisas." in html
    assert "Aqui é Ana, de Clínica Sonrisas" in whatsapp_texto(_lead("BR", "cnpj"), "pt", perfil=perfil)


def test_html_quita_lineas_con_enlaces():
    h = html_correo("Hola.\n\nTexto.\n\nSí, me interesa: http://a/si\nNo, gracias: http://a/no", "http://a/si", "http://a/no", "http://a/baja", nota="Prueba")
    assert "Texto." in h and "Prueba" in h and h.count("http://a/si") == 1
