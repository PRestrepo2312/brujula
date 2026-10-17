import { Component, inject } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../core/auth.service';

@Component({
  selector: 'pagina-login',
  template: `
    <div class="tarjeta" style="max-width:520px;margin:60px auto;text-align:center">
      <h1>Brújula</h1>
      <p>Encuentra leads en fuentes públicas, los contacta y mide cuánto cuesta cada lead calificado por fuente y canal.</p>
      @if (auth.activo) {
        <button class="boton" (click)="auth.login('/')">Entrar con mi cuenta</button>
        <p class="sec">Las cuentas las crea el administrador de la empresa.</p>
      } @else {
        <button class="boton" (click)="entrar()">Entrar (modo local, sin login)</button>
      }
    </div>`,
})
export class LoginPage {
  auth = inject(AuthService);
  private router = inject(Router);
  entrar(): void { this.router.navigateByUrl('/'); }
}
