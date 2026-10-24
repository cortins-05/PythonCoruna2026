/*
  Iconos de trazo (24x24, sin relleno, hereda el color con currentColor). Cada icono es una lista de trazos:
  un string es el atributo d de un path, ["c", cx, cy, r] un círculo, ["r", x, y, ancho, alto, radio] un rectángulo y ["l", x1, y1, x2, y2] una línea.
  Una sección que necesite un icono que no está aquí lo registra con registrarIcono(nombre, trazos) desde su propio fichero.
*/
import { svg } from "./dom.js";

const ICONOS = {
  sparkles: ["m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3z", "M19 3v4", "M21 5h-4"],
  chat: ["M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"],
  home: ["M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z", "M9 22V12h6v10"],
  inbox: ["M22 12h-6l-2 3h-4l-2-3H2", "M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"],
  calendar: [["r", 3, 4, 18, 18, 2], "M16 2v4", "M8 2v4", "M3 10h18"],
  bed: ["M2 4v16", "M2 8h18a2 2 0 0 1 2 2v10", "M2 17h20", "M6 8v9"],
  key: ["m21 2-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.78 7.78 5.5 5.5 0 0 1 7.78-7.78zm0 0L15.5 7.5m0 0 3 3L22 7l-3-3m-3.5 3.5L19 4"],
  door: ["M13 4h3a2 2 0 0 1 2 2v14", "M2 20h3", "M13 20h9", "M10 12v.01", "M13 4.56v16.16a1 1 0 0 1-1.24.97L5 20V5.56a2 2 0 0 1 1.52-1.94l4-1A2 2 0 0 1 13 4.56z"],
  message: ["M7.9 20A9 9 0 1 0 4 16.1L2 22z"],
  mail: [["r", 2, 4, 20, 16, 2], "m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"],
  plug: ["M12 22v-5", "M9 8V2", "M15 8V2", "M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8z"],
  receipt: ["M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1z", "M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8", "M12 17.5v-11"],
  truck: ["M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2", "M15 18H9", "M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.62l-3.48-4.35A1 1 0 0 0 17.52 8H14", ["c", 17, 18, 2], ["c", 7, 18, 2]],
  layers: ["m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83z", "m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65", "m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"],
  check: ["M20 6 9 17l-5-5"],
  x: ["M18 6 6 18", "m6 6 12 12"],
  plus: ["M5 12h14", "M12 5v14"],
  minus: ["M5 12h14"],
  "chevron-down": ["m6 9 6 6 6-6"],
  "chevron-up": ["m18 15-6-6-6 6"],
  "chevron-left": ["m15 18-6-6 6-6"],
  "chevron-right": ["m9 18 6-6-6-6"],
  "chevrons-right": ["m6 17 5-5-5-5", "m13 17 5-5-5-5"],
  "arrow-left": ["m12 19-7-7 7-7", "M19 12H5"],
  "arrow-right": ["M5 12h14", "m12 5 7 7-7 7"],
  "arrow-up": ["m5 12 7-7 7 7", "M12 19V5"],
  "arrow-down": ["M12 5v14", "m19 12-7 7-7-7"],
  "arrow-up-right": ["M7 7h10v10", "M7 17 17 7"],
  "more-h": [["c", 12, 12, 1], ["c", 19, 12, 1], ["c", 5, 12, 1]],
  "more-v": [["c", 12, 12, 1], ["c", 12, 5, 1], ["c", 12, 19, 1]],
  search: [["c", 11, 11, 8], "m21 21-4.3-4.3"],
  send: ["m22 2-7 20-4-9-9-4z", "M22 2 11 13"],
  info: [["c", 12, 12, 10], "M12 16v-4", "M12 8h.01"],
  alert: ["m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3", "M12 9v4", "M12 17h.01"],
  clock: [["c", 12, 12, 10], "M12 6v6l4 2"],
  user: ["M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2", ["c", 12, 7, 4]],
  users: ["M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2", ["c", 9, 7, 4], "M22 21v-2a4 4 0 0 0-3-3.87", "M16 3.13a4 4 0 0 1 0 7.75"],
  file: ["M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5z", "M14 2v6h6", "M16 13H8", "M16 17H8", "M10 9H8"],
  list: ["M8 6h13", "M8 12h13", "M8 18h13", "M3 6h.01", "M3 12h.01", "M3 18h.01"],
  refresh: ["M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8", "M21 3v5h-5", "M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16", "M3 21v-5h5"],
  camera: ["M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3z", ["c", 12, 13, 3]],
  shield: ["M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"],
  copy: [["r", 8, 8, 14, 14, 2], "M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"],
  edit: ["M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z"],
  trash: ["M3 6h18", "M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6", "M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"],
  filter: ["M22 3H2l8 9.46V19l4 2v-8.54z"],
  bell: ["M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9", "M10.3 21a1.94 1.94 0 0 0 3.4 0"],
  grid: [["r", 3, 3, 7, 7, 1], ["r", 14, 3, 7, 7, 1], ["r", 14, 14, 7, 7, 1], ["r", 3, 14, 7, 7, 1]],
  building: ["M3 21h18", "M5 21V7l8-4v18", "M19 21V11l-6-4", "M9 9v.01", "M9 12v.01", "M9 15v.01", "M9 18v.01"],
  bot: ["M12 8V4H8", ["r", 4, 8, 16, 12, 2], "M2 14h2", "M20 14h2", "M15 13v2", "M9 13v2"],
  paperclip: ["m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"],
  download: ["M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4", "m7 10 5 5 5-5", "M12 15V3"],
  upload: ["M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4", "m17 8-5-5-5 5", "M12 3v12"],
  lock: [["r", 3, 11, 18, 11, 2], "M7 11V7a5 5 0 0 1 10 0v4"],
  eye: ["M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z", ["c", 12, 12, 3]],
  sun: [["c", 12, 12, 4], "M12 2v2", "M12 20v2", "m4.93 4.93 1.41 1.41", "m17.66 17.66 1.41 1.41", "M2 12h2", "M20 12h2", "m6.34 17.66-1.41 1.41", "m19.07 4.93-1.41 1.41"],
  moon: ["M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z"],
  zap: ["M13 2 3 14h9l-1 8 10-12h-9z"],
  menu: ["M4 6h16", "M4 12h16", "M4 18h16"],
  "panel-left": [["r", 3, 3, 18, 18, 2], "M9 3v18"],
  euro: ["M4 10h12", "M4 14h9", "M19 6a7.7 7.7 0 0 0-5.2-2A7.9 7.9 0 0 0 6 12c0 4.4 3.5 8 7.8 8 2 0 3.8-.8 5.2-2"],
  phone: ["M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"],
  "credit-card": [["r", 2, 5, 20, 14, 2], "M2 10h20"],
  "id-card": [["r", 2, 4, 20, 16, 2], ["c", 9, 11, 2], "M15 9h3", "M15 13h3", "M6 17c.5-1.5 1.5-2 3-2s2.5.5 3 2"],
  printer: ["M6 9V2h12v7", "M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2", ["r", 6, 14, 12, 8, 0]],
  "external-link": ["M15 3h6v6", "M10 14 21 3", "M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"],
  loader: ["M12 2v4", "m16.2 7.8 2.9-2.9", "M18 12h4", "m16.2 16.2 2.9 2.9", "M12 18v4", "m4.9 19.1 2.9-2.9", "M2 12h4", "m4.9 4.9 2.9 2.9"],
  dot: [["c", 12, 12, 3]],
};

