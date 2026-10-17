import { JsonPipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';

@Component({
  selector: 'pagina-lotes',
  imports: [FormsModule, JsonPipe],
  template: `
    <h1>Lotes: <em>la brújula reparte</em></h1>
    <div class="fila c2">
      <div class="tarjeta">
        <h2>Nuevo lote</h2>
        @if (estado(); as e) {
          @if (e.modo_prueba?.activo) {<div class="aviso">Modo prueba: el lote se arma con los leads reales (nombre, señales y pitch), pero la llamada se desvía a {{ e.modo_prueba.telefono || 'ningún número (falta TELEFONO_PRUEBA)' }} (una por lote) y los correos a {{ e.modo_prueba.correos.join(', ') || 'ningún correo' }}. Ningún lead recibe nada.</div>}
          @if (!e.ventana_ok) {
            @if (e.respetar_ley_2300 === false) {<div class="aviso">Fuera del horario de la Ley 2300 ({{ e.razon }}): la empresa desactivó esa restricción en Configuración, así que el lote sale sin motivo y queda en la bitácora.</div>}
            @else {<div class="aviso">Fuera de la ventana de la Ley 2300 ({{ e.razon }}). Para contactar igual escriba el motivo: queda en la bitácora con su usuario ({{ auth.email }}) y el horario de la secuencia de Dapta se abre hoy por dos horas.</div>}
          }
        }
        <div class="fila c2" style="margin:0 0 10px">
          <div><label>Cuántos leads</label><input type="number" [(ngModel)]="n" min="1" max="500"></div>
          <div><label>Modo</label><select [(ngModel)]="modo"><option value="brujula">La brújula reparte</option><option value="manual">Manual (priors)</option></select></div>
        </div>
        @if (estado() && !estado().ventana_ok && estado().respetar_ley_2300 !== false) {<div><label>Motivo del override</label><input [(ngModel)]="motivo" placeholder="p. ej. demo con números del equipo"></div>}
        <div class="acciones" style="margin-top:12px"><button class="boton" (click)="crear()" [disabled]="ocupado()">Preparar y enviar</button></div>
        @if (resultado(); as r) {
          @if (r.error) {<div class="aviso">{{ r.error }}</div>} @else {
            <div class="ok-msg">Lote {{ r.lote_id }}: {{ r.intentos }} intentos. {{ r.explicacion }}</div>
            <p class="sec">Envío: {{ r.envio?.resultado | json }} · omitidos: {{ r.omitidos | json }}</p>
          }
        }
      </div>
      <div class="tarjeta">
        <h2>Últimos lotes</h2>
        <table><thead><tr><th>#</th><th>Cuándo</th><th>Modo</th><th>Reparto y explicación</th></tr></thead>
          <tbody>@for (l of lotes(); track l.id) {<tr><td>{{ l.id }}</td><td>{{ l.creado_en }}</td><td>{{ l.modo }}@if (l.fuera_ventana) { <span class="pill descarta">override: {{ l.override_usuario }}</span>}</td><td class="sec">{{ l.explicacion }}</td></tr>} @empty {<tr><td colspan="4" class="sec">Sin lotes.</td></tr>}</tbody></table>
        <h2 style="margin-top:14px">Bitácora</h2>
        <table><tbody>@for (b of bitacora(); track b.id) {<tr><td class="sec" style="white-space:nowrap">{{ b.creado_en }}</td><td><span class="pill">{{ b.tipo }}</span></td><td>{{ b.mensaje }}</td></tr>}</tbody></table>
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
}
