/*
  Primitivas de interfaz. Cada función devuelve un elemento del DOM (o un objeto con `el` cuando tiene estado) y todo el texto
  entra como texto, nunca como HTML. Los estilos viven en css/components.css con el prefijo ui-.
  El lenguaje visual (bloques, bordes, tarjetas y pestañas) sale de design/DIRECTRICES.md.
*/
import { el, svg, vaciar, uid } from "./dom.js";
import { icono, registrarIcono, nombresIconos } from "./icons.js";

export { el, vaciar, uid, icono, registrarIcono, nombresIconos };

const unir = (...clases) => clases.flat().filter(Boolean).join(" ");

/* ------------------------------------------------------------------ formato */

const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

/** "2026-10-24" a "24 oct". */
export function fechaCorta(iso) {
  if (!iso) return "Sin fecha";
  const [a, m, d] = String(iso).slice(0, 10).split("-").map(Number);
  return `${d} ${MESES[m - 1] ?? ""}`.trim();
}

/** "2026-10-24T09:00" a "09:00". */
export function hora(iso) {
  return iso && String(iso).includes("T") ? String(iso).slice(11, 16) : "";
}

export function fechaHora(iso) {
  return iso ? `${fechaCorta(iso)} ${hora(iso)}`.trim() : "Sin fecha";
}

export function moneda(valor, divisa = "EUR") {
  if (valor == null || valor === "") return "";
  return new Intl.NumberFormat("es-ES", { style: "currency", currency: divisa }).format(Number(valor));
}

/* ------------------------------------------------------------------ botones */

/**
 * variante: cta (amarillo, la acción principal de la vista, solo una), oscuro, secundario, fantasma (solo icono), peligro.
 * Un botón sin texto necesita `etiqueta` para los lectores de pantalla.
 */
export function boton({ texto = "", icono: ic = null, variante = "secundario", tam = "md", onclick, desactivado = false,
  tipo = "button", etiqueta = null, cargando = false, clase = "" } = {}) {
  return el("button", {
    type: tipo,
    class: unir("ui-btn", `ui-btn--${variante}`, tam === "sm" && "ui-btn--sm", !texto && "ui-btn--solo-icono", clase),
    disabled: desactivado || cargando,
    aria: { label: etiqueta || (texto ? null : "Acción"), busy: cargando ? "true" : null },
    onclick,
  }, cargando ? icono("loader", { clase: "ui-girar" }) : ic && icono(ic), texto && el("span", null, texto));
}

/** Botón amarillo con flecha que abre un menú oscuro, como el de la referencia de tickets. */
export function botonDividido({ texto, icono: ic, onclick, items = [], etiquetaMenu = "Más acciones" }) {
  const principal = boton({ texto, icono: ic, variante: "cta", onclick, clase: "ui-split__principal" });
  const flecha = boton({ icono: "chevron-down", variante: "cta", etiqueta: etiquetaMenu, clase: "ui-split__flecha" });
  const menu = menuOscuro({ ancla: flecha, items });
  flecha.addEventListener("click", () => menu.alternar());
  return el("div", { class: "ui-split" }, principal, flecha);
}

/* ------------------------------------------------------------------ chips e insignias */

/** tono: neutro, ok, aviso, critico, info. `punto` añade el punto de color. El estado siempre lleva texto, nunca solo color. */
export function chip({ texto, tono = "neutro", punto = false, icono: ic = null, clase = "" }) {
  return el("span", { class: unir("ui-chip", `ui-chip--${tono}`, clase) },
    punto && el("span", { class: "ui-chip__punto", aria: { hidden: "true" } }),
    ic && icono(ic, { tam: 13 }), el("span", null, texto));
}

export function insignia(n, { tono = "neutro" } = {}) {
  return el("span", { class: unir("ui-insignia", `ui-insignia--${tono}`) }, String(n));
}

/* ------------------------------------------------------------------ pastillas (filtros en fila) */

