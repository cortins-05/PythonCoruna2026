# Guía de diseño de Uniroom

Esta guía vale para todos los agentes y para cualquier persona que toque la interfaz. Se lee junto con `CONTRATO-CORE.md`, que fija la API, los bloques del chat y quién posee cada fichero, y manda sobre esta guía en caso de duda. La guía viva con todos los componentes renderizados está en `#/galeria`, y si dudas de cómo se ve algo, ábrela antes de inventar.

## 1. Qué es la aplicación y a quién sirve

Uniroom es la plataforma de recepción de un hotel familiar de Galicia. Bebe de cinco fuentes (RoomCloud, OfiHotel, recepción, correo y WhatsApp), las unifica en una sola fuente de verdad, contrasta cada petición con las demás fuentes y deja a recepción solo la confirmación. La usa Flor, en recepción, con prisa, a veces desde el móvil y con el lobby delante, así que cada pantalla tiene que decir en pocos segundos qué hay que atender primero y por qué.

La interfaz es una SPA de módulos ES sin build, con un menú lateral y cinco pantallas: Fuente única, Comunicaciones, Estancias, Ocupación y Asistente. La pantalla Guía de estilo (`#/galeria`) es interna y sirve de comprobación visual. Casi todo es de demostración y los envíos son simulados, y la pantalla lo dice una sola vez con la palabra "simulado".

## 2. Principios visuales

1. **Bloques con borde fino.** Todo contenido vive en un `panel` con borde de 1 px, esquinas redondeadas y una cabecera con título y acciones. No hay sombras pesadas, las sombras solo se usan en menús y diálogos.
2. **Tarjetas** para elementos seleccionables de una colección. La tarjeta seleccionada pasa a menta y, si es una opción guiada, lleva la textura de puntos (`variante: "punteada"`).
3. **Chips para el estado.** Pastel con punto de color y siempre con texto. Un estado nunca se comunica solo con color.
4. **Una sola acción principal por vista**, en amarillo (`variante: "cta"`), y la pone la barra superior (`ctx.barra({ cta })`). Las demás acciones son `secundario`, `oscuro` o `fantasma`.
5. **Menú oscuro flotante** (`menuOscuro`) para acciones secundarias de un elemento.
6. **Tres niveles de navegación como máximo en una misma zona.** Baldosas con icono para categorías grandes, pestañas con muesca para vistas y pastillas para filtros.
7. **Aire y jerarquía.** Espacios de la escala `--s-*`, nunca valores sueltos, y los datos importantes con etiqueta pequeña gris encima y valor en negrita debajo (`kv`).
8. **Lista y detalle.** Una colección usa `.u-dos-paneles`: lista de tarjetas a la izquierda y detalle a la derecha, que en móvil se apilan.
9. **Iconos de trazo** de `icons.js` (24x24, heredan el color). Uno nuevo se registra con `ui.registrarIcono(nombre, trazos)` desde tu fichero.
10. **Solo tokens.** Prohibido escribir colores hexadecimales, `rgb()` o `rgba()` en el CSS de una sección, y también radios y espacios fuera de la escala (los bordes de 1 px y los anchos de maquetación sí valen).

## 3. Las tres líneas visuales

Los tokens de `tokens.css` son la línea A. `lineas.css` sobrescribe tokens para las líneas B y C, solo en tema claro, y se activan con `?linea=b` o `?linea=c` en la URL (por ejemplo `/?linea=c#/fuente`). Una sección que use solo tokens se adapta sola a las tres.

| Línea | Personalidad | Acento y CTA | Menú lateral | Cuándo usarla |
|---|---|---|---|---|
| A (por defecto) | Neutra y luminosa, azul sobre blanco y CTA amarillo | acento `#2860F0`, CTA `#FFD21F` | claro | Es la línea de la demo. Úsala siempre salvo que se pida otra |
| B | Grafito e índigo, esquinas contenidas (radios de 6 a 14 px) | acento y CTA `#4338CA` | oscuro grafito | Presentación a un público de software o gestión, donde pesa lo sobrio |
| C | Hotel cálido, arena y verde pino, títulos con serifa y radios de 10 a 24 px | acento `#1F5C4A`, CTA `#F2B84B` | verde pino | Presentación al hotel, donde pesa la hospitalidad |

