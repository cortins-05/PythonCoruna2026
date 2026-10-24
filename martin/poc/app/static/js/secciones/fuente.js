/*
  Sección "Fuente única": de dónde bebe la aplicación, cómo se unifica y quién gana cuando dos fuentes compiten.
  Datos: GET /api/fuente-unica. Lo mínimo se pinta con ui-hotel.js (semáforo, pastilla de nivel y escalera).
*/
import { ICONO_FUENTE, chipSemaforo, pastillaNivel, escalera } from "../ui-hotel.js";

const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;
const LEE = { roomcloud: "/api/sync/roomcloud", ofihotel: "/api/sync/ofihotel" };

function etiquetaTipo(f) {
  if (f.tipo === "firme") return "reserva firme";
  if (f.tipo === "peticion") return "petición";
  return "salida";
}

function estadoFuente(f) {
  const sinLectura = f.estado === "sin_lectura" || (f.ultima == null && f.id in LEE);
  if (sinLectura) return { texto: "Sin lectura", tono: "neutro" };
  if (f.estado === "real") return { texto: "Real", tono: "ok" };
  return { texto: "Simulado", tono: "info" };
}

export default {
  id: "fuente",
  async montar(contenedor, ctx) {
    const { el, ui } = ctx;
    const raiz = el("div", { class: "sec-fuente" });
    contenedor.append(raiz);
    let datos = null;
    let secuencia = 0;
    let vivo = true;

    /* ------------------------------------------------------------ acciones */
    const ejecutar = async (hacer, errorTexto) => {
      try { await hacer(); } catch (e) { ctx.avisar(e.message || errorTexto, "critico"); }
    };

    const simularReserva = () => ejecutar(async () => {
      const r = await ctx.api("/api/demo/reserva-roomcloud", "POST", { tipo: "SGL-STD" });
      ctx.avisar(`Entra la reserva ${r.id} de Booking (${r.tipo}) del ${ui.fechaCorta(r.desde)} al ${ui.fechaCorta(r.hasta)}. Si una petición competía por ese hueco, pasa a No disponible.`, "ok");
    }, "No se ha podido simular la reserva");

    const leer = (id) => ejecutar(async () => {
      const r = await ctx.api(LEE[id], "POST");
      if (id === "roomcloud") {
        ctx.avisar(`RoomCloud leído: ${plural(r.nuevas ?? 0, "reserva nueva", "reservas nuevas")}, ${plural(r.actualizadas ?? 0, "actualizada", "actualizadas")} y ${plural(r.canceladas ?? 0, "cancelada", "canceladas")}.`, "ok");
      } else {
        ctx.avisar(`OfiHotel leído: ${plural(r.estancias ?? 0, "estancia", "estancias")}, con datos hasta las ${(r.datos_hasta || "").slice(11, 16) || "X"} de ayer.`, "ok");
      }
    }, "No se ha podido leer la fuente");

    const reiniciar = () => ejecutar(async () => {
      const ok = await ctx.confirmar({
        titulo: "Volver al inicio de la demo", texto: "Se borran los cambios hechos durante la demo y vuelven los datos de partida.",
        confirmar: "Volver al inicio", tono: "critico",
      });
      if (!ok) return;
      await ctx.api("/api/demo/semilla?nivel=demo", "POST");
      ctx.avisar("La demo vuelve a su estado inicial.", "ok");
    }, "No se ha podido reiniciar la demo");

    /* ------------------------------------------------------------ piezas */
    const botonLeer = (id) => {
      const b = ui.boton({ texto: "Leer ahora", icono: "refresh", tam: "sm", variante: "secundario" });
      b.addEventListener("click", async () => {
        b.disabled = true;
        await leer(id);
        if (b.isConnected) b.disabled = false;
      });
      return b;
    };

    const tarjetaFuente = (f) => {
      const est = estadoFuente(f);
      const prioridad = f.nivel != null ? { nivel: f.nivel, fuente: f.nombre, id: f.id, tipo: f.tipo } : null;
      return el("article", { class: `fu__fuente fu__fuente--${f.tipo}`, dataset: { fuente: f.id } },
        el("header", { class: "fu__fuente-cab" },
          el("span", { class: "fu__fuente-icono", aria: { hidden: "true" } }, ui.icono(ICONO_FUENTE[f.id] ?? f.icono ?? "layers", { tam: 20 })),
          el("h3", { class: "fu__fuente-nombre" }, f.nombre),
          prioridad && pastillaNivel(prioridad, { compacta: true })),
        el("div", { class: "fu__fuente-chips" },
          el("span", { class: `fu__tipo fu__tipo--${f.tipo}` }, etiquetaTipo(f)),
          ui.chip({ texto: est.texto, tono: est.tono, punto: true })),
        el("p", { class: "fu__cifra" }, el("strong", null, String(f.recibido)), el("span", null, f.tipo === "salida" ? (f.recibido === 1 ? "enviado" : "enviados") : (f.recibido === 1 ? "recibido" : "recibidos"))),
        el("p", { class: "fu__detalle" }, f.detalle),
        el("p", { class: "fu__ultima" }, f.ultima ? `Última lectura ${f.ultima}` : "Sin lectura todavía"),
        el("p", { class: "fu__entra" }, f.entra),
        f.id in LEE && el("div", { class: "fu__fuente-pie" }, botonLeer(f.id)),
        f.tipo !== "salida" && el("span", { class: "fu__conector", role: "presentation", aria: { hidden: "true" } }));
    };

    const bandaTotales = (t) => {
      const c = t.por_color ?? {};
      const kpi = (etiqueta, valor, detalle, chip) => el("div", { class: "fu__kpi" },
        el("span", { class: "fu__kpi-etiqueta" }, etiqueta),
        el("strong", { class: "fu__kpi-valor" }, String(valor)),
        chip || el("span", { class: "fu__kpi-detalle" }, detalle));
      const hasta = datos.datos_ofihotel?.datos_hasta ? datos.datos_ofihotel.datos_hasta.slice(11, 16) : null;
      return el("div", { class: "fu__totales", role: "group", aria: { label: "Totales" } },
        kpi("Estancias", t.estancias, hasta ? `Datos de OfiHotel hasta las ${hasta} de ayer` : "Estancias en la plataforma"),
        kpi("Peticiones por confirmar", t.comunicaciones_pendientes, "", chipSemaforo("azul", "Por atender")),
        kpi("Conflictos", t.conflictos, "", chipSemaforo("rojo")),
        kpi("Partes pendientes", c.naranja ?? 0, "", chipSemaforo("naranja")));
    };

    const bandaUnica = (t) => el("div", { class: "fu__unica" },
      el("span", { class: "fu__unica-icono", aria: { hidden: "true" } }, ui.icono("layers", { tam: 22 })),
      el("div", { class: "fu__unica-textos" },
        el("strong", null, "Fuente única"),
        el("span", null, `${plural(t.estancias, "estancia", "estancias")}, ${plural(t.comunicaciones_pendientes, "petición", "peticiones")}, ${plural(t.conflictos, "conflicto", "conflictos")}`)));

    const filaCola = (item) => el("li", { class: "fu__cola-fila" },
      el("div", { class: "fu__cola-chip" }, chipSemaforo(item.color)),
      el("div", { class: "fu__cola-textos" }, el("strong", null, item.titulo), el("span", null, item.detalle)),
      item.prioridad && pastillaNivel(item.prioridad, { compacta: true }),
      ui.boton({ texto: "Abrir", icono: "arrow-up-right", tam: "sm", onclick: () => ctx.navegar(item.ruta, item.params) }));

    const filaActividad = (ev) => el("li", { class: "fu__ev" },
      el("span", { class: "fu__ev-icono", aria: { hidden: "true" } }, ui.icono(ICONO_FUENTE[ev.fuente] ?? ev.icono ?? "dot", { tam: 16 })),
      el("div", { class: "fu__ev-textos" },
        el("div", { class: "fu__ev-cab" }, el("strong", null, ev.titulo), el("time", { class: "fu__ev-hora" }, ev.hora)),
        el("span", null, ev.detalle)));

    const controles = () => {
      const bt = (texto, icono, onclick, variante = "secundario") => ui.boton({ texto, icono, variante, tam: "sm", onclick });
      return el("details", { class: "fu__controles" },
        el("summary", null, ui.icono("zap", { tam: 16 }), el("span", null, "Controles de la demo"), ui.icono("chevron-down", { tam: 16, clase: "fu__flecha" })),
        el("div", { class: "fu__controles-cuerpo" },
          el("p", null, "Lanzan entradas simuladas para enseñar cómo reacciona la plataforma."),
          el("div", { class: "fu__controles-botones" },
            bt("Entra un mensaje", "message", () => ctx.navegar("comunicaciones", { simular: "1" })),
            bt("Entra una reserva de Booking", "plus", simularReserva),
            bt("Leer RoomCloud", "refresh", () => leer("roomcloud")),
            bt("Leer OfiHotel", "refresh", () => leer("ofihotel")),
            bt("Volver al inicio de la demo", "arrow-left", reiniciar, "peligro"))));
    };

    /* ------------------------------------------------------------ estados */
    const cargando = () => raiz.replaceChildren(
      el("div", { class: "fu__carga" }, ui.esqueleto({ lineas: 2, alto: 56 }), ui.esqueleto({ lineas: 3, alto: 120 }), ui.esqueleto({ lineas: 3, alto: 90 })));

    const error = (e) => raiz.replaceChildren(ui.panel({ hijos: [ui.vacio({
      icono: "alert", titulo: "No se ha podido cargar la fuente única", texto: e?.message || "Inténtalo de nuevo en unos segundos.",
      accion: { texto: "Reintentar", icono: "refresh", onclick: () => cargar(true) },
    })] }));

    function pintar() {
      const d = datos;
      const entrantes = d.fuentes.filter((f) => f.tipo !== "salida").sort((a, b) => a.nivel - b.nivel);
      const salidas = d.fuentes.filter((f) => f.tipo === "salida");
      raiz.replaceChildren(
        bandaTotales(d.totales),
        ui.panel({
          titulo: "De dónde bebe la aplicación", subtitulo: "Cinco vías de entrada, ordenadas por nivel de prioridad, y una de salida",
          hijos: [el("div", { class: "fu__origen" },
            entrantes.length ? el("div", { class: "fu__fuentes" }, entrantes.map(tarjetaFuente))
              : ui.vacio({ icono: "plug", titulo: "Todavía no hay fuentes", texto: "Lee RoomCloud u OfiHotel para empezar." }),
            bandaUnica(d.totales),
            salidas.length > 0 && el("div", { class: "fu__salida" },
              el("span", { class: "fu__conector fu__conector--salida", role: "presentation", aria: { hidden: "true" } }),
              salidas.map(tarjetaFuente)))],
        }),
        ui.panel({
          titulo: "Quién gana cuando dos fuentes compiten", subtitulo: "Gana la de más prioridad. Una petición nunca desplaza a una reserva firme.",
          variante: "suave", hijos: [escalera(d.prioridades, { reglas: true })],
        }),
        el("div", { class: "fu__doble" },
          ui.panel({
            titulo: "Qué atender primero", subtitulo: "Ordenado por la prioridad de la fuente y después por urgencia",
            hijos: [d.cola.length ? el("ul", { class: "fu__cola" }, d.cola.map(filaCola))
              : ui.vacio({ icono: "check", titulo: "Nada pendiente", texto: "Todo está cuadrado." })],
          }),
          ui.panel({
            titulo: "Actividad reciente",
            hijos: [d.actividad.length ? el("ol", { class: "fu__linea" }, d.actividad.map(filaActividad))
              : ui.vacio({ icono: "clock", titulo: "Sin actividad todavía" })],
          })),
        controles());
    }

    async function cargar(conEsqueleto = false) {
      const mia = ++secuencia;
      if (conEsqueleto || !datos) cargando();
      try {
        const r = await ctx.api("/api/fuente-unica");
        if (!vivo || mia !== secuencia) return;
        datos = r;
        pintar();
      } catch (e) {
        if (!vivo || mia !== secuencia) return;
        datos = null;
        error(e);
      }
    }

    ctx.barra({
      titulo: "Fuente única", subtitulo: "Lo que entra al hotel por cinco vías, unificado en una sola plataforma",
      cta: { texto: "Simular una reserva de Booking", icono: "plus", onclick: simularReserva },
      acciones: [{ icono: "refresh", texto: "Actualizar", etiqueta: "Actualizar", onclick: () => cargar(true) }],
    });
    const baja = ctx.suscribir("datos-cambiaron", () => cargar());
    await cargar();
    return { destruir() { vivo = false; baja(); } };
  },
};
