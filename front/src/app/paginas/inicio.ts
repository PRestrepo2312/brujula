import { AfterViewChecked, Component, ElementRef, inject, signal, ViewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { ApiService } from '../core/api.service';

interface Turno { de: 'brujula' | 'yo'; texto: string }

/** Asistente de inicio por chat: la brújula pregunta, consulta el RUES y la página, propone y guarda. Sin formularios. */
@Component({
  selector: 'pagina-inicio',
  imports: [FormsModule, RouterLink],
  template: `
    <div class="page-head"><div><span class="eyebrow">Asistente de inicio</span><h1>Cuéntele a la brújula <em>de su empresa</em></h1><p>Una conversación corta: su empresa, su página, cómo presentarse, a quién buscar y cuánto le cuesta hoy un cliente por pauta.</p></div>
      <a class="btn btn-ghost" routerLink="/">Hacerlo después</a></div>
    <div class="chat card">
      <div class="hilo" #hilo>
        @for (t of turnos(); track $index) {
          <div class="burbuja" [class.yo]="t.de === 'yo'">
            @if (t.de === 'brujula') {<div class="quien"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="10"/><path d="M15.6 8.4 13.5 13.5 8.4 15.6l2.1-5.1z" fill="currentColor" stroke="none"/></svg></div>}
            <div class="texto">{{ t.texto }}</div>
          </div>
        }
        @if (ocupado()) {<div class="burbuja"><div class="quien"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="10"/></svg></div><div class="texto muted">Un momento…</div></div>}
      </div>
      @if (listo()) {
        <div class="row" style="margin-top:14px"><a class="btn btn-primary btn-lg" routerLink="/buscar">Buscar empresas</a><a class="btn btn-secondary" routerLink="/configuracion">Ver lo guardado en Configuración</a></div>
      } @else {
        <div class="atajos">
          @for (a of atajos(); track a) {<button class="choice" (click)="enviar(a)" [disabled]="ocupado()">{{ a }}</button>}
        </div>
        <div class="entrada">
          <input [(ngModel)]="texto" [placeholder]="pista()" (keyup.enter)="enviar()" [disabled]="ocupado()">
          <button class="btn btn-primary" (click)="enviar()" [disabled]="ocupado() || !texto.trim()">Enviar</button>
        </div>
      }
    </div>
  `,
  styles: [`
    .chat { max-width: 860px; }
    .hilo { display: flex; flex-direction: column; gap: 12px; max-height: 56vh; overflow-y: auto; padding: 4px 2px; }
    .burbuja { display: flex; gap: 10px; align-items: flex-start; max-width: 88%; }
    .burbuja.yo { align-self: flex-end; flex-direction: row-reverse; }
    .quien { flex: none; width: 30px; height: 30px; border-radius: 50%; background: var(--ink); color: #93B4FF; display: grid; place-items: center; } .quien svg { width: 18px; height: 18px; }
    .texto { background: #F2F5FA; border: 1px solid var(--line); border-radius: 12px; padding: 10px 14px; white-space: pre-wrap; font-size: 14px; line-height: 1.5; }
    .yo .texto { background: var(--accent); border-color: var(--accent); color: #fff; }
    .atajos { display: flex; gap: 8px; flex-wrap: wrap; margin: 14px 0 8px; }
    .entrada { display: flex; gap: 8px; } .entrada input { flex: 1; }
  `],
})
export class InicioPage implements AfterViewChecked {
  private api = inject(ApiService);
  private router = inject(Router);
  @ViewChild('hilo') hilo?: ElementRef<HTMLDivElement>;
  turnos = signal<Turno[]>([]);
  estado: any = { paso: 'empresa', datos: {} };
  texto = '';
  ocupado = signal(false);
  listo = signal(false);

  constructor() { this.enviar('', true); }

  ngAfterViewChecked(): void { const h = this.hilo?.nativeElement; if (h) h.scrollTop = h.scrollHeight; }

  pista(): string {
    return ({ empresa: 'Clínica Sonrisas, NIT 900123456', sitio: 'www.suempresa.com o "no tengo"', propuesta: '"Así está bien" o lo que quiera cambiar', pauta: '25 dólares o 90.000 pesos, o "no sé"' } as Record<string, string>)[this.estado.paso] || '';
  }
  atajos(): string[] {
    return ({ sitio: ['No tengo página'], propuesta: ['Así está bien'], pauta: ['No sé'] } as Record<string, string[]>)[this.estado.paso] || [];
  }

  enviar(texto?: string, inicial = false): void {
    const m = (texto ?? this.texto).trim();
    if (!inicial && !m) return;
    if (!inicial) this.turnos.update((t) => [...t, { de: 'yo', texto: m }]);
    this.texto = ''; this.ocupado.set(true);
    this.api.asistente(inicial ? '' : m, this.estado).subscribe({
      next: (r) => {
        this.estado = { paso: r.paso, datos: r.datos };
        this.turnos.update((t) => [...t, { de: 'brujula', texto: r.respuesta }]);
        if (r.listo) this.listo.set(true);
        this.ocupado.set(false);
      },
      error: (e) => { this.turnos.update((t) => [...t, { de: 'brujula', texto: 'Algo falló: ' + (e.error?.error || e.message) + '. Intente de nuevo.' }]); this.ocupado.set(false); } });
  }
}
