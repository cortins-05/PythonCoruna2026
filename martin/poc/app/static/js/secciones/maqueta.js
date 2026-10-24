/*
  Maqueta de la pestaña del asistente con datos de ejemplo escritos a mano. Sirve para juzgar la línea visual del chat (bienvenida con baldosas,
  pastillas y tarjetas guiadas, y respuestas con tarjetas, flujos, tablas, documentos y propuestas) antes de construir la versión real.
  No llama a la API. La versión real la construyen los agentes asistente-shell y asistente-bloques.
*/
const PREGUNTAS = {
  llegadas: ["¿Qué llegadas hay hoy?", "¿Quién no ha hecho el check-in?", "Abre el check-in de Ana"],
  ocupacion: ["¿Cómo está la ocupación esta semana?", "¿Queda algo libre el 24 de octubre?", "Añade una reserva física"],
  mensajes: ["¿Qué mensajes están sin responder?", "¿Qué ha dicho Ana por WhatsApp?", "Responde a Claire sobre su factura"],
  aprobar: ["¿Qué hay pendiente de aprobar?", "Aprueba la respuesta a Ana", "¿Por qué se propuso cerrar DBL-STD?"],
  documentos: ["Prepárame la factura de Ana", "¿Qué albaranes están en borrador?", "Envía la factura de Claire"],
};

const FLUJOS = [
  { icono: "key", titulo: "Hacer un check-in", texto: "Documento, pago y parte de viajeros en un solo flujo." },
  { icono: "receipt", titulo: "Emitir una factura", texto: "Borrador desde la estancia y envío por correo." },
  { icono: "bed", titulo: "Cerrar disponibilidad", texto: "Propuesta con aprobación antes de tocar RoomCloud." },
  { icono: "message", titulo: "Responder un mensaje", texto: "Plantilla validada y aprobada por recepción." },
];

