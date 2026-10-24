/* Sección "Bandeja". La construye el agente bandeja (ver design/CONTRATO.md). Este stub solo comprueba el montaje y la navegación. */
export default {
  id: "bandeja",
  async montar(contenedor, ctx) {
    ctx.barra({ titulo: "Bandeja", subtitulo: "Lo que llega y lo que espera aprobación" });
    contenedor.append(ctx.ui.panel({
      titulo: "Sección pendiente de construir",
      subtitulo: "La construye el agente bandeja.",
      hijos: [ctx.ui.vacio({
        icono: "layers", titulo: "Todavía no hay nada aquí",
        texto: "El menú, la barra y los componentes ya funcionan. Mira la guía de estilo para ver todo lo que puedes usar.",
        accion: { texto: "Abrir la guía de estilo", icono: "layers", onclick: () => ctx.navegar("galeria") },
      })],
    }));
  },
};
