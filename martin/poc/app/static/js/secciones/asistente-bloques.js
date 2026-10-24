/*
  Pintado de los bloques del chat. Interfaz fija: renderBloque(bloque, { ejecutar, ui, el }) devuelve un HTMLElement.
  ejecutar(accion, valores) devuelve una promesa de { ok, mensaje, estado, detalle } y es lo único que dispara acciones.
  Todo el texto entra como nodo de texto (nada de innerHTML). Un tipo desconocido o un bloque roto se pinta como aviso y nunca rompe el chat.

  Los bloques son compactos: filas simples, sin etiquetas de colores salvo una excepción real (conflicto, no disponible, alerta).
  Campos que usa cada bloque (formas de design/CONTRATO-CORE.md 4.1 y CONTRATO.md 5):
  - resumen_kpi: titulo, items[{etiqueta, valor, tono}]
  - tarjeta_reserva: titulo, subtitulo, semaforo{color,motivo}, acciones
  - lista_estancias: titulo, estancias[{id, huesped, checkin, checkout, tipo, semaforo}]
  - comunicacion: comunicacion{id, canal, hora, de, contraste{veredicto,motivo}, respuesta{canal,destinatario,asunto,texto}, alerta{hora,texto}, estado, resultado}, acciones
  - lista_comunicaciones: titulo, comunicaciones[] (una fila con acción abrir_comunicacion)
  - fuentes: titulo, fuentes[{id,nivel,nombre,estado,ultima}], acciones (sincronizar)
  - prioridades: titulo, prioridades{niveles,reglas}, resaltar
  - cola: titulo, items[{id,color,titulo,detalle,ruta,params}]
  - conflictos: titulo, conflictos[{id,nivel,texto,expediente_id}]
  - navegacion: titulo, items[{seccion,titulo,params,insignia}]
  - proceso: id, titulo, pasos[{id,titulo,detalle}], acciones
  - tabla_ocupacion: titulo, fechas[], filas[{tipo,celdas[{fecha,libres,cerrado}]}]
  - propuesta: id, texto, destino, destinatario, estado, acciones
  - formulario (walkin): id, titulo, campos[{nombre,etiqueta,tipo,opciones,valor,obligatorio}], envio{tipo,etiqueta,formulario}
  - aviso: tono, titulo, texto. sugerencias: items[string]
*/
import { escalera, NOMBRE_FUENTE, NOMBRE_SISTEMA } from "../ui-hotel.js";
import { fechaCorta, icono as iconoUi } from "../ui.js";

const TIPOS_ACCION = new Set(["preguntar", "abrir_seccion", "abrir_estancia", "abrir_comunicacion", "confirmar_comunicacion", "descartar_comunicacion",
  "aprobar_propuesta", "rechazar_propuesta", "enviar_formulario", "sincronizar", "simular_roomcloud", "marcar_ofihotel"]);
const NOMBRE_CANAL = { correo: "correo", whatsapp: "WhatsApp" };
const VEREDICTO = { disponible: ["ok", "Disponible"], ajustado: ["aviso", "Disponible sin margen"], en_competencia: ["aviso", "En competencia"], no_disponible: ["critico", "No disponible"], sin_datos: ["neutro", "Sin datos"] };
const TONOS = new Set(["neutro", "ok", "aviso", "critico", "info"]);
const tono = (t) => (TONOS.has(t) ? t : "neutro");
const reducido = () => typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;

/* ------------------------------------------------------------------ utilidades */

/** replaceChildren que ignora null, undefined y false (el nativo los pinta como texto). */
function llenar(nodo, ...hijos) {
  nodo.replaceChildren(...hijos.flat(Infinity).filter((h) => h != null && h !== false));
}

const MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

/** Pule datos técnicos que llegan en bruto: fechas ISO ("24 oct") y horas con decimales ("24 h"). */
function limpiar(texto) {
  return String(texto ?? "")
    .replace(/\b(\d{4})-(\d{2})-(\d{2})\b/g, (_, a, m, d) => `${Number(d)} ${MESES_CORTOS[Number(m) - 1] ?? m}`)
    .replace(/\b(\d+)\.0 h\b/g, "$1 h");
}

/** 34600111222 pasa a +34 600 111 222; cualquier otro destinatario queda tal cual. */
function telefono(valor) {
  const t = String(valor ?? "");
  const m = /^\+?(34)(\d{3})(\d{3})(\d{3})$/.exec(t);
  return m ? `+${m[1]} ${m[2]} ${m[3]} ${m[4]}` : t;
}

