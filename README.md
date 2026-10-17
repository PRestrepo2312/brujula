# Brújula

**Encuentra empresas en fuentes públicas y gratuitas, las contacta por el canal que tengan, mide cuánto cuesta cada lead y cada lead calificado por fuente y por canal, y reparte el siguiente lote hacia donde sale más barato un buen lead.**

Proyecto del equipo **JFB Devs** para el reto de Dapta en la Hackathon 30X (16 al 18 de octubre de 2026): *"Más leads, menor costo"*.

> 3 de cada 5 leads que llegan a Dapta preguntan si también les ayudan a conseguirlos. Brújula es ese botón.

## Qué hace (y qué es real)

| Paso del reto | Qué hace Brújula | Estado |
|---|---|---|
| **Encontrar** (2+ fuentes gratuitas, sin duplicados) | Conectores a registros públicos de Colombia con teléfono y correo: REPS (IPS privadas), MEN (colegios privados), Registro Nacional de Turismo, SECOP II (proveedores) y OpenStreetMap. Normaliza teléfonos a E.164 (repara fijos de 7 dígitos), correos y nombres; deduplica por NIT, dominio, teléfono y nombre parecido en la misma ciudad. | Funciona con datos reales (API de datos.gov.co y Overpass). |
| **Filtrar por ICP** | Reglas (país, sector, ciudad, canal, tamaño) + Jev (TypeSafe, vía OpenRouter): probabilidad calibrada de que encaje. 0,7 pasa, 0,4 a 0,7 lo revisa una persona en el tablero, menos se descarta. | Reglas: funciona. Jev: funciona con `OPENROUTER_API_KEY`; sin clave, solo reglas. |
| **Contactar** | Primer mensaje por el canal del lead: correo (Resend o Amazon SES, con botones "me interesa / no / baja"), voz (agente de Dapta por secuencia, vía MCP). WhatsApp queda simulado hasta tener línea con plantilla aprobada. | Correo real con clave y dominio verificado; voz real con clave MCP, agente, secuencia y créditos en Dapta. Sin credenciales, ambos corren en **modo simulado** y lo dicen. |
| **Medir** | Tres métricas con su nombre: costo por lead encontrado (por fuente), CPL (por canal, leads que respondieron) y CPLQ (leads que Dapta calificó). Más speed-to-lead. Cada intento guarda su costo real (créditos de Dapta, mensajes, correos, tokens). | Funciona. |
| **Calificar** | Los que responden entran al agente calificador de Dapta (secuencia de voz); el resultado vuelve por webhook y por lectura de llamadas (`find_qualified_leads`, `list_calls`). | Funciona con Dapta configurado. |
| **El extra: reasignar** | La brújula: bandido multibrazo (Thompson sampling) por fuente × canal, recompensa = leads calificados por dólar, con piso de exploración del 15 % y una explicación en una frase. Corre por lote (cada hora con EventBridge). | Funciona. |
| **Cumplimiento** | Ventana de la Ley 2300 (L-V 7 a. m.-7 p. m., sábados 8 a. m.-3 p. m., nunca domingos ni festivos) con override explícito que queda en la bitácora; lista de exclusión (RNE de la CRC y bajas); solo personas jurídicas y canales corporativos; atribución de datos.gov.co. | Funciona. |

El botón **"Simular resultados"** del tablero inventa respuestas y calificaciones sobre intentos simulados. Está para enseñar el tablero sin credenciales y se marca como simulado en los datos: no es evidencia de nada.

