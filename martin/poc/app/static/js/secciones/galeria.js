/*
  Guía de estilo viva: enseña cada componente con sus variantes y reproduce las dos composiciones de las referencias
  (detalle de ticket y navegación por pestañas). Sirve de comprobación visual para cualquier cambio en tokens o componentes.
*/
import { chipSemaforo, pastillaNivel, escalera, chipVeredicto, chipsSistemas, NOMBRE_COLOR, ICONO_FUENTE, NOMBRE_FUENTE } from "../ui-hotel.js";

/* Datos de ejemplo escritos aquí para que la guía no dependa de la API */
const PRIORIDADES = {
  niveles: [
    { nivel: 1, id: "roomcloud", nombre: "RoomCloud", tipo: "firme", icono: "refresh", descripcion: "Reservas de Booking, Expedia y la web, con garantía de pago" },
    { nivel: 2, id: "ofihotel", nombre: "OfiHotel", tipo: "firme", icono: "building", descripcion: "Lo registrado en el programa del hotel, con los datos de ayer" },
    { nivel: 3, id: "recepcion", nombre: "Recepción", tipo: "firme", icono: "door", descripcion: "Walk-ins y peticiones que recepción ya ha confirmado" },
    { nivel: 4, id: "correo", nombre: "Correo", tipo: "peticion", icono: "mail", descripcion: "Petición de fechas sin confirmar" },
    { nivel: 5, id: "whatsapp", nombre: "WhatsApp", tipo: "peticion", icono: "message", descripcion: "Petición de fechas sin confirmar" },
  ],
  reglas: [
    "Lo firme bloquea la habitación y una petición nunca lo desplaza.",
    "Entre peticiones gana el nivel más alto y, a igual nivel, la que llegó antes.",
    "Si entra una reserva de RoomCloud que ocupa el hueco, la petición pasa a No disponible y se avisa.",
  ],
};
const SISTEMAS = {
  ejemplo: { roomcloud: { estado: "sincronizado" }, ofihotel: { estado: "por_migrar" }, documentacion: { estado: "parte_pendiente" } },
  vencido: { roomcloud: { estado: "sincronizado" }, ofihotel: { estado: "migrado" }, documentacion: { estado: "parte_vencido" } },
};
const PASOS_PROCESO = [
  { titulo: "Llega el mensaje", fuente: "whatsapp", detalle: "Una persona pide una habitación doble del 28 al 30 de octubre.", dato: "Prioridad 5 (WhatsApp)" },
  { titulo: "Se contrasta con las demás fuentes", fuente: "ofihotel", detalle: "Se cuentan las habitaciones ocupadas noche a noche.", dato: "2 libres por noche" },
  { titulo: "Se prepara la respuesta", fuente: "sistema", detalle: "La respuesta sale por el mismo canal y queda lista para confirmar.", dato: "Respuesta en español" },
  { titulo: "Recepción confirma", fuente: "recepcion", detalle: "Flor revisa el borrador y lo envía (simulado).", dato: "Prioridad 3 (Recepción)" },
];

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

    const seccion = (id, titulo, subtitulo, ...hijos) => ui.panel({ id: `gal-${id}`, titulo, subtitulo, hijos });
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
      ui.boton({ icono: "more-h", variante: "fantasma", etiqueta: "Más" }), ui.boton({ texto: "Volver", icono: "arrow-left", variante: "texto" }), ui.boton({ texto: "Pequeño", tam: "sm" }),
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

    /* Semáforo, prioridad, veredicto y sistemas del hotel */
    const semaforo = fila(...Object.keys(NOMBRE_COLOR).map((c) => chipSemaforo(c)));
    const mini = (n) => ({ nivel: n.nivel, fuente: n.nombre, id: n.id, tipo: n.tipo });
    const niveles = fila(...PRIORIDADES.niveles.map((n) => pastillaNivel(mini(n))),
      ...PRIORIDADES.niveles.map((n) => pastillaNivel(mini(n), { compacta: true })));
    const escaleras = el("div", { class: "u-dos-paneles galeria__escaleras" },
      el("div", null, el("h3", { class: "galeria__sub" }, "Completa, con el nivel de correo resaltado"), escalera(PRIORIDADES, { resaltar: "correo" })),
      el("div", null, el("h3", { class: "galeria__sub" }, "Compacta, sin descripciones ni reglas"), escalera(PRIORIDADES, { compacta: true, reglas: false })));
    const veredictos = fila(...["disponible", "ajustado", "en_competencia", "no_disponible", "sin_datos"].map((v) => chipVeredicto(v)));
    const sistemas = el("div", { class: "galeria__pila-chica" }, chipsSistemas(SISTEMAS.ejemplo), chipsSistemas(SISTEMAS.vencido));
    const fuentes = fila(...Object.keys(NOMBRE_FUENTE).map((f) => el("span", { class: "galeria__fuente" }, ui.icono(ICONO_FUENTE[f], { tam: 16 }), NOMBRE_FUENTE[f])));

    /* Proceso animado: los pasos aparecen uno a uno y con movimiento reducido salen de golpe */
    const zonaProceso = el("div", { class: "galeria__proceso", aria: { live: "polite" } });
    let temporizador = null;
    const reducido = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const pintarProceso = (n) => {
      zonaProceso.replaceChildren(ui.pasos(PASOS_PROCESO.map((p, i) => ({
        estado: i < n - 1 ? "hecho" : i === n - 1 ? "actual" : "pendiente", titulo: p.titulo, detalle: p.detalle,
        contenido: i < n ? el("div", { class: "galeria__dato" }, ui.icono(ICONO_FUENTE[p.fuente] ?? "alert", { tam: 14 }), p.dato) : null,
      }))));
    };
    const lanzarProceso = () => {
      clearInterval(temporizador);
      if (reducido()) { pintarProceso(PASOS_PROCESO.length); return; }
      let n = 1;
      pintarProceso(n);
      temporizador = setInterval(() => { n += 1; pintarProceso(n); if (n >= PASOS_PROCESO.length) clearInterval(temporizador); }, 600);
    };
    lanzarProceso();
    const proceso = el("div", null, zonaProceso, el("div", { class: "galeria__repetir" }, ui.boton({ texto: "Repetir el proceso", icono: "refresh", tam: "sm", onclick: lanzarProceso })));

    const burbujas = el("div", { class: "galeria__burbujas" },
      el("div", { class: "gal-burbuja gal-burbuja--whatsapp" },
        el("div", { class: "gal-burbuja__cab" }, ui.icono("message", { tam: 14 }), "WhatsApp · Claire Dubois"),
        el("p", { class: "gal-burbuja__texto" }, "Buenos días, ¿tenéis una habitación doble del 28 al 30 de octubre?")),
      el("div", { class: "gal-burbuja gal-burbuja--correo" },
        el("div", { class: "gal-burbuja__cab" }, ui.icono("mail", { tam: 14 }), "Respuesta por el mismo canal (simulada)"),
        el("p", { class: "gal-burbuja__texto" }, "Hola Claire, tenemos una doble libre esas dos noches por 192,73 euros. Si quieres, te la reservamos.")));

    /* Índice de la guía: cada botón lleva a su sección sin tocar el hash de la ruta */
    const indice = [["navegacion", "Navegación"], ["colores", "Colores"], ["botones", "Botones"], ["chips", "Chips"], ["tarjetas", "Tarjetas"],
      ["formularios", "Formularios"], ["tabla", "Tabla"], ["pasos", "Pasos"], ["menus", "Menús y avisos"], ["vacios", "Vacío y carga"],
      ["semaforo", "Semáforo"], ["prioridad", "Prioridad"], ["veredicto", "Veredicto"], ["sistemas", "Sistemas"], ["proceso", "Proceso"], ["burbujas", "Burbujas"], ["iconos", "Iconos"]];
    const nav = el("nav", { class: "galeria__indice", aria: { label: "Secciones de la guía" } }, indice.map(([id, texto]) =>
      ui.pastilla({ texto, onclick: () => document.getElementById(`gal-${id}`)?.scrollIntoView({ behavior: reducido() ? "auto" : "smooth", block: "start" }) })));

    contenedor.append(el("div", { class: "sec-galeria galeria__pila" },
      nav,
      el("div", { id: "gal-navegacion", class: "u-dos-paneles" }, detalle, ui.panel({ titulo: "Navegación", subtitulo: "Tiles, pestañas con muesca, pastillas y carrusel", hijos: [tiles.el, subrayado.el, pastillas.el, tarjetas] })),
      seccion("colores", "Colores", "Tokens de color del tema activo (cambia el tema desde el menú de abajo a la izquierda)", colores),
      seccion("botones", "Botones", "Una sola acción amarilla por vista", botones),
      seccion("chips", "Chips e insignias", "El estado siempre lleva texto, no solo color", chips),
      seccion("tarjetas", "Tarjetas", "Normal, seleccionada, punteada y horizontal", tarjetasSueltas),
      seccion("formularios", "Formularios", "Etiqueta encima, borde de control con contraste y mensajes de error", campos),
      seccion("tabla", "Tabla", "Cabeceras de columna y filas interactivas con teclado", tabla),
      seccion("pasos", "Pasos", "Flujo vertical con marcador y conector", pasos),
      seccion("menus", "Menús, avisos y diálogos", "Menú flotante oscuro, toast y confirmación propia", avisos),
      seccion("vacios", "Estados vacío y de carga", "", vacios),
      seccion("semaforo", "Semáforo de estancias", "Seis colores, cada uno con su texto", semaforo),
      seccion("prioridad", "Prioridad de las fuentes", "Pastilla con nombre, pastilla compacta y escalera completa y compacta", niveles, escaleras),
      seccion("veredicto", "Veredicto de una petición", "Cinco estados, de disponible a sin datos", veredictos),
      seccion("sistemas", "Estado por sistema", "RoomCloud, OfiHotel y documentación de una estancia, y el icono de cada fuente", sistemas, fuentes),
      seccion("proceso", "Proceso animado", "Los pasos aparecen uno a uno y con movimiento reducido salen de golpe", proceso),
      seccion("burbujas", "Burbujas de respuesta", "Mensaje recibido por WhatsApp y respuesta por el canal de origen", burbujas),
      seccion("iconos", "Iconos", `${ui.nombresIconos().length} iconos de trazo`, iconos)));
  },
};
