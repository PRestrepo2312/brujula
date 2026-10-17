import { DecimalPipe, JsonPipe } from '@angular/common';
import { Component, inject, input, signal, effect } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiService } from '../core/api.service';

@Component({
  selector: 'pagina-lead-detalle',
  imports: [FormsModule, RouterLink, JsonPipe, DecimalPipe],
  template: `
    @if (d(); as d) {
      <p><a routerLink="/leads">Leads</a> › {{ titulo(d.lead.razon_social) }}</p>
      <h1>{{ titulo(d.lead.razon_social) }}</h1>
      <p class="sec">{{ d.lead.fuente_clave }} · {{ d.lead.sector }} {{ d.lead.subsector }} · {{ titulo(d.lead.ciudad) }}@if (d.lead.identificacion) { · NIT {{ d.lead.identificacion }}} · fuentes: {{ d.lead.fuentes_todas?.join(', ') }}</p>
      <div class="fila c3">
        <div class="tarjeta"><h2>Contacto</h2>
          <p>Teléfono: <b>{{ d.lead.telefono || '–' }}</b> {{ d.lead.telefono_tipo }}<br>Correo: <b>{{ d.lead.correo || '–' }}</b><br>Web: {{ d.lead.sitio_web || '–' }}<br>Canales: {{ d.lead.canales?.join(', ') }}</p>
          <p class="sec">Señales: {{ d.lead.senales | json }}</p></div>
        <div class="tarjeta"><h2>ICP <span class="pill" [class]="'pill ' + d.lead.icp_estado">{{ d.lead.icp_estado }} · {{ d.lead.icp_score }}</span></h2>
          <p class="sec">{{ d.lead.icp_detalle | json }}</p>
          @if (d.lead.icp_estado === 'revisar') {<div class="acciones"><button class="boton" (click)="revisar('aprobar')">Aprobar</button><button class="boton gris" (click)="revisar('descartar')">Descartar</button></div>}
        </div>
        <div class="tarjeta"><h2>Mensaje que redactaría el agente</h2>
          <div class="acciones">
            <select [(ngModel)]="idioma" style="width:170px"><option value="">Idioma de la fuente</option><option value="es">Español</option><option value="pt">Português</option><option value="en">English</option></select>
            <button class="boton sec" (click)="verMensaje()" [disabled]="ocupado()">Vista previa (correo)</button>
          </div>
          <p class="sec" style="margin-top:6px">Con agente de texto activo, redacta directo en ese idioma; sin agente, usa la plantilla en ese idioma.</p>
          @if (mensaje(); as m) {<p style="white-space:pre-wrap;font-size:13px;margin-top:10px">{{ m.texto }}</p><p class="sec">idioma: {{ m.idioma }} · motor: {{ m.motor }} · USD {{ m.costo_usd | number:'1.4-4' }}</p>}
        </div>
      </div>
      <div class="fila c2">
        <div class="tarjeta"><h2>Intentos de contacto</h2>
          <table><thead><tr><th>#</th><th>Canal</th><th>Proveedor</th><th>Estado</th><th>Clasificación</th><th>Costo USD</th><th>Enviado</th></tr></thead>
            <tbody>@for (it of d.intentos; track it.id) {<tr><td>{{ it.id }}</td><td>{{ it.canal }}</td><td>{{ it.proveedor }}</td><td>{{ it.estado }}@if (it.fuera_ventana) { <span class="pill descarta">override</span>}</td><td>{{ it.clasificacion }}</td><td class="n">{{ it.costo_usd | number:'1.4-4' }}</td><td>{{ it.enviado_en || '–' }}</td></tr>} @empty {<tr><td colspan="7" class="sec">Sin intentos.</td></tr>}</tbody></table>
          <h2 style="margin-top:14px">Calificación de Dapta</h2>
          @for (c of d.calificaciones; track c.id) {<p><span class="pill" [class]="'pill ' + (c.resultado === 'calificado' ? 'pasa' : (c.resultado === 'pendiente' ? 'revisar' : 'descarta'))">{{ c.resultado }}</span> <span class="sec">{{ c.datos | json }}</span></p>} @empty {<p class="sec">Todavía no ha pasado por el calificador.</p>}
        </div>
        <div class="tarjeta"><h2>Registrar una respuesta (WhatsApp o llamada manual)</h2>
          <textarea rows="3" [(ngModel)]="texto" placeholder="Lo que respondió la empresa; el agente lo clasifica"></textarea>
          <div class="acciones" style="margin-top:8px"><select [(ngModel)]="canal" style="width:140px"><option value="whatsapp">whatsapp</option><option value="voz">voz</option><option value="correo">correo</option></select>
            <button class="boton" (click)="responder()" [disabled]="!texto.trim() || ocupado()">Clasificar y guardar</button></div>
          @if (msg()) {<div class="ok-msg">{{ msg() }}</div>}
          <h2 style="margin-top:14px">Duplicados fusionados</h2>
          @for (x of d.duplicados; track x.id) {<p>{{ x.razon_social }} <span class="sec">({{ x.fuente }})</span></p>} @empty {<p class="sec">Ninguno.</p>}
        </div>
      </div>
    } @else { <p class="sec">Cargando…</p> }
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
}
