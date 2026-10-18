# Qué muestra el video de demostración

El video (menos de tres minutos) se entrega en la plataforma de la hackathon. Se produjo con capturas reales de la plataforma desplegada, locución en español y subtítulos. En orden:

1. **El problema.** Pauta que sube cada mes, bases compradas, WhatsApps sin responder, llamadas a deshora y, al final, nadie sabe cuánto costó cada lead. Tres de cada cinco pymes que llegan a Dapta preguntan de dónde sacar clientes.
2. **Brújula.** Más leads, menor costo: encuentra empresas en registros públicos gratuitos, las contacta con los agentes de Dapta y mide cuánto cuesta cada cliente por canal.
3. **Asistente de inicio** (captura real). La empresa da su NIT y su página; Brújula la busca en el RUES, lee la web y propone cómo presentarse y a quién buscar.
4. **Buscar por chat** (captura real). La persona dice a quién quiere y la brújula elige las fuentes públicas: REPS (salud), MEN (colegios), RNT (turismo), SECOP (proveedores del Estado), RUES (empresas nuevas), OpenStreetMap, DENUE (México), CNPJ (Brasil) y licencias de Nueva York. Un "sí" y busca: 144 empresas nuevas en Medellín.
5. **Leads** sin duplicados, con el puntaje de encaje contra el cliente ideal.
6. **Primer contacto en nombre de la empresa**: el correo real con botones para responder y la **llamada real del agente de voz de Dapta** (Colegio George Williams), con resumen, variables extraídas, transcripción y grabación.
7. **WhatsApp**: el agente de texto de Dapta responde y el lead entra solo (lead real "WhatsApp entrante"; el primer mensaje saliente aparece como simulado porque la plantilla de Meta está en revisión).
8. **Lotes**: se piden en el chat o se dejan automáticos; la brújula reparte entre fuentes y canales según lo que ya funcionó.
9. **Tablero**: leads encontrados, contactados y calificados por Dapta, costo por respuesta y por cliente calificado, el **cuadrante costo contra calidad** y **Brújula contra pauta** (20,2 veces más barato en la prueba del fin de semana).
10. **Cumplimiento**: solo datos públicos de empresas, horario de la Ley 2300, lista de exclusión, baja con un clic y el modo prueba para demostrar sin molestar a terceros.
11. **Arquitectura en AWS** (el diagrama de [`arquitectura-aws.png`](arquitectura-aws.png)): una Lambda sirve la API y el front, Postgres en RDS, claves en Secrets Manager, Cognito para entrar, EventBridge para los lotes en horario legal y S3 para los archivos; afuera, Dapta, OpenAI, Brevo y datos.gov.co.
12. **Cierre**: Brújula, del equipo JFB Devs, para el reto de Dapta.

Las cifras que se ven en el video son las de la prueba real del 17 de octubre (las llamadas y los correos salieron desviados al equipo, como explica el README). Las mismas pantallas están en [`capturas/`](capturas/).
