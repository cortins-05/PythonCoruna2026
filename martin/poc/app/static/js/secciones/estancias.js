/*
  Sección "Estancias": una tabla con el estado de cada estancia en RoomCloud, OfiHotel y documentación. Solo la fila con problema lleva color.
  La API ya entrega la lista ordenada por urgencia y no se reordena aquí. Datos: /api/estancias y /api/expedientes/{id}.
*/
import { NOMBRE_FUENTE, NOMBRE_SISTEMA } from "../ui-hotel.js";

const FILTROS = [{ id: "todas", texto: "Todas" }, { id: "hoy", texto: "Hoy" }, { id: "en_casa", texto: "En casa" }, { id: "salidas", texto: "Salidas" }];
const PROBLEMA = new Set(["rojo", "naranja", "amarillo"]);
// Una palabra por sistema; la celda con problema se marca aparte
const PALABRA = {
  roomcloud: { sincronizado: "Al día", cancelada: "Cancelada", no_aplica: "-" },
  ofihotel: { migrado: "Migrada", marcado: "Marcada", por_migrar: "Por migrar", sin_lectura: "Sin lectura", no_aplica: "-" },
  documentacion: { parte_enviado: "Enviado", parte_pendiente: "Pendiente", parte_vencido: "Vencido", incompleta: "Incompleta", sin_datos: "Sin datos", no_aplica: "-" },
};
const MALO = new Set(["parte_vencido", "parte_pendiente", "incompleta", "por_migrar"]);

