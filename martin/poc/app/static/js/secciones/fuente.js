/*
  Sección "Fuente única": las cinco fuentes de entrada, el orden en que ganan y lo que hay que atender.
  Datos: GET /api/fuente-unica.
*/
const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;

export default {
  id: "fuente",
  async montar(contenedor, ctx) {
    const { el, ui } = ctx;
    const raiz = el("div", { class: "sec-fuente" });
    contenedor.append(raiz);
    let datos = null;
    let secuencia = 0;
    let vivo = true;

    /* ------------------------------------------------------------ acciones */
    const ejecutar = async (hacer, errorTexto) => {
      try { await hacer(); } catch (e) { ctx.avisar(e.message || errorTexto, "critico"); }
    };

    const simularReserva = () => ejecutar(async () => {
      const r = await ctx.api("/api/demo/reserva-roomcloud", "POST", { tipo: "SGL-STD" });
      ctx.avisar(`Entra la reserva ${r.id} de Booking del ${ui.fechaCorta(r.desde)} al ${ui.fechaCorta(r.hasta)}.`, "ok");
    }, "No se ha podido simular la reserva");

    const reiniciar = () => ejecutar(async () => {
      const ok = await ctx.confirmar({
        titulo: "Reiniciar la demo", texto: "Se borran los cambios hechos durante la demo y vuelven los datos de partida.",
        confirmar: "Reiniciar la demo", tono: "critico",
      });
      if (!ok) return;
      await ctx.api("/api/demo/semilla?nivel=demo", "POST");
      ctx.avisar("La demo vuelve a su estado inicial.", "ok");
    }, "No se ha podido reiniciar la demo");

    /* ------------------------------------------------------------ piezas */
    const fuente = (f) => el("li", { class: "fu__fuente", dataset: { fuente: f.id } },
      el("span", { class: "fu__nombre" }, f.nombre),
      el("strong", { class: "fu__cifra" }, String(f.recibido)),
      el("span", { class: "fu__ultima" }, f.ultima ? `leído a las ${f.ultima}` : "sin leer"));

    const filaCola = (item) => el("li", { class: `fu__fila${item.color === "rojo" ? " fu__fila--problema" : ""}` },
      el("span", { class: "fu__fila-titulo" }, item.titulo),
      ui.boton({ texto: "Abrir", variante: "fantasma", tam: "sm", onclick: () => ctx.navegar(item.ruta, item.params) }));

    const filaActividad = (ev) => el("li", { class: "fu__ev" },
      el("time", { class: "fu__ev-hora" }, ev.hora),
      el("span", null, `${ev.titulo}. ${ev.detalle}`));

    /* ------------------------------------------------------------ estados */
    const cargando = () => raiz.replaceChildren(el("div", { class: "fu__carga" }, ui.esqueleto({ lineas: 2, alto: 90 }), ui.esqueleto({ lineas: 3, alto: 120 })));

    const error = (e) => raiz.replaceChildren(ui.vacio({
      icono: "alert", titulo: "No se ha podido cargar la fuente única", texto: e?.message || "Inténtalo de nuevo en unos segundos.",
      accion: { texto: "Reintentar", icono: "refresh", onclick: () => cargar(true) },
    }));

    function pintar() {
      const d = datos;
      const entrantes = d.fuentes.filter((f) => f.tipo !== "salida").sort((a, b) => a.nivel - b.nivel);
      const niveles = [...d.prioridades.niveles].sort((a, b) => a.nivel - b.nivel);
      const cola = d.cola.slice(0, 6);
      const actividad = d.actividad.slice(0, 4);
      raiz.replaceChildren(
        el("section", { class: "fu__bloque", aria: { label: "Fuentes" } },
          entrantes.length ? el("ul", { class: "fu__fuentes" }, entrantes.map(fuente))
            : ui.vacio({ icono: "plug", titulo: "Todavía no hay fuentes" }),
          el("p", { class: "fu__orden" }, `Gana la de más prioridad: ${niveles.map((n) => `${n.nivel} ${n.nombre}`).join(", ")}.`)),
        el("section", { class: "fu__bloque" },
          el("h2", { class: "fu__titulo" }, "Qué atender primero"),
          cola.length ? el("ul", { class: "fu__lista" }, cola.map(filaCola)) : el("p", { class: "fu__vacio" }, "Nada pendiente.")),
        actividad.length > 0 && el("section", { class: "fu__bloque" },
          el("h2", { class: "fu__titulo" }, "Actividad"),
          el("ul", { class: "fu__lista" }, actividad.map(filaActividad))),
        el("details", { class: "fu__menu" },
          el("summary", null, "Demo"),
          el("div", { class: "fu__menu-cuerpo" },
            ui.boton({ texto: "Reiniciar la demo", variante: "fantasma", tam: "sm", onclick: reiniciar }))));
    }

    async function cargar(conEsqueleto = false) {
      const mia = ++secuencia;
      if (conEsqueleto || !datos) cargando();
      try {
        const r = await ctx.api("/api/fuente-unica");
        if (!vivo || mia !== secuencia) return;
        datos = r;
        pintar();
      } catch (e) {
        if (!vivo || mia !== secuencia) return;
        datos = null;
        error(e);
      }
    }

    ctx.barra({
      titulo: "Fuente única",
      cta: { texto: "Simular reserva de Booking", icono: "plus", onclick: simularReserva },
      acciones: [{ icono: "refresh", texto: "Actualizar", etiqueta: "Actualizar", onclick: () => cargar(true) }],
    });
    const baja = ctx.suscribir("datos-cambiaron", () => cargar());
    await cargar();
    return { destruir() { vivo = false; baja(); } };
  },
};
