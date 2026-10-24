/*
  Pintado de los bloques del chat. Interfaz fija: renderBloque(bloque, { ejecutar, ui, el }) devuelve un HTMLElement.
  ejecutar(accion, valores) devuelve una promesa de { ok, mensaje, estado, detalle } y es lo único que dispara acciones.
  Todo el texto entra como nodo de texto (nada de innerHTML). Un tipo desconocido o un bloque roto se pinta como aviso y nunca rompe el chat.

  Campos que usa cada bloque (formas de design/CONTRATO-CORE.md 4.1 y CONTRATO.md 5):
  - resumen_kpi: titulo, items[{etiqueta, valor, detalle, tono}]
  - tarjeta_reserva: titulo, subtitulo, chips[{texto,tono}], campos[{etiqueta,valor}], prioridad, semaforo{color,motivo,accion_sugerida}, sistemas, acciones
  - lista_estancias: titulo, contadores{color:n}, estancias[{id, huesped, checkin, checkout, tipo, origen, personas, prioridad, sistemas, semaforo}]
  - comunicacion: comunicacion{id, canal, hora, de, asunto, texto, tipo, peticion, prioridad, estado, contraste{veredicto,motivo,noches[]},
    respuesta{canal,destinatario,asunto,texto}, alerta{hora,texto}, resultado{hora,canal,destinatario,accion,actor,simulado}}, acciones
  - lista_comunicaciones: titulo, comunicaciones[] (cada una con los campos anteriores; se pinta una fila con acción abrir_comunicacion)
  - fuentes: titulo, fuentes[{id,nivel,tipo,nombre,icono,estado,detalle,ultima,recibido}], acciones (sincronizar)
  - prioridades: titulo, prioridades{niveles,reglas}, resaltar
  - cola: titulo, items[{id,color,titulo,detalle,prioridad,ruta,params}]
  - conflictos: titulo, conflictos[{id,tipo,nivel,texto,expediente_id,sistemas}]
  - navegacion: titulo, items[{seccion,titulo,descripcion,icono,params,insignia}]
  - proceso: id, titulo, resumen, pasos[{id,titulo,fuente,detalle,dato,resultado}], acciones
  - tabla_ocupacion: titulo, fechas[], filas[{tipo,capacidad,celdas[{fecha,ocupadas,libres,cerrado}]}]
  - propuesta: id, texto, destino, destinatario, origen, estado, acciones
  - formulario (walkin): id, titulo, campos[{nombre,etiqueta,tipo,opciones,valor,obligatorio}], envio{tipo,etiqueta,formulario}
  - aviso: tono, titulo, texto. sugerencias: items[string]
*/
import { chipSemaforo, pastillaNivel, escalera, chipVeredicto, chipsSistemas, chipSistema, ICONO_FUENTE, NOMBRE_FUENTE, NOMBRE_COLOR, NOMBRE_SISTEMA } from "../ui-hotel.js";
import { fechaCorta, icono as iconoUi } from "../ui.js";

const TIPOS_ACCION = new Set(["preguntar", "abrir_seccion", "abrir_estancia", "abrir_comunicacion", "confirmar_comunicacion", "descartar_comunicacion",
  "aprobar_propuesta", "rechazar_propuesta", "enviar_formulario", "sincronizar", "simular_roomcloud", "marcar_ofihotel"]);
const ICONO_ACCION = { confirmar_comunicacion: "check", aprobar_propuesta: "check", sincronizar: "refresh", preguntar: "sparkles", simular_roomcloud: "zap" };
const NOMBRE_CANAL = { correo: "correo", whatsapp: "WhatsApp" };
const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
const TIPO_HAB = { "DBL-STD": "doble", "SGL-STD": "individual", "TWN-STD": "twin", "TRP-STD": "triple" };
const TONOS = new Set(["neutro", "ok", "aviso", "critico", "info"]);
const tono = (t) => (TONOS.has(t) ? t : "neutro");
const reducido = () => typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;

/* ------------------------------------------------------------------ utilidades */

