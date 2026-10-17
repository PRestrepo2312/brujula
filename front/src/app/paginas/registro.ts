import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';

@Component({
  selector: 'pagina-registro',
  imports: [FormsModule, RouterLink],
  template: `
    <div class="auth">
      <section class="auth-brand">
        <div>
          <div class="logo"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9.5"/><path d="M15.5 8.5 13.6 13.6 8.5 15.5l1.9-5.1z" fill="#9FE1C8" stroke="none"/></svg> BRÚJULA</div>
          <h1>Su empresa, <em>su espacio</em>: nadie más ve sus leads.</h1>
          <p>Cree la empresa en un minuto. Usted queda como administrador, define su cliente ideal y agrega a su equipo cuando quiera.</p>
        </div>
        <p class="small">Equipo JFB Devs · Hackathon 30X</p>
      </section>
      <section class="auth-form">
        <div class="auth-card">
          <h2>Crear mi empresa</h2><p class="lead">Tres datos y entra de inmediato.</p>
          <div class="field"><label>Nombre de la empresa</label><input [(ngModel)]="empresa" placeholder="Clínica Sonrisas SAS" (keyup.enter)="crear()"></div>
          <div class="field"><label>Su correo</label><input type="email" [(ngModel)]="email" autocomplete="username" (keyup.enter)="crear()"></div>
          <div class="field"><label>Clave</label><input type="password" [(ngModel)]="clave" autocomplete="new-password"><span class="hint">12 caracteres o más, con mayúscula, minúscula y número.</span></div>
          <div class="field"><label>Repita la clave</label><input type="password" [(ngModel)]="clave2" autocomplete="new-password" (keyup.enter)="crear()"></div>
          <div class="field"><label>Su cliente ideal, en sus palabras <span class="muted">(opcional)</span></label><textarea rows="2" [(ngModel)]="icp" placeholder="Clínicas odontológicas en Bogotá con más de 10 empleados"></textarea></div>
          <button class="btn btn-primary btn-lg btn-block" (click)="crear()" [disabled]="ocupado() || !empresa.trim() || !email || clave.length < 12 || clave !== clave2">{{ ocupado() ? 'Creando…' : 'Crear empresa y entrar' }}</button>
          @if (error()) {<div class="banner banner-danger">{{ error() }}</div>}
          <div class="auth-links"><a routerLink="/login">Ya tengo cuenta</a></div>
        </div>
      </section>
    </div>`,
})
export class RegistroPage {
  private api = inject(ApiService);
  private auth = inject(AuthService);
  private router = inject(Router);
  empresa = ''; email = ''; clave = ''; clave2 = ''; icp = '';
  ocupado = signal(false); error = signal('');

  async crear(): Promise<void> {
    if (this.ocupado() || this.clave !== this.clave2) return;
    this.ocupado.set(true); this.error.set('');
    try {
      await this.api.registro({ empresa: this.empresa.trim(), email: this.email.trim(), clave: this.clave, icp_texto: this.icp.trim() }).toPromise();
      const r = await this.auth.entrar(this.email.trim(), this.clave);
      this.router.navigateByUrl(r.ok ? '/' : '/login');
    } catch (e: any) {
      this.error.set(e?.error?.error || e?.message || String(e));
    }
    this.ocupado.set(false);
  }
}