export function registrarIcono(nombre, trazos) {
  ICONOS[nombre] = trazos;
}

export const nombresIconos = () => Object.keys(ICONOS).sort();

function trazo(item) {
  if (typeof item === "string") return svg("path", { d: item });
  const [tipo, ...n] = item;
  if (tipo === "c") return svg("circle", { cx: n[0], cy: n[1], r: n[2] });
  if (tipo === "r") return svg("rect", { x: n[0], y: n[1], width: n[2], height: n[3], rx: n[4] });
  if (tipo === "l") return svg("line", { x1: n[0], y1: n[1], x2: n[2], y2: n[3] });
  return svg("path", { d: "" });
}

/** Logotipo de Uniroom: una U que abre como una puerta y un punto encima. Hereda el color, así que cada línea visual lo tiñe con --lat-logo-texto. */
export function logo({ tam = 24 } = {}) {
  const nodo = svg("svg", { viewBox: "0 0 24 24", width: tam, height: tam, fill: "none", stroke: "currentColor", "stroke-width": 2.4,
    "stroke-linecap": "round", "stroke-linejoin": "round", class: "ui-logo", role: "img", "aria-label": "Uniroom" });
  nodo.append(svg("path", { d: "M6.5 4.5v9a5.5 5.5 0 0 0 11 0v-9" }), svg("circle", { cx: 12, cy: 8.5, r: 1.2, fill: "currentColor", stroke: "none" }));
  return nodo;
}

/** Devuelve un SVG. Si pasas titulo, el icono se anuncia a los lectores de pantalla, y si no, queda oculto como decoración. */
export function icono(nombre, { tam = 18, clase = "", titulo = "" } = {}) {
  const trazos = ICONOS[nombre] ?? ICONOS.dot;
  const nodo = svg("svg", {
    viewBox: "0 0 24 24", width: tam, height: tam, fill: "none", stroke: "currentColor", "stroke-width": 1.75,
    "stroke-linecap": "round", "stroke-linejoin": "round", class: `ui-icono ${clase}`.trim(),
    ...(titulo ? { role: "img", "aria-label": titulo } : { "aria-hidden": "true", focusable: "false" }),
  });
  trazos.forEach((t) => nodo.append(trazo(t)));
  return nodo;
}
