# Front de Brújula

Angular 20 (componentes standalone y signals). Páginas: tablero, en vivo, inicio (chat), buscar (chat y modo manual), leads y detalle, lotes, notificaciones, configuración, login y registro.

- Desarrollo: `npm install && npx ng serve` (lee `public/config.json`, que apunta a la API local).
- Producción: el `Dockerfile` de la raíz lo compila con `--base-href /app/` y la misma Lambda lo sirve en `/app/`; la configuración (ids de Cognito, URL de la API) la genera el servidor en `/app/config.json`.
- Nombres legibles de fuentes y canales: `src/app/core/nombres.ts`. Chat compartido por los dos asistentes: `src/app/paginas/chat.ts`.

Todo lo demás está en el [README principal](../README.md).