## Cómo correrlo

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # Windows; en Linux .venv/bin/pip
cp .env.example .env                                                     # complete las claves que tenga
python cli.py fetch reps --ciudad BOGOTA --limite 200
python cli.py fetch rnt  --ciudad BOGOTA --limite 200
python cli.py fetch men  --ciudad BOGOTA --limite 200
python cli.py score                     # ICP (Jev si hay clave; si no, reglas)
python cli.py lote --n 30               # la brújula reparte y envía (dentro de la ventana legal)
python cli.py sync                      # pasa a Dapta los que respondieron y lee las llamadas
python cli.py metricas
python cli.py web                       # tablero en http://localhost:8000
```

Más comandos: `python cli.py -h` (`prueba` mide la deduplicación con 50 empresas y duplicados trampa; `descubrir` busca datasets con columnas de contacto en catálogos abiertos; `dapta-setup` crea el agente de voz y la secuencia en Dapta; `rne` carga la lista de exclusión).

Pruebas: `pip install -r requirements-dev.txt && python -m pytest`.

## Dapta

Brújula habla con Dapta por su MCP (`https://mcp.dapta.ai/mcp`, cabecera `x-api-key`). `cli.py dapta-setup` crea el agente calificador (propósito 103, voz colombiana, variables post-llamada: interesado, pierde_contactos, mejor_momento, correo_demo, baja) con webhook a `/webhook/dapta`, y la secuencia con el horario de la Ley 2300. Los contactos se adjuntan por `commit_attach_sequence_contacts`; **la secuencia se activa en el panel de Dapta** (el MCP no arranca llamadas). Las llamadas necesitan un plan con créditos (la prueba Pro sirve).

## API y front

El servidor expone la API JSON en `/api/*` (OpenAPI en `/api/docs`) con CORS configurable (`CORS_ORIGINS`): métricas, leads con filtros y paginación, detalle y revisión humana de un lead, creación de lotes, lotes, bitácora, ICP, sincronización con Dapta, archivos y exportaciones. El tablero HTML que sirve el propio servidor usa la misma lógica y es el que se despliega. Un front separado (Angular en S3 + CloudFront) consume esta API sin cambios en el servidor.

## Archivos: S3 con URL prefirmadas

Subidas (lista propia de la pyme en CSV o el RNE de la CRC): `POST /api/archivos/url-subida` devuelve una URL prefirmada de PUT válida 15 minutos y una clave; el navegador sube directo a S3 y luego llama a `POST /api/archivos/procesar` con la clave y el tipo (`leads_csv` o `rne`). Exportaciones (`GET /api/exportar/leads|intentos|bitacora`): el servidor genera el CSV, lo guarda en el bucket y devuelve una URL prefirmada de GET válida 15 minutos. El bucket es privado y las subidas caducan a los 30 días. Sin bucket (`EXPORT_BUCKET` vacío) el mismo flujo corre en disco local, y así corren las pruebas.

## Arquitectura en AWS

`deploy/cloudformation.yml` levanta Lambda con imagen de contenedor y Function URL (HTTPS), PostgreSQL en RDS, Secrets Manager, S3 con CORS para las URL prefirmadas y EventBridge con dos reglas: el siguiente lote cada hora dentro de la ventana legal y la sincronización con Dapta cada 15 minutos. `deploy/deploy.sh` construye la imagen, la sube a ECR y despliega la pila. `deploy/iam-politica-despliegue.json` es la política mínima del usuario que despliega. Detalle y decisiones en `docs/arquitectura.md`.

## Fuentes y licencias

datos.gov.co (CC BY-SA 4.0): REPS `c36g-9fc2`, MEN `cfw5-qzt5`, RNT `thwd-ivmp`, SECOP II proveedores `qmzu-gj57` y contratos `jbjy-vk9h`. OpenStreetMap (ODbL). Otros países, solo encontrar: DENUE del INEGI (México), CNPJ vía BrasilAPI (Brasil), licencias de negocios de Nueva York (EE. UU.). Google Places queda fuera: sus términos no permiten guardar nombre, teléfono ni dirección más de 30 días.

## Límites conocidos

- WhatsApp no envía de verdad: exige línea verificada por Meta y plantilla aprobada.
- La ventana legal se calcula con los festivos de octubre de 2026 a enero de 2027; para producción hay que cargar el calendario completo.
- La consulta al RNE de la CRC es por archivo CSV; el web service de la CRC exige registro de la empresa.
- Un lead es una empresa. Si una fuente trae a una persona natural (SECOP, OSM), se filtra por tipo y por NIT.
