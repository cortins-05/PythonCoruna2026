/*
  Piezas compartidas del hotel: semáforo de estancias, prioridad de las fuentes, veredictos de disponibilidad y estados por sistema.
  Las usan varias secciones y el chat, así que viven aquí y no se duplican. Todo el texto entra como nodo de texto, nunca como HTML.
*/
import { el, icono, chip } from "./ui.js";

export const ICONO_FUENTE = { roomcloud: "refresh", ofihotel: "building", recepcion: "door", correo: "mail", whatsapp: "message", ses: "shield", sistema: "alert" };
export const NOMBRE_FUENTE = { roomcloud: "RoomCloud", ofihotel: "OfiHotel", recepcion: "Recepción", correo: "Correo", whatsapp: "WhatsApp", ses: "SES.Hospedajes", sistema: "Sistema" };

/* ------------------------------------------------------------------ semáforo de estancias */

const TONO_COLOR = { rojo: "critico", naranja: "naranja", amarillo: "aviso", azul: "info", gris: "neutro", verde: "ok" };
export const NOMBRE_COLOR = {
  rojo: "Conflicto", naranja: "Parte pendiente", amarillo: "Por pasar a OfiHotel", azul: "Por atender", gris: "Por reflejar", verde: "Todo cuadrado",
};

/** Chip del color del semáforo con su texto (el color nunca va solo). `color`: rojo, naranja, amarillo, azul, gris o verde. */
export function chipSemaforo(color, texto = NOMBRE_COLOR[color] ?? color) {
  return chip({ texto, tono: TONO_COLOR[color] ?? "neutro", punto: true });
}

/** Tono de ui.js (`neutro|ok|aviso|critico|info`) o `naranja` equivalente a un color del semáforo. */
export const tonoDeColor = (color) => TONO_COLOR[color] ?? "neutro";

/* ------------------------------------------------------------------ prioridad de las fuentes */

/** Pastilla "1 RoomCloud". `prioridad` es `{nivel, fuente, id, tipo}` tal como lo devuelve la API. `compacta` deja solo el número. */
export function pastillaNivel(prioridad, { compacta = false } = {}) {
  const { nivel, fuente, tipo } = prioridad;
  const significado = tipo === "firme" ? "reserva firme" : "petición sin confirmar";
  return el("span", {
    class: `pastilla-nivel pastilla-nivel--${tipo}${compacta ? " pastilla-nivel--compacta" : ""}`,
    dataset: { nivel: String(nivel) }, title: `Prioridad ${nivel}: ${fuente} (${significado})`,
    role: compacta ? "img" : null, aria: { label: compacta ? `Prioridad ${nivel}, ${fuente}, ${significado}` : null },
  }, el("span", { class: "pastilla-nivel__n", aria: { hidden: "true" } }, String(nivel)),
  !compacta && el("span", { class: "pastilla-nivel__texto" }, fuente));
}

/**
 * La escalera de prioridades entera: reservas firmes arriba, peticiones debajo y las reglas. `prioridades` es `{niveles, reglas}`.
 * `resaltar` es el id de un nivel (por ejemplo "correo") para marcarlo; `compacta` quita las descripciones; `reglas: false` oculta las reglas.
 */
export function escalera(prioridades, { resaltar = null, compacta = false, reglas = true } = {}) {
  const fila = (n) => el("li", { class: `escalera__fila${n.id === resaltar ? " is-resaltada" : ""}`, dataset: { nivel: String(n.nivel), fuente: n.id } },
    el("span", { class: "escalera__numero", aria: { hidden: "true" } }, String(n.nivel)),
    el("span", { class: "escalera__icono", aria: { hidden: "true" } }, icono(n.icono, { tam: 16 })),
    el("div", { class: "escalera__texto" }, el("strong", null, n.nombre), !compacta && el("span", null, n.descripcion)));
  const grupo = (tipo, titulo, ayuda) => el("section", { class: `escalera__grupo escalera__grupo--${tipo}`, aria: { label: titulo } },
    el("header", { class: "escalera__cabecera" }, el("strong", null, titulo), el("span", null, ayuda)),
    el("ol", { class: "escalera__lista" }, prioridades.niveles.filter((n) => n.tipo === tipo).map(fila)));
  return el("div", { class: "escalera" },
    grupo("firme", "Reservas firmes", "Bloquean la habitación"),
    el("div", { class: "escalera__entre" }, icono("lock", { tam: 13 }), el("span", null, "Una petición nunca desplaza a una reserva firme")),
    grupo("peticion", "Peticiones sin confirmar", "Compiten entre sí por lo que queda libre"),
    reglas && el("ol", { class: "escalera__reglas", aria: { label: "Reglas de prioridad" } }, prioridades.reglas.map((r) => el("li", null, r))));
}

/* ------------------------------------------------------------------ veredicto de una petición */

const VEREDICTO = {
  disponible: ["ok", "Disponible"], ajustado: ["aviso", "Disponible, sin margen"], en_competencia: ["aviso", "En competencia"],
  no_disponible: ["critico", "No disponible"], sin_datos: ["neutro", "Sin datos"],
};

/** Chip del veredicto de contraste: disponible, ajustado, en_competencia, no_disponible o sin_datos. */
export function chipVeredicto(veredicto) {
  const [tono, texto] = VEREDICTO[veredicto] ?? VEREDICTO.sin_datos;
  return chip({ texto, tono, punto: true });
}

/* ------------------------------------------------------------------ estado de una estancia en cada sistema */

const ESTADO_SISTEMA = {
  roomcloud: { sincronizado: ["ok", "Sincronizada"], cancelada: ["neutro", "Cancelada"], no_aplica: ["neutro", "No aplica"] },
  ofihotel: {
    migrado: ["ok", "Migrada"], marcado: ["info", "Marcada"], por_migrar: ["aviso", "Por migrar"], sin_lectura: ["neutro", "Sin lectura"], no_aplica: ["neutro", "No aplica"],
  },
  documentacion: {
    parte_enviado: ["ok", "Parte enviado"], parte_pendiente: ["aviso", "Parte pendiente"], parte_vencido: ["critico", "Parte vencido"],
    incompleta: ["aviso", "Incompleta"], sin_datos: ["neutro", "Sin datos"], no_aplica: ["neutro", "No aplica"],
  },
};
export const NOMBRE_SISTEMA = { roomcloud: "RoomCloud", ofihotel: "OfiHotel", documentacion: "Documentación" };

/** Chip de un sistema concreto: `sistema` es roomcloud, ofihotel o documentacion y `estado` el valor de `sistemas[sistema].estado`. */
export function chipSistema(sistema, estado, { conNombre = true } = {}) {
  const [tono, texto] = ESTADO_SISTEMA[sistema]?.[estado] ?? ["neutro", estado];
  return chip({ texto: conNombre ? `${NOMBRE_SISTEMA[sistema]}: ${texto}` : texto, tono, punto: true });
}

/** Los tres chips de una estancia (`sistemas` tal como lo devuelve la API) en una fila. */
export function chipsSistemas(sistemas) {
  return el("div", { class: "chips-sistemas" }, Object.keys(NOMBRE_SISTEMA).map((s) => chipSistema(s, sistemas[s].estado)));
}
