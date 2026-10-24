/* Sección "Mensajes". La construye el agente mensajes (ver design/CONTRATO.md). Este stub solo comprueba el montaje y la navegación. */
export default {
  id: "mensajes",
  async montar(contenedor, ctx) {
    ctx.barra({ titulo: "Mensajes", subtitulo: "WhatsApp y correo" });
    contenedor.append(ctx.ui.panel({
      titulo: "Sección pendiente de construir",
      subtitulo: "La construye el agente mensajes.",
      hijos: [ctx.ui.vacio({
        icono: "layers", titulo: "Todavía no hay nada aquí",
        texto: "El menú, la barra y los componentes ya funcionan. Mira la guía de estilo para ver todo lo que puedes usar.",
        accion: { texto: "Abrir la guía de estilo", icono: "layers", onclick: () => ctx.navegar("galeria") },
      })],
    }));
  },
};
