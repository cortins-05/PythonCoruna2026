/*
  Sección "Ocupación": lo que ocupa cada fuente cada noche y qué peticiones compiten por lo que queda.
  Datos: GET /api/ocupacion?dias=30 y GET /api/propuestas?estado=pendiente (solo cerrar_disponibilidad).
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
    let tipo = null;
    let mes = null;
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
      titulo: "Ocupación", subtitulo: "Calendario mensual por tipo de habitación",
      cta: { texto: "Simular reserva de Booking", icono: "plus", onclick: simular },
      acciones: [{ icono: "refresh", etiqueta: "Actualizar", onclick: () => cargar() }],
    });

    /* ------------------------------------------------------------ piezas */

    const prioridadDe = (id) => {
      const f = datos?.fuentes?.find((x) => x.id === id);
      return f ? { nivel: f.nivel, fuente: f.nombre, id: f.id, tipo: f.tipo } : { nivel: 0, fuente: NOMBRE_FUENTE[id] ?? id, id, tipo: "firme" };
    };

    const NOMBRE_MES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
    const CABECERA = [["lun", "lunes"], ["mar", "martes"], ["mié", "miércoles"], ["jue", "jueves"], ["vie", "viernes"], ["sáb", "sábado"], ["dom", "domingo"]];

    function estadoDia(dia, capacidad) {
      if (dia.ocupadas > capacidad) return "overbooking";
      if (dia.libres <= 0) return "completo";
      return "libre";
    }

    const claveMes = (iso) => iso.slice(0, 7);
    const sumaMes = (clave, n) => { const d = new Date(Number(clave.slice(0, 4)), Number(clave.slice(5, 7)) - 1 + n, 1, 12); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`; };
    const isoDe = (y, m, d) => `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;

    function celda(tipo, capacidad, dia, iso) {
      if (!dia) {
        return el("td", { class: "oc__td" }, el("span", { class: "oc__vacia" }, el("span", { class: "oc__num" }, String(numeroDia(iso)))));
      }
      const pets = datos.peticiones.filter((p) => tocaNoche(p, tipo, dia.fecha));
      const est = estadoDia(dia, capacidad);
      const activa = seleccion?.tipo === tipo && seleccion?.fecha === dia.fecha;
      const estados = [est === "overbooking" && "overbooking", est === "completo" && "lleno", dia.cerrado_en_roomcloud && "cerrado"].filter(Boolean);
      const etiqueta = `${diaSemana(dia.fecha, DIAS_LARGOS)} ${numeroDia(dia.fecha)}: ${dia.ocupadas} de ${capacidad} ocupadas`
        + `${estados.length ? `, ${estados.join(", ")}` : ""}${pets.length ? `, ${plural(pets.length, "petición", "peticiones")}` : ""}`;
      const boton = el("button", {
        type: "button", class: `oc__celda oc__celda--${est}${dia.cerrado_en_roomcloud ? " es-cerrado" : ""}${activa ? " is-activa" : ""}`,
        dataset: { tipo, fecha: dia.fecha }, aria: { pressed: String(activa), label: etiqueta },
        onclick: () => elegir(tipo, dia.fecha),
      },
      el("span", { class: "oc__num" }, String(numeroDia(dia.fecha))),
      el("span", { class: "oc__cifra" }, el("strong", null, String(dia.ocupadas)), `/${capacidad}`),
      el("span", { class: "oc__marcas" },
        est === "overbooking" && el("span", { class: "oc__marca oc__marca--critico" }, ui.icono("alert", { tam: 12 }), el("span", { class: "oc__marca-txt" }, "Overbooking")),
        est === "completo" && el("span", { class: "oc__marca oc__marca--aviso" }, ui.icono("lock", { tam: 12 }), el("span", { class: "oc__marca-txt" }, "Lleno")),
        dia.cerrado_en_roomcloud && el("span", { class: "oc__marca oc__marca--info" }, ui.icono("x", { tam: 12 }), el("span", { class: "oc__marca-txt" }, "Cerrado")),
        pets.length > 0 && el("span", { class: "oc__marca oc__marca--pet" }, ui.icono("inbox", { tam: 12 }), el("span", { class: "oc__marca-n" }, String(pets.length)))));
      return el("td", { class: "oc__td" }, boton);
    }

    function calendario() {
      const tipos = datos.mapa.tipos;
      if (!tipo || !tipos[tipo]) tipo = Object.keys(tipos)[0];
      const info = tipos[tipo];
      const fechas = datos.mapa.fechas;
      const minMes = claveMes(fechas[0]);
      const maxMes = claveMes(fechas[fechas.length - 1]);
      if (!mes || mes < minMes || mes > maxMes) mes = minMes;
      const [y, m] = mes.split("-").map(Number);
      const porFecha = new Map(info.dias.map((d) => [d.fecha, d]));
      const primero = (new Date(y, m - 1, 1, 12).getDay() + 6) % 7;
      const nDias = new Date(y, m, 0).getDate();
      const filas = [];
      for (let i = 0, d = 1 - primero; i < Math.ceil((primero + nDias) / 7); i++) {
        const tds = [];
        for (let c = 0; c < 7; c++, d++) {
          const f = new Date(y, m - 1, d, 12);
          const iso = isoDe(f.getFullYear(), f.getMonth() + 1, f.getDate());
          tds.push(d >= 1 && d <= nDias ? celda(tipo, info.capacidad, porFecha.get(iso), iso) : el("td", { class: "oc__td" }));
        }
        filas.push(el("tr", null, tds));
      }
      const selector = el("select", { class: "oc__select", aria: { label: "Tipo de habitación" }, onchange: (e) => { tipo = e.target.value; seleccion = null; pintar(); } },
        Object.keys(tipos).map((t) => el("option", { value: t, selected: t === tipo }, `${NOMBRE_TIPO[t] ?? t} (${tipos[t].capacidad})`)));
      const nav = el("div", { class: "oc__nav" },
        ui.boton({ icono: "chevron-left", variante: "secundario", tam: "sm", etiqueta: "Mes anterior", desactivado: mes <= minMes, onclick: () => { mes = sumaMes(mes, -1); seleccion = null; pintar(); } }),
        el("strong", { class: "oc__mes", aria: { live: "polite" } }, `${NOMBRE_MES[m - 1]} ${y}`),
        ui.boton({ icono: "chevron-right", variante: "secundario", tam: "sm", etiqueta: "Mes siguiente", desactivado: mes >= maxMes, onclick: () => { mes = sumaMes(mes, 1); seleccion = null; pintar(); } }));
      return el("div", { class: "oc__cal" },
        el("div", { class: "oc__controles" }, selector, nav),
        el("table", { class: "oc__tabla" },
          el("caption", { class: "oc__caption" }, `Habitaciones ocupadas sobre capacidad, ${NOMBRE_TIPO[tipo] ?? tipo}, ${NOMBRE_MES[m - 1]} ${y}`),
          el("thead", null, el("tr", null, CABECERA.map(([c, l]) => el("th", { scope: "col", class: "oc__th-dia" }, el("abbr", { title: l }, c))))),
          el("tbody", null, filas)));
    }

    function detalle() {
      if (!seleccion) {
        return el("p", { class: "oc__detalle-vacio" }, "Pulsa un día para ver el desglose por fuente y sus peticiones.");
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
      const b = raiz.querySelector(`.oc__celda[data-fecha="${fecha}"]`);
      b?.focus();
    }

    function pintar() {
      raiz.replaceChildren(
        ui.panel({ hijos: [calendario(), el("div", { class: "oc__detalle-caja", aria: { live: "polite" } }, detalle())] }),
        el("div", { class: "oc__doble" }, panelPeticiones(), panelCierres()));
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
        const [oc, pr] = await Promise.all([ctx.api("/api/ocupacion?dias=30"), ctx.api("/api/propuestas?estado=pendiente")]);
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
