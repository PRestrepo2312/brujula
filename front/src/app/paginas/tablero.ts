import { DecimalPipe, KeyValuePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiService, Metricas } from '../core/api.service';

@Component({
  selector: 'pagina-tablero',
  imports: [DecimalPipe, KeyValuePipe, RouterLink],
  template: `
    <h1>Dónde conviene buscar, <em>medido</em></h1>
    @if (m(); as m) {
      <p class="sec">Calculado {{ m.calculado_en }} UTC</p>
      <div class="fila c4">
        <div class="tarjeta kpi"><b>{{ m.embudo.encontrados }}</b><span>leads encontrados · {{ m.embudo.del_perfil }} del perfil · {{ m.embudo.a_revisar }} por revisar</span></div>
        <div class="tarjeta kpi"><b>{{ m.embudo.contactados }}</b><span>contactados · {{ m.embudo.respondieron }} respondieron</span></div>
        <div class="tarjeta kpi"><b>{{ m.embudo.calificados }}</b><span>calificados por Dapta · {{ m.embudo.no_calificados }} no calificados</span></div>
        <div class="tarjeta kpi"><b>USD {{ m.embudo.costo_total_usd | number:'1.2-2' }}</b><span>gasto · CPL {{ m.embudo.cpl_global ?? '–' }} · CPLQ {{ m.embudo.cplq_global ?? '–' }}</span></div>
      </div>
      <div class="reco"><b>La brújula dice:</b> {{ m.recomendacion }}</div>
      <div class="fila c2">
        <div class="tarjeta">
          <h2>Por fuente × canal: las tres métricas</h2>
          <table>
            <thead><tr><th>Fuente + canal</th><th>Enviados</th><th>Respondieron</th><th>Calificados</th><th>Gasto</th><th>CPL</th><th>CPLQ</th><th>Speed (min)</th></tr></thead>
            <tbody>
              @for (c of m.cruces | keyvalue; track c.key) {
                <tr><td>{{ c.key.replace('|', ' + ') }}</td><td class="n">{{ c.value.enviados }}</td><td class="n">{{ c.value.respondieron }}</td><td class="n">{{ c.value.calificados }}</td>
                  <td class="n">{{ c.value.costo_usd | number:'1.3-3' }}</td><td class="n">{{ c.value.cpl ?? '–' }}</td><td class="n"><b>{{ c.value.cplq ?? '–' }}</b></td><td class="n">{{ c.value.speed_to_lead_min ?? '–' }}</td></tr>
              } @empty { <tr><td colspan="8" class="sec">Todavía no hay intentos. Cree un lote en Lotes.</td></tr> }
            </tbody>
          </table>
          <h2 style="margin-top:16px">Por fuente: costo por lead encontrado</h2>
          <table>
            <thead><tr><th>Fuente</th><th>Encontrados</th><th>Del perfil</th><th>Teléfono</th><th>Correo</th><th>Gasto</th><th>Por lead del perfil</th></tr></thead>
            <tbody>
              @for (f of m.fuentes | keyvalue; track f.key) {
                <tr><td>{{ f.key }}</td><td class="n">{{ f.value.encontrados }}</td><td class="n">{{ f.value.del_perfil }}</td><td class="n">{{ f.value.con_telefono }}</td><td class="n">{{ f.value.con_correo }}</td>
                  <td class="n">{{ f.value.costo_encontrar_usd | number:'1.4-4' }}</td><td class="n"><b>{{ f.value.costo_por_lead_encontrado ?? '–' }}</b></td></tr>
              } @empty { <tr><td colspan="7" class="sec">Sin leads. Empiece en <a routerLink="/buscar">Buscar</a>.</td></tr> }
            </tbody>
          </table>
        </div>
        <div class="tarjeta">
          <h2>Embudo</h2>
          @for (p of embudo(); track p.nombre) {
            <div style="margin:8px 0"><div style="display:flex;justify-content:space-between"><span>{{ p.nombre }}</span><b>{{ p.valor }}</b></div><div class="barra"><i [style.width.%]="p.pct"></i></div></div>
          }
          <h2 style="margin-top:16px">Por canal</h2>
          <table>
            <thead><tr><th>Canal</th><th>Enviados</th><th>Resp.</th><th>Tasa</th><th>Calif.</th><th>CPL</th><th>CPLQ</th></tr></thead>
            <tbody>
              @for (c of m.canales | keyvalue; track c.key) {
                <tr><td>{{ c.key }}</td><td class="n">{{ c.value.enviados }}</td><td class="n">{{ c.value.respondieron }}</td><td class="n">{{ c.value.tasa_respuesta != null ? (c.value.tasa_respuesta * 100 | number:'1.0-1') + '%' : '–' }}</td><td class="n">{{ c.value.calificados }}</td><td class="n">{{ c.value.cpl ?? '–' }}</td><td class="n"><b>{{ c.value.cplq ?? '–' }}</b></td></tr>
              } @empty { <tr><td colspan="7" class="sec">Sin intentos.</td></tr> }
            </tbody>
          </table>
          <div class="acciones" style="margin-top:14px">
            <button class="boton sec" (click)="sincronizar()" [disabled]="ocupado()">Sincronizar con Dapta</button>
            <button class="boton gris" (click)="simular()" [disabled]="ocupado()">Simular resultados (demo)</button>
          </div>
          @if (msg()) {<div class="ok-msg">{{ msg() }}</div>}
        </div>
      </div>
    } @else { <p class="sec">Cargando…</p> }
  `,
})
export class TableroPage {
  private api = inject(ApiService);
  m = signal<Metricas | null>(null);
  ocupado = signal(false);
  msg = signal('');

  constructor() { this.cargar(); }
  cargar(): void { this.api.metricas().subscribe((m) => this.m.set(m)); }

  embudo(): { nombre: string; valor: number; pct: number }[] {
    const e = this.m()?.embudo; if (!e) return [];
    const max = Math.max(1, e.encontrados);
    return [['Encontrados', e.encontrados], ['Del perfil', e.del_perfil], ['Contactados', e.contactados], ['Respondieron', e.respondieron], ['Calificados', e.calificados]]
      .map(([n, v]) => ({ nombre: n as string, valor: v as number, pct: Math.round(((v as number) / max) * 100) }));
  }

  sincronizar(): void {
    this.ocupado.set(true);
    this.api.sincronizar().subscribe({ next: (r) => { this.msg.set(JSON.stringify(r)); this.cargar(); this.ocupado.set(false); }, error: (e) => { this.msg.set(e.message); this.ocupado.set(false); } });
  }
  simular(): void {
    this.ocupado.set(true);
    this.api.simular().subscribe({ next: (r) => { this.msg.set(`Simulado: ${r.simulados} intentos, ${r.respondieron} respuestas, ${r.calificados} calificados (datos de demostración).`); this.cargar(); this.ocupado.set(false); }, error: () => this.ocupado.set(false) });
  }
}
