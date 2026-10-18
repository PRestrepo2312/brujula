import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiService } from '../core/api.service';

interface Fuente {
  clave: string; nombre: string; pais: string; tipo: string; contacta: boolean; descripcion: string;
  usa_ciudad: boolean; usa_sector: boolean; ayuda_ciudad: string; ayuda_sector: string; idioma: string;
}

const PAISES: Record<string, string> = { CO: 'Colombia', MX: 'México', BR: 'Brasil', US: 'Estados Unidos' };
const CIUDADES_CO = ['BOGOTA', 'MEDELLIN', 'CALI', 'BARRANQUILLA', 'CARTAGENA', 'BUCARAMANGA', 'CUCUTA', 'PEREIRA', 'MANIZALES', 'IBAGUE', 'SANTA MARTA',
  'VILLAVICENCIO', 'PASTO', 'MONTERIA', 'NEIVA', 'ARMENIA', 'VALLEDUPAR', 'POPAYAN', 'SINCELEJO', 'TUNJA', 'RIOHACHA', 'FLORENCIA', 'YOPAL', 'QUIBDO'];
const ESTADOS_MX: [string, string][] = [['00', 'Todo México'], ['01', 'Aguascalientes'], ['02', 'Baja California'], ['03', 'Baja California Sur'], ['04', 'Campeche'],
  ['05', 'Coahuila'], ['06', 'Colima'], ['07', 'Chiapas'], ['08', 'Chihuahua'], ['09', 'Ciudad de México'], ['10', 'Durango'], ['11', 'Guanajuato'], ['12', 'Guerrero'],
  ['13', 'Hidalgo'], ['14', 'Jalisco'], ['15', 'Estado de México'], ['16', 'Michoacán'], ['17', 'Morelos'], ['18', 'Nayarit'], ['19', 'Nuevo León'], ['20', 'Oaxaca'],
  ['21', 'Puebla'], ['22', 'Querétaro'], ['23', 'Quintana Roo'], ['24', 'San Luis Potosí'], ['25', 'Sinaloa'], ['26', 'Sonora'], ['27', 'Tabasco'], ['28', 'Tamaulipas'],
  ['29', 'Tlaxcala'], ['30', 'Veracruz'], ['31', 'Yucatán'], ['32', 'Zacatecas']];

