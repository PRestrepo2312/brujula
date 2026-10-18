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
| **Cumplimiento** | Ventana de la Ley 2300 (L-V 7 a. m.-7 p. m., sábados 8 a. m.-3 p. m., nunca domingos ni festivos) con override explícito por lote que queda en la bitácora; cada empresa puede desactivar el horario en Configuración bajo su responsabilidad (`respetar_ley_2300`, con constancia de quién lo cambió, y la secuencia de Dapta pasa a horario sin límite); lista de exclusión (RNE de la CRC y bajas); solo personas jurídicas y canales corporativos; atribución de datos.gov.co. | Funciona. |

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

El override de horario por usuario (Ley 2300) también abre el horario de la secuencia de Dapta: al enviar un lote con override que lleve llamadas, `ejecutar_lote` amplía el día de hoy en la secuencia (06:00 AM a 11:59 PM, hora Bogotá) y lo anota en la bitácora (`override_dapta`, con usuario, motivo y hora de vencimiento); dos horas después, la sincronización restaura el horario legal (`override_dapta_cierre`).

## WhatsApp

La línea de WhatsApp Business (Meta) está conectada a Dapta y asignada al agente de texto "Brújula · chat" (`DAPTA_TEXT_AGENT_ID`), que atiende en español con el mismo guion de calificación que el de voz. Lo **entrante es real**: `pipeline.sincronizar_chats` (cada 15 minutos, en "Sincronizar con Dapta" y tras el webhook post-conversación) lee las conversaciones del agente, las liga al lead por teléfono cuando Dapta deja ver los dígitos del identificador y, si no, a un lead "WhatsApp entrante", clasifica lo que escribió la persona (interesado, después, no interesado, baja) y guarda el costo en créditos. El **primer mensaje saliente** por WhatsApp exige una plantilla aprobada por Meta en esa línea; mientras no exista, el canal lo simula y lo dice.

## Cómo se presenta cada empresa y el asistente de inicio

Los mensajes hablan en nombre de la empresa que usa Brújula, no de Brújula: cada empresa tiene un perfil comercial (`config.perfil`: nombre con el que se presenta, qué ofrece, a quién, qué la distingue, quién firma, NIT, página) y con él se arman el correo, el WhatsApp y las variables de la llamada de Dapta (`{{remitente}}`, `{{propuesta}}`). La empresa de demostración habla como Brújula. El perfil se llena conversando con el **asistente de inicio** (`/app/inicio`, `POST /api/asistente`): en cuatro turnos pide nombre y NIT (lo busca en el RUES de datos.gov.co), la página web (la lee: título, descripción y texto), propone cómo presentarse y el cliente ideal (con el agente de texto, o con reglas si no hay agente), acepta correcciones y pregunta cuánto le cuesta hoy un lead por pauta; al final guarda perfil, cliente ideal y costo de pauta. Lo mismo se puede hacer con botones en Configuración y, opcionalmente, el NIT en el registro.

**Buscar también es un chat** (`/app/buscar`, `POST /api/asistente/buscar`). La brújula lee el cliente ideal y propone en qué fuentes públicas buscar (REPS para salud, MEN para educación, RNT para turismo, SECOP para el resto) y en qué ciudades; la persona corrige conversando ("también en Medellín", "reps y men", "clínicas dentales en Cali", "fuentes" para ver todas) y confirma con "sí". Un cliente ideal nuevo escrito ahí se interpreta con el agente y se guarda. El modo manual (marcar fuentes, parámetros por fuente, cargar CSV o exclusiones) sigue en `/app/buscar/manual`. El asistente de inicio, al terminar, ofrece buscar de una vez con ese mismo plan.

**Encaje y calor.** Son dos cosas distintas. El encaje (0 a 100 %) mide cuánto se parece el lead al cliente ideal con lo que ya se sabe de él (sector, ciudad, tamaño y señales como página, teléfono o correo); Brújula contacta primero a los que encajan. Lo "caliente" no se adivina: sale de lo que hizo el lead después de contactarlo (contactado, respondió, calificado por el agente de Dapta con sus variables). En Leads se ordena por mejor encaje, más calientes o últimos agregados. La búsqueda la lanza la persona desde Buscar (o cargando un CSV); el contacto por lotes sí puede programarse dentro del horario legal, y las respuestas de Dapta llegan por webhook y por una sincronización cada 15 minutos.

