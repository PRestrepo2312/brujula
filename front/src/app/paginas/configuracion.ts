import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';

@Component({
  selector: 'pagina-configuracion',
  imports: [FormsModule, RouterLink],
  template: `
    <div class="page-head"><div><span class="eyebrow">Configuración</span><h1>Su empresa y <em>cómo contacta</em></h1><p>Cómo se presenta, por qué canales, con qué horario y quién entra.</p></div></div>
    @if (e(); as e) {
      <div class="grid cols-main">
        <div>
          <div class="card">
            <div class="card-head"><h2>{{ e.nombre }}</h2><button class="btn btn-primary" (click)="guardar()" [disabled]="ocupado()">Guardar cambios</button></div>
            @if (msg()) {<div class="banner banner-ok">{{ msg() }}</div>}
            <h2 style="margin-top:4px">Cómo se presenta</h2>
            <p class="small muted">Lo que dicen los correos, los mensajes de WhatsApp y la llamada del agente en su nombre. Puede dejar que la brújula lo proponga: <a routerLink="/inicio">conversar con el asistente</a>, o aquí mismo con el NIT y la página.</p>
            <div class="row" style="margin-bottom:12px">
              <button class="btn btn-secondary" (click)="buscarNit()" [disabled]="ocupado() || !form.config.perfil.nit">Buscar el NIT en el RUES</button>
              <button class="btn btn-secondary" (click)="proponer()" [disabled]="ocupado()">Proponer con el agente</button>
              @if (msgPerfil()) {<span class="small muted">{{ msgPerfil() }}</span>}
            </div>
            <div class="grid cols-2">
              <div class="field"><label>Nombre con el que se presenta</label><input [(ngModel)]="form.config.perfil.nombre" [placeholder]="e.nombre"></div>
              <div class="field"><label>Quién firma</label><input [(ngModel)]="form.config.perfil.remitente" placeholder="el equipo de {{ e.nombre }}"></div>
            </div>
            <div class="field"><label>Qué ofrece <span class="muted">(completa "Les escribe …: ")</span></label><textarea rows="2" [(ngModel)]="form.config.perfil.que_ofrece" placeholder="llenamos la agenda de clínicas odontológicas con pacientes nuevos"></textarea></div>
            <div class="grid cols-2">
              <div class="field"><label>A quién le vende</label><input [(ngModel)]="form.config.perfil.a_quien"></div>
              <div class="field"><label>Qué lo distingue</label><input [(ngModel)]="form.config.perfil.diferencial"></div>
              <div class="field"><label>NIT</label><input [(ngModel)]="form.config.perfil.nit"></div>
              <div class="field"><label>Página web</label><input [(ngModel)]="form.config.perfil.sitio_web"></div>
              <div class="field"><label>Cuánto le cuesta hoy un cliente por pauta (USD)</label><input type="number" step="0.5" min="0" [(ngModel)]="form.config.costo_lead_pauta_usd" placeholder="25"><span class="hint">El tablero compara este valor con lo que cuesta un lead calificado con Brújula.</span></div>
            </div>
            <hr class="divider">
            <h2>Datos y canales</h2>
            <div class="grid cols-2">
              <div class="field"><label>Nombre</label><input [(ngModel)]="form.nombre"></div>
              <div class="field"><label>Correo para notificaciones</label><input [(ngModel)]="form.correo_notificaciones" placeholder="ventas@empresa.com"></div>
              <div class="field"><label>Leads por lote</label><input type="number" [(ngModel)]="form.config.presupuesto_lote" min="1" max="500"></div>
              <div class="field"><label>Encaje mínimo para contactar (%)</label><input type="number" min="70" max="100" step="5" [ngModel]="umbralPct()" (ngModelChange)="form.config.umbral_contacto = $event / 100"><span class="hint">Solo entran en un lote las empresas con ese encaje o más. 70 % es lo que la brújula considera "encaja"; súbalo a 80 o 90 para ser más exigente.</span></div>
              <div class="field"><label>Contacto automático</label><div class="choices">
                <span class="choice" [class.on]="form.config.contacto_automatico === true" (click)="form.config.contacto_automatico = true">Activo: la brújula arma y envía lotes sola, cada hora en horario legal</span>
                <span class="choice" [class.on]="!form.config.contacto_automatico" (click)="form.config.contacto_automatico = false">Apagado: solo cuando yo lo pida (Lotes o el chat de Buscar)</span>
              </div></div>
              <div class="field"><label>Canales activos</label><div class="choices">@for (c of ['voz','correo','whatsapp']; track c) {<span class="choice" [class.on]="form.config.canales.includes(c)" (click)="alternar(c)">{{ c }}</span>}</div></div>
              <div class="field"><label>Avisar por</label><div class="choices">@for (c of ['app','correo']; track c) {<span class="choice" [class.on]="form.config.notificar_por.includes(c)" (click)="alternarAviso(c)">{{ c }}</span>}</div></div>
            </div>
            <hr class="divider">
            <h2>Horario de la Ley 2300</h2>
            <p class="small muted">Lunes a viernes de 7 a. m. a 7 p. m., sábados de 8 a. m. a 3 p. m., nunca domingos ni festivos.</p>
            <div class="choices">
              <span class="choice" [class.on]="form.config.respetar_ley_2300 !== false" (click)="form.config.respetar_ley_2300 = true">Respetar el horario</span>
              <span class="choice" [class.on]="form.config.respetar_ley_2300 === false" (click)="form.config.respetar_ley_2300 = false">Desactivar bajo mi responsabilidad</span>
            </div>
            @if (form.config.respetar_ley_2300 === false) {<div class="banner banner-warn">Con el horario desactivado los lotes salen a cualquier hora sin pedir motivo y la secuencia de Dapta llama todos los días a toda hora. El cambio queda en la bitácora con su usuario.</div>}
            <hr class="divider">
            <h2>Idioma de los mensajes por fuente</h2>
            <p class="small muted">Sin elegir, cada fuente usa el idioma de su país.</p>
            <div class="table-wrap"><table class="table">
              @for (f of fuentes(); track f.clave) {
                <tr><td>{{ f.nombre }}</td>
                  <td style="width:260px"><select [ngModel]="form.config.idiomas[f.clave] || ''" (ngModelChange)="form.config.idiomas[f.clave] = $event">
                    <option value="">{{ nombreIdioma(f.idioma) }} (idioma del país)</option><option value="es">Español</option><option value="pt">Português</option><option value="en">English</option>
                  </select></td></tr>
              }
            </table></div>
            <hr class="divider">
            <h2>Dapta de la empresa</h2>
            <p class="small muted">Clave MCP actual: {{ e.dapta_api_key || 'la del servidor (demo)' }}. Con clave propia, los agentes y la secuencia son de la empresa.</p>
            <div class="grid cols-3">
              <div class="field"><label>Nueva clave MCP</label><input type="password" [(ngModel)]="form.dapta_api_key" placeholder="dapta_pat_…"></div>
              <div class="field"><label>Agente de voz (id)</label><input [(ngModel)]="form.dapta_agent_id"></div>
              <div class="field"><label>Secuencia (id)</label><input [(ngModel)]="form.dapta_sequence_id"></div>
            </div>
          </div>
        </div>
        <div>
          @if (estado(); as s) {
            <div class="card">
              <div class="card-head"><h2>Modo prueba</h2><span class="tag" [class.tag-warn]="s.modo_prueba?.activo">{{ s.modo_prueba?.activo ? 'activo: desvío' : 'apagado: contacto real' }}</span></div>
              <p class="small">Demostración real sin tocar a terceros: la búsqueda, el cliente ideal, el mensaje con el nombre y las señales de cada empresa, el lote y las métricas corren igual, pero la llamada del agente se marca a <b>{{ s.modo_prueba?.telefono || 'ningún número (se fija al desplegar con TELEFONO_PRUEBA)' }}</b> (una por lote) y los correos van a <b>{{ s.modo_prueba?.correos?.join(', ') || 'ningún correo' }}</b>. Cada contacto guarda el destino original y el desviado. Para contactar de verdad se despliega con MODO_PRUEBA=0 y sin destinos.</p>
            </div>
          }
          <div class="card">
            <h2>Su cuenta</h2>
            <p class="small">{{ auth.email }} · {{ auth.rol === 'superadmin' ? 'superadmin de la plataforma' : auth.rol === 'admin' ? 'administrador de esta empresa' : 'usuario de esta empresa' }}. Cada empresa es un espacio aparte: sus leads, lotes, métricas y configuración solo los ven sus usuarios.</p>
            @if (auth.rol === 'admin' || auth.rol === 'superadmin') {
              <h3>Agregar una persona {{ auth.rol === 'superadmin' ? '' : 'a mi empresa' }}</h3>
              <p class="small muted">Recibe por correo una clave temporal y entra directo al espacio de la empresa. "usuario" trabaja con los leads; "admin" además configura y agrega gente.</p>
              <div class="field"><label>Correo</label><input [(ngModel)]="usuario.email"></div>
              <div class="grid cols-2">
                @if (auth.rol === 'superadmin') {<div class="field"><label>Empresa (id)</label><input type="number" [(ngModel)]="usuario.empresa_id"></div>}
                <div class="field"><label>Rol</label><select [(ngModel)]="usuario.rol"><option value="usuario">usuario</option><option value="admin">admin</option>@if (auth.rol === 'superadmin') {<option value="superadmin">superadmin</option>}</select></div>
              </div>
              <div class="row"><button class="btn btn-secondary" (click)="crearUsuario()" [disabled]="!usuario.email || ocupado()">Crear usuario</button>@if (msgAdmin()) {<span class="small muted">{{ msgAdmin() }}</span>}</div>
            }
          </div>
          @if (auth.rol === 'superadmin') {
            <div class="card">
              <h2>Empresas (superadmin)</h2>
              <div class="table-wrap"><table class="table"><thead><tr><th>#</th><th>Nombre</th><th>Correo</th></tr></thead><tbody>@for (x of empresas(); track x.id) {<tr><td class="muted">{{ x.id }}</td><td>{{ x.nombre }}</td><td class="small">{{ x.correo_notificaciones }}</td></tr>}</tbody></table></div>
              <p class="small muted">Para mirar otra empresa agregue <code>?empresa=ID</code> a la dirección.</p>
              <h3>Nueva empresa</h3>
              <div class="grid cols-2"><div class="field"><label>Nombre</label><input [(ngModel)]="nueva.nombre"></div><div class="field"><label>Correo</label><input [(ngModel)]="nueva.correo_notificaciones"></div></div>
              <div class="field"><label>Cliente ideal (en sus palabras)</label><textarea rows="2" [(ngModel)]="nueva.icp_texto"></textarea></div>
              <button class="btn btn-secondary" (click)="crearEmpresa()" [disabled]="!nueva.nombre || ocupado()">Crear empresa</button>
            </div>
          }
        </div>
      </div>
    } @else { <p class="muted">Cargando…</p> }
  `,
})
export class ConfiguracionPage {
  private api = inject(ApiService);
  auth = inject(AuthService);
  e = signal<any>(null);
  empresas = signal<any[]>([]);
  form: any = { nombre: '', correo_notificaciones: '', dapta_api_key: '', dapta_agent_id: '', dapta_sequence_id: '', config: { canales: ['voz', 'correo'], presupuesto_lote: 20, notificar_por: ['app', 'correo'], idiomas: {}, perfil: {} } };
  nueva = { nombre: '', correo_notificaciones: '', icp_texto: '' };
  usuario = { email: '', empresa_id: 1, rol: 'usuario' };
  estado = signal<any>(null);
  fuentes = signal<any[]>([]);
  msg = signal(''); msgAdmin = signal(''); msgPerfil = signal(''); ocupado = signal(false);
  private rues: any = null;