/** Frase de resultado de una comunicación ya tramitada. */
function frase(c) {
  const r = c.resultado;
  if (c.estado === "descartada") return "Descartada";
  const via = r ? `Enviado por ${NOMBRE_CANAL[r.canal] ?? r.canal}${r.destinatario ? ` a ${telefono(r.destinatario)}` : ""}` : `Respondida por ${NOMBRE_CANAL[c.canal] ?? c.canal}`;
  const base = r?.accion === "reservada" ? `${via} y reserva creada` : r?.accion === "en_espera" ? `${via} y petición en espera` : via;
  return base;
}

/** Línea de veredicto en texto plano; solo lo que no está disponible lleva color. */
function veredicto(ctx, k) {
  if (!k) return null;
  const [t, txt] = VEREDICTO[k.veredicto] ?? VEREDICTO.sin_datos;
  return ctx.el("p", { class: `bl-veredicto${t === "critico" || t === "aviso" ? ` is-${t}` : ""}` }, ctx.el("strong", null, txt), k.motivo ? `. ${limpiar(k.motivo)}` : null);
}

export function renderBloque(bloque, { ejecutar, ui, el }) {
  const ctx = { ejecutar: typeof ejecutar === "function" ? ejecutar : async () => ({ ok: false, mensaje: "Acción no disponible" }), ui, el };
  try {
    const fn = PINTORES[bloque?.tipo];
    if (!fn) return pintarAviso({ tono: "aviso", titulo: "Bloque no reconocido", texto: `El tipo "${bloque?.tipo ?? "desconocido"}" no se puede mostrar.` }, ctx);
    return fn(bloque, ctx);
  } catch (e) {
    console.error("Bloque con error", bloque?.tipo, e);
    return pintarAviso({ tono: "aviso", titulo: "No se ha podido mostrar este bloque", texto: "Pregunta de nuevo." }, ctx);
  }
}

/** Raíz de un bloque: article con el prefijo de la sección. */
function raiz(ctx, tipo, ...hijos) {
  return ctx.el("article", { class: `sec-asistente-bloques bl bl--${tipo}`, dataset: { bloque: tipo } }, ...hijos);
}

function cabecera(ctx, titulo) {
  return titulo ? ctx.el("h3", { class: "bl__titulo" }, titulo) : null;
}

/**
 * Botones de acciones. El primero es el principal (amarillo) y el resto discretos. `alTerminar(res, accion)` permite repintar el bloque.
 * Con `discreto` ninguno es principal. Devuelve { el, estado } donde estado es la línea de resultado (role=status).
 */
function acciones(ctx, lista, { alTerminar = null, valores = null, discreto = false } = {}) {
  const { el, ui } = ctx;
  const validas = (lista ?? []).filter((a) => a && TIPOS_ACCION.has(a.tipo));
  const estado = el("p", { class: "bl__estado", role: "status" });
  estado.hidden = true;
  if (!validas.length) return { el: null, estado };
  const botones = validas.map((a, i) => {
    const b = ui.boton({
      texto: a.etiqueta ?? "Abrir", variante: i === 0 && !discreto ? "cta" : "fantasma", tam: "sm",
      onclick: async () => {
        botones.forEach((x) => { x.disabled = true; });
        b.setAttribute("aria-busy", "true");
        let res;
        try { res = await ctx.ejecutar(a, valores ? valores() : undefined); } catch (e) { res = { ok: false, mensaje: "No se ha podido completar la acción." }; }
        botones.forEach((x) => { x.disabled = false; });
        b.removeAttribute("aria-busy");
        const articulo = b.closest("article.bl");
        if (res?.ok && res.tarjeta && articulo) {
          articulo.className = "sec-asistente-bloques bl bl--resultado";
          articulo.dataset.bloque = "resultado";
          articulo.replaceChildren(pintarResultado({ ...res.tarjeta, tipo: "resultado" }, ctx).firstChild);
          return;
        }
        if (res?.mensaje) mostrarEstado(estado, res);
        if (alTerminar) alTerminar(res ?? {}, a);
      },
    });
    return b;
  });
  return { el: el("div", { class: "bl__acciones" }, botones), estado };
}

function mostrarEstado(nodo, res) {
  nodo.hidden = false;
  nodo.className = `bl__estado is-${res.ok === false ? "critico" : "ok"}`;
  nodo.replaceChildren(ctxIcono(res.ok === false ? "alert" : "check"), document.createTextNode(res.mensaje));
}
const ctxIcono = (n) => iconoUi(n, { tam: 14 });

