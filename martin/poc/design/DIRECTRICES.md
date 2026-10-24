# Directrices de diseño y de trabajo de la interfaz del hub

Estas directrices valen para todos los agentes y para cualquier persona que toque la interfaz. Se leen junto con `CONTRATO.md`, que fija la API, los bloques del chat y quién posee cada fichero.
La interfaz es una aplicación de una sola página con un menú lateral a la izquierda y una pestaña por sección, y la pestaña del asistente es un chat que enseña tarjetas, flujos y controles con los que se puede actuar sin salir de la conversación.

## 1. Lenguaje visual

Sale de dos referencias que tienes en disco (ábrelas con Read antes de diseñar nada):

- `C:\Users\marti\Proyectos\PythonCoruna2026\.claude\refs\ref1-ticket.jpg`: una vista de detalle de ticket de soporte. De ella tomamos el panel de detalles con etiquetas grises y valores en negrita, los chips con punto de color, el botón amarillo dividido con flecha, los botones fantasma con borde fino, las pestañas de texto con línea y el **menú flotante oscuro** con esquinas muy redondeadas.
- `C:\Users\marti\Proyectos\PythonCoruna2026\.claude\refs\ref2-tabs.jpg`: un sistema de pestañas en tres niveles. De ella tomamos las **baldosas con icono** (la activa en azul sólido), las **pestañas de texto con una muesca curva negra** bajo la activa, la **fila de pastillas** grises (la activa en negro, con un "+" al principio y un "⋮" al final) y el **carrusel de tarjetas** con textura de puntos, flechas de borde fino y la tarjeta seleccionada en menta.

La guía de estilo viva está en `#/galeria` y reproduce las dos composiciones. Si dudas de cómo se ve algo, abre esa página y míralo antes de inventar.

Reglas, en orden de importancia:

1. **Bloques con borde fino.** Todo vive dentro de paneles o tarjetas con borde de 1 px, fondo claro y esquinas muy redondeadas (panel 18 px, baldosa 16 px, tarjeta 14 px, control 10 px, pastilla 8 px). No hay sombras fuertes en reposo, y la sombra solo aparece al pasar el cursor por una tarjeta interactiva y en los menús flotantes.
2. **Selección fuerte, estado pastel.** Lo seleccionado se rellena con fuerza (azul en baldosas y menú lateral, negro en pastillas, menta en tarjetas) y los estados se dicen con un chip pastel con punto de color y siempre con texto, nunca solo con color.
3. **Una sola acción amarilla por vista.** El botón `cta` es la acción principal de la pantalla y va arriba a la derecha a través de `ctx.barra({ cta })`. El resto de acciones son `secundario`, `oscuro` o `fantasma`.
4. **El menú oscuro flotante es para las acciones secundarias** de un elemento (más opciones, ver registro, derivar), igual que en la referencia de tickets.
5. **Tres niveles de pestañas.** Baldosas con icono para elegir una categoría grande, pestañas con muesca para cambiar de vista dentro de ella y pastillas para filtrar. No mezcles más de dos niveles en la misma zona.
6. **Tarjetas punteadas para opciones guiadas.** Las que invitan a empezar un flujo (bienvenida del asistente, atajos) llevan la textura de puntos, y la elegida pasa a menta.
7. **Aire.** Espacios de la escala `--s-*`, nunca valores sueltos, y los datos importantes con etiqueta pequeña gris encima y valor en negrita debajo (`ui.kv`).
8. **Lista y detalle.** Las vistas con una colección usan dos paneles (`.u-dos-paneles`): la lista a la izquierda con tarjetas seleccionables y el detalle a la derecha con `kv`, pasos y acciones, como la referencia de tickets. En móvil se apilan.
9. **Iconos de trazo** de `icons.js` (24x24, hereda el color). Un icono que falta se registra con `ui.registrarIcono(nombre, trazos)` desde tu propio fichero.

## 2. Tokens

Todo color, radio, espacio, tamaño de letra, sombra y duración sale de `css/tokens.css` con `var(--...)`. Está prohibido escribir colores hexadecimales, `rgb()` o `rgba()` en el CSS de una sección, y también radios y espacios que no estén en la escala (los bordes de 1 px y los anchos de maquetación sí valen).
El tema oscuro funciona solo si usas los tokens, y se fuerza con `?tema=claro` o `?tema=oscuro` en la URL (por ejemplo `/?tema=oscuro#/bandeja`), que es lo que se usa para las capturas.

