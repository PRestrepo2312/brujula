import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { ApiService } from '../core/api.service';

/** Asistente de inicio: su empresa (NIT y página) → cómo se presenta → su cliente ideal. Guiado, con el agente proponiendo y la persona corrigiendo. */
@Component({
  selector: 'pagina-inicio',
  imports: [FormsModule, RouterLink],
  template: `
    <div class="page-head"><div><span class="eyebrow">Asistente de inicio</span><h1>Cuéntenos de su empresa y a quién le vende</h1><p>Tres pasos. Brújula trae lo que ya existe en registros públicos y en su página, el agente propone el texto y usted lo corrige.</p></div>
      <a class="btn btn-ghost" routerLink="/">Hacerlo después</a></div>
    <div class="steps">
      <div class="stepbar"><span [class.on]="paso() >= 1">1 Su empresa</span><span [class.on]="paso() >= 2">2 Cómo se presenta</span><span [class.on]="paso() >= 3">3 Su cliente ideal</span></div>
      @if (paso() === 1) {
        <div class="card">
          <h2>Su empresa</h2>
          <div class="grid cols-2">
            <div class="field"><label>Nombre con el que se presenta</label><input [(ngModel)]="perfil.nombre" placeholder="Clínica Sonrisas"></div>
            <div class="field"><label>NIT <span class="muted">(opcional)</span></label>
              <div class="row" style="flex-wrap:nowrap"><input [(ngModel)]="perfil.nit" inputmode="numeric" placeholder="900123456"><button class="btn btn-secondary" (click)="buscarNit()" [disabled]="ocupado() || !nitValido()">Buscar en el RUES</button></div>
              @if (rues(); as r) {<span class="hint">{{ r.razon_social }} · {{ titulo(r.ciudad) }} · sector {{ r.sector }} · matrícula {{ r.matricula }} · {{ r.estado }}</span>}
              @if (aviso()) {<span class="hint" style="color:var(--danger)">{{ aviso() }}</span>}
            </div>
            <div class="field"><label>Página web <span class="muted">(opcional)</span></label>
              <div class="row" style="flex-wrap:nowrap"><input [(ngModel)]="perfil.sitio_web" placeholder="www.suempresa.com"><button class="btn btn-secondary" (click)="leerSitio()" [disabled]="ocupado() || !perfil.sitio_web.trim()">Leer la página</button></div>
              @if (sitio(); as s) {<span class="hint"><b>{{ s.titulo }}</b> {{ s.descripcion }}</span>}
            </div>
            <div class="field"><label>Notas para el agente <span class="muted">(opcional)</span></label><textarea rows="2" [(ngModel)]="notas" placeholder="Lo que quiera destacar: servicios, zona, diferencial"></textarea></div>
          </div>
          <div class="row"><button class="btn btn-primary btn-lg" (click)="proponer()" [disabled]="ocupado() || !perfil.nombre.trim()">{{ ocupado() ? 'Preparando…' : 'Continuar: proponer cómo presentarse' }}</button></div>
        </div>
      }
      @if (paso() === 2) {
        <div class="card">
          <div class="card-head"><h2>Cómo se presenta</h2>@if (motor()) {<span class="tag tag-info">propuesto {{ motor() === 'reglas' ? 'con los datos del registro y la página' : 'por el agente' }}</span>}</div>
          <p class="small muted">Es lo que dirán los correos, los mensajes de WhatsApp y la llamada del agente. Corrija lo que quiera.</p>
          <div class="field"><label>Qué ofrece <span class="muted">(completa "Les escribe {{ perfil.remitente || 'el equipo de ' + perfil.nombre }}: …")</span></label><textarea rows="2" [(ngModel)]="perfil.que_ofrece"></textarea></div>
          <div class="grid cols-2">
            <div class="field"><label>A quién le vende</label><input [(ngModel)]="perfil.a_quien"></div>
            <div class="field"><label>Qué lo distingue <span class="muted">(opcional)</span></label><input [(ngModel)]="perfil.diferencial"></div>
            <div class="field"><label>Quién firma</label><input [(ngModel)]="perfil.remitente" placeholder="el equipo de Clínica Sonrisas"></div>
          </div>
          <div class="banner"><b>Así empezaría un correo:</b> "Hola, equipo de [empresa]. Les escribe {{ perfil.remitente || 'el equipo de ' + perfil.nombre }}: {{ perfil.que_ofrece || '…' }}. Les escribimos porque [la señal de esa empresa]."</div>
          <div class="row"><button class="btn btn-secondary" (click)="paso.set(1)">Atrás</button><button class="btn btn-primary btn-lg" (click)="paso.set(3)" [disabled]="!perfil.que_ofrece.trim()">Continuar: su cliente ideal</button></div>
        </div>
      }
      @if (paso() === 3) {
        <div class="card">
          <h2>Su cliente ideal</h2>
          <p class="small muted">A quién debe buscar Brújula en los registros públicos. En sus palabras: sector, tamaño, ciudades, cómo atienden.</p>
          <div class="field"><textarea rows="3" [(ngModel)]="icpTexto" placeholder="Clínicas odontológicas en Bogotá y Medellín con más de 10 empleados que agendan citas por WhatsApp"></textarea></div>
          <div class="row"><button class="btn btn-secondary" (click)="interpretar()" [disabled]="ocupado() || !icpTexto.trim()">Ver cómo lo entiende Brújula</button></div>
          @if (icp(); as i) {
            <div class="choices" style="margin-top:12px">
              @for (s of i.sectores; track s) {<span class="tag tag-accent">{{ s }}</span>}
              @for (c of i.ciudades; track c) {<span class="tag">{{ c }}</span>}
              @if (i.empleados_min || i.empleados_max) {<span class="tag">{{ i.empleados_min ?? '' }} a {{ i.empleados_max ?? '' }} empleados</span>}
              @for (p of i.palabras_sector; track p) {<span class="tag">{{ p }}</span>}
            </div>
          }
          @if (aviso()) {<div class="banner banner-danger">{{ aviso() }}</div>}
          <div class="row" style="margin-top:16px"><button class="btn btn-secondary" (click)="paso.set(2)">Atrás</button><button class="btn btn-primary btn-lg" (click)="guardar()" [disabled]="ocupado() || !icpTexto.trim()">{{ ocupado() ? 'Guardando…' : 'Guardar y empezar a buscar' }}</button></div>
        </div>
      }
    </div>
  `,
  styles: [`
    .steps { max-width: 880px; }
    .stepbar { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
    .stepbar span { font-size: 12px; font-weight: 600; letter-spacing: .04em; color: var(--muted); padding: 6px 12px; border-radius: 999px; background: #EEF0F3; }
    .stepbar span.on { background: var(--ink); color: #fff; }
    .eyebrow { display: block; font-family: var(--mono); font-size: 11px; letter-spacing: .14em; text-transform: uppercase; color: var(--accent); margin-bottom: 6px; }
  `],
})
export class InicioPage {
  private api = inject(ApiService);
  private router = inject(Router);
  paso = signal(1);
  perfil: any = { nombre: '', nit: '', sitio_web: '', que_ofrece: '', a_quien: '', diferencial: '', remitente: '' };
  notas = '';
  icpTexto = '';
  rues = signal<any>(null);
  sitio = signal<any>(null);
  icp = signal<any>(null);
  motor = signal('');
  aviso = signal('');
  ocupado = signal(false);
  private config: any = {};