/** Fila simple: texto a la izquierda y una acción discreta a la derecha. */
function fila(ctx, { clase = "", principal, secundario = null, extra = null, accion = null }) {
  const { el } = ctx;
  const a = accion ? acciones(ctx, [accion], { discreto: true }) : { el: null, estado: null };
  return el("li", { class: `bl-fila ${clase}`.trim() },
    el("div", { class: "bl-fila__texto" }, el("strong", null, principal), secundario && el("span", null, secundario), extra),
    a.el, a.estado);
}

/* ------------------------------------------------------------------ pintores */

function pintarKpi(b, ctx) {
  const { el } = ctx;
  return raiz(ctx, "kpi", cabecera(ctx, b.titulo),
    el("div", { class: "bl-kpis" }, (b.items ?? []).map((k) => el("div", { class: `bl-kpi is-${tono(k.tono)}` },
      el("strong", { class: "bl-kpi__valor" }, k.valor), el("span", { class: "bl-kpi__etiqueta" }, k.etiqueta)))));
}

function pintarReserva(b, ctx) {
  const { el } = ctx;
  const a = acciones(ctx, b.acciones, { discreto: true });
  return raiz(ctx, "reserva",
    el("div", { class: "bl-fila__texto" }, el("strong", null, b.titulo), b.subtitulo && el("span", null, b.subtitulo),
      b.semaforo?.motivo && el("span", { class: b.semaforo.color === "rojo" ? "is-critico" : null }, limpiar(b.semaforo.motivo))),
    a.el, a.estado);
}

function pintarEstancias(b, ctx) {
  const { el, ui } = ctx;
  const filas = (b.estancias ?? []).map((e) => fila(ctx, {
    principal: e.huesped, secundario: `${fechaCorta(e.checkin)} a ${fechaCorta(e.checkout)}${e.tipo ? ` · ${e.tipo}` : ""}`,
    extra: e.semaforo?.motivo && el("span", { class: e.semaforo.color === "rojo" ? "is-critico" : null }, limpiar(e.semaforo.motivo)),
    accion: { tipo: "abrir_estancia", etiqueta: "Abrir", id: e.id },
  }));
  return raiz(ctx, "estancias", cabecera(ctx, b.titulo), filas.length ? el("ul", { class: "bl-lista" }, filas) : ui.vacio({ titulo: "No hay estancias que mostrar" }));
}

/* ---- comunicación */

function pintarComunicacion(b, ctx) {
  const { el, ui } = ctx;
  let c = b.comunicacion;
  const cuerpo = el("div", { class: "bl__cuerpo" });
  const marco = raiz(ctx, "comunicacion", cuerpo);

  const pintar = (mensajeLocal = null) => {
    const pendiente = c.estado === "pendiente" || c.estado === "en_espera";
    const principales = (b.acciones ?? []).filter((x) => x.tipo === "confirmar_comunicacion" || x.tipo === "descartar_comunicacion");
    const a = pendiente ? acciones(ctx, principales, { alTerminar: (res) => {
      if (res.ok === false) return;
      const detalleCom = res.detalle?.canal && res.detalle?.id ? res.detalle : null;
      c = detalleCom ?? { ...c, estado: res.estado ?? (res.ok ? "respondida" : c.estado) };
      pintar(res.mensaje ?? null);
    } }) : { el: null, estado: null };
    const r = c.respuesta;
    const borrador = r && el("blockquote", { class: "bl-borrador" },
      el("span", { class: "bl-borrador__para" }, `Para ${telefono(r.destinatario ?? "")} por ${NOMBRE_CANAL[r.canal] ?? r.canal}`),
      r.asunto && el("strong", null, r.asunto),
      el("p", null, r.texto));
    llenar(cuerpo,
      c.alerta && el("p", { class: "bl-alerta", role: "alert" }, `Aviso de las ${c.alerta.hora}. ${c.alerta.texto}`),
      el("h3", { class: "bl__titulo" }, c.de?.nombre ?? "Sin nombre", el("span", { class: "bl__hora" }, ` · ${NOMBRE_CANAL[c.canal] ?? c.canal} ${c.hora ?? ""}`)),
      veredicto(ctx, c.contraste),
      borrador,
      pendiente ? a.el : el("p", { class: `bl__estado is-${c.estado === "descartada" ? "neutro" : "ok"}`, role: "status" },
        ui.icono(c.estado === "descartada" ? "x" : "check", { tam: 14 }), mensajeLocal ?? frase(c)),
      pendiente && a.estado);
  };
  pintar();
  return marco;
}

