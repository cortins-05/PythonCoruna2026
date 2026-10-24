/*
  Sección "Ocupación": lo que ocupa cada fuente cada noche y qué peticiones compiten por lo que queda.
  Datos: GET /api/ocupacion?dias=14 y GET /api/propuestas?estado=pendiente (solo cerrar_disponibilidad).
*/
import { chipVeredicto, NOMBRE_FUENTE } from "../ui-hotel.js";

const FUENTES = ["roomcloud", "ofihotel", "recepcion"];
const DIAS_SEMANA = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];
const DIAS_LARGOS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
const NOMBRE_TIPO = { "DBL-STD": "Doble estándar", "SGL-STD": "Individual estándar" };

const diaSemana = (iso, lista = DIAS_SEMANA) => lista[new Date(`${iso}T12:00:00`).getDay()];
const numeroDia = (iso) => Number(iso.slice(8, 10));
const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;
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
      titulo: "Ocupación",
      cta: { texto: "Simular reserva de Booking", icono: "plus", onclick: simular },
      acciones: [{ icono: "refresh", etiqueta: "Actualizar", onclick: () => cargar() }],
    });

    /* ------------------------------------------------------------ piezas */

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
      el("span", { class: "oc__cifra" }, `${dia.ocupadas}/${capacidad}`),
      el("span", { class: "oc__marca" }, est === "overbooking" ? "overbooking" : est === "completo" ? "lleno" : dia.cerrado_en_roomcloud ? "cerrado" : ""));
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
        el("th", { scope: "col", class: "oc__th-tipo" }, "Tipo"),
        fechas.map((f) => el("th", { scope: "col", class: "oc__th-dia" },
          el("span", { class: "oc__dia-semana" }, diaSemana(f)), el("span", { class: "oc__dia-num" }, numeroDia(f))))));
      const cuerpo = el("tbody", null, Object.entries(tipos).map(([tipo, info]) => el("tr", null,
        el("th", { scope: "row", class: "oc__th-tipo" }, tipo),
        info.dias.map((dia) => celda(tipo, info.capacidad, dia)))));
      return el("div", { class: "oc__scroll", role: "region", tabindex: "0", aria: { label: "Rejilla de ocupación, se desplaza en horizontal" } },
        el("table", { class: "oc__tabla" },
          el("caption", { class: "oc__caption" }, "Habitaciones ocupadas sobre capacidad, por tipo y noche"),
          cabecera, cuerpo));
    }

    function detalle() {
      if (!seleccion) return null;
      const { tipo, fecha } = seleccion;
      const info = datos.mapa.tipos[tipo];
      const dia = info?.dias.find((d) => d.fecha === fecha);
      if (!dia) return null;
      return el("div", { class: "oc__detalle", id: "oc-detalle", tabindex: "-1" },
        el("h3", null, `${tipo}, ${diaSemana(fecha, DIAS_LARGOS)} ${ui.fechaCorta(fecha)}: ${dia.ocupadas} de ${info.capacidad} ocupadas`),
        el("ul", { class: "oc__desglose", "aria-label": "Desglose por fuente" }, FUENTES.map((f) => el("li", null,
          el("span", null, NOMBRE_FUENTE[f]), el("strong", null, String(dia.por_fuente[f]))))));
    }

    function filaPeticion(p) {
      return el("li", { class: "oc__peticion" },
        el("div", { class: "oc__peticion-info" },
          el("strong", null, p.de),
          el("span", { class: "oc__peticion-datos" }, `${NOMBRE_FUENTE[p.canal] ?? p.canal}, ${p.tipo_habitacion}, ${plural(p.habitaciones, "habitación", "habitaciones")}, ${ui.fechaCorta(p.desde)} a ${ui.fechaCorta(p.hasta)}`)),
        p.veredicto === "disponible" ? el("span", { class: "oc__peticion-datos" }, "Disponible") : chipVeredicto(p.veredicto),
        ui.boton({ texto: "Abrir petición", tam: "sm", variante: "secundario", etiqueta: `Abrir la petición de ${p.de}`, onclick: () => ctx.navegar("comunicaciones", { id: p.id }) }));
    }

    function seccionPeticiones() {
      if (!datos.peticiones.length) return null;
      return el("section", { class: "oc__bloque" }, el("h2", null, "Peticiones que compiten"),
        el("ul", { class: "oc__lista" }, datos.peticiones.map(filaPeticion)));
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

    function seccionCierres() {
      const lista = propuestas.filter((p) => p.plantilla === "cerrar_disponibilidad");
      if (!lista.length) return null;
      return el("section", { class: "oc__bloque" }, el("h2", null, "Cierres propuestos"),
        el("ul", { class: "oc__lista" }, lista.map((p) => el("li", { class: "oc__peticion" },
          el("div", { class: "oc__peticion-info" }, el("span", null, textoCierre(p))),
          el("div", { class: "oc__acciones" },
            ui.boton({ texto: "Rechazar cierre", variante: "secundario", tam: "sm", etiqueta: `Rechazar el cierre ${p.id}`, onclick: () => decidir(p, "rechazar") }),
            ui.boton({ texto: "Aprobar cierre", variante: "secundario", tam: "sm", etiqueta: `Aprobar el cierre ${p.id}`, onclick: () => decidir(p, "aprobar") }))))));
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
        el("section", { class: "oc__bloque" }, rejilla(), el("div", { class: "oc__detalle-caja", aria: { live: "polite" } }, detalle())),
        seccionPeticiones(), seccionCierres());
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
