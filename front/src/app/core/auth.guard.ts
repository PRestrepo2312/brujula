import { inject } from '@angular/core';
import { CanActivateFn } from '@angular/router';
import { AuthService } from './auth.service';

/** Sin sesión y con Cognito activo, manda a la página de login de Cognito y vuelve a la ruta pedida. */
export const authGuard: CanActivateFn = (route, state) => {
  const auth = inject(AuthService);
  if (auth.autenticado) return true;
  auth.login(state.url);
  return false;
};
