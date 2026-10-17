import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../core/auth.service';

type Modo = 'clave' | 'nueva' | 'olvide' | 'codigo';

@Component({
  selector: 'pagina-login',
  imports: [FormsModule],
  template: `
    <div class="entrada">
      <div class="tarjeta login">
        <div class="marca-login"><i></i><div><b>BRÚJULA</b><span>Más leads, menor costo</span></div></div>
        @if (!auth.activo) {
          <p>Modo local: sin login.</p>
          <button class="boton ancho" (click)="ir()">Entrar</button>
        } @else {
          @switch (modo()) {
            @case ('clave') {
              <h2>Entrar</h2>
              <label>Correo</label><input type="email" [(ngModel)]="email" autocomplete="username" (keyup.enter)="entrar()">
              <label>Clave</label><input type="password" [(ngModel)]="clave" autocomplete="current-password" (keyup.enter)="entrar()">
              <button class="boton ancho" (click)="entrar()" [disabled]="ocupado() || !email || !clave">{{ ocupado() ? 'Entrando…' : 'Entrar' }}</button>
              <div class="enlaces"><a (click)="cambiar('olvide')">Olvidé mi clave</a><a (click)="auth.login(siguiente)">Entrar con la página de Cognito</a></div>
            }
            @case ('nueva') {
              <h2>Clave nueva</h2>
              <p class="sec">Es su primer ingreso: elija una clave de 12 caracteres o más, con mayúscula, minúscula y número.</p>
              <label>Clave nueva</label><input type="password" [(ngModel)]="nueva" autocomplete="new-password">
              <label>Repítala</label><input type="password" [(ngModel)]="nueva2" autocomplete="new-password" (keyup.enter)="fijarNueva()">
              <button class="boton ancho" (click)="fijarNueva()" [disabled]="ocupado() || nueva.length < 12 || nueva !== nueva2">Guardar y entrar</button>
            }
            @case ('olvide') {
              <h2>Recuperar la clave</h2>
              <p class="sec">Le enviamos un código al correo de su cuenta.</p>
              <label>Correo</label><input type="email" [(ngModel)]="email" autocomplete="username" (keyup.enter)="pedirCodigo()">
              <button class="boton ancho" (click)="pedirCodigo()" [disabled]="ocupado() || !email">Enviar código</button>
              <div class="enlaces"><a (click)="cambiar('clave')">Volver</a></div>
            }
            @case ('codigo') {
              <h2>Código y clave nueva</h2>
              <label>Código del correo</label><input [(ngModel)]="codigo" inputmode="numeric" autocomplete="one-time-code">
              <label>Clave nueva</label><input type="password" [(ngModel)]="nueva" autocomplete="new-password">
              <label>Repítala</label><input type="password" [(ngModel)]="nueva2" autocomplete="new-password" (keyup.enter)="confirmarCodigo()">
              <button class="boton ancho" (click)="confirmarCodigo()" [disabled]="ocupado() || !codigo || nueva.length < 12 || nueva !== nueva2">Cambiar clave y entrar</button>
              <div class="enlaces"><a (click)="cambiar('clave')">Volver</a></div>
            }
          }
          @if (error()) {<div class="aviso">{{ error() }}</div>}
          @if (info()) {<div class="ok-msg">{{ info() }}</div>}
          <p class="sec pie-login">Las cuentas las crea el administrador de su empresa. La clave viaja cifrada directo a Amazon Cognito; Brújula nunca la ve.</p>
        }
      </div>
    </div>`,
})
export class LoginPage {
  auth = inject(AuthService);
  private router = inject(Router);
  siguiente = inject(ActivatedRoute).snapshot.queryParamMap.get('next') || '/';
  modo = signal<Modo>('clave');
  email = ''; clave = ''; nueva = ''; nueva2 = ''; codigo = '';
  private session = '';
  ocupado = signal(false); error = signal(''); info = signal('');

  constructor() { if (this.auth.autenticado) this.ir(); }

  ir(): void { this.router.navigateByUrl(this.siguiente); }
  cambiar(m: Modo): void { this.modo.set(m); this.error.set(''); this.info.set(''); }

  private async correr(accion: () => Promise<void>): Promise<void> {
    this.ocupado.set(true); this.error.set(''); this.info.set('');
    try { await accion(); } catch (e: any) { this.error.set(e?.message || String(e)); }
    this.ocupado.set(false);
  }

  entrar(): void {
    this.correr(async () => {
      const r = await this.auth.entrar(this.email, this.clave);
      if (r.ok) { this.ir(); return; }
      if (r.desafio === 'NEW_PASSWORD_REQUIRED') { this.session = r.session || ''; this.modo.set('nueva'); }
    });
  }

  fijarNueva(): void {
    this.correr(async () => { await this.auth.claveNueva(this.email, this.nueva, this.session); this.ir(); });
  }

  pedirCodigo(): void {
    this.correr(async () => { await this.auth.olvide(this.email); this.modo.set('codigo'); this.info.set('Código enviado. Revise el correo (también la carpeta de spam).'); });
  }

  confirmarCodigo(): void {
    this.correr(async () => {
      await this.auth.confirmarOlvide(this.email, this.codigo, this.nueva);
      const r = await this.auth.entrar(this.email, this.nueva);
      if (r.ok) this.ir(); else this.modo.set('clave');
    });
  }
}
