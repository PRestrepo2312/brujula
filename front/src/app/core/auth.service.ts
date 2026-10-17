import { Injectable, inject, signal } from '@angular/core';
import { ConfigService } from './config.service';

const CLAVE = 'brujula.sesion';

interface Sesion { idToken: string; accessToken: string; expira: number; email: string; empresaId: number; rol: string }

/** Login con Cognito por la página alojada (flujo de código con PKCE). Sin Cognito configurado, modo abierto. */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private cfg = inject(ConfigService);
  sesion = signal<Sesion | null>(this.leer());

  get activo(): boolean { return this.cfg.loginActivo; }
  get autenticado(): boolean { return !this.activo || (!!this.sesion() && this.sesion()!.expira > Date.now()); }
  get token(): string | null { return this.sesion()?.idToken ?? null; }
  get email(): string { return this.activo ? (this.sesion()?.email ?? '') : 'local'; }
  get rol(): string { return this.activo ? (this.sesion()?.rol ?? 'usuario') : 'admin'; }

  private leer(): Sesion | null {
    try { const v = sessionStorage.getItem(CLAVE); return v ? JSON.parse(v) : null; } catch { return null; }
  }

  private redirectUri(): string { return `${this.cfg.config.frontUrl.replace(/\/$/, '')}/callback`; }

  async login(siguiente = '/'): Promise<void> {
    const c = this.cfg.config.cognito;
    const verificador = this.aleatorio(64);
    const desafio = await this.sha256Base64Url(verificador);
    const estado = this.aleatorio(16);
    sessionStorage.setItem('brujula.pkce', JSON.stringify({ verificador, estado, siguiente }));
    const q = new URLSearchParams({ response_type: 'code', client_id: c.clientId, redirect_uri: this.redirectUri(), scope: 'openid email profile',
      code_challenge: desafio, code_challenge_method: 'S256', state: estado });
    window.location.href = `https://${c.domain}/oauth2/authorize?${q.toString()}`;
  }

  /** Vuelve de Cognito con ?code=...&state=...: canjea el código por tokens. Devuelve la ruta a la que ir. */
  async callback(code: string, estado: string): Promise<string> {
    const c = this.cfg.config.cognito;
    const guardado = JSON.parse(sessionStorage.getItem('brujula.pkce') || '{}');
    if (!guardado.verificador || guardado.estado !== estado) throw new Error('estado de login inválido');
    const cuerpo = new URLSearchParams({ grant_type: 'authorization_code', client_id: c.clientId, code, redirect_uri: this.redirectUri(), code_verifier: guardado.verificador });
    const r = await fetch(`https://${c.domain}/oauth2/token`, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: cuerpo.toString() });
    if (!r.ok) throw new Error(`Cognito respondió ${r.status}`);
    const t = await r.json();
    const claims = this.claims(t.id_token);
    const s: Sesion = { idToken: t.id_token, accessToken: t.access_token, expira: Date.now() + (t.expires_in - 60) * 1000,
      email: claims['email'] || claims['cognito:username'] || '', empresaId: Number(claims['custom:empresa_id'] || 1), rol: claims['custom:rol'] || 'usuario' };
    sessionStorage.setItem(CLAVE, JSON.stringify(s));
    sessionStorage.removeItem('brujula.pkce');
    this.sesion.set(s);
    return guardado.siguiente || '/';
  }

  logout(): void {
    sessionStorage.removeItem(CLAVE);
    this.sesion.set(null);
    if (this.activo) {
      const c = this.cfg.config.cognito;
      const q = new URLSearchParams({ client_id: c.clientId, logout_uri: `${this.cfg.config.frontUrl.replace(/\/$/, '')}/login` });
      window.location.href = `https://${c.domain}/logout?${q.toString()}`;
    }
  }

  private claims(jwt: string): Record<string, any> {
    try { return JSON.parse(atob(jwt.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))); } catch { return {}; }
  }

  private aleatorio(n: number): string {
    const bytes = new Uint8Array(n); crypto.getRandomValues(bytes);
    return Array.from(bytes, (b) => ('0' + (b & 0xff).toString(16)).slice(-2)).join('').slice(0, n);
  }

  private async sha256Base64Url(texto: string): Promise<string> {
    const d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(texto));
    return btoa(String.fromCharCode(...new Uint8Array(d))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }
}
