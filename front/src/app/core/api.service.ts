import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ConfigService } from './config.service';

export interface Lead {
  id: number; razon_social: string; sector: string; subsector: string; ciudad: string; telefono: string | null; telefono_tipo: string;
  correo: string | null; sitio_web: string | null; canales: string[] | null; senales: Record<string, unknown>; fuente_clave: string; fuentes_todas: string[] | null;
  icp_score: number | null; icp_estado: string; icp_detalle: Record<string, unknown>; estado: string; identificacion: string | null; empleados: number | null;
  creado_en?: string; actualizado_en?: string;
}
export interface Metricas {
  calculado_en: string; recomendacion: string;
  embudo: { encontrados: number; del_perfil: number; a_revisar: number; contactados: number; respondieron: number; calificados: number; no_calificados: number; costo_total_usd: number; cpl_global: number | null; cplq_global: number | null };
  fuentes: Record<string, any>; canales: Record<string, any>; cruces: Record<string, any>;
  comparacion_pauta?: { pauta_usd: number; brujula_usd: number | null; base: string | null; veces: number | null } | null;
}

/** Todas las rutas de la API de Brújula. El interceptor pone el JWT. */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);
  private cfg = inject(ConfigService);
  private get base(): string { return this.cfg.config.apiUrl; }

  estado(): Observable<any> { return this.http.get(`${this.base}/api/estado`); }
  yo(): Observable<any> { return this.http.get(`${this.base}/api/yo`); }
  metricas(): Observable<Metricas> { return this.http.get<Metricas>(`${this.base}/api/metricas`); }
  enVivo(): Observable<any> { return this.http.get(`${this.base}/api/en-vivo`); }
  fuentes(): Observable<any[]> { return this.http.get<any[]>(`${this.base}/api/fuentes`); }
  buscar(cuerpo: { fuentes: string[]; ciudad: string; sector: string; limite: number; parametros?: Record<string, { ciudad?: string; sector?: string }> }): Observable<any> { return this.http.post(`${this.base}/api/buscar`, cuerpo); }
  leads(filtros: { estado?: string; fuente?: string; q?: string; limite?: number; pagina?: number; orden?: string } = {}): Observable<Lead[]> {
    let p = new HttpParams();
    Object.entries(filtros).forEach(([k, v]) => { if (v !== undefined && v !== '' && v !== null) p = p.set(k, String(v)); });
    return this.http.get<Lead[]>(`${this.base}/api/leads`, { params: p });
  }
  lead(id: number): Observable<any> { return this.http.get(`${this.base}/api/lead/${id}`); }
  revisar(id: number, decision: 'aprobar' | 'descartar'): Observable<any> { return this.http.post(`${this.base}/api/lead/${id}/revision`, { decision }); }
  mensaje(id: number, canal = 'correo', idioma = ''): Observable<any> { return this.http.get(`${this.base}/api/lead/${id}/mensaje`, { params: { canal, idioma } }); }
  respuesta(lead_id: number, texto: string, canal = 'whatsapp'): Observable<any> { return this.http.post(`${this.base}/api/respuesta`, { lead_id, texto, canal }); }
  lote(cuerpo: { n?: number | null; modo: string; motivo_override?: string; usuario?: string }): Observable<any> { return this.http.post(`${this.base}/api/lote`, cuerpo); }
  lotes(): Observable<any[]> { return this.http.get<any[]>(`${this.base}/api/lotes`); }
  bitacora(limite = 60): Observable<any[]> { return this.http.get<any[]>(`${this.base}/api/bitacora`, { params: { limite } }); }
  icp(): Observable<any> { return this.http.get(`${this.base}/api/icp`); }
  guardarIcp(icp: any): Observable<any> { return this.http.put(`${this.base}/api/icp`, icp); }
  interpretarIcp(texto: string): Observable<any> { return this.http.post(`${this.base}/api/icp/interpretar`, { texto }); }
  puntuar(todos = false): Observable<any> { return this.http.post(`${this.base}/api/puntuar`, null, { params: { todos } }); }
  sincronizar(): Observable<any> { return this.http.post(`${this.base}/api/sincronizar`, null); }
  simular(): Observable<any> { return this.http.post(`${this.base}/api/simular`, null); }
  empresa(): Observable<any> { return this.http.get(`${this.base}/api/empresa`); }
  guardarEmpresa(cambio: any): Observable<any> { return this.http.put(`${this.base}/api/empresa`, cambio); }
  empresas(): Observable<any[]> { return this.http.get<any[]>(`${this.base}/api/empresas`); }
  crearEmpresa(cuerpo: { nombre: string; correo_notificaciones: string; icp_texto: string }): Observable<any> { return this.http.post(`${this.base}/api/empresas`, cuerpo); }
  crearUsuario(cuerpo: { email: string; empresa_id: number; rol: string }): Observable<any> { return this.http.post(`${this.base}/api/usuarios`, cuerpo); }
  registro(cuerpo: { empresa: string; email: string; clave: string; icp_texto: string; nit?: string; rues?: any }): Observable<any> { return this.http.post(`${this.base}/api/registro`, cuerpo); }
  nit(nit: string): Observable<any> { return this.http.post(`${this.base}/api/nit`, { nit }); }
  asistente(mensaje: string, estado: any): Observable<any> { return this.http.post(`${this.base}/api/asistente`, { mensaje, estado }); }
  asistenteBuscar(mensaje: string, estado: any): Observable<any> { return this.http.post(`${this.base}/api/asistente/buscar`, { mensaje, estado }); }
  sitio(url: string): Observable<any> { return this.http.post(`${this.base}/api/empresa/sitio`, { url }); }
  sugerir(cuerpo: { nombre: string; rues?: any; sitio?: any; notas?: string }): Observable<any> { return this.http.post(`${this.base}/api/empresa/sugerir`, cuerpo); }
  notificaciones(noLeidas = false): Observable<any[]> { return this.http.get<any[]>(`${this.base}/api/notificaciones`, { params: { no_leidas: noLeidas } }); }
  leerNotificaciones(id?: number): Observable<any> { return this.http.post(`${this.base}/api/notificaciones/leer`, null, { params: id ? { id } : {} }); }
  urlSubida(nombre: string, content_type = 'text/csv'): Observable<any> { return this.http.post(`${this.base}/api/archivos/url-subida`, { nombre, content_type }); }
  subirLocal(clave: string, archivo: File): Observable<any> {
    const f = new FormData(); f.append('clave', clave); f.append('archivo', archivo);
    return this.http.post(`${this.base}/api/archivos/subir-local`, f);
  }
  procesarArchivo(clave: string, tipo: 'leads_csv' | 'rne'): Observable<any> { return this.http.post(`${this.base}/api/archivos/procesar`, { clave, tipo, pais: 'CO' }); }
  exportar(tipo: 'leads' | 'intentos' | 'bitacora'): Observable<any> { return this.http.get(`${this.base}/api/exportar/${tipo}`); }

  /** Sube un archivo: PUT prefirmado a S3 en la nube, o al servidor en local. Devuelve la clave. */
  async subir(archivo: File, firmar: (nombre: string) => Promise<any>): Promise<string> {
    const firma = await firmar(archivo.name);
    if (firma.metodo === 'PUT') {
      const r = await fetch(firma.url, { method: 'PUT', headers: { 'Content-Type': firma.content_type || 'text/csv' }, body: archivo });
      if (!r.ok) throw new Error(`S3 respondió ${r.status}`);
    } else {
      await this.subirLocal(firma.clave, archivo).toPromise();
    }
    return firma.clave;
  }
}
