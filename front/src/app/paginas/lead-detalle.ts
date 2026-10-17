import { DecimalPipe } from '@angular/common';
import { Component, inject, input, signal, effect } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiService } from '../core/api.service';

@Component({
  selector: 'pagina-lead-detalle',
  imports: [FormsModule, RouterLink, DecimalPipe],
  template: `
    @if (d(); as d) {
      <p class="small"><a routerLink="/leads">Leads</a> <span class="muted">/ {{ titulo(d.lead.razon_social) }}</span></p>
      <div class="page-head">
        <div><h1>{{ titulo(d.lead.razon_social) }}</h1>
          <p>{{ d.lead.fuente_clave }} · {{ d.lead.sector }} {{ d.lead.subsector }} · {{ titulo(d.lead.ciudad) }}@if (d.lead.identificacion) { · NIT {{ d.lead.identificacion }}}@if ((d.lead.fuentes_todas?.length ?? 0) > 1) { · también en {{ d.lead.fuentes_todas.join(', ') }}}</p></div>
        <div class="row"><span class="tag" [class]="'tag ' + d.lead.icp_estado">ICP {{ d.lead.icp_estado }} · {{ d.lead.icp_score ?? '–' }}</span><span class="tag tag-info">{{ d.lead.estado }}</span></div>
      </div>
      <div class="grid cols-3">
        <div class="card">
          <h2>Contacto</h2>
          <dl class="kv">
            <dt>Teléfono</dt><dd>{{ d.lead.telefono || '–' }} <span class="muted">{{ d.lead.telefono_tipo }}</span></dd>
            <dt>Correo</dt><dd>{{ d.lead.correo || '–' }}</dd>
            <dt>Sitio web</dt><dd>{{ d.lead.sitio_web || '–' }}</dd>
            <dt>Canales</dt><dd>{{ d.lead.canales?.join(', ') || '–' }}</dd>
            @if (d.lead.empleados) {<dt>Empleados</dt><dd>{{ d.lead.empleados }}</dd>}
          </dl>
          <h3>Señales</h3>
          @if (pares(d.lead.senales).length) {<dl class="kv">@for (p of pares(d.lead.senales); track p[0]) {<dt>{{ p[0] }}</dt><dd>{{ p[1] }}</dd>}</dl>} @else {<p class="muted small">Sin señales.</p>}
        </div>
        <div class="card">
          <h2>Puntaje contra el cliente ideal</h2>
          @if (pares(d.lead.icp_detalle).length) {<dl class="kv">@for (p of pares(d.lead.icp_detalle); track p[0]) {<dt>{{ p[0] }}</dt><dd>{{ p[1] }}</dd>}</dl>} @else {<p class="muted small">Sin detalle.</p>}
          @if (d.lead.icp_estado === 'revisar') {
            <div class="row" style="margin-top:12px"><button class="btn btn-primary" (click)="revisar('aprobar')">Aprobar</button><button class="btn btn-secondary" (click)="revisar('descartar')">Descartar</button></div>
          }
          <h3>Calificación de Dapta</h3>
          @for (c of d.calificaciones; track c.id) {
            <p><span class="tag" [class]="c.resultado === 'calificado' ? 'tag tag-ok' : c.resultado === 'pendiente' ? 'tag tag-warn' : 'tag tag-danger'">{{ c.resultado }}</span></p>
            @if (pares(c.datos).length) {<dl class="kv">@for (p of pares(c.datos); track p[0]) {<dt>{{ p[0] }}</dt><dd>{{ p[1] }}</dd>}</dl>}
          } @empty {<p class="muted small">Todavía no ha pasado por el calificador.</p>}
        </div>
        <div class="card">
          <h2>Primer mensaje</h2>
          <div class="field"><label>Idioma</label><select [(ngModel)]="idioma"><option value="">El de la fuente</option><option value="es">Español</option><option value="pt">Português</option><option value="en">English</option></select></div>
          <button class="btn btn-secondary" (click)="verMensaje()" [disabled]="ocupado()">Vista previa del correo</button>
          @if (mensaje(); as m) {<p style="white-space:pre-wrap;font-size:13px;margin-top:12px;border-left:3px solid var(--line);padding-left:10px">{{ m.texto }}</p><p class="small muted">{{ m.idioma }} · {{ m.motor }} · USD {{ m.costo_usd | number:'1.4-4' }}</p>}
          <p class="small muted" style="margin-top:8px">Con agente de texto activo redacta en ese idioma; sin agente, usa la plantilla.</p>
        </div>
      </div>
      <div class="grid cols-main" style="margin-top:16px">
        <div class="card">
          <h2>Intentos de contacto</h2>
          <div class="table-wrap"><table class="table">
            <thead><tr><th>#</th><th>Canal</th><th>Proveedor</th><th>Estado</th><th>Respuesta</th><th class="num">Costo USD</th><th>Cuándo</th></tr></thead>
            <tbody>@for (it of d.intentos; track it.id) {<tr><td class="muted">{{ it.id }}</td><td>{{ it.canal }}</td><td>{{ it.proveedor }}</td><td>{{ it.estado }}@if (it.fuera_ventana) { <span class="tag tag-warn">override</span>}@if (it.detalle?.desvio) { <span class="tag tag-warn" [title]="'original: ' + it.detalle.desvio.original">desviado</span>}</td><td>{{ it.clasificacion || '–' }}</td><td class="num">{{ it.costo_usd | number:'1.4-4' }}</td><td class="muted small">{{ fecha(it.enviado_en) }}</td></tr>} @empty {<tr><td colspan="7"><div class="empty">Sin intentos todavía.</div></td></tr>}</tbody>
          </table></div>
          @if (d.duplicados?.length) {<h3>Duplicados fusionados</h3>@for (x of d.duplicados; track x.id) {<p class="small">{{ x.razon_social }} <span class="muted">({{ x.fuente }})</span></p>}}
        </div>
        <div class="card">
          <h2>Registrar una respuesta</h2>
          <p class="small muted">Lo que respondió la empresa por WhatsApp o en una llamada manual; el agente lo clasifica.</p>
          <div class="field"><textarea rows="3" [(ngModel)]="texto" placeholder="Sí, nos interesa; llámennos el martes"></textarea></div>
          <div class="row"><select [(ngModel)]="canal" style="max-width:150px"><option value="whatsapp">WhatsApp</option><option value="voz">Llamada</option><option value="correo">Correo</option></select>
            <button class="btn btn-primary" (click)="responder()" [disabled]="!texto.trim() || ocupado()">Clasificar y guardar</button></div>
          @if (msg()) {<div class="banner banner-ok">{{ msg() }}</div>}
        </div>
      </div>
    } @else { <p class="muted">Cargando…</p> }
  `,
})
export class LeadDetallePage {
  private api = inject(ApiService);
  id = input.required<string>();
  d = signal<any>(null);
  mensaje = signal<any>(null);
  msg = signal('');
  ocupado = signal(false);
  texto = ''; canal = 'whatsapp'; idioma = '';