Familias: superficies (`--c-bg`, `--c-surface`, `--c-surface-2`, `--c-surface-3`), bordes (`--c-borde`, `--c-borde-fuerte`, `--c-borde-control`), texto (`--c-texto`, `--c-texto-2`, `--c-texto-3`), acento (`--c-acento*`, `--c-enlace`), CTA (`--c-cta*`), fuerte (`--c-fuerte*`), tonos `--c-ok-*`, `--c-aviso-*`, `--c-critico-*`, `--c-info-*`, `--c-neutro-*` (con `-bg`, `-borde`, `-texto` y `-punto`), menta, menú oscuro, radios `--r-*`, espacios `--s-1` a `--s-9`, tipografía `--t-*` y `--p-*`, sombras `--sombra-*` y movimiento `--ease` y `--dur`.
Los contrastes están calculados con `python scripts/contraste.py` y deben seguir pasando si cambias un token.

## 3. Catálogo de componentes (`ctx.ui`)

| Función | Para qué |
|---|---|
| `boton({ texto, icono, variante, tam, onclick, desactivado, cargando, etiqueta })` | Botón. Variantes `cta`, `oscuro`, `secundario`, `fantasma` (solo icono) y `peligro`. Un botón sin texto necesita `etiqueta` |
| `botonDividido({ texto, icono, onclick, items })` | Botón amarillo con flecha que abre un menú oscuro |
| `chip({ texto, tono, punto, icono })` e `insignia(n, { tono })` | Estados y contadores. Tonos `neutro`, `ok`, `aviso`, `critico`, `info` |
| `pastilla` y `filaPastillas({ items, activo, onchange, anadir, mas })` | Filtros en fila. Devuelve `{ el, set, valor }` |
| `tileTabs({ items, activo, onchange })` | Baldosas con icono. Devuelve `{ el, set, valor, idPestana }` |
| `tabsSubrayado({ items, activo, onchange })` | Pestañas con muesca curva. Devuelve `{ el, set, valor, idPestana }` |
| `tarjeta({ titulo, subtitulo, icono, chips, cuerpo, pie, seleccionada, onclick, variante, direccion })` | Tarjeta. `variante`: `normal`, `punteada`, `menta`. Con `onclick` toda ella es un botón y no debe contener otros controles |
| `carrusel({ items, ancho })` | Carrusel horizontal con flechas |
| `panel({ titulo, subtitulo, acciones, hijos })` | Bloque con borde y cabecera, el contenedor básico |
| `kv(pares, { columnas })` | Etiqueta y valor. El valor puede ser texto o un nodo |
| `menuOscuro({ ancla, items })` | Menú flotante oscuro con teclado. Devuelve `{ abrir, cerrar, alternar }` |
| `campo({ etiqueta, nombre, tipo, valor, opciones, ... })` | Campo de formulario con etiqueta, ayuda y error. Devuelve `{ el, entrada, leer, poner, error }` |
| `tabla({ columnas, filas, onfila })` | Tabla accesible con filas interactivas |
| `pasos(items, { onclick })` | Flujo vertical con marcador y conector. Estados `hecho`, `actual`, `pendiente`, `bloqueado` |
| `vacio`, `esqueleto` | Estado vacío y de carga |
| `ctx.avisar(texto, tono)` y `ctx.confirmar({ ... })` | Aviso breve y diálogo de confirmación propio |
| `avatar`, `separador`, `fechaCorta`, `hora`, `fechaHora`, `moneda`, `icono` | Utilidades |

## 4. Interacción

- **Estados completos.** Cada control tiene reposo, hover, foco visible, seleccionado, desactivado y cargando, y cada vista tiene estado de carga (esqueleto), vacío (con una acción útil) y error (con mensaje claro y botón para reintentar).
- **Acciones que comprometen** (enviar un parte, emitir o enviar un documento, cerrar disponibilidad, reiniciar datos) piden confirmación con `ctx.confirmar` y el botón de confirmar nombra la acción ("Sí, enviar el parte"). Las destructivas usan `tono: "critico"`. Nunca `alert`, `confirm` ni `prompt`.
- **Feedback.** Tras una acción sale un `ctx.avisar` breve (`ok` si fue bien, `critico` si falló) y la vista se actualiza sola porque escucha `datos-cambiaron`.
- **Errores de la API.** Se capturan, se enseña `e.message` (ya viene en frases en español de la API) y se deja la vista usable. Un 409 con `conflicto`, `faltan` o `pendientes` se explica, no se traga.
- **Teclado.** Todo se puede hacer sin ratón: pestañas con flechas, menús con flechas y Escape, filas y tarjetas interactivas con Enter y espacio, diálogos con foco atrapado (los gestiona `<dialog>`).
- **Deep links.** Una sección lee `ctx.params` al montarse y cambia el hash con `ctx.navegar` cuando el usuario elige algo, para que se pueda compartir y volver atrás.

## 5. Accesibilidad

