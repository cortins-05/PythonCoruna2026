/*
  Sección "Comunicaciones": lista de peticiones por correo y WhatsApp a la izquierda y, a la derecha, la petición ya contrastada con las fuentes,
  el borrador de respuesta por el mismo canal y la confirmación de recepción. Los envíos son simulados (ver design/CONTRATO-CORE.md).
*/
import { chipVeredicto, pastillaNivel, escalera, ICONO_FUENTE, NOMBRE_FUENTE } from "../ui-hotel.js";

const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
const HABITACION = { SGL: "Individual", DBL: "Doble", TPL: "Triple", FAM: "Familiar", SUI: "Suite" };
const IDIOMA = { es: "ES", fr: "FR", en: "EN" };
const ESTADO = { pendiente: ["info", "Pendiente"], en_espera: ["aviso", "En espera"], respondida: ["ok", "Respondida"], descartada: ["neutro", "Descartada"] };
const TIPO = { pregunta: "una pregunta", cambio: "una petición de cambio", otro: "un mensaje de otro tipo" };
const ID_FUENTE = Object.fromEntries(Object.entries(NOMBRE_FUENTE).map(([id, nombre]) => [nombre, id]));

const EJEMPLOS = [
  { id: "doble", titulo: "Doble del 5 al 7 de noviembre", canal: "whatsapp", contacto: "34611222333", nombre: "Lucía Méndez", asunto: "",
    texto: "Hola, ¿tenéis una habitación doble libre del 5 al 7 de noviembre para dos personas?" },
  { id: "individual", titulo: "Individual para esta noche", canal: "correo", contacto: "carlos.vidal@example.com", nombre: "Carlos Vidal", asunto: "Habitación individual para esta noche",
    texto: "Buenos días, necesito una habitación individual para esta noche. ¿Tenéis disponibilidad?" },
  { id: "frances", titulo: "Doble del 24 al 27 en francés", canal: "correo", contacto: "julie.moreau@example.fr", nombre: "Julie Moreau", asunto: "Demande de chambre du 24 au 27 octobre",
    texto: "Bonjour, avez-vous une chambre double de libre du 24 au 27 octobre pour 2 personnes ? Merci d'avance." },
];

/* ------------------------------------------------------------------ formato */

const partes = (iso) => String(iso).slice(0, 10).split("-").map(Number);
const diaMes = (iso) => { const [, m, d] = partes(iso); return { d, m: MESES[m - 1] }; };

/** "24 al 27 de octubre", o "30 de octubre al 2 de noviembre" si cruza de mes. */
function rango(desde, hasta) {
  const a = diaMes(desde);
  const b = diaMes(hasta);
  return a.m === b.m ? `${a.d} al ${b.d} de ${b.m}` : `${a.d} de ${a.m} al ${b.d} de ${b.m}`;
}

const habitacion = (codigo) => HABITACION[String(codigo ?? "").slice(0, 3)] ?? String(codigo ?? "Sin tipo");
const nombreCanal = (canal) => (canal === "whatsapp" ? "WhatsApp" : "correo");
const porCanal = (canal) => (canal === "whatsapp" ? "por WhatsApp" : "por correo");
const extracto = (c) => (c.asunto && c.canal === "correo" ? c.asunto : c.texto);

/* ------------------------------------------------------------------ sección */

