/* Sección "Fuente única". La construye el agente fuente (ver design/CONTRATO-CORE.md). Este stub solo comprueba el montaje y la navegación. */
export default {
  id: "fuente",
  async montar(contenedor, ctx) {
    ctx.barra({ titulo: "Fuente única", subtitulo: "Todo lo que entra, en un solo sitio" });
    contenedor.append(ctx.ui.panel({
      titulo: "Sección pendiente de construir",
      subtitulo: "La construye el agente fuente.",
      hijos: [ctx.ui.vacio({ icono: "layers", titulo: "Todavía no hay nada aquí", texto: "El menú, la barra y los componentes ya funcionan." })],
    }));
  },
};