export function pastilla({ texto = "", activa = false, onclick, icono: ic = null, cuenta = null, etiqueta = null }) {
  return el("button", {
    type: "button", class: unir("ui-pastilla", activa && "is-activa", !texto && "ui-pastilla--solo-icono"),
    aria: { pressed: String(activa), label: etiqueta || (texto ? null : "Opción") }, onclick,
  }, ic && icono(ic, { tam: 15 }), texto && el("span", null, texto), cuenta != null && el("span", { class: "ui-pastilla__cuenta" }, String(cuenta)));
}

/** Fila de pastillas como la de la referencia: opcionalmente un "+" al principio y un menú "⋮" al final. La pastilla activa es negra. */
export function filaPastillas({ items, activo, onchange, anadir = null, mas = null, etiqueta = "Filtros" }) {
  const fila = el("div", { class: "ui-pastillas", role: "group", aria: { label: etiqueta } });
  let actual = activo ?? items[0]?.id;
  const dibujar = () => {
    vaciar(fila);
    if (anadir) fila.append(pastilla({ icono: "plus", etiqueta: anadir.etiqueta ?? "Añadir", onclick: anadir.onclick }));
    for (const it of items) {
      fila.append(pastilla({ texto: it.texto, cuenta: it.cuenta, activa: it.id === actual, onclick: () => { actual = it.id; dibujar(); onchange?.(it.id); } }));
    }
    if (mas) fila.append(pastilla({ icono: "more-v", etiqueta: mas.etiqueta ?? "Más opciones", onclick: mas.onclick }));
  };
  dibujar();
  return { el: fila, set(id) { actual = id; dibujar(); }, get valor() { return actual; } };
}

/* ------------------------------------------------------------------ pestañas */

function teclado(lista, botones, seleccionar) {
  lista.addEventListener("keydown", (e) => {
    const i = botones.indexOf(document.activeElement);
    if (i < 0) return;
    let j = i;
    if (e.key === "ArrowRight") j = (i + 1) % botones.length;
    else if (e.key === "ArrowLeft") j = (i - 1 + botones.length) % botones.length;
    else if (e.key === "Home") j = 0;
    else if (e.key === "End") j = botones.length - 1;
    else return;
    e.preventDefault();
    botones[j].focus();
    seleccionar(j);
  });
}

/** Pestañas de baldosa con icono, como la fila superior de la referencia. La activa va en azul. */
export function tileTabs({ items, activo, onchange, etiqueta = "Categorías" }) {
  const lista = el("div", { class: "ui-tiles", role: "tablist", aria: { label: etiqueta } });
  const base = uid("tile");
  const botones = items.map((it) => el("button", {
    type: "button", role: "tab", id: `${base}-${it.id}`, class: "ui-tile", onclick: () => elegir(it.id, true),
  }, el("span", { class: "ui-tile__icono" }, it.icono && icono(it.icono, { tam: 18 })), el("span", { class: "ui-tile__texto" }, it.texto)));
  lista.append(...botones);
  let actual = null;
  function elegir(id, avisar) {
    actual = id;
    botones.forEach((b, i) => {
      const on = items[i].id === id;
      b.classList.toggle("is-activa", on);
      b.setAttribute("aria-selected", String(on));
      b.tabIndex = on ? 0 : -1;
    });
    if (avisar) onchange?.(id);
  }
  elegir(activo ?? items[0]?.id, false);
  teclado(lista, botones, (j) => elegir(items[j].id, true));
  return { el: lista, set: (id) => elegir(id, false), get valor() { return actual; }, idPestana: (id) => `${base}-${id}` };
}

