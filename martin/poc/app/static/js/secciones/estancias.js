/*
  Sección "Estancias": el semáforo por sistema. De cada estancia se ve su estado en RoomCloud, OfiHotel y documentación, y el color de lo más urgente.
  La API ya entrega la lista ordenada por urgencia y no se reordena aquí. Datos: /api/estancias, /api/expedientes/{id} y los conflictos que vienen en la lista.
*/
import { chipSemaforo, chipSistema, chipsSistemas, pastillaNivel, tonoDeColor, NOMBRE_COLOR, NOMBRE_FUENTE, NOMBRE_SISTEMA } from "../ui-hotel.js";

const COLORES = ["rojo", "naranja", "amarillo", "azul", "gris", "verde"];
const FILTROS = [{ id: "todas", texto: "Todas" }, { id: "hoy", texto: "Hoy" }, { id: "en_casa", texto: "En casa" }, { id: "salidas", texto: "Salidas" }];
const ICONO_SISTEMA = { roomcloud: "refresh", ofihotel: "building", documentacion: "file" };

export default {
  id: "estancias",
  async montar(contenedor, ctx) {
    const { el, ui } = ctx;
    const { fechaCorta, fechaHora } = ui;

    const estado = {
      filtro: FILTROS.some((f) => f.id === ctx.params.filtro) ? ctx.params.filtro : "todas",
      color: COLORES.includes(ctx.params.color) ? ctx.params.color : "",
      id: ctx.params.id || "",
      datos: null,
      detalle: null,
      errorDetalle: null,
    };
    let peticion = 0;
    let peticionDetalle = 0;
    let vivo = true;

    ctx.barra({ titulo: "Estancias", subtitulo: "Estado de cada estancia en cada sistema", acciones: [{ icono: "refresh", etiqueta: "Actualizar", onclick: () => cargar() }] });

    /* ------------------------------------------------------------ URL */

    const sincronizarUrl = () => {
      const q = new URLSearchParams();
      if (estado.filtro !== "todas") q.set("filtro", estado.filtro);
      if (estado.color) q.set("color", estado.color);
      if (estado.id) q.set("id", estado.id);
      const consulta = q.toString();
      // replaceState no dispara hashchange, así que la sección no se vuelve a montar
      history.replaceState(null, "", `#/estancias${consulta ? `?${consulta}` : ""}`);
    };

    /* ------------------------------------------------------------ esqueleto de la pantalla */

    const banner = el("div", { class: "sec-estancias__banner" });
    const semaforo = el("div", { class: "sec-estancias__semaforo", role: "group", aria: { label: "Filtrar por color del semáforo" } });
    const zonaTabs = el("div", { class: "sec-estancias__tabs" });
    const leyenda = el("details", { class: "sec-estancias__leyenda" });
    const zonaCriticos = el("div", { class: "sec-estancias__criticos", aria: { live: "polite" } });
    const lista = el("div", { class: "sec-estancias__lista", aria: { live: "polite" } });
    const detalle = el("aside", { class: "sec-estancias__detalle", tabindex: "-1", aria: { label: "Detalle de la estancia" }, hidden: true });
    const cuerpo = el("div", { class: "sec-estancias__cuerpo" }, lista, detalle);
    const raiz = el("div", { class: "sec-estancias" }, banner, semaforo, zonaTabs, leyenda, zonaCriticos, cuerpo);
    contenedor.append(raiz);

    const tabs = ui.tabsSubrayado({ items: FILTROS, activo: estado.filtro, etiqueta: "Qué estancias ver", onchange: (id) => { estado.filtro = id; sincronizarUrl(); cargar(); } });
    zonaTabs.append(tabs.el);

    /* ------------------------------------------------------------ carga */

    async function cargar({ silencioso = false } = {}) {
      const mia = ++peticion;
      if (!silencioso || !estado.datos) {
        lista.replaceChildren(ui.esqueleto({ lineas: 5, alto: 18 }));
      }
      try {
        const q = new URLSearchParams({ filtro: estado.filtro });
        if (estado.color) q.set("color", estado.color);
        const datos = await ctx.api(`/api/estancias?${q}`);
        if (!vivo || mia !== peticion) return;
        estado.datos = datos;
        pintarCabecera();
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

    /* ------------------------------------------------------------ cabecera: banner, semáforo, leyenda */

    function pintarCabecera() {
      const d = estado.datos;
      const of = d.datos_ofihotel;
      banner.replaceChildren();
      if (of) {
        const texto = of.disponible
          ? `Datos de OfiHotel hasta ${fechaCorta(of.datos_hasta)} ${ui.hora(of.datos_hasta)}, solo lectura`
          : "OfiHotel no está disponible: se muestran los últimos datos conocidos, solo lectura";
        banner.append(ui.icono("info", { tam: 15 }), el("span", null, texto));
      }

      semaforo.replaceChildren(...COLORES.map((color) => {
        const activo = estado.color === color;
        const n = d.contadores?.[color] ?? 0;
        return el("button", {
          type: "button", class: `sec-estancias__color${activo ? " is-activo" : ""}`, aria: { pressed: String(activo) },
          title: activo ? "Quitar el filtro" : `Ver solo: ${NOMBRE_COLOR[color]}`,
          onclick: () => { estado.color = activo ? "" : color; sincronizarUrl(); cargar(); },
        }, chipSemaforo(color), el("strong", { class: "sec-estancias__cuenta u-tabular" }, String(n)));
      }));

      leyenda.replaceChildren(
        el("summary", null, "Qué significa cada color"),
        el("ul", { class: "sec-estancias__leyenda-lista" }, (d.leyenda ?? []).map((l) => el("li", null, chipSemaforo(l.color, l.titulo), el("span", null, l.descripcion)))));
    }

    /* ------------------------------------------------------------ conflictos */

    const conflictosDe = (id) => (estado.datos?.conflictos ?? []).filter((c) => c.expediente_id === id);

    function pintarCriticos() {
      const ids = new Set((estado.datos.estancias ?? []).map((e) => e.id));
      // Un conflicto sin estancia en la lista (habitación doble, overbooking) no tendría dónde verse
      const sueltos = (estado.datos.conflictos ?? []).filter((c) => !c.expediente_id || !ids.has(c.expediente_id) && c.nivel === "rojo");
      zonaCriticos.replaceChildren();
      if (!sueltos.length) return;
      zonaCriticos.append(ui.panel({
        titulo: "Conflictos sin estancia asignada", subtitulo: "Hay que resolverlos antes del próximo check-in", variante: "suave", clase: "sec-estancias__panel-critico",
        acciones: [ui.chip({ texto: String(sueltos.length), tono: "critico", punto: true })],
        hijos: [el("ul", { class: "sec-estancias__conflictos" }, sueltos.map((c) => el("li", null,
          ui.icono("alert", { tam: 16 }), el("span", null, c.texto),
          c.expediente_id && ui.boton({ texto: "Abrir estancia", tam: "sm", onclick: () => abrir(c.expediente_id) }))))],
      }));
    }

    /* ------------------------------------------------------------ lista */

    function pintarLista() {
      const estancias = estado.datos.estancias ?? [];
      if (!estancias.length) {
        const filtrando = estado.color || estado.filtro !== "todas";
        lista.replaceChildren(ui.vacio({
          icono: "bed", titulo: filtrando ? "Ninguna estancia coincide con el filtro" : "No hay estancias todavía",
          texto: filtrando ? "Quita el color o cambia de pestaña para ver el resto." : "Las estancias aparecen cuando se lee RoomCloud.",
          accion: filtrando ? { texto: "Quitar los filtros", icono: "x", onclick: () => { estado.color = ""; estado.filtro = "todas"; tabs.set("todas"); sincronizarUrl(); cargar(); } } : null,
        }));
        return;
      }
      lista.replaceChildren(el("ul", { class: "sec-estancias__filas", "aria-label": "Estancias, de más a menos urgente" }, estancias.map(fila)));
    }

    function fila(e) {
      const propios = conflictosDe(e.id).filter((c) => c.texto !== e.semaforo.motivo);
      const seleccionada = e.id === estado.id;
      return el("li", null, el("button", {
        type: "button", class: `sec-estancias__fila tono-${tonoDeColor(e.semaforo.color)}${seleccionada ? " is-seleccionada" : ""}`,
        dataset: { id: e.id }, aria: { current: seleccionada ? "true" : null }, onclick: () => abrir(e.id),
      },
      el("span", { class: "sec-estancias__fila-cabeza" },
        el("strong", { class: "sec-estancias__nombre" }, e.huesped),
        pastillaNivel(e.prioridad, { compacta: true }),
        el("span", { class: "sec-estancias__fila-semaforo" }, chipSemaforo(e.semaforo.color))),
      el("span", { class: "sec-estancias__fila-datos" },
        el("span", null, `${fechaCorta(e.checkin)} a ${fechaCorta(e.checkout)}`),
        el("span", null, e.tipo),
        el("span", null, NOMBRE_FUENTE[e.origen] ?? e.origen)),
      el("span", { class: "sec-estancias__motivo" }, e.semaforo.motivo),
      propios.map((c) => el("span", { class: "sec-estancias__motivo is-conflicto" }, ui.icono("alert", { tam: 13 }), c.texto)),
      chipsSistemas(e.sistemas)));
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
      const volver = ui.boton({ texto: "Volver", icono: "arrow-left", tam: "sm", variante: "secundario", onclick: cerrar });
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

      const cabecera = el("header", { class: "sec-estancias__det-cabecera" },
        volver,
        el("h2", { class: "sec-estancias__det-nombre" }, nombre),
        ui.kv([
          { etiqueta: "Fechas", valor: `${fechaCorta(exp.checkin_prevista)} a ${fechaCorta(exp.checkout_prevista)}` },
          { etiqueta: "Tipo", valor: exp.tipo ?? "Sin tipo" },
          { etiqueta: "Personas", valor: String(exp.personas ?? "") },
          { etiqueta: "Origen", valor: el("span", { class: "sec-estancias__origen" }, NOMBRE_FUENTE[exp.origen] ?? exp.origen, item && pastillaNivel(item.prioridad)) },
        ], { columnas: 2 }));

      const grande = el("section", { class: `sec-estancias__grande tono-${tonoDeColor(sem.color)}`, aria: { label: "Semáforo de la estancia" } },
        chipSemaforo(sem.color),
        el("p", { class: "sec-estancias__grande-motivo" }, sem.motivo),
        sem.accion_sugerida && el("p", { class: "sec-estancias__grande-accion" }, ui.icono("arrow-right", { tam: 15 }), el("span", null, "Acción sugerida: ", el("strong", null, sem.accion_sugerida))));

      const tarjetas = el("div", { class: "sec-estancias__sistemas" }, Object.keys(NOMBRE_SISTEMA).map((s) => {
        const sis = exp.sistemas[s];
        return el("div", { class: "sec-estancias__sistema" },
          el("h4", null, ui.icono(ICONO_SISTEMA[s], { tam: 16 }), NOMBRE_SISTEMA[s]),
          chipSistema(s, sis.estado, { conNombre: false }),
          el("p", null, sis.detalle),
          s === "ofihotel" && of.habitacion && el("p", { class: "sec-estancias__habitacion" }, `Habitación ${of.habitacion}`, of.inferida ? " (inferida)" : ""));
      }));

      const bloques = [cabecera, grande,
        el("section", { class: "sec-estancias__seccion" }, el("h3", null, "Estado en cada sistema"), tarjetas)];

      const confl = exp.conflictos ?? [];
      if (confl.length) bloques.push(el("section", { class: "sec-estancias__seccion" }, el("h3", null, "Conflictos"), ...confl.map(conflicto)));

      bloques.push(el("section", { class: "sec-estancias__seccion" }, el("h3", null, "Registro"), registro(exp.registro ?? [])));

      const acciones = el("div", { class: "sec-estancias__acciones" },
        of.estado === "por_migrar" && ui.boton({ texto: "Marcar como pasada a OfiHotel", icono: "check", variante: "oscuro", onclick: (ev) => marcar(exp, nombre, ev.currentTarget) }),
        ui.boton({ texto: "Preguntar al asistente", icono: "sparkles", onclick: () => ctx.navegar("asistente", { q: `Cuéntame el estado de la estancia de ${nombre}` }) }));
      bloques.push(acciones);

      detalle.replaceChildren(...bloques);
    }

    // "RoomCloud dice del 24/10 al 27/10 y OfiHotel del 24/10 al 26/10" a dos columnas
    const RE_FECHAS = /RoomCloud dice del (\d{1,2}\/\d{1,2}) al (\d{1,2}\/\d{1,2}) y OfiHotel del (\d{1,2}\/\d{1,2}) al (\d{1,2}\/\d{1,2})/;
    const corto = (dm) => { const [d, m] = dm.split("/").map(Number); return `${d} ${["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"][m - 1]}`; };

    function conflicto(c) {
      const m = RE_FECHAS.exec(c.texto);
      if (c.tipo === "fechas_distintas" && m) {
        const lado = (sistema, desde, hasta) => el("div", { class: "sec-estancias__lado" },
          el("span", { class: "sec-estancias__lado-sistema" }, ui.icono(ICONO_SISTEMA[sistema], { tam: 14 }), `${NOMBRE_SISTEMA[sistema]} dice`),
          el("strong", null, `${corto(desde)} al ${corto(hasta)}`));
        return el("div", { class: "sec-estancias__comparacion" }, lado("roomcloud", m[1], m[2]), lado("ofihotel", m[3], m[4]));
      }
      return el("p", { class: "sec-estancias__conflicto-texto" }, ui.icono("alert", { tam: 15 }), el("span", null, c.texto));
    }

    function registro(entradas) {
      if (!entradas.length) return el("p", { class: "sec-estancias__nada" }, "Todavía no hay actividad registrada.");
      return el("ol", { class: "sec-estancias__registro" }, [...entradas].reverse().map((r) => el("li", null,
        el("span", { class: "sec-estancias__registro-hora u-tabular" }, fechaHora(r.hora)),
        el("span", null, el("strong", null, r.actor), ` · ${r.accion}`))));
    }

    async function marcar(exp, nombre, boton) {
      const ok = await ctx.confirmar({
        titulo: "Marcar como pasada a OfiHotel",
        texto: `OfiHotel es de solo lectura, así que esto solo marca la estancia de ${nombre} como pasada dentro de la aplicación. La lectura de mañana confirmará si OfiHotel la tiene.`,
        confirmar: "Sí, marcar como pasada", cancelar: "Cancelar",
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
