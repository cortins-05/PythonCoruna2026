/*
  Sección "Asistente": bienvenida, conversación con streaming y ejecución de las acciones de los bloques (CONTRATO-CORE, apartados 4 y 4.2).
  El pintado de cada bloque lo hace asistente-bloques.js. Aquí viven el estado de la conversación, el SSE y `ejecutar`.
  El stream es el único sitio donde se usa fetch directo, porque ctx.api espera un JSON completo y no puede leer un ReadableStream.
*/
import { renderBloque } from "./asistente-bloques.js";

const CLAVE_SESION = "asistente.conversacion";
const ACTOR = "Flor";
const MAX_HISTORIAL = 8;

/* Estado que sobrevive al cambio de sección (el módulo se queda cargado) */
let conversacion = [];
let qConsumida = null;

function leerSesion() {
  try {
    const crudo = sessionStorage.getItem(CLAVE_SESION);
    const datos = crudo ? JSON.parse(crudo) : [];
    return Array.isArray(datos) ? datos : [];
  } catch { return []; }
}

function guardarSesion() {
  try { sessionStorage.setItem(CLAVE_SESION, JSON.stringify(conversacion)); } catch { /* sin almacenamiento o cuota llena */ }
}

const reducirMovimiento = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

/* ------------------------------------------------------------------ SSE */

/** Divide el buffer en eventos completos (separados por línea en blanco) y devuelve lo que sobra para el siguiente fragmento. */
export function extraerEventos(buffer) {
  const limpio = buffer.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const trozos = limpio.split("\n\n");
  const resto = trozos.pop();
  const eventos = [];
  for (const trozo of trozos) {
    let nombre = "message";
    const datos = [];
    for (const linea of trozo.split("\n")) {
      if (!linea || linea.startsWith(":")) continue;
      const i = linea.indexOf(":");
      const campo = i === -1 ? linea : linea.slice(0, i);
      const valor = i === -1 ? "" : linea.slice(i + 1).replace(/^ /, "");
      if (campo === "event") nombre = valor;
      else if (campo === "data") datos.push(valor);
    }
    if (!datos.length) continue;
    try { eventos.push({ nombre, datos: JSON.parse(datos.join("\n")) }); } catch { /* evento mal formado: se ignora */ }
  }
  return { eventos, resto };
}

async function leerStream(cuerpo, senal, alEvento) {
  const respuesta = await fetch("/api/chat/stream", {
    method: "POST", headers: { "content-type": "application/json", accept: "text/event-stream" }, body: JSON.stringify(cuerpo), signal: senal,
  });
  if (!respuesta.ok || !respuesta.body) throw new Error(`El stream respondió ${respuesta.status}`);
  const lector = respuesta.body.getReader();
  const decodificador = new TextDecoder("utf-8");
  let buffer = "";
  for (;;) {
    const { done, value } = await lector.read();
    buffer += decodificador.decode(value ?? new Uint8Array(), { stream: !done });
    const { eventos, resto } = extraerEventos(done ? `${buffer}\n\n` : buffer);
    buffer = done ? "" : resto;
    eventos.forEach(alEvento);
    if (done) break;
  }
}

/* ------------------------------------------------------------------ sección */