En B el CTA deja de ser amarillo y pasa a índigo, así que el texto "una sola acción en amarillo" significa "una sola acción con `variante: "cta"`". Las líneas B y C no tienen tema oscuro: `?linea=` fuerza el tema claro.

## 4. Tokens

Todo sale de `app/static/css/tokens.css` (y de `hotel.css` para el naranja). Los valores son los del tema claro de la línea A, y en tema oscuro cambian automáticamente.

### 4.1 Colores

| Familia | Tokens | Uso |
|---|---|---|
| Superficies | `--c-bg` `#F5F5F3`, `--c-surface` `#FFFFFF`, `--c-surface-2` `#FAFAF8`, `--c-surface-3` `#F0F0ED` | Fondo de la página, paneles, cabeceras de tabla, hover |
| Bordes | `--c-borde` `#E6E6E1`, `--c-borde-fuerte` `#D2D2CC`, `--c-borde-control` `#8A8A84` | Divisores, bordes de tarjeta, bordes de campos y controles (3:1) |
| Texto | `--c-texto` `#111111`, `--c-texto-2` `#565652`, `--c-texto-3` `#6B6B67` | Principal, secundario, terciario. Los tres llegan a 4,5:1 sobre las cuatro superficies |
| Acento | `--c-acento` `#2860F0`, `--c-acento-hover`, `--c-acento-texto`, `--c-acento-suave`, `--c-acento-borde`, `--c-enlace` | Selección fuerte (tile activo, enlaces, foco) |
| CTA | `--c-cta` `#FFD21F`, `--c-cta-hover`, `--c-cta-texto` | La acción principal de la vista |
| Fuerte | `--c-fuerte` `#111111`, `--c-fuerte-hover`, `--c-fuerte-texto` | Pastilla activa, botón oscuro, números de la escalera |
| Menta | `--c-menta`, `--c-menta-borde` | Tarjeta seleccionada y burbuja de WhatsApp |
| Menú oscuro | `--c-menu`, `--c-menu-texto`, `--c-menu-texto-2`, `--c-menu-hover`, `--c-menu-borde` | Menú flotante |
| Menú lateral | `--lat-bg`, `--lat-borde`, `--lat-texto`, `--lat-texto-fuerte`, `--lat-grupo`, `--lat-hover`, `--lat-activo-bg`, `--lat-activo-texto`, `--lat-icono-bg`, `--lat-icono-borde`, `--lat-logo-bg`, `--lat-logo-texto` | Cada línea puede darle otro color |

### 4.2 Tonos de estado y semáforo

Cada tono tiene cuatro variables: `--c-<tono>-bg`, `--c-<tono>-borde`, `--c-<tono>-texto` y `--c-<tono>-punto`. Los tonos son `neutro`, `ok`, `aviso`, `critico`, `info` (en `tokens.css`) y `naranja` (en `hotel.css`, con la clase `ui-chip--naranja`).

El semáforo de estancias tiene seis colores y cada uno se pinta con un tono. Los textos de abajo son los de `NOMBRE_COLOR` y salen solos de `chipSemaforo`.

| Color del semáforo | Tono | Texto del chip | Significa |
|---|---|---|---|
| `rojo` | `critico` | Conflicto | Dos fuentes dicen cosas incompatibles |
| `naranja` | `naranja` | Parte pendiente | Falta el parte de viajeros y corre el plazo |
| `amarillo` | `aviso` | Por pasar a OfiHotel | La estancia está en RoomCloud y falta marcarla en OfiHotel |
| `azul` | `info` | Por atender | Hay una acción de recepción |
| `gris` | `neutro` | Por reflejar | Falta que un sistema se ponga al día |
| `verde` | `ok` | Todo cuadrado | Sin pendientes |

### 4.3 Espacios, radios, tipografía, sombras y movimiento

