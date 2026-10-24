# Contrato del núcleo de la demo de Uniroom

Este documento manda sobre `CONTRATO.md` en todo lo que dice. De `CONTRATO.md` siguen vigentes el apartado 2 (la interfaz `ctx` de una sección) y el 6 (plantillas). Si algo de aquí no te basta, no lo cambies por tu cuenta: sigue con lo que haya y apunta la petición en `peticiones_a_base` de tu informe.

## 0. Qué tiene que entender quien ve la demo

La aplicación **bebe de todas las fuentes** (RoomCloud, OfiHotel, recepción, correo y WhatsApp), **unifica la información** y la deja en una sola plataforma que hace de **fuente única de verdad**. Cada petición que llega por correo o WhatsApp aparece ya contrastada con las demás fuentes, recepción solo la confirma y **la respuesta sale por el mismo canal** por el que llegó. Cuando dos fuentes compiten por la misma habitación **gana la de mayor prioridad** y la pantalla lo dice con palabras. El asistente enseña los procesos y ejecuta las operaciones básicas.

Prioridad de las fuentes (escalera de 5 niveles, `GET /api/prioridades`):

| Nivel | Fuente | Tipo | Qué significa |
|---|---|---|---|
| 1 | RoomCloud | firme | Reservas de Booking, Expedia y la web, con garantía de pago |
| 2 | OfiHotel | firme | Lo registrado en el programa del hotel, con los datos de ayer |
| 3 | Recepción | firme | Walk-ins y peticiones que recepción ya ha confirmado |
| 4 | Correo | petición | Petición de fechas sin confirmar |
| 5 | WhatsApp | petición | Petición de fechas sin confirmar |

Lo firme (1 a 3) bloquea la habitación y una petición nunca lo desplaza. Entre peticiones gana el nivel más alto y, a igual nivel, la que llegó antes. Si entra una reserva de RoomCloud que ocupa el hueco de una petición, la petición pasa a "No disponible" y se avisa.

**Es una fachada.** Todo es de demostración salvo el chat y las operaciones básicas. No añadas funcionalidad que no se vea. Los envíos son simulados y la pantalla lo indica con la palabra "simulado" sin ensuciar. Fuera de alcance: OCR, facturas, albaranes, documentos, check-out (se hace en OfiHotel) y cualquier escritura en OfiHotel (solo se lee).

## 1. Reparto de ficheros

Cada agente trabaja en su rama `ui/<agente>` y solo toca sus ficheros. Todo lo demás es base y no se edita.

| Agente | Rama | Ficheros que posee |
|---|---|---|
| `fuente` | `ui/fuente` | `static/js/secciones/fuente.js`, `static/css/secciones/fuente.css` |
| `comunicaciones` | `ui/comunicaciones` | `static/js/secciones/comunicaciones.js`, `static/css/secciones/comunicaciones.css` |
| `estancias` | `ui/estancias` | `static/js/secciones/estancias.js`, `static/css/secciones/estancias.css` |
| `ocupacion` | `ui/ocupacion` | `static/js/secciones/ocupacion.js`, `static/css/secciones/ocupacion.css` |
| `asistente-shell` | `ui/asistente-shell` | `static/js/secciones/asistente.js`, `static/css/secciones/asistente.css` |
| `asistente-bloques` | `ui/asistente-bloques` | `static/js/secciones/asistente-bloques.js`, `static/css/secciones/asistente-bloques.css` |
| `back-bloques` | `ui/back-bloques` | `app/chat_bloques.py`, `app/chat_procesos.py` (nuevo), `tests/test_chat_bloques.py` |

Base (nadie la edita salvo quien integra): `app/main.py`, `app/hub.py`, `app/estados.py`, `app/prioridades.py`, `app/comunicaciones.py`, `app/disponibilidad.py`, `app/chat.py`, `app/lector.py`, `app/routers/*`, `static/index.html`, `static/css/{tokens,base,components,lineas,hotel}.css`, `static/js/{core,dom,ui,icons,secciones,ui-hotel}.js`, `design/*`, `scripts/*` y los tests que ya existen. Si necesitas un componente que no está, constrúyelo dentro de tu fichero y descríbelo en tu informe.

## 2. Front