export default {
  id: "asistente",
  async montar(contenedor, ctx) {
    const { el, ui } = ctx;
    if (!conversacion.length) conversacion = leerSesion();

    let controlador = null; // AbortController del stream en curso
    let ocupado = false;
    let seguirAlFinal = true;
    let destruido = false;
    let sugerencias = null;

    /* ---------- piezas fijas del DOM */
    const raiz = el("div", { class: "sec-asistente" });
    const log = el("div", { class: "asi__log", role: "log", aria: { live: "polite", label: "Conversación con el asistente", relevant: "additions" } });
    const bienvenida = el("div", { class: "asi__bienvenida" });
    const irAlFinal = ui.boton({ texto: "Ir al final", icono: "arrow-down", variante: "oscuro", tam: "sm", clase: "asi__ir-final", onclick: () => bajar(true) });
    irAlFinal.hidden = true;

    const entrada = el("textarea", {
      class: "asi__entrada", rows: 1, placeholder: "Pregunta algo o pide una acción", maxlength: 2000,
      aria: { label: "Mensaje para el asistente" },
    });
    const botonEnviar = ui.boton({ icono: "send", variante: "oscuro", etiqueta: "Enviar mensaje", clase: "asi__enviar", onclick: () => enviarDesdeCaja() });
    const botonDetener = ui.boton({ texto: "Detener", icono: "x", variante: "secundario", clase: "asi__detener", onclick: () => detener() });
    botonDetener.hidden = true;
    const caja = el("div", { class: "asi__caja" }, irAlFinal, el("div", { class: "asi__caja-interior" }, entrada, botonDetener, botonEnviar));

    /* ---------- menciones: escribir @ y el número de una habitación */
    const TIPOS_HAB = { "SGL-STD": "Individual", "DBL-STD": "Doble", "TPL-STD": "Triple", "FAM-STD": "Familiar", "SUI-STD": "Suite" };
    const menuMenciones = el("div", { class: "asi__menciones", role: "listbox", aria: { label: "Habitaciones" } });
    menuMenciones.hidden = true;
    caja.append(menuMenciones);
    let habitacionesMencion = null;
    let opcionesMencion = [];
    let activaMencion = 0;
    function cerrarMenciones() { menuMenciones.hidden = true; opcionesMencion = []; }
    function pintarMenciones() {
      menuMenciones.hidden = false;
      menuMenciones.replaceChildren(...opcionesMencion.map((h, i) => el("button", {
        type: "button", role: "option", class: `asi__mencion${i === activaMencion ? " is-activa" : ""}`,
        onmousedown: (ev) => { ev.preventDefault(); insertarMencion(h); },
      }, el("b", null, `@${h.numero}`), el("span", null, `${TIPOS_HAB[h.tipo] ?? h.tipo} · ${h.noche ? h.noche.nombre : "libre"}`))));
    }
    function insertarMencion(h) {
      const pos = entrada.selectionStart;
      const antes = entrada.value.slice(0, pos).replace(/@\d*$/, `@${h.numero} `);
      entrada.value = antes + entrada.value.slice(pos);
      entrada.setSelectionRange(antes.length, antes.length);
      cerrarMenciones();
      entrada.focus();
    }
    entrada.addEventListener("input", async () => {
      const m = entrada.value.slice(0, entrada.selectionStart).match(/@(\d*)$/);
      if (!m) { cerrarMenciones(); return; }
      if (!habitacionesMencion) {
        try { habitacionesMencion = (await ctx.api("/api/habitaciones")).habitaciones; } catch { habitacionesMencion = []; }
      }
      opcionesMencion = habitacionesMencion.filter((h) => String(h.numero).startsWith(m[1])).slice(0, 8);
      activaMencion = 0;
      if (opcionesMencion.length) pintarMenciones(); else cerrarMenciones();
    });
    entrada.addEventListener("keydown", (e) => {
      if (menuMenciones.hidden) return;
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        activaMencion = (activaMencion + (e.key === "ArrowDown" ? 1 : -1) + opcionesMencion.length) % opcionesMencion.length;
        pintarMenciones();
      } else if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault(); e.stopImmediatePropagation();
        insertarMencion(opcionesMencion[activaMencion]);
      } else if (e.key === "Escape") { cerrarMenciones(); }
    }, true);

    /* ---------- scroll */
    const distanciaAlFinal = () => document.documentElement.scrollHeight - (window.scrollY + window.innerHeight);
    function bajar(forzar = false) {
      if (!forzar && !seguirAlFinal) return;
      seguirAlFinal = true;
      window.scrollTo({ top: document.documentElement.scrollHeight, behavior: forzar && !reducirMovimiento() ? "smooth" : "auto" });
      irAlFinal.hidden = true;
    }
    function alScroll() {
      const lejos = distanciaAlFinal() > 120;
      seguirAlFinal = !lejos;
      irAlFinal.hidden = !lejos || !conversacion.length;
    }
    window.addEventListener("scroll", alScroll, { passive: true });

    /* ---------- caja de texto */
    function ajustarAlto() {
      entrada.style.height = "auto";
      entrada.style.height = `${Math.min(entrada.scrollHeight, 200)}px`;
    }
    entrada.addEventListener("input", ajustarAlto);
    entrada.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); enviarDesdeCaja(); }
    });
    function enviarDesdeCaja() {
      const texto = entrada.value.trim();
      if (!texto || ocupado) return;
      entrada.value = "";
      ajustarAlto();
      enviar(texto);
    }
    function marcarOcupado(si) {
      ocupado = si;
      botonEnviar.disabled = si;
      botonDetener.hidden = !si;
      botonEnviar.hidden = si;
      raiz.classList.toggle("esta-ocupado", si);
    }
    function detener() { controlador?.abort(); }

    /* ---------- mensajes */
    function burbujaUsuario(texto) {
      return el("div", { class: "asi__usuario" }, el("p", { class: "asi__usuario-texto" }, texto));
    }

    /** Crea el contenedor de un mensaje del asistente y devuelve los métodos para ir añadiendo contenido en orden de llegada. */
    function mensajeAsistente(modelo) {
      const cuerpo = el("div", { class: "asi__contenido" });
      const nodo = el("div", { class: "asi__asistente" },
        el("span", { class: "asi__yo", aria: { hidden: "true" } }, ui.icono("sparkles", { tam: 18 })), cuerpo);
      const herramientas = new Map();
      let parrafo = null; // el párrafo de texto actual, para seguir escribiendo en él

      function pintarBloque(bloque) {
        parrafo = null;
        let nodoBloque;
        try {
          nodoBloque = renderBloque(bloque, { ejecutar, ui, el });
        } catch {
          nodoBloque = el("p", { class: "asi__bloque-error u-texto-2" }, "No se pudo mostrar este contenido.");
        }
        cuerpo.append(el("div", { class: "asi__bloque" }, nodoBloque));
      }
      function pintarTexto(delta) {
        if (!parrafo) { parrafo = el("p", { class: "asi__texto" }); cuerpo.append(parrafo); }
        parrafo.append(document.createTextNode(delta));
      }
      return {
        nodo, cuerpo,
        herramienta(ev) {
          let linea = herramientas.get(ev.id);
          if (!linea) {
            linea = el("div", { class: "asi__herramienta", aria: { hidden: "true" } });
            herramientas.set(ev.id, linea);
            parrafo = null;
            cuerpo.append(linea);
          }
          linea.replaceChildren(ui.icono(ev.estado === "fin" ? "check" : "loader", { tam: 14, clase: ev.estado === "fin" ? "" : "ui-girar" }), el("span", null, ev.etiqueta || ev.nombre || "Consultando"));
          linea.classList.toggle("is-hecha", ev.estado === "fin");
        },
        bloque: pintarBloque,
        texto: pintarTexto,
        tieneTexto: () => !!cuerpo.querySelector(".asi__texto"),
        /* Las líneas de progreso son efímeras: al cerrar el mensaje se quitan */
        cerrar(modo) {
          herramientas.forEach((l) => l.remove());
          nodo.removeAttribute("aria-busy");
          nodo.querySelector(".asi__pie")?.remove();
        },
        aviso(texto, tono = "aviso") {
          cuerpo.append(el("div", { class: "asi__aviso" }, ui.chip({ texto, tono, icono: "info" })));
        },
        iniciar() { nodo.setAttribute("aria-busy", "true"); },
        pintarModelo() {
          for (const p of modelo.partes) {
            if (p.tipo === "bloque") pintarBloque(p.bloque);
            else if (p.texto) { parrafo = null; pintarTexto(p.texto); parrafo = null; }
          }
          if (modelo.interrumpida) this.aviso("Respuesta interrumpida", "neutro");
        },
      };
    }
    const ultimoAsistente = () => [...conversacion].reverse().find((m) => m.rol === "asistente");

    function pintarConversacion() {
      log.replaceChildren();
      for (const m of conversacion) {
        if (m.rol === "usuario") log.append(burbujaUsuario(m.texto));
        else { const msg = mensajeAsistente(m); msg.pintarModelo(); log.append(msg.nodo); }
      }
    }

    /* ---------- vista vacía o con conversación */
    function actualizarVista() {
      const vacia = conversacion.length === 0;
      raiz.classList.toggle("es-vacio", vacia);
      if (vacia) bienvenida.append(caja); else raiz.append(caja);
      ajustarAlto();
      irAlFinal.hidden = true;
    }

    function historialParaEnviar() {
      return conversacion
        .filter((m) => (m.rol === "usuario" ? m.texto : textoDe(m)))
        .slice(-MAX_HISTORIAL)
        .map((m) => ({ role: m.rol === "usuario" ? "user" : "assistant", content: m.rol === "usuario" ? m.texto : textoDe(m) }));
    }
    const textoDe = (m) => m.partes.filter((p) => p.tipo === "texto").map((p) => p.texto).join("");

    /* ---------- envío */
    async function enviar(texto) {
      if (ocupado || destruido) return;
      const historial = historialParaEnviar();
      const primera = conversacion.length === 0;
      conversacion.push({ rol: "usuario", texto });
      const modelo = { rol: "asistente", partes: [], modo: null };
      conversacion.push(modelo);
      if (primera) actualizarVista();
      log.append(burbujaUsuario(texto));
      const msg = mensajeAsistente(modelo);
      msg.iniciar();
      log.append(msg.nodo);
      conversacion.forEach((m) => { if (m !== modelo && m.rol === "asistente") m.modo = null; });
      log.querySelectorAll(".asi__pie").forEach((p) => p.remove());
      seguirAlFinal = true;
      bajar(true);
      marcarOcupado(true);
      controlador = new AbortController();
      const cuerpoPeticion = { mensaje: texto, historial };
      let recibido = false;
      let cerrado = false;

      const anadirTexto = (delta) => {
        const ultima = modelo.partes[modelo.partes.length - 1];
        if (ultima?.tipo === "texto") ultima.texto += delta; else modelo.partes.push({ tipo: "texto", texto: delta });
        msg.texto(delta);
      };
      const anadirBloque = (bloque) => { modelo.partes.push({ tipo: "bloque", bloque }); msg.bloque(bloque); };
      const alEvento = ({ nombre, datos }) => {
        recibido = true;
        if (nombre === "herramienta") msg.herramienta(datos);
        else if (nombre === "bloque") anadirBloque(datos);
        else if (nombre === "texto") anadirTexto(datos.delta ?? "");
        else if (nombre === "fin") {
          if (!msg.tieneTexto() && datos.respuesta) anadirTexto(datos.respuesta);
          modelo.modo = datos.modo ?? null;
          cerrado = true;
        } else if (nombre === "error") {
          throw Object.assign(new Error(datos.mensaje || "No se pudo completar la respuesta"), { deEvento: true });
        }
        bajar();
      };

      try {
        try {
          await leerStream(cuerpoPeticion, controlador.signal, alEvento);
          if (!cerrado) throw new Error("El stream terminó sin cierre");
        } catch (e) {
          if (e.name === "AbortError") throw e;
          // Si ya se pintó algo, solo se avisa. Si no, se pide la respuesta de una vez a /api/chat
          if (e.deEvento && modelo.partes.length) { msg.aviso(e.message, "critico"); }
          else if (!modelo.partes.length) {
            const r = await ctx.api("/api/chat", "POST", cuerpoPeticion);
            msg.aviso("Respuesta recibida sin streaming", "neutro");
            (r.bloques ?? []).forEach(anadirBloque);
            if (r.respuesta) anadirTexto(r.respuesta);
            modelo.modo = r.modo ?? null;
            bajar();
          } else {
            msg.aviso("La respuesta se cortó antes de terminar", "aviso");
          }
        }
      } catch (e) {
        if (e.name === "AbortError") {
          modelo.interrumpida = true;
          msg.aviso("Respuesta interrumpida", "neutro");
        } else {
          msg.aviso(e.message || "No se pudo obtener respuesta", "critico");
        }
      } finally {
        msg.cerrar(modelo.modo);
        controlador = null;
        guardarSesion();
        if (!destruido) {
          marcarOcupado(false);
          entrada.focus({ preventScroll: true });
          bajar();
        }
      }
    }

    /* ---------- acciones de los bloques (apartado 4.2) */
    const resultado = (ok, mensaje, estado, detalle = null, tarjeta = null) => ({ ok, mensaje, estado, detalle, tarjeta });

    /** Añade un mensaje del asistente ya cerrado, con el resumen de lo que acaba de pasar y la siguiente pregunta dentro. */
    function mensajeResumen(texto, preguntas) {
      const modelo = { rol: "asistente", partes: [{ tipo: "texto", texto }, { tipo: "bloque", bloque: { tipo: "sugerencias", items: preguntas } }], modo: null };
      conversacion.push(modelo);
      const msg = mensajeAsistente(modelo);
      msg.pintarModelo();
      log.append(msg.nodo);
      guardarSesion();
      bajar(true);
    }
    const fallo = (e) => resultado(false, e?.message || "No se pudo completar la operación", "error", e?.detalle ?? null);

    function contenidoComunicacion(com) {
      const r = com.respuesta ?? {};
      return el("div", { class: "asi__confirmar" },
        ui.kv([
          { etiqueta: "Canal", valor: r.canal === "whatsapp" ? "WhatsApp" : r.canal === "correo" ? "Correo" : (r.canal ?? com.canal ?? "") },
          { etiqueta: "Destinatario", valor: r.destinatario ?? com.de?.contacto ?? "" },
        ], { columnas: 2 }),
        r.asunto && ui.kv([{ etiqueta: "Asunto", valor: r.asunto }], { columnas: 1 }),
        el("div", { class: "asi__confirmar-texto", tabindex: 0, role: "group", aria: { label: "Texto que se enviará" } }, r.texto ?? ""),
        el("p", { class: "asi__confirmar-nota u-texto-2" }, "El envío es simulado: no sale ningún mensaje real."));
    }

    async function confirmarComunicacion(accion) {
      const com = await ctx.api(`/api/comunicaciones/${encodeURIComponent(accion.id)}`);
      const canal = com.respuesta?.canal ?? com.canal;
      const ok = await ctx.confirmar({
        titulo: "Confirmar y enviar la respuesta", texto: "Se va a enviar esto por el mismo canal por el que llegó la petición.",
        confirmar: canal === "whatsapp" ? "Sí, enviar por WhatsApp" : "Sí, enviar por correo", contenido: contenidoComunicacion(com),
      });
      if (!ok) return resultado(false, "No se ha enviado nada", "cancelado");
      const body = { actor: ACTOR };
      if (accion.texto) body.texto = accion.texto;
      const r = await ctx.api(`/api/comunicaciones/${encodeURIComponent(accion.id)}/confirmar`, "POST", body);
      const res = r?.resultado ?? {};
      const medio = res.canal ?? canal;
      const nombreCanal = medio === "whatsapp" ? "WhatsApp" : "correo";
      const dest = res.destinatario ?? com.respuesta?.destinatario ?? "";
      const extra = res.accion === "reservada" ? " y habitación reservada" : res.accion === "en_espera" ? " y petición en espera" : res.accion === "sin_hueco" ? " sin hueco disponible" : "";
      const siguiente = res.accion === "reservada" ? "¿Qué estancias tienen algo pendiente?" : "¿Qué peticiones hay por confirmar?";
      const que = res.accion === "reservada" ? "Respuesta enviada y habitación reservada" : res.accion === "en_espera" ? "Respuesta enviada, petición en espera" : res.accion === "sin_hueco" ? "Respuesta enviada, sin hueco disponible" : "Respuesta enviada";
      mensajeResumen(`He enviado la respuesta por ${nombreCanal} a ${dest}${extra}. El envío es simulado y no ha salido ningún mensaje real.`, [siguiente, "¿Cómo está la ocupación?"]);
      return resultado(true, `Enviado por ${nombreCanal} a ${dest} (simulado)${extra}`, res.accion ?? "respondida", r, {
        titulo: que, filas: [{ etiqueta: "Canal", valor: nombreCanal }, { etiqueta: "A", valor: dest }, { etiqueta: "Quién", valor: ACTOR }],
        acciones: [{ tipo: "abrir_seccion", etiqueta: "Ver comunicaciones", seccion: "comunicaciones" }],
      });
    }

    async function descartarComunicacion(accion) {
      const ok = await ctx.confirmar({ titulo: "Descartar la petición", texto: "La petición se marca como descartada y no se envía respuesta.", confirmar: "Sí, descartar", tono: "critico", contenido: el("span") });
      if (!ok) return resultado(false, "No se ha descartado nada", "cancelado");
      const r = await ctx.api(`/api/comunicaciones/${encodeURIComponent(accion.id)}/descartar`, "POST", { actor: ACTOR });
      mensajeResumen("He descartado la petición y no se ha enviado ninguna respuesta.", ["¿Qué peticiones hay por confirmar?", "¿Qué atender primero?"]);
      return resultado(true, "Petición descartada", "descartada", r, {
        titulo: "Petición descartada", tono: "neutro", simulado: false, filas: [{ etiqueta: "Respuesta", valor: "Ninguna" }, { etiqueta: "Quién", valor: ACTOR }],
        acciones: [{ tipo: "abrir_seccion", etiqueta: "Ver comunicaciones", seccion: "comunicaciones" }],
      });
    }

    async function aprobarPropuesta(accion) {
      const ok = await ctx.confirmar({ titulo: "Aprobar la propuesta", texto: "Se ejecuta la propuesta tal como está escrita. Los envíos y los cierres de RoomCloud son simulados.", confirmar: "Sí, aprobar", contenido: el("span") });
      if (!ok) return resultado(false, "No se ha aprobado nada", "cancelado");
      const r = await ctx.api(`/api/propuestas/${encodeURIComponent(accion.id)}/aprobar`, "POST", { actor: ACTOR });
      mensajeResumen("He aprobado la propuesta. El cierre en RoomCloud es simulado y no se ha escrito nada fuera de la aplicación.", ["¿Cómo está la ocupación?", "¿Qué propuestas hay pendientes de aprobar?"]);
      return resultado(true, "Propuesta aprobada (simulado)", "aprobada", r, {
        titulo: "Cierre aprobado", filas: [{ etiqueta: "Sistema", valor: "RoomCloud" }, { etiqueta: "Quién", valor: ACTOR }, { etiqueta: "Resultado", valor: "Venta cerrada en la simulación" }],
        acciones: [{ tipo: "abrir_seccion", etiqueta: "Ver la ocupación", seccion: "ocupacion" }],
      });
    }

    async function rechazarPropuesta(accion) {
      const ok = await ctx.confirmar({ titulo: "Rechazar la propuesta", texto: "La propuesta se marca como rechazada y no se ejecuta nada.", confirmar: "Sí, rechazar", tono: "critico", contenido: el("span") });
      if (!ok) return resultado(false, "No se ha rechazado nada", "cancelado");
      const r = await ctx.api(`/api/propuestas/${encodeURIComponent(accion.id)}/rechazar`, "POST", { actor: ACTOR });
      return resultado(true, "Propuesta rechazada", "rechazada", r);
    }

    async function enviarFormulario(accion, valores) {
      if (accion.formulario !== "walkin") return resultado(false, "Este formulario no se puede enviar desde el chat", "error");
      const v = valores ?? {};
      const cuerpo = {
        nombre: String(v.nombre ?? "").trim(), apellidos: String(v.apellidos ?? "").trim(), telefono: String(v.telefono ?? "").trim(),
        tipo: String(v.tipo ?? ""), checkin: String(v.checkin ?? ""), checkout: String(v.checkout ?? ""),
        personas: Number(v.personas) || 1, viaja_por_trabajo: v.viaja_por_trabajo === true || v.viaja_por_trabajo === "true" || v.viaja_por_trabajo === "Sí",
      };
      if (!cuerpo.nombre || !cuerpo.tipo || !cuerpo.checkin || !cuerpo.checkout) return resultado(false, "Faltan el nombre, el tipo de habitación o las fechas", "error");
      try {
        const r = await ctx.api("/api/walkin", "POST", cuerpo);
        return resultado(true, `Reserva física añadida (${r.id})`, "creada", r);
      } catch (e) {
        if (e.status !== 409 || !e.detalle?.conflicto) throw e;
        const lista = e.message;
        const forzar = await ctx.confirmar({
          titulo: "No queda habitación libre", texto: `${lista}. Si la añades, habrá overbooking.`, confirmar: "Sí, añadir con overbooking", tono: "critico", contenido: el("span"),
        });
        if (!forzar) return resultado(false, "No se ha añadido la reserva", "cancelado", e.detalle);
        const r = await ctx.api("/api/walkin", "POST", { ...cuerpo, forzar: true });
        return resultado(true, `Reserva física añadida con overbooking (${r.id})`, "creada_forzada", r);
      }
    }

    async function sincronizar(accion) {
      const fuente = accion.fuente === "ofihotel" ? "ofihotel" : "roomcloud";
      const r = await ctx.api(`/api/sync/${fuente}`, "POST");
      if (fuente === "roomcloud") return resultado(true, `RoomCloud leído: ${r?.nuevas ?? 0} reservas nuevas (simulado)`, "sincronizado", r);
      return resultado(true, "OfiHotel leído en solo lectura, con los datos de ayer", "sincronizado", r);
    }

    async function simularRoomcloud(accion) {
      const ok = await ctx.confirmar({ titulo: "Simular una reserva de Booking", texto: "Entra una reserva de prueba por RoomCloud y la aplicación recalcula la ocupación. Es simulado.", confirmar: "Sí, simular la reserva", contenido: el("span") });
      if (!ok) return resultado(false, "No se ha simulado nada", "cancelado");
      const r = await ctx.api("/api/demo/reserva-roomcloud", "POST", { tipo: accion.tipo || "SGL-STD" });
      return resultado(true, "Entró una reserva de Booking (simulado)", "simulada", r);
    }

    async function marcarOfihotel(accion) {
      const ok = await ctx.confirmar({ titulo: "Marcar como pasada a OfiHotel", texto: "Se anota que recepción ya ha dado de alta esta estancia en OfiHotel. Aquí no se escribe nada en OfiHotel.", confirmar: "Sí, marcar como pasada", contenido: el("span") });
      if (!ok) return resultado(false, "No se ha marcado nada", "cancelado");
      const r = await ctx.api(`/api/expedientes/${encodeURIComponent(accion.id)}/tramites/ofihotel_alta`, "POST", { actor: ACTOR, nota: "Marcado desde el asistente" });
      mensajeResumen("He marcado la estancia como pasada a OfiHotel. La lectura de mañana la confirmará.", ["¿Qué estancias tienen algo pendiente?", "¿Qué conflictos hay?"]);
      return resultado(true, "Estancia marcada como pasada a OfiHotel", "pasada", r, {
        titulo: "Estancia pasada a OfiHotel", simulado: false, filas: [{ etiqueta: "Quién", valor: ACTOR }, { etiqueta: "Confirmación", valor: "En la próxima lectura de OfiHotel" }],
        acciones: [{ tipo: "abrir_estancia", etiqueta: "Abrir la estancia", id: accion.id }],
      });
    }

    async function modificarEstancia(accion) {
      const ok = await ctx.confirmar({ titulo: "Cambiar las fechas", texto: `Las fechas de la estancia pasan a ser del ${accion.entrada} al ${accion.salida}.`, confirmar: "Sí, cambiar", contenido: el("span") });
      if (!ok) return resultado(false, "No se ha cambiado nada", "cancelado");
      const r = await ctx.api(`/api/expedientes/${encodeURIComponent(accion.id)}/fechas`, "PUT", { checkin: accion.entrada, checkout: accion.salida, actor: ACTOR });
      mensajeResumen("He cambiado las fechas de la estancia.", ["¿Qué conflictos hay?", "¿Cómo está la ocupación?"]);
      return resultado(true, "Fechas cambiadas", "cambiada", r, {
        titulo: "Fechas cambiadas", simulado: false, filas: [{ etiqueta: "Nuevas fechas", valor: `${accion.entrada} a ${accion.salida}` }, { etiqueta: "Quién", valor: ACTOR }],
        acciones: [{ tipo: "abrir_estancia", etiqueta: "Abrir la estancia", id: accion.id }],
      });
    }

    /** Ejecuta una acción de un bloque. Nunca lanza: los errores vuelven como ok:false con su mensaje. */
    async function ejecutar(accion, valores) {
      try {
        switch (accion?.tipo) {
          case "preguntar":
            if (!accion.texto) return resultado(false, "La acción no trae ninguna pregunta", "error");
            if (ocupado) return resultado(false, "Espera a que termine la respuesta actual", "ocupado");
            enviar(String(accion.texto));
            return resultado(true, "Pregunta enviada", "enviada");
          case "abrir_seccion": ctx.navegar(accion.seccion, accion.params ?? {}); return resultado(true, "Abriendo la pantalla", "abierta");
          case "abrir_estancia": ctx.navegar("estancias", { id: accion.id }); return resultado(true, "Abriendo la estancia", "abierta");
          case "abrir_comunicacion": ctx.navegar("comunicaciones", { id: accion.id }); return resultado(true, "Abriendo la comunicación", "abierta");
          case "confirmar_comunicacion": return await confirmarComunicacion(accion);
          case "descartar_comunicacion": return await descartarComunicacion(accion);
          case "aprobar_propuesta": return await aprobarPropuesta(accion);
          case "rechazar_propuesta": return await rechazarPropuesta(accion);
          case "enviar_formulario": return await enviarFormulario(accion, valores);
          case "sincronizar": return await sincronizar(accion);
          case "simular_roomcloud": return await simularRoomcloud(accion);
          case "marcar_ofihotel": return await marcarOfihotel(accion);
          case "modificar_estancia": return await modificarEstancia(accion);
          default: return resultado(false, "Esta acción no se puede ejecutar desde el chat", "error");
        }
      } catch (e) {
        return fallo(e);
      }
    }

    /* ---------- bienvenida */
    function pintarBienvenida(datos) {
      const dos = (datos?.categorias ?? []).slice(0, 2).map((c) => (c.preguntas ?? [])[0]).filter(Boolean);
      return dos.map((p) => el("button", { type: "button", class: "asi__pregunta", onclick: () => enviar(p) }, p));
    }

    const zonaSugerencias = el("div", { class: "asi__sugerencias" }, ui.esqueleto({ lineas: 3, alto: 16 }));
    async function cargarSugerencias() {
      zonaSugerencias.replaceChildren(ui.esqueleto({ lineas: 3, alto: 16 }));
      try {
        sugerencias = await ctx.api("/api/chat/sugerencias");
        if (destruido) return;
        zonaSugerencias.replaceChildren(...pintarBienvenida(sugerencias));
      } catch (e) {
        if (destruido) return;
        zonaSugerencias.replaceChildren(ui.vacio({
          icono: "alert", titulo: "No se pudieron cargar las sugerencias", texto: e.message,
          accion: { texto: "Reintentar", icono: "refresh", onclick: cargarSugerencias },
        }));
      }
    }

    bienvenida.append(
      el("div", { class: "asi__saludo" },
        el("h2", null, "Hola, Flor")),
      zonaSugerencias);
    const panelBienvenida = ui.panel({ variante: "punteada", clase: "asi__panel-bienvenida", hijos: [bienvenida] });
    raiz.append(panelBienvenida, log);

    /* ---------- barra y arranque */
    function nuevaConversacion() {
      controlador?.abort();
      conversacion = [];
      guardarSesion();
      log.replaceChildren();
      actualizarVista();
      marcarOcupado(false);
      window.scrollTo({ top: 0 });
      entrada.focus({ preventScroll: true });
    }
    ctx.barra({
      titulo: "Asistente", subtitulo: "Habla con la información del hotel",
      acciones: [{ icono: "plus", texto: "Nueva conversación", onclick: nuevaConversacion }],
    });

    const app = contenedor.closest(".app");
    app?.classList.add("es-asistente");
    contenedor.append(raiz);
    pintarConversacion();
    actualizarVista();
    cargarSugerencias();
    if (conversacion.length) bajar(true);

    const q = (ctx.params?.q ?? "").trim();
    if (q && q !== qConsumida) { qConsumida = q; enviar(q); }
    else if (!conversacion.length) entrada.focus({ preventScroll: true });

    return {
      destruir() {
        destruido = true;
        app?.classList.remove("es-asistente");
        window.removeEventListener("scroll", alScroll);
        const habiaStream = !!controlador;
        controlador?.abort();
        if (habiaStream) guardarSesion();
      },
    };
  },
};
