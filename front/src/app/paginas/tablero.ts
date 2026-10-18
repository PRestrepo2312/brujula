import { DecimalPipe, KeyValuePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiService, Metricas } from '../core/api.service';

@Component({
  selector: 'pagina-tablero',
  imports: [DecimalPipe, KeyValuePipe, RouterLink],
  template: `
    <div class="page-head">
      <div>
        <span class="eyebrow">Tablero · {{ hoy }}</span>
        <h1 class="hero">Dónde buscar, <em>por qué canal</em>, y cuánto cuesta.</h1>
        <p>Medido con lo que ya pasó: cada fuente y cada canal con su costo por cliente calificado.</p>
      </div>
      <div class="row">
        <button class="btn btn-secondary" (click)="sincronizar()" [disabled]="ocupado()">Sincronizar con Dapta</button>
        <button class="btn btn-ghost" (click)="simular()" [disabled]="ocupado()">Datos de ejemplo</button>
      </div>
    </div>
    @if (msg()) {<div class="banner banner-ok">{{ msg() }}</div>}
    @if (estado()?.perfil_completo === false) {<div class="banner banner-info"><b>Falta decir cómo se presenta su empresa.</b> Los mensajes y la llamada hablan en su nombre: complete el <a routerLink="/inicio">asistente de inicio</a> (tres pasos).</div>}
    @if (m(); as m) {
      <div class="grid cols-4">
        <div class="card kpi kpi-dark"><div class="label"><span>Leads encontrados</span><span>01</span></div><div class="value">{{ m.embudo.encontrados }}</div><div class="sub">{{ m.embudo.del_perfil }} encajan con su cliente ideal · {{ m.embudo.a_revisar }} por revisar</div></div>
        <div class="card kpi"><div class="label"><span>Contactados</span><span>02</span></div><div class="value">{{ m.embudo.contactados }}</div><div class="sub">{{ m.embudo.respondieron }} respondieron</div></div>
        <div class="card kpi kpi-blue"><div class="label"><span>Calificados por Dapta</span><span>03</span></div><div class="value">{{ m.embudo.calificados }}</div><div class="sub">{{ m.embudo.no_calificados }} no calificados</div></div>
        <div class="card kpi kpi-accent"><div class="label"><span>Gasto total · USD</span><span>04</span></div><div class="value">{{ m.embudo.costo_total_usd | number:'1.2-2' }}</div><div class="sub">por respuesta {{ m.embudo.cpl_global ?? '–' }} · por calificado {{ m.embudo.cplq_global ?? '–' }}</div></div>
      </div>
      <div class="callout" style="margin-top:16px">
        <div class="icon"><svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.6"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="1.3" fill="#fff"/><path d="M15.6 8.4 13.5 13.5 8.4 15.6l2.1-5.1z" fill="#93B4FF" stroke="none"/></svg></div>
        <div><span class="eyebrow">La brújula dice</span><div class="texto">{{ m.recomendacion }}</div></div>
      </div>
      <div class="grid cols-main" style="margin-top:16px">
        <div>
          <div class="card">
            <div class="card-head"><h2>Fuente y canal: las tres métricas</h2><span class="muted small">calculado {{ fecha(m.calculado_en) }}</span></div>
            <div class="table-wrap"><table class="table">
              <thead><tr><th>Fuente + canal</th><th class="num">Enviados</th><th class="num">Respondieron</th><th class="num">Calificados</th><th class="num">Gasto USD</th><th class="num">Costo/respuesta</th><th class="num">Costo/calificado</th><th class="num">Tiempo</th></tr></thead>
              <tbody>
                @for (c of m.cruces | keyvalue; track c.key) {
                  <tr><td>{{ c.key.replace('|', ' · ') }}</td><td class="num">{{ c.value.enviados }}</td><td class="num">{{ c.value.respondieron }}</td><td class="num">{{ c.value.calificados }}</td>
                    <td class="num">{{ c.value.costo_usd | number:'1.3-3' }}</td><td class="num">{{ c.value.cpl ?? '–' }}</td><td class="num"><b>{{ c.value.cplq ?? '–' }}</b></td><td class="num">{{ c.value.speed_to_lead_min != null ? c.value.speed_to_lead_min + ' min' : '–' }}</td></tr>
                } @empty { <tr><td colspan="8"><div class="empty"><b>Todavía no hay contactos</b>Cree un lote en <a routerLink="/lotes">Lotes</a> para empezar a medir.</div></td></tr> }
              </tbody>
            </table></div>
          </div>
          <div class="card">
            <h2>Por fuente: cuánto cuesta encontrar</h2>
            <div class="table-wrap"><table class="table">
              <thead><tr><th>Fuente</th><th class="num">Encontrados</th><th class="num">Encajan</th><th class="num">Con teléfono</th><th class="num">Con correo</th><th class="num">Gasto USD</th><th class="num">Por lead que encaja</th></tr></thead>
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
            <div class="card-head"><h2>Embudo</h2><span class="tag tag-info">{{ pctCalificados(m) }} calificado</span></div>
            @for (p of embudo(); track p.nombre) {
              <div style="margin:10px 0"><div class="row row-between"><span>{{ p.nombre }}</span><b class="mono">{{ p.valor }}</b></div><div class="bar"><i [style.width.%]="p.pct"></i></div></div>
            }
          </div>
          <div class="card">
            <h2>Por canal</h2>
            <div class="table-wrap"><table class="table">
              <thead><tr><th>Canal</th><th class="num">Enviados</th><th class="num">Resp.</th><th class="num">Tasa</th><th class="num">Calif.</th><th class="num">Costo/calificado</th></tr></thead>
              <tbody>
                @for (c of m.canales | keyvalue; track c.key) {
                  <tr><td>{{ c.key }}</td><td class="num">{{ c.value.enviados }}</td><td class="num">{{ c.value.respondieron }}</td><td class="num">{{ c.value.tasa_respuesta != null ? (c.value.tasa_respuesta * 100 | number:'1.0-1') + '%' : '–' }}</td><td class="num">{{ c.value.calificados }}</td><td class="num"><b>{{ c.value.cplq ?? '–' }}</b></td></tr>
                } @empty { <tr><td colspan="6"><div class="empty">Sin contactos.</div></td></tr> }
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
  estado = signal<any>(null);
  ocupado = signal(false);
  msg = signal('');
  hoy = new Date().toLocaleDateString('es-CO', { weekday: 'long', day: 'numeric', month: 'long' });

  constructor() { this.cargar(); }
  cargar(): void { this.api.metricas().subscribe((m) => this.m.set(m)); this.api.estado().subscribe({ next: (e) => this.estado.set(e), error: () => {} }); }

  embudo(): { nombre: string; valor: number; pct: number }[] {
    const e = this.m()?.embudo; if (!e) return [];
    const max = Math.max(1, e.encontrados);
    return [['Encontrados', e.encontrados], ['Encajan', e.del_perfil], ['Contactados', e.contactados], ['Respondieron', e.respondieron], ['Calificados', e.calificados]]
      .map(([n, v]) => ({ nombre: n as string, valor: v as number, pct: Math.round(((v as number) / max) * 100) }));
  }
  pctCalificados(m: Metricas): string { const c = m.embudo.contactados || 0; return c ? Math.round((m.embudo.calificados / c) * 100) + '%' : '0%'; }
  fecha(iso: string): string { try { return new Date(iso + (iso.endsWith('Z') ? '' : 'Z')).toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' }); } catch { return iso; } }

  sincronizar(): void {
    this.ocupado.set(true);
    this.api.sincronizar().subscribe({
      next: (r) => { const d = r.dapta || {}; const w = r.whatsapp || {}; this.msg.set(`Dapta: ${d.llamadas_leidas ?? 0} llamadas leídas, ${d.intentos_actualizados ?? 0} contactos actualizados, ${d.calificaciones_nuevas ?? 0} calificaciones nuevas · WhatsApp: ${w.conversaciones ?? 0} conversaciones.`); this.cargar(); this.ocupado.set(false); },
      error: (e) => { this.msg.set(e.message); this.ocupado.set(false); } });
  }
  simular(): void {
    this.ocupado.set(true);
    this.api.simular().subscribe({ next: (r) => { this.msg.set(`Datos de ejemplo: ${r.simulados} contactos, ${r.respondieron} respuestas, ${r.calificados} calificados (marcados como ejemplo, no cuentan como reales).`); this.cargar(); this.ocupado.set(false); }, error: () => this.ocupado.set(false) });
  }
}
