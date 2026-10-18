import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiService } from '../core/api.service';

@Component({
  selector: 'pagina-notificaciones',
  imports: [RouterLink],
  template: `
    <div class="page-head">
      <div><span class="eyebrow">Notificaciones</span><h1>Lo que <em>pasó</em></h1><p>Búsquedas que terminan, lotes que salen, leads que responden y calificaciones de Dapta.</p></div>
      <button class="btn btn-secondary" (click)="leerTodas()">Marcar todas como leídas</button>
    </div>
    <div class="card">
      <div class="table-wrap"><table class="table">
        <thead><tr><th>Cuándo</th><th>Tipo</th><th>Mensaje</th><th>Correo</th></tr></thead>
        <tbody>@for (n of lista(); track n.id) {
          <tr [style.fontWeight]="n.leida ? 400 : 600"><td class="small muted" style="white-space:nowrap">{{ fecha(n.creado_en) }}</td><td><span class="tag" [class]="'tag ' + clase(n.tipo)">{{ n.tipo }}</span></td>
            <td>{{ n.mensaje }} @if (n.lead_id) {<a [routerLink]="['/leads', n.lead_id]">ver lead</a>}</td><td class="small muted">{{ n.enviada_correo ? 'enviado' : '–' }}</td></tr>
        } @empty {<tr><td colspan="4"><div class="empty"><b>Nada todavía</b>Las notificaciones llegan cuando termina una búsqueda, sale un lote, un lead responde o Dapta lo califica.</div></td></tr>}</tbody>
      </table></div>
    </div>
  `,
})
export class NotificacionesPage {
  private api = inject(ApiService);
  lista = signal<any[]>([]);
  constructor() { this.cargar(); }
  cargar(): void { this.api.notificaciones(false).subscribe((n) => this.lista.set(n)); }
  leerTodas(): void { this.api.leerNotificaciones().subscribe(() => this.cargar()); }
  clase(t: string): string { return t === 'calificado' ? 'tag-ok' : t === 'baja' || t === 'no_calificado' ? 'tag-danger' : t === 'respondio' ? 'tag-accent' : t === 'lote' || t === 'busqueda' ? 'tag-info' : ''; }
  fecha(iso: string | null): string { if (!iso) return '–'; try { return new Date(iso + (iso.endsWith('Z') ? '' : 'Z')).toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' }); } catch { return iso; } }
}
