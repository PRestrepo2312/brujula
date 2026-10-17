import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';

@Component({
  selector: 'pagina-configuracion',
  imports: [FormsModule],
  template: `
    <h1>Configuración de <em>la empresa</em></h1>
    @if (e(); as e) {
      <div class="fila c2">
        <div class="tarjeta">
          <h2>{{ e.nombre }}</h2>
          <div class="fila c2" style="margin:0 0 10px">
            <div><label>Nombre</label><input [(ngModel)]="form.nombre"></div>
            <div><label>Correo para notificaciones</label><input [(ngModel)]="form.correo_notificaciones" placeholder="ventas@empresa.com"></div>
          </div>
          <div class="fila c2" style="margin:0 0 10px">
            <div><label>Leads por lote</label><input type="number" [(ngModel)]="form.config.presupuesto_lote" min="1" max="500"></div>
            <div><label>Canales activos</label><div class="acciones">
              @for (c of ['voz','correo','whatsapp']; track c) {<span class="chip" [class.on]="form.config.canales.includes(c)" (click)="alternar(c)">{{ c }}</span>}
            </div></div>
          </div>
          <div><label>Avisar por</label><div class="acciones">
            @for (c of ['app','correo']; track c) {<span class="chip" [class.on]="form.config.notificar_por.includes(c)" (click)="alternarAviso(c)">{{ c }}</span>}
          </div></div>
          <div style="margin-top:12px"><label>Idioma de los mensajes por fuente (sin elegir: el del país de la fuente)</label>
            <div class="acciones">
              @for (f of fuentes(); track f.clave) {
                <span class="chip" style="cursor:default">{{ f.clave.toUpperCase() }}
                  <select [(ngModel)]="form.config.idiomas[f.clave]" style="width:auto;padding:2px 4px;border:0;background:transparent">
                    <option value="">{{ nombreIdioma(f.idioma) }} (país)</option><option value="es">Español</option><option value="pt">Português</option><option value="en">English</option>
                  </select></span>
              }
            </div>
          </div>
          <div style="margin-top:12px"><label>Horario de la Ley 2300 (lunes a viernes 7 a. m. a 7 p. m., sábados 8 a. m. a 3 p. m., nunca domingos ni festivos)</label>
            <div class="acciones">
              <span class="chip" [class.on]="form.config.respetar_ley_2300 !== false" (click)="form.config.respetar_ley_2300 = true">Respetar el horario</span>
              <span class="chip" [class.on]="form.config.respetar_ley_2300 === false" (click)="form.config.respetar_ley_2300 = false">Desactivar bajo mi responsabilidad</span>
            </div>
            @if (form.config.respetar_ley_2300 === false) {<div class="aviso">Con el horario desactivado los lotes salen a cualquier hora sin pedir motivo y la secuencia de Dapta llama todos los días a toda hora. El cambio queda en la bitácora con su usuario.</div>}
          </div>
          <h2 style="margin-top:16px">Dapta de la empresa</h2>
          <p class="sec">Clave MCP: {{ e.dapta_api_key || 'usa la del servidor (demo)' }}</p>
          <div class="fila c3" style="margin:0 0 10px">
            <div><label>Nueva clave MCP</label><input type="password" [(ngModel)]="form.dapta_api_key" placeholder="dapta_pat_…"></div>
            <div><label>Agente de voz (id)</label><input [(ngModel)]="form.dapta_agent_id"></div>
            <div><label>Secuencia (id)</label><input [(ngModel)]="form.dapta_sequence_id"></div>
          </div>
          <div class="acciones"><button class="boton" (click)="guardar()" [disabled]="ocupado()">Guardar</button>@if (msg()) {<span class="sec">{{ msg() }}</span>}</div>
        </div>
        <div class="tarjeta">
          @if (estado(); as s) {
            <h2>Modo prueba <span class="pill" [class.prueba]="s.modo_prueba?.activo">{{ s.modo_prueba?.activo ? 'activo: desvío' : 'apagado: contacto real' }}</span></h2>
            <p class="sec">Demo real sin tocar a terceros: la búsqueda, el ICP, el pitch con el nombre y las señales de cada empresa, el lote y las métricas corren igual,
              pero la llamada del agente se marca a <b>{{ s.modo_prueba?.telefono || 'ningún número (se fija al desplegar con TELEFONO_PRUEBA)' }}</b> (una por lote)
              y los correos van a <b>{{ s.modo_prueba?.correos?.join(', ') || 'ningún correo' }}</b> (identidades verificadas en SES). El intento guarda el destino original y el desviado.
              Para contactar de verdad se despliega con MODO_PRUEBA=0 y sin destinos.</p>
            <hr style="border:0;border-top:1px solid var(--border);margin:16px 0">
          }
          <h2>Su cuenta</h2>
          <p>{{ auth.email }} · {{ auth.rol === 'superadmin' ? 'superadmin de la plataforma' : auth.rol === 'admin' ? 'administrador de esta empresa' : 'usuario de esta empresa' }}.
            Cada empresa es un espacio aparte: sus leads, lotes, métricas y configuración solo los ven sus usuarios.</p>
          @if (auth.rol === 'superadmin') {
            <h2 style="margin-top:14px">Empresas (superadmin)</h2>
            <table><thead><tr><th>#</th><th>Nombre</th><th>Correo</th></tr></thead><tbody>@for (x of empresas(); track x.id) {<tr><td>{{ x.id }}</td><td>{{ x.nombre }}</td><td>{{ x.correo_notificaciones }}</td></tr>}</tbody></table>
            <p class="sec">Para mirar otra empresa agregue <code>?empresa=ID</code> a la dirección.</p>
            <h2 style="margin-top:14px">Nueva empresa</h2>
            <div class="fila c2" style="margin:0 0 8px"><div><label>Nombre</label><input [(ngModel)]="nueva.nombre"></div><div><label>Correo</label><input [(ngModel)]="nueva.correo_notificaciones"></div></div>
            <div><label>Cliente ideal (en sus palabras)</label><textarea rows="2" [(ngModel)]="nueva.icp_texto"></textarea></div>
            <div class="acciones" style="margin-top:8px"><button class="boton sec" (click)="crearEmpresa()" [disabled]="!nueva.nombre || ocupado()">Crear empresa</button></div>
          }
          @if (auth.rol === 'admin' || auth.rol === 'superadmin') {
            <h2 style="margin-top:14px">Agregar una persona {{ auth.rol === 'superadmin' ? '' : 'a mi empresa' }}</h2>
            <p class="sec">Recibe por correo una clave temporal y entra directo al espacio de la empresa. "usuario" trabaja con los leads; "admin" además configura y agrega gente.</p>
            <div class="fila c3" style="margin:0 0 8px">
              <div><label>Correo</label><input [(ngModel)]="usuario.email"></div>
              @if (auth.rol === 'superadmin') {<div><label>Empresa (id)</label><input type="number" [(ngModel)]="usuario.empresa_id"></div>}
              <div><label>Rol</label><select [(ngModel)]="usuario.rol"><option value="usuario">usuario</option><option value="admin">admin</option>@if (auth.rol === 'superadmin') {<option value="superadmin">superadmin</option>}</select></div>
            </div>
            <div class="acciones"><button class="boton sec" (click)="crearUsuario()" [disabled]="!usuario.email || ocupado()">Crear usuario</button>@if (msgAdmin()) {<span class="sec">{{ msgAdmin() }}</span>}</div>
          }
        </div>
      </div>
    } @else { <p class="sec">Cargando…</p> }
  `,
})
export class ConfiguracionPage {
  private api = inject(ApiService);
  auth = inject(AuthService);
  e = signal<any>(null);
  empresas = signal<any[]>([]);
  form: any = { nombre: '', correo_notificaciones: '', dapta_api_key: '', dapta_agent_id: '', dapta_sequence_id: '', config: { canales: ['voz', 'correo'], presupuesto_lote: 20, notificar_por: ['app', 'correo'] } };
  nueva = { nombre: '', correo_notificaciones: '', icp_texto: '' };
  usuario = { email: '', empresa_id: 1, rol: 'usuario' };
  estado = signal<any>(null);
  fuentes = signal<any[]>([]);
  msg = signal(''); msgAdmin = signal(''); ocupado = signal(false);

