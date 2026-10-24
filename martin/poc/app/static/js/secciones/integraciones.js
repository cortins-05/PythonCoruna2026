/* Sección "Integraciones". La construye el agente integraciones-front (ver design/CONTRATO.md). Este stub solo comprueba el montaje y la navegación. */
export default {
  id: "integraciones",
  async montar(contenedor, ctx) {
    ctx.barra({ titulo: "Integraciones", subtitulo: "Estado de cada conexión" });
    contenedor.append(ctx.ui.panel({
      titulo: "Sección pendiente de construir",
      subtitulo: "La construye el agente integraciones-front.",
      hijos: [ctx.ui.vacio({
        icono: "layers", titulo: "Todavía no hay nada aquí",
        texto: "El menú, la barra y los componentes ya funcionan. Mira la guía de estilo para ver todo lo que puedes usar.",
        accion: { texto: "Abrir la guía de estilo", icono: "layers", onclick: () => ctx.navegar("galeria") },
      })],
    }));
  },
};