  constructor() {
    this.api.empresa().subscribe((e) => {
      this.config = { ...(e.config || {}) };
      const p = this.config.perfil || {};
      this.perfil = { nombre: p.nombre || e.nombre || '', nit: p.nit || '', sitio_web: p.sitio_web || '', que_ofrece: p.que_ofrece || '', a_quien: p.a_quien || '', diferencial: p.diferencial || '', remitente: p.remitente || '' };
      if (p.razon_social) this.rues.set({ razon_social: p.razon_social, ciudad: p.ciudad, sector: p.sector, matricula: '', estado: '' });
    });
    this.api.icp().subscribe((r) => { this.icpTexto = r.texto || ''; });
  }

  titulo(s: string): string { return (s || '').toLowerCase().replace(/(^|\s)\S/g, (c) => c.toUpperCase()); }
  nitValido(): boolean { return String(this.perfil.nit || '').replace(/\D/g, '').length >= 8; }

  buscarNit(): void {
    this.ocupado.set(true); this.aviso.set('');
    this.api.nit(this.perfil.nit).subscribe({
      next: (r) => { this.rues.set(r); if (!this.perfil.nombre.trim()) this.perfil.nombre = this.titulo(r.sigla || r.razon_social); this.ocupado.set(false); },
      error: (e) => { this.aviso.set(e.error?.error || 'No se pudo consultar el RUES'); this.ocupado.set(false); } });
  }

  leerSitio(): void {
    this.ocupado.set(true); this.aviso.set('');
    this.api.sitio(this.perfil.sitio_web).subscribe({
      next: (s) => { this.sitio.set(s); this.ocupado.set(false); },
      error: (e) => { this.aviso.set(e.error?.error || 'No se pudo leer la página'); this.ocupado.set(false); } });
  }

  proponer(): void {
    this.ocupado.set(true); this.aviso.set('');
    this.api.sugerir({ nombre: this.perfil.nombre.trim(), rues: this.rues(), sitio: this.sitio() || (this.perfil.sitio_web.trim() ? { url: this.perfil.sitio_web.trim() } : null), notas: this.notas }).subscribe({
      next: (r) => {
        const s = r.sugerencia || {};
        this.perfil.que_ofrece = this.perfil.que_ofrece || s.que_ofrece || '';
        this.perfil.a_quien = this.perfil.a_quien || s.a_quien || '';
        this.perfil.diferencial = this.perfil.diferencial || s.diferencial || '';
        this.perfil.remitente = this.perfil.remitente || s.remitente || '';
        if (!this.icpTexto.trim()) this.icpTexto = s.icp_texto || '';
        this.motor.set(r.motor || ''); this.paso.set(2); this.ocupado.set(false);
      },
      error: (e) => { this.aviso.set(e.error?.error || e.message); this.paso.set(2); this.ocupado.set(false); } });
  }

  interpretar(): void {
    this.ocupado.set(true); this.aviso.set('');
    this.api.interpretarIcp(this.icpTexto).subscribe({ next: (r) => { this.icp.set(r.icp); this.ocupado.set(false); }, error: (e) => { this.aviso.set(e.message); this.ocupado.set(false); } });
  }

  guardar(): void {
    this.ocupado.set(true); this.aviso.set('');
    const perfil = { ...(this.config.perfil || {}), ...this.perfil };
    const terminar = () => {
      this.api.guardarEmpresa({ nombre: this.perfil.nombre.trim() || undefined, icp_texto: this.icpTexto.trim(), config: { ...this.config, perfil } }).subscribe({
        next: () => { this.ocupado.set(false); this.router.navigateByUrl('/buscar'); },
        error: (e) => { this.aviso.set(e.error?.error || e.message); this.ocupado.set(false); } });
    };
    if (this.icp()) { this.api.guardarIcp(this.icp()).subscribe({ next: terminar, error: terminar }); }
    else { this.api.interpretarIcp(this.icpTexto).subscribe({ next: (r) => this.api.guardarIcp(r.icp).subscribe({ next: terminar, error: terminar }), error: terminar }); }
  }
}
