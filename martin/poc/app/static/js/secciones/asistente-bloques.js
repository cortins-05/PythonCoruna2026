/*
  Pintado de los bloques del chat. Interfaz fija (ver design/CONTRATO.md, apartado 5):
  renderBloque(bloque, { ejecutar, ui, el }) devuelve un HTMLElement, y ejecutar(accion, valores) devuelve una promesa de { ok, mensaje, estado, detalle }.
  Este stub enseña el JSON crudo hasta que lo construya el agente asistente-bloques.
*/
export function renderBloque(bloque, { el }) {
  return el("pre", { class: "u-texto-2" }, JSON.stringify(bloque, null, 2));
}
