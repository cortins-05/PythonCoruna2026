/*
  Pasos de una estancia en Recepción. Interfaz fija (ver design/CONTRATO.md, apartado 2b):
  crearPasos(exp, ctx, { recargar }) devuelve [{ id, titulo, estado, resumen, contenido }] con los ids documento, pago, parte, ofihotel y checkout,
  y crearRegistro(exp, ctx) devuelve un HTMLElement con la línea de tiempo. Este stub lo sustituye el agente recepcion-pasos.
*/
export function crearPasos(exp, ctx) {
  return ["documento", "pago", "parte", "ofihotel", "checkout"].map((id) => ({
    id, titulo: id, estado: "pendiente", resumen: "", contenido: ctx.el("p", { class: "u-texto-2" }, "Paso pendiente de construir por el agente recepcion-pasos."),
  }));
}

export function crearRegistro(exp, ctx) {
  return ctx.el("p", { class: "u-texto-2" }, "Registro pendiente de construir.");
}
