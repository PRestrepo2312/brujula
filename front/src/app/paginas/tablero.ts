import { DecimalPipe, KeyValuePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiService, Metricas } from '../core/api.service';

@Component({
  selector: 'pagina-tablero',
  imports: [DecimalPipe, KeyValuePipe, RouterLink],
  template: `
    <div class="page-head">
      <div><h1>Tablero</h1><p>Dónde conviene buscar y por qué canal, medido con lo que ya pasó.</p></div>
      <div class="row">
        <button class="btn btn-secondary" (click)="sincronizar()" [disabled]="ocupado()">Sincronizar con Dapta</button>
        <button class="btn btn-ghost" (click)="simular()" [disabled]="ocupado()">Simular resultados</button>
      </div>
    </div>
    @if (msg()) {<div class="banner banner-ok">{{ msg() }}</div>}
    @if (m(); as m) {
      <div class="grid cols-4">
        <div class="card kpi"><div class="label">Leads encontrados</div><div class="value">{{ m.embudo.encontrados }}</div><div class="sub">{{ m.embudo.del_perfil }} del perfil · {{ m.embudo.a_revisar }} por revisar</div></div>
        <div class="card kpi"><div class="label">Contactados</div><div class="value">{{ m.embudo.contactados }}</div><div class="sub">{{ m.embudo.respondieron }} respondieron</div></div>
        <div class="card kpi"><div class="label">Calificados por Dapta</div><div class="value">{{ m.embudo.calificados }}</div><div class="sub">{{ m.embudo.no_calificados }} no calificados</div></div>
        <div class="card kpi"><div class="label">Gasto total</div><div class="value">USD {{ m.embudo.costo_total_usd | number:'1.2-2' }}</div><div class="sub">CPL {{ m.embudo.cpl_global ?? '–' }} · CPLQ {{ m.embudo.cplq_global ?? '–' }}</div></div>
      </div>
      <div class="callout" style="margin-top:16px"><b>La brújula dice:</b> {{ m.recomendacion }}</div>
      <div class="grid cols-main" style="margin-top:16px">
        <div>
          <div class="card">
            <div class="card-head"><h2>Fuente y canal: las tres métricas</h2><span class="muted small">calculado {{ m.calculado_en }} UTC</span></div>
            <div class="table-wrap"><table class="table">
              <thead><tr><th>Fuente + canal</th><th class="num">Enviados</th><th class="num">Resp.</th><th class="num">Calif.</th><th class="num">Gasto</th><th class="num">CPL</th><th class="num">CPLQ</th><th class="num">Speed</th></tr></thead>
              <tbody>
                @for (c of m.cruces | keyvalue; track c.key) {
                  <tr><td>{{ c.key.replace('|', ' · ') }}</td><td class="num">{{ c.value.enviados }}</td><td class="num">{{ c.value.respondieron }}</td><td class="num">{{ c.value.calificados }}</td>
                    <td class="num">{{ c.value.costo_usd | number:'1.3-3' }}</td><td class="num">{{ c.value.cpl ?? '–' }}</td><td class="num"><b>{{ c.value.cplq ?? '–' }}</b></td><td class="num">{{ c.value.speed_to_lead_min != null ? c.value.speed_to_lead_min + ' min' : '–' }}</td></tr>
                } @empty { <tr><td colspan="8"><div class="empty"><b>Todavía no hay intentos</b>Cree un lote en <a routerLink="/lotes">Lotes</a> para empezar a medir.</div></td></tr> }
              </tbody>
            </table></div>
          </div>
          <div class="card">
            <h2>Por fuente: costo por lead encontrado</h2>
            <div class="table-wrap"><table class="table">
              <thead><tr><th>Fuente</th><th class="num">Encontrados</th><th class="num">Del perfil</th><th class="num">Con teléfono</th><th class="num">Con correo</th><th class="num">Gasto</th><th class="num">Por lead del perfil</th></tr></thead>
              <tbody>
                @for (f of m.fuentes | keyvalue; track f.key) {
                  <tr><td>{{ f.key }}</td><td class="num">{{ f.value.encontrados }}</td><td class="num">{{ f.value.del_perfil }}</td><td class="num">{{ f.value.con_telefono }}</td><td class="num">{{ f.value.con_correo }}</td>
                    <td class="num">{{ f.value.costo_encontrar_usd | number:'1.4-4' }}</td><td class="num"><b>{{ f.value.costo_por_lead_encontrado ?? '–' }}</b></td></tr>
                } @empty { <tr><td colspan="7"><div class="empty"><b>Sin leads</b>Empiece en <a routerLink="/buscar">Buscar</a>.</div></td></tr> }
              </tbody>
            </table></div>
          </div>
        </div>
        <div>
          <div class="card">
            <h2>Embudo</h2>
            @for (p of embudo(); track p.nombre) {
              <div style="margin:10px 0"><div class="row row-between"><span>{{ p.nombre }}</span><b class="mono">{{ p.valor }}</b></div><div class="bar"><i [style.width.%]="p.pct"></i></div></div>
            }
          </div>
          <div class="card">
            <h2>Por canal</h2>
            <div class="table-wrap"><table class="table">
              <thead><tr><th>Canal</th><th class="num">Enviados</th><th class="num">Resp.</th><th class="num">Tasa</th><th class="num">Calif.</th><th class="num">CPLQ</th></tr></thead>
              <tbody>
                @for (c of m.canales | keyvalue; track c.key) {
                  <tr><td>{{ c.key }}</td><td class="num">{{ c.value.enviados }}</td><td class="num">{{ c.value.respondieron }}</td><td class="num">{{ c.value.tasa_respuesta != null ? (c.value.tasa_respuesta * 100 | number:'1.0-1') + '%' : '–' }}</td><td class="num">{{ c.value.calificados }}</td><td class="num"><b>{{ c.value.cplq ?? '–' }}</b></td></tr>
                } @empty { <tr><td colspan="6"><div class="empty">Sin intentos.</div></td></tr> }
              </tbody>
            </table></div>
          </div>
        </div>
      </div>
    } @else { <p class="muted">Cargando…</p> }
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
    this.api.sincronizar().subscribe({
      next: (r) => { const d = r.dapta || {}; const w = r.whatsapp || {}; this.msg.set(`Dapta: ${d.llamadas_leidas ?? 0} llamadas leídas, ${d.intentos_actualizados ?? 0} intentos actualizados, ${d.calificaciones_nuevas ?? 0} calificaciones nuevas · WhatsApp: ${w.conversaciones ?? 0} conversaciones.`); this.cargar(); this.ocupado.set(false); },
      error: (e) => { this.msg.set(e.message); this.ocupado.set(false); } });
  }
  simular(): void {
    this.ocupado.set(true);
    this.api.simular().subscribe({ next: (r) => { this.msg.set(`Simulado: ${r.simulados} intentos, ${r.respondieron} respuestas, ${r.calificados} calificados (datos de demostración, marcados como tales).`); this.cargar(); this.ocupado.set(false); }, error: () => this.ocupado.set(false) });
  }
}