@Component({
  selector: 'pagina-buscar-manual',
  imports: [FormsModule, RouterLink],
  template: `
    <div class="page-head"><div><span class="eyebrow">Buscar a mano</span><h1>Elija usted <em>las fuentes</em></h1><p>El modo manual: describa a quién busca, marque las fuentes y la ciudad, o cargue su propia lista en CSV. Si prefiere, <a routerLink="/buscar">la brújula lo propone conversando</a>.</p></div></div>
    <div class="grid cols-main">
      <div>
        <div class="card">
          <div class="step"><span class="step-n">1</span><div style="flex:1">
            <h2>Cliente ideal</h2>
            <div class="field"><label>En sus palabras</label><textarea rows="3" [(ngModel)]="texto" placeholder="Clínicas odontológicas en Bogotá con más de 10 empleados que agendan citas por WhatsApp"></textarea></div>
            <div class="row"><button class="btn btn-secondary" (click)="interpretar()" [disabled]="ocupado() || !texto.trim()">Interpretar con el agente</button>@if (motor()) {<span class="muted small">motor: {{ motor() }}</span>}</div>
            @if (icp(); as i) {
              <div class="choices" style="margin-top:12px">
                @for (s of i.sectores; track s) {<span class="tag tag-accent">{{ s }}</span>}
                @for (c of i.ciudades; track c) {<span class="tag">{{ c }}</span>}
                @if (i.empleados_min || i.empleados_max) {<span class="tag">{{ i.empleados_min ?? '' }} a {{ i.empleados_max ?? '' }} empleados</span>}
                @for (p of i.palabras_sector; track p) {<span class="tag">{{ p }}</span>}
              </div>
              <p class="small muted" style="margin-top:8px">Encaja con 70 % o más; entre 40 % y 70 % lo revisa una persona; por debajo se descarta.</p>
            }
          </div></div>
        </div>
        <div class="card">
          <div class="step"><span class="step-n">2</span><div style="flex:1">
            <h2>Fuentes</h2>
            <p class="small muted">Registros públicos y gratuitos. <b>Contacta</b>: Brújula puede llamar o escribir. <b>Solo encontrar</b>: trae la empresa para su lista, sin contacto automático. Pase el cursor por una fuente para ver qué trae.</p>
            @for (g of grupos(); track g.pais) {
              <h3>{{ g.nombre }}</h3>
              <div class="fuentes">
                @for (f of g.fuentes; track f.clave) {
                  <label class="fuente" [class.on]="elegidas().includes(f.clave)" [title]="f.descripcion">
                    <input type="checkbox" [checked]="elegidas().includes(f.clave)" (change)="alternar(f.clave)">
                    <span class="fuente-nombre">{{ f.nombre }}</span>
                    <span class="tag" [class.tag-ok]="f.contacta">{{ f.contacta ? 'contacta' : 'solo encontrar' }}</span>
                  </label>
                }
              </div>
            }
          </div></div>
        </div>
        <div class="card">
          <div class="step"><span class="step-n">3</span><div style="flex:1">
            <h2>Dónde y qué</h2>
            @if (elegidas().length === 0) {<p class="muted">Elija al menos una fuente.</p>}
            <div class="grid cols-2">
              @if (pideCiudadCo()) {
                <div class="field"><label>Ciudad de Colombia <span class="muted">({{ nombresDe(fuentesConCiudadCo()) }})</span></label>
                  <select [(ngModel)]="ciudad"><option value="">Todas las ciudades</option>@for (c of ciudadesCo; track c) {<option [value]="c">{{ titulo(c) }}</option>}</select></div>
              }
              @if (elegidas().includes('denue')) {
                <div class="field"><label>Entidad federativa de México (DENUE)</label>
                  <select [(ngModel)]="entidadMx">@for (e of estadosMx; track e[0]) {<option [value]="e[0]">{{ e[1] }}</option>}</select></div>
              }
              @if (elegidas().includes('nyc')) {
                <div class="field"><label>Borough de Nueva York <span class="muted">(opcional)</span></label><input [(ngModel)]="boroughNyc" placeholder="Manhattan, Brooklyn, Queens…"></div>
              }
              @if (fuentesConSector().length > 0) {
                <div class="field"><label>Palabra del sector <span class="muted">(opcional)</span></label><input [(ngModel)]="sector" placeholder="odontología, hotel, software"><span class="hint">{{ ayudaSector() }}</span></div>
              }
              <div class="field"><label>Límite por fuente</label><input type="number" [(ngModel)]="limite" min="10" max="500"></div>
            </div>
            @if (elegidas().includes('cnpj')) {
              <div class="field"><label>Brasil: CNPJ separados por coma</label><textarea rows="3" [(ngModel)]="cnpjs" placeholder="12345678000195, 98765432000100"></textarea><span class="hint">Salen de una consulta por CNAE en Base dos Dados.</span></div>
            }
            <div class="row" style="margin-top:4px">
              <button class="btn btn-primary btn-lg" (click)="buscar()" [disabled]="ocupado() || elegidas().length === 0 || (elegidas().includes('cnpj') && !cnpjs.trim())">{{ ocupado() ? 'Buscando…' : 'Buscar empresas' }}</button>
              <button class="btn btn-ghost" (click)="puntuar()" [disabled]="ocupado()">Volver a medir el encaje de los pendientes</button>
            </div>
            @if (ocupado()) {<p class="small muted" style="margin-top:8px">Consultando fuentes públicas; puede tardar hasta un minuto por fuente.</p>}
            @if (error()) {<div class="banner banner-danger">{{ error() }}</div>}
          </div></div>
        </div>
      </div>
      <div>
        <div class="card">
          <h2>Resultado</h2>
          @if (resultado(); as r) {
            <div class="banner banner-ok"><b>{{ r.nuevos }}</b> empresas nuevas. Cliente ideal: {{ r.icp?.pasa ?? 0 }} encajan, {{ r.icp?.revisar ?? 0 }} por revisar, {{ r.icp?.descarta ?? 0 }} no encajan. <a routerLink="/leads">Ver leads</a></div>
            <div class="table-wrap"><table class="table">
              <thead><tr><th>Fuente</th><th class="num">Nuevas</th><th class="num">Ya estaban</th><th class="num">Duplicados</th><th>Detalle</th></tr></thead>
              <tbody>@for (f of r.fuentes; track f.fuente) {<tr><td>{{ nombreDe(f.fuente) }}</td><td class="num">{{ f.nuevos ?? '–' }}</td><td class="num">{{ f.ya_estaban ?? '–' }}</td><td class="num">{{ f.dedupe?.duplicados ?? '–' }}</td><td [class.muted]="!f.error">{{ f.error || (f.segundos + ' s') }}</td></tr>}</tbody>
            </table></div>
          } @else {
            <div class="empty"><b>Aquí aparece lo que traiga cada fuente</b>Nuevas, repetidas, duplicadas y el tiempo que tardó.</div>
          }
        </div>
        <div class="card">
          <h2>Lista propia o exclusiones</h2>
          <p class="small muted">CSV con columnas nombre, nit, telefono, correo, ciudad, sector, web. La subida va directo a S3 con URL prefirmada. La lista de exclusión (RNE) son números o correos que nunca se contactan.</p>
          <input type="file" accept=".csv,text/csv" (change)="archivo = $any($event.target).files?.[0] ?? null">
          <div class="row" style="margin-top:10px">
            <button class="btn btn-secondary" (click)="subir('leads_csv')" [disabled]="!archivo || ocupado()">Cargar como leads</button>
            <button class="btn btn-ghost" (click)="subir('rne')" [disabled]="!archivo || ocupado()">Cargar como exclusiones</button>
          </div>
          @if (msgArchivo()) {<div class="banner banner-ok">{{ msgArchivo() }}</div>}
        </div>
      </div>
    </div>
  `,
  styles: [`
    .fuentes { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; } @media (max-width: 1200px) { .fuentes { grid-template-columns: 1fr; } }
    .fuente { display: flex; align-items: center; gap: 10px; border: 1px solid var(--line); border-radius: 6px; padding: 9px 12px; cursor: pointer; background: #fff; font-size: 13px; }
    .fuente:hover { border-color: var(--line-strong); } .fuente.on { border-color: var(--accent); background: var(--accent-soft); }
    .fuente input { width: 15px; height: 15px; margin: 0; accent-color: var(--accent); flex: none; }
    .fuente-nombre { flex: 1; color: var(--ink); font-weight: 500; }
  `],
})
export class BuscarManualPage {
  private api = inject(ApiService);
  texto = '';
  ciudad = 'BOGOTA';
  sector = '';
  limite = 100;
  entidadMx = '09';
  boroughNyc = '';
  cnpjs = '';
  archivo: File | null = null;
  ciudadesCo = CIUDADES_CO;
  estadosMx = ESTADOS_MX;
  fuentes = signal<Fuente[]>([]);
  elegidas = signal<string[]>(['reps', 'rnt', 'men']);
  icp = signal<any>(null);
  motor = signal('');
  resultado = signal<any>(null);
  error = signal('');
  msgArchivo = signal('');
  ocupado = signal(false);