Nivel objetivo WCAG 2.2 AA. En concreto: texto con contraste mínimo de 4,5:1 y bordes de controles y foco con 3:1 (los tokens ya cumplen), foco siempre visible, nombres accesibles en botones de solo icono, el estado nunca solo por color, un único `h1` por vista (lo pone la barra, tú empiezas en `h2`), tablas con `th scope` y título, formularios con `label`, regiones dinámicas con `aria-live` cuando algo cambia sin acción del usuario, objetivos táctiles de al menos 32 px en escritorio y 40 px en móvil, y respeto de `prefers-reduced-motion` (ya lo gestiona la base).

## 6. Textos de la interfaz

Español con registro cuidado, también en las etiquetas, los avisos y los mensajes de error. Frases claras y concretas, sin guiones largos (—), sin la construcción "no es X, es Y", sin metáforas, sin emojis y sin coletillas que no aporten un dato. El vocabulario de dominio se queda en inglés cuando ya se usa así (check-in, check-out, walk-in, overbooking) y las fechas van como "24 oct" y las horas en formato de 24 horas.
Los botones nombran la acción ("Aprobar y enviar", "Emitir factura") y no "Aceptar". Si una cifra o un gráfico se entienden solos, no los expliques con prosa al lado.

## 7. Código

- Módulos ES nativos, sin dependencias, sin CDN ni fuentes externas (la aplicación tiene que funcionar sin red).
- Los elementos se crean con `ctx.el` y todo dato que viene del servidor entra como texto. **Prohibido** `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `eval`, `new Function` y atributos `on*` como string.
- Las peticiones van solo por `ctx.api`. Nada de `fetch` directo.
- El CSS de una sección va bajo el prefijo `.sec-<id>` (pon esa clase al contenedor raíz que montas) y usa solo tokens.
- No toques ficheros que no son tuyos (ver `CONTRATO.md`). Si necesitas un cambio en uno de ellos, descríbelo en `peticiones_a_base`.
- Funciones pequeñas con nombres en español, comentarios que expliquen el porqué y nada de `console.log` en lo que entregas.

## 8. Cómo verificar tu trabajo

Con el conductor de capturas (`scripts/captura.py`, explicado en `design/VERIFICAR.md`), que arranca su propio servidor con datos propios, abre Chrome en modo headless, hace clics reales y devuelve un informe de errores de consola:

```
cd martin/poc
python scripts/captura.py --ruta "#/bandeja" --semilla completa --salida C:\Users\marti\Proyectos\PythonCoruna2026\.claude\capturas\<tu-agente>\bandeja-claro.png
```

Antes de entregar tienes que haber hecho y mirado (con Read sobre cada imagen):

1. La sección con datos (`--semilla completa`) en claro y en oscuro a 1440x900, y en móvil a 390x844.
2. La sección vacía (`--semilla vacia`) y, si procede, con un error provocado.
3. Los flujos principales con clics reales (`--paso "click:..."`), con una captura después de cada paso importante.
4. Una pasada de teclado (`--paso "tab:N"`) comprobando que el foco se ve.
5. La comparación con `#/galeria` y con las dos referencias: ¿se parece en bloques, bordes, tarjetas y sistemas interactivos? Si no, corrige y repite al menos una vez.
6. `python -m pytest tests -q` en verde, y `python scripts/captura.py` sin errores de consola, excepciones ni peticiones fallidas.

Guarda tus capturas en `C:\Users\marti\Proyectos\PythonCoruna2026\.claude\capturas\<tu-agente>\` para que se puedan revisar después.

## 9. Git y entrega

Cada agente trabaja en su rama `ui/<agente>` creada desde `origin/ui/base` (`git fetch origin` y `git switch -c ui/<agente> origin/ui/base`), con commits pequeños de mensaje corto en español y la línea final `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`, y termina con `git push -u origin ui/<agente>`. No hagas merge, no toques `main` ni `ui/base`, y no uses `git stash`.
El informe final es estructurado: `rama`, `commit`, `archivos`, `capturas` (rutas absolutas), `pruebas` (comando y resultado), `decisiones`, `limitaciones`, `peticiones_a_base` y `checklist` (una entrada por cada punto de "Definición de hecho" con `cumple` y una nota).

## 10. Definición de hecho

- La sección cumple el contrato (formas de la API, interfaz de sección, bloques y acciones si aplica).
- Se ve como las referencias: bloques con borde fino, tarjetas, baldosas, pastillas, pestañas con muesca y menú oscuro donde corresponda, una sola acción amarilla.
- Claro, oscuro y móvil revisados con capturas.
- Estados de carga, vacío y error resueltos.
- Teclado, foco y contraste comprobados.
- Cero colores sueltos, cero `innerHTML`, cero `alert`, `confirm` o `prompt`, cero peticiones fuera de `ctx.api`.
- Tests en verde, sin errores de consola y rama subida.
