import { DecimalPipe } from '@angular/common';
import { Component, inject, OnDestroy, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiService } from '../core/api.service';
import { nombreFuente } from '../core/nombres';

/** Ciudades de Colombia con su posición (latitud, longitud) para dibujar los leads en un mapa de puntos. */
const CIUDADES: Record<string, [number, number]> = {
  BOGOTA: [4.711, -74.072], MEDELLIN: [6.244, -75.581], CALI: [3.452, -76.532], BARRANQUILLA: [10.969, -74.781], CARTAGENA: [10.391, -75.479],
  BUCARAMANGA: [7.119, -73.123], IBAGUE: [4.439, -75.232], PEREIRA: [4.814, -75.695], MANIZALES: [5.07, -75.514], CUCUTA: [7.894, -72.508],
  'SANTA MARTA': [11.241, -74.199], VILLAVICENCIO: [4.142, -73.627], PASTO: [1.214, -77.278], MONTERIA: [8.748, -75.882], NEIVA: [2.927, -75.282],
  ARMENIA: [4.534, -75.681], POPAYAN: [2.444, -76.614], VALLEDUPAR: [10.463, -73.253], SINCELEJO: [9.305, -75.398], TUNJA: [5.535, -73.367],
  SOLEDAD: [10.918, -74.765], SOACHA: [4.579, -74.217], BELLO: [6.339, -75.558], ENVIGADO: [6.168, -75.586], ITAGUI: [6.172, -75.611],
  RIOHACHA: [11.544, -72.907], QUIBDO: [5.692, -76.658], FLORENCIA: [1.614, -75.606], YOPAL: [5.337, -72.396], LETICIA: [-4.215, -69.941],
};

interface Punto { ciudad: string; n: number; x: number; y: number; r: number }

/** Pantalla en vivo: contadores, lo que está pasando y dónde están los leads. Se refresca sola cada cinco segundos. */
@Component({
  selector: 'pagina-en-vivo',
  imports: [DecimalPipe, RouterLink],
  template: `
    <div class="page-head">
      <div><span class="eyebrow">En vivo</span><h1>Lo que la brújula <em>está haciendo</em></h1><p>Últimas 24 horas. Se actualiza sola cada cinco segundos{{ d()?.modo_prueba ? '; en modo prueba las llamadas y correos van al equipo' : '' }}.</p></div>
      <div class="row"><span class="pulso" [class.on]="vivo()"></span><span class="muted small">{{ vivo() ? 'conectado' : 'reconectando…' }} · {{ hora() }}</span></div>
    </div>
    @if (d(); as d) {
      <div class="grid cols-5">
        <div class="kpi kpi-dark"><div class="label"><span>Leads encontrados</span><span class="num">01</span></div><div class="value">{{ d.contadores.leads | number }}</div><div class="sub">{{ d.contadores.encajan | number }} encajan · {{ d.contadores.nuevos_24h }} nuevos hoy</div></div>
        <div class="kpi"><div class="label"><span>Contactados hoy</span><span class="num">02</span></div><div class="value">{{ d.contadores.contactados_24h }}</div><div class="sub">por correo, llamada o WhatsApp</div></div>
        <div class="kpi kpi-blue"><div class="label"><span>Respondieron hoy</span><span class="num">03</span></div><div class="value">{{ d.contadores.respondieron_24h }}</div><div class="sub">registradas por la brújula</div></div>
        <div class="kpi"><div class="label"><span>Calificados por Dapta</span><span class="num">04</span></div><div class="value">{{ d.contadores.calificados }}</div><div class="sub">en total</div></div>
        <div class="kpi kpi-accent"><div class="label"><span>Gasto hoy · USD</span><span class="num">05</span></div><div class="value">{{ d.contadores.costo_24h_usd | number:'1.2-2' }}</div><div class="sub">llamadas y correos reales</div></div>
      </div>
      <div class="grid cols-main" style="margin-top:16px">
        <div class="card">
          <div class="card-head"><h2>Dónde están los leads</h2><span class="muted small">{{ sinCiudad() | number }} sin ciudad en la fuente</span></div>
          <svg viewBox="0 0 760 640" class="mapa" role="img" aria-label="Leads por ciudad">
            <rect x="0" y="0" width="760" height="640" rx="14" fill="#F7F9FD"/>
            @for (p of puntos(); track p.ciudad) {
              <circle [attr.cx]="p.x" [attr.cy]="p.y" [attr.r]="p.r" fill="#2563EB" fill-opacity=".22" stroke="#2563EB" stroke-width="1.5"/>
              <circle [attr.cx]="p.x" [attr.cy]="p.y" r="3" fill="#0C1733"/>
              <text [attr.x]="p.x + p.r + 6" [attr.y]="p.y + 4" class="ciudad">{{ titulo(p.ciudad) }} <tspan class="n">{{ p.n }}</tspan></text>
            }
            @if (!puntos().length) {<text x="380" y="320" text-anchor="middle" class="ciudad">Todavía no hay leads con ciudad conocida.</text>}
          </svg>
          @if (otras().length) {<p class="small muted" style="margin:10px 0 0">Otras ciudades: {{ otras().join(', ') }}.</p>}
        </div>
        <div class="card">
          <div class="card-head"><h2>Lo que está pasando</h2><span class="muted small">{{ d.eventos.length }} últimos</span></div>
          <div class="feed">
            @for (e of d.eventos; track e.cuando + e.texto) {
              <div class="ev" [class.nuevo]="esNuevo(e.cuando)">
                <span class="tag" [class]="'tag ' + clase(e.tipo)">{{ etiqueta(e.tipo) }}</span>
                <span class="texto">@if (e.lead_id) {<a [routerLink]="['/leads', e.lead_id]">{{ e.texto }}</a>} @else {{{ e.texto }}}</span>
                <span class="hace muted small">{{ hace(e.cuando) }}</span>
              </div>
            } @empty { <div class="empty"><b>Nada todavía</b>Haga una búsqueda o un lote y lo verá aparecer aquí.</div> }
          </div>
          @if (fuentesHoy().length) {<div class="row" style="margin-top:12px;flex-wrap:wrap">@for (f of fuentesHoy(); track f[0]) {<span class="choice on">{{ f[0] }} · {{ f[1] }} hoy</span>}</div>}
        </div>
      </div>
    } @else { <p class="muted">Conectando…</p> }
  `,
  styles: [`
    .pulso { width: 12px; height: 12px; border-radius: 50%; background: #B91C1C; display: inline-block; margin-right: 8px; }
    .pulso.on { background: #0F6E56; box-shadow: 0 0 0 4px rgba(15,110,86,.2); }
    .mapa { width: 100%; height: auto; display: block; }
    .ciudad { font-size: 12px; fill: var(--ink); font-weight: 600; } .ciudad .n { fill: var(--accent); font-family: var(--mono); }
    .feed { display: grid; gap: 8px; max-height: 560px; overflow: auto; }
    .ev { display: grid; grid-template-columns: 120px 1fr auto; gap: 10px; align-items: center; padding: 8px 10px; border-radius: 10px; background: #F7F9FD; font-size: 13.5px; }
    .ev.nuevo { background: #E6EEFF; }
    .ev .texto { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .ev .tag { justify-self: start; }
    .grid.cols-5 { display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px; }
  `],
})
export class EnVivoPage implements OnDestroy {
  private api = inject(ApiService);
  d = signal<any>(null);
  vivo = signal(false);
  private reloj: any;
  private vistos = new Set<string>();
  private primera = true;