const dia = (iso) => Number(String(iso).slice(8, 10));
const mes = (iso) => MESES[Number(String(iso).slice(5, 7)) - 1] ?? "";

/** "24 al 27 de octubre", o "30 de octubre al 2 de noviembre" si cambia el mes. */
function rangoLargo(desde, hasta) {
  if (!desde || !hasta) return "";
  return mes(desde) === mes(hasta) ? `${dia(desde)} al ${dia(hasta)} de ${mes(hasta)}` : `${dia(desde)} de ${mes(desde)} al ${dia(hasta)} de ${mes(hasta)}`;
}

const reponer = (nodo, ...hijos) => nodo.replaceChildren(...hijos.flat().filter((h) => h != null && h !== false));
const recortar = (t, n) => (String(t ?? "").length > n ? `${String(t).slice(0, n).trimEnd()}…` : String(t ?? ""));
const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;

function entendido(c) {
  const p = c.peticion;
  if (c.tipo === "peticion_habitacion" && p) {
    const hab = TIPO_HAB[p.tipo_habitacion] ?? p.tipo_habitacion ?? "habitación";
    const partes = [p.habitaciones > 1 ? `${p.habitaciones} habitaciones ${hab}s` : hab, rangoLargo(p.desde, p.hasta), plural(p.personas ?? 1, "persona", "personas")];
    return `Entendido: ${partes.filter(Boolean).join(", ")}`;
  }
  return { pregunta: "Entendido: pregunta del cliente, sin petición de habitación", cambio: "Entendido: cambio sobre una reserva" }[c.tipo] ?? "Entendido: mensaje sin petición de habitación";
}

/** Frase de resultado de una comunicación ya tramitada. */
function frase(c) {
  const r = c.resultado;
  if (c.estado === "descartada") return "Descartada";
  const via = r ? `Enviado por ${NOMBRE_CANAL[r.canal] ?? r.canal}${r.destinatario ? ` a ${r.destinatario}` : ""}` : `Respondida por ${NOMBRE_CANAL[c.canal] ?? c.canal}`;
  const base = r?.accion === "reservada" ? `${via} y reserva creada` : r?.accion === "en_espera" ? `${via}; queda en espera` : via;
  return `${base}${r?.actor ? `, por ${r.actor}` : ""} (simulado)`;
}

export function renderBloque(bloque, { ejecutar, ui, el }) {
  const ctx = { ejecutar: typeof ejecutar === "function" ? ejecutar : async () => ({ ok: false, mensaje: "Acción no disponible" }), ui, el };
  try {
    const fn = PINTORES[bloque?.tipo];
    if (!fn) return pintarAviso({ tono: "aviso", titulo: "Bloque no reconocido", texto: `El asistente ha devuelto un bloque de tipo "${bloque?.tipo ?? "desconocido"}" que esta pantalla no sabe mostrar.` }, ctx);
    return fn(bloque, ctx);
  } catch (e) {
    console.error("Bloque con error", bloque?.tipo, e);
    return pintarAviso({ tono: "aviso", titulo: "No se ha podido mostrar este bloque", texto: "Pregunta de nuevo o abre la pantalla correspondiente desde el menú." }, ctx);
  }
}

/** Raíz de un bloque: article con el prefijo de la sección. */
function raiz(ctx, tipo, ...hijos) {
  return ctx.el("article", { class: `sec-asistente-bloques bl bl--${tipo}`, dataset: { bloque: tipo } }, ...hijos);
}

function cabecera(ctx, titulo, extra = null, subtitulo = null) {
  const { el } = ctx;
  return el("header", { class: "bl__cab" },
    el("div", { class: "bl__cab-textos" }, titulo && el("h3", { class: "bl__titulo" }, titulo), subtitulo && el("p", { class: "bl__sub" }, subtitulo)),
    extra && el("div", { class: "bl__cab-extra" }, extra));
}

/**
 * Botones de acciones. El primero es el principal. `alTerminar(res, accion)` permite repintar el bloque.
 * Devuelve { el, estado } donde estado es la línea de resultado (role=status).
 */
