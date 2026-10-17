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

## Modo prueba: demo real sin tocar a terceros

Con `MODO_PRUEBA=1` (valor con el que se despliega) todo el ciclo corre con los leads reales —búsqueda, ICP, lote, pitch con el nombre y las señales de cada empresa, métricas—, pero el contacto se **desvía**: la secuencia de Dapta marca a `TELEFONO_PRUEBA` (una llamada por lote, con las variables de la empresa real) y los correos van a `CORREOS_PRUEBA` (identidades verificadas en SES; en el sandbox SES solo entrega a identidades verificadas, que es exactamente esa lista). El intento guarda `detalle.desvio = {original, destino}` y el cuerpo del correo empieza con "Prueba: este correo iba para …". Un canal sin destino queda `omitido` sin costo (`verificar_lead` lo saca del lote y el canal lo bloquea como segunda barrera); ningún lead recibe nada. `CRON_LOTES=DISABLED` apaga las reglas de EventBridge que lanzan el lote cada hora. La aplicación muestra "MODO PRUEBA → número" en el encabezado; para contactar de verdad se despliega con `MODO_PRUEBA=0`, sin destinos y `CRON_LOTES=ENABLED`.

## Empresas, agente y notificaciones

Brújula es multiempresa: cada cuenta (empresa) tiene su ICP, sus canales, su presupuesto por lote, su Dapta y su correo de notificaciones; leads, lotes, costos, bajas y bitácora están aislados por `empresa_id`. Los usuarios viven en Cognito con los atributos `custom:empresa_id` y `custom:rol` (`admin` ve todas las empresas con `?empresa=ID`; `usuario` solo la suya). La empresa 1 es la de demostración y existe siempre.

El agente reparte el trabajo entre dos modelos y reglas de respaldo:
- **Bedrock (Claude Haiku 5.5)**: lo lento y creativo. Convierte el cliente ideal escrito en español en criterios estructurados (`POST /api/icp/interpretar`), redacta el primer mensaje de cada lead con su señal y explica decisiones en una frase.
- **Jev (TypeSafe, por OpenRouter)**: lo rápido y repetitivo con probabilidad calibrada. Puntúa cada lead contra el ICP y clasifica respuestas libres (interesado, no, después, equivocado, baja).
- Sin Bedrock o sin Jev, mandan las reglas y palabras clave: nada se cae y el resultado dice qué motor se usó.

Notificaciones por empresa (`/api/notificaciones`): búsqueda terminada, lote enviado, lead que respondió, calificado por Dapta, baja; en la app y por correo cuando SES está configurado.

## API y front

El servidor expone la API JSON en `/api/*` (OpenAPI en `/api/docs`) con CORS configurable (`CORS_ORIGINS`): estado y agente, empresa y usuarios, ICP e interpretación, fuentes y búsqueda, leads con filtros y paginación, detalle, revisión humana y vista previa del mensaje, respuestas libres, lotes, bitácora, notificaciones, sincronización con Dapta, archivos y exportaciones. El tablero HTML que sirve el propio servidor (`/tablero`) usa la misma lógica. El front Angular vive en `front/`: el `Dockerfile` lo compila en una primera etapa (`ng build --base-href /app/`) y la misma aplicación lo sirve en `/app/` (la raíz `/` redirige allí), con lo que API y front comparten origen y no hace falta CloudFront ni dominio. El front lee su configuración de `/app/config.json` (la genera el servidor con los ids de Cognito) y entra con un formulario propio en español que habla directo con la API de Cognito por HTTPS (`USER_PASSWORD_AUTH`: la clave nunca pasa por Brújula), con cambio de clave en el primer ingreso y recuperación por código al correo; la página alojada de Cognito (flujo de código con PKCE, callback `/app/callback`) queda como alternativa. Las llamadas a la API llevan el JWT en `Authorization: Bearer`. `deploy/front.yml` y `deploy/front.sh` son la variante en S3 + CloudFront para cuentas con CloudFront habilitado.

## Archivos: S3 con URL prefirmadas

Subidas (lista propia de la pyme en CSV o el RNE de la CRC): `POST /api/archivos/url-subida` devuelve una URL prefirmada de PUT válida 15 minutos y una clave; el navegador sube directo a S3 y luego llama a `POST /api/archivos/procesar` con la clave y el tipo (`leads_csv` o `rne`). Exportaciones (`GET /api/exportar/leads|intentos|bitacora`): el servidor genera el CSV, lo guarda en el bucket y devuelve una URL prefirmada de GET válida 15 minutos. El bucket es privado y las subidas caducan a los 30 días. Sin bucket (`EXPORT_BUCKET` vacío) el mismo flujo corre en disco local, y así corren las pruebas.

## Arquitectura en AWS

`deploy/cloudformation.yml` levanta Lambda con imagen de contenedor y Function URL (HTTPS), PostgreSQL en RDS, Secrets Manager, S3 con CORS para las URL prefirmadas y EventBridge con dos reglas: el siguiente lote cada hora dentro de la ventana legal y la sincronización con Dapta cada 15 minutos. La Function URL pública lleva los dos permisos que Lambda exige desde octubre de 2025 (`lambda:InvokeFunctionUrl` y `lambda:InvokeFunction` limitado a llamadas por la URL). `deploy/deploy.sh` construye la imagen (front incluido), la sube a ECR, despliega la pila, crea la pila de Cognito (`deploy/cognito.yml`) con las URL de retorno del servidor y del front, y vuelve a actualizar la pila principal con los ids de Cognito y la URL pública; `SALTAR_IMAGEN=1 TAG=<etiqueta>` reanuda sin reconstruir. `deploy/iam-politica-despliegue.json` es la política mínima del usuario que despliega. Detalle y decisiones en `docs/arquitectura.md`.

## Fuentes y licencias

datos.gov.co (CC BY-SA 4.0): REPS `c36g-9fc2`, MEN `cfw5-qzt5`, RNT `thwd-ivmp`, SECOP II proveedores `qmzu-gj57` y contratos `jbjy-vk9h`. OpenStreetMap (ODbL). Otros países, solo encontrar: DENUE del INEGI (México), CNPJ vía BrasilAPI (Brasil), licencias de negocios de Nueva York (EE. UU.). Google Places queda fuera: sus términos no permiten guardar nombre, teléfono ni dirección más de 30 días.

## Límites conocidos

- WhatsApp no envía de verdad: exige línea verificada por Meta y plantilla aprobada.
- La ventana legal se calcula con los festivos de octubre de 2026 a enero de 2027; para producción hay que cargar el calendario completo.
- La consulta al RNE de la CRC es por archivo CSV; el web service de la CRC exige registro de la empresa.
- Un lead es una empresa. Si una fuente trae a una persona natural (SECOP, OSM), se filtra por tipo y por NIT.