  constructor() { this.cargar(); }
  nombreIdioma(c: string): string { return ({ es: 'Español', pt: 'Português', en: 'English' } as Record<string, string>)[c] || c; }
  umbralPct(): number { return Math.round(((this.form.config.umbral_contacto ?? 0.7) as number) * 100); }
  titulo(s: string): string { return (s || '').toLowerCase().replace(/(^|\s)\S/g, (c) => c.toUpperCase()); }
  buscarNit(): void {
    this.ocupado.set(true); this.msgPerfil.set('');
    this.api.nit(this.form.config.perfil.nit).subscribe({
      next: (r) => { this.tomarRues(r); this.msgPerfil.set(`RUES: ${r.razon_social}, ${this.titulo(r.ciudad)}, sector ${r.sector}, matrícula ${r.matricula}. Se presenta como ${this.form.config.perfil.nombre}.`); this.ocupado.set(false); },
      error: (e) => { this.msgPerfil.set(e.error?.error || 'No se pudo consultar el RUES'); this.ocupado.set(false); } });
  }
  /** El nombre del registro reemplaza al de la empresa solo si la persona no escribió uno propio. */
  private tomarRues(r: any): void {
    this.rues = r; const p = this.form.config.perfil;
    if (!p.nombre || p.nombre === this.e()?.nombre) p.nombre = r.nombre_comercial || this.titulo(r.razon_social);
  }
  proponer(): void {
    const p = this.form.config.perfil;
    if (!this.rues && (p.nit || '').replace(/\D/g, '').length >= 8) {
      this.ocupado.set(true); this.msgPerfil.set('Buscando el NIT en el RUES…');
      this.api.nit(p.nit).subscribe({ next: (r) => { this.tomarRues(r); this.sugerir(); }, error: () => this.sugerir() });
      return;
    }
    this.sugerir();
  }
  private sugerir(): void {
    this.ocupado.set(true); this.msgPerfil.set('');
    const p = this.form.config.perfil;
    this.api.sugerir({ nombre: p.nombre || this.e()?.nombre || '', rues: this.rues, sitio: p.sitio_web ? { url: p.sitio_web } : null, notas: '' }).subscribe({
      next: (r) => { const s = r.sugerencia || {}; p.que_ofrece = s.que_ofrece || p.que_ofrece; p.a_quien = s.a_quien || p.a_quien; p.diferencial = s.diferencial || p.diferencial; p.remitente = s.remitente || p.remitente; this.msgPerfil.set(`Propuesta lista (${r.motor === 'reglas' ? 'con los datos disponibles' : 'por el agente'}); revise y guarde.`); this.ocupado.set(false); },
      error: (e) => { this.msgPerfil.set(e.error?.error || e.message); this.ocupado.set(false); } });
  }
  cargar(): void {
    this.api.estado().subscribe((s) => this.estado.set(s));
    this.api.fuentes().subscribe((f) => this.fuentes.set(f.filter((x) => x.clave !== 'csv')));
    this.api.empresa().subscribe((e) => { this.e.set(e); this.form = { nombre: e.nombre, correo_notificaciones: e.correo_notificaciones, dapta_api_key: '', dapta_agent_id: e.dapta_agent_id, dapta_sequence_id: e.dapta_sequence_id, config: { idiomas: {}, ...e.config, perfil: { nombre: '', remitente: '', que_ofrece: '', a_quien: '', diferencial: '', nit: '', sitio_web: '', ...(e.config?.perfil || {}) } } }; this.usuario.empresa_id = e.id; });
    if (this.auth.rol === 'superadmin') this.api.empresas().subscribe({ next: (l) => this.empresas.set(l), error: () => {} });
  }
  alternar(c: string): void { const l = this.form.config.canales as string[]; this.form.config.canales = l.includes(c) ? l.filter((x) => x !== c) : [...l, c]; }
  alternarAviso(c: string): void { const l = this.form.config.notificar_por as string[]; this.form.config.notificar_por = l.includes(c) ? l.filter((x) => x !== c) : [...l, c]; }
  guardar(): void {
    this.ocupado.set(true);
    const cambio: any = { ...this.form }; if (!cambio.dapta_api_key) delete cambio.dapta_api_key;
    this.api.guardarEmpresa(cambio).subscribe({ next: () => { this.msg.set('Cambios guardados.'); this.cargar(); this.ocupado.set(false); }, error: (e) => { this.msg.set(e.message); this.ocupado.set(false); } });
  }
  crearEmpresa(): void { this.ocupado.set(true); this.api.crearEmpresa(this.nueva).subscribe({ next: (r) => { this.msgAdmin.set(`Empresa ${r.id} creada (ICP por ${r.icp_motor}).`); this.cargar(); this.ocupado.set(false); }, error: (e) => { this.msgAdmin.set(e.error?.error || e.message); this.ocupado.set(false); } }); }
  crearUsuario(): void { this.ocupado.set(true); this.api.crearUsuario(this.usuario).subscribe({ next: (r) => { this.msgAdmin.set(r.ok ? `Usuario ${r.email} creado; recibe la clave temporal por correo.` : JSON.stringify(r)); this.ocupado.set(false); }, error: (e) => { this.msgAdmin.set(e.error?.error || e.message); this.ocupado.set(false); } }); }
}
