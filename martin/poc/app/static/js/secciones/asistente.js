/* Sección "Asistente". La construye el agente asistente-shell (ver design/CONTRATO.md). Este stub solo comprueba el montaje y la navegación. */
import { renderBloque } from "./asistente-bloques.js";

export default {
  id: "asistente",
  async montar(contenedor, ctx) {
    ctx.barra({ titulo: "Asistente", subtitulo: "Habla con la información del hotel" });
    contenedor.append(renderBloque({ tipo: "aviso", tono: "info", titulo: "Pendiente", texto: "El pintado de bloques lo construye asistente-bloques." }, { el: ctx.el, ui: ctx.ui, ejecutar: async () => ({ ok: false }) }));
    contenedor.append(ctx.ui.panel({
      titulo: "Sección pendiente de construir",
      subtitulo: "La construye el agente asistente-shell.",
      hijos: [ctx.ui.vacio({
        icono: "layers", titulo: "Todavía no hay nada aquí",
        texto: "El menú, la barra y los componentes ya funcionan. Mira la guía de estilo para ver todo lo que puedes usar.",
        accion: { texto: "Abrir la guía de estilo", icono: "layers", onclick: () => ctx.navegar("galeria") },
      })],
    }));
  },
};
