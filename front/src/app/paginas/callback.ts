import { Component, inject, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../core/auth.service';

@Component({
  selector: 'pagina-callback',
  template: `<div class="auth-form" style="min-height:100vh"><div class="auth-card card">
    @if (error()) {<div class="banner banner-danger">{{ error() }}</div><a href="login">Volver a intentar</a>} @else {<p class="muted">Entrando…</p>}
  </div></div>`,
})
export class CallbackPage {
  private auth = inject(AuthService);
  private ruta = inject(ActivatedRoute);
  private router = inject(Router);
  error = signal('');

  constructor() {
    const q = this.ruta.snapshot.queryParamMap;
    const code = q.get('code') || '';
    const state = q.get('state') || '';
    if (!code) { this.router.navigateByUrl('/login'); return; }
    this.auth.callback(code, state).then((destino) => this.router.navigateByUrl(destino)).catch((e) => this.error.set(String(e)));
  }
}
