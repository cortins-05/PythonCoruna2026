/* Sección "Recepción". La construye el agente recepcion-lista (ver design/CONTRATO.md). Este stub solo comprueba el montaje y la navegación. */
import { crearPasos, crearRegistro } from "./recepcion-pasos.js";

export default {
  id: "recepcion",
  async montar(contenedor, ctx) {
    ctx.barra({ titulo: "Recepción", subtitulo: "Estancias, check-in y check-out" });
    void crearPasos; void crearRegistro;
    contenedor.append(ctx.ui.panel({
      titulo: "Sección pendiente de construir",
      subtitulo: "La construye el agente recepcion-lista.",
      hijos: [ctx.ui.vacio({
        icono: "layers", titulo: "Todavía no hay nada aquí",
        texto: "El menú, la barra y los componentes ya funcionan. Mira la guía de estilo para ver todo lo que puedes usar.",
        accion: { texto: "Abrir la guía de estilo", icono: "layers", onclick: () => ctx.navegar("galeria") },
      })],
    }));
  },
};