La interfaz de una sección (`export default { id, montar(contenedor, ctx) }` y todo lo que ofrece `ctx`) está en `CONTRATO.md`, apartado 2, y el catálogo de componentes en `DIRECTRICES.md` y en `#/galeria`. Reglas que no se negocian: solo tokens de `tokens.css` (nada de colores sueltos), tema claro y oscuro, estados con texto además de color, foco visible, nada de `innerHTML`, nada de `alert`, `confirm` ni `prompt`, y todas tus clases bajo el prefijo `.sec-<id>`.

**Piezas compartidas** en `static/js/ui-hotel.js` (úsalas, no las dupliques): `chipSemaforo(color, texto?)`, `tonoDeColor(color)`, `pastillaNivel(prioridad, {compacta})`, `escalera(prioridades, {resaltar, compacta, reglas})`, `chipVeredicto(veredicto)`, `chipSistema(sistema, estado)`, `chipsSistemas(sistemas)`, y los diccionarios `ICONO_FUENTE`, `NOMBRE_FUENTE`, `NOMBRE_COLOR`, `NOMBRE_SISTEMA`. Importa con `import { ... } from "../ui-hotel.js"`. Los colores del semáforo son `rojo` (conflicto), `naranja` (parte pendiente), `amarillo` (falta pasar a OfiHotel), `azul` (por atender), `gris` (por reflejar) y `verde` (todo cuadrado).

Rutas (hash): `#/fuente`, `#/comunicaciones?id=cm-0001&canal=whatsapp|correo|todos`, `#/estancias?id=<id>&filtro=todas|hoy|en_casa|salidas&color=rojo`, `#/ocupacion`, `#/asistente?q=<pregunta>`.

## 3. API

Las formas reales están volcadas con la semilla `completa` en `design/muestras/*.json` (se regeneran con `python scripts/volcar_muestras.py`). Escribe contra esas muestras y no contra suposiciones. El reloj de la demo está fijo en `2026-10-24T09:00`.

| Método y ruta | Devuelve o hace | Muestra |
|---|---|---|
| `GET /api/prioridades` | `{niveles:[{nivel,id,nombre,tipo,icono,descripcion}], reglas:[texto]}` | `prioridades.json` |
| `GET /api/fuente-unica` | `{reloj, prioridades, fuentes[], cola[], actividad[], totales, datos_ofihotel, leyenda}` | `fuente-unica.json` |
| `GET /api/comunicaciones?estado=pendientes&canal=todos` | `{reloj, comunicaciones[], contadores, prioridades}` | `comunicaciones.json` |
| `GET /api/comunicaciones/{id}` | una comunicación (ver abajo) | `comunicacion.json` |
| `POST /api/comunicaciones/simular` | `{canal:"whatsapp"\|"correo", contacto, texto, nombre?, asunto?}` y devuelve la comunicación ya contrastada | |
| `PUT /api/comunicaciones/{id}/texto` | `{texto}` guarda el borrador editado | |
| `POST /api/comunicaciones/{id}/confirmar` | `{actor:"Flor", texto?}` envía por el canal de origen (simulado), reserva si hay hueco y devuelve la comunicación | |
| `POST /api/comunicaciones/{id}/descartar` | `{actor}` | |
| `GET /api/estancias?filtro=todas&color=` | `{reloj, datos_ofihotel, leyenda, estancias[], conflictos[], entradas, contadores}` | `estancias.json` |
| `GET /api/conflictos` | `{conflictos:[{id,tipo,nivel,expediente_id,sistemas,texto}]}` | `conflictos.json` |
| `GET /api/expedientes/{id}` | detalle con `registro`, `tramites`, `sistemas`, `semaforo`, `conflictos` | `expediente.json` |
| `POST /api/expedientes/{id}/tramites/ofihotel_alta` | `{actor, nota}` marca la estancia como pasada a OfiHotel | |
| `GET /api/ocupacion?dias=14` | mapa con `por_fuente` en cada casilla, `conflictos`, `peticiones[]` | `ocupacion.json` |
| `GET /api/propuestas?estado=pendiente` | propuestas (en la demo solo importa `cerrar_disponibilidad`) | `propuestas.json` |
| `POST /api/propuestas/{id}/aprobar` y `/rechazar` | `{actor}` | |
| `GET /api/insignias` | `{insignias:{comunicaciones, estancias, fuente}}` | `insignias.json` |
| `POST /api/sync/roomcloud` y `/api/sync/ofihotel` | leer la fuente (en la demo son simulados) | |
| `POST /api/demo/reserva-roomcloud` | `{tipo:"SGL-STD", desde?, hasta?, nombre?, personas?}` entra una reserva de Booking que desplaza a las peticiones | |
| `POST /api/demo/semilla?nivel=completa` | deja la demo en el estado inicial | |

