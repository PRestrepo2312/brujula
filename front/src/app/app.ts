import { Component, inject, signal } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { ApiService } from './core/api.service';
import { AuthService } from './core/auth.service';

const ENTRADA = ['/login', '/registro', '/callback'];

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  auth = inject(AuthService);
  private api = inject(ApiService);
  private router = inject(Router);
  estado = signal<any>(null);
  noLeidas = signal(0);
  enEntrada = signal(ENTRADA.some((p) => location.pathname.includes(p)));

  constructor() {
    this.router.events.subscribe((ev) => {
      if (ev instanceof NavigationEnd) {
        this.enEntrada.set(ENTRADA.some((p) => ev.urlAfterRedirects.startsWith(p)));
        if (this.auth.autenticado && !this.enEntrada()) this.refrescar();
      }
    });
    setInterval(() => { if (this.auth.autenticado && !this.enEntrada()) this.refrescar(); }, 60000);
  }

  refrescar(): void {
    this.api.estado().subscribe({ next: (e) => this.estado.set(e), error: () => this.estado.set(null) });
    this.api.notificaciones(true).subscribe({ next: (n) => this.noLeidas.set(n.length), error: () => {} });
  }

  rolTexto(): string {
    return ({ superadmin: 'Superadmin de la plataforma', admin: 'Administrador de la empresa', usuario: 'Usuario' } as Record<string, string>)[this.auth.rol] || this.auth.rol;
  }
}
