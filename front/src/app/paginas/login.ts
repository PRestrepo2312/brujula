import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthService } from '../core/auth.service';
import { ClaveRequisitos, claveValida } from './clave-requisitos';

type Modo = 'clave' | 'nueva' | 'olvide' | 'codigo';

@Component({
  selector: 'pagina-login',
  imports: [FormsModule, RouterLink, ClaveRequisitos],
  template: `
    <div class="auth">
      <section class="auth-brand">
        <div>
          <div class="logo"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9.5"/><path d="M15.5 8.5 13.6 13.6 8.5 15.5l1.9-5.1z" fill="#9FE1C8" stroke="none"/></svg> BRÚJULA</div>
          <h1>Más leads, <em>menor costo</em>: encuentre empresas en registros públicos, contáctelas y sepa cuánto cuesta cada cliente calificado.</h1>
          <p>Una herramienta para equipos comerciales de pymes. Cada empresa trabaja en su propio espacio.</p>
          <ul>
            <li>Fuentes públicas y gratuitas: REPS, MEN, RNT, SECOP, RUES, OpenStreetMap, DENUE, CNPJ.</li>
            <li>Contacto por voz, correo y WhatsApp con agentes, dentro del horario de la Ley 2300.</li>
            <li>Costo por lead encontrado, por lead que respondió y por lead calificado, por fuente y canal.</li>
          </ul>
        </div>
        <p class="small">Equipo JFB Devs · Hackathon 30X</p>
      </section>
      <section class="auth-form">
        <div class="auth-card">
          @if (!auth.activo) {
            <h2>Modo local</h2><p class="lead">Sin login configurado.</p>
            <button class="btn btn-primary btn-lg btn-block" (click)="ir()">Entrar</button>
          } @else {
            @switch (modo()) {
              @case ('clave') {
                <h2>Entrar</h2><p class="lead">Con el correo y la clave de su empresa.</p>
                <div class="field"><label>Correo</label><input type="email" [(ngModel)]="email" autocomplete="username" (keyup.enter)="entrar()"></div>
                <div class="field"><label>Clave</label><input type="password" [(ngModel)]="clave" autocomplete="current-password" (keyup.enter)="entrar()"></div>
                <button class="btn btn-primary btn-lg btn-block" (click)="entrar()" [disabled]="ocupado() || !email || !clave">{{ ocupado() ? 'Entrando…' : 'Entrar' }}</button>
                <div class="auth-links"><a (click)="cambiar('olvide')">Olvidé mi clave</a><a routerLink="/registro">Crear mi empresa</a></div>
              }
              @case ('nueva') {
                <h2>Clave nueva</h2><p class="lead">Es su primer ingreso: elija una clave de 12 caracteres o más, con mayúscula, minúscula y número.</p>
                <div class="field"><label>Clave nueva</label><input type="password" [(ngModel)]="nueva" autocomplete="new-password"></div>
                <div class="field"><label>Repítala</label><input type="password" [(ngModel)]="nueva2" autocomplete="new-password" (keyup.enter)="fijarNueva()"><clave-requisitos [clave]="nueva" [repetida]="nueva2"/></div>
                <button class="btn btn-primary btn-lg btn-block" (click)="fijarNueva()" [disabled]="ocupado() || !claveValida(nueva) || nueva !== nueva2">Guardar y entrar</button>
              }
              @case ('olvide') {
                <h2>Recuperar la clave</h2><p class="lead">Le enviamos un código al correo de su cuenta.</p>
                <div class="field"><label>Correo</label><input type="email" [(ngModel)]="email" autocomplete="username" (keyup.enter)="pedirCodigo()"></div>
                <button class="btn btn-primary btn-lg btn-block" (click)="pedirCodigo()" [disabled]="ocupado() || !email">Enviar código</button>
                <div class="auth-links"><a (click)="cambiar('clave')">Volver</a></div>
              }
              @case ('codigo') {
                <h2>Código y clave nueva</h2><p class="lead">Escriba el código que llegó al correo y elija la clave nueva.</p>
                <div class="field"><label>Código</label><input [(ngModel)]="codigo" inputmode="numeric" autocomplete="one-time-code"></div>
                <div class="field"><label>Clave nueva</label><input type="password" [(ngModel)]="nueva" autocomplete="new-password"></div>
                <div class="field"><label>Repítala</label><input type="password" [(ngModel)]="nueva2" autocomplete="new-password" (keyup.enter)="confirmarCodigo()"><clave-requisitos [clave]="nueva" [repetida]="nueva2"/></div>
                <button class="btn btn-primary btn-lg btn-block" (click)="confirmarCodigo()" [disabled]="ocupado() || !codigo || !claveValida(nueva) || nueva !== nueva2">Cambiar clave y entrar</button>
                <div class="auth-links"><a (click)="cambiar('clave')">Volver</a></div>
              }
            }
            @if (error()) {<div class="banner banner-danger">{{ error() }}</div>}
            @if (info()) {<div class="banner banner-ok">{{ info() }}</div>}
            <p class="small muted" style="margin-top:18px">La clave viaja cifrada directo a Amazon Cognito. <a (click)="auth.login(siguiente)" style="cursor:pointer">Entrar con la página de Cognito</a></p>
          }
        </div>
      </section>
    </div>`,
})
export class LoginPage {
  auth = inject(AuthService);
  private router = inject(Router);
  siguiente = inject(ActivatedRoute).snapshot.queryParamMap.get('next') || '/';
  modo = signal<Modo>('clave');
  email = ''; clave = ''; nueva = ''; nueva2 = ''; codigo = '';
  claveValida = claveValida;
  private session = '';
  ocupado = signal(false); error = signal(''); info = signal('');

  constructor() { if (this.auth.autenticado) this.ir(); }

  ir(): void { this.router.navigateByUrl(this.siguiente); }
  cambiar(m: Modo): void { this.modo.set(m); this.error.set(''); this.info.set(''); }

  private async correr(accion: () => Promise<void>): Promise<void> {
    this.ocupado.set(true); this.error.set(''); this.info.set('');
    try { await accion(); } catch (e: any) { this.error.set(e?.message || String(e)); }
    this.ocupado.set(false);
  }

  entrar(): void {
    this.correr(async () => {
      const r = await this.auth.entrar(this.email, this.clave);
      if (r.ok) { this.ir(); return; }
      if (r.desafio === 'NEW_PASSWORD_REQUIRED') { this.session = r.session || ''; this.modo.set('nueva'); }
    });
  }
  fijarNueva(): void { this.correr(async () => { await this.auth.claveNueva(this.email, this.nueva, this.session); this.ir(); }); }
  pedirCodigo(): void { this.correr(async () => { await this.auth.olvide(this.email); this.modo.set('codigo'); this.info.set('Código enviado. Revise el correo (también la carpeta de spam).'); }); }
  confirmarCodigo(): void {
    this.correr(async () => {
      await this.auth.confirmarOlvide(this.email, this.codigo, this.nueva);
      const r = await this.auth.entrar(this.email, this.nueva);
      if (r.ok) this.ir(); else this.modo.set('clave');
    });
  }
}
