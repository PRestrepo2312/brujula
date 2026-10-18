import { Injectable, inject, signal } from '@angular/core';
import { ConfigService } from './config.service';

const CLAVE = 'brujula.sesion';

interface Sesion { idToken: string; accessToken: string; expira: number; email: string; empresaId: number; rol: string }
export interface ResultadoEntrada { ok: boolean; desafio?: 'NEW_PASSWORD_REQUIRED'; session?: string }

/** Errores de Cognito en español. Con PreventUserExistenceErrors, "no existe" y "clave mala" son el mismo mensaje. */
const MENSAJES: Record<string, string> = {
  NotAuthorizedException: 'Correo o clave incorrectos.',
  UserNotFoundException: 'Correo o clave incorrectos.',
  UserNotConfirmedException: 'La cuenta no está confirmada.',
  PasswordResetRequiredException: 'Debe restablecer la clave: use "Olvidé mi clave".',
  InvalidPasswordException: 'La clave debe tener 12 caracteres o más, con mayúscula, minúscula y número.',
  InvalidParameterException: 'Revise los datos: la clave debe tener 12 caracteres o más, con mayúscula, minúscula y número.',
  CodeMismatchException: 'El código no coincide.',
  ExpiredCodeException: 'El código venció; pida uno nuevo.',
  LimitExceededException: 'Demasiados intentos; espere unos minutos.',
  TooManyRequestsException: 'Demasiados intentos; espere unos minutos.',
};

/**
 * Sesión con Amazon Cognito. Dos caminos:
 *  - formulario propio (entrar / clave nueva / recuperar): habla directo con la API de Cognito por HTTPS, la clave nunca pasa por Brújula;
 *  - página alojada de Cognito (login): flujo de código con PKCE, por si se prefiere.
 * Sin Cognito configurado (local) corre en modo abierto.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private cfg = inject(ConfigService);
  sesion = signal<Sesion | null>(this.leer());

  get activo(): boolean { return this.cfg.loginActivo; }
  get autenticado(): boolean { return !this.activo || (!!this.sesion() && this.sesion()!.expira > Date.now()); }
  get token(): string | null { return this.sesion()?.idToken ?? null; }
  get email(): string { return this.activo ? (this.sesion()?.email ?? '') : 'local'; }
  get rol(): string { return this.activo ? (this.sesion()?.rol ?? 'usuario') : 'superadmin'; }

  private leer(): Sesion | null {
    try { const v = sessionStorage.getItem(CLAVE); return v ? JSON.parse(v) : null; } catch { return null; }
  }

  private get base(): string { return this.cfg.config.frontUrl.replace(/\/$/, ''); }
  private redirectUri(): string { return `${this.base}/callback`; }

  // ---------- formulario propio: API de Cognito ----------

  private async idp(objetivo: string, cuerpo: Record<string, unknown>): Promise<any> {
    const r = await fetch(`https://cognito-idp.${this.cfg.config.cognito.region}.amazonaws.com/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-amz-json-1.1', 'X-Amz-Target': `AWSCognitoIdentityProviderService.${objetivo}` },
      body: JSON.stringify(cuerpo),
    });
    const datos = await r.json().catch(() => ({}));
    if (!r.ok) {
      const tipo = String(datos.__type || '').split('#').pop() || '';
      const texto = String(datos.message || '');
      // Casos que el tipo genérico esconde: la cuenta existe pero nunca fijó su clave (registro a medias o invitación sin usar).
      if (/cannot be reset in the current state|User is disabled/i.test(texto) && objetivo === 'ForgotPassword') {
        throw new Error('Esa cuenta todavía no tiene clave propia. Si usted se registró y falló, vuelva a "Crear mi empresa" con el mismo correo y se completa; si lo invitaron, entre con la clave temporal del correo de invitación.');
      }
      throw new Error(MENSAJES[tipo] || texto || `Cognito respondió ${r.status}`);
    }
    return datos;
  }

  async entrar(email: string, clave: string): Promise<ResultadoEntrada> {
    const r = await this.idp('InitiateAuth', { AuthFlow: 'USER_PASSWORD_AUTH', ClientId: this.cfg.config.cognito.clientId, AuthParameters: { USERNAME: email.trim(), PASSWORD: clave } });
    if (r.AuthenticationResult) { this.guardar(r.AuthenticationResult.IdToken, r.AuthenticationResult.AccessToken, r.AuthenticationResult.ExpiresIn); return { ok: true }; }
    if (r.ChallengeName === 'NEW_PASSWORD_REQUIRED') return { ok: false, desafio: 'NEW_PASSWORD_REQUIRED', session: r.Session };
    throw new Error(`Desafío de Cognito no soportado: ${r.ChallengeName}`);
  }

  /** Primer ingreso: Cognito exige cambiar la clave temporal. */
  async claveNueva(email: string, nueva: string, session: string): Promise<void> {
    const r = await this.idp('RespondToAuthChallenge', { ChallengeName: 'NEW_PASSWORD_REQUIRED', ClientId: this.cfg.config.cognito.clientId, Session: session,
      ChallengeResponses: { USERNAME: email.trim(), NEW_PASSWORD: nueva } });
    if (!r.AuthenticationResult) throw new Error('No se pudo guardar la clave nueva.');
    this.guardar(r.AuthenticationResult.IdToken, r.AuthenticationResult.AccessToken, r.AuthenticationResult.ExpiresIn);
  }

  async olvide(email: string): Promise<void> {
    await this.idp('ForgotPassword', { ClientId: this.cfg.config.cognito.clientId, Username: email.trim() });
  }

  async confirmarOlvide(email: string, codigo: string, nueva: string): Promise<void> {
    await this.idp('ConfirmForgotPassword', { ClientId: this.cfg.config.cognito.clientId, Username: email.trim(), ConfirmationCode: codigo.trim(), Password: nueva });
  }

  private guardar(idToken: string, accessToken: string, expiraEn: number): void {
    const claims = this.claims(idToken);
    const s: Sesion = { idToken, accessToken, expira: Date.now() + (expiraEn - 60) * 1000,
      email: claims['email'] || claims['cognito:username'] || '', empresaId: Number(claims['custom:empresa_id'] || 1), rol: claims['custom:rol'] || 'usuario' };
    sessionStorage.setItem(CLAVE, JSON.stringify(s));
    this.sesion.set(s);
  }

  // ---------- página alojada de Cognito (flujo de código con PKCE) ----------

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
    this.guardar(t.id_token, t.access_token, t.expires_in);
    sessionStorage.removeItem('brujula.pkce');
    return guardado.siguiente || '/';
  }

  logout(): void {
    sessionStorage.removeItem(CLAVE);
    this.sesion.set(null);
    window.location.href = `${this.base}/login`;
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