export default {
  id: "estancias",
  async montar(contenedor, ctx) {
    const { el, ui } = ctx;
    const { fechaCorta, fechaHora } = ui;

    const estado = {
      filtro: FILTROS.some((f) => f.id === ctx.params.filtro) ? ctx.params.filtro : "todas",
      id: ctx.params.id || "",
      datos: null,
      detalle: null,
      errorDetalle: null,
    };
    let peticion = 0;
    let peticionDetalle = 0;
    let vivo = true;

    ctx.barra({ titulo: "Estancias", acciones: [{ icono: "refresh", etiqueta: "Actualizar", onclick: () => cargar() }] });

    const sincronizarUrl = () => {
      const q = new URLSearchParams();
      if (estado.filtro !== "todas") q.set("filtro", estado.filtro);
      if (estado.id) q.set("id", estado.id);
      const consulta = q.toString();
      // replaceState no dispara hashchange, así que la sección no se vuelve a montar
      history.replaceState(null, "", `#/estancias${consulta ? `?${consulta}` : ""}`);
    };

    const banner = el("div", { class: "sec-estancias__banner" });
    const zonaTabs = el("div", { class: "sec-estancias__tabs" });
    const zonaCriticos = el("div", { class: "sec-estancias__criticos", aria: { live: "polite" } });
    const lista = el("div", { class: "sec-estancias__lista", aria: { live: "polite" } });
    const detalle = el("aside", { class: "sec-estancias__detalle", tabindex: "-1", aria: { label: "Detalle de la estancia" }, hidden: true });
    const cuerpo = el("div", { class: "sec-estancias__cuerpo" }, lista, detalle);
    const raiz = el("div", { class: "sec-estancias" }, banner, zonaTabs, zonaCriticos, cuerpo);
    contenedor.append(raiz);

    const tabs = ui.tabsSubrayado({ items: FILTROS, activo: estado.filtro, etiqueta: "Qué estancias ver", onchange: (id) => { estado.filtro = id; sincronizarUrl(); cargar(); } });
    zonaTabs.append(tabs.el);

    async function cargar({ silencioso = false } = {}) {
      const mia = ++peticion;
      if (!silencioso || !estado.datos) {
        lista.replaceChildren(ui.esqueleto({ lineas: 5, alto: 18 }));
      }
      try {
        const datos = await ctx.api(`/api/estancias?${new URLSearchParams({ filtro: estado.filtro })}`);
        if (!vivo || mia !== peticion) return;
        estado.datos = datos;
        pintarBanner();
        pintarCriticos();
        pintarLista();
      } catch (e) {
        if (!vivo || mia !== peticion) return;
        lista.replaceChildren(ui.vacio({ icono: "alert", titulo: "No se pudieron cargar las estancias", texto: e.message ?? String(e),
          accion: { texto: "Reintentar", icono: "refresh", onclick: () => cargar() } }));
      }
      if (estado.id) cargarDetalle();
      else pintarDetalle();
    }

    async function cargarDetalle() {
      const mia = ++peticionDetalle;
      estado.errorDetalle = null;
      if (!estado.detalle || estado.detalle.id !== estado.id) {
        estado.detalle = null;
        detalle.hidden = false;
        detalle.replaceChildren(ui.esqueleto({ lineas: 6, alto: 18 }));
      }
      try {
        const exp = await ctx.api(`/api/expedientes/${encodeURIComponent(estado.id)}`);
        if (!vivo || mia !== peticionDetalle) return;
        estado.detalle = exp;
      } catch (e) {
        if (!vivo || mia !== peticionDetalle) return;
        estado.detalle = null;
        estado.errorDetalle = e.message ?? String(e);
      }
      pintarDetalle();
    }

    function pintarBanner() {
      const of = estado.datos.datos_ofihotel;
      banner.replaceChildren();
      if (!of) return;
      banner.append(of.disponible
        ? `Datos de OfiHotel hasta ${fechaCorta(of.datos_hasta)} ${ui.hora(of.datos_hasta)}`
        : "OfiHotel no está disponible, se muestran los últimos datos conocidos");
    }

    const conflictosDe = (id) => (estado.datos?.conflictos ?? []).filter((c) => c.expediente_id === id);

    function pintarCriticos() {
      const ids = new Set((estado.datos.estancias ?? []).map((e) => e.id));
      // Un conflicto sin estancia en la lista (habitación doble, overbooking) no tendría dónde verse
      const sueltos = (estado.datos.conflictos ?? []).filter((c) => !c.expediente_id || !ids.has(c.expediente_id) && c.nivel === "rojo");
      zonaCriticos.replaceChildren();
      if (!sueltos.length) return;
      zonaCriticos.append(el("ul", { class: "sec-estancias__conflictos" }, sueltos.map((c) => el("li", null,
        el("span", null, c.texto),
        c.expediente_id && ui.boton({ texto: "Abrir estancia", tam: "sm", variante: "fantasma", onclick: () => abrir(c.expediente_id) })))));
    }

    /* ------------------------------------------------------------ tabla */

    function pintarLista() {
      const estancias = estado.datos.estancias ?? [];
      if (!estancias.length) {
        const filtrando = estado.filtro !== "todas";
        lista.replaceChildren(ui.vacio({
          icono: "bed", titulo: filtrando ? "Ninguna estancia coincide con el filtro" : "No hay estancias todavía",
          accion: filtrando ? { texto: "Ver todas", icono: "x", onclick: () => { estado.filtro = "todas"; tabs.set("todas"); sincronizarUrl(); cargar(); } } : null,
        }));
        return;
      }
      const cabecera = el("tr", null, ["Huésped", "Fechas", "Tipo", "RoomCloud", "OfiHotel", "Documentación", "Problema"].map((t) => el("th", { scope: "col" }, t)));
      const tabla = el("table", { class: "sec-estancias__tabla" },
        el("caption", { class: "u-ocultar-visual" }, "Estancias, de más a menos urgente"),
        el("thead", null, cabecera),
        el("tbody", null, estancias.map(fila)));
      lista.replaceChildren(el("div", { class: "sec-estancias__caja" }, tabla));
    }

    function celda(sistema, sis) {
      const clave = sis.estado;
      return el("td", { class: MALO.has(clave) ? "is-malo" : "" }, PALABRA[sistema]?.[clave] ?? clave);
    }

    function fila(e) {
      const seleccionada = e.id === estado.id;
      const propios = conflictosDe(e.id).filter((c) => c.texto !== e.semaforo.motivo);
      const hayProblema = PROBLEMA.has(e.semaforo.color) || propios.length > 0;
      const todos = conflictosDe(e.id);
      const corto = (txt) => (todos.some((c) => c.tipo === "fechas_distintas" && c.texto === txt) ? "Fechas distintas entre RoomCloud y OfiHotel" : txt);
      const problema = [hayProblema ? corto(e.semaforo.motivo) : "", ...propios.map((c) => corto(c.texto))].filter(Boolean).join(". ");
      return el("tr", {
        class: `${hayProblema ? "is-problema" : ""}${seleccionada ? " is-seleccionada" : ""}`, tabindex: "0", dataset: { id: e.id },
        aria: { current: seleccionada ? "true" : null },
        onclick: () => abrir(e.id),
        onkeydown: (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); abrir(e.id); } },
      },
      el("th", { scope: "row" }, e.huesped),
      el("td", { class: "u-tabular" }, `${fechaCorta(e.checkin)} a ${fechaCorta(e.checkout)}`),
      el("td", null, e.tipo),
      ...Object.keys(NOMBRE_SISTEMA).map((s) => celda(s, e.sistemas[s])),
      el("td", { class: "sec-estancias__problema", title: problema }, problema));
    }

    /* ------------------------------------------------------------ detalle */

    function abrir(id) {
      estado.id = id;
      sincronizarUrl();
      pintarLista();
      detalle.hidden = false;
      cargarDetalle().then(() => detalle.focus({ preventScroll: true }));
    }

    function cerrar() {
      const id = estado.id;
      estado.id = "";
      estado.detalle = null;
      sincronizarUrl();
      pintarDetalle();
      pintarLista();
      lista.querySelector(`[data-id="${CSS.escape(id)}"]`)?.focus();
    }

    function pintarDetalle() {
      raiz.classList.toggle("con-detalle", Boolean(estado.id));
      if (!estado.id) { detalle.hidden = true; detalle.replaceChildren(); return; }
      detalle.hidden = false;
      const volver = ui.boton({ texto: "Cerrar", icono: "arrow-left", tam: "sm", variante: "fantasma", onclick: cerrar });
      volver.classList.add("sec-estancias__volver");
      if (estado.errorDetalle) {
        detalle.replaceChildren(volver, ui.vacio({ icono: "alert", titulo: "No se pudo abrir la estancia", texto: estado.errorDetalle,
          accion: { texto: "Reintentar", icono: "refresh", onclick: () => cargarDetalle() } }));
        return;
      }
      const exp = estado.detalle;
      if (!exp) return;
      const item = (estado.datos?.estancias ?? []).find((x) => x.id === exp.id);
      const nombre = item?.huesped ?? [exp.reserva?.nombre, exp.reserva?.apellidos].filter(Boolean).join(" ") ?? exp.id;
      const sem = exp.semaforo;
      const of = exp.sistemas.ofihotel;
      const pendiente = of.estado === "por_migrar";

      const cabecera = el("header", { class: "sec-estancias__det-cabecera" },
        volver,
        el("h2", { class: "sec-estancias__det-nombre" }, nombre),
        el("p", { class: "sec-estancias__det-datos" },
          `${fechaCorta(exp.checkin_prevista)} a ${fechaCorta(exp.checkout_prevista)}`, exp.tipo ? ` · ${exp.tipo}` : "",
          exp.personas ? ` · ${exp.personas} pers.` : "", ` · ${NOMBRE_FUENTE[exp.origen] ?? exp.origen}`));

      const bloques = [cabecera];
      const confl = (exp.conflictos ?? []).filter((c) => c.texto !== sem.motivo);
      if (PROBLEMA.has(sem.color)) {
        bloques.push(el("p", { class: "sec-estancias__aviso" }, el("strong", null, sem.motivo), sem.accion_sugerida ? ` ${sem.accion_sugerida}` : ""));
      }

      bloques.push(el("dl", { class: "sec-estancias__sistemas" }, Object.keys(NOMBRE_SISTEMA).flatMap((s) => {
        const sis = exp.sistemas[s];
        const hab = s === "ofihotel" && of.habitacion && !/hab\./.test(sis.detalle ?? "") ?` Habitación ${of.habitacion}${of.inferida ? " (inferida)" : ""}.` : "";
        return [el("dt", null, NOMBRE_SISTEMA[s]), el("dd", null, `${sis.detalle}${hab}`)];
      })));

      for (const c of confl) bloques.push(el("p", { class: "sec-estancias__conflicto-texto" }, c.texto));

      const reg = [...(exp.registro ?? [])].reverse().slice(0, 4);
      if (reg.length) {
        bloques.push(el("ul", { class: "sec-estancias__registro" }, reg.map((r) => el("li", null,
          el("span", { class: "u-tabular" }, fechaHora(r.hora)), ` ${r.actor}, ${r.accion}`))));
      }

      bloques.push(el("div", { class: "sec-estancias__acciones" },
        pendiente && ui.boton({ texto: "Marcar como pasada a OfiHotel", variante: "cta", onclick: (ev) => marcar(exp, nombre, ev.currentTarget) }),
        ui.boton({ texto: "Preguntar al asistente", variante: pendiente ? "fantasma" : "cta", onclick: () => ctx.navegar("asistente", { q: `Cuéntame el estado de la estancia de ${nombre}` }) })));

      detalle.replaceChildren(...bloques);
    }

    async function marcar(exp, nombre, boton) {
      const ok = await ctx.confirmar({
        titulo: "Marcar como pasada a OfiHotel",
        texto: `OfiHotel es de solo lectura, así que esto solo marca la estancia de ${nombre} como pasada dentro de la aplicación. La lectura de mañana confirmará si OfiHotel la tiene.`,
        confirmar: "Marcar como pasada", cancelar: "Cancelar",
        contenido: document.createDocumentFragment(), // ui.confirmar hace append(null) y pinta "null" si no recibe nodo
      });
      if (!ok) return;
      boton.disabled = true;
      try {
        await ctx.api(`/api/expedientes/${encodeURIComponent(exp.id)}/tramites/ofihotel_alta`, "POST", { actor: "Flor" });
        ctx.avisar("Estancia marcada como pasada a OfiHotel", "ok");
      } catch (e) {
        boton.disabled = false;
        ctx.avisar(e.message ?? "No se pudo marcar la estancia", "critico");
      }
    }

    /* ------------------------------------------------------------ vida de la sección */

    const baja = ctx.suscribir("datos-cambiaron", () => cargar({ silencioso: true }));
    cargar();
    return { destruir() { vivo = false; baja(); } };
  },
};