/** Pestañas de texto con línea fina y una muesca curva negra bajo la activa, como la fila central de la referencia. */
export function tabsSubrayado({ items, activo, onchange, etiqueta = "Pestañas" }) {
  const lista = el("div", { class: "ui-tabs", role: "tablist", aria: { label: etiqueta } });
  const base = uid("tab");
  const trazo = svg("path", { fill: "none", stroke: "currentColor", "stroke-width": 2.5, "stroke-linecap": "round" });
  const indicador = svg("svg", { class: "ui-tabs__indicador", height: 10, "aria-hidden": "true", focusable: "false" }, trazo);
  const botones = items.map((it) => el("button", {
    type: "button", role: "tab", id: `${base}-${it.id}`, class: "ui-tab", onclick: () => elegir(it.id, true),
  }, el("span", null, it.texto), it.cuenta != null && insignia(it.cuenta)));
  lista.append(...botones, indicador);
  let actual = null;
  function colocar() {
    const i = items.findIndex((it) => it.id === actual);
    const b = botones[i];
    if (!b || !b.offsetWidth) return;
    const w = b.offsetWidth, c = w / 2;
    indicador.style.width = `${w}px`;
    indicador.style.transform = `translateX(${b.offsetLeft}px)`;
    indicador.setAttribute("viewBox", `0 0 ${w} 10`);
    trazo.setAttribute("d", `M0 1.5 H${c - 20} C${c - 10} 1.5 ${c - 10} 7.5 ${c} 7.5 C${c + 10} 7.5 ${c + 10} 1.5 ${c + 20} 1.5 H${w}`);
  }
  function elegir(id, avisar) {
    actual = id;
    botones.forEach((b, i) => {
      const on = items[i].id === id;
      b.classList.toggle("is-activa", on);
      b.setAttribute("aria-selected", String(on));
      b.tabIndex = on ? 0 : -1;
    });
    colocar();
    if (avisar) onchange?.(id);
  }
  elegir(activo ?? items[0]?.id, false);
  teclado(lista, botones, (j) => elegir(items[j].id, true));
  if (typeof ResizeObserver !== "undefined") new ResizeObserver(colocar).observe(lista);
  requestAnimationFrame(colocar);
  return { el: lista, set: (id) => elegir(id, false), get valor() { return actual; }, idPestana: (id) => `${base}-${id}` };
}

/* ------------------------------------------------------------------ tarjetas, paneles y datos */

/**
 * Tarjeta con borde fino. variante: normal, punteada (textura de puntos como las del carrusel de la referencia) o menta (seleccionada).
 * Si recibe onclick, toda la tarjeta es un botón y no debe contener otros controles dentro.
 */
export function tarjeta({ titulo, subtitulo, icono: ic = null, chips = [], cuerpo = null, pie = null, seleccionada = false,
  onclick, variante = "normal", direccion = "vertical", etiqueta = null, clase = "" }) {
  const interactiva = typeof onclick === "function";
  const raiz = el("div", {
    class: unir("ui-tarjeta", `ui-tarjeta--${variante}`, `ui-tarjeta--${direccion}`, interactiva && "es-interactiva", seleccionada && "is-seleccionada", clase),
    role: interactiva ? "button" : null, tabindex: interactiva ? 0 : null,
    aria: { pressed: interactiva ? String(seleccionada) : null, label: etiqueta },
    onclick,
    onkeydown: interactiva ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onclick(e); } } : null,
  },
  ic && el("span", { class: "ui-tarjeta__icono" }, typeof ic === "string" ? icono(ic, { tam: 20 }) : ic),
  el("div", { class: "ui-tarjeta__texto" },
    titulo && el("div", { class: "ui-tarjeta__titulo" }, titulo),
    subtitulo && el("div", { class: "ui-tarjeta__subtitulo" }, subtitulo),
    chips.length > 0 && el("div", { class: "ui-tarjeta__chips" }, chips.map((c) => (c instanceof Node ? c : chip(c)))),
    cuerpo && el("div", { class: "ui-tarjeta__cuerpo" }, cuerpo),
    pie && el("div", { class: "ui-tarjeta__pie" }, pie)));
  return raiz;
}

