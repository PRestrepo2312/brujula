import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiService, Lead } from '../core/api.service';

@Component({
  selector: 'pagina-leads',
  imports: [FormsModule, RouterLink],
  template: `
    <h1>Leads <em>del perfil</em></h1>
    <div class="acciones" style="margin:12px 0">
      <input [(ngModel)]="q" placeholder="buscar por nombre" style="width:220px" (keyup.enter)="cargar()">
      <select [(ngModel)]="estado" style="width:170px" (change)="cargar()">
        <option value="">todos</option>
        @for (e of ['pasa','revisar','descarta','listo','contactado','respondio','calificado','no_calificado','baja']; track e) {<option [value]="e">{{ e }}</option>}
      </select>
      <input [(ngModel)]="fuente" placeholder="fuente" style="width:120px" (keyup.enter)="cargar()">
      <button class="boton sec" (click)="cargar()">Filtrar</button>
      <button class="boton gris" (click)="exportar()">Exportar CSV</button>
      @if (urlExport()) {<a [href]="urlExport()" target="_blank">Descargar (15 min)</a>}
    </div>
    <div class="tarjeta">
      <table>
        <thead><tr><th>Empresa</th><th>Fuente</th><th>Sector</th><th>Ciudad</th><th>Canales</th><th>ICP</th><th>Estado</th><th>Señales</th></tr></thead>
        <tbody>
          @for (l of leads(); track l.id) {
            <tr><td><a [routerLink]="['/leads', l.id]">{{ titulo(l.razon_social) }}</a> @if ((l.fuentes_todas?.length ?? 0) > 1) {<span class="pill">{{ l.fuentes_todas?.length }} fuentes</span>}</td>
              <td>{{ l.fuente_clave }}</td><td>{{ l.sector }}</td><td>{{ titulo(l.ciudad) }}</td><td>{{ l.canales?.join(', ') }}</td>
              <td class="n"><span class="pill" [class]="'pill ' + l.icp_estado">{{ l.icp_score ?? '–' }}</span></td><td>{{ l.estado }}</td>
              <td class="sec">{{ claves(l.senales) }}</td></tr>
          } @empty { <tr><td colspan="8" class="sec">Sin leads con esos filtros.</td></tr> }
        </tbody>
      </table>
    </div>
  `,
})
export class LeadsPage {
  private api = inject(ApiService);
  q = ''; estado = ''; fuente = '';
  leads = signal<Lead[]>([]);
  urlExport = signal('');

  constructor() { this.cargar(); }
  cargar(): void { this.api.leads({ q: this.q, estado: this.estado, fuente: this.fuente, limite: 300 }).subscribe((l) => this.leads.set(l)); }
  exportar(): void { this.api.exportar('leads').subscribe((r) => this.urlExport.set(r.url.startsWith('http') ? r.url : `${(this.api as any).base}${r.url}`)); }
  titulo(s: string): string { return (s || '').toLowerCase().replace(/(^|\s)\S/g, (c) => c.toUpperCase()); }
  claves(o: Record<string, unknown>): string { return Object.keys(o || {}).join(', '); }
}
