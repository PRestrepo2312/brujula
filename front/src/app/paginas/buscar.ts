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
  selector: 'pagina-buscar',
  imports: [FormsModule, RouterLink],
  template: `
    <h1>Buscar <em>clientes potenciales</em></h1>
    <div class="fila c2">
      <div class="tarjeta">
        <h2>1. Describa su cliente ideal</h2>
        <label>En sus palabras (el agente lo convierte en criterios)</label>
        <textarea rows="4" [(ngModel)]="texto" placeholder="Ej.: clínicas odontológicas en Bogotá con más de 10 empleados que agendan citas por WhatsApp"></textarea>
        <div class="acciones" style="margin-top:10px">
          <button class="boton" (click)="interpretar()" [disabled]="ocupado() || !texto.trim()">Interpretar con el agente</button>
          @if (motor()) {<span class="sec">motor: {{ motor() }}</span>}
        </div>
        @if (icp(); as i) {
          <h2 style="margin-top:16px">Criterios</h2>
          <div class="acciones">
            @for (s of i.sectores; track s) {<span class="chip on">{{ s }}</span>}
            @for (c of i.ciudades; track c) {<span class="chip">{{ c }}</span>}
            @if (i.empleados_min || i.empleados_max) {<span class="chip">{{ i.empleados_min ?? '' }} a {{ i.empleados_max ?? '' }} empleados</span>}
            @for (p of i.palabras_sector; track p) {<span class="chip">{{ p }}</span>}
          </div>
          <p class="sec">Pasa con 0,7 o más; entre 0,4 y 0,7 lo revisa una persona; menos se descarta.</p>
        }
      </div>
      <div class="tarjeta">
        <h2>2. Elija las fuentes</h2>
        <p class="sec">Registros públicos y gratuitos. "Contacta" = Brújula puede llamar o escribir; "solo encontrar" = trae la empresa para su lista, sin contacto automático. Pase el cursor por una fuente para ver qué trae.</p>
        @for (g of grupos(); track g.pais) {
          <h3 class="pais">{{ g.nombre }}</h3>
          <div class="fuentes">
            @for (f of g.fuentes; track f.clave) {
              <div class="fuente" [class.on]="elegidas().includes(f.clave)" (click)="alternar(f.clave)" [title]="f.descripcion">
                <div class="fuente-cab"><b>{{ f.nombre }}</b><span class="pill" [class.pasa]="f.contacta">{{ f.contacta ? 'contacta' : 'solo encontrar' }}</span></div>
              </div>
            }
          </div>
        }
        <h2 style="margin-top:16px">3. Dónde y qué</h2>
        @if (elegidas().length === 0) {<p class="sec">Elija al menos una fuente.</p>}
        <div class="fila c2" style="margin:0 0 10px">
          @if (pideCiudadCo()) {
            <div><label>Ciudad de Colombia ({{ nombresDe(fuentesConCiudadCo()) }})</label>
              <select [(ngModel)]="ciudad"><option value="">Todas las ciudades</option>@for (c of ciudadesCo; track c) {<option [value]="c">{{ titulo(c) }}</option>}</select></div>
          }
          @if (elegidas().includes('denue')) {
            <div><label>Entidad federativa de México (DENUE)</label>
              <select [(ngModel)]="entidadMx">@for (e of estadosMx; track e[0]) {<option [value]="e[0]">{{ e[1] }}</option>}</select></div>
          }
          @if (elegidas().includes('nyc')) {
            <div><label>Borough de Nueva York (opcional)</label><input [(ngModel)]="boroughNyc" placeholder="Manhattan, Brooklyn, Queens…"></div>
          }
          <div><label>Límite por fuente</label><input type="number" [(ngModel)]="limite" min="10" max="500"></div>
        </div>
        @if (fuentesConSector().length > 0) {
          <div><label>Palabra del sector (opcional) · {{ ayudaSector() }}</label><input [(ngModel)]="sector" placeholder="Ej.: odontología, hotel, software"></div>
        }
        @if (elegidas().includes('cnpj')) {
          <div style="margin-top:10px"><label>Brasil: CNPJ separados por coma (de una consulta por CNAE en Base dos Dados)</label>
            <textarea rows="3" [(ngModel)]="cnpjs" placeholder="12345678000195, 98765432000100"></textarea></div>
        }
        <div class="acciones" style="margin-top:12px">
          <button class="boton" (click)="buscar()" [disabled]="ocupado() || elegidas().length === 0 || (elegidas().includes('cnpj') && !cnpjs.trim())">Buscar y puntuar</button>
          <button class="boton gris" (click)="puntuar()" [disabled]="ocupado()">Volver a puntuar pendientes</button>
        </div>
        @if (ocupado()) {<p class="sec">Consultando fuentes públicas… puede tardar hasta un minuto por fuente.</p>}
        @if (resultado(); as r) {
          <div class="ok-msg">{{ r.nuevos }} empresas nuevas. ICP: {{ r.icp?.pasa ?? 0 }} pasan, {{ r.icp?.revisar ?? 0 }} por revisar, {{ r.icp?.descarta ?? 0 }} descartadas.
            <a routerLink="/leads">Ver leads</a></div>
          <table><thead><tr><th>Fuente</th><th>Nuevas</th><th>Ya estaban</th><th>Duplicados</th><th>Segundos / detalle</th></tr></thead>
            <tbody>@for (f of r.fuentes; track f.fuente) {<tr><td>{{ nombreDe(f.fuente) }}</td><td class="n">{{ f.nuevos ?? '–' }}</td><td class="n">{{ f.ya_estaban ?? '–' }}</td><td class="n">{{ f.dedupe?.duplicados ?? '–' }}</td><td [class.sec]="!!f.error">{{ f.error || f.segundos }}</td></tr>}</tbody></table>
        }
        @if (error()) {<div class="aviso">{{ error() }}</div>}
      </div>
    </div>
    <div class="tarjeta">
      <h2>Lista propia (CSV) o lista de exclusión (RNE)</h2>
      <p class="sec">Columnas aceptadas: nombre, nit, telefono, correo, ciudad, sector, web. La subida va directo a S3 con URL prefirmada.</p>
      <div class="acciones">
        <input type="file" accept=".csv,text/csv" (change)="archivo = $any($event.target).files?.[0] ?? null" style="width:auto">
        <button class="boton sec" (click)="subir('leads_csv')" [disabled]="!archivo || ocupado()">Cargar como leads</button>
        <button class="boton gris" (click)="subir('rne')" [disabled]="!archivo || ocupado()">Cargar como exclusiones (RNE)</button>
      </div>
      @if (msgArchivo()) {<div class="ok-msg">{{ msgArchivo() }}</div>}
    </div>
  `,
  styles: [`
    .pais { font-size: 11px; letter-spacing: .14em; text-transform: uppercase; color: var(--sec); margin: 12px 0 6px; }
    .fuentes { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; } @media (max-width: 700px) { .fuentes { grid-template-columns: 1fr; } }
    .fuente { border: 1px solid var(--border); border-radius: 10px; padding: 10px 12px; cursor: pointer; background: #fff; font-size: 13px; }
    .fuente.on { border-color: var(--accent); background: #FCEBDD; }
    .fuente-cab { display: flex; justify-content: space-between; align-items: center; gap: 8px; } .fuente-cab b { color: var(--ink); font-weight: 600; }
  `],
})
export class BuscarPage {
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

  alternar(clave: string): void {
    this.elegidas.update((e) => (e.includes(clave) ? e.filter((x) => x !== clave) : [...e, clave]));
  }
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
