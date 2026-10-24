/* Sección "Comunicaciones". La construye el agente comunicaciones (ver design/CONTRATO-CORE.md). Este stub solo comprueba el montaje y la navegación. */
export default {
  id: "comunicaciones",
  async montar(contenedor, ctx) {
    ctx.barra({ titulo: "Comunicaciones", subtitulo: "Peticiones contrastadas, listas para confirmar" });
    contenedor.append(ctx.ui.panel({
      titulo: "Sección pendiente de construir",
      subtitulo: "La construye el agente comunicaciones.",
      hijos: [ctx.ui.vacio({ icono: "layers", titulo: "Todavía no hay nada aquí", texto: "El menú, la barra y los componentes ya funcionan." })],
    }));
  },
};
