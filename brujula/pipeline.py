"""Orquestación por empresa: preparar un lote (manual o con la brújula), ejecutarlo por canal, registrar respuestas y sincronizar con Dapta."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from sqlmodel import select

from . import agente
from .bandit import Brazo, repartir
from .channels import canal as canal_de
from .compliance import anotar, esta_excluido, registrar_exclusion, ventana_permitida, verificar_lead
from .config import config
from .db import sesion
from .empresas import config_de, dapta_de, icp_de
from .models import Bitacora, Calificacion, Intento, Lead, Lote
from .notificaciones import notificar

CANALES_POSIBLES = ("voz", "correo")   # whatsapp entra cuando exista línea aprobada


def _canales(empresa_id: int) -> tuple[str, ...]:
    activos = [c for c in config_de(empresa_id).get("canales", CANALES_POSIBLES) if c in CANALES_POSIBLES]
    return tuple(activos) or CANALES_POSIBLES


def _brazos(s, empresa_id: int) -> list[Brazo]:
    canales = _canales(empresa_id)
    leads = s.exec(select(Lead).where(Lead.empresa_id == empresa_id, Lead.duplicado_de.is_(None), Lead.icp_estado == "pasa", Lead.estado == "listo")).all()
    intentos = s.exec(select(Intento).where(Intento.empresa_id == empresa_id)).all()
    lead_por_id = {l.id: l for l in s.exec(select(Lead).where(Lead.empresa_id == empresa_id, Lead.duplicado_de.is_(None))).all()}
    calificados = {c.lead_id for c in s.exec(select(Calificacion).where(Calificacion.empresa_id == empresa_id, Calificacion.resultado == "calificado")).all()}
    hay_calificaciones = bool(calificados)
    from .config import config
    brazos: dict[str, Brazo] = {}
    for l in leads:
        for c in canales:
            # En modo prueba solo cuentan los canales que tienen destino de desvío.
            if c in (l.canales or []) and (not config.modo_prueba or config.destino_prueba(c)):
                b = brazos.setdefault(f"{l.fuente_clave}|{c}", Brazo(l.fuente_clave, c))
                b.disponibles += 1
    for it in intentos:
        l = lead_por_id.get(it.lead_id)
        if not l or it.canal not in canales:
            continue
        b = brazos.setdefault(f"{l.fuente_clave}|{it.canal}", Brazo(l.fuente_clave, it.canal))
        if it.estado in ("programado", "fallido"):
            continue
        b.intentos += 1
        b.costo_usd += it.costo_usd
        exito = (it.lead_id in calificados) if hay_calificaciones else (it.estado in ("respondio", "contestado") or it.clasificacion in ("interesado", "no_interesado", "despues"))
        b.exitos += 1 if exito else 0
    return list(brazos.values())


def preparar_lote(n: int | None = None, modo: str = "brujula", reparto: dict[str, int] | None = None, usuario: str = "",
                  motivo_override: str = "", empresa_id: int = 1) -> dict:
    """Crea el lote y sus intentos (programados). Respeta la ventana legal salvo override explícito con motivo."""
    cfg = config_de(empresa_id)
    n = n or int(cfg.get("presupuesto_lote", 20))
    permitido, razon = ventana_permitida()
    fuera = not permitido
    respetar = bool(cfg.get("respetar_ley_2300", True))
    if fuera and respetar and not motivo_override:
        return {"error": f"No se puede contactar ahora: {razon}. Para hacerlo igual, pase un motivo de override.", "fuera_ventana": True}
    if fuera and not respetar and not motivo_override:
        # La empresa desactivó el horario legal en su configuración: el lote sale igual y queda constancia.
        motivo_override = "horario de la Ley 2300 desactivado en la configuración de la empresa"
    with sesion() as s:
        brazos = _brazos(s, empresa_id)
        if modo == "brujula" or not reparto:
            reparto, explicacion = repartir(brazos, n)
        else:
            explicacion = "Reparto manual: " + ", ".join(f"{k} {v}" for k, v in reparto.items())
        if not reparto:
            return {"error": "No hay leads listos con canal disponible. Corra una búsqueda y puntúe el ICP primero."}
        lote = Lote(empresa_id=empresa_id, reparto=reparto, explicacion=explicacion, modo=modo, fuera_ventana=fuera, override_motivo=motivo_override, override_usuario=usuario)
        s.add(lote)
        s.commit()
        s.refresh(lote)
        creados = 0
        omitidos = defaultdict(int)
        for clave, cupo in reparto.items():
            fuente, canal = clave.split("|", 1)
            leads = s.exec(select(Lead).where(Lead.empresa_id == empresa_id, Lead.duplicado_de.is_(None), Lead.icp_estado == "pasa", Lead.estado == "listo",
                                              Lead.fuente_clave == fuente).order_by(Lead.icp_score.desc(), Lead.id)).all()
            for l in leads:
                if cupo <= 0:
                    break
                if canal not in (l.canales or []):
                    continue
                ok, por_que = verificar_lead(l, canal)
                if not ok:
                    omitidos[por_que] += 1
                    continue
                s.add(Intento(empresa_id=empresa_id, lead_id=l.id, lote_id=lote.id, canal=canal, estado="programado", fuera_ventana=fuera))
                l.estado = "contactado"
                l.actualizado_en = datetime.utcnow()
                s.add(l)
                cupo -= 1
                creados += 1
        s.commit()
        if fuera:
            anotar("override", f"Lote {lote.id} fuera de la ventana de la Ley 2300", empresa_id, lote_id=lote.id, usuario=usuario, motivo=motivo_override, contactos=creados, razon=razon)
        anotar("reparto", explicacion, empresa_id, lote_id=lote.id, reparto=reparto, modo=modo)
        return {"lote_id": lote.id, "reparto": reparto, "explicacion": explicacion, "intentos": creados, "omitidos": dict(omitidos),
                "fuera_ventana": fuera, "ventana": razon}


def ejecutar_lote(lote_id: int) -> dict:
    """Envía los intentos programados del lote por su canal y guarda estado, costo y referencia."""
    canales = {}
    resumen = defaultdict(int)
    with sesion() as s:
        lote = s.get(Lote, lote_id)
        if not lote:
            return {"error": "lote inexistente"}
        empresa_id = lote.empresa_id
        icp = icp_de(empresa_id)
        intentos = s.exec(select(Intento).where(Intento.lote_id == lote_id, Intento.estado == "programado")).all()
        for it in intentos:
            l = s.get(Lead, it.lead_id)
            if it.canal not in canales:
                canales[it.canal] = canal_de(it.canal, empresa_id=empresa_id)
            c = canales[it.canal]
            if it.canal == "correo" and not it.detalle.get("texto"):
                from .mensajes import idioma_de
                texto, info = agente.redactar_mensaje(l, "correo", icp, idioma=idioma_de(l, empresa_id))
                it.detalle = {**(it.detalle or {}), "texto": texto, "redaccion": info}
            r = c.enviar(l, it)
            it.estado = r.estado
            it.costo_usd = r.costo_usd + float((it.detalle or {}).get("redaccion", {}).get("costo_usd", 0.0))
            it.ref_externa = r.ref_externa
            it.proveedor = r.proveedor
            it.mensaje = r.mensaje
            it.detalle = {**(it.detalle or {}), **r.detalle}
            it.enviado_en = datetime.utcnow() if r.estado != "fallido" else None
            s.add(it)
            resumen[f"{it.canal}:{r.estado}:{r.proveedor}"] += 1
        s.commit()
        fuera, motivo, usuario = lote.fuera_ventana, lote.override_motivo, lote.override_usuario
    if fuera and resumen.get("voz:programado:dapta", 0) > 0 and config_de(empresa_id).get("respetar_ley_2300", True):
        # El override del usuario también abre el horario de la secuencia de Dapta (dos horas); sincronizar lo restaura.
        # (Con el horario legal desactivado en la configuración, la secuencia ya está sin límite y no hace falta.)
        try:
            r = canales["voz"].abrir_ventana_hoy()
            hasta = (datetime.utcnow() + timedelta(hours=2)).isoformat()
            anotar("override_dapta", f"Override del lote {lote_id}: la secuencia de Dapta puede llamar hoy fuera del horario de la Ley 2300; se restaura en dos horas",
                   empresa_id, lote_id=lote_id, hasta=hasta, usuario=usuario, motivo=motivo, dapta_verified=r.get("verified") if isinstance(r, dict) else None)
        except Exception as e:  # noqa: BLE001
            anotar("error", f"no se pudo abrir el horario de la secuencia de Dapta: {e}"[:300], empresa_id, lote_id=lote_id)
    notificar(empresa_id, "lote", f"Lote {lote_id} enviado: " + ", ".join(f"{k} {v}" for k, v in resumen.items()))
    return {"lote_id": lote_id, "resultado": dict(resumen)}


def aplicar_horario_dapta(empresa_id: int, respetar: bool, usuario: str = "") -> dict:
    """Al cambiar respetar_ley_2300 en la configuración: horario legal o sin límite en la secuencia de Dapta, y constancia en la bitácora."""
    voz = canal_de("voz", empresa_id=empresa_id)
    r: dict = {}
    if voz.real:
        try:
            r = voz.aplicar_horario(respetar)
        except Exception as e:  # noqa: BLE001
            r = {"error": str(e)[:200]}
    texto = ("Horario de la Ley 2300 activado" if respetar
             else "Horario de la Ley 2300 DESACTIVADO: la empresa asume la responsabilidad de contactar fuera del horario legal")
    anotar("ley_2300", f"{texto} por {usuario or 'sistema'}", empresa_id, usuario=usuario, respetar=respetar, dapta=r.get("verified") if isinstance(r, dict) else None)
    return {"respetar_ley_2300": respetar, "dapta": r}


def _dict_json(valor) -> dict:
    """Un objeto, o un texto JSON con un objeto, a dict; cualquier otra cosa, dict vacío."""
    if isinstance(valor, dict):
        return valor
    if isinstance(valor, str) and valor.strip().startswith("{"):
        try:
            import json
            v = json.loads(valor)
            return v if isinstance(v, dict) else {}
        except ValueError:
            return {}
    return {}


def restaurar_ventana_dapta_si_vencio(voz, empresa_id: int = 1) -> bool:
    """Si un override abrió el horario de la secuencia de Dapta y ya pasaron las dos horas, vuelve el horario de la Ley 2300."""
    with sesion() as s:
        ultimo = s.exec(select(Bitacora).where(Bitacora.empresa_id == empresa_id, Bitacora.tipo == "override_dapta").order_by(Bitacora.id.desc())).first()
        if not ultimo:
            return False
        ultimo_id, hasta = ultimo.id, (ultimo.datos or {}).get("hasta", "")
        cierre = s.exec(select(Bitacora).where(Bitacora.empresa_id == empresa_id, Bitacora.tipo == "override_dapta_cierre", Bitacora.id > ultimo_id)).first()
    if cierre or not hasta or datetime.utcnow().isoformat() < hasta:
        return False
    try:
        voz.aplicar_horario(config_de(empresa_id).get("respetar_ley_2300", True))
        anotar("override_dapta_cierre", "Horario de la Ley 2300 restaurado en la secuencia de Dapta", empresa_id, override_id=ultimo_id)
        return True
    except Exception as e:  # noqa: BLE001
        anotar("error", f"no se pudo restaurar el horario de la secuencia de Dapta: {e}"[:300], empresa_id)
        return False


def registrar_respuesta_token(token: str, valor: str) -> dict:
    """Clic en el correo: si | no | baja."""
    with sesion() as s:
        it = s.exec(select(Intento).where(Intento.canal == "correo")).all()
        it = next((x for x in it if (x.detalle or {}).get("token") == token), None)
        if not it:
            return {"error": "token desconocido"}
        l = s.get(Lead, it.lead_id)
        it.respondido_en = datetime.utcnow()
        if valor == "si":
            it.estado, it.clasificacion = "respondio", "interesado"
            l.estado = "respondio"
        elif valor == "no":
            it.estado, it.clasificacion = "respondio", "no_interesado"
            l.estado = "respondio"
        else:
            it.estado, it.clasificacion = "baja", "baja"
            l.estado = "baja"
            registrar_exclusion(l.correo or "", "baja", l.empresa_id)
            if l.telefono:
                registrar_exclusion(l.telefono, "baja", l.empresa_id)
        s.add(it)
        s.add(l)
        s.commit()
        empresa_id, nombre, lead_id = l.empresa_id, l.razon_social, l.id
    tipo = "baja" if valor == "baja" else "respondio"
    notificar(empresa_id, tipo, f"{nombre.title()} respondió al correo: {'me interesa' if valor == 'si' else ('no, gracias' if valor == 'no' else 'pide baja')}", lead_id)
    return {"lead_id": lead_id, "empresa": nombre, "valor": valor}


def registrar_respuesta_texto(lead_id: int, texto: str, canal: str = "whatsapp") -> dict:
    """Respuesta libre (WhatsApp o transcripción): la clasifica el agente (Jev o palabras clave)."""
    clase, info = agente.clasificar_respuesta(texto)
    with sesion() as s:
        l = s.get(Lead, lead_id)
        if not l:
            return {"error": "lead inexistente"}
        it = s.exec(select(Intento).where(Intento.lead_id == lead_id, Intento.canal == canal).order_by(Intento.id.desc())).first()
        if not it:
            it = Intento(empresa_id=l.empresa_id, lead_id=lead_id, canal=canal, estado="enviado", proveedor="manual")
        it.respuesta = texto
        it.clasificacion = clase
        it.respondido_en = datetime.utcnow()
        it.estado = "baja" if clase == "baja" else "respondio"
        it.detalle = {**(it.detalle or {}), "clasificacion": info}
        if clase == "baja":
            l.estado = "baja"
            registrar_exclusion(l.telefono or "", "baja", l.empresa_id)
            registrar_exclusion(l.correo or "", "baja", l.empresa_id)
        else:
            l.estado = "respondio"
        s.add(it)
        s.add(l)
        s.commit()
        empresa_id, nombre = l.empresa_id, l.razon_social
    notificar(empresa_id, "baja" if clase == "baja" else "respondio", f"{nombre.title()} respondió por {canal}: {clase}", lead_id)
    return {"lead_id": lead_id, "clasificacion": clase, "motor": info.get("motor")}


def registrar_evento_correo(ref_externa: str, tipo: str) -> bool:
    """Eventos de Resend o SES: entregado, abierto, clic, rebote, queja."""
    mapa = {"email.delivered": "entregado", "email.opened": "abierto", "email.clicked": "abierto", "email.bounced": "fallido", "email.complained": "baja"}
    nuevo = mapa.get(tipo)
    if not nuevo:
        return False
    with sesion() as s:
        it = s.exec(select(Intento).where(Intento.ref_externa == ref_externa)).first()
        if not it:
            return False
        orden = ["programado", "enviado", "entregado", "abierto", "respondio"]
        if it.estado in ("respondio", "baja"):
            return True
        if nuevo == "baja":
            it.estado = "baja"
            l = s.get(Lead, it.lead_id)
            registrar_exclusion(l.correo or "", "baja", l.empresa_id)
        elif nuevo == "fallido" or orden.index(nuevo) > orden.index(it.estado if it.estado in orden else "programado"):
            it.estado = nuevo
        s.add(it)
        s.commit()
        return True


def pasar_a_dapta_los_que_respondieron(empresa_id: int = 1) -> dict:
    """Los que respondieron por correo o WhatsApp entran al calificador de Dapta (la secuencia del agente)."""
    voz = canal_de("voz", empresa_id=empresa_id)
    enviados, omitidos = 0, 0
    with sesion() as s:
        leads = s.exec(select(Lead).where(Lead.empresa_id == empresa_id, Lead.estado == "respondio", Lead.telefono.is_not(None))).all()
        for l in leads:
            ya = s.exec(select(Calificacion).where(Calificacion.lead_id == l.id)).first()
            if ya or esta_excluido(l.telefono, empresa_id=empresa_id):
                omitidos += 1
                continue
            it = Intento(empresa_id=empresa_id, lead_id=l.id, canal="voz", estado="programado", detalle={"motivo": "calificacion"})
            s.add(it)
            s.commit()
            s.refresh(it)
            r = voz.enviar(l, it)
            it.estado, it.costo_usd, it.ref_externa, it.proveedor, it.mensaje = r.estado, r.costo_usd, r.ref_externa, r.proveedor, r.mensaje
            it.detalle = {**it.detalle, **r.detalle}
            it.enviado_en = datetime.utcnow()
            s.add(it)
            if r.estado == "omitido":      # modo prueba: no entra al calificador
                s.commit()
                omitidos += 1
                continue
            s.add(Calificacion(empresa_id=empresa_id, lead_id=l.id, intento_id=it.id, resultado="pendiente", ref_externa=r.ref_externa, datos={"via": r.proveedor}))
            s.commit()
            enviados += 1
    return {"enviados_a_dapta": enviados, "omitidos": omitidos, "modo": "real" if voz.real else "simulado"}


def sincronizar_dapta(limite: int = 200, empresa_id: int = 1) -> dict:
    """Lee las llamadas del agente de Dapta y actualiza intentos (estado, duración, costo real) y calificaciones."""
    from .channels.voz_dapta import CanalVozDapta
    voz = CanalVozDapta(empresa_id=empresa_id)
    if not voz.real:
        return {"error": "Dapta no configurado (clave, agente o secuencia)."}
    restaurar_ventana_dapta_si_vencio(voz, empresa_id)
    agente_id = voz.ids["agent_id"]
    from .channels.voz_dapta import duracion_seg, inicio_llamada
    llamadas = voz.mcp.llamadas(agente_id, limit=limite)
    filas = [c for c in (llamadas.get("calls") or []) if isinstance(c, dict)] if isinstance(llamadas, dict) else []
    # De la más antigua a la más reciente: si un contacto tuvo dos intentos (ocupado y luego contestó), queda el último.
    filas.sort(key=lambda c: inicio_llamada(c) or datetime.min)
    actualizados, nuevas_cali = 0, 0
    avisos = []
    with sesion() as s:
        for c in filas:
            tel = c.get("to_number") or c.get("phone") or c.get("contact_phone") or ""
            call_id = c.get("call_id") or c.get("id") or ""
            if not tel:
                continue
            inicio = inicio_llamada(c)
            # El intento de esa llamada: el que ya tiene su call_id, o el último programado antes de que empezara (en modo prueba, varios leads comparten el número).
            candidatos = s.exec(select(Intento).where(Intento.empresa_id == empresa_id, Intento.canal == "voz", Intento.ref_externa == tel).order_by(Intento.id.desc())).all()
            it = next((x for x in candidatos if call_id and call_id in (x.detalle or {}).get("llamadas", [])), None) \
                or next((x for x in candidatos if x.proveedor == "dapta" and (not inicio or not x.enviado_en or x.enviado_en <= inicio)), None)
            if not it:
                l = s.exec(select(Lead).where(Lead.empresa_id == empresa_id, Lead.telefono == tel)).first()
                if not l:
                    continue
                it = Intento(empresa_id=empresa_id, lead_id=l.id, canal="voz", estado="programado", ref_externa=tel, proveedor="dapta")
                s.add(it)
                s.commit()
                s.refresh(it)
            razon = (c.get("disconnect_reason") or c.get("disconnection_reason") or "").lower()
            dur = duracion_seg(c)
            if "voicemail" in razon or c.get("in_voicemail") is True:
                it.estado = "buzon"
            elif dur > 0 or "user_hangup" in razon or "agent_hangup" in razon:
                it.estado = "contestado"
            else:
                it.estado = "no_contesta"
            an_crudo = _dict_json(c.get("call_analysis"))          # list_calls lo manda como texto JSON; get_call como objeto
            an = dict(_dict_json(an_crudo.get("custom_analysis_data")) or _dict_json(c.get("custom_analysis_data")))
            for k in ("call_summary", "user_sentiment", "in_voicemail"):
                if an_crudo.get(k) is not None:
                    an[k] = an_crudo[k]
            resumen = an.get("call_summary") or c.get("call_summary") or c.get("summary") or ""
            llamadas_previas = [x for x in (it.detalle or {}).get("llamadas", []) if x != call_id]
            it.duracion_seg = dur
            it.costo_usd = round(sum(float((it.detalle or {}).get("costos", {}).get(x, 0.0)) for x in llamadas_previas) + voz.costo_llamada(c), 4)
            it.detalle = {**(it.detalle or {}), "call_id": call_id, "razon": razon, "resumen": resumen, "llamadas": llamadas_previas + [call_id],
                          "costos": {**(it.detalle or {}).get("costos", {}), call_id: voz.costo_llamada(c)}, "desde": c.get("from_number")}
            it.enviado_en = it.enviado_en or datetime.utcnow()
            exito = c.get("call_successful")
            if exito is None and an_crudo.get("call_successful") is not None:
                exito = an_crudo.get("call_successful")
            l = s.get(Lead, it.lead_id)
            if isinstance(an, dict) and an:
                if str(an.get("interesado", "")).lower() in ("true", "si", "sí", "yes"):
                    it.clasificacion = "interesado"
                if str(an.get("baja", "")).lower() in ("true", "si", "sí", "yes"):
                    it.clasificacion = "baja"
                    l.estado = "baja"
                    registrar_exclusion(l.telefono or "", "baja", empresa_id)
            if it.estado == "contestado":
                if l.estado in ("contactado", "listo"):
                    l.estado = "respondio"
                    avisos.append(("respondio", f"{l.razon_social.title()} contestó la llamada de Dapta", l.id))
                cali = s.exec(select(Calificacion).where(Calificacion.lead_id == it.lead_id)).first()
                if exito is not None:
                    res = "calificado" if exito else "no_calificado"
                    if not cali:
                        cali = Calificacion(empresa_id=empresa_id, lead_id=it.lead_id, intento_id=it.id, ref_externa=it.detalle.get("call_id"))
                        nuevas_cali += 1
                    if cali.resultado != res:
                        avisos.append(("calificado" if exito else "no_calificado", f"Dapta {'calificó' if exito else 'no calificó'} a {l.razon_social.title()}", l.id))
                    cali.resultado = res
                    cali.datos = an if isinstance(an, dict) else {"analisis": an}
                    s.add(cali)
                    l.estado = res
            s.add(l)
            s.add(it)
            actualizados += 1
        s.commit()
    for tipo, msg, lid in avisos:
        notificar(empresa_id, tipo, msg, lid)
    return {"llamadas_leidas": len(filas), "intentos_actualizados": actualizados, "calificaciones_nuevas": nuevas_cali}


def simular_resultados(semilla: int = 7, empresa_id: int = 1) -> dict:
    """Solo para demos sin credenciales: inventa respuestas y calificaciones plausibles sobre los intentos simulados."""
    import random
    rnd = random.Random(semilla)
    tasas = {"correo": (0.08, 0.35), "voz": (0.30, 0.45), "whatsapp": (0.15, 0.40)}   # (responde, califica si respondió)
    n_resp, n_cali = 0, 0
    with sesion() as s:
        intentos = s.exec(select(Intento).where(Intento.empresa_id == empresa_id, Intento.proveedor == "simulado", Intento.estado.in_(["enviado", "programado"]))).all()
        for it in intentos:
            pr, pc = tasas.get(it.canal, (0.1, 0.3))
            l = s.get(Lead, it.lead_id)
            if it.canal == "voz":
                contesto = rnd.random() < 0.55
                it.estado = "contestado" if contesto else ("buzon" if rnd.random() < 0.3 else "no_contesta")
                it.duracion_seg = rnd.randint(40, 240) if contesto else 0
                it.costo_usd = (-(-it.duracion_seg // 60)) * config.tarifas.voz_minuto_contestado if contesto else (config.tarifas.voz_buzon if it.estado == "buzon" else config.tarifas.voz_no_contesta)
                responde = contesto and rnd.random() < (pr / 0.55)
            else:
                responde = rnd.random() < pr
            if responde:
                it.estado = "respondio" if it.canal != "voz" else it.estado
                it.clasificacion = "interesado" if rnd.random() < 0.6 else "no_interesado"
                it.respondido_en = datetime.utcnow()
                l.estado = "respondio"
                n_resp += 1
                if rnd.random() < pc:
                    s.add(Calificacion(empresa_id=empresa_id, lead_id=l.id, intento_id=it.id, resultado="calificado", costo_usd=0.0 if it.canal == "voz" else 2 * config.tarifas.voz_minuto_contestado, datos={"simulado": True}))
                    l.estado = "calificado"
                    n_cali += 1
                elif it.clasificacion == "interesado":
                    s.add(Calificacion(empresa_id=empresa_id, lead_id=l.id, intento_id=it.id, resultado="no_calificado", costo_usd=0.0 if it.canal == "voz" else 2 * config.tarifas.voz_minuto_contestado, datos={"simulado": True}))
                    l.estado = "no_calificado"
            s.add(it)
            s.add(l)
        s.commit()
    return {"simulados": len(intentos), "respondieron": n_resp, "calificados": n_cali}
