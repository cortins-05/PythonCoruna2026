/*
  Núcleo de la aplicación: API, eventos, navegación por hash, menú lateral, barra superior y montaje de secciones.
  Las secciones no importan nada de aquí: reciben un contexto (ctx) con lo que necesitan al montarse. Ver design/CONTRATO.md.
*/
import { SECCIONES, GRUPOS, SECCION_INICIAL } from "./secciones.js";
import { el, vaciar } from "./dom.js";
import * as ui from "./ui.js";

/* ------------------------------------------------------------------ API y eventos */

export class ErrorApi extends Error {
  constructor(status, detalle) {
    super(textoDeDetalle(detalle).join(" "));
    this.status = status;
    this.detalle = detalle;
  }
}

/** Convierte lo que devuelve la API en un error (string, {problemas}, {faltan}, {pendientes}, {conflicto}) en una lista de frases. */
export function textoDeDetalle(detalle) {
  if (detalle == null) return ["Error desconocido"];
  if (typeof detalle === "string") return [detalle];
  if (Array.isArray(detalle)) return detalle.map((d) => (typeof d === "string" ? d : JSON.stringify(d)));
  for (const clave of ["problemas", "faltan", "pendientes"]) if (Array.isArray(detalle[clave])) return detalle[clave].map(String);
  if (Array.isArray(detalle.conflicto)) return detalle.conflicto.map((c) => `${c.tipo} el ${c.fecha}: ${c.ocupadas} ocupadas para ${c.capacidad}`);
  return [typeof detalle.message === "string" ? detalle.message : "No se pudo completar la operación"];
}

const oyentes = new Map();
export const bus = {
  on(evento, fn) {
    if (!oyentes.has(evento)) oyentes.set(evento, new Set());
    oyentes.get(evento).add(fn);
    return () => oyentes.get(evento)?.delete(fn);
  },
  emit(evento, datos) {
    oyentes.get(evento)?.forEach((fn) => { try { fn(datos); } catch (e) { console.error(e); } });
  },
};

let cambiosPendientes = null;
function avisarCambios(info) {
  if (cambiosPendientes) return;
  cambiosPendientes = setTimeout(() => { cambiosPendientes = null; bus.emit("datos-cambiaron", info); }, 40);
}

/** ruta puede ser "/api/bandeja" o "/bandeja". Tras cualquier petición que no sea GET y salga bien se emite datos-cambiaron. */
export async function api(ruta, metodo = "GET", cuerpo) {
  const url = ruta.startsWith("/api/") ? ruta : `/api${ruta.startsWith("/") ? "" : "/"}${ruta}`;
  const opciones = { method: metodo, headers: {} };
  if (cuerpo !== undefined) {
    opciones.headers["content-type"] = "application/json";
    opciones.body = JSON.stringify(cuerpo);
  }
  let respuesta;
  try {
    respuesta = await fetch(url, opciones);
  } catch {
    throw new ErrorApi(0, "No se pudo conectar con el servidor");
  }
  const texto = await respuesta.text();
  let datos = null;
  try { datos = texto ? JSON.parse(texto) : null; } catch { datos = texto; }
  if (!respuesta.ok) throw new ErrorApi(respuesta.status, datos?.detail ?? datos ?? respuesta.statusText);
  if (metodo !== "GET") avisarCambios({ ruta: url, metodo });
  return datos;
}

/* ------------------------------------------------------------------ estado global y tema */

export const estado = { reloj: "", modos: {} };

async function cargarEstado() {
  try {
    const datos = await api("/api/estado");
    const cambioReloj = datos.reloj !== estado.reloj;
    Object.assign(estado, { reloj: datos.reloj, modos: datos });
    if (cambioReloj) bus.emit("reloj-cambio", estado);
    pintarBarra();
  } catch { /* la barra sigue sin reloj */ }
}

const leerTema = () => { try { return localStorage.getItem("tema") || "auto"; } catch { return "auto"; } };
function aplicarTema(tema, persistir = true) {
  if (tema === "auto") delete document.documentElement.dataset.tema;
  else document.documentElement.dataset.tema = tema;
  if (!persistir) return;
  try { localStorage.setItem("tema", tema); } catch { /* sin almacenamiento */ }
}

/* ------------------------------------------------------------------ navegación */

function leerHash() {
  const [ruta, consulta = ""] = location.hash.replace(/^#\/?/, "").split("?");
  return { id: ruta || SECCION_INICIAL, params: Object.fromEntries(new URLSearchParams(consulta)) };
}

export function navegar(id, params = {}) {
  const consulta = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== "")).toString();
  location.hash = `#/${id}${consulta ? `?${consulta}` : ""}`;
}

/* ------------------------------------------------------------------ menú lateral */

const $ = (selector) => document.querySelector(selector);
let insignias = {};

