import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ApiService, Lead } from '../core/api.service';

const ESTADOS: [string, string][] = [['', 'Todos los estados'], ['listo', 'Listos para contactar'], ['contactado', 'Contactados'], ['respondio', 'Respondieron'],
  ['calificado', 'Calificados'], ['no_calificado', 'No calificados'], ['nuevo', 'Nuevos (sin puntuar)'], ['descartado', 'Descartados'], ['baja', 'Baja']];

@Component({
  selector: 'pagina-leads',
  imports: [FormsModule],
  template: `
    <div class="page-head">
      <div><span class="eyebrow">Leads</span><h1>Las empresas <em>encontradas</em></h1><p>Cuánto encaja cada una con su cliente ideal y qué ha pasado con ella.</p></div>
      <div class="row"><button class="btn btn-secondary" (click)="exportar()">Exportar CSV</button>@if (urlExport()) {<a [href]="urlExport()" target="_blank">Descargar (15 min)</a>}</div>
    </div>
    <div class="card">
      <div class="row" style="margin-bottom:12px">
        <input [(ngModel)]="q" placeholder="Buscar por nombre" style="max-width:260px" (keyup.enter)="cargar()">
        <select [(ngModel)]="estado" style="max-width:220px" (change)="cargar()">@for (e of estados; track e[0]) {<option [value]="e[0]">{{ e[1] }}</option>}</select>
        <select [(ngModel)]="icp" style="max-width:190px" (change)="cargar()"><option value="">Encaje: todos</option><option value="pasa">Encajan</option><option value="revisar">Por revisar</option><option value="descarta">No encajan</option></select>
        <input [(ngModel)]="fuente" placeholder="Fuente (reps, men…)" style="max-width:170px" (keyup.enter)="cargar()">
        <button class="btn btn-secondary" (click)="cargar()">Filtrar</button>
        <span class="muted small">{{ leads().length }} leads</span>
      </div>
      <div class="table-wrap"><table class="table">
        <thead><tr><th>Empresa</th><th>Fuente</th><th>Sector</th><th>Ciudad</th><th>Canales</th><th class="num">Encaje</th><th>Estado</th><th>Señales</th></tr></thead>
        <tbody>
          @for (l of leads(); track l.id) {
            <tr class="row-link" (click)="abrir(l.id)">
              <td><b>{{ titulo(l.razon_social) }}</b> @if ((l.fuentes_todas?.length ?? 0) > 1) {<span class="tag tag-info">{{ l.fuentes_todas?.length }} fuentes</span>}</td>
              <td>{{ l.fuente_clave }}</td><td>{{ l.sector }}</td><td>{{ titulo(l.ciudad) }}</td><td>{{ l.canales?.join(', ') || '–' }}</td>
              <td class="num"><span class="tag" [class]="'tag ' + l.icp_estado">{{ l.icp_score != null ? (l.icp_score * 100).toFixed(0) + ' %' : '–' }}</span></td><td><span class="tag" [class]="'tag ' + claseEstado(l.estado)">{{ nombreEstado(l.estado) }}</span></td>
              <td class="muted small">{{ claves(l.senales) }}</td>
            </tr>
          } @empty { <tr><td colspan="8"><div class="empty"><b>Sin leads con esos filtros</b>Cambie el filtro o haga una búsqueda nueva.</div></td></tr> }
        </tbody>
      </table></div>
    </div>
  `,
})
export class LeadsPage {
  private api = inject(ApiService);
  private router = inject(Router);
  q = ''; estado = ''; fuente = ''; icp = '';
  estados = ESTADOS;
  leads = signal<Lead[]>([]);
  urlExport = signal('');

  constructor() { this.cargar(); }
  cargar(): void {
    this.api.leads({ q: this.q, estado: this.estado, fuente: this.fuente, limite: 300 }).subscribe((l) => this.leads.set(this.icp ? l.filter((x) => x.icp_estado === this.icp) : l));
  }
  abrir(id: number): void { this.router.navigate(['/leads', id]); }
  exportar(): void { this.api.exportar('leads').subscribe((r) => this.urlExport.set(r.url.startsWith('http') ? r.url : `${(this.api as any).base}${r.url}`)); }
  titulo(s: string): string { return (s || '').toLowerCase().replace(/(^|\s)\S/g, (c) => c.toUpperCase()); }
  claves(o: Record<string, unknown>): string { return Object.keys(o || {}).join(', '); }
  nombreEstado(e: string): string {
    return ({ nuevo: 'nuevo', listo: 'listo', contactado: 'contactado', respondio: 'respondió', calificado: 'calificado', no_calificado: 'no calificado', descartado: 'descartado', baja: 'baja' } as Record<string, string>)[e] || e;
  }
  claseEstado(e: string): string { return e === 'calificado' ? 'tag-ok' : e === 'respondio' ? 'tag-accent' : e === 'baja' || e === 'descartado' || e === 'no_calificado' ? 'tag-danger' : e === 'contactado' ? 'tag-info' : ''; }
}