**Comunicación** (`design/muestras/comunicacion.json`): `{id, ts, hora, canal, de:{nombre,contacto}, asunto, texto, tipo:"peticion_habitacion"|"pregunta"|"cambio"|"otro", idioma:"es"|"fr"|"en", peticion:{tipo_habitacion,desde,hasta,noches,personas,habitaciones}|null, prioridad:{nivel,fuente,id,tipo}, estado:"pendiente"|"en_espera"|"respondida"|"descartada", expediente_id|null, contraste|null, respuesta:{canal,destinatario,asunto,texto,idioma}, alerta:{hora,texto}|null, resultado:{hora,canal,destinatario,texto,accion:"reservada"|"en_espera"|"sin_hueco"|"respondida"|"descartada",reserva_id,actor,simulado}|null}`.

**Contraste**: `{veredicto:"disponible"|"ajustado"|"en_competencia"|"no_disponible"|"sin_datos", motivo (frase en español lista para mostrar), noches:[{fecha,capacidad,ocupadas,libres,retenidas,libres_para_esta,por_fuente:{roomcloud,ofihotel,recepcion},ocupantes:{roomcloud:[nombre],ofihotel:[...],recepcion:[...]},retenida_por:[idComunicacion]}], bloqueada_por:[{fuente,id,nivel,cantidad,ocupantes}], retenida_por:[{comunicacion,de,canal,nivel,fuente,hora}], alternativa:{desde,hasta,noches}|null}`. `ocupadas` cuenta lo firme, `retenidas` lo que ocupan peticiones de mayor prioridad y `libres_para_esta` es lo que le queda a esta petición.

**Estancia** (cada elemento de `estancias`): `{id, huesped, estado, checkin, checkout, pendientes, parte, parte_restante_h, viaja_por_trabajo, tipo, origen, personas, prioridad, sistemas:{roomcloud,ofihotel,documentacion}:{estado,detalle}, semaforo:{color,tono,motivo,accion_sugerida}}`.

Ordenación y avisos: la cola de `fuente-unica` ya viene ordenada por prioridad de la fuente y después por urgencia. No la reordenes en el front. Las alertas de una comunicación (`alerta`) se muestran siempre arriba y en tono crítico.

## 4. Chat

`POST /api/chat/stream` con `{mensaje, historial:[{role:"user"|"assistant", content}]}` responde `text/event-stream`. Se consume con `fetch` y `ReadableStream` (no con `EventSource`, que no admite POST). Eventos, cada uno con `event: <nombre>` y `data: <json>`:

| Evento | Datos | Qué hace el front |
|---|---|---|
| `herramienta` | `{id, nombre, etiqueta, estado:"inicio"\|"fin"}` | Línea efímera de progreso ("Consultando las comunicaciones"); se atenúa al terminar |
| `bloque` | un bloque (apartado 4.1) | Lo añade al mensaje del asistente en cuanto llega |
| `texto` | `{delta}` | Añade texto al mensaje, como texto plano |
| `fin` | `{respuesta, modo:"real"\|"simulado", propuestas:[id]}` | Cierra el mensaje y habilita la caja |
| `error` | `{mensaje}` | Muestra el aviso y habilita la caja |

`POST /api/chat` devuelve lo mismo de una vez (`{respuesta, modo, propuestas, bloques}`) y es el plan B si el stream falla. `GET /api/chat/sugerencias` y `GET /api/chat/bloques-muestra` siguen como en `CONTRATO.md` apartado 4.5, con contenido nuevo.