| Familia | Valores |
|---|---|
| Espacios | `--s-1` 4, `--s-2` 8, `--s-3` 12, `--s-4` 16, `--s-5` 20, `--s-6` 24, `--s-7` 32, `--s-8` 40, `--s-9` 48 px |
| Radios | `--r-panel` 18, `--r-tile` 16, `--r-card` 14, `--r-ctl` 10, `--r-chip` 8, `--r-pill` 999 px (B y C los cambian) |
| Tipografía | `--f-sans` (Inter y la pila del sistema, sin fuentes externas), `--f-mono`, `--f-titulo` (igual que sans salvo en la línea C, que usa serifa) |
| Tamaños | `--t-xs` 12, `--t-sm` 13, `--t-md` 14, `--t-lg` 16, `--t-xl` 20, `--t-2xl` 24, `--t-3xl` 30 px |
| Pesos | `--p-normal` 400, `--p-medio` 500, `--p-fuerte` 600 |
| Sombras | `--sombra-1` (reposo), `--sombra-2` (elevada), `--sombra-menu` (menús y diálogos) |
| Movimiento | `--ease` y `--dur` (160 ms) |
| Layout | `--sidebar-w` 256, `--sidebar-w-compacta` 76, `--barra-h` 68, `--contenido-max` 1280 px |

### 4.4 Tema claro y oscuro

El tema oscuro sale de la preferencia del sistema o se fuerza con `?tema=claro` o `?tema=oscuro` en la URL, que no se guarda y es lo que usan las capturas. El menú de la esquina inferior izquierda guarda la elección del usuario. Todo lo que use tokens funciona en los dos temas sin más. Ningún par de texto y fondo puede bajar de 4,5:1 y ningún borde de control ni foco de 3:1, y `python scripts/contraste.py` (líneas A, `b` y `c`) lo comprueba.

## 5. Catálogo de componentes

Todo lo de `ui.js` se usa como `ctx.ui.<función>` dentro de una sección. Todo lo de `ui-hotel.js` se importa con `import { ... } from "../ui-hotel.js"`. Todo texto entra como nodo de texto: nunca se pinta HTML.

### 5.1 `ui.js`

