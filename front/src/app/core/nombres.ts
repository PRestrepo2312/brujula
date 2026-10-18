/** Nombres que entiende cualquiera, en vez de las claves internas (reps, men, rnt…). Mismo mapa que brujula/metrics.py. */
export const NOMBRE_FUENTE: Record<string, string> = {
  reps: 'Salud (REPS)', men: 'Colegios (MEN)', rnt: 'Turismo (RNT)', secop: 'Proveedores del Estado (SECOP)', rues: 'Recién matriculadas (RUES)',
  osm: 'Mapa (OSM)', csv: 'Lista propia', whatsapp: 'WhatsApp entrante', denue: 'México (DENUE)', cnpj: 'Brasil (CNPJ)', nyc: 'Nueva York (licencias)',
};
export const NOMBRE_CANAL: Record<string, string> = { correo: 'correo', voz: 'llamada', whatsapp: 'WhatsApp' };

export function nombreFuente(clave: string): string { return NOMBRE_FUENTE[clave] || clave; }
export function nombreCanal(clave: string): string { return NOMBRE_CANAL[clave] || clave; }
/** 'rnt|correo' → 'Turismo (RNT) + correo'. */
export function nombreCruce(clave: string): string { const [f, c] = clave.split('|'); return `${nombreFuente(f)} + ${nombreCanal(c ?? '')}`; }