**Seguridad (obligatoria).** Los bloques y sus acciones los construye el servidor a partir de lo que devuelven las herramientas, nunca a partir del texto del modelo. El modelo solo elige herramientas y casi todas son de lectura. El texto de la respuesta se pinta siempre como texto, sin HTML ni markdown.

### 4.1 Bloques

Todos los textos son texto plano y `tono` es `neutro|ok|aviso|critico|info`. Siguen vigentes `resumen_kpi`, `tabla_ocupacion`, `propuesta`, `formulario` (solo `walkin`), `aviso` y `sugerencias` tal como están en `CONTRATO.md` apartado 5. Cambian o se añaden estos:

```json
{"tipo": "tarjeta_reserva", "id": "2-EX-7730021", "titulo": "Claire Dubois", "subtitulo": "24/10 a 27/10 · DBL-STD",
 "chips": [{"texto": "Conflicto", "tono": "critico"}], "campos": [{"etiqueta": "Origen", "valor": "RoomCloud"}],
 "prioridad": {"nivel": 1, "fuente": "RoomCloud", "id": "roomcloud", "tipo": "firme"},
 "semaforo": {"color": "rojo", "motivo": "…", "accion_sugerida": "Revisar el conflicto"},
 "sistemas": {"roomcloud": {"estado": "sincronizado", "detalle": "…"}, "ofihotel": {"estado": "migrado", "detalle": "…"}, "documentacion": {"estado": "sin_datos", "detalle": "…"}},
 "acciones": [{"tipo": "abrir_estancia", "etiqueta": "Abrir", "id": "2-EX-7730021"}]}

{"tipo": "lista_estancias", "titulo": "Estancias con algo pendiente", "contadores": {"rojo": 1, "naranja": 1, "amarillo": 1, "azul": 0, "gris": 1, "verde": 0},
 "estancias": [ /* cada una con la forma de Estancia del apartado 3 */ ]}

{"tipo": "comunicacion", "comunicacion": { /* la comunicación completa del apartado 3, con contraste y respuesta */ },
 "acciones": [{"tipo": "confirmar_comunicacion", "etiqueta": "Confirmar y enviar por correo", "id": "cm-0001"},
              {"tipo": "descartar_comunicacion", "etiqueta": "Descartar", "id": "cm-0001"}, {"tipo": "abrir_comunicacion", "etiqueta": "Abrir", "id": "cm-0001"}]}

{"tipo": "lista_comunicaciones", "titulo": "Peticiones por confirmar", "comunicaciones": [ /* comunicaciones completas */ ]}

{"tipo": "fuentes", "titulo": "De dónde bebe la aplicación", "fuentes": [ /* fuentes de /api/fuente-unica */ ], "prioridades": {"niveles": [], "reglas": []},
 "acciones": [{"tipo": "sincronizar", "etiqueta": "Leer RoomCloud", "fuente": "roomcloud"}]}

{"tipo": "prioridades", "titulo": "Quién gana cuando dos cosas compiten", "prioridades": {"niveles": [], "reglas": []}, "resaltar": "correo"}

{"tipo": "cola", "titulo": "Qué atender primero", "items": [ /* cola de /api/fuente-unica */ ]}

{"tipo": "conflictos", "titulo": "Conflictos entre fuentes", "conflictos": [{"id": "cf-1", "tipo": "fechas_distintas", "nivel": "rojo", "texto": "…", "expediente_id": "2-EX-7730021", "sistemas": ["roomcloud", "ofihotel"]}]}

{"tipo": "navegacion", "titulo": "Ir a una pantalla", "items": [{"seccion": "comunicaciones", "titulo": "Comunicaciones", "descripcion": "Peticiones contrastadas, listas para confirmar", "icono": "inbox", "params": {}, "insignia": 6}]}

{"tipo": "proceso", "id": "peticion_mensaje", "titulo": "Cómo entra una petición por WhatsApp o correo", "resumen": "…",
 "pasos": [{"id": "recibir", "titulo": "Llega el mensaje", "fuente": "whatsapp", "detalle": "…", "dato": "Prioridad 5 (WhatsApp)", "resultado": "Petición entendida: doble, 28 al 30 de octubre"}],
 "acciones": [{"tipo": "abrir_seccion", "etiqueta": "Ver las comunicaciones", "seccion": "comunicaciones", "params": {}}]}
```

