import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiService } from '../core/api.service';
import { ChatBrujula } from './chat';

/** Asistente de inicio por chat: la brújula pregunta, consulta el RUES y la página, propone, guarda y ofrece buscar de una vez. */
@Component({
  selector: 'pagina-inicio',
  imports: [RouterLink, ChatBrujula],
  template: `
    <div class="page-head"><div><span class="eyebrow">Asistente de inicio</span><h1>Cuéntele a la brújula <em>de su empresa</em></h1><p>Una conversación corta: su empresa, su página, cómo presentarse, a quién buscar y cuánto le cuesta hoy un cliente por pauta. Si ya lo hizo, arranca con lo guardado.</p></div>
      <div class="row"><button class="btn btn-secondary" (click)="chat.reiniciar()" [disabled]="chat.ocupado()">Empezar de nuevo</button><a class="btn btn-ghost" routerLink="/">Hacerlo después</a></div></div>
    <chat-brujula #chat [pedir]="pedir" [pistas]="pistas" [atajosPorPaso]="atajos" [esperas]="esperas" (respuesta)="ultimo.set($event)">
      @if (ultimo()?.resultado) {<a class="btn btn-primary btn-lg" routerLink="/leads">Ver los leads</a><a class="btn btn-secondary" routerLink="/lotes">Contactarlos por lotes</a>}
      @else {<a class="btn btn-primary btn-lg" routerLink="/buscar">Buscar empresas</a>}
      <a class="btn btn-secondary" routerLink="/configuracion">Ver lo guardado en Configuración</a>
    </chat-brujula>
  `,
})
export class InicioPage {
  private api = inject(ApiService);
  ultimo = signal<any>(null);
  pedir = (m: string, estado: any) => this.api.asistente(m, estado);
  pistas = { empresa: 'Clínica Sonrisas, NIT 900123456', sitio: 'www.suempresa.com o "no tengo"', propuesta: '"Así está bien", lo que quiera cambiar, u otro NIT o página si es otra empresa',
             pauta: '25 dólares o 90.000 pesos, o "no sé"', buscar: '"Sí", otra ciudad, otro sector o "después"', listo: 'Otro nombre o NIT para empezar de nuevo' };
  atajos = { sitio: ['No tengo página'], propuesta: ['Así está bien'], pauta: ['No sé'], buscar: ['Sí, busca ya', 'Después'] };
  esperas = { empresa: 'Consultando el RUES…', sitio: 'Leyendo la página y redactando…', propuesta: 'Redactando…', buscar: 'Buscando en las fuentes públicas…' };
}