function filaComunicacion(ctx, c) {
  const { el } = ctx;
  const [t, txt] = c.contraste ? (VEREDICTO[c.contraste.veredicto] ?? VEREDICTO.sin_datos) : [null, null];
  return fila(ctx, {
    principal: c.de?.nombre ?? "Sin nombre", secundario: `${NOMBRE_CANAL[c.canal] ?? c.canal} ${c.hora ?? ""}`.trim(),
    extra: txt && el("span", { class: t === "critico" || t === "aviso" ? `is-${t}` : null }, txt),
    accion: { tipo: "abrir_comunicacion", etiqueta: "Abrir", id: c.id },
  });
}

function pintarListaComunicaciones(b, ctx) {
  const { el, ui } = ctx;
  const lista = b.comunicaciones ?? [];
  return raiz(ctx, "comunicaciones", cabecera(ctx, b.titulo),
    lista.length ? el("ul", { class: "bl-lista" }, lista.map((c) => filaComunicacion(ctx, c))) : ui.vacio({ titulo: "No hay comunicaciones pendientes" }));
}

/* ---- fuentes, prioridades, cola, conflictos, navegación */

function pintarFuentes(b, ctx) {
  const { el } = ctx;
  const a = acciones(ctx, b.acciones, { discreto: true });
  const filas = (b.fuentes ?? []).map((f) => el("li", { class: "bl-fila" },
    el("div", { class: "bl-fila__texto" }, el("strong", null, f.nombre ?? NOMBRE_FUENTE[f.id]),
      el("span", null, [f.nivel ? `Prioridad ${f.nivel}` : "Solo salida", f.ultima ? `última lectura ${f.ultima}` : null].filter(Boolean).join(" · ")),
      f.estado === "error" && el("span", { class: "is-critico" }, "Con error"))));
  return raiz(ctx, "fuentes", cabecera(ctx, b.titulo), el("ul", { class: "bl-lista" }, filas), a.el, a.estado);
}

function pintarPrioridades(b, ctx) {
  return raiz(ctx, "prioridades", cabecera(ctx, b.titulo), escalera(b.prioridades, { resaltar: b.resaltar ?? null, compacta: true }));
}

function pintarCola(b, ctx) {
  const { el, ui } = ctx;
  const filas = (b.items ?? []).map((it) => fila(ctx, {
    clase: it.color === "rojo" ? "is-critico" : "", principal: it.titulo, secundario: it.detalle,
    accion: { tipo: "abrir_seccion", etiqueta: "Abrir", seccion: it.ruta, params: it.params ?? {} },
  }));
  return raiz(ctx, "cola", cabecera(ctx, b.titulo), filas.length ? el("ul", { class: "bl-lista" }, filas) : ui.vacio({ icono: "check", titulo: "No hay nada pendiente" }));
}

function pintarConflictos(b, ctx) {
  const { el, ui } = ctx;
  const filas = (b.conflictos ?? []).map((c) => fila(ctx, {
    clase: c.nivel === "rojo" ? "is-critico" : "", principal: c.texto,
    secundario: c.sistemas?.length > 0 ? c.sistemas.map((s) => NOMBRE_SISTEMA[s] ?? s).join(" y ") : null,
    accion: c.expediente_id ? { tipo: "abrir_estancia", etiqueta: "Abrir estancia", id: c.expediente_id } : null,
  }));
  return raiz(ctx, "conflictos", cabecera(ctx, b.titulo), filas.length ? el("ul", { class: "bl-lista" }, filas) : ui.vacio({ icono: "check", titulo: "No hay conflictos entre fuentes" }));
}

function pintarNavegacion(b, ctx) {
  const { el } = ctx;
  const filas = (b.items ?? []).map((it) => el("li", null, el("button", {
    type: "button", class: "bl-nav__enlace",
    onclick: () => ctx.ejecutar({ tipo: "abrir_seccion", seccion: it.seccion, params: it.params ?? {}, etiqueta: it.titulo }),
  }, it.titulo, it.insignia ? el("span", { class: "bl-nav__n" }, String(it.insignia)) : null)));
  return raiz(ctx, "navegacion", cabecera(ctx, b.titulo), el("ul", { class: "bl-nav" }, filas));
}

/* ---- proceso */