| Función | Cuándo usarla | Ejemplo |
|---|---|---|
| `boton({ texto, icono, variante, tam, onclick, desactivado, cargando, etiqueta, clase })` | Cualquier acción. Variantes `cta` (una por vista), `oscuro`, `secundario`, `fantasma` (borde fino y fondo de superficie, vale con texto o solo icono) y `peligro`. Un botón sin texto exige `etiqueta` | `ui.boton({ texto: "Volver", icono: "arrow-left", variante: "fantasma" })` |
| `botonDividido({ texto, icono, onclick, items })` | Acción principal con alternativas en un menú oscuro | `ui.botonDividido({ texto: "Aprobar y enviar", icono: "check", onclick, items: [{ texto: "Ver el registro", icono: "list" }] })` |
| `chip({ texto, tono, punto, icono })` | Estado de un elemento. Tonos `neutro`, `ok`, `aviso`, `critico`, `info` | `ui.chip({ texto: "Parte enviado", tono: "ok", punto: true })` |
| `insignia(n, { tono })` | Contador pequeño | `ui.insignia(3, { tono: "aviso" })` |
| `filaPastillas({ items, activo, onchange, anadir, mas })` | Filtros en fila. Devuelve `{ el, set, valor }` | `ui.filaPastillas({ items: [{ id: "todas", texto: "Todas", cuenta: 8 }], activo: "todas", onchange })` |
| `tileTabs({ items, activo, onchange })` | Categoría grande con icono. Devuelve `{ el, set, valor, idPestana }` | `ui.tileTabs({ items: [{ id: "ll", texto: "Llegadas", icono: "key" }], activo: "ll" })` |
| `tabsSubrayado({ items, activo, onchange })` | Cambio de vista dentro de una categoría | `ui.tabsSubrayado({ items: [{ id: "h", texto: "Hoy" }, { id: "m", texto: "Mañana" }], activo: "h" })` |
| `tarjeta({ titulo, subtitulo, icono, chips, cuerpo, pie, seleccionada, onclick, variante, direccion })` | Elemento de una colección. Con `onclick` toda ella es un botón y no debe contener otros controles. `variante`: `normal`, `punteada`, `menta` | `ui.tarjeta({ titulo: "Claire Dubois", subtitulo: "24 a 27 oct", chips: [{ texto: "Conflicto", tono: "critico", punto: true }], onclick })` |
| `carrusel({ items, ancho })` | Opciones guiadas en horizontal, con flechas | `ui.carrusel({ ancho: 250, items: [tarjetaA, tarjetaB] })` |
| `panel({ titulo, subtitulo, acciones, hijos })` | Contenedor básico de toda vista. Su título es un `h2` | `ui.panel({ titulo: "Cola de trabajo", subtitulo: "Por prioridad", hijos: [tabla] })` |
| `kv(pares, { columnas })` | Etiqueta gris y valor en negrita. El valor es texto o un nodo | `ui.kv([{ etiqueta: "Canal", valor: "WhatsApp" }, { etiqueta: "Estado", valor: chip }])` |
| `menuOscuro({ ancla, items, alineacion })` | Acciones secundarias. Devuelve `{ abrir, cerrar, alternar }`. Los items son `{ texto, icono, onclick, peligro }` o `{ separador: true }` | `const m = ui.menuOscuro({ ancla: b, items }); b.addEventListener("click", () => m.alternar())` |
| `campo({ etiqueta, nombre, tipo, valor, opciones, placeholder, ayuda, error, obligatorio })` | Formularios. `tipo`: `texto`, `select`, `fecha`, `area` y similares. Devuelve `{ el, entrada, leer, poner, error }` | `ui.campo({ etiqueta: "Nombre", nombre: "n", obligatorio: true }).el` |
| `tabla({ columnas, filas, onfila, etiqueta })` | Datos tabulares con `caption`, `th scope` y filas con teclado. Cada columna es `{ clave, titulo, alinear, render }` | `ui.tabla({ etiqueta: "Llegadas de hoy", columnas, filas, onfila })` |
| `pasos(items, { onclick })` | Flujo vertical. Estados `hecho`, `actual`, `pendiente`, `bloqueado` | `ui.pasos([{ estado: "hecho", titulo: "Documento" }, { estado: "actual", titulo: "Parte" }])` |
| `vacio({ icono, titulo, texto, accion })` | Estado vacío o de error, con una acción útil | `ui.vacio({ icono: "inbox", titulo: "Nada pendiente", accion: { texto: "Actualizar", onclick } })` |
| `esqueleto({ lineas, alto })` | Estado de carga | `ui.esqueleto({ lineas: 4 })` |
| `ctx.avisar(texto, tono)` | Aviso breve tras una acción (`ok`, `critico`, `aviso`, `neutro`) | `ctx.avisar("Parte enviado (simulado)", "ok")` |
| `ctx.confirmar({ titulo, texto, confirmar, cancelar, tono, contenido })` | Diálogo previo a una acción que compromete. Devuelve una promesa de booleano. El botón nombra la acción | `if (await ctx.confirmar({ titulo: "Enviar el parte", confirmar: "Sí, enviar el parte" })) { ... }` |
| `avatar`, `separador`, `fechaCorta`, `hora`, `fechaHora`, `moneda`, `icono(nombre, { tam })` | Utilidades. `fechaCorta("2026-10-24")` da "24 oct" | `ui.moneda(192.73)` |

### 5.2 `ui-hotel.js`

Son las piezas compartidas del dominio. Úsalas siempre y no las dupliques.

| Función | Cuándo usarla | Ejemplo |
|---|---|---|
| `chipSemaforo(color, texto?)` | Color de una estancia, con su texto. `color`: `rojo`, `naranja`, `amarillo`, `azul`, `gris`, `verde` | `chipSemaforo(e.semaforo.color)` |
| `tonoDeColor(color)` | Tono (`critico`, `naranja`, `aviso`, `info`, `neutro`, `ok`) de un color del semáforo, para pintar bordes o chips propios | `ui.chip({ texto: "Revisar", tono: tonoDeColor("rojo") })` |
| `pastillaNivel(prioridad, { compacta })` | Nivel de prioridad de una fuente ("1 RoomCloud"). `prioridad` es `{ nivel, fuente, id, tipo }` tal como lo da la API. Compacta deja solo el número | `pastillaNivel(c.prioridad)` |
| `escalera(prioridades, { resaltar, compacta, reglas })` | La escalera de 5 niveles con las reglas. `prioridades` es `{ niveles, reglas }` de `GET /api/prioridades`. `resaltar` es el id de un nivel | `escalera(datos.prioridades, { resaltar: "correo", compacta: true })` |
| `chipVeredicto(veredicto)` | Veredicto de una petición: `disponible`, `ajustado`, `en_competencia`, `no_disponible`, `sin_datos` | `chipVeredicto(c.contraste.veredicto)` |
| `chipSistema(sistema, estado, { conNombre })` y `chipsSistemas(sistemas)` | Estado de una estancia en `roomcloud`, `ofihotel` y `documentacion`. `chipsSistemas` pinta los tres | `chipsSistemas(e.sistemas)` |
| `ICONO_FUENTE`, `NOMBRE_FUENTE`, `NOMBRE_COLOR`, `NOMBRE_SISTEMA` | Diccionarios para icono y nombre de cada fuente, color y sistema | `ui.icono(ICONO_FUENTE[f.id])` |

