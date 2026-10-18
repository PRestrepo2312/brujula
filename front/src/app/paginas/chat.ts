import { AfterViewChecked, Component, ElementRef, input, OnInit, output, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Observable } from 'rxjs';

export interface Turno { de: 'brujula' | 'yo'; texto: string }

/** El chat de la brújula: hilo, atajos por paso y entrada. La página dueña decide a qué API habla y qué botones mostrar al terminar. */
@Component({
  selector: 'chat-brujula',
  imports: [FormsModule],
  template: `
    <div class="chat card">
      <div class="hilo" #hilo>
        @for (t of turnos(); track $index) {
          <div class="burbuja" [class.yo]="t.de === 'yo'">
            @if (t.de === 'brujula') {<div class="quien"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="10"/><path d="M15.6 8.4 13.5 13.5 8.4 15.6l2.1-5.1z" fill="currentColor" stroke="none"/></svg></div>}
            <div class="texto">{{ t.texto }}</div>
          </div>
        }
        @if (ocupado()) {<div class="burbuja"><div class="quien"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="10"/></svg></div><div class="texto muted">{{ esperando() }}</div></div>}
      </div>
      @if (listo()) {<div class="row" style="margin-top:14px"><ng-content></ng-content></div>}
      <div class="atajos">
        @for (a of atajos(); track a) {<button class="choice" (click)="enviar(a)" [disabled]="ocupado()">{{ a }}</button>}
      </div>
      <div class="entrada">
        <input [(ngModel)]="texto" [placeholder]="pista()" (keyup.enter)="enviar()" [disabled]="ocupado()">
        <button class="btn btn-primary" (click)="enviar()" [disabled]="ocupado() || !texto.trim()">Enviar</button>
      </div>
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
export class ChatBrujula implements OnInit, AfterViewChecked {
  /** Cómo hablar con el servidor: (mensaje, estado) → respuesta {respuesta, paso, datos, listo?}. */
  pedir = input.required<(m: string, estado: any) => Observable<any>>();
  pistas = input<Record<string, string>>({});
  atajosPorPaso = input<Record<string, string[]>>({});
  /** Texto mientras el servidor trabaja, por paso (p. ej. "Buscando en las fuentes…"). */
  esperas = input<Record<string, string>>({});
  respuesta = output<any>();
  hilo = viewChild<ElementRef<HTMLDivElement>>('hilo');
  turnos = signal<Turno[]>([]);
  estado: any = { paso: '', datos: {} };
  texto = '';
  ocupado = signal(false);
  listo = signal(false);
  private pasoEnCurso = '';

  ngOnInit(): void { this.enviar('', true); }
  ngAfterViewChecked(): void { const h = this.hilo()?.nativeElement; if (h) h.scrollTop = h.scrollHeight; }
  pista(): string { return this.pistas()[this.estado.paso] || ''; }
  atajos(): string[] { return this.atajosPorPaso()[this.estado.paso] || []; }
  esperando(): string { return this.esperas()[this.pasoEnCurso] || 'Un momento…'; }
  reiniciar(): void { this.turnos.set([]); this.estado = { paso: '', datos: {} }; this.listo.set(false); this.enviar('', true); }

  enviar(texto?: string, inicial = false): void {
    const m = (texto ?? this.texto).trim();
    if (!inicial && !m) return;
    if (!inicial) this.turnos.update((t) => [...t, { de: 'yo', texto: m }]);
    this.texto = ''; this.ocupado.set(true); this.pasoEnCurso = this.estado.paso;
    this.pedir()(inicial ? '' : m, this.estado).subscribe({
      next: (r) => {
        this.estado = { paso: r.paso, datos: r.datos };
        this.turnos.update((t) => [...t, { de: 'brujula', texto: r.respuesta }]);
        this.listo.set(!!r.listo); this.ocupado.set(false); this.respuesta.emit(r);
      },
      error: (e) => { this.turnos.update((t) => [...t, { de: 'brujula', texto: 'Algo falló: ' + (e.error?.error || e.message) + '. Intente de nuevo.' }]); this.ocupado.set(false); } });
  }
}