El tablero muestra con eso dos cosas que el reto pide: el **porcentaje de calificados por canal** y un **cuadrante costo contra calidad** (costo por respuesta contra % de calificados, una burbuja por fuente y canal con su volumen), y **Brújula contra pauta**: el costo por lead que la empresa escribió frente al costo por lead calificado medido, con el factor de ahorro. En el detalle de cada lead se ve el agente de Dapta trabajando: resumen, variables extraídas, transcripción y grabación de la llamada (la sincronización las trae de `get_call`).

## Idiomas de los mensajes

Cada fuente tiene un idioma por defecto según su país (Colombia y México en español, Brasil en portugués, Nueva York en inglés) y la empresa puede fijar otro por fuente en Configuración (`config.idiomas`). Las plantillas de correo y WhatsApp existen en los tres idiomas (`brujula/mensajes.py`: textos, señales y botones); con agente de texto, él redacta directamente en el idioma del lead. En el detalle de cada lead se previsualiza el mensaje en el idioma de la fuente o en otro (`GET /api/lead/{id}/mensaje?idioma=pt`). Los correos del sistema (clave temporal, código de recuperación) salen de Cognito con la misma marca, en español (`deploy/cognito.yml`).

## Empresas, usuarios y roles

Cada empresa es un espacio aparte (`empresa_id` en leads, lotes, intentos, calificaciones, costos, bitácora y notificaciones): sus usuarios solo ven lo suyo. Tres roles en Cognito (`custom:rol`): **usuario** trabaja con los leads de su empresa; **admin** además configura la empresa (ICP, canales, Dapta, horario) y agrega personas a su empresa (`POST /api/usuarios`, siempre dentro de la suya); **superadmin** es la plataforma: crea empresas (`POST /api/empresas`), crea usuarios en cualquiera y puede mirar otra empresa con `?empresa=ID`. Hay dos formas de entrar: **registro propio** (`/app/registro` → `POST /api/registro`: nombre de la empresa, correo y clave; el servidor crea la empresa y su primer usuario como admin con APIs de administrador de Cognito y la persona entra de inmediato) y **alta por un admin** (recibe una clave temporal por correo y entra directo al espacio de su empresa). El User Pool sigue en "solo creación por administrador" y el cliente de Cognito solo puede escribir `email`: la empresa y el rol los fija siempre el servidor, nadie puede cambiárselos a sí mismo. Cada alta queda en la bitácora.

## Empresas, agente y notificaciones

Brújula es multiempresa: cada cuenta (empresa) tiene su ICP, sus canales, su presupuesto por lote, su Dapta y su correo de notificaciones; leads, lotes, costos, bajas y bitácora están aislados por `empresa_id`. Los usuarios viven en Cognito con los atributos `custom:empresa_id` y `custom:rol` (`admin` ve todas las empresas con `?empresa=ID`; `usuario` solo la suya). La empresa 1 es la de demostración y existe siempre.

El agente reparte el trabajo entre dos modelos y reglas de respaldo:
- **Agente de texto**: lo lento y creativo. Convierte el cliente ideal escrito en español en criterios estructurados (`POST /api/icp/interpretar`), redacta el primer mensaje de cada lead con su señal y explica decisiones en una frase. Corre en Amazon Bedrock (API converse, modelo por `BEDROCK_MODEL`: Claude Haiku 5.5 o Amazon Nova) y, mientras la cuenta de AWS no tenga Bedrock habilitado, en el mismo Amazon Nova por OpenRouter (`LLM_OPENROUTER_MODEL`, por defecto `amazon/nova-lite-v1`, con la misma clave de Jev). `GET /api/estado` dice qué motor está activo.
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