export default {
  id: "maqueta",
  async montar(contenedor, ctx) {
    const { el, ui } = ctx;
    ctx.barra({ titulo: "Asistente", subtitulo: "Habla con la información del hotel", acciones: [{ icono: "plus", texto: "Nueva conversación" }] });

    /* Bienvenida: baldosas, pastillas y carrusel de flujos, igual que la referencia de pestañas */
    const pastillas = el("div", { class: "maq__pastillas" });
    const pintarPreguntas = (id) => {
      pastillas.replaceChildren(...PREGUNTAS[id].map((p) => ui.pastilla({ texto: p })));
    };
    const tiles = ui.tileTabs({
      items: [{ id: "llegadas", texto: "Llegadas", icono: "key" }, { id: "ocupacion", texto: "Ocupación", icono: "bed" }, { id: "mensajes", texto: "Mensajes", icono: "message" },
        { id: "aprobar", texto: "Aprobar", icono: "check" }, { id: "documentos", texto: "Documentos", icono: "receipt" }],
      activo: "documentos", onchange: pintarPreguntas, etiqueta: "Qué quieres hacer",
    });
    pintarPreguntas("documentos");
    const bienvenida = ui.panel({
      variante: "punteada",
      hijos: [el("div", { class: "maq__bienvenida" },
        el("div", { class: "maq__saludo" }, el("h2", null, "Hola, Flor"),
          el("p", null, "Pregúntame por las llegadas, la ocupación, los mensajes o los documentos, y te enseño lo que necesites para actuar sin salir de aquí.")),
        tiles.el, pastillas,
        ui.carrusel({ ancho: 250, etiqueta: "Flujos guiados", items: FLUJOS.map((f, i) => ui.tarjeta({ icono: f.icono, titulo: f.titulo, subtitulo: f.texto, seleccionada: i === 1, onclick: () => {} })) }))],
    });

    /* Piezas de la conversación */
    const usuario = (texto) => el("div", { class: "maq__usuario" }, texto);
    const asistente = (texto, ...bloques) => el("div", { class: "maq__asistente" },
      el("span", { class: "maq__yo", aria: { hidden: "true" } }, ui.icono("sparkles", { tam: 18 })),
      el("div", { class: "maq__contenido" }, el("p", { class: "maq__texto" }, texto), ...bloques));

    const kpis = el("div", { class: "maq__kpis" }, [
      { e: "Llegadas de hoy", v: "3", d: "1 con check-in hecho", t: "neutro" },
      { e: "Partes sin enviar", v: "1", d: "vence en 20 h", t: "aviso" },
      { e: "Ocupación de hoy", v: "100 %", d: "3 de 3 DBL-STD", t: "critico" },
    ].map((k) => el("div", { class: `maq__kpi is-${k.t}` }, el("span", { class: "maq__kpi-etiqueta" }, k.e), el("strong", { class: "maq__kpi-valor" }, k.v), el("span", { class: "maq__kpi-detalle" }, k.d))));

    const reserva = (titulo, sub, chips, campos) => ui.tarjeta({
      titulo, subtitulo: sub, chips, cuerpo: ui.kv(campos, { columnas: 2 }),
      pie: [ui.boton({ texto: "Abrir", icono: "arrow-up-right", tam: "sm" })],
    });
    const reservas = el("div", { class: "maq__reservas" },
      reserva("Ana Pereira Lage", "24 oct a 26 oct · DBL-STD", [{ texto: "En casa", tono: "ok", punto: true }, { texto: "Parte pendiente", tono: "aviso", punto: true }],
        [{ etiqueta: "Origen", valor: "RoomCloud" }, { etiqueta: "Trabajo", valor: "Sí" }]),
      reserva("Marcos Vilas", "24 oct a 25 oct · SGL-STD", [{ texto: "Pendiente de llegada", tono: "info", punto: true }],
        [{ etiqueta: "Origen", valor: "Web propia" }, { etiqueta: "Trabajo", valor: "No" }]),
      reserva("Claire Dubois", "24 oct a 27 oct · DBL-STD", [{ texto: "Pendiente de llegada", tono: "info", punto: true }],
        [{ etiqueta: "Origen", valor: "Expedia" }, { etiqueta: "Trabajo", valor: "No" }]));

    const documento = ui.panel({
      titulo: "Factura de Ana Pereira", subtitulo: "Borrador creado desde la estancia 1-BK-4471920",
      acciones: [ui.chip({ texto: "Borrador", tono: "aviso", punto: true }), ui.chip({ texto: "Sin validez fiscal", tono: "neutro", icono: "info" })],
      hijos: [
        ui.tabla({
          etiqueta: "Líneas de la factura",
          columnas: [{ clave: "c", titulo: "Concepto" }, { clave: "n", titulo: "Noches", alinear: "derecha" }, { clave: "i", titulo: "Importe", alinear: "derecha" }],
          filas: [{ c: "Alojamiento DBL-STD", n: 2, i: ui.moneda(192.73) }, { c: "IVA 10 %", n: "", i: ui.moneda(19.27) }],
        }),
        ui.kv([{ etiqueta: "Receptor", valor: "Atlántico Consultores SL" }, { etiqueta: "Correo", valor: "facturas@atlantico.example" }, { etiqueta: "Total", valor: ui.moneda(212) }], { columnas: 3 }),
        el("div", { class: "u-fila" }, ui.boton({ texto: "Abrir documento", icono: "arrow-up-right" }), ui.boton({ texto: "Emitir", icono: "check", variante: "oscuro" }),
          ui.boton({ icono: "more-h", variante: "fantasma", etiqueta: "Más acciones" })),
      ],
    });

    const propuesta = ui.panel({
      titulo: "Pendiente de tu aprobación", subtitulo: "Nada sale hasta que lo apruebes",
      acciones: [ui.chip({ texto: "Correo conocido de la estancia", tono: "ok", icono: "shield" })],
      variante: "suave",
      hijos: [
        el("blockquote", { class: "maq__cita" }, "Emitir la factura de la estancia 1-BK-4471920 y enviarla a facturas@atlantico.example"),
        ui.kv([{ etiqueta: "Destino", valor: "Documentos y correo" }, { etiqueta: "Propuesta por", valor: "Asistente" }]),
        el("div", { class: "u-fila" }, ui.boton({ texto: "Aprobar y enviar", icono: "check", variante: "cta" }), ui.boton({ texto: "Rechazar" })),
      ],
    });

    const celdas = (libres, cerrado) => ui.chip({ texto: libres === 0 ? "Completo" : `${libres} libre${libres === 1 ? "" : "s"}`, tono: libres === 0 ? "critico" : libres === 1 ? "aviso" : "ok", punto: true, clase: cerrado ? "maq__cerrado" : "" });
    const dias = ["24 oct", "25 oct", "26 oct", "27 oct", "28 oct"];
    const ocupacion = ui.panel({
      titulo: "Ocupación de los próximos cinco días", subtitulo: "Habitaciones libres por tipo",
      hijos: [el("div", { class: "maq__ocup" },
        el("div", { class: "maq__ocup-fila maq__ocup-cabecera" }, el("span", null, "Tipo"), ...dias.map((d) => el("span", null, d))),
        el("div", { class: "maq__ocup-fila" }, el("strong", null, "DBL-STD"), celdas(0, true), celdas(1), celdas(2), celdas(3), celdas(3)),
        el("div", { class: "maq__ocup-fila" }, el("strong", null, "SGL-STD"), celdas(1), celdas(2), celdas(2), celdas(2), celdas(2)))],
    });

    const flujo = ui.panel({
      titulo: "Check-in de Ana Pereira", subtitulo: "Cada paso se abre en Recepción",
      hijos: [ui.pasos([
        { estado: "hecho", titulo: "Documento y datos", detalle: "NIF 12345678Z leído y confirmado" },
        { estado: "hecho", titulo: "Pago y empresa", detalle: "Tarjeta · Atlántico Consultores SL" },
        { estado: "actual", titulo: "Parte de viajeros", detalle: "Quedan 20 h para enviarlo", contenido: el("div", { class: "u-fila" }, ui.boton({ texto: "Revisar y enviar", tam: "sm", variante: "oscuro", icono: "arrow-up-right" })) },
        { estado: "pendiente", titulo: "Alta en OfiHotel" },
      ])],
    });

    const sugerencias = el("div", { class: "maq__pastillas" }, ["¿Cómo está la ocupación?", "¿Qué partes están pendientes?", "Cierra DBL-STD el 24"].map((t) => ui.pastilla({ texto: t, icono: "sparkles" })));

    const compositor = el("div", { class: "maq__compositor" },
      ui.boton({ icono: "paperclip", variante: "fantasma", etiqueta: "Adjuntar", tam: "sm" }),
      el("input", { type: "text", placeholder: "Pregunta algo o pide una acción", "aria-label": "Mensaje para el asistente" }),
      ui.boton({ icono: "send", variante: "oscuro", etiqueta: "Enviar" }));

    contenedor.append(el("div", { class: "sec-maqueta" },
      bienvenida,
      usuario("¿Qué llegadas hay hoy?"),
      asistente("Hoy llegan tres huéspedes y Ana Pereira ya ha hecho el check-in, aunque su parte de viajeros sigue sin enviar.", kpis, reservas),
      usuario("Prepárame la factura de Ana"),
      asistente("He preparado un borrador con los datos de su estancia. Para emitirla y enviarla hace falta tu aprobación.", documento, propuesta),
      usuario("¿Cómo está la ocupación esta semana?"),
      asistente("El 24 de octubre DBL-STD está completo, así que he propuesto cerrar la venta en RoomCloud.", ocupacion, flujo, sugerencias),
      compositor));
  },
};