/** Carrusel horizontal con flechas de borde fino a los lados, como el de la referencia. */
export function carrusel({ items, ancho = 240, etiqueta = "Opciones" }) {
  const pista = el("div", { class: "ui-carrusel__pista", role: "group", tabindex: 0, aria: { label: etiqueta } },
    items.map((n) => el("div", { class: "ui-carrusel__item", estilo: { "--ancho": `${ancho}px` } }, n)));
  const izq = boton({ icono: "chevron-left", variante: "fantasma", etiqueta: "Anterior", clase: "ui-carrusel__flecha",
    onclick: () => pista.scrollBy({ left: -(ancho + 12) * 1.5, behavior: "smooth" }) });
  const der = boton({ icono: "chevron-right", variante: "fantasma", etiqueta: "Siguiente", clase: "ui-carrusel__flecha",
    onclick: () => pista.scrollBy({ left: (ancho + 12) * 1.5, behavior: "smooth" }) });
  const actualizar = () => {
    izq.disabled = pista.scrollLeft <= 2;
    der.disabled = pista.scrollLeft + pista.clientWidth >= pista.scrollWidth - 2;
  };
  pista.addEventListener("scroll", actualizar, { passive: true });
  requestAnimationFrame(actualizar);
  if (typeof ResizeObserver !== "undefined") new ResizeObserver(actualizar).observe(pista);
  return el("div", { class: "ui-carrusel" }, izq, pista, der);
}

/** Rejilla de etiqueta y valor, como el panel de detalles de la referencia. El valor puede ser texto o un nodo (por ejemplo un chip). */
export function kv(pares, { columnas = 2 } = {}) {
  return el("dl", { class: "ui-kv", estilo: { "--columnas": columnas } }, pares.map((p) => el("div", { class: "ui-kv__par" },
    el("dt", null, p.etiqueta),
    el("dd", { class: p.tono ? `is-${p.tono}` : null }, p.icono && icono(p.icono, { tam: 14 }), p.valor ?? ""))));
}

/** Bloque con borde fino y cabecera: el contenedor básico de casi todas las vistas. */
export function panel({ titulo, subtitulo, acciones = [], hijos = [], variante = "normal", clase = "", id }) {
  const idTitulo = uid("panel");
  return el("section", { class: unir("ui-panel", `ui-panel--${variante}`, clase), id, aria: { labelledby: titulo ? idTitulo : null } },
    (titulo || acciones.length > 0) && el("header", { class: "ui-panel__cabecera" },
      el("div", { class: "ui-panel__textos" },
        titulo && el("h2", { class: "ui-panel__titulo", id: idTitulo }, titulo),
        subtitulo && el("p", { class: "ui-panel__subtitulo" }, subtitulo)),
      acciones.length > 0 && el("div", { class: "ui-panel__acciones" }, acciones)),
    el("div", { class: "ui-panel__cuerpo" }, hijos));
}

export const separador = () => el("hr", { class: "ui-separador" });

export function avatar(texto, { tam = "md" } = {}) {
  const iniciales = String(texto ?? "?").trim().split(/\s+/).slice(0, 2).map((p) => p[0]?.toUpperCase() ?? "").join("") || "?";
  return el("span", { class: unir("ui-avatar", `ui-avatar--${tam}`), aria: { hidden: "true" } }, iniciales);
}

/* ------------------------------------------------------------------ menú flotante oscuro */

/**
 * Menú flotante oscuro con esquinas muy redondeadas, como el de la referencia. Se abre con abrir() o alternar().
 * items: { texto, icono, onclick, peligro } o { separador: true }. Se cierra con Escape, con un clic fuera y al elegir.
 */
