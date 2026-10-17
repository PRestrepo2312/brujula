import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiService } from '../core/api.service';

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
        <h2>2. Fuentes y ciudad</h2>
        <div class="acciones">
          @for (f of fuentes(); track f.clave) {
            <span class="chip" [class.on]="elegidas().includes(f.clave)" (click)="alternar(f.clave)" [title]="f.nombre">{{ f.clave }} <small>{{ f.pais }}{{ f.contacta ? '' : ' · solo encontrar' }}</small></span>
          }
        </div>
        <div class="fila c2" style="margin:12px 0">
          <div><label>Ciudad</label><input [(ngModel)]="ciudad" placeholder="BOGOTA"></div>
          <div><label>Límite por fuente</label><input type="number" [(ngModel)]="limite" min="10" max="500"></div>
        </div>
        <div><label>Palabra del sector (opcional, para SECOP y OpenStreetMap)</label><input [(ngModel)]="sector" placeholder="clinica"></div>
        <div class="acciones" style="margin-top:12px">
          <button class="boton" (click)="buscar()" [disabled]="ocupado() || elegidas().length === 0">Buscar y puntuar</button>
          <button class="boton gris" (click)="puntuar()" [disabled]="ocupado()">Volver a puntuar pendientes</button>
        </div>
        @if (ocupado()) {<p class="sec">Consultando fuentes públicas… puede tardar hasta un minuto por fuente.</p>}
        @if (resultado(); as r) {
          <div class="ok-msg">{{ r.nuevos }} empresas nuevas. ICP: {{ r.icp?.pasa ?? 0 }} pasan, {{ r.icp?.revisar ?? 0 }} por revisar, {{ r.icp?.descarta ?? 0 }} descartadas.
            <a routerLink="/leads">Ver leads</a></div>
          <table><thead><tr><th>Fuente</th><th>Nuevas</th><th>Ya estaban</th><th>Duplicados</th><th>Segundos</th></tr></thead>
            <tbody>@for (f of r.fuentes; track f.fuente) {<tr><td>{{ f.fuente }}</td><td class="n">{{ f.nuevos ?? '–' }}</td><td class="n">{{ f.ya_estaban ?? '–' }}</td><td class="n">{{ f.dedupe?.duplicados ?? '–' }}</td><td class="n">{{ f.segundos ?? f.error }}</td></tr>}</tbody></table>
        }
        @if (error()) {<div class="aviso">{{ error() }}</div>}
      </div>
    </div>
    <div class="tarjeta">
      <h2>3. Lista propia (CSV) o lista de exclusión (RNE)</h2>
      <p class="sec">Columnas aceptadas: nombre, nit, telefono, correo, ciudad, sector, web. La subida va directo a S3 con URL prefirmada.</p>
      <div class="acciones">
        <input type="file" accept=".csv,text/csv" (change)="archivo = $any($event.target).files?.[0] ?? null" style="width:auto">
        <button class="boton sec" (click)="subir('leads_csv')" [disabled]="!archivo || ocupado()">Cargar como leads</button>
        <button class="boton gris" (click)="subir('rne')" [disabled]="!archivo || ocupado()">Cargar como exclusiones (RNE)</button>
      </div>
      @if (msgArchivo()) {<div class="ok-msg">{{ msgArchivo() }}</div>}
    </div>
  `,
})
export class BuscarPage {
  private api = inject(ApiService);
  texto = '';
  ciudad = 'BOGOTA';
  sector = '';
  limite = 100;
  archivo: File | null = null;
  fuentes = signal<any[]>([]);
  elegidas = signal<string[]>(['reps', 'rnt', 'men']);
  icp = signal<any>(null);
  motor = signal('');
  resultado = signal<any>(null);
  error = signal('');
  msgArchivo = signal('');
  ocupado = signal(false);

  constructor() {
    this.api.fuentes().subscribe((f) => this.fuentes.set(f.filter((x) => x.clave !== 'csv')));
    this.api.icp().subscribe((r) => { this.icp.set(r.icp); this.texto = r.texto || r.icp?.descripcion || ''; });
  }

  alternar(clave: string): void {
    this.elegidas.update((e) => (e.includes(clave) ? e.filter((x) => x !== clave) : [...e, clave]));
  }

  interpretar(): void {
    this.ocupado.set(true); this.error.set('');
    this.api.interpretarIcp(this.texto).subscribe({ next: (r) => { this.icp.set(r.icp); this.motor.set(r.motor); this.ocupado.set(false); }, error: (e) => { this.error.set(e.message); this.ocupado.set(false); } });
  }

  buscar(): void {
    this.ocupado.set(true); this.error.set(''); this.resultado.set(null);
    this.api.buscar({ fuentes: this.elegidas(), ciudad: this.ciudad.trim().toUpperCase(), sector: this.sector.trim(), limite: this.limite })
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