  grupos = computed(() => {
    const orden = ['CO', 'MX', 'BR', 'US'];
    return orden.map((p) => ({ pais: p, nombre: PAISES[p] || p, fuentes: this.fuentes().filter((f) => f.pais === p) })).filter((g) => g.fuentes.length > 0);
  });
  seleccionadas = computed(() => this.fuentes().filter((f) => this.elegidas().includes(f.clave)));
  fuentesConCiudadCo = computed(() => this.seleccionadas().filter((f) => f.pais === 'CO' && f.usa_ciudad));
  pideCiudadCo = computed(() => this.fuentesConCiudadCo().length > 0);
  fuentesConSector = computed(() => this.seleccionadas().filter((f) => f.usa_sector && f.clave !== 'cnpj'));
  ayudaSector = computed(() => this.fuentesConSector().map((f) => `${f.clave.toUpperCase()}: ${f.ayuda_sector}`).join(' · '));

  constructor() {
    this.api.fuentes().subscribe((f) => this.fuentes.set((f as Fuente[]).filter((x) => x.clave !== 'csv')));
    this.api.icp().subscribe((r) => { this.icp.set(r.icp); this.texto = r.texto || r.icp?.descripcion || ''; });
  }

  alternar(clave: string): void { this.elegidas.update((e) => (e.includes(clave) ? e.filter((x) => x !== clave) : [...e, clave])); }
  nombreDe(clave: string): string { return this.fuentes().find((f) => f.clave === clave)?.nombre || clave; }
  nombresDe(fs: Fuente[]): string { return fs.map((f) => f.clave.toUpperCase()).join(', '); }
  titulo(s: string): string { return s.toLowerCase().replace(/(^|\s)\S/g, (c) => c.toUpperCase()); }