export default {
  id: "comunicaciones",
  async montar(contenedor, ctx) {
    const { el, ui } = ctx;
    contenedor.classList.add("sec-comunicaciones");

    const est = { lista: [], contadores: {}, prioridades: null, canal: ["whatsapp", "correo"].includes(ctx.params.canal) ? ctx.params.canal : "todos", id: ctx.params.id ?? null, movilDetalle: Boolean(ctx.params.id), cargado: false, error: null };
    const zonaLista = el("div", { class: "com__lista" });
    const zonaDetalle = el("div", { class: "com__detalle", tabindex: "-1" });
    contenedor.append(el("div", { class: "u-dos-paneles com" }, zonaLista, zonaDetalle));

    ctx.barra({
      titulo: "Comunicaciones",
      subtitulo: "Peticiones contrastadas con todas las fuentes, listas para confirmar",
      acciones: [{ icono: "plus", texto: "Simular un mensaje", onclick: () => abrirSimulador() }],
    });

    /* ---------------------------------------------------------- datos */

    async function cargar({ foco = null } = {}) {
      const enLista = zonaLista.contains(document.activeElement);
      const idFoco = enLista ? document.activeElement.dataset?.id : null;
      try {
        const datos = await ctx.api("/api/comunicaciones?estado=todas&canal=todos");
        est.lista = datos.comunicaciones ?? [];
        est.contadores = datos.contadores ?? {};
        est.prioridades = datos.prioridades ?? est.prioridades;
        est.error = null;
      } catch (e) {
        est.error = e.message;
      }
      est.cargado = true;
      if (!est.lista.some((c) => c.id === est.id)) {
        est.id = visibles()[0]?.id ?? est.lista[0]?.id ?? null;
        if (!est.id) est.movilDetalle = false;
      }
      pintarLista();
      pintarDetalle();
      if (foco === "detalle") zonaDetalle.focus({ preventScroll: true });
      else if (idFoco) zonaLista.querySelector(`[data-id="${idFoco}"]`)?.focus({ preventScroll: true });
    }

    const visibles = () => est.lista.filter((c) => est.canal === "todos" || c.canal === est.canal);
    const actual = () => est.lista.find((c) => c.id === est.id) ?? null;

    function seleccionar(id) {
      est.id = id;
      est.movilDetalle = true;
      ctx.navegar("comunicaciones", { id, canal: est.canal === "todos" ? null : est.canal });
    }

    /* ---------------------------------------------------------- lista */

    function pintarLista() {
      zonaLista.classList.toggle("is-oculta-movil", est.movilDetalle);
      const abiertas = (est.contadores.whatsapp ?? 0) + (est.contadores.correo ?? 0);
      const filtros = ui.filaPastillas({
        etiqueta: "Filtrar por canal", activo: est.canal,
        items: [
          { id: "todos", texto: "Todas", cuenta: abiertas },
          { id: "correo", texto: "Correo", cuenta: est.contadores.correo ?? 0 },
          { id: "whatsapp", texto: "WhatsApp", cuenta: est.contadores.whatsapp ?? 0 },
        ],
        onchange: (canal) => {
          est.canal = canal;
          if (!visibles().some((c) => c.id === est.id)) est.id = visibles()[0]?.id ?? null;
          pintarLista();
          pintarDetalle();
        },
      });
      const filas = visibles();
      const cuerpo = est.error ? ui.vacio({ icono: "alert", titulo: "No se pudieron cargar las comunicaciones", texto: est.error, accion: { texto: "Reintentar", variante: "secundario", onclick: () => cargar() } })
        : !est.cargado ? ui.esqueleto({ lineas: 5, alto: 56 })
          : filas.length === 0 ? ui.vacio({ icono: "inbox", titulo: "No hay comunicaciones", texto: "Simula un mensaje para ver cómo se contrasta con las fuentes." })
            : el("ul", { class: "com__filas" }, filas.map(fila));
      zonaLista.replaceChildren(el("div", { class: "com__filtros" }, filtros.el), cuerpo);
    }

    function fila(c) {
      const cerrada = c.estado === "respondida" || c.estado === "descartada";
      const [tono, textoEstado] = ESTADO[c.estado] ?? ESTADO.pendiente;
      const veredicto = c.contraste?.veredicto;
      return el("li", null, el("button", {
        type: "button", class: `com__fila${c.id === est.id ? " is-seleccionada" : ""}${cerrada ? " is-atenuada" : ""}`, dataset: { id: c.id },
        aria: { current: c.id === est.id ? "true" : null }, onclick: () => seleccionar(c.id),
      },
      el("span", { class: "com__canal", aria: { hidden: "true" } }, ctx.ui.icono(ICONO_FUENTE[c.canal] ?? "message", { tam: 18 })),
      el("span", { class: "com__fila-texto" },
        el("span", { class: "com__fila-cabecera" },
          el("strong", { class: "u-trunc" }, c.de.nombre),
          c.alerta && el("span", { class: "com__alerta-punto", title: "Trae una alerta" }, el("span", { class: "u-ocultar-visual" }, "Con alerta")),
          el("span", { class: "com__hora u-tabular" }, c.hora)),
        el("span", { class: "com__extracto" }, extracto(c)),
        el("span", { class: "com__fila-chips" },
          pastillaNivel(c.prioridad, { compacta: true }),
          cerrada ? ui.chip({ texto: textoEstado, tono, punto: true }) : veredicto ? chipVeredicto(veredicto) : ui.chip({ texto: "Sin contraste", tono: "neutro" })))));
    }

    /* ---------------------------------------------------------- detalle */

    function pintarDetalle() {
      zonaDetalle.classList.toggle("is-oculta-movil", !est.movilDetalle);
      const c = actual();
      if (!c) {
        zonaDetalle.replaceChildren(ui.panel({ hijos: [ui.vacio({ icono: "inbox", titulo: "Elige una comunicación", texto: "Aquí aparece el mensaje con el contraste de las fuentes." })] }));
        return;
      }
      const hijos = [];
      hijos.push(el("div", { class: "com__volver" }, ui.boton({ texto: "Volver a la lista", icono: "arrow-left", variante: "secundario", tam: "sm", onclick: () => { est.movilDetalle = false; pintarLista(); pintarDetalle(); zonaLista.querySelector(`[data-id="${c.id}"]`)?.focus(); } })));
      if (c.alerta) {
        hijos.push(el("div", { class: "com__banner", role: "alert" }, ui.icono("alert", { tam: 20 }),
          el("div", null, el("strong", null, `Alerta de las ${c.alerta.hora}`), el("p", null, c.alerta.texto))));
      }
      hijos.push(cabecera(c), bloqueMensaje(c), bloqueEntendido(c));
      if (c.contraste) hijos.push(bloqueContraste(c));
      hijos.push(bloqueRespuesta(c));
      zonaDetalle.replaceChildren(el("div", { class: "com__detalle-pila" }, hijos));
    }

    function cabecera(c) {
      const [tono, texto] = ESTADO[c.estado] ?? ESTADO.pendiente;
      return ui.panel({ hijos: [el("header", { class: "com__cab" },
        ui.avatar(c.de.nombre),
        el("div", { class: "com__cab-texto" },
          el("h2", { class: "com__nombre" }, c.de.nombre),
          el("p", { class: "com__contacto" }, `${nombreCanal(c.canal) === "correo" ? "Correo" : "WhatsApp"} · ${c.de.contacto} · ${c.hora}`)),
        el("div", { class: "com__cab-chips" },
          ui.chip({ texto: IDIOMA[c.idioma] ?? String(c.idioma).toUpperCase(), tono: "neutro" }),
          pastillaNivel(c.prioridad),
          ui.chip({ texto, tono, punto: true })))] });
    }

    function bloqueMensaje(c) {
      return ui.panel({ titulo: "Mensaje recibido", hijos: [el("blockquote", { class: "com__cita" },
        c.asunto && c.canal === "correo" && el("strong", { class: "com__asunto" }, c.asunto),
        el("p", null, c.texto))] });
    }

    function bloqueEntendido(c) {
      const p = c.peticion;
      if (c.tipo !== "peticion_habitacion" || !p) {
        return ui.panel({ titulo: "Lo que hemos entendido", hijos: [el("p", { class: "com__nota" },
          `Es ${TIPO[c.tipo] ?? "un mensaje"}, así que no hace falta contrastarlo con las fuentes. Basta con revisar la respuesta.`)] });
      }
      return ui.panel({ titulo: "Lo que hemos entendido", hijos: [ui.kv([
        { etiqueta: "Habitación", valor: habitacion(p.tipo_habitacion) },
        { etiqueta: "Fechas", valor: rango(p.desde, p.hasta) },
        { etiqueta: "Noches", valor: String(p.noches) },
        { etiqueta: "Personas", valor: String(p.personas) },
        { etiqueta: "Habitaciones", valor: String(p.habitaciones) },
      ], { columnas: 3 })] });
    }

    function bloqueContraste(c) {
      const k = c.contraste;
      const hijos = [];
      if (k.noches?.length) hijos.push(tablaNoches(k.noches));
      hijos.push(el("div", { class: "com__veredicto" }, el("span", { class: "com__veredicto-chip" }, chipVeredicto(k.veredicto)), el("p", { class: "com__motivo" }, k.motivo)));
      if (k.bloqueada_por?.length) {
        hijos.push(el("section", { class: "com__sub", aria: { label: "Lo ocupan" } }, el("h3", null, "Lo ocupan"),
          el("ul", { class: "com__lista-simple" }, k.bloqueada_por.map((b) => el("li", null,
            pastillaNivel({ nivel: b.nivel, fuente: b.fuente, id: b.id, tipo: "firme" }),
            el("span", null, `${b.ocupantes.join(", ")} (${b.cantidad})`))))));
      }
      if (k.retenida_por?.length) {
        hijos.push(el("section", { class: "com__sub", aria: { label: "Tiene prioridad" } }, el("h3", null, "Tiene prioridad"),
          el("ul", { class: "com__lista-simple" }, k.retenida_por.map((r) => el("li", null,
            pastillaNivel({ nivel: r.nivel, fuente: r.fuente, id: ID_FUENTE[r.fuente] ?? r.fuente, tipo: "peticion" }),
            el("span", null, `${r.de}, por ${r.canal === "whatsapp" ? "WhatsApp" : "correo"}, a las ${r.hora}`))))));
      }
      if (k.alternativa) {
        hijos.push(el("div", { class: "com__alternativa" }, ui.icono("calendar", { tam: 18 }),
          el("p", null, el("strong", null, "Alternativa que se propone al cliente: "), rango(k.alternativa.desde, k.alternativa.hasta))));
      }
      if (est.prioridades?.niveles) {
        const gana = k.bloqueada_por?.[0]?.id ?? ID_FUENTE[k.retenida_por?.[0]?.fuente] ?? c.prioridad.id;
        hijos.push(el("section", { class: "com__sub", aria: { label: "Por qué gana" } }, el("h3", null, "Por qué gana"),
          escalera(est.prioridades, { resaltar: gana, compacta: true, reglas: false })));
      }
      return ui.panel({ titulo: "Contraste con las fuentes", hijos });
    }

    function tablaNoches(noches) {
      const celda = (n, fuente) => {
        const cantidad = n.por_fuente?.[fuente] ?? 0;
        const nombres = n.ocupantes?.[fuente] ?? [];
        return el("td", { class: "u-derecha" }, String(cantidad), nombres.length > 0 && el("span", { class: "com__nombres" }, nombres.join(", ")));
      };
      const prioritarias = (n) => n.retenidas ?? 0;
      return el("div", { class: "ui-tabla-caja" }, el("table", { class: "ui-tabla com__tabla" },
        el("caption", { class: "u-ocultar-visual" }, "Habitaciones por noche y fuente para esta petición"),
        el("thead", null, el("tr", null, ["Noche", "Capacidad", "RoomCloud", "OfiHotel", "Recepción", "Peticiones con más prioridad", "Libres para esta petición"]
          .map((t, i) => el("th", { scope: "col", class: i > 0 ? "u-derecha" : null }, t)))),
        el("tbody", null, noches.map((n) => {
          const sinHueco = (n.libres_para_esta ?? 0) <= 0;
          return el("tr", { class: sinHueco ? "is-sin-hueco" : null },
            el("th", { scope: "row" }, ui.fechaCorta(n.fecha)),
            el("td", { class: "u-derecha" }, String(n.capacidad)),
            celda(n, "roomcloud"), celda(n, "ofihotel"), celda(n, "recepcion"),
            el("td", { class: "u-derecha" }, String(prioritarias(n))),
            el("td", { class: "u-derecha com__libres" }, String(n.libres_para_esta ?? 0), sinHueco && el("span", { class: "com__sin-hueco" }, "Sin hueco")));
        }))));
    }

    /* ---------------------------------------------------------- respuesta */

    function bloqueRespuesta(c) {
      const r = c.respuesta;
      const titulo = `Respuesta ${porCanal(c.canal)}`;
      if (!r) return ui.panel({ titulo, hijos: [el("p", { class: "com__nota" }, "Todavía no hay borrador de respuesta.")] });
      const cerrada = c.estado === "respondida" || c.estado === "descartada";
      const area = el("textarea", {
        class: "ui-entrada com__texto", rows: 6, disabled: cerrada, id: `com-texto-${c.id}`,
        aria: { label: `Texto de la respuesta ${porCanal(c.canal)}` },
      });
      area.value = r.texto ?? "";
      const contador = el("span", { class: "com__contador u-tabular", aria: { live: "off" } });
      const contar = () => { contador.textContent = `${area.value.length} caracteres`; };
      contar();
      area.addEventListener("input", contar);
      area.addEventListener("change", async () => {
        if (area.value === r.texto) return;
        try {
          await ctx.api(`/api/comunicaciones/${c.id}/texto`, "PUT", { texto: area.value });
          r.texto = area.value;
        } catch (e) { ctx.avisar(e.message, "critico"); }
      });

      const cabeceraMsg = c.canal === "correo"
        ? el("div", { class: "com__correo-cab" },
          el("p", null, el("span", null, "Para: "), r.destinatario),
          el("p", null, el("span", null, "Asunto: "), r.asunto))
        : el("p", { class: "com__wa-cab" }, ui.icono("message", { tam: 14 }), `Para ${c.de.nombre}, ${r.destinatario}`);
      const burbuja = el("div", { class: `com__burbuja com__burbuja--${c.canal}` }, cabeceraMsg, area, el("div", { class: "com__burbuja-pie" }, contador));

      const hijos = [burbuja];
      if (cerrada) hijos.push(resultado(c));
      else {
        const etiqueta = `Confirmar y enviar ${porCanal(c.canal)}`;
        hijos.push(el("div", { class: "com__acciones" },
          ui.boton({ texto: etiqueta, icono: "send", variante: "cta", onclick: () => confirmar(c, area) }),
          ui.boton({ texto: "Descartar", icono: "x", variante: "secundario", onclick: () => descartar(c) })));
      }
      return ui.panel({ titulo, hijos });
    }

    function resultado(c) {
      const r = c.resultado;
      if (!r) return el("p", { class: "com__nota" }, c.estado === "descartada" ? "Descartada sin enviar respuesta." : "Respondida.");
      const lineas = [];
      if (r.accion === "descartada") lineas.push("Descartada sin enviar respuesta.");
      else lineas.push(`Enviado ${r.canal === "whatsapp" ? "por WhatsApp" : "por correo"} a ${r.destinatario}${r.simulado ? " (simulado)" : ""} a las ${r.hora}.`);
      if (r.accion === "reservada") lineas.push("Reserva creada con prioridad 3, Recepción.");
      return el("div", { class: "com__resultado", role: "status" }, ui.icono("check", { tam: 18 }),
        el("div", null, lineas.map((l) => el("p", null, l)),
          r.accion === "reservada" && (r.reserva_id || c.expediente_id) && el("a", {
            class: "com__enlace", href: "#/estancias", onclick: (e) => { e.preventDefault(); ctx.navegar("estancias", { id: r.reserva_id ?? c.expediente_id }); },
          }, "Ver la estancia")));
    }

    async function confirmar(c, area) {
      const texto = area.value;
      const aviso = el("div", { class: "com__previa" },
        el("dl", null,
          el("div", null, el("dt", null, "Canal"), el("dd", null, c.canal === "whatsapp" ? "WhatsApp" : "Correo")),
          el("div", null, el("dt", null, "Destinatario"), el("dd", null, c.respuesta.destinatario)),
          c.canal === "correo" && el("div", null, el("dt", null, "Asunto"), el("dd", null, c.respuesta.asunto))),
        el("p", { class: "com__previa-texto" }, texto));
      const ok = await ctx.confirmar({
        titulo: `Confirmar y enviar ${porCanal(c.canal)}`,
        texto: "El envío es simulado: la respuesta no sale a ningún cliente real.",
        confirmar: `Confirmar y enviar ${porCanal(c.canal)}`, contenido: aviso,
      });
      if (!ok) { area.focus(); return; }
      try {
        const nueva = await ctx.api(`/api/comunicaciones/${c.id}/confirmar`, "POST", { actor: "Flor", texto });
        ctx.avisar(nueva?.resultado?.accion === "reservada" ? "Reserva creada y respuesta enviada (simulado)" : "Respuesta enviada (simulado)", "ok");
      } catch (e) { ctx.avisar(e.message, "critico"); }
      await cargar({ foco: "detalle" });
    }

    async function descartar(c) {
      const ok = await ctx.confirmar({ titulo: "Descartar la comunicación", texto: `${c.de.nombre} no recibirá respuesta.`, confirmar: "Descartar", tono: "critico" });
      if (!ok) return;
      try {
        await ctx.api(`/api/comunicaciones/${c.id}/descartar`, "POST", { actor: "Flor" });
        ctx.avisar("Comunicación descartada", "ok");
      } catch (e) { ctx.avisar(e.message, "critico"); }
      await cargar({ foco: "detalle" });
    }

    /* ---------------------------------------------------------- simulador */

    function abrirSimulador() {
      const previo = document.activeElement;
      const canal = ui.campo({ etiqueta: "Canal", nombre: "canal", tipo: "select", opciones: [{ valor: "whatsapp", texto: "WhatsApp" }, { valor: "correo", texto: "Correo" }], valor: "whatsapp" });
      const contacto = ui.campo({ etiqueta: "Contacto (teléfono o correo)", nombre: "contacto", obligatorio: true });
      const nombre = ui.campo({ etiqueta: "Nombre", nombre: "nombre" });
      const asunto = ui.campo({ etiqueta: "Asunto", nombre: "asunto" });
      const texto = ui.campo({ etiqueta: "Mensaje", nombre: "texto", tipo: "area", filas: 4, obligatorio: true });
      const global = el("p", { class: "ui-campo__error", role: "alert" });
      global.hidden = true;
      const alternar = () => { asunto.el.hidden = canal.leer() !== "correo"; };
      canal.entrada.addEventListener("change", alternar);
      alternar();

      const dialogo = el("dialog", { class: "ui-dialogo com__dialogo", aria: { labelledby: "com-sim-titulo" } });
      const ejemplos = el("div", { class: "com__ejemplos", role: "group", aria: { label: "Ejemplos de un clic" } },
        EJEMPLOS.map((e) => ui.boton({ texto: e.titulo, variante: "secundario", tam: "sm", onclick: () => enviar(e) })));
      let enviando = false;
      async function enviar(datos) {
        if (enviando) return;
        const cuerpo = datos ?? { canal: canal.leer(), contacto: contacto.leer().trim(), nombre: nombre.leer().trim(), asunto: asunto.leer().trim(), texto: texto.leer().trim() };
        if (!datos) {
          contacto.error(cuerpo.contacto ? "" : "Escribe el teléfono o el correo");
          texto.error(cuerpo.texto ? "" : "Escribe el mensaje");
          if (!cuerpo.contacto || !cuerpo.texto) return;
        }
        enviando = true;
        const { id: _i, titulo: _t, ...limpio } = cuerpo;
        if (limpio.canal !== "correo") delete limpio.asunto;
        if (!limpio.nombre) delete limpio.nombre;
        try {
          const nueva = await ctx.api("/api/comunicaciones/simular", "POST", limpio);
          dialogo.close("ok");
          est.canal = "todos";
          est.id = nueva.id;
          est.movilDetalle = true;
          ctx.avisar("Mensaje simulado y contrastado con las fuentes", "ok");
          await cargar({ foco: "detalle" });
        } catch (e) {
          global.textContent = e.message;
          global.hidden = false;
          enviando = false;
        }
      }
      dialogo.append(
        el("h2", { class: "ui-dialogo__titulo", id: "com-sim-titulo" }, "Simular un mensaje"),
        el("p", { class: "ui-dialogo__texto" }, "Entra como si lo hubiera enviado un cliente y se contrasta con las fuentes."),
        el("p", { class: "com__ejemplos-titulo" }, "Ejemplos de un clic"), ejemplos,
        el("form", { class: "com__form", novalidate: true, onsubmit: (e) => { e.preventDefault(); enviar(null); } },
          canal.el, contacto.el, nombre.el, asunto.el, texto.el, global,
          el("div", { class: "ui-dialogo__acciones" },
            ui.boton({ texto: "Cancelar", variante: "secundario", onclick: () => dialogo.close("no") }),
            ui.boton({ texto: "Simular el mensaje", variante: "cta", tipo: "submit" }))));
      dialogo.addEventListener("close", () => { dialogo.remove(); (previo?.isConnected ? previo : zonaDetalle).focus?.(); });
      dialogo.addEventListener("click", (e) => { if (e.target === dialogo) dialogo.close("no"); });
      document.body.append(dialogo);
      dialogo.showModal();
    }

    /* ---------------------------------------------------------- arranque */

    pintarLista();
    pintarDetalle();
    await cargar();
    if (ctx.params.simular === "1") abrirSimulador();
    return { destruir() { document.querySelectorAll("dialog.com__dialogo").forEach((d) => d.remove()); } };
  },
};
