/*
  Helpers mínimos del DOM. Todo lo que se pinta con datos pasa por aquí, y por diseño los textos entran como nodos de texto:
  nunca se interpreta HTML y nunca se asigna un manejador de eventos desde un string, así que un dato malicioso no puede ejecutar código.
*/
const NS_SVG = "http://www.w3.org/2000/svg";
const URL_PELIGROSA = /^\s*(javascript|vbscript):/i;
const ATRIBUTOS_URL = new Set(["href", "src", "action", "formaction", "xlink:href"]);

function anadir(padre, hijos) {
  for (const hijo of hijos.flat(Infinity)) {
    if (hijo == null || hijo === false) continue;
    padre.append(hijo instanceof Node ? hijo : document.createTextNode(String(hijo)));
  }
}

function aplicar(nodo, atributos) {
  for (const [clave, valor] of Object.entries(atributos)) {
    if (valor == null || valor === false) continue;
    if (clave === "class") {
      nodo.setAttribute("class", Array.isArray(valor) ? valor.filter(Boolean).join(" ") : String(valor));
    } else if (clave === "dataset") {
      for (const [k, v] of Object.entries(valor)) if (v != null) nodo.dataset[k] = String(v);
    } else if (clave === "aria") {
      for (const [k, v] of Object.entries(valor)) if (v != null && v !== false) nodo.setAttribute(`aria-${k}`, String(v));
    } else if (clave === "estilo") {
      for (const [k, v] of Object.entries(valor)) if (v != null) nodo.style.setProperty(k, String(v));
    } else if (clave.startsWith("on")) {
      if (typeof valor === "function") nodo.addEventListener(clave.slice(2).toLowerCase(), valor);
    } else if (ATRIBUTOS_URL.has(clave) && URL_PELIGROSA.test(String(valor))) {
      continue;
    } else if (valor === true) {
      nodo.setAttribute(clave, "");
    } else {
      nodo.setAttribute(clave, String(valor));
    }
  }
}

/** Crea un elemento. Los hijos de tipo string son texto, y los atributos on* solo aceptan funciones. */
export function el(tag, atributos = null, ...hijos) {
  const nodo = document.createElement(tag);
  if (atributos) aplicar(nodo, atributos);
  anadir(nodo, hijos);
  return nodo;
}

/** Crea un elemento SVG (los nombres de atributo se respetan tal cual, por ejemplo viewBox). */
export function svg(tag, atributos = null, ...hijos) {
  const nodo = document.createElementNS(NS_SVG, tag);
  if (atributos) for (const [k, v] of Object.entries(atributos)) if (v != null && v !== false) nodo.setAttribute(k, String(v));
  anadir(nodo, hijos);
  return nodo;
}

export function vaciar(nodo) {
  nodo.replaceChildren();
  return nodo;
}

let contador = 0;
export const uid = (prefijo = "ui") => `${prefijo}-${++contador}`;