`flujo` desaparece (sus pasos eran del check-in con documento). `proceso` lo sustituye: es la explicación animada de un proceso con datos fijos. Cada paso lleva `fuente` (una clave de `ICONO_FUENTE` o `sistema`), `detalle`, `dato` opcional (un dato corto que enseña qué hace el sistema) y `resultado` opcional. El front los va revelando uno a uno (unos 600 ms por paso), y con `prefers-reduced-motion` los muestra de golpe. Al terminar aparecen las `acciones`. Los procesos que existen: `peticion_mensaje`, `reserva_canal`, `checkin_parte`, `overbooking_cierre`, `fuente_unica`, `prioridades`.

### 4.2 Acciones

Lista cerrada. El pintado solo ejecuta estos tipos. Cada acción devuelve al bloque `{ok, mensaje, estado, detalle}` para que se vea actualizado.

| Tipo | Campos | Efecto |
|---|---|---|
| `preguntar` | `texto` | Envía ese texto al chat como si lo hubiera escrito la persona |
| `abrir_seccion` | `seccion`, `params` | Navega a `#/<seccion>?...` |
| `abrir_estancia` | `id` | Navega a `#/estancias?id=…` |
| `abrir_comunicacion` | `id` | Navega a `#/comunicaciones?id=…` |
| `confirmar_comunicacion` | `id`, `texto` opcional | `POST /api/comunicaciones/{id}/confirmar` con diálogo previo que muestra canal, destinatario y texto |
| `descartar_comunicacion` | `id` | `POST /api/comunicaciones/{id}/descartar` con confirmación |
| `aprobar_propuesta` y `rechazar_propuesta` | `id` | `POST /api/propuestas/{id}/aprobar` o `rechazar`; aprobar pide confirmación |
| `enviar_formulario` | `formulario` y valores | `walkin` envía `POST /api/walkin` y, si hay conflicto (409), ofrece forzar |
| `sincronizar` | `fuente` | `POST /api/sync/{fuente}` |
| `simular_roomcloud` | `tipo` opcional | `POST /api/demo/reserva-roomcloud` |
| `marcar_ofihotel` | `id` | `POST /api/expedientes/{id}/tramites/ofihotel_alta` |

## 5. Textos que ve el usuario

Español de España, registro cuidado, frases completas, sin voz pasiva ni condicionales de cortesía ("podrías", "sería conveniente"). Sin em dash (—), sin la forma "no es X, es Y" y sin metáforas. El vocabulario de dominio va en inglés: check-in, walk-in, overbooking. Los rangos y categorías, en minúscula. Cada botón dice lo que hace ("Confirmar y enviar por correo", no "Aceptar"). Una cifra, una vez: no repitas el mismo dato en dos sitios de la pantalla. Si hay tabla o gráfica, el texto señala la tendencia y las excepciones y no recorre los valores. Todo lo que sea simulado lo dice una vez, sin ruido.

## 6. Verificación y entrega

1. Tu worktree arranca en otra base. Antes de nada: `git fetch origin && git checkout -B ui/<agente> origin/ui/base` y confirma que existe `martin/poc/design/CONTRATO-CORE.md`. Todo el trabajo va en `martin/poc`.
2. Mira `design/VERIFICAR.md` y usa `python scripts/captura.py` para capturar tu pantalla con la semilla `completa`, en tema claro y oscuro y a ancho de móvil (390 px) y de escritorio (1280 px). Mira tus capturas con Read y corrige lo que esté mal antes de dar nada por hecho. La captura debe terminar sin errores de consola.
3. Los tests de Python no son tuyos (salvo `back-bloques`). Antes de entregar corre `python -m pytest tests -q` y confirma que sigue en verde.
4. Haz commits pequeños con mensajes en español. `git push origin ui/<agente>`. Nunca hagas merge ni empujes a otra rama.
5. No escribas ninguna clave de API en ningún fichero ni en tu informe. No llames a ningún servicio externo.
6. Tu respuesta final es un informe corto: qué has hecho, qué ficheros, qué capturas has mirado y qué viste en ellas, qué falla o falta, y `peticiones_a_base` con el cambio exacto que necesitas en ficheros de base si lo hay.
