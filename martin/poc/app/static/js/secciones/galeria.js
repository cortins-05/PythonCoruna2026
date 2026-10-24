/*
  Guía de estilo viva: enseña cada componente con sus variantes y reproduce las dos composiciones de las referencias
  (detalle de ticket y navegación por pestañas). Sirve de comprobación visual para cualquier cambio en tokens o componentes.
*/
const COLORES = [
  ["Fondo", "--c-bg"], ["Superficie", "--c-surface"], ["Superficie 2", "--c-surface-2"], ["Superficie 3", "--c-surface-3"],
  ["Borde", "--c-borde"], ["Borde fuerte", "--c-borde-fuerte"], ["Borde de control", "--c-borde-control"],
  ["Texto", "--c-texto"], ["Texto 2", "--c-texto-2"], ["Texto 3", "--c-texto-3"],
  ["Acento", "--c-acento"], ["Acento suave", "--c-acento-suave"], ["CTA", "--c-cta"], ["Fuerte", "--c-fuerte"],
  ["OK", "--c-ok-punto"], ["Aviso", "--c-aviso-punto"], ["Crítico", "--c-critico-punto"], ["Info", "--c-info-punto"], ["Menta", "--c-menta"],
];

export default {
  id: "galeria",
  async montar(contenedor, ctx) {
    const { el, ui } = ctx;
    ctx.barra({
      titulo: "Guía de estilo",
      subtitulo: "Todos los componentes y composiciones del sistema de diseño",
      cta: { texto: "Acción principal", icono: "check", onclick: () => ctx.avisar("Solo hay una acción amarilla por vista", "ok") },
      acciones: [{ icono: "refresh", etiqueta: "Actualizar", onclick: () => ctx.avisar("Actualizado", "neutro") }],
    });

    const seccion = (titulo, subtitulo, ...hijos) => ui.panel({ titulo, subtitulo, hijos });
    const fila = (...hijos) => el("div", { class: "galeria__muestra" }, ...hijos);

    /* Composición 1: detalle, como la referencia de tickets */
    const menuDetalle = ui.botonDividido({
      texto: "Aprobar y enviar", icono: "check", onclick: () => ctx.avisar("Propuesta aprobada", "ok"),
      items: [
        { texto: "Asistencia remota", icono: "eye" }, { texto: "Ver el registro", icono: "list" },
        { texto: "Abrir notas internas", icono: "file" }, { texto: "Volver a la bandeja", icono: "arrow-left" },
      ],
    });
    const detalle = ui.panel({
      titulo: "Detalle de la propuesta",
      acciones: [ui.boton({ icono: "more-h", variante: "fantasma", etiqueta: "Más" }), ui.boton({ icono: "arrow-right", variante: "fantasma", etiqueta: "Derivar" }), menuDetalle],
      hijos: [
        ui.tabsSubrayado({ items: [{ id: "a", texto: "Actividad" }, { id: "n", texto: "Notas" }], activo: "a", etiqueta: "Detalle" }).el,
        ui.kv([
          { etiqueta: "Estado", valor: ui.chip({ texto: "Pendiente", tono: "info", punto: true }) },
          { etiqueta: "Prioridad", valor: "Alta", icono: "arrow-up", tono: "aviso" },
          { etiqueta: "Salud", valor: ui.chip({ texto: "Aviso", tono: "aviso", punto: true }) },
          { etiqueta: "Canal", valor: "WhatsApp" },
          { etiqueta: "Recibido", valor: "Hoy, 9:05" },
          { etiqueta: "Plazo", valor: "Antes de las 20:00" },
          { etiqueta: "Asignado a", valor: "Flor" },
          { etiqueta: "Estancia", valor: "1-BK-4471920" },
        ]),
      ],
    });

    /* Composición 2: navegación, como la referencia de pestañas */
    const tiles = ui.tileTabs({
      items: [{ id: "ll", texto: "Llegadas", icono: "key" }, { id: "oc", texto: "Ocupación", icono: "bed" }, { id: "me", texto: "Mensajes", icono: "message" },
        { id: "ap", texto: "Aprobar", icono: "check" }, { id: "do", texto: "Documentos", icono: "receipt" }, { id: "in", texto: "Sistema", icono: "plug" }],
      activo: "ll", onchange: (id) => ctx.avisar(`Categoría: ${id}`, "neutro"),
    });
    const subrayado = ui.tabsSubrayado({
      items: [{ id: "h", texto: "Hoy" }, { id: "m", texto: "Mañana" }, { id: "s", texto: "Semana" }, { id: "t", texto: "Todo" }], activo: "m",
    });
    const pastillas = ui.filaPastillas({
      items: [{ id: "a", texto: "DBL-STD" }, { id: "b", texto: "SGL-STD", cuenta: 2 }, { id: "c", texto: "Suites" }, { id: "d", texto: "Familiar" }], activo: "a",
      anadir: { onclick: () => ctx.avisar("Añadir filtro", "neutro") }, mas: { onclick: () => ctx.avisar("Más opciones", "neutro") },
    });
    const tarjetas = ui.carrusel({
      ancho: 250,
      items: [
        ui.tarjeta({ icono: "key", titulo: "Hacer un check-in", subtitulo: "Documento, pago y parte en un solo flujo.", variante: "punteada", seleccionada: true, onclick: () => {} }),
        ui.tarjeta({ icono: "receipt", titulo: "Emitir una factura", subtitulo: "Borrador desde la estancia y envío por correo.", variante: "punteada", onclick: () => {} }),
        ui.tarjeta({ icono: "bed", titulo: "Cerrar disponibilidad", subtitulo: "Propuesta con aprobación antes de tocar RoomCloud.", variante: "punteada", onclick: () => {} }),
        ui.tarjeta({ icono: "message", titulo: "Responder un mensaje", subtitulo: "Plantilla validada y aprobada por recepción.", variante: "punteada", onclick: () => {} }),
      ],
    });

    /* Componentes sueltos */
    const botones = fila(
      ui.boton({ texto: "Acción principal", variante: "cta", icono: "check" }), ui.boton({ texto: "Oscuro", variante: "oscuro" }),
      ui.boton({ texto: "Secundario", variante: "secundario" }), ui.boton({ texto: "Peligro", variante: "peligro", icono: "trash" }),
      ui.boton({ icono: "more-h", variante: "fantasma", etiqueta: "Más" }), ui.boton({ texto: "Pequeño", tam: "sm" }),
      ui.boton({ texto: "Cargando", cargando: true }), ui.boton({ texto: "Desactivado", desactivado: true }));
    const chips = fila(
      ui.chip({ texto: "Pendiente de llegada", tono: "aviso", punto: true }), ui.chip({ texto: "Parte enviado", tono: "ok", punto: true }),
      ui.chip({ texto: "Fuera de plazo", tono: "critico", punto: true }), ui.chip({ texto: "En curso", tono: "info", punto: true }),
      ui.chip({ texto: "Simulado", tono: "neutro" }), ui.insignia(3), ui.insignia(12, { tono: "aviso" }), ui.insignia(1, { tono: "critico" }), ui.insignia(7, { tono: "acento" }));
    const tarjetasSueltas = el("div", { class: "u-rejilla" },
      ui.tarjeta({ titulo: "Tarjeta normal", subtitulo: "Borde fino y esquinas redondeadas", chips: [{ texto: "Aviso", tono: "aviso", punto: true }] }),
      ui.tarjeta({ titulo: "Seleccionada", subtitulo: "Relleno menta y borde verde", seleccionada: true, onclick: () => {} }),
      ui.tarjeta({ titulo: "Punteada", subtitulo: "Textura de puntos sutil", variante: "punteada", icono: "sparkles" }),
      ui.tarjeta({ titulo: "Horizontal", subtitulo: "Icono a la izquierda", icono: "mail", direccion: "horizontal" }));

    const campos = el("div", { class: "u-rejilla" },
      ui.campo({ etiqueta: "Nombre", nombre: "n", placeholder: "Ana", obligatorio: true }).el,
      ui.campo({ etiqueta: "Tipo de habitación", nombre: "t", tipo: "select", opciones: ["DBL-STD", "SGL-STD"], valor: "DBL-STD" }).el,
      ui.campo({ etiqueta: "Llegada", nombre: "l", tipo: "fecha", valor: "2026-10-24" }).el,
      (() => { const c = ui.campo({ etiqueta: "Documento", nombre: "d", valor: "12345678A", ayuda: "Letra y ocho dígitos" }); c.error("La letra del NIF no cuadra"); return c.el; })(),
      ui.campo({ etiqueta: "Notas", nombre: "no", tipo: "area", filas: 2, placeholder: "Texto libre" }).el);

    const tabla = ui.tabla({
      etiqueta: "Ejemplo de tabla",
      columnas: [{ clave: "n", titulo: "Concepto" }, { clave: "c", titulo: "Cantidad", alinear: "derecha" }, { clave: "i", titulo: "Importe", alinear: "derecha" },
        { clave: "e", titulo: "Estado", render: (f) => ui.chip({ texto: f.e, tono: f.t, punto: true }) }],
      filas: [{ n: "Alojamiento DBL-STD", c: 2, i: ui.moneda(192.73), e: "Emitido", t: "ok" }, { n: "Desayuno", c: 2, i: ui.moneda(18), e: "Borrador", t: "aviso" }],
      onfila: () => ctx.avisar("Fila pulsada", "neutro"),
    });

    const pasos = ui.pasos([
      { estado: "hecho", titulo: "Documento y datos", detalle: "NIF 12345678Z" }, { estado: "hecho", titulo: "Pago y empresa", detalle: "Tarjeta · Atlántico Consultores SL" },
      { estado: "actual", titulo: "Parte de viajeros", detalle: "Quedan 20 h para enviarlo" }, { estado: "pendiente", titulo: "Alta en OfiHotel" }, { estado: "bloqueado", titulo: "Check-out", detalle: "Falta el parte" },
    ]);

    const menuSuelto = ui.boton({ texto: "Abrir el menú oscuro", icono: "more-h" });
    const menu = ui.menuOscuro({ ancla: menuSuelto, alineacion: "inicio", items: [
      { texto: "Leer reservas de RoomCloud", icono: "refresh" }, { texto: "Ver el registro", icono: "list" }, { separador: true }, { texto: "Reiniciar", icono: "trash", peligro: true }] });
    menuSuelto.addEventListener("click", () => menu.alternar());
    const avisos = fila(menuSuelto,
      ui.boton({ texto: "Mostrar aviso", onclick: () => ctx.avisar("Parte enviado (simulado)", "ok") }),
      ui.boton({ texto: "Aviso crítico", onclick: () => ctx.avisar("El parte está fuera de plazo", "critico") }),
      ui.boton({ texto: "Pedir confirmación", variante: "oscuro", onclick: async () => ctx.avisar((await ctx.confirmar({ titulo: "Enviar el parte", texto: "Esta acción compromete legalmente al hotel.", confirmar: "Sí, enviar" })) ? "Confirmado" : "Cancelado") }));

    const colores = el("div", { class: "galeria__colores" }, COLORES.map(([nombre, variable]) => el("div", { class: "galeria__color" },
      el("i", { estilo: { background: `var(${variable})` } }), el("span", null, `${nombre} ${variable}`))));
    const iconos = el("div", { class: "galeria__iconos" }, ui.nombresIconos().map((n) => el("div", { class: "galeria__icono" }, ui.icono(n, { tam: 22 }), n)));
    const vacios = el("div", { class: "u-rejilla" },
      ui.vacio({ icono: "inbox", titulo: "Nada pendiente", texto: "Cuando llegue algo que necesite aprobación aparecerá aquí." }), ui.esqueleto({ lineas: 4 }));

    contenedor.append(el("div", { class: "sec-galeria galeria__pila" },
      el("div", { class: "u-dos-paneles" }, detalle, ui.panel({ titulo: "Navegación", subtitulo: "Tiles, pestañas con muesca, pastillas y carrusel", hijos: [tiles.el, subrayado.el, pastillas.el, tarjetas] })),
      seccion("Colores", "Tokens de color del tema activo (cambia el tema desde el menú de abajo a la izquierda)", colores),
      seccion("Botones", "Una sola acción amarilla por vista", botones),
      seccion("Chips e insignias", "El estado siempre lleva texto, no solo color", chips),
      seccion("Tarjetas", "Normal, seleccionada, punteada y horizontal", tarjetasSueltas),
      seccion("Formularios", "Etiqueta encima, borde de control con contraste y mensajes de error", campos),
      seccion("Tabla", "Cabeceras de columna y filas interactivas con teclado", tabla),
      seccion("Pasos", "Flujo vertical con marcador y conector", pasos),
      seccion("Menús, avisos y diálogos", "Menú flotante oscuro, toast y confirmación propia", avisos),
      seccion("Estados vacío y de carga", "", vacios),
      seccion("Iconos", `${ui.nombresIconos().length} iconos de trazo`, iconos)));
  },
};
