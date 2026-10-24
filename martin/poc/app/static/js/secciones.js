/*
  Manifiesto de secciones: el menú lateral y el router salen de aquí. Cada sección es un módulo en js/secciones/<id>.js con
  export default { id, montar(contenedor, ctx) }, y sus estilos propios en css/secciones/<nombre>.css (todos los listados en `css` deben existir).
*/
export const SECCION_INICIAL = "asistente";

export const GRUPOS = [
  { id: "principal", titulo: null },
  { id: "operativa", titulo: "Operativa" },
  { id: "comunicacion", titulo: "Comunicación" },
  { id: "sistema", titulo: "Sistema" },
];

export const SECCIONES = [
  { id: "asistente", titulo: "Asistente", icono: "sparkles", grupo: "principal", modulo: "./secciones/asistente.js", css: ["asistente", "asistente-bloques"] },
  { id: "hoy", titulo: "Hoy", icono: "home", grupo: "operativa", modulo: "./secciones/hoy.js", css: ["hoy"] },
  { id: "recepcion", titulo: "Recepción", icono: "door", grupo: "operativa", modulo: "./secciones/recepcion.js", css: ["recepcion", "recepcion-pasos"] },
  { id: "ocupacion", titulo: "Ocupación", icono: "bed", grupo: "operativa", modulo: "./secciones/ocupacion.js", css: ["ocupacion"] },
  { id: "documentos", titulo: "Documentos", icono: "receipt", grupo: "operativa", modulo: "./secciones/documentos.js", css: ["documentos"] },
  { id: "bandeja", titulo: "Bandeja", icono: "inbox", grupo: "comunicacion", modulo: "./secciones/bandeja.js", css: ["bandeja"] },
  { id: "mensajes", titulo: "Mensajes", icono: "message", grupo: "comunicacion", modulo: "./secciones/mensajes.js", css: ["mensajes"] },
  { id: "integraciones", titulo: "Integraciones", icono: "plug", grupo: "sistema", modulo: "./secciones/integraciones.js", css: ["integraciones"] },
  { id: "galeria", titulo: "Guía de estilo", icono: "layers", grupo: "sistema", modulo: "./secciones/galeria.js", css: ["galeria"] },
];
