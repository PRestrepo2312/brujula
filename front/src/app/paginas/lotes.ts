import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';

@Component({
  selector: 'pagina-lotes',
  imports: [FormsModule],
  template: `
    <div class="page-head"><div><span class="eyebrow">Lotes</span><h1>Contactar <em>por tandas</em></h1><p>Cada lote reparte un número de contactos entre fuentes y canales; la brújula decide el reparto con lo que ya funcionó y lo explica en una frase.</p></div></div>
    <div class="grid cols-main">
      <div>
        <div class="card">
          <h2>Nuevo lote</h2>
          @if (estado(); as e) {
            @if (e.modo_prueba?.activo) {<div class="banner banner-warn"><b>Modo prueba.</b> El lote se arma con los leads reales (nombre, señales y pitch), pero la llamada se desvía a {{ e.modo_prueba.telefono || 'ningún número (falta TELEFONO_PRUEBA)' }} (una por lote) y los correos a {{ e.modo_prueba.correos.join(', ') || 'ningún correo' }}. Ningún lead recibe nada.</div>}
            @if (!e.ventana_ok) {
              @if (e.respetar_ley_2300 === false) {<div class="banner banner-info">Fuera del horario de la Ley 2300 ({{ e.razon }}). La empresa desactivó esa restricción en Configuración: el lote sale sin motivo y queda en la bitácora.</div>}
              @else {<div class="banner banner-warn"><b>Fuera del horario de la Ley 2300</b> ({{ e.razon }}). Para contactar igual escriba el motivo: queda en la bitácora con su usuario ({{ auth.email }}) y el horario de la secuencia de Dapta se abre hoy por dos horas.</div>}
            }
          }
          <div class="grid cols-2">
            <div class="field"><label>Cuántos leads</label><input type="number" [(ngModel)]="n" min="1" max="500"></div>
            <div class="field"><label>Reparto</label><select [(ngModel)]="modo"><option value="brujula">Lo decide la brújula</option><option value="manual">Manual (valores iniciales)</option></select></div>
          </div>
          @if (estado() && !estado().ventana_ok && estado().respetar_ley_2300 !== false) {<div class="field"><label>Motivo de la excepción de horario</label><input [(ngModel)]="motivo" placeholder="demo con los números del equipo"></div>}
          <button class="btn btn-primary btn-lg" (click)="crear()" [disabled]="ocupado()">{{ ocupado() ? 'Enviando…' : 'Preparar y enviar' }}</button>
          @if (resultado(); as r) {
            @if (r.error) {<div class="banner banner-danger">{{ r.error }}</div>} @else {
              <div class="banner banner-ok"><b>Lote {{ r.lote_id }}</b>: {{ r.intentos }} intentos. {{ r.explicacion }}</div>
              @if (pares(r.envio?.resultado).length) {<div class="choices">@for (p of pares(r.envio?.resultado); track p[0]) {<span class="tag">{{ p[0].split(':').join(' · ') }}: {{ p[1] }}</span>}</div>}
              @if (pares(r.omitidos).length) {<p class="small muted" style="margin-top:8px">Omitidos: @for (p of pares(r.omitidos); track p[0]) {<span>{{ p[0] }} ({{ p[1] }}) </span>}</p>}
            }
          }
        </div>
      </div>
      <div>
        <div class="card">
          <h2>Últimos lotes</h2>
          <div class="table-wrap"><table class="table">
            <thead><tr><th>#</th><th>Cuándo</th><th>Reparto</th><th>Explicación</th></tr></thead>
            <tbody>@for (l of lotes(); track l.id) {<tr><td class="muted">{{ l.id }}</td><td class="small">{{ fecha(l.creado_en) }}</td><td>{{ l.modo === 'brujula' ? 'brújula' : 'manual' }}@if (l.fuera_ventana) { <span class="tag tag-warn">excepción: {{ l.override_usuario || 'configuración' }}</span>}</td><td class="small muted">{{ l.explicacion }}</td></tr>} @empty {<tr><td colspan="4"><div class="empty">Sin lotes todavía.</div></td></tr>}</tbody>
          </table></div>
        </div>
        <div class="card">
          <h2>Bitácora</h2>
          <div class="table-wrap"><table class="table">
            <tbody>@for (b of bitacora(); track b.id) {<tr><td class="small muted" style="white-space:nowrap">{{ fecha(b.creado_en) }}</td><td><span class="tag">{{ b.tipo }}</span></td><td class="small">{{ b.mensaje }}</td></tr>} @empty {<tr><td><div class="empty">Sin eventos.</div></td></tr>}</tbody>
          </table></div>
        </div>
      </div>
    </div>
  `,
})
export class LotesPage {
  private api = inject(ApiService);
  auth = inject(AuthService);
  n = 20; modo = 'brujula'; motivo = '';
  estado = signal<any>(null);
  lotes = signal<any[]>([]);
  bitacora = signal<any[]>([]);
  resultado = signal<any>(null);
  ocupado = signal(false);

  constructor() { this.cargar(); }
  cargar(): void {
    this.api.estado().subscribe((e) => this.estado.set(e));
    this.api.lotes().subscribe((l) => this.lotes.set(l));
    this.api.bitacora(40).subscribe((b) => this.bitacora.set(b));
  }
  crear(): void {
    this.ocupado.set(true);
    this.api.lote({ n: this.n, modo: this.modo, motivo_override: this.motivo, usuario: this.auth.email })
      .subscribe({ next: (r) => { this.resultado.set(r); this.cargar(); this.ocupado.set(false); }, error: (e) => { this.resultado.set({ error: e.error?.error || e.message }); this.ocupado.set(false); } });
  }
  pares(o: any): [string, string][] { return o && typeof o === 'object' ? Object.entries(o).map(([k, v]) => [k, String(v)]) : []; }
  fecha(iso: string | null): string { if (!iso) return '–'; try { return new Date(iso + (iso.endsWith('Z') ? '' : 'Z')).toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' }); } catch { return iso; } }
}