function pintarProceso(b, ctx) {
  const { el, ui } = ctx;
  const pasos = (b.pasos ?? []).slice(0, 6);
  const lista = el("ol", { class: "bl-pasos", aria: { label: "Pasos del proceso" } });
  const pie = el("div", { class: "bl-proceso__pie" });
  const marco = raiz(ctx, "proceso", cabecera(ctx, b.titulo), lista, pie);
  let temporizador = null;
  let visto = false;
  let corrida = 0;

  const pintarPaso = (p, animar) => {
    const li = el("li", { class: `bl-paso${animar ? " is-entrando" : ""}` },
      el("div", { class: "bl-paso__cuerpo" }, el("strong", null, p.titulo), p.detalle && el("p", { class: "bl-paso__detalle" }, p.detalle)));
    lista.append(li);
    if (animar) requestAnimationFrame(() => requestAnimationFrame(() => li.classList.remove("is-entrando")));
  };

  const terminar = () => {
    const a = acciones(ctx, b.acciones);
    llenar(pie,
      el("div", { class: "bl__acciones" }, a.el?.children ? [...a.el.children] : null, ui.boton({ texto: "Ver de nuevo", variante: "fantasma", tam: "sm", onclick: arrancar })),
      a.estado);
  };

  function arrancar() {
    clearTimeout(temporizador);
    const mia = ++corrida;
    lista.replaceChildren();
    pie.replaceChildren();
    if (reducido() || !pasos.length) { pasos.forEach((p) => pintarPaso(p, false)); terminar(); return; }
    let i = 0;
    const siguiente = () => {
      if (mia !== corrida) return;
      if (marco.isConnected) visto = true;
      else if (visto) return; // el bloque se quitó del chat
      pintarPaso(pasos[i], true);
      i += 1;
      if (i < pasos.length) temporizador = setTimeout(siguiente, 450);
      else terminar();
    };
    siguiente();
  }
  arrancar();
  return marco;
}

/* ---- tabla de ocupación */

function pintarOcupacion(b, ctx) {
  const { el } = ctx;
  const fechas = b.fechas ?? [];
  const celda = (c) => {
    if (!c) return el("td", { class: "u-derecha u-tabular" }, "");
    if (c.cerrado) return el("td", { class: "u-derecha u-tabular bl-ocup__cerrado" }, "Cerrado");
    return el("td", { class: `u-derecha u-tabular${c.libres === 0 ? " is-critico" : ""}` }, String(c.libres));
  };
  return raiz(ctx, "ocupacion", cabecera(ctx, b.titulo ?? "Habitaciones libres"),
    el("div", { class: "ui-tabla-caja" }, el("table", { class: "ui-tabla bl-ocup" },
      el("caption", { class: "u-ocultar-visual" }, "Habitaciones libres por tipo y día"),
      el("thead", null, el("tr", null, el("th", { scope: "col" }, "Tipo"), fechas.map((f) => el("th", { scope: "col", class: "u-derecha" }, fechaCorta(f))))),
      el("tbody", null, (b.filas ?? []).map((f) => el("tr", null, el("th", { scope: "row" }, f.tipo),
        fechas.map((fe) => celda((f.celdas ?? []).find((c) => c.fecha === fe)))))))));
}

/* ---- propuesta */

function pintarPropuesta(b, ctx) {
  const { el, ui } = ctx;
  let estado = b.estado ?? "pendiente";
  let resultado = null;
  const cuerpo = el("div", { class: "bl__cuerpo" });
  const marco = raiz(ctx, "propuesta", cuerpo);
  const pintar = () => {
    const pendiente = estado === "pendiente";
    const a = pendiente ? acciones(ctx, b.acciones, { alTerminar: (res, acc) => {
      if (res.ok === false) return;
      estado = res.estado ?? (acc.tipo === "rechazar_propuesta" ? "rechazada" : "aprobada");
      resultado = res.mensaje ?? null;
      pintar();
    } }) : { el: null, estado: null };
    const para = [b.destino && (NOMBRE_FUENTE[b.destino] ?? b.destino), b.destinatario && telefono(b.destinatario)].filter(Boolean).join(" · ");
    llenar(cuerpo,
      el("blockquote", { class: "bl-cita" }, limpiar(b.texto)),
      para && el("p", { class: "bl__hora" }, `Para ${para}`),
      pendiente ? a.el : el("p", { class: `bl__estado is-${estado === "aprobada" ? "ok" : "neutro"}`, role: "status" },
        ui.icono(estado === "aprobada" ? "check" : "x", { tam: 14 }), resultado ?? (estado === "aprobada" ? "Aprobada" : "Rechazada")),
      pendiente && a.estado);
  };
  pintar();
  return marco;
}

