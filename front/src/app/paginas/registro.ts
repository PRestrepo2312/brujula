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
          <div class="logo"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9.5"/><path d="M15.5 8.5 13.6 13.6 8.5 15.5l1.9-5.1z" fill="currentColor" stroke="none" opacity=".9"/></svg> BRÚJULA</div>
          <h1>Su empresa, <em>su espacio</em>: nadie más ve sus clientes potenciales.</h1>
          <p>Cree la empresa en un minuto. Si escribe el NIT, Brújula trae el nombre, la ciudad y el sector del registro mercantil; después un asistente le ayuda a decir qué ofrece y a quién le vende.</p>
        </div>
        <p class="small">Equipo JFB Devs · Hackathon 30X</p>
      </section>
      <section class="auth-form">
        <div class="auth-card">
          <h2>Crear mi empresa</h2><p class="lead">Entra de inmediato; lo demás se completa guiado.</p>
          <div class="field"><label>NIT <span class="muted">(opcional)</span></label>
            <div class="row" style="flex-wrap:nowrap"><input [(ngModel)]="nit" placeholder="900123456" inputmode="numeric" (keyup.enter)="buscarNit()"><button class="btn btn-secondary" type="button" (click)="buscarNit()" [disabled]="buscando() || !nitValido()">{{ buscando() ? 'Buscando…' : 'Buscar' }}</button></div>
            @if (rues(); as r) {<span class="hint">Registro mercantil: <b>{{ r.razon_social }}</b>{{ r.sigla ? ' (' + r.sigla + ')' : '' }} · {{ titulo(r.ciudad) }} · {{ r.sector }} · matrícula {{ r.matricula }}</span>}
            @if (nitError()) {<span class="hint" style="color:var(--danger)">{{ nitError() }}</span>}
          </div>
          <div class="field"><label>Nombre de la empresa</label><input [(ngModel)]="empresa" placeholder="Clínica Sonrisas SAS" (keyup.enter)="crear()"></div>
          <div class="field"><label>Su correo</label><input type="email" [(ngModel)]="email" autocomplete="username" (keyup.enter)="crear()"></div>
          <div class="field"><label>Clave</label><input type="password" [(ngModel)]="clave" autocomplete="new-password"><span class="hint">12 caracteres o más, con mayúscula, minúscula y número.</span></div>
          <div class="field"><label>Repita la clave</label><input type="password" [(ngModel)]="clave2" autocomplete="new-password" (keyup.enter)="crear()"></div>
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
  empresa = ''; email = ''; clave = ''; clave2 = ''; nit = '';
  rues = signal<any>(null);
  nitError = signal('');
  buscando = signal(false);
  ocupado = signal(false); error = signal('');

  titulo(s: string): string { return (s || '').toLowerCase().replace(/(^|\s)\S/g, (c) => c.toUpperCase()); }
  nitValido(): boolean { return this.nit.replace(/\D/g, '').length >= 8; }

  buscarNit(): void {
    this.buscando.set(true); this.nitError.set(''); this.rues.set(null);
    this.api.nit(this.nit).subscribe({
      next: (r) => { this.rues.set(r); if (!this.empresa.trim()) this.empresa = this.titulo(r.sigla || r.razon_social); this.buscando.set(false); },
      error: (e) => { this.nitError.set(e.error?.error || 'No se pudo consultar el RUES'); this.buscando.set(false); } });
  }

  async crear(): Promise<void> {
    if (this.ocupado() || this.clave !== this.clave2) return;
    this.ocupado.set(true); this.error.set('');
    try {
      await this.api.registro({ empresa: this.empresa.trim(), email: this.email.trim(), clave: this.clave, icp_texto: '', nit: this.nit.trim(), rues: this.rues() }).toPromise();
      const r = await this.auth.entrar(this.email.trim(), this.clave);
      this.router.navigateByUrl(r.ok ? '/inicio' : '/login');
    } catch (e: any) {
      this.error.set(e?.error?.error || e?.message || String(e));
    }
    this.ocupado.set(false);
  }
}
