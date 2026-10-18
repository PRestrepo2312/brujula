import { Component, input } from '@angular/core';

/** Reglas de la clave (las mismas del User Pool y de auth.validar_clave): 12 o más, mayúscula, minúscula y número. */
export const REGLAS_CLAVE: { clave: string; texto: string; cumple: (c: string) => boolean }[] = [
  { clave: 'largo', texto: '12 caracteres o más', cumple: (c) => c.length >= 12 },
  { clave: 'mayus', texto: 'una mayúscula', cumple: (c) => /[A-ZÁÉÍÓÚÑ]/.test(c) },
  { clave: 'minus', texto: 'una minúscula', cumple: (c) => /[a-záéíóúñ]/.test(c) },
  { clave: 'numero', texto: 'un número', cumple: (c) => /\d/.test(c) },
];
export function claveValida(c: string): boolean { return REGLAS_CLAVE.every((r) => r.cumple(c)); }

/** Lista viva bajo el campo de clave: cada regla dice "falta" o "listo" mientras la persona escribe, y si la repetición coincide. */
@Component({
  selector: 'clave-requisitos',
  template: `
    <ul class="reqs" aria-live="polite">
      @for (r of reglas; track r.clave) {
        <li [class.ok]="r.cumple(clave())" [class.falta]="clave() && !r.cumple(clave())"><span class="marca">{{ r.cumple(clave()) ? 'listo' : 'falta' }}</span>{{ r.texto }}</li>
      }
      @if (repetida() !== null) {
        <li [class.ok]="clave() && clave() === repetida()" [class.falta]="repetida() && clave() !== repetida()"><span class="marca">{{ clave() && clave() === repetida() ? 'listo' : 'falta' }}</span>las dos claves iguales</li>
      }
    </ul>
  `,
  styles: [`
    .reqs { list-style: none; margin: 8px 0 0; padding: 0; display: grid; gap: 4px; font-size: 12.5px; color: var(--muted); }
    .reqs li { display: flex; align-items: center; gap: 8px; }
    .marca { font-family: var(--mono); font-size: 10px; letter-spacing: .06em; text-transform: uppercase; padding: 1px 6px; border-radius: 999px; background: #EEF1F6; color: #6B7280; min-width: 44px; text-align: center; }
    .ok { color: var(--ink); } .ok .marca { background: #D7F0E6; color: #0F6E56; }
    .falta { color: #B91C1C; } .falta .marca { background: #FDE2E2; color: #B91C1C; }
  `],
})
export class ClaveRequisitos {
  clave = input<string>('');
  /** null = no mostrar la fila de "las dos claves iguales". */
  repetida = input<string | null>(null);
  reglas = REGLAS_CLAVE;
}