function acciones(ctx, lista, { alTerminar = null, valores = null } = {}) {
  const { el, ui } = ctx;
  const validas = (lista ?? []).filter((a) => a && TIPOS_ACCION.has(a.tipo));
  const estado = el("p", { class: "bl__estado", role: "status" });
  estado.hidden = true;
  if (!validas.length) return { el: null, estado };
  const botones = validas.map((a, i) => {
    const b = ui.boton({
      texto: a.etiqueta ?? "Abrir", icono: ICONO_ACCION[a.tipo] ?? (a.tipo.startsWith("abrir") ? "arrow-up-right" : null),
      variante: i === 0 ? "oscuro" : "secundario", tam: "sm",
      onclick: async () => {
        botones.forEach((x) => { x.disabled = true; });
        b.setAttribute("aria-busy", "true");
        let res;
        try { res = await ctx.ejecutar(a, valores ? valores() : undefined); } catch (e) { res = { ok: false, mensaje: "No se ha podido completar la acción." }; }
        botones.forEach((x) => { x.disabled = false; });
        b.removeAttribute("aria-busy");
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

/* ------------------------------------------------------------------ pintores */

function pintarKpi(b, ctx) {
  const { el } = ctx;
  return raiz(ctx, "kpi", b.titulo && cabecera(ctx, b.titulo),
    el("div", { class: "bl-kpis" }, (b.items ?? []).map((k) => el("div", { class: `bl-kpi is-${tono(k.tono)}` },
      el("span", { class: "bl-kpi__etiqueta" }, k.etiqueta), el("strong", { class: "bl-kpi__valor" }, k.valor), k.detalle && el("span", { class: "bl-kpi__detalle" }, k.detalle)))));
}

function cuerpoReserva(ctx, d) {
  const { el, ui } = ctx;
  return el("div", { class: "bl-reserva" },
    el("div", { class: "bl-reserva__cab" },
      el("div", { class: "bl-reserva__textos" }, el("strong", { class: "bl-reserva__titulo" }, d.titulo), d.subtitulo && el("span", { class: "bl-reserva__sub" }, d.subtitulo)),
      d.prioridad && pastillaNivel(d.prioridad)),
    el("div", { class: "bl__chips" }, d.semaforo && chipSemaforo(d.semaforo.color), (d.chips ?? []).map((c) => ui.chip({ texto: c.texto, tono: tono(c.tono), punto: true }))),
    d.semaforo?.motivo && el("p", { class: "bl-reserva__motivo" }, d.semaforo.motivo),
    d.campos?.length > 0 && ui.kv(d.campos, { columnas: 3 }),
    d.sistemas && chipsSistemas(d.sistemas));
}

function pintarReserva(b, ctx) {
  const a = acciones(ctx, b.acciones);
  return raiz(ctx, "reserva", cuerpoReserva(ctx, b), a.el, a.estado);
}

function pintarEstancias(b, ctx) {
  const { el, ui } = ctx;
  const cont = Object.entries(b.contadores ?? {}).filter(([, n]) => n > 0).map(([c, n]) => chipSemaforo(c, `${NOMBRE_COLOR[c] ?? c}: ${n}`));
  const filas = (b.estancias ?? []).map((e) => {
    const a = acciones(ctx, [{ tipo: "abrir_estancia", etiqueta: "Abrir", id: e.id }]);
    return el("li", { class: "bl-fila" }, cuerpoReserva(ctx, {
      titulo: e.huesped, subtitulo: `${fechaCorta(e.checkin)} a ${fechaCorta(e.checkout)} · ${e.tipo ?? ""}`.trim(), prioridad: e.prioridad, semaforo: e.semaforo, sistemas: e.sistemas,
      campos: [{ etiqueta: "Origen", valor: NOMBRE_FUENTE[e.origen] ?? e.origen ?? "" }, { etiqueta: "Personas", valor: String(e.personas ?? "") }],
    }), a.el, a.estado);
  });
  return raiz(ctx, "estancias", cabecera(ctx, b.titulo, null), cont.length > 0 && el("div", { class: "bl__chips" }, cont),
    filas.length ? el("ul", { class: "bl-lista" }, filas) : ui.vacio({ titulo: "No hay estancias que mostrar" }));
}

/* ---- comunicación */

function tablaNoches(ctx, noches, id) {
  const { el } = ctx;
  const cols = ["Noche", "RoomCloud", "OfiHotel", "Recepción", "Retenidas", "Libres para esta"];
  return el("div", { class: "ui-tabla-caja" }, el("table", { class: "ui-tabla bl-noches" },
    el("caption", { class: "u-ocultar-visual" }, "Disponibilidad noche a noche para esta petición"),
    el("thead", null, el("tr", null, cols.map((c) => el("th", { scope: "col", class: c === "Noche" ? null : "u-derecha" }, c)))),
    el("tbody", null, noches.map((n) => el("tr", null,
      el("th", { scope: "row" }, fechaCorta(n.fecha)),
      ["roomcloud", "ofihotel", "recepcion"].map((f) => el("td", { class: "u-derecha u-tabular" }, String(n.por_fuente?.[f] ?? 0))),
      el("td", { class: "u-derecha u-tabular" }, String(n.retenidas ?? 0)),
      el("td", { class: `u-derecha u-tabular bl-noches__libres${n.libres_para_esta > 0 ? " is-ok" : " is-critico"}` }, String(n.libres_para_esta ?? 0)))))));
}

function pintarComunicacion(b, ctx) {
  const { el, ui } = ctx;
  let c = b.comunicacion;
  const cuerpo = el("div", { class: "bl__cuerpo" });
  const marco = raiz(ctx, "comunicacion", cuerpo);

  const pintar = (mensajeLocal = null) => {
    const pendiente = c.estado === "pendiente";
    const k = c.contraste;
    const a = pendiente ? acciones(ctx, b.acciones, { alTerminar: (res) => {
      if (res.ok === false) return;
      const detalleCom = res.detalle?.canal && res.detalle?.id ? res.detalle : null;
      c = detalleCom ?? { ...c, estado: res.estado ?? (res.ok ? "respondida" : c.estado) };
      pintar(res.mensaje ?? null);
    } }) : { el: null, estado: null };
    const borrador = c.respuesta && el("div", { class: `bl-burbuja bl-burbuja--${c.respuesta.canal ?? c.canal}` },
      el("div", { class: "bl-burbuja__cab" }, ui.icono(ICONO_FUENTE[c.respuesta.canal] ?? "message", { tam: 14 }),
        el("span", null, `Respuesta por ${NOMBRE_CANAL[c.respuesta.canal] ?? c.respuesta.canal} a ${c.respuesta.destinatario ?? ""}`)),
      c.respuesta.asunto && el("strong", { class: "bl-burbuja__asunto" }, c.respuesta.asunto),
      el("p", { class: "bl-burbuja__texto" }, c.respuesta.texto));
    reponer(cuerpo,
      c.alerta && el("div", { class: "bl-banner", role: "alert" }, ui.icono("alert", { tam: 16 }),
        el("div", null, el("strong", null, `Aviso de las ${c.alerta.hora}`), el("span", null, c.alerta.texto))),
      el("header", { class: "bl-com__cab" },
        el("span", { class: "bl-com__canal", aria: { hidden: "true" } }, ui.icono(ICONO_FUENTE[c.canal] ?? "message", { tam: 18 })),
        el("div", { class: "bl-com__quien" }, el("strong", null, c.de?.nombre ?? "Sin nombre"),
          el("span", null, `${NOMBRE_CANAL[c.canal] ?? c.canal} · ${c.hora ?? ""}${c.de?.contacto ? ` · ${c.de.contacto}` : ""}`)),
        c.prioridad && pastillaNivel(c.prioridad)),
      el("blockquote", { class: "bl-com__original" }, c.asunto && c.canal === "correo" && el("strong", null, c.asunto), el("p", null, recortar(c.texto, 220))),
      el("p", { class: "bl-com__entendido" }, ui.icono("sparkles", { tam: 14 }), entendido(c)),
      k && el("div", { class: "bl-com__veredicto" }, chipVeredicto(k.veredicto), k.motivo && el("span", { class: "bl-com__motivo" }, k.motivo)),
      k?.noches?.length > 0 && tablaNoches(ctx, k.noches, c.id),
      borrador,
      pendiente ? a.el : el("p", { class: `bl__estado is-${c.estado === "descartada" ? "neutro" : "ok"}`, role: "status" },
        ui.icono(c.estado === "descartada" ? "x" : "check", { tam: 14 }), mensajeLocal ?? frase(c)),
      pendiente && a.estado);
  };
  pintar();
  return marco;
}

function filaComunicacion(ctx, c) {
  const { el, ui } = ctx;
  const a = acciones(ctx, [{ tipo: "abrir_comunicacion", etiqueta: "Abrir", id: c.id }]);
  return el("li", { class: "bl-fila bl-fila--com" },
    el("div", { class: "bl-com__cab" },
      el("span", { class: "bl-com__canal", aria: { hidden: "true" } }, ui.icono(ICONO_FUENTE[c.canal] ?? "message", { tam: 18 })),
      el("div", { class: "bl-com__quien" }, el("strong", null, c.de?.nombre ?? "Sin nombre"), el("span", null, `${NOMBRE_CANAL[c.canal] ?? c.canal} · ${c.hora ?? ""}`)),
      c.prioridad && pastillaNivel(c.prioridad)),
    el("p", { class: "bl-com__entendido" }, entendido(c)),
    el("div", { class: "bl-com__veredicto" }, c.contraste ? chipVeredicto(c.contraste.veredicto) : null,
      c.estado !== "pendiente" && ui.chip({ texto: { respondida: "Respondida", descartada: "Descartada", en_espera: "En espera" }[c.estado] ?? c.estado, tono: "neutro", punto: true }),
      c.contraste?.motivo && el("span", { class: "bl-com__motivo" }, c.contraste.motivo)),
    a.el, a.estado);
}

function pintarListaComunicaciones(b, ctx) {
  const { el, ui } = ctx;
  const lista = b.comunicaciones ?? [];
  return raiz(ctx, "comunicaciones", cabecera(ctx, b.titulo, ui.insignia(lista.length)),
    lista.length ? el("ul", { class: "bl-lista" }, lista.map((c) => filaComunicacion(ctx, c))) : ui.vacio({ titulo: "No hay comunicaciones pendientes" }));
}

/* ---- fuentes, prioridades, cola, conflictos, navegación */

const ESTADO_FUENTE = { simulado: ["info", "Simulado"], real: ["ok", "Real"], error: ["critico", "Con error"], sin_datos: ["neutro", "Sin datos"] };

function pintarFuentes(b, ctx) {
  const { el, ui } = ctx;
  const a = acciones(ctx, b.acciones);
  const tarjetas = (b.fuentes ?? []).map((f) => {
    const [t, txt] = ESTADO_FUENTE[f.estado] ?? ["neutro", f.estado ?? ""];
    return el("li", { class: "bl-fuente" },
      el("div", { class: "bl-fuente__cab" }, el("span", { class: "bl-fuente__icono", aria: { hidden: "true" } }, ui.icono(ICONO_FUENTE[f.id] ?? f.icono ?? "dot", { tam: 16 })),
        el("strong", null, f.nombre ?? NOMBRE_FUENTE[f.id])),
      el("div", { class: "bl__chips" }, f.nivel ? pastillaNivel({ nivel: f.nivel, fuente: f.nombre, tipo: f.tipo }, { compacta: true }) : ui.chip({ texto: "Solo salida", tono: "neutro" }),
        ui.chip({ texto: txt, tono: t, punto: true })),
      f.detalle && el("p", { class: "bl-fuente__detalle" }, f.detalle),
      f.ultima && el("p", { class: "bl-fuente__ultima" }, `Última lectura: ${f.ultima}`));
  });
  return raiz(ctx, "fuentes", cabecera(ctx, b.titulo), el("ul", { class: "bl-fuentes" }, tarjetas), a.el, a.estado);
}

function pintarPrioridades(b, ctx) {
  return raiz(ctx, "prioridades", cabecera(ctx, b.titulo), escalera(b.prioridades, { resaltar: b.resaltar ?? null, compacta: false }));
}

function pintarCola(b, ctx) {
  const { el, ui } = ctx;
  const filas = (b.items ?? []).map((it) => {
    const ir = acciones(ctx, [{ tipo: "abrir_seccion", etiqueta: "Abrir", seccion: it.ruta, params: it.params ?? {} }]);
    return el("li", { class: "bl-fila bl-fila--cola" },
      el("div", { class: "bl-cola__chips" }, chipSemaforo(it.color), it.prioridad && pastillaNivel(it.prioridad)),
      el("div", { class: "bl-cola__texto" }, el("strong", null, it.titulo), it.detalle && el("span", null, it.detalle)),
      ir.el, ir.estado);
  });
  return raiz(ctx, "cola", cabecera(ctx, b.titulo, null),
    filas.length ? el("ul", { class: "bl-lista" }, filas) : ui.vacio({ icono: "check", titulo: "No hay nada pendiente" }));
}

function pintarConflictos(b, ctx) {
  const { el, ui } = ctx;
  const filas = (b.conflictos ?? []).map((c) => {
    const crit = c.nivel === "rojo";
    const a = c.expediente_id ? acciones(ctx, [{ tipo: "abrir_estancia", etiqueta: "Abrir estancia", id: c.expediente_id }]) : { el: null, estado: null };
    return el("li", { class: `bl-conflicto is-${crit ? "critico" : "neutro"}` },
      el("span", { class: "bl-conflicto__icono", aria: { hidden: "true" } }, ui.icono("alert", { tam: 16 })),
      el("div", { class: "bl-conflicto__texto" },
        el("p", null, el("strong", null, crit ? "Conflicto: " : "Aviso: "), c.texto),
        c.sistemas?.length > 0 && el("span", { class: "bl-conflicto__sistemas" }, `Sistemas: ${c.sistemas.map((s) => NOMBRE_SISTEMA[s] ?? s).join(" y ")}`)),
      a.el, a.estado);
  });
  return raiz(ctx, "conflictos", cabecera(ctx, b.titulo), filas.length ? el("ul", { class: "bl-lista" }, filas) : ui.vacio({ icono: "check", titulo: "No hay conflictos entre fuentes" }));
}

function pintarNavegacion(b, ctx) {
  const { el, ui } = ctx;
  const tarjetas = (b.items ?? []).map((it) => ui.tarjeta({
    icono: it.icono ?? "arrow-up-right", titulo: it.titulo, subtitulo: it.descripcion, direccion: "horizontal",
    chips: it.insignia ? [ui.insignia(it.insignia, { tono: "acento" })] : [],
    etiqueta: `${it.titulo}${it.insignia ? `, ${it.insignia} pendientes` : ""}`,
    onclick: () => ctx.ejecutar({ tipo: "abrir_seccion", seccion: it.seccion, params: it.params ?? {}, etiqueta: it.titulo }),
  }));
  return raiz(ctx, "navegacion", cabecera(ctx, b.titulo), el("div", { class: "bl-nav" }, tarjetas));
}

/* ---- proceso */

function pintarProceso(b, ctx) {
  const { el, ui } = ctx;
  const pasos = b.pasos ?? [];
  const lista = el("ol", { class: "bl-pasos", aria: { label: "Pasos del proceso" } });
  const pie = el("div", { class: "bl-proceso__pie" });
  const marco = raiz(ctx, "proceso", cabecera(ctx, b.titulo, null, b.resumen), lista, pie);
  let temporizador = null;
  let visto = false;
  let corrida = 0;

  const pintarPaso = (p, animar) => {
    const li = el("li", { class: `bl-paso${animar ? " is-entrando" : ""}`, dataset: { fuente: p.fuente ?? "sistema" } },
      el("span", { class: "bl-paso__marca", aria: { hidden: "true" } }, ui.icono(ICONO_FUENTE[p.fuente] ?? "dot", { tam: 16 })),
      el("div", { class: "bl-paso__cuerpo" },
        el("div", { class: "bl-paso__cab" }, el("strong", null, p.titulo), p.fuente && el("span", { class: "bl-paso__fuente" }, NOMBRE_FUENTE[p.fuente] ?? p.fuente)),
        p.detalle && el("p", { class: "bl-paso__detalle" }, p.detalle),
        p.dato && el("div", { class: "bl__chips" }, ui.chip({ texto: p.dato, tono: "info" })),
        p.resultado && el("p", { class: "bl-paso__resultado" }, ui.icono("check", { tam: 14 }), el("span", null, p.resultado))));
    lista.append(li);
    if (animar) requestAnimationFrame(() => requestAnimationFrame(() => li.classList.remove("is-entrando")));
  };

  const terminar = () => {
    const a = acciones(ctx, b.acciones);
    reponer(pie,
      el("div", { class: "bl__acciones" }, ui.boton({ texto: "Ver de nuevo", icono: "refresh", variante: "fantasma", tam: "sm", onclick: arrancar }), a.el?.children ? [...a.el.children] : null),
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
      if (i < pasos.length) temporizador = setTimeout(siguiente, 600);
      else terminar();
    };
    siguiente();
  }
  arrancar();
  return marco;
}

/* ---- tabla de ocupación */

function pintarOcupacion(b, ctx) {
  const { el, ui } = ctx;
  const fechas = b.fechas ?? [];
  const chipCelda = (c) => {
    if (!c) return ui.chip({ texto: "Sin datos", tono: "neutro" });
    if (c.cerrado) return ui.chip({ texto: "Cerrado", tono: "neutro", punto: true });
    return ui.chip({ texto: c.libres === 0 ? "Completo" : plural(c.libres, "libre", "libres"), tono: c.libres === 0 ? "critico" : c.libres === 1 ? "aviso" : "ok", punto: true });
  };
  return raiz(ctx, "ocupacion", cabecera(ctx, b.titulo ?? "Ocupación", null, "Habitaciones libres por tipo"),
    el("div", { class: "ui-tabla-caja" }, el("table", { class: "ui-tabla bl-ocup" },
      el("caption", { class: "u-ocultar-visual" }, "Habitaciones libres por tipo y día"),
      el("thead", null, el("tr", null, el("th", { scope: "col" }, "Tipo"), fechas.map((f) => el("th", { scope: "col" }, fechaCorta(f))))),
      el("tbody", null, (b.filas ?? []).map((f) => el("tr", null, el("th", { scope: "row" }, f.tipo),
        fechas.map((fe) => el("td", null, chipCelda((f.celdas ?? []).find((c) => c.fecha === fe))))))))));
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
    const etiqueta = { pendiente: ["aviso", "Pendiente de aprobación"], aprobada: ["ok", "Aprobada"], rechazada: ["neutro", "Rechazada"] }[estado] ?? ["neutro", estado];
    reponer(cuerpo,
      cabecera(ctx, "Propuesta del asistente", ui.chip({ texto: etiqueta[1], tono: etiqueta[0], punto: true }), pendiente ? "Nada sale hasta que la apruebes" : null),
      el("blockquote", { class: "bl-cita" }, b.texto),
      ui.kv([b.destino && { etiqueta: "Destino", valor: NOMBRE_FUENTE[b.destino] ?? b.destino }, b.destinatario && { etiqueta: "Destinatario", valor: b.destinatario },
        b.origen && { etiqueta: "Propuesta por", valor: b.origen }].filter(Boolean), { columnas: 3 }),
      pendiente ? a.el : el("p", { class: `bl__estado is-${estado === "aprobada" ? "ok" : "neutro"}`, role: "status" },
        ui.icono(estado === "aprobada" ? "check" : "x", { tam: 14 }), resultado ?? (estado === "aprobada" ? "Aprobada" : "Rechazada")),
      pendiente && a.estado);
  };
  pintar();
  return marco;
}

/* ---- formulario walkin */

function pintarFormulario(b, ctx) {
  const { el, ui } = ctx;
  const campos = (b.campos ?? []).map((f) => ({ f, c: ui.campo({ etiqueta: f.etiqueta, nombre: f.nombre, tipo: f.tipo ?? "texto", opciones: f.opciones ?? [], valor: f.valor ?? "", obligatorio: !!f.obligatorio, ...(f.tipo === "numero" ? { min: 1 } : {}) }) }));
  const leer = () => Object.fromEntries(campos.map(({ f, c }) => [f.nombre, c.leer()]));
  const estado = el("p", { class: "bl__estado", role: "status" });
  estado.hidden = true;
  const envio = b.envio ?? { tipo: "enviar_formulario", etiqueta: "Añadir reserva", formulario: b.id ?? "walkin" };
  const enviar = ui.boton({ texto: envio.etiqueta ?? "Añadir reserva", icono: "plus", variante: "oscuro", tam: "sm", tipo: "submit" });
  const form = el("form", { class: "bl-form", novalidate: true, onsubmit: async (e) => {
    e.preventDefault();
    let falta = false;
    campos.forEach(({ f, c }) => { const vacio = f.obligatorio && (c.leer() === "" || c.leer() == null); c.error(vacio ? "Este dato es obligatorio" : ""); falta ||= vacio; });
    if (falta) return;
    enviar.disabled = true;
    let res;
    try { res = await ctx.ejecutar({ ...envio, tipo: "enviar_formulario", formulario: envio.formulario ?? b.id ?? "walkin" }, leer()); } catch { res = { ok: false, mensaje: "No se ha podido añadir la reserva." }; }
    if (res?.ok === false) enviar.disabled = false;
    else campos.forEach(({ c }) => { c.entrada.disabled = true; });
    if (res?.mensaje) mostrarEstado(estado, res);
  } }, el("div", { class: "bl-form__campos" }, campos.map(({ c }) => c.el)), el("div", { class: "bl__acciones" }, enviar), estado);
  return raiz(ctx, "formulario", cabecera(ctx, b.titulo ?? "Reserva física"), form);
}

/* ---- aviso y sugerencias */

function pintarAviso(b, ctx) {
  const { el, ui } = ctx;
  const t = tono(b.tono);
  const ic = { ok: "check", aviso: "alert", critico: "alert", info: "info", neutro: "info" }[t];
  return raiz(ctx, "aviso", el("div", { class: `bl-aviso is-${t}`, role: t === "critico" ? "alert" : null },
    el("span", { class: "bl-aviso__icono", aria: { hidden: "true" } }, ui.icono(ic, { tam: 18 })),
    el("div", { class: "bl-aviso__texto" }, b.titulo && el("strong", null, b.titulo), b.texto && el("p", null, b.texto))));
}

function pintarSugerencias(b, ctx) {
  const { el, ui } = ctx;
  return raiz(ctx, "sugerencias", el("div", { class: "bl-sugerencias", role: "group", aria: { label: "Preguntas sugeridas" } },
    (b.items ?? []).map((t) => ui.pastilla({ texto: String(t), icono: "sparkles", onclick: () => ctx.ejecutar({ tipo: "preguntar", texto: String(t) }) }))));
}

const PINTORES = {
  resumen_kpi: pintarKpi, tarjeta_reserva: pintarReserva, lista_estancias: pintarEstancias, comunicacion: pintarComunicacion,
  lista_comunicaciones: pintarListaComunicaciones, fuentes: pintarFuentes, prioridades: pintarPrioridades, cola: pintarCola, conflictos: pintarConflictos,
  navegacion: pintarNavegacion, proceso: pintarProceso, tabla_ocupacion: pintarOcupacion, propuesta: pintarPropuesta, formulario: pintarFormulario,
  aviso: pintarAviso, sugerencias: pintarSugerencias,
};
