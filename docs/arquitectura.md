# Arquitectura

## En una frase
Un servicio web (FastAPI) con conectores a fuentes públicas, una base PostgreSQL, el MCP de Dapta como motor de voz y calificación, y EventBridge marcando el ciclo "encontrar, contactar, medir, reasignar" cada hora dentro de la ventana legal.

## Piezas en AWS y por qué cada una

| Pieza | Para qué | Por qué esta y no otra |
|---|---|---|
| **Lambda con imagen de contenedor y Function URL** | El tablero, la API, los webhooks de Dapta y de correo, y los endpoints de cron. HTTPS propio sin dominio. | La misma imagen de ECR corre en Lambda con el Lambda Web Adapter; sin servidores ni balanceadores y con costo cero en reposo. App Runner dejó de aceptar cuentas nuevas en abril de 2026. Dapta necesita una URL pública para el webhook post-llamada; los correos necesitan enlaces públicos para "me interesa / no / baja". |
| **RDS PostgreSQL** (db.t3.micro) | Leads, intentos con su costo, calificaciones, lotes y bitácora. | Lambda no tiene disco persistente; SQLite queda para desarrollo. El código es el mismo (SQLModel, `DATABASE_URL`). |
| **Secrets Manager** | Clave MCP de Dapta, OpenRouter (Jev), Resend, clave del cron y la URL de la base. | Las claves no van en la imagen ni en variables planas; la aplicación los lee al arrancar por SECRET_ARN. |
| **EventBridge** (API destinations) | Regla 1: `POST /cron/lote` cada hora, L-V 7 a 18 y sábados 8 a 14 (Bogotá). Regla 2: `POST /cron/sincronizar` cada 15 min. | Es el "cada lote" de la brújula sin un proceso vivo. La app vuelve a validar la ventana legal: EventBridge propone, el cumplimiento dispone. |
| **S3** | Exportaciones (leads, bitácora) y copias de lo descargado de cada fuente. | Reproducibilidad: el jurado puede ver con qué datos se corrió cada lote. |
| **Amazon SES** | Canal correo con eventos (entrega, apertura, clic, rebote) por SNS a `/webhook/ses`. | Sin dominio propio: remitente con identidad de correo verificada y salida del sandbox. Resend es el segundo proveedor con la misma interfaz (`EMAIL_PROVIDER`). |
| **S3 con URL prefirmadas** | Subidas desde el navegador (listas propias de la pyme, RNE de la CRC) con PUT prefirmado de 15 minutos; exportaciones (leads, intentos, bitácora) con GET prefirmado de 15 minutos. Bucket privado, CORS para PUT/GET, las subidas caducan a los 30 días. | El servidor nunca recibe el archivo ni lo sirve: firma y procesa por clave. Sin bucket, el mismo flujo corre local. |
| **Front Angular en la misma Lambda** | Angular 20 compilado dentro de la imagen y servido en `/app/` por la aplicación (la raíz redirige allí); consume `/api/*` (OpenAPI en `/api/docs`) con el JWT de Cognito. El tablero HTML del servidor queda en `/tablero`. | Mismo origen para API y front: sin CORS, sin CloudFront y sin dominio (la Function URL ya es HTTPS). `deploy/front.yml` es la variante S3 + CloudFront. API primero: el servidor no depende del front para funcionar. |
| **CloudWatch** | Logs de Lambda. | Viene solo. |

Fuera de AWS, a propósito:
- **Dapta** (voz, calificación, secuencias) por MCP: es el producto del reto, no se reemplaza.
- **Jev** (TypeSafe) por OpenRouter: el modelo de decisión del organizador, para puntuar el ICP y clasificar respuestas. Es barato (USD 0,042 por millón de tokens) y rápido; si falla, mandan las reglas.
- **Fuentes** (datos.gov.co, Overpass, DENUE, BrasilAPI, NYC Open Data): públicas y gratuitas; se citan.

## Flujo de datos
1. `fetch`: conector → `Registro` normalizado → `Lead` (principal o duplicado) → costo de descarga prorrateado.
2. `score`: reglas + Jev → `icp_score`, `icp_estado`; los "revisar" los decide una persona en `/lead/{id}`.
3. `lote`: cumplimiento (ventana, exclusión, persona jurídica) → la brújula reparte por fuente × canal → `Intento`s programados → cada canal envía y guarda estado, costo y referencia.
4. Respuestas: correo por clic (`/r/{token}`) o eventos (`/webhook/resend`, `/webhook/ses`); voz por `list_calls` y el webhook post-llamada de Dapta.
5. `sync`: los que respondieron entran a la secuencia del calificador de Dapta; `find_qualified_leads` y el análisis post-llamada cierran la `Calificacion`.
6. `metricas`: costo por lead encontrado (fuente), CPL y CPLQ (canal y fuente × canal), speed-to-lead, embudo y la recomendación en una frase.

## Decisiones de diseño
- **RDS PostgreSQL** con SSL y contraseña fuerte guardada en Secrets Manager; la Lambda se conecta sin NAT ni túneles.
- **SQLite en desarrollo, PostgreSQL en nube**: mismo modelo; las pruebas corren en SQLite.
- **El MCP de Dapta no arranca la secuencia**: la activación es un clic en su panel. Lo dice su documentación; lo dejamos explícito en el tablero.
- **Costos**: cada intento guarda su costo real cuando el proveedor lo entrega (créditos de Dapta) y una tarifa publicada cuando no (Meta, SES, OpenRouter). La tabla está en `brujula/config.py`.
- **Bandido explicable**: priors declarados, un piso de exploración del 15 % y una explicación por lote; el reparto se recalcula con cada resultado.
