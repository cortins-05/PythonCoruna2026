/*
  Manifiesto de secciones: el menú lateral y el router salen de aquí. Cada sección es un módulo en js/secciones/<id>.js con
  export default { id, montar(contenedor, ctx) }, y sus estilos propios en css/secciones/<nombre>.css (todos los listados en `css` deben existir).
*/
export const SECCION_INICIAL = "comunicaciones";

export const GRUPOS = [
  { id: "principal", titulo: null },
  { id: "operativa", titulo: "Operativa" },
  { id: "sistema", titulo: "Sistema" },
];

export const SECCIONES = [
  { id: "asistente", titulo: "Asistente", icono: "sparkles", grupo: "principal", modulo: "./secciones/asistente.js", css: ["asistente", "asistente-bloques"] },
  { id: "comunicaciones", titulo: "Comunicaciones", icono: "inbox", grupo: "operativa", modulo: "./secciones/comunicaciones.js", css: ["comunicaciones"] },
  { id: "hoy", titulo: "Hoy", icono: "calendar", grupo: "operativa", modulo: "./secciones/hoy.js", css: ["hoy"] },
  { id: "estancias", titulo: "Estancias", icono: "key", grupo: "operativa", modulo: "./secciones/estancias.js", css: ["estancias"] },
  { id: "ocupacion", titulo: "Ocupación", icono: "bed", grupo: "operativa", modulo: "./secciones/ocupacion.js", css: ["ocupacion"] },
  { id: "fuente", titulo: "Fuente única", icono: "layers", grupo: "operativa", modulo: "./secciones/fuente.js", css: ["fuente"] },
  { id: "galeria", titulo: "Guía de estilo", icono: "grid", grupo: "sistema", modulo: "./secciones/galeria.js", css: ["galeria"] },
  { id: "maqueta", titulo: "Maqueta del asistente", icono: "sparkles", grupo: "sistema", oculta: true, modulo: "./secciones/maqueta.js", css: ["maqueta"] },
];