  constructor() { effect(() => { const id = Number(this.id()); if (id) this.cargar(id); }); }
  cargar(id: number): void { this.api.lead(id).subscribe((d) => this.d.set(d)); }
  revisar(dec: 'aprobar' | 'descartar'): void { this.api.revisar(Number(this.id()), dec).subscribe(() => this.cargar(Number(this.id()))); }
  verMensaje(): void { this.ocupado.set(true); this.api.mensaje(Number(this.id()), 'correo', this.idioma).subscribe({ next: (m) => { this.mensaje.set(m); this.ocupado.set(false); }, error: () => this.ocupado.set(false) }); }
  responder(): void {
    this.ocupado.set(true);
    this.api.respuesta(Number(this.id()), this.texto, this.canal).subscribe({ next: (r) => { this.msg.set(`Clasificada como ${r.clasificacion} (${r.motor}).`); this.texto = ''; this.cargar(Number(this.id())); this.ocupado.set(false); }, error: (e) => { this.msg.set(e.message); this.ocupado.set(false); } });
  }
  titulo(s: string): string { return (s || '').toLowerCase().replace(/(^|\s)\S/g, (c) => c.toUpperCase()); }
  pares(o: any): [string, string][] {
    if (!o || typeof o !== 'object') return [];
    return Object.entries(o).map(([k, v]) => [k.replace(/_/g, ' '), typeof v === 'object' ? JSON.stringify(v) : String(v)]);
  }
  fecha(iso: string | null): string { if (!iso) return '–'; try { return new Date(iso + (iso.endsWith('Z') ? '' : 'Z')).toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' }); } catch { return iso; } }
}