  constructor() { this.cargar(); this.reloj = setInterval(() => this.cargar(), 5000); }
  ngOnDestroy(): void { clearInterval(this.reloj); }
  cargar(): void {
    this.api.enVivo().subscribe({ next: (d) => { if (this.primera) { d.eventos.forEach((e: any) => this.vistos.add(e.cuando + e.texto)); this.primera = false; } this.d.set(d); this.vivo.set(true); }, error: () => this.vivo.set(false) });
  }
  hora(): string { return new Date().toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }
  esNuevo(cuando: string): boolean { return !this.vistos.has(cuando + (this.d()?.eventos.find((e: any) => e.cuando === cuando)?.texto || '')); }
  titulo(s: string): string { return (s || '').toLowerCase().replace(/(^|\s)\S/g, (c) => c.toUpperCase()); }
  norm(s: string): string { return (s || '').toUpperCase().normalize('NFD').replace(/[̀-ͯ]/g, '').trim(); }
  puntos(): Punto[] {
    const cs = this.d()?.ciudades || [];
    const max = Math.max(1, ...cs.map((c: any) => c.n));
    const out: Punto[] = [];
    for (const c of cs) {
      const k = this.norm(c.ciudad); const ll = CIUDADES[k]; if (!ll) continue;
      const [lat, lon] = ll;
      out.push({ ciudad: k, n: c.n, x: 40 + ((lon + 79.2) / (79.2 - 66.6)) * 680, y: 30 + ((12.8 - lat) / (12.8 + 4.4)) * 580, r: 6 + 34 * Math.sqrt(c.n / max) });
    }
    return out;
  }
  sinCiudad(): number { return (this.d()?.ciudades || []).filter((c: any) => !c.ciudad).reduce((a: number, c: any) => a + c.n, 0); }
  otras(): string[] { return (this.d()?.ciudades || []).filter((c: any) => c.ciudad && !CIUDADES[this.norm(c.ciudad)]).slice(0, 12).map((c: any) => `${this.titulo(c.ciudad)} ${c.n}`); }
  fuentesHoy(): [string, number][] { return Object.entries(this.d()?.fuentes_24h || {}).map(([k, v]) => [nombreFuente(k), v as number]); }
  hace(iso: string): string {
    const ms = Date.now() - new Date(iso + (iso.endsWith('Z') ? '' : 'Z')).getTime(); const min = Math.round(ms / 60000);
    if (min < 1) return 'ahora'; if (min < 60) return `hace ${min} min`; const h = Math.round(min / 60); if (h < 48) return `hace ${h} h`; return `hace ${Math.round(h / 24)} días`;
  }
  etiqueta(t: string): string {
    const [a, b] = t.split(':');
    const canal: Record<string, string> = { correo: 'Correo', voz: 'Llamada', whatsapp: 'WhatsApp', calificacion: 'Dapta', busqueda: 'Búsqueda', reparto: 'Lote', override: 'Excepción', registro: 'Registro', ley_2300: 'Horario', override_dapta: 'Horario', respuesta: 'Respuesta', baja: 'Baja' };
    return (canal[a] || this.titulo(a)) + (b ? ` · ${b}` : '');
  }
  clase(t: string): string {
    if (t.includes('calificado') && !t.includes('no_')) return 'tag-ok';
    if (t.includes('contestado') || t.startsWith('respuesta')) return 'tag-accent';
    if (t.includes('fallido') || t.includes('baja') || t.includes('no_calificado')) return 'tag-danger';
    if (t.startsWith('busqueda') || t.startsWith('reparto')) return 'tag-info';
    return '';
  }
}