export function menuOscuro({ ancla, items, alineacion = "fin", ancho = 264 }) {
  let nodo = null;
  const capas = () => document.getElementById("capas") ?? document.body;
  const cerrar = () => {
    if (!nodo) return;
    nodo.remove();
    nodo = null;
    ancla.setAttribute("aria-expanded", "false");
    document.removeEventListener("pointerdown", fuera, true);
    document.removeEventListener("keydown", teclas, true);
    window.removeEventListener("resize", cerrar);
  };
  function fuera(e) { if (nodo && !nodo.contains(e.target) && !ancla.contains(e.target)) cerrar(); }
  function teclas(e) {
    if (!nodo) return;
    const botones = [...nodo.querySelectorAll("button")];
    const i = botones.indexOf(document.activeElement);
    if (e.key === "Escape") { e.preventDefault(); cerrar(); ancla.focus(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); botones[(i + 1) % botones.length]?.focus(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); botones[(i - 1 + botones.length) % botones.length]?.focus(); }
    else if (e.key === "Home") { e.preventDefault(); botones[0]?.focus(); }
    else if (e.key === "End") { e.preventDefault(); botones.at(-1)?.focus(); }
    else if (e.key === "Tab") cerrar();
  }
  function abrir() {
    if (nodo) return;
    nodo = el("div", { class: "ui-menu", role: "menu", estilo: { "--ancho": `${ancho}px` } }, items.map((it) => (it.separador
      ? el("div", { class: "ui-menu__sep", role: "separator" })
      : el("button", {
        type: "button", role: "menuitem", class: unir("ui-menu__item", it.peligro && "is-peligro"),
        onclick: async () => { cerrar(); await it.onclick?.(); },
      }, it.icono && icono(it.icono, { tam: 18 }), el("span", null, it.texto)))));
    capas().append(nodo);
    const r = ancla.getBoundingClientRect();
    const alto = nodo.offsetHeight;
    const izquierda = alineacion === "fin" ? r.right - ancho : r.left;
    nodo.style.left = `${Math.max(8, Math.min(izquierda, window.innerWidth - ancho - 8))}px`;
    const abajo = r.bottom + 8;
    nodo.style.top = `${abajo + alto > window.innerHeight - 8 ? Math.max(8, r.top - alto - 8) : abajo}px`;
    ancla.setAttribute("aria-expanded", "true");
    ancla.setAttribute("aria-haspopup", "menu");
    nodo.querySelector("button")?.focus();
    document.addEventListener("pointerdown", fuera, true);
    document.addEventListener("keydown", teclas, true);
    window.addEventListener("resize", cerrar);
  }
  return { abrir, cerrar, alternar: () => (nodo ? cerrar() : abrir()), get abierto() { return Boolean(nodo); } };
}

/* ------------------------------------------------------------------ formularios */

const TIPOS_ENTRADA = { texto: "text", fecha: "date", numero: "number", correo: "email", telefono: "tel", hora: "time" };

/**
 * Campo con etiqueta encima. tipo: texto, area, select, fecha, numero, correo, telefono, hora.
 * Devuelve { el, entrada, leer(), poner(v), error(mensaje) }. Las opciones de un select son strings o { valor, texto }.
 */