/* ---- formulario walk-in */

function pintarFormulario(b, ctx) {
  const { el, ui } = ctx;
  const campos = (b.campos ?? []).map((f) => ({ f, c: ui.campo({ etiqueta: f.etiqueta, nombre: f.nombre, tipo: f.tipo ?? "texto", opciones: f.opciones ?? [], valor: f.valor ?? "", obligatorio: !!f.obligatorio, ...(f.tipo === "numero" ? { min: 1 } : {}) }) }));
  const leer = () => Object.fromEntries(campos.map(({ f, c }) => [f.nombre, c.leer()]));
  const estado = el("p", { class: "bl__estado", role: "status" });
  estado.hidden = true;
  const envio = b.envio ?? { tipo: "enviar_formulario", etiqueta: "Añadir walk-in", formulario: b.id ?? "walkin" };
  const enviar = ui.boton({ texto: envio.etiqueta ?? "Añadir walk-in", variante: "cta", tam: "sm", tipo: "submit" });
  const form = el("form", { class: "bl-form", novalidate: true, onsubmit: async (e) => {
    e.preventDefault();
    let falta = false;
    campos.forEach(({ f, c }) => { const vacio = f.obligatorio && (c.leer() === "" || c.leer() == null); c.error(vacio ? "Falta este dato" : ""); falta ||= vacio; });
    if (falta) return;
    enviar.disabled = true;
    let res;
    try { res = await ctx.ejecutar({ ...envio, tipo: "enviar_formulario", formulario: envio.formulario ?? b.id ?? "walkin" }, leer()); } catch { res = { ok: false, mensaje: "No se ha podido añadir el walk-in." }; }
    if (res?.ok === false) enviar.disabled = false;
    else campos.forEach(({ c }) => { c.entrada.disabled = true; });
    if (res?.mensaje) mostrarEstado(estado, res);
  } }, el("div", { class: "bl-form__campos" }, campos.map(({ c }) => c.el)), el("div", { class: "bl__acciones" }, enviar), estado);
  return raiz(ctx, "formulario", cabecera(ctx, b.titulo ?? "Walk-in"), form);
}

/* ---- aviso y sugerencias */

function pintarAviso(b, ctx) {
  const { el } = ctx;
  const t = tono(b.tono);
  return raiz(ctx, "aviso", el("div", { class: `bl-aviso is-${t}`, role: t === "critico" ? "alert" : null },
    b.titulo && el("strong", null, b.titulo), b.texto && el("p", null, b.texto)));
}

function pintarSugerencias(b, ctx) {
  const { el } = ctx;
  return raiz(ctx, "sugerencias", el("div", { class: "bl-sugerencias", role: "group", aria: { label: "Preguntas sugeridas" } },
    (b.items ?? []).map((t) => el("button", { type: "button", class: "bl-sugerencia", onclick: () => ctx.ejecutar({ tipo: "preguntar", texto: String(t) }) }, String(t)))));
}

/** Tarjeta de resultado de una acción de escritura: qué se hizo, con filas de datos y la siguiente acción. */
function pintarResultado(b, ctx) {
  const { el, ui } = ctx;
  const t = tono(b.tono ?? "ok");
  const sig = acciones(ctx, b.acciones);
  return raiz(ctx, "resultado", el("div", { class: `bl-resultado is-${t}` },
    el("div", { class: "bl-resultado__cab" },
      el("span", { class: "bl-resultado__icono", aria: { hidden: "true" } }, ui.icono(t === "ok" ? "check" : "info", { tam: 20 })),
      el("strong", { class: "bl-resultado__titulo" }, b.titulo ?? "Hecho"),
      b.simulado !== false && ui.chip({ texto: "Simulado", tono: "neutro" })),
    (b.filas ?? []).length > 0 && ui.kv(b.filas, { columnas: 2 }),
    sig.el));
}

const PINTORES = {
  resultado: pintarResultado,
  resumen_kpi: pintarKpi, tarjeta_reserva: pintarReserva, lista_estancias: pintarEstancias, comunicacion: pintarComunicacion,
  lista_comunicaciones: pintarListaComunicaciones, fuentes: pintarFuentes, prioridades: pintarPrioridades, cola: pintarCola, conflictos: pintarConflictos,
  navegacion: pintarNavegacion, proceso: pintarProceso, tabla_ocupacion: pintarOcupacion, propuesta: pintarPropuesta, formulario: pintarFormulario,
  aviso: pintarAviso, sugerencias: pintarSugerencias,
};
