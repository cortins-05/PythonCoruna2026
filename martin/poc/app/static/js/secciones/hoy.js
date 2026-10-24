/* Sección "Hoy": quién hay en cada habitación hoy, quién llega y quién sale. Datos: GET /api/habitaciones. */
const TIPOS = { "SGL-STD": "Individual", "DBL-STD": "Doble", "TPL-STD": "Triple", "FAM-STD": "Familiar", "SUI-STD": "Suite" };
const ESTADOS = { en_casa: "En casa", llega_hoy: "Llega hoy", sale_hoy: "Sale hoy" };
const corta = (iso) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;

export default {
  id: "hoy",
  async montar(contenedor, ctx) {
    const { el, ui } = ctx;
    const raiz = el("div", { class: "sec-hoy" });
    contenedor.append(raiz);
    ctx.barra({ titulo: "Hoy", acciones: [{ icono: "refresh", etiqueta: "Actualizar", onclick: () => cargar() }] });

    const persona = (s, etiqueta) => el("div", { class: `hoy__persona hoy__persona--${s.estado}` },
      el("strong", null, s.nombre),
      el("span", null, `${etiqueta} · ${corta(s.desde)} a ${corta(s.hasta)}`));

    function tarjeta(h) {
      const libre = !h.noche;
      return el("article", { class: `hoy__hab${libre ? " is-libre" : ""}`, aria: { label: `Habitación ${h.numero}` } },
        el("header", null, el("b", null, String(h.numero)), el("span", null, TIPOS[h.tipo] ?? h.tipo)),
        h.noche ? persona(h.noche, ESTADOS[h.noche.estado]) : el("div", { class: "hoy__libre" }, "Libre esta noche"),
        h.sale ? persona(h.sale, ESTADOS.sale_hoy) : null);
    }

    async function cargar() {
      try {
        const d = await ctx.api("/api/habitaciones");
        const r = d.resumen;
        raiz.replaceChildren(
          el("p", { class: "hoy__resumen" }, `${r.ocupadas} de ${r.habitaciones} ocupadas. Llegan ${r.llegan} y salen ${r.salen}.`),
          el("div", { class: "hoy__rejilla" }, d.habitaciones.map(tarjeta)));
      } catch (e) {
        raiz.replaceChildren(ui.vacio({ icono: "alert", titulo: "No se pudo cargar", texto: e.message, accion: { texto: "Reintentar", icono: "refresh", onclick: cargar } }));
      }
    }
    await cargar();
    const baja = ctx.suscribir("datos-cambiaron", cargar);
    return { destruir() { baja(); } };
  },
};
