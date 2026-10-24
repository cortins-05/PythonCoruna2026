/*
  Sección "Ocupación": lo que ocupa cada fuente cada noche y qué peticiones compiten por lo que queda.
  Datos: GET /api/ocupacion?dias=14 y GET /api/propuestas?estado=pendiente (solo cerrar_disponibilidad).
*/
import { chipVeredicto, pastillaNivel, ICONO_FUENTE, NOMBRE_FUENTE } from "../ui-hotel.js";

const FUENTES = ["roomcloud", "ofihotel", "recepcion"];
const DIAS_SEMANA = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];
const DIAS_LARGOS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
const NOMBRE_TIPO = { "DBL-STD": "Doble estándar", "SGL-STD": "Individual estándar" };

const diaSemana = (iso, lista = DIAS_SEMANA) => lista[new Date(`${iso}T12:00:00`).getDay()];
const numeroDia = (iso) => Number(iso.slice(8, 10));
const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;
const primerNombre = (nombre) => String(nombre ?? "").split(" ")[0];
/** Una petición ocupa las noches desde `desde` hasta el día anterior a `hasta` (la salida). */
const tocaNoche = (p, tipo, fecha) => p.tipo_habitacion === tipo && p.desde <= fecha && fecha < p.hasta;

export default {
  id: "ocupacion",
  async montar(contenedor, ctx) {
    const { el, ui } = ctx;
    const raiz = el("div", { class: "sec-ocupacion" });
    contenedor.append(raiz);

    let datos = null;
    let propuestas = [];
    let seleccion = null; // { tipo, fecha }
    let ocupado = false;

    async function simular() {
      if (ocupado) return;
      ocupado = true;
      try {
        await ctx.api("/api/demo/reserva-roomcloud", "POST", { tipo: "SGL-STD" });
        ctx.avisar("Entra una reserva simulada de Booking en SGL-STD. Las casillas y las peticiones se han actualizado.", "ok");
      } catch (e) {
        ctx.avisar(e.message || "No se ha podido simular la reserva.", "critico");
      } finally { ocupado = false; }
    }

    ctx.barra({
      titulo: "Ocupación", subtitulo: "Lo que ocupa cada fuente, noche a noche",
      cta: { texto: "Simular reserva de Booking", icono: "plus", onclick: simular },
      acciones: [{ icono: "refresh", etiqueta: "Actualizar", onclick: () => cargar() }],
    });

    /* ------------------------------------------------------------ piezas */

    const prioridadDe = (id) => {
      const f = datos?.fuentes?.find((x) => x.id === id);
      return f ? { nivel: f.nivel, fuente: f.nombre, id: f.id, tipo: f.tipo } : { nivel: 0, fuente: NOMBRE_FUENTE[id] ?? id, id, tipo: "firme" };
    };

    function leyenda() {
      return ui.panel({
        titulo: "Fuentes", variante: "suave",
        hijos: [
          el("ul", { class: "oc__leyenda" }, FUENTES.map((id) => el("li", { class: "oc__leyenda-item" },
            el("span", { class: `oc__muestra oc__seg--${id}`, aria: { hidden: "true" } }),
            ui.icono(ICONO_FUENTE[id], { tam: 14 }),
            el("strong", null, NOMBRE_FUENTE[id]),
            pastillaNivel(prioridadDe(id), { compacta: true })))),
          el("p", { class: "oc__nota" }, "Lo firme (niveles 1 a 3) bloquea la habitación; una petición solo ocupa lo que queda libre."),
          el("p", { class: "oc__nota" }, el("span", { class: "oc__muestra-pet", aria: { hidden: "true" } }), " El contorno discontinuo marca las noches que ocuparía una petición pendiente."),
        ],
      });
    }

    function barraSegmentada(dia, capacidad) {
      const total = Math.max(capacidad, dia.ocupadas, 1);
      return el("span", { class: "oc__barra", aria: { hidden: "true" } },
        FUENTES.filter((f) => dia.por_fuente[f] > 0).map((f) =>
          el("span", { class: `oc__seg oc__seg--${f}`, estilo: { width: `${(dia.por_fuente[f] / total) * 100}%` } })));
    }

    function estadoDia(dia, capacidad) {
      if (dia.ocupadas > capacidad) return "overbooking";
      if (dia.libres <= 0) return "completo";
      return "libre";
    }

    function celda(tipo, capacidad, dia) {
      const pets = datos.peticiones.filter((p) => tocaNoche(p, tipo, dia.fecha));
      const est = estadoDia(dia, capacidad);
      const activa = seleccion?.tipo === tipo && seleccion?.fecha === dia.fecha;
      const desglose = FUENTES.map((f) => `${NOMBRE_FUENTE[f]} ${dia.por_fuente[f]}`).join(", ");
      const etiqueta = `${NOMBRE_TIPO[tipo] ?? tipo}, ${diaSemana(dia.fecha, DIAS_LARGOS)} ${numeroDia(dia.fecha)}: ${dia.ocupadas} de ${capacidad} ocupadas (${desglose})`
        + `${est === "completo" ? ", completo" : est === "overbooking" ? ", overbooking" : ""}${dia.cerrado_en_roomcloud ? ", cerrado en RoomCloud" : ""}`
        + `${pets.length ? `, ${plural(pets.length, "petición pendiente", "peticiones pendientes")}` : ""}`;
      const boton = el("button", {
        type: "button", class: `oc__celda oc__celda--${est}${pets.length ? " tiene-peticion" : ""}${activa ? " is-activa" : ""}`,
        dataset: { tipo, fecha: dia.fecha }, aria: { pressed: String(activa), label: etiqueta },
        onclick: () => elegir(tipo, dia.fecha),
        onkeydown: (e) => moverFoco(e, boton),
      },
      el("span", { class: "oc__cifra" }, el("strong", null, String(dia.ocupadas)), `/${capacidad}`),
      barraSegmentada(dia, capacidad),
      el("span", { class: "oc__marcas" },
        est === "overbooking" && el("span", { class: "oc__marca oc__marca--critico" }, ui.icono("alert", { tam: 11 }), "Overbooking"),
        est === "completo" && el("span", { class: "oc__marca oc__marca--aviso" }, ui.icono("lock", { tam: 11 }), "Completo"),
        dia.cerrado_en_roomcloud && el("span", { class: "oc__marca oc__marca--info" }, ui.icono("x", { tam: 11 }), "Cerrado")),
      pets.length > 0 && el("span", { class: "oc__pets" }, pets.slice(0, 2).map((p) => el("span", { class: "oc__pet", title: `${p.de}, ${NOMBRE_FUENTE[p.canal] ?? p.canal}` },
        ui.icono(ICONO_FUENTE[p.canal] ?? "dot", { tam: 11 }), el("span", null, primerNombre(p.de)))),
      pets.length > 2 && el("span", { class: "oc__pet oc__pet--mas" }, `+${pets.length - 2}`)));
      return el("td", { class: "oc__td" }, boton);
    }

    function moverFoco(e, actual) {
      const delta = { ArrowRight: [0, 1], ArrowLeft: [0, -1], ArrowDown: [1, 0], ArrowUp: [-1, 0] }[e.key];
      if (!delta) return;
      const tabla = actual.closest("table");
      const filas = [...tabla.querySelectorAll("tbody tr")];
      const f = filas.findIndex((tr) => tr.contains(actual));
      const botones = [...filas[f].querySelectorAll(".oc__celda")];
      const c = botones.indexOf(actual);
      const destino = filas[f + delta[0]]?.querySelectorAll(".oc__celda")[c + delta[1]];
      const fin = delta[0] === 0 ? botones[c + delta[1]] : destino;
      if (fin) { e.preventDefault(); fin.focus(); }
    }

    function rejilla() {
      const { fechas, tipos } = datos.mapa;
      const cabecera = el("thead", null, el("tr", null,
        el("th", { scope: "col", class: "oc__th-tipo" }, "Habitación"),
        fechas.map((f) => el("th", { scope: "col", class: `oc__th-dia${[0, 6].includes(new Date(`${f}T12:00:00`).getDay()) ? " es-finde" : ""}` },
          el("span", { class: "oc__dia-semana" }, diaSemana(f)), el("span", { class: "oc__dia-num" }, ui.fechaCorta(f))))));
      const cuerpo = el("tbody", null, Object.entries(tipos).map(([tipo, info]) => el("tr", null,
        el("th", { scope: "row", class: "oc__th-tipo" }, el("strong", null, tipo), el("span", null, plural(info.capacidad, "habitación", "habitaciones"))),
        info.dias.map((dia) => celda(tipo, info.capacidad, dia)))));
      return el("div", { class: "oc__scroll", role: "region", tabindex: "0", aria: { label: "Rejilla de ocupación, se desplaza en horizontal" } },
        el("table", { class: "oc__tabla" },
          el("caption", { class: "oc__caption" }, `Habitaciones ocupadas sobre capacidad, por tipo y noche, durante los próximos ${datos.dias} días`),
          el("colgroup", null, el("col", { class: "oc__col-tipo" }), fechas.map(() => el("col", { class: "oc__col-dia" }))),
          cabecera, cuerpo));
    }

    function detalle() {
      if (!seleccion) {
        return el("p", { class: "oc__detalle-vacio" }, "Elige una casilla para ver el desglose de esa noche y las peticiones que la tocan.");
      }
      const { tipo, fecha } = seleccion;
      const info = datos.mapa.tipos[tipo];
      const dia = info?.dias.find((d) => d.fecha === fecha);
      if (!dia) return el("p", { class: "oc__detalle-vacio" }, "Esa noche ya no está en la rejilla.");
      const pets = datos.peticiones.filter((p) => tocaNoche(p, tipo, fecha));
      const est = estadoDia(dia, info.capacidad);
      return el("div", { class: "oc__detalle", id: "oc-detalle", tabindex: "-1" },
        el("div", { class: "oc__detalle-cab" },
          el("h3", null, `${tipo}, ${diaSemana(fecha, DIAS_LARGOS)} ${ui.fechaCorta(fecha)}`),
          ui.chip({ texto: `${dia.ocupadas} de ${info.capacidad} ocupadas`, tono: est === "libre" ? "ok" : est === "completo" ? "aviso" : "critico", punto: true }),
          est === "overbooking" && ui.chip({ texto: "Overbooking", tono: "critico", icono: "alert" }),
          est === "completo" && ui.chip({ texto: "Completo", tono: "aviso", icono: "lock" }),
          dia.cerrado_en_roomcloud && ui.chip({ texto: "Cerrado en RoomCloud", tono: "info", icono: "x" })),
        el("ul", { class: "oc__desglose", "aria-label": "Desglose por fuente" }, FUENTES.map((f) => el("li", { class: "oc__desglose-fila" },
          el("span", { class: `oc__muestra oc__seg--${f}`, aria: { hidden: "true" } }),
          el("span", { class: "oc__desglose-nombre" }, ui.icono(ICONO_FUENTE[f], { tam: 14 }), NOMBRE_FUENTE[f]),
          pastillaNivel(prioridadDe(f), { compacta: true }),
          el("strong", { class: "oc__desglose-n" }, plural(dia.por_fuente[f], "habitación", "habitaciones"))))),
        el("p", { class: "oc__nota" }, dia.libres > 0
          ? `Quedan ${plural(dia.libres, "habitación libre", "habitaciones libres")} para las peticiones.`
          : "No queda ninguna habitación libre, así que ninguna petición cabe esta noche."),
        pets.length > 0
          ? el("div", null, el("h4", { class: "oc__subtitulo" }, "Peticiones que tocan esta noche"), el("ul", { class: "oc__lista" }, pets.map(filaPeticion)))
          : el("p", { class: "oc__nota" }, "Ninguna petición pendiente toca esta noche."));
    }

    function filaPeticion(p) {
      return el("li", { class: "oc__peticion" },
        el("div", { class: "oc__peticion-info" },
          el("strong", null, p.de),
          el("span", { class: "oc__peticion-datos" }, ui.icono(ICONO_FUENTE[p.canal] ?? "dot", { tam: 13 }),
            `${NOMBRE_FUENTE[p.canal] ?? p.canal}, ${p.hora} · ${p.tipo_habitacion} · ${plural(p.habitaciones, "habitación", "habitaciones")} · ${ui.fechaCorta(p.desde)} a ${ui.fechaCorta(p.hasta)}`)),
        el("div", { class: "oc__peticion-estado" }, chipVeredicto(p.veredicto), pastillaNivel(p.prioridad)),
        ui.boton({ texto: "Abrir", icono: "inbox", tam: "sm", etiqueta: `Abrir la petición de ${p.de}`, onclick: () => ctx.navegar("comunicaciones", { id: p.id }) }));
    }

    function panelPeticiones() {
      return ui.panel({
        titulo: "Peticiones que compiten", subtitulo: "Correo y WhatsApp pendientes de confirmar",
        hijos: [datos.peticiones.length
          ? el("ul", { class: "oc__lista" }, datos.peticiones.map(filaPeticion))
          : ui.vacio({ icono: "check", titulo: "No hay peticiones pendientes", texto: "Cuando llegue una petición de fechas por correo o WhatsApp, aparece aquí." })],
      });
    }

    const textoCierre = (p) => (p.slots?.tipo && p.slots.entrada
      ? `Cerrar la venta de ${p.slots.tipo} del ${ui.fechaCorta(p.slots.entrada)} al ${ui.fechaCorta(p.slots.salida)} en RoomCloud` : p.texto);

    async function decidir(p, accion) {
      if (accion === "aprobar") {
        const ok = await ctx.confirmar({
          titulo: "Aprobar el cierre de venta",
          texto: `${textoCierre(p)}. El cierre en RoomCloud es simulado: la demo lo registra y no toca el sistema real.`,
          confirmar: "Aprobar cierre", cancelar: "Volver", contenido: el("span"),
        });
        if (!ok) return;
      }
      try {
        await ctx.api(`/api/propuestas/${p.id}/${accion}`, "POST", { actor: "Flor" });
        ctx.avisar(accion === "aprobar" ? "Cierre aprobado. En RoomCloud queda simulado." : "Cierre rechazado.", accion === "aprobar" ? "ok" : "neutro");
      } catch (e) {
        ctx.avisar(e.message || "No se ha podido registrar la decisión.", "critico");
      }
    }

    function panelCierres() {
      const lista = propuestas.filter((p) => p.plantilla === "cerrar_disponibilidad");
      return ui.panel({
        titulo: "Cierres de venta en RoomCloud propuestos", subtitulo: "Evitan nuevas ventas de lo que ya está completo",
        hijos: [lista.length
          ? el("ul", { class: "oc__lista" }, lista.map((p) => el("li", { class: "oc__peticion" },
            el("div", { class: "oc__peticion-info" },
              el("strong", null, `Cerrar ${p.slots?.tipo ?? ""}`),
              el("span", { class: "oc__peticion-datos" }, textoCierre(p))),
            el("div", { class: "oc__acciones" },
              ui.boton({ texto: "Rechazar", variante: "secundario", tam: "sm", etiqueta: `Rechazar el cierre ${p.id}`, onclick: () => decidir(p, "rechazar") }),
              ui.boton({ texto: "Aprobar", variante: "oscuro", tam: "sm", etiqueta: `Aprobar el cierre ${p.id}`, onclick: () => decidir(p, "aprobar") })))))
          : ui.vacio({ icono: "check", titulo: "No hay cierres pendientes", texto: "Cuando una noche se llene, la aplicación propone cerrar la venta en RoomCloud y lo verás aquí." })],
      });
    }

    /* ------------------------------------------------------------ pintado */

    function elegir(tipo, fecha) {
      seleccion = seleccion?.tipo === tipo && seleccion?.fecha === fecha ? null : { tipo, fecha };
      pintar();
      const b = raiz.querySelector(`.oc__celda[data-tipo="${tipo}"][data-fecha="${fecha}"]`);
      b?.focus();
    }

    function pintar() {
      const scroll = raiz.querySelector(".oc__scroll")?.scrollLeft ?? 0;
      raiz.replaceChildren(
        leyenda(),
        ui.panel({ titulo: "Ocupación de los próximos 14 días", hijos: [rejilla(), el("div", { class: "oc__detalle-caja", aria: { live: "polite" } }, detalle())] }),
        el("div", { class: "oc__doble" }, panelPeticiones(), panelCierres()));
      const nuevo = raiz.querySelector(".oc__scroll");
      if (nuevo) nuevo.scrollLeft = scroll;
    }

    function pintarError(e) {
      raiz.replaceChildren(ui.panel({ hijos: [ui.vacio({
        icono: "alert", titulo: "No se ha podido cargar la ocupación", texto: e?.message || "El servidor no responde.",
        accion: { texto: "Volver a intentarlo", icono: "refresh", onclick: () => cargar(true) },
      })] }));
    }

    async function cargar(conEsqueleto = false) {
      if (!datos || conEsqueleto) raiz.replaceChildren(ui.esqueleto({ lineas: 6, alto: 28 }));
      try {
        const [oc, pr] = await Promise.all([ctx.api("/api/ocupacion?dias=14"), ctx.api("/api/propuestas?estado=pendiente")]);
        datos = oc;
        propuestas = Array.isArray(pr) ? pr : (pr?.propuestas ?? []);
        pintar();
      } catch (e) { pintarError(e); }
    }

    const baja = ctx.suscribir("datos-cambiaron", () => cargar());
    await cargar();
    return { destruir() { baja(); } };
  },
};