  interpretar(): void {
    this.ocupado.set(true); this.error.set('');
    this.api.interpretarIcp(this.texto).subscribe({ next: (r) => { this.icp.set(r.icp); this.motor.set(r.motor); this.ocupado.set(false); }, error: (e) => { this.error.set(e.message); this.ocupado.set(false); } });
  }

  buscar(): void {
    this.ocupado.set(true); this.error.set(''); this.resultado.set(null);
    const parametros: Record<string, { ciudad?: string; sector?: string }> = {};
    if (this.elegidas().includes('denue')) parametros['denue'] = { ciudad: this.entidadMx };
    if (this.elegidas().includes('cnpj')) parametros['cnpj'] = { sector: this.cnpjs.trim(), ciudad: '' };
    if (this.elegidas().includes('nyc')) parametros['nyc'] = { ciudad: this.boroughNyc.trim() };
    this.api.buscar({ fuentes: this.elegidas(), ciudad: this.ciudad.trim().toUpperCase(), sector: this.sector.trim(), limite: this.limite, parametros })
      .subscribe({ next: (r) => { this.resultado.set(r); this.ocupado.set(false); }, error: (e) => { this.error.set(e.error?.error || e.message); this.ocupado.set(false); } });
  }

  puntuar(): void {
    this.ocupado.set(true);
    this.api.puntuar(false).subscribe({ next: (r) => { this.resultado.set({ nuevos: 0, icp: r, fuentes: [] }); this.ocupado.set(false); }, error: () => this.ocupado.set(false) });
  }

  async subir(tipo: 'leads_csv' | 'rne'): Promise<void> {
    if (!this.archivo) return;
    this.ocupado.set(true); this.msgArchivo.set('');
    try {
      const clave = await this.api.subir(this.archivo, (n) => this.api.urlSubida(n).toPromise());
      const r: any = await this.api.procesarArchivo(clave, tipo).toPromise();
      this.msgArchivo.set(tipo === 'rne' ? `${r.excluidos_cargados} exclusiones cargadas.` : `${r.nuevos} leads nuevos, ${r.dedupe?.duplicados ?? 0} duplicados detectados.`);
    } catch (e: any) { this.msgArchivo.set(`Error: ${e.message}`); }
    this.ocupado.set(false);
  }
}