function alternarLateral(abrir) {
  $("#app").classList.toggle("lateral-abierto", abrir);
}

function construirLateral() {
  const lateral = $("#lateral");
  vaciar(lateral);
  lateral.append(el("div", { class: "lateral__marca" },
    el("span", { class: "lateral__logo" }, ui.icono("key", { tam: 20 })),
    el("div", { class: "lateral__nombre" }, el("strong", null, "Uniroom"), el("span", null, "Hotel de demostración"))));
  const nav = el("nav", { class: "lateral__nav", aria: { label: "Secciones" } });
  for (const grupo of GRUPOS) {
    const items = SECCIONES.filter((s) => s.grupo === grupo.id && !s.oculta);
    if (!items.length) continue;
    if (grupo.titulo) nav.append(el("div", { class: "lateral__grupo" }, grupo.titulo));
    nav.append(el("ul", { class: "lateral__lista" }, items.map((s) => el("li", null, el("a", {
      class: "nav-item", href: `#/${s.id}`, dataset: { seccion: s.id }, title: s.titulo, onclick: () => alternarLateral(false),
    }, el("span", { class: "nav-item__icono" }, ui.icono(s.icono, { tam: 16 })), el("span", { class: "nav-item__texto" }, s.titulo))))));
  }
  lateral.append(nav);

  const botonUsuario = ui.boton({ icono: "more-h", variante: "fantasma", tam: "sm", etiqueta: "Preferencias de Flor" });
  const menuUsuario = ui.menuOscuro({
    ancla: botonUsuario, alineacion: "inicio", ancho: 240,
    items: [
      { texto: "Tema claro", icono: "sun", onclick: () => aplicarTema("claro") },
      { texto: "Tema oscuro", icono: "moon", onclick: () => aplicarTema("oscuro") },
      { texto: "Tema del sistema", icono: "panel-left", onclick: () => aplicarTema("auto") },
    ],
  });
  botonUsuario.addEventListener("click", () => menuUsuario.alternar());
  lateral.append(el("div", { class: "lateral__pie" }, ui.avatar("Flor"),
    el("div", { class: "lateral__persona" }, el("strong", null, "Flor"), el("span", null, "Recepción")), botonUsuario));
}

