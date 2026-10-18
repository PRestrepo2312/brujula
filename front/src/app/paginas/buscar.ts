import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiService } from '../core/api.service';
import { ChatBrujula } from './chat';

/** Buscar conversando: la brújula propone fuentes y ciudades a partir del cliente ideal; la persona corrige y confirma. */
@Component({
  selector: 'pagina-buscar',
  imports: [RouterLink, ChatBrujula],
  template: `
    <div class="page-head"><div><span class="eyebrow">Buscar</span><h1>Dígale a la brújula <em>a quién buscar</em></h1><p>Ella elige las fuentes públicas y la ciudad a partir de su cliente ideal; usted corrige conversando y confirma. Las empresas quedan en Leads con su encaje.</p></div>
      <a class="btn btn-ghost" routerLink="/buscar/manual">Elegir fuentes a mano o cargar un CSV</a></div>
    <chat-brujula [pedir]="pedir" [pistas]="pistas" [atajosPorPaso]="atajos" [esperas]="esperas">
      <a class="btn btn-primary btn-lg" routerLink="/leads">Ver los leads</a><a class="btn btn-secondary" routerLink="/lotes">Contactarlos por lotes</a>
    </chat-brujula>
  `,
})
export class BuscarPage {
  private api = inject(ApiService);
  pedir = (m: string, estado: any) => this.api.asistenteBuscar(m, estado);
  pistas = { plan: '"Sí", "en Medellín", "clínicas dentales en Cali", "reps y men", "fuentes"…', hecho: 'Otra ciudad, otro sector u otra fuente para buscar de nuevo' };
  atajos = { plan: ['Sí, busca así', 'Ver las fuentes'] };
  esperas = { plan: 'Buscando en las fuentes públicas…', hecho: 'Un momento…' };
}