## 6. Recetas de las cinco pantallas

Cada pantalla empieza con la barra superior (`ctx.barra({ titulo, subtitulo, cta, acciones })`, que pinta el único `h1`) y sus paneles empiezan en `h2`. El orden es el de lectura de recepción: primero lo urgente y al final el detalle.

1. **Fuente única** (`#/fuente`). Panel de resumen con los totales y los datos de OfiHotel (de ayer), panel con la escalera de prioridades (`escalera`), panel de fuentes con su estado y un botón secundario para leer cada una, cola de trabajo ordenada tal como llega de la API (con `pastillaNivel` en cada fila) y panel de actividad reciente.
2. **Comunicaciones** (`#/comunicaciones`). Lista y detalle en `.u-dos-paneles`. A la izquierda `filaPastillas` por canal y tarjetas seleccionables con `pastillaNivel` y `chipVeredicto`. A la derecha, de arriba abajo, la alerta en tono crítico si existe, el mensaje recibido, el contraste noche a noche con el motivo, la respuesta editable y la acción principal "Confirmar y enviar por <canal>" como único `cta`, con "Descartar" como secundario.
3. **Estancias** (`#/estancias`). Lista y detalle. A la izquierda `filaPastillas` de filtro y contadores por color del semáforo, con tarjetas y `chipSemaforo`. A la derecha `kv` con los datos de la estancia, `chipsSistemas`, los conflictos si los hay, `pasos` de los trámites y la acción sugerida por el semáforo.
4. **Ocupación** (`#/ocupacion`). Mapa de habitaciones por día, panel de peticiones con `chipVeredicto` y, si hay conflictos, un panel con `chip` crítico antes del mapa. Cada casilla del mapa lleva texto además de color y el texto de la pantalla señala la tendencia y las excepciones sin recorrer los valores.
5. **Asistente** (`#/asistente`). Cabecera con sugerencias en `carrusel` de tarjetas punteadas cuando el chat está vacío, historial de mensajes con bloques (tarjetas, listas, `proceso` animado, burbujas de respuesta) y caja de texto abajo. Las líneas efímeras de herramienta se atenúan al terminar.

## 7. Microcopy

- **Registro.** Español de España con registro cuidado, también en etiquetas, avisos y errores. Frases completas, sin voz pasiva ni condicionales de cortesía ("podrías", "sería conveniente").
- **Prohibido** el em dash, la forma "no es X, es Y" (y sus variantes con "sino"), las metáforas y los emojis.
- **Vocabulario de dominio en inglés**: check-in, check-out, walk-in, overbooking. Rangos y categorías en minúscula.
- **Cada botón dice lo que hace**: "Confirmar y enviar por correo", "Descartar la petición", nunca "Aceptar" ni "OK". El botón de un diálogo repite la acción ("Sí, enviar el parte"). Los destructivos usan `tono: "critico"`.
- **Una cifra, una vez.** Si un dato aparece en dos sitios de la pantalla, quita uno. Si hay tabla o gráfica, el texto señala la tendencia y las excepciones y no recorre los valores.
- **Fechas y horas.** "24 oct" y horas de 24 horas. Dinero con `ui.moneda`.
- **Simulado.** Lo que sea simulado lo dice una vez, con la palabra "simulado", sin ruido.
- **Errores.** Se muestra `e.message` (la API ya responde en español) y se deja la vista usable con un botón para reintentar.