function marcarActivo(id) {
  document.querySelectorAll(".nav-item").forEach((a) => {
    if (a.dataset.seccion === id) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
}

function pintarInsignias(nuevas = {}) {
  insignias = { ...insignias, ...nuevas };
  document.querySelectorAll(".nav-item").forEach((a) => {
    a.querySelector(".ui-insignia")?.remove();
    const n = insignias[a.dataset.seccion];
    if (n > 0) a.append(ui.insignia(n, { tono: a.dataset.seccion === "comunicaciones" ? "aviso" : "neutro" }));
  });
}

async function cargarInsignias() {
  try { pintarInsignias((await api("/api/insignias")).insignias ?? {}); } catch { /* el resumen aún no existe */ }
}

/* ------------------------------------------------------------------ barra superior */

let barraOpciones = { titulo: "" };

function menuGlobal(ancla) {
  const accion = (texto, icono, ruta, ok) => ({
    texto, icono,
    onclick: async () => {
      try { const r = await api(ruta, "POST"); ui.toast(typeof ok === "function" ? ok(r) : ok, "ok"); }
      catch (e) { ui.toast(e.message, "critico"); }
    },
  });
  return ui.menuOscuro({
    ancla,
    items: [
      accion("Leer reservas de RoomCloud", "refresh", "/api/sync/roomcloud", (r) => `RoomCloud leído: ${r?.nuevas ?? 0} reservas nuevas`),
      accion("Leer OfiHotel (solo lectura)", "building", "/api/sync/ofihotel", "OfiHotel leído en solo lectura"),
      { texto: "Avanzar el reloj 6 horas", icono: "clock", onclick: async () => { await api("/api/reloj", "POST", { horas: 6 }); ui.toast("Reloj de la demo adelantado 6 horas", "ok"); } },
      accion("Cargar datos de demostración", "sparkles", "/api/demo/semilla?nivel=completa", "Datos de demostración cargados"),
      { separador: true },
      {
        texto: "Reiniciar los datos", icono: "trash", peligro: true,
        onclick: async () => {
          if (!(await ui.confirmar({ titulo: "Reiniciar los datos de la demo", texto: "Se borran expedientes, mensajes, propuestas y documentos. No se puede deshacer.", confirmar: "Reiniciar", tono: "critico" }))) return;
          await api("/api/reiniciar", "POST");
          ui.toast("Datos reiniciados", "ok");
        },
      },
    ],
  });
}

function pintarBarra() {
  const barra = $("#barra");
  if (!barra) return;
  vaciar(barra);
  const { titulo = "", subtitulo = "", cta = null, acciones = [] } = barraOpciones;
  const botonMas = ui.boton({ icono: "more-h", variante: "fantasma", etiqueta: "Acciones de la demo" });
  const menu = menuGlobal(botonMas);
  botonMas.addEventListener("click", () => menu.alternar());
  const fecha = estado.reloj ? ui.chip({ texto: `Demo · ${ui.fechaHora(estado.reloj)}`, tono: "info", icono: "clock" }) : null;
  barra.append(
    ui.boton({ icono: "menu", variante: "fantasma", etiqueta: "Abrir el menú", clase: "barra__menu-movil", onclick: () => alternarLateral(true) }),
    el("div", { class: "barra__titulos" },
      el("h1", { class: "barra__titulo" }, titulo),
      subtitulo && el("p", { class: "barra__subtitulo" }, subtitulo)),
    el("div", { class: "barra__acciones" },
      fecha,
      acciones.map((a) => ui.boton({ icono: a.icono, texto: a.texto, etiqueta: a.etiqueta ?? a.texto, variante: "fantasma", onclick: a.onclick })),
      botonMas,
      cta && ui.boton({ texto: cta.texto, icono: cta.icono, variante: "cta", onclick: cta.onclick })));
}

/* ------------------------------------------------------------------ montaje de secciones */

let activa = null;
let primeraVez = true;
const hojasCargadas = new Set();

function cargarHojas(nombres = []) {
  for (const nombre of nombres) {
    if (hojasCargadas.has(nombre)) continue;
    hojasCargadas.add(nombre);
    document.head.append(el("link", { rel: "stylesheet", href: `/static/css/secciones/${nombre}.css` }));
  }
}

function crearCtx(def, params, bajas) {
  return {
    api, el, ui, navegar, params, estado,
    suscribir(evento, fn) { const baja = bus.on(evento, fn); bajas.push(baja); return baja; },
    avisar: ui.toast,
    confirmar: ui.confirmar,
    barra(opciones) { barraOpciones = { titulo: def.titulo, ...opciones }; pintarBarra(); },
    insignia(id, n) { pintarInsignias({ [id]: n }); },
    recargarEstado: cargarEstado,
  };
}

async function montar() {
  const { id, params } = leerHash();
  const def = SECCIONES.find((s) => s.id === id) ?? SECCIONES.find((s) => s.id === SECCION_INICIAL);
  if (activa) {
    try { activa.instancia?.destruir?.(); } catch (e) { console.error(e); }
    activa.bajas.forEach((baja) => baja());
  }
  const contenedor = vaciar($("#contenido"));
  const bajas = [];
  activa = { id: def.id, bajas, instancia: null };
  barraOpciones = { titulo: def.titulo };
  pintarBarra();
  marcarActivo(def.id);
  document.title = `${def.titulo} · Recepción`;
  cargarHojas(def.css);
  contenedor.append(ui.esqueleto({ lineas: 4, alto: 16 }));
  try {
    const modulo = await import(def.modulo);
    if (activa.id !== def.id || activa.bajas !== bajas) return;
    vaciar(contenedor);
    activa.instancia = await modulo.default.montar(contenedor, crearCtx(def, params, bajas)) ?? null;
    bus.emit("seccion-activa", def.id);
  } catch (e) {
    console.error(e);
    vaciar(contenedor);
    contenedor.append(ui.vacio({ icono: "alert", titulo: `No se pudo cargar ${def.titulo}`, texto: e.message ?? String(e),
      accion: { texto: "Reintentar", icono: "refresh", onclick: montar } }));
  }
  if (!primeraVez) $("#contenido").focus({ preventScroll: true });
  primeraVez = false;
}

/* ------------------------------------------------------------------ arranque */

function arrancar() {
  // ?tema=claro|oscuro fuerza el tema sin guardarlo, y ?linea=b|c prueba otra línea visual (siempre en claro)
  const consulta = new URLSearchParams(location.search);
  const linea = consulta.get("linea");
  if (linea === "b" || linea === "c") document.documentElement.dataset.linea = linea;
  const forzado = consulta.get("tema") ?? (linea ? "claro" : null);
  if (["claro", "oscuro", "auto"].includes(forzado)) aplicarTema(forzado, false);
  else aplicarTema(leerTema(), false);
  construirLateral();
  $("#saltar").addEventListener("click", () => $("#contenido").focus());
  $("#velo").addEventListener("click", () => alternarLateral(false));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") alternarLateral(false); });
  window.addEventListener("hashchange", montar);
  bus.on("datos-cambiaron", () => { cargarEstado(); cargarInsignias(); });
  bus.on("reloj-cambio", cargarInsignias);
  cargarEstado();
  cargarInsignias();
  montar();
}

arrancar();
