/* Sección "Estancias". La construye el agente estancias (ver design/CONTRATO-CORE.md). Este stub solo comprueba el montaje y la navegación. */
export default {
  id: "estancias",
  async montar(contenedor, ctx) {
    ctx.barra({ titulo: "Estancias", subtitulo: "Estado de cada estancia en cada sistema" });
    contenedor.append(ctx.ui.panel({
      titulo: "Sección pendiente de construir",
      subtitulo: "La construye el agente estancias.",
      hijos: [ctx.ui.vacio({ icono: "layers", titulo: "Todavía no hay nada aquí", texto: "El menú, la barra y los componentes ya funcionan." })],
    }));
  },
};
