import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';

/** Sin sesión y con Cognito activo, va al formulario de entrada y vuelve a la ruta pedida. */
export const authGuard: CanActivateFn = (route, state) => {
  const auth = inject(AuthService);
  if (auth.autenticado) return true;
  return inject(Router).createUrlTree(['/login'], { queryParams: { next: state.url } });
};