export function campo({ etiqueta, nombre, tipo = "texto", valor = "", opciones = [], placeholder = "", ayuda = "", error = "",
  obligatorio = false, id, onchange, oninput, min, max, step, filas = 3, desactivado = false, clase = "" }) {
  const idc = id ?? uid("campo");
  const idAyuda = `${idc}-ayuda`;
  const idError = `${idc}-error`;
  let entrada;
  if (tipo === "select") {
    entrada = el("select", { id: idc, name: nombre, class: "ui-entrada ui-entrada--select", required: obligatorio, disabled: desactivado, onchange },
      opciones.map((o) => { const op = typeof o === "string" ? { valor: o, texto: o } : o; return el("option", { value: op.valor }, op.texto); }));
    entrada.value = valor;
  } else if (tipo === "area") {
    entrada = el("textarea", { id: idc, name: nombre, class: "ui-entrada", rows: filas, placeholder, required: obligatorio, disabled: desactivado, oninput, onchange });
    entrada.value = valor ?? "";
  } else {
    entrada = el("input", { id: idc, name: nombre, class: "ui-entrada", type: TIPOS_ENTRADA[tipo] ?? "text", placeholder, required: obligatorio,
      disabled: desactivado, min, max, step, oninput, onchange });
    entrada.value = valor ?? "";
  }
  const mensaje = el("p", { class: "ui-campo__error", id: idError, role: "alert" }, error);
  mensaje.hidden = !error;
  const raiz = el("div", { class: unir("ui-campo", clase) },
    etiqueta && el("label", { class: "ui-campo__etiqueta", for: idc }, etiqueta, obligatorio && el("span", { class: "ui-campo__oblig", aria: { hidden: "true" } }, " *")),
    tipo === "select" ? el("div", { class: "ui-select" }, entrada, icono("chevron-down", { tam: 16, clase: "ui-select__flecha" })) : entrada,
    ayuda && el("p", { class: "ui-campo__ayuda", id: idAyuda }, ayuda),
    mensaje);
  const describir = () => entrada.setAttribute("aria-describedby", [ayuda && idAyuda, !mensaje.hidden && idError].filter(Boolean).join(" "));
  describir();
  return {
    el: raiz, entrada,
    leer: () => (tipo === "numero" && entrada.value !== "" ? Number(entrada.value) : entrada.value),
    poner: (v) => { entrada.value = v ?? ""; },
    error(texto) {
      mensaje.textContent = texto ?? "";
      mensaje.hidden = !texto;
      entrada.setAttribute("aria-invalid", texto ? "true" : "false");
      describir();
    },
  };
}

/* ------------------------------------------------------------------ estados vacíos y de carga */

export function vacio({ icono: ic = "info", titulo, texto = "", accion = null }) {
  return el("div", { class: "ui-vacio" },
    el("span", { class: "ui-vacio__icono" }, icono(ic, { tam: 22 })),
    el("p", { class: "ui-vacio__titulo" }, titulo),
    texto && el("p", { class: "ui-vacio__texto" }, texto),
    accion && (accion instanceof Node ? accion : boton(accion)));
}

export function esqueleto({ lineas = 3, alto = 14 } = {}) {
  return el("div", { class: "ui-esqueleto", role: "status", aria: { label: "Cargando" } },
    Array.from({ length: lineas }, (_, i) => el("span", { class: "ui-esqueleto__linea", estilo: { height: `${alto}px`, width: `${100 - (i % 3) * 18}%` } })));
}

/* ------------------------------------------------------------------ avisos y diálogos */

let zonaToasts = null;

/** Aviso breve abajo a la derecha. tono: neutro, ok, aviso, critico. Se anuncia a los lectores de pantalla. */
export function toast(texto, tono = "neutro") {
  if (!zonaToasts || !zonaToasts.isConnected) {
    zonaToasts = el("div", { class: "ui-toasts", role: "status", aria: { live: "polite" } });
    (document.getElementById("capas") ?? document.body).append(zonaToasts);
  }
  const nodo = el("div", { class: unir("ui-toast", `ui-toast--${tono}`) },
    el("span", { class: "ui-toast__punto", aria: { hidden: "true" } }), el("span", { class: "ui-toast__texto" }, texto),
    el("button", { type: "button", class: "ui-toast__cerrar", aria: { label: "Cerrar aviso" }, onclick: () => nodo.remove() }, icono("x", { tam: 14 })));
  zonaToasts.append(nodo);
  setTimeout(() => nodo.remove(), tono === "critico" ? 7000 : 4500);
  return nodo;
}

