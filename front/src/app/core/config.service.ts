import { Injectable } from '@angular/core';

export interface ConfigFront {
  apiUrl: string;
  cognito: { domain: string; clientId: string; userPoolId: string; region: string };
  frontUrl: string;
}

/**
 * Configuración del front, leída de config.json (relativo al base href) al arrancar.
 * En la nube la sirve la propia API en /app/config.json; en local es public/config.json (API en localhost:8000).
 */
@Injectable({ providedIn: 'root' })
export class ConfigService {
  config: ConfigFront = { apiUrl: 'http://localhost:8000', cognito: { domain: '', clientId: '', userPoolId: '', region: 'us-east-1' }, frontUrl: '' };

  async cargar(): Promise<void> {
    try {
      const r = await fetch('config.json', { cache: 'no-store' });
      if (r.ok) this.config = { ...this.config, ...(await r.json()) };
    } catch {
      /* sin config.json: valores locales */
    }
    if (!this.config.frontUrl) this.config.frontUrl = window.location.origin;
    this.config.apiUrl = (this.config.apiUrl || '').replace(/\/$/, '');   // vacío = mismo origen que el front
  }

  get loginActivo(): boolean {
    return !!(this.config.cognito.domain && this.config.cognito.clientId);
  }
}
