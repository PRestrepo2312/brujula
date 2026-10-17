import { Routes } from '@angular/router';
import { authGuard } from './core/auth.guard';

export const routes: Routes = [
  { path: 'login', loadComponent: () => import('./paginas/login').then((m) => m.LoginPage) },
  { path: 'callback', loadComponent: () => import('./paginas/callback').then((m) => m.CallbackPage) },
  { path: 'registro', loadComponent: () => import('./paginas/registro').then((m) => m.RegistroPage) },
  { path: '', canActivate: [authGuard], loadComponent: () => import('./paginas/tablero').then((m) => m.TableroPage) },
  { path: 'buscar', canActivate: [authGuard], loadComponent: () => import('./paginas/buscar').then((m) => m.BuscarPage) },
  { path: 'leads', canActivate: [authGuard], loadComponent: () => import('./paginas/leads').then((m) => m.LeadsPage) },
  { path: 'leads/:id', canActivate: [authGuard], loadComponent: () => import('./paginas/lead-detalle').then((m) => m.LeadDetallePage) },
  { path: 'lotes', canActivate: [authGuard], loadComponent: () => import('./paginas/lotes').then((m) => m.LotesPage) },
  { path: 'notificaciones', canActivate: [authGuard], loadComponent: () => import('./paginas/notificaciones').then((m) => m.NotificacionesPage) },
  { path: 'configuracion', canActivate: [authGuard], loadComponent: () => import('./paginas/configuracion').then((m) => m.ConfiguracionPage) },
  { path: '**', redirectTo: '' },
];