  constructor() { this.cargar(); }
  nombreIdioma(c: string): string { return ({ es: 'Español', pt: 'Português', en: 'English' } as Record<string, string>)[c] || c; }
  cargar(): void {
    this.api.estado().subscribe((s) => this.estado.set(s));
    this.api.fuentes().subscribe((f) => this.fuentes.set(f.filter((x) => x.clave !== 'csv')));
    this.api.empresa().subscribe((e) => { this.e.set(e); this.form = { nombre: e.nombre, correo_notificaciones: e.correo_notificaciones, dapta_api_key: '', dapta_agent_id: e.dapta_agent_id, dapta_sequence_id: e.dapta_sequence_id, config: { idiomas: {}, ...e.config } }; this.usuario.empresa_id = e.id; });
    if (this.auth.rol === 'superadmin') this.api.empresas().subscribe({ next: (l) => this.empresas.set(l), error: () => {} });
  }
  alternar(c: string): void { const l = this.form.config.canales as string[]; this.form.config.canales = l.includes(c) ? l.filter((x) => x !== c) : [...l, c]; }
  alternarAviso(c: string): void { const l = this.form.config.notificar_por as string[]; this.form.config.notificar_por = l.includes(c) ? l.filter((x) => x !== c) : [...l, c]; }
  guardar(): void {
    this.ocupado.set(true);
    const cambio: any = { ...this.form }; if (!cambio.dapta_api_key) delete cambio.dapta_api_key;
    this.api.guardarEmpresa(cambio).subscribe({ next: () => { this.msg.set('Guardado.'); this.cargar(); this.ocupado.set(false); }, error: (e) => { this.msg.set(e.message); this.ocupado.set(false); } });
  }
  crearEmpresa(): void { this.ocupado.set(true); this.api.crearEmpresa(this.nueva).subscribe({ next: (r) => { this.msgAdmin.set(`Empresa ${r.id} creada (ICP por ${r.icp_motor}).`); this.cargar(); this.ocupado.set(false); }, error: (e) => { this.msgAdmin.set(e.error?.error || e.message); this.ocupado.set(false); } }); }
  crearUsuario(): void { this.ocupado.set(true); this.api.crearUsuario(this.usuario).subscribe({ next: (r) => { this.msgAdmin.set(r.ok ? `Usuario ${r.email} creado; recibe la contraseña temporal por correo.` : JSON.stringify(r)); this.ocupado.set(false); }, error: (e) => { this.msgAdmin.set(e.error?.error || e.message); this.ocupado.set(false); } }); }
}
