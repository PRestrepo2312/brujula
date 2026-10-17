import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiService } from '../core/api.service';

@Component({
  selector: 'pagina-notificaciones',
  imports: [RouterLink],
  template: `
    <h1>Notificaciones</h1>
    <div class="acciones" style="margin:10px 0"><button class="boton gris" (click)="leerTodas()">Marcar todas como leídas</button></div>
    <div class="tarjeta">
      <table><thead><tr><th>Cuándo</th><th>Tipo</th><th>Mensaje</th><th>Correo</th></tr></thead>
        <tbody>@for (n of lista(); track n.id) {
          <tr [style.fontWeight]="n.leida ? 400 : 600"><td class="sec" style="white-space:nowrap">{{ n.creado_en }}</td><td><span class="pill" [class]="'pill ' + clase(n.tipo)">{{ n.tipo }}</span></td>
            <td>{{ n.mensaje }} @if (n.lead_id) {<a [routerLink]="['/leads', n.lead_id]">ver lead</a>}</td><td>{{ n.enviada_correo ? 'enviado' : '–' }}</td></tr>
        } @empty {<tr><td colspan="4" class="sec">Nada todavía. Las notificaciones llegan cuando termina una búsqueda, sale un lote, un lead responde o Dapta lo califica.</td></tr>}</tbody></table>
    </div>
  `,
})
export class NotificacionesPage {
  private api = inject(ApiService);
  lista = signal<any[]>([]);
  constructor() { this.cargar(); }
  cargar(): void { this.api.notificaciones(false).subscribe((n) => this.lista.set(n)); }
  leerTodas(): void { this.api.leerNotificaciones().subscribe(() => this.cargar()); }
  clase(t: string): string { return t === 'calificado' ? 'pasa' : t === 'baja' ? 'descarta' : t === 'respondio' ? 'revisar' : ''; }
}
