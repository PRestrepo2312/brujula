import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';

@Component({
  selector: 'pagina-registro',
  imports: [FormsModule, RouterLink],
  template: `
    <div class="entrada">
      <div class="tarjeta login">
        <div class="marca-login"><i></i><div><b>BRÚJULA</b><span>Más leads, menor costo</span></div></div>
        <h2>Crear mi empresa</h2>
        <p class="sec">Su empresa es un espacio propio: nadie más ve sus leads. Usted queda como administrador y agrega a su equipo desde Configuración.</p>
        <label>Nombre de la empresa</label><input [(ngModel)]="empresa" placeholder="Ej.: Clínica Sonrisas SAS" (keyup.enter)="crear()">
        <label>Su correo</label><input type="email" [(ngModel)]="email" autocomplete="username" (keyup.enter)="crear()">
        <label>Clave (12 caracteres o más, con mayúscula, minúscula y número)</label><input type="password" [(ngModel)]="clave" autocomplete="new-password">
        <label>Repita la clave</label><input type="password" [(ngModel)]="clave2" autocomplete="new-password" (keyup.enter)="crear()">
        <label>Su cliente ideal, en sus palabras (opcional; se puede cambiar después)</label>
        <textarea rows="2" [(ngModel)]="icp" placeholder="Ej.: clínicas odontológicas en Bogotá con más de 10 empleados"></textarea>
        <button class="boton ancho" (click)="crear()" [disabled]="ocupado() || !empresa.trim() || !email || clave.length < 12 || clave !== clave2">{{ ocupado() ? 'Creando…' : 'Crear empresa y entrar' }}</button>
        @if (error()) {<div class="aviso">{{ error() }}</div>}
        <div class="enlaces"><a routerLink="/login">Ya tengo cuenta</a></div>
      </div>
    </div>`,
})
export class RegistroPage {
  private api = inject(ApiService);
  private auth = inject(AuthService);
  private router = inject(Router);
  empresa = ''; email = ''; clave = ''; clave2 = ''; icp = '';
  ocupado = signal(false); error = signal('');

  async crear(): Promise<void> {
    if (this.ocupado() || this.clave !== this.clave2) return;
    this.ocupado.set(true); this.error.set('');
    try {
      await this.api.registro({ empresa: this.empresa.trim(), email: this.email.trim(), clave: this.clave, icp_texto: this.icp.trim() }).toPromise();
      const r = await this.auth.entrar(this.email.trim(), this.clave);
      if (r.ok) this.router.navigateByUrl('/'); else this.router.navigateByUrl('/login');
    } catch (e: any) {
      this.error.set(e?.error?.error || e?.message || String(e));
    }
    this.ocupado.set(false);
  }
}
