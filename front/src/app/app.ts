import { Component, inject, signal } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { ApiService } from './core/api.service';
import { AuthService } from './core/auth.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  auth = inject(AuthService);
  private api = inject(ApiService);
  estado = signal<any>(null);
  noLeidas = signal(0);

  constructor() {
    if (this.auth.autenticado) this.refrescar();
    setInterval(() => { if (this.auth.autenticado) this.refrescar(); }, 60000);
  }

  refrescar(): void {
    this.api.estado().subscribe({ next: (e) => this.estado.set(e), error: () => this.estado.set(null) });
    this.api.notificaciones(true).subscribe({ next: (n) => this.noLeidas.set(n.length), error: () => {} });
  }

  hora(iso: string): string {
    try { return new Date(iso).toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' }); } catch { return ''; }
  }
}
