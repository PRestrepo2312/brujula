import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { AuthService } from './auth.service';
import { ConfigService } from './config.service';

/** Pone el JWT de Cognito en las llamadas a la API. */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const cfg = inject(ConfigService);
  const propia = cfg.config.apiUrl ? req.url.startsWith(cfg.config.apiUrl) : req.url.startsWith('/');
  if (auth.activo && auth.token && propia) {
    return next(req.clone({ setHeaders: { Authorization: `Bearer ${auth.token}` } }));
  }
  return next(req);
};