/** Diálogo de confirmación propio (nunca confirm nativo). Devuelve una promesa de booleano. `contenido` admite un nodo extra. */
export function confirmar({ titulo, texto = "", confirmar: etiquetaOk = "Confirmar", cancelar = "Cancelar", tono = "neutro", contenido = null }) {
  return new Promise((resolver) => {
    const idTitulo = uid("dlg");
    const dialogo = el("dialog", { class: "ui-dialogo", aria: { labelledby: idTitulo } });
    const ok = boton({ texto: etiquetaOk, variante: tono === "critico" ? "peligro" : "cta", onclick: () => dialogo.close("ok") });
    const no = boton({ texto: cancelar, variante: "secundario", onclick: () => dialogo.close("no") });
    dialogo.append(
      el("h2", { class: "ui-dialogo__titulo", id: idTitulo }, titulo),
      texto && el("p", { class: "ui-dialogo__texto" }, texto),
      contenido,
      el("div", { class: "ui-dialogo__acciones" }, no, ok));
    dialogo.addEventListener("close", () => { resolver(dialogo.returnValue === "ok"); dialogo.remove(); });
    dialogo.addEventListener("click", (e) => { if (e.target === dialogo) dialogo.close("no"); });
    document.body.append(dialogo);
    dialogo.showModal();
    (tono === "critico" ? no : ok).focus();
  });
}

/* ------------------------------------------------------------------ tablas y pasos */

/**
 * Tabla con cabeceras de columna. columnas: { clave, titulo, ancho, alinear, render(fila) }.
 * Si pasas onfila, las filas son interactivas con teclado. Sin filas pinta el estado vacío.
 */
export function tabla({ columnas, filas, vacio: configVacio = { titulo: "Sin datos" }, onfila = null, etiqueta = "Tabla" }) {
  if (!filas.length) return vacio(configVacio);
  const cabecera = el("thead", null, el("tr", null, columnas.map((c) => el("th", {
    scope: "col", class: c.alinear ? `u-${c.alinear}` : null, estilo: c.ancho ? { width: c.ancho } : null }, c.titulo))));
  const cuerpo = el("tbody", null, filas.map((fila) => el("tr", {
    class: onfila ? "es-interactiva" : null, tabindex: onfila ? 0 : null,
    onclick: onfila ? () => onfila(fila) : null,
    onkeydown: onfila ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onfila(fila); } } : null,
  }, columnas.map((c) => el("td", { class: c.alinear ? `u-${c.alinear}` : null }, c.render ? c.render(fila) : String(fila[c.clave] ?? ""))))));
  return el("div", { class: "ui-tabla-caja" }, el("table", { class: "ui-tabla" }, el("caption", { class: "u-ocultar-visual" }, etiqueta), cabecera, cuerpo));
}

const ETIQUETA_PASO = { hecho: "hecho", actual: "en curso", pendiente: "pendiente", bloqueado: "bloqueado" };

/** Lista vertical de pasos con marcador y conector. estado: hecho, actual, pendiente o bloqueado. Un paso puede llevar `contenido` (un nodo). */
export function pasos(items, { onclick = null } = {}) {
  return el("ol", { class: "ui-pasos" }, items.map((p, i) => el("li", {
    class: unir("ui-paso", `is-${p.estado ?? "pendiente"}`), aria: { current: p.estado === "actual" ? "step" : null } },
  el("span", { class: "ui-paso__marca", aria: { hidden: "true" } }, p.estado === "hecho" ? icono("check", { tam: 14 }) : p.estado === "bloqueado" ? icono("lock", { tam: 13 }) : String(i + 1)),
  el("div", { class: "ui-paso__cuerpo" },
    onclick
      ? el("button", { type: "button", class: "ui-paso__titulo", onclick: () => onclick(p) }, p.titulo)
      : el("span", { class: "ui-paso__titulo" }, p.titulo),
    el("span", { class: "u-ocultar-visual" }, ` (${ETIQUETA_PASO[p.estado ?? "pendiente"]})`),
    p.detalle && el("span", { class: "ui-paso__detalle" }, p.detalle),
    p.contenido))));
}
