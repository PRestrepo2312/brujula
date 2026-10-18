import { DecimalPipe, KeyValuePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiService, Metricas } from '../core/api.service';
import { nombreCanal, nombreCruce, nombreFuente } from '../core/nombres';

interface Burbuja { clave: string; nombre: string; cpl: number; tasa: number; n: number; num: number; x: number; y: number; r: number; zona: string; color: string }

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
      <div class="grid cols-2" style="margin-top:16px">
        <div class="card">
          <div class="card-head"><h2>Costo contra calidad</h2><span class="muted small">cada burbuja es una fuente con un canal; su tamaño, cuántos contactos</span></div>
          @if (cuadro().burbujas.length) {
            <svg viewBox="0 0 520 300" class="cuadrantes" role="img" aria-label="Costo por respuesta contra porcentaje de calificados">
              <rect x="56" y="14" width="448" height="236" fill="#F7F9FD" stroke="#E4E8F0"/>
              <line [attr.x1]="56 + 448 * cuadro().xMed" y1="14" [attr.x2]="56 + 448 * cuadro().xMed" y2="250" stroke="#CBD3E1" stroke-dasharray="4 4"/>
              <line x1="56" [attr.y1]="250 - 236 * cuadro().yMed" x2="504" [attr.y2]="250 - 236 * cuadro().yMed" stroke="#CBD3E1" stroke-dasharray="4 4"/>
              <text x="62" y="30" class="cuadrante" style="fill:#0F6E56">Baratos y buenos</text><text x="498" y="30" class="cuadrante" text-anchor="end" style="fill:#2563EB">Caros y buenos</text>
              <text x="62" y="244" class="cuadrante" style="fill:#B7791F">Baratos y flojos</text><text x="498" y="244" class="cuadrante" text-anchor="end" style="fill:#B91C1C">Caros y flojos</text>
              @for (b of cuadro().burbujas; track b.clave) {
                <circle [attr.cx]="b.x" [attr.cy]="b.y" [attr.r]="b.r" [attr.fill]="b.color" fill-opacity=".22" [attr.stroke]="b.color" stroke-width="1.5"/>
                <text [attr.x]="b.x" [attr.y]="b.y + 4" text-anchor="middle" class="numero">{{ b.num }}</text>
              }
              <text x="280" y="282" text-anchor="middle" class="eje">Costo por cada respuesta, en USD: más barato a la izquierda</text>
              <text x="18" y="132" text-anchor="middle" class="eje" transform="rotate(-90 18 132)">Calificados por Dapta, %: mejor arriba</text>
            </svg>
            <ol class="leyenda">
              @for (b of cuadro().burbujas; track b.clave) {
                <li><span class="punto" [style.background]="b.color">{{ b.num }}</span><div><b>{{ b.nombre }}</b><div class="muted small">{{ b.n }} contactos · USD {{ b.cpl | number:'1.2-2' }} por respuesta · {{ b.tasa * 100 | number:'1.0-0' }} % calificados · {{ b.zona }}</div></div></li>
              }
            </ol>
          } @else { <div class="empty"><b>Todavía no hay respuestas</b>Cuando los leads respondan y Dapta califique, cada fuente y canal aparece aquí según lo que cuesta y lo que trae.</div> }
        </div>
        <div class="card">
          <div class="card-head"><h2>Brújula contra pauta</h2><span class="muted small">el costo de pauta lo escribe la empresa, no es un dato inventado</span></div>
          @if (m.comparacion_pauta; as cp) {
            <div class="grid cols-2">
              <div class="kpi" style="padding:0"><div class="label"><span>Con Brújula</span></div><div class="value" style="font-size:30px">USD {{ cp.brujula_usd != null ? (cp.brujula_usd | number:'1.2-2') : '–' }}</div><div class="sub" style="border:0;padding-top:4px">por lead {{ cp.base === 'calificado' ? 'calificado' : cp.base === 'respuesta' ? 'que respondió' : '(sin datos todavía)' }}</div></div>
              <div class="kpi" style="padding:0"><div class="label"><span>Con pauta</span></div><div class="value" style="font-size:30px">USD {{ cp.pauta_usd | number:'1.2-2' }}</div><div class="sub" style="border:0;padding-top:4px">por lead, según la empresa</div></div>
            </div>
            @if (cp.veces) {<div class="banner banner-ok" style="margin-bottom:0"><b>{{ cp.veces }} veces más barato</b> con Brújula que con pauta, medido con lo que ya pasó.</div>}
            @else {<div class="banner" style="margin-bottom:0">Cuando haya leads que respondan o se califiquen, aquí aparece el ahorro frente a la pauta.</div>}
          } @else {
            <div class="empty"><b>¿Cuánto le cuesta hoy un cliente por pauta?</b>Dígaselo a la brújula en el <a routerLink="/inicio">asistente de inicio</a> o escríbalo en <a routerLink="/configuracion">Configuración</a> y aquí verá el ahorro.</div>
          }
        </div>
      </div>
      <div class="grid cols-main" style="margin-top:16px">
        <div>
          <div class="card">
            <div class="card-head"><h2>Fuente y canal: las tres métricas</h2><span class="muted small">calculado {{ fecha(m.calculado_en) }}</span></div>
            <div class="table-wrap"><table class="table">
              <thead><tr><th>Fuente + canal</th><th class="num">Enviados</th><th class="num">Respondieron</th><th class="num">Calificados</th><th class="num">Gasto USD</th><th class="num">Costo/respuesta</th><th class="num">Costo/calificado</th><th class="num">Tiempo</th></tr></thead>
              <tbody>
                @for (c of m.cruces | keyvalue; track c.key) {
                  <tr><td>{{ nombreCruce(c.key) }}</td><td class="num">{{ c.value.enviados }}</td><td class="num">{{ c.value.respondieron }}</td><td class="num">{{ c.value.calificados }}</td>
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
                  <tr><td>{{ nombreFuente(f.key) }}</td><td class="num">{{ f.value.encontrados }}</td><td class="num">{{ f.value.del_perfil }}</td><td class="num">{{ f.value.con_telefono }}</td><td class="num">{{ f.value.con_correo }}</td>
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
              <thead><tr><th>Canal</th><th class="num">Enviados</th><th class="num">Resp.</th><th class="num">% resp.</th><th class="num">Calif.</th><th class="num">% calif.</th><th class="num">Costo/calificado</th></tr></thead>
              <tbody>
                @for (c of m.canales | keyvalue; track c.key) {
                  <tr><td>{{ nombreCanal(c.key) }}</td><td class="num">{{ c.value.enviados }}</td><td class="num">{{ c.value.respondieron }}</td><td class="num">{{ c.value.tasa_respuesta != null ? (c.value.tasa_respuesta * 100 | number:'1.0-1') + '%' : '–' }}</td><td class="num">{{ c.value.calificados }}</td><td class="num"><b>{{ c.value.tasa_calificacion != null ? (c.value.tasa_calificacion * 100 | number:'1.0-1') + '%' : '–' }}</b></td><td class="num"><b>{{ c.value.cplq ?? '–' }}</b></td></tr>
                } @empty { <tr><td colspan="7"><div class="empty">Sin contactos.</div></td></tr> }
              </tbody>
            </table></div>
          </div>
        </div>
      </div>
    } @else { <p class="muted">Cargando…</p> }
  `,
  styles: [`
    .cuadrantes { width: 100%; height: auto; display: block; }
    .cuadrante { font-family: var(--mono); font-size: 9px; fill: #8A94A8; letter-spacing: .08em; text-transform: uppercase; }
    .numero { font-family: var(--mono); font-size: 11px; font-weight: 700; fill: var(--ink); }
    .eje { font-size: 11px; fill: var(--muted); }
    .leyenda { list-style: none; margin: 10px 0 0; padding: 0; display: grid; gap: 8px; }
    .leyenda li { display: flex; gap: 10px; align-items: flex-start; font-size: 13px; }
    .punto { flex: none; width: 22px; height: 22px; border-radius: 50%; color: #fff; font: 700 11px/22px var(--mono); text-align: center; }
  `],
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

  nombreCruce = nombreCruce; nombreFuente = nombreFuente; nombreCanal = nombreCanal;

  /** Cuadrante costo contra calidad: X = costo por respuesta (USD), Y = % de calificados sobre los que respondieron, tamaño = contactos.
   *  Las líneas punteadas son la mediana de cada eje; la zona de cada burbuja sale de ahí y se repite en la leyenda numerada. */
  cuadro(): { burbujas: Burbuja[]; xMed: number; yMed: number } {
    const cruces = this.m()?.cruces || {};
    const p = Object.entries(cruces).filter(([, v]: any) => v.cpl != null && v.enviados > 0)
      .map(([k, v]: any) => ({ clave: k, nombre: nombreCruce(k), cpl: v.cpl as number, tasa: (v.tasa_calificacion ?? 0) as number, n: v.enviados as number }))
      .sort((a, b) => a.cpl - b.cpl);
    if (!p.length) return { burbujas: [], xMed: 0.5, yMed: 0.5 };
    const maxCpl = Math.max(...p.map((q) => q.cpl), 0.01); const maxN = Math.max(...p.map((q) => q.n), 1);
    const med = (xs: number[]) => { const s = [...xs].sort((a, c) => a - c); const i = Math.floor(s.length / 2); return s.length % 2 ? s[i] : (s[i - 1] + s[i]) / 2; };
    const xs = p.map((q) => 0.08 + 0.84 * (q.cpl / maxCpl)); const ys = p.map((q) => 0.1 + 0.8 * Math.min(1, q.tasa));
    const xMed = med(xs), yMed = med(ys);
    const burbujas = p.map((q, i) => {
      const barato = xs[i] <= xMed, bueno = ys[i] >= yMed;
      const zona = barato && bueno ? 'barato y bueno' : bueno ? 'caro y bueno' : barato ? 'barato y flojo' : 'caro y flojo';
      const color = barato && bueno ? '#0F6E56' : bueno ? '#2563EB' : barato ? '#B7791F' : '#B91C1C';
      return { ...q, num: i + 1, x: 56 + 448 * xs[i], y: 250 - 236 * ys[i], r: 9 + 20 * Math.sqrt(q.n / maxN), zona, color };
    });
    return { burbujas, xMed, yMed };
  }
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