## 8. Accesibilidad

Nivel objetivo WCAG 2.2 AA.

- **Contraste.** Texto a 4,5:1 como mínimo (3:1 para texto grande), y bordes de controles, iconos y foco a 3:1. Se comprueba con `python scripts/contraste.py`, `python scripts/contraste.py b` y `python scripts/contraste.py c`. Si añades o cambias un token, vuelve a correrlo.
- **Foco visible** en todos los controles (anillo de `--c-enlace`). Nunca se quita sin sustituirlo.
- **Estados no solo con color.** Los chips llevan texto, las casillas del mapa llevan texto, los pasos llevan "(hecho)" para lectores y los enlaces se distinguen por algo más que el color.
- **Tablas** con `caption` (el parámetro `etiqueta` de `ui.tabla`), `th scope` y filas interactivas operables con Enter y espacio.
- **Un solo `h1`** por vista (lo pone la barra) y paneles con `h2`.
- **Botones solo de icono** con `etiqueta`. Campos con `label`. Regiones que cambian sin acción del usuario con `aria-live`.
- **Teclado.** Pestañas con flechas, menús con flechas y Escape, diálogos con foco atrapado (`<dialog>`).
- **Movimiento reducido.** `prefers-reduced-motion` lo gestiona la base. Las animaciones propias (por ejemplo la del `proceso`) deben mostrarse de golpe con esa preferencia.
- **Objetivos táctiles** de al menos 32 px en escritorio y 40 px en móvil.

## 9. Código

- Módulos ES nativos, sin dependencias, sin CDN ni fuentes externas, y funciona sin red.
- Los elementos se crean con `ctx.el`. **Prohibido** `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `eval`, `new Function` y atributos `on*` como string. Los atributos `on*` de `el()` solo aceptan funciones.
- Las peticiones van por `ctx.api` y nada de `fetch` directo. Nada de `alert`, `confirm` ni `prompt`.
- El CSS de una sección va bajo `.sec-<id>` y usa solo tokens.
- Funciones pequeñas con nombres en español y sin `console.log` en lo que entregas.

## 10. Cómo verificar con `scripts/captura.py`

El script arranca su propio servidor con datos propios, abre Chrome headless, ejecuta los pasos y devuelve un informe JSON con los errores de consola. Se lanza desde `martin/poc` y el detalle está en `design/VERIFICAR.md`.

```
python scripts/captura.py --ruta "#/fuente" --semilla completa --salida "%TEMP%/hotel/fuente-claro.png"
python scripts/captura.py --ruta "#/fuente" --tema oscuro --salida "%TEMP%/hotel/fuente-oscuro.png"
python scripts/captura.py --ruta "#/fuente" --ancho 390 --alto 844 --pagina-completa --salida "%TEMP%/hotel/fuente-movil.png"
python scripts/captura.py --ruta "#/galeria" --paso "tab:6" --salida "%TEMP%/hotel/foco.png"
```

Antes de entregar una pantalla tienes que haber mirado con `Read`:

1. La pantalla con la semilla `completa` en claro, en oscuro y a 390 px.
2. La pantalla con la semilla `vacia`.
3. Los flujos principales con clics reales (`--paso "click:..."`) y una captura tras cada paso importante.
4. Una pasada de teclado (`--paso "tab:N"`) para comprobar el foco.
5. Una comparación con `#/galeria`. Para ver otra línea, usa `--url` con `?linea=b` o `?linea=c`.
6. `python -m pytest tests -q` en verde y la captura sin errores de consola.

## 11. Checklist de entrega de una pantalla

- Usa los componentes de `ui.js` y `ui-hotel.js` y no duplica ninguno.
- Una sola acción `cta`, puesta en la barra.
- Estados de carga, vacío y error resueltos.
- Cero colores sueltos, cero `innerHTML`, cero `alert`, `confirm` o `prompt`, cero `fetch` directo.
- Claro, oscuro y 390 px revisados con capturas, y líneas B y C sin roturas.
- Texto sin em dash, sin "no es X, es Y" y sin metáforas.
- Tests en verde y sin errores de consola.
