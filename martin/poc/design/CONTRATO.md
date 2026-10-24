# Contrato del hub: secciones, API, bloques del chat y reparto de ficheros

Este documento es la fuente de verdad para que varios agentes trabajen en paralelo sin pisarse. Si algo de aquí no te basta,
no lo cambies por tu cuenta: sigue con lo que haya y apunta la desviación o la petición en el campo `peticiones_a_base` de tu informe final.

Todo el texto que ve el usuario va en español con registro cuidado (ver `DIRECTRICES.md`, apartado de microcopy).

## 1. Secciones y propietarios

Cada agente trabaja en su rama `ui/<agente>` y solo toca los ficheros que se le asignan aquí. Los ficheros de la columna "Base" no los edita nadie salvo el integrador.

| Agente | Rama | Ficheros que posee |
|---|---|---|
| `asistente-shell` | `ui/asistente-shell` | `static/js/secciones/asistente.js`, `static/css/secciones/asistente.css` |
| `asistente-bloques` | `ui/asistente-bloques` | `static/js/secciones/asistente-bloques.js`, `static/css/secciones/asistente-bloques.css` |
| `hoy` | `ui/hoy` | `static/js/secciones/hoy.js`, `static/css/secciones/hoy.css` |
| `bandeja` | `ui/bandeja` | `static/js/secciones/bandeja.js`, `static/css/secciones/bandeja.css` |
| `ocupacion` | `ui/ocupacion` | `static/js/secciones/ocupacion.js`, `static/css/secciones/ocupacion.css` |
| `recepcion-lista` | `ui/recepcion-lista` | `static/js/secciones/recepcion.js`, `static/css/secciones/recepcion.css` |
| `recepcion-pasos` | `ui/recepcion-pasos` | `static/js/secciones/recepcion-pasos.js`, `static/css/secciones/recepcion-pasos.css` |
| `mensajes` | `ui/mensajes` | `static/js/secciones/mensajes.js`, `static/css/secciones/mensajes.css` |
| `documentos-front` | `ui/documentos-front` | `static/js/secciones/documentos.js`, `static/css/secciones/documentos.css` |
| `integraciones-front` | `ui/integraciones-front` | `static/js/secciones/integraciones.js`, `static/css/secciones/integraciones.css` |
| `back-chat` | `ui/back-chat` | `app/chat.py`, `app/chat_bloques.py`, `app/routers/chat.py`, `tests/test_chat_bloques.py` |
| `back-mensajes` | `ui/back-mensajes` | `app/routers/mensajes.py`, `app/adapters/correo.py`, `tests/test_mensajes.py` |
| `back-hoy` | `ui/back-hoy` | `app/routers/hoy.py`, `app/routers/integraciones.py`, `tests/test_hoy_integraciones.py` |
| `back-documentos` | `ui/back-documentos` | `app/documentos.py`, `app/routers/documentos.py`, `fixtures/hotel.json`, `tests/test_documentos.py` |

**Base (no editar):** `app/main.py`, `app/hub.py`, `app/plantillas.py`, `app/lector.py`, `app/store.py`, `app/deps.py`, `app/routers/demo.py`, `requirements.txt`,
`static/index.html`, `static/legacy.html`, `static/css/tokens.css`, `static/css/base.css`, `static/css/components.css`, `static/js/core.js`, `static/js/dom.js`, `static/js/ui.js`,
`static/js/icons.js`, `static/js/secciones.js`, `static/js/secciones/galeria.js`, `static/css/secciones/galeria.css`, `design/*`, `scripts/*`, y los tests que ya existen.

Si necesitas un componente reutilizable que no está en `ui.js`, constrúyelo dentro de tu propio fichero y descríbelo en tu informe para que el integrador decida si lo promueve.
Si necesitas cambiar un fichero de base, no lo hagas: pídelo en `peticiones_a_base` con el cambio exacto.

## 2. Interfaz de una sección (front)

```js
// static/js/secciones/<id>.js
export default {
  id: "bandeja",
  async montar(contenedor, ctx) {
    ctx.barra({ titulo: "Bandeja", subtitulo: "Lo que ha llegado y lo que espera aprobación",
                cta: { texto: "Aprobar", icono: "check", onclick: () => {} },          // opcional, un solo botón amarillo
                acciones: [{ icono: "refresh", etiqueta: "Actualizar", onclick: recargar }] });   // opcional, botones fantasma
    // ... construir la vista dentro de `contenedor` con ctx.el y ctx.ui
    const baja = ctx.suscribir("datos-cambiaron", recargar);
    return { destruir() { baja(); } };           // opcional: limpiar temporizadores y suscripciones
  },
};
```

`ctx` ofrece, y solo esto:

- `api(ruta, metodo = "GET", cuerpo)`: devuelve el JSON. `ruta` puede ser `"/api/bandeja"` o `"/bandeja"`. Si la respuesta no es 2xx lanza `ErrorApi` con `status`, `detalle` y un `message` ya en español (junta `problemas`, `faltan`, `pendientes` o `conflicto`). Tras cualquier petición que no sea GET y salga bien emite `datos-cambiaron` solo.
- `el(tag, atributos, ...hijos)`: crea elementos. Los hijos de tipo string son nodos de texto (nunca HTML). Atributos: `class`, `id`, `dataset`, `aria` (objeto que se vuelve `aria-*`), `on<evento>` (función), cualquier otro se pasa a `setAttribute`.
- `ui`: las primitivas de `ui.js` (ver `DIRECTRICES.md`, catálogo).
- `navegar(id, params)`: cambia de sección (`#/id?clave=valor`).
- `params`: objeto con los parámetros del hash al montar (ver apartado 7).
- `suscribir(evento, fn)`: devuelve la función para darse de baja. Eventos: `datos-cambiaron`, `reloj-cambio`, `seccion-activa`.
- `avisar(texto, tono)`: toast; `tono` es `neutro`, `ok`, `aviso` o `critico`.
- `confirmar({ titulo, texto, confirmar, cancelar, tono })`: diálogo propio que devuelve una promesa de booleano. Prohibido `alert`, `confirm` y `prompt`.
- `estado`: `{ reloj, modos }` (lo mismo que `/api/estado`).
- `barra(opciones)`: rellena la barra superior (título, subtítulo, un CTA y acciones fantasma).
- `insignia(seccionId, n)`: pone el contador del menú lateral (lo normal es dejar que el núcleo lo haga con `/api/hoy`).

### 2b. Interfaces entre dos agentes de la misma sección

**Recepción** la construyen dos agentes. `recepcion-lista` posee `recepcion.js` (lista de estancias a la izquierda con filtros `hoy`, `en_casa`, `salidas` y `todos`, cabecera del detalle con `kv` y chips, y la composición de los pasos) y
`recepcion-pasos` posee `recepcion-pasos.js`, que exporta dos funciones:

```js
export function crearPasos(exp, ctx, { recargar }) { /* ... */ }   // -> [{ id, titulo, estado, resumen, contenido }]
export function crearRegistro(exp, ctx) { /* ... */ }              // -> HTMLElement con la línea de tiempo (exp.registro)
```

`exp` es el JSON de `GET /api/expedientes/{id}` completo. `crearPasos` devuelve cinco pasos con estos `id`, en este orden: `documento` (lectura OCR y datos del huésped), `pago` (medio de pago y datos de empresa con correo),
`parte` (previsualización del XML y confirmación), `ofihotel` (datos para copiar y casilla de alta hecha) y `checkout` (factura, habitación liberada y cierre). `estado` es `hecho`, `actual`, `pendiente` o `bloqueado`
(sale de `exp.tramites` y de lo que falte), `resumen` es una frase corta para el paso plegado y `contenido` es el `HTMLElement` con los controles del paso. `recargar()` vuelve a pedir la estancia y repinta.
`recepcion.js` pinta los pasos con `ui.pasos` y muestra el `contenido` del paso `actual` (o del que pida `ctx.params.paso`) en un panel a la derecha. El check-out enlaza con Documentos (`ctx.navegar("documentos", { nuevo: exp.id })`).

**Chat.** `asistente-shell` posee `asistente.js` (pantalla de bienvenida, lista de mensajes, caja de texto, historial y el despachador de acciones `ejecutar`) y `asistente-bloques` posee `asistente-bloques.js`
(la función `renderBloque(bloque, { ejecutar, ui, el })` del apartado 5, con un pintado por cada tipo de bloque).

## 3. API existente (no cambiar su forma)

Se ve en `app/main.py` y en `static/legacy.html` (la interfaz antigua, que sigue funcionando en `/legacy` y sirve de referencia de uso):
`/api/estado`, `/api/reiniciar`, `/api/reloj`, `/api/sync/roomcloud`, `/api/sync/ofihotel`, `/api/panel`, `/api/expedientes[/{id}[/ocr|huesped|pago|parte|parte/confirmar|ofihotel|tramites/{t}|cerrar]]`,
`/api/disponibilidad`, `/api/walkin`, `/api/webhook/whatsapp`, `/api/whatsapp/simular`, `/api/bandeja`, `/api/propuestas[/{id}/aprobar|rechazar]`, `/api/chat`.

Añadidos en la base (todos opcionales para quien no los use):

- `EmpresaIn` admite `email` (opcional) además de `razon_social`, `cif` y `direccion`. El correo de la empresa es uno de los destinatarios válidos para enviar documentos.
- `POST /api/demo/semilla?nivel=vacia|basica|completa` deja el sistema en un estado de demostración coherente. `completa` incluye reservas de RoomCloud, lectura de OfiHotel, a Ana con check-in hecho y parte enviado, un mensaje de WhatsApp de Ana, un correo de Claire pidiendo su factura, propuestas pendientes, un albarán en borrador y una factura emitida.
- `HOTEL_DB` (variable de entorno) cambia la ruta del JSON de datos, para que cada agente use el suyo.

## 4. API nueva

Los esquemas completos están en `app/routers/*.py` en forma de datos de muestra. Los routers de base devuelven datos de muestra con la forma definitiva y los agentes `back-*` los sustituyen por lógica real **sin cambiar la forma**. `tests/test_contrato.py` valida estas formas y debe seguir pasando.

### 4.1 `GET /api/hoy` (agente `back-hoy`)

```json
{
  "reloj": "2026-10-24T09:00",
  "kpis": [
    {"id": "llegadas", "etiqueta": "Llegadas de hoy", "valor": 3, "detalle": "1 con check-in hecho", "tono": "neutro", "ruta": "recepcion"},
    {"id": "en_casa", "etiqueta": "En casa", "valor": 1, "detalle": "", "tono": "neutro", "ruta": "recepcion"},
    {"id": "salidas", "etiqueta": "Salidas de hoy", "valor": 0, "detalle": "", "tono": "neutro", "ruta": "recepcion"},
    {"id": "partes", "etiqueta": "Partes sin enviar", "valor": 1, "detalle": "el más urgente vence en 20 h", "tono": "aviso", "ruta": "recepcion"},
    {"id": "pendientes", "etiqueta": "Pendientes de aprobar", "valor": 2, "detalle": "", "tono": "aviso", "ruta": "bandeja"},
    {"id": "sin_responder", "etiqueta": "Mensajes sin responder", "valor": 2, "detalle": "1 WhatsApp y 1 correo", "tono": "aviso", "ruta": "mensajes"},
    {"id": "ocupacion", "etiqueta": "Ocupación de hoy", "valor": "100 %", "detalle": "3 de 3 DBL-STD", "tono": "critico", "ruta": "ocupacion"},
    {"id": "documentos", "etiqueta": "Documentos por enviar", "valor": 1, "detalle": "", "tono": "neutro", "ruta": "documentos"}
  ],
  "alertas": [{"id": "al-1", "nivel": "critico|aviso|info", "texto": "DBL-STD completo el 24/10", "ruta": "ocupacion", "params": {}}],
  "llegadas": [ /* resumen de expediente, como en /api/panel */ ],
  "salidas": [ /* idem */ ],
  "proximas_acciones": [{"texto": "Aprobar la respuesta a Ana", "ruta": "bandeja", "params": {"propuesta": "pr-0003"}}],
  "insignias": {"bandeja": 2, "mensajes": 2, "recepcion": 1, "documentos": 1}
}
```

`tono` es `neutro`, `ok`, `aviso` o `critico`. `ruta` es el id de una sección.

### 4.2 `GET /api/integraciones` (agente `back-hoy`)

```json
{
  "reloj": "2026-10-24T09:00",
  "integraciones": [
    {"id": "roomcloud", "nombre": "RoomCloud", "tipo": "Channel manager", "modo": "simulado|real|supuesto", "estado": "ok|aviso|error|desconectado",
     "resumen": "XML grabado y reconstruido", "ultima_sync": "2026-10-24T09:00",
     "capacidades": ["Leer reservas"], "limites": ["No escribe disponibilidad sin aprobación"],
     "acciones": [{"id": "sincronizar", "etiqueta": "Leer reservas", "metodo": "POST", "ruta": "/api/sync/roomcloud"}]}
  ],
  "avisos_globales": ["Todo lo marcado como simulado no sale de este equipo."]
}
```

Ids de integración: `roomcloud`, `ofihotel`, `whatsapp`, `correo`, `ses`, `ocr`, `lector`, `chat`. `ultima_sync` puede ser `null`.

### 4.3 Mensajes: WhatsApp y correo (agente `back-mensajes`)

Una conversación es un hilo con una persona por un canal. Su `id` es `wa:<wa_id>` o `mail:<direccion en minúsculas>`.

- `GET /api/mensajes/conversaciones?canal=todos|whatsapp|correo`

```json
{"conversaciones": [{
  "id": "wa:34600111222", "canal": "whatsapp", "nombre": "Ana", "contacto": "34600111222", "expediente_id": "1-BK-4471920",
  "ultimo": {"texto": "Hola, ¿a qué hora es el check-in?", "hora": "09:00", "direccion": "entrante"},
  "sin_responder": true, "intencion": "pregunta_checkin_horario", "propuestas_pendientes": 1
}]}
```

- `GET /api/mensajes/conversaciones/{id}`

```json
{"conversacion": { /* igual que arriba */ },
 "mensajes": [{"id": "ev-0007", "direccion": "entrante|saliente", "hora": "09:00", "texto": "…", "asunto": null,
               "adjuntos": [{"nombre": "Factura DEMO-F-0001.pdf", "documento_id": "doc-0003"}],
               "interpretacion": {"intencion": "pregunta_checkin_horario", "confianza": 0.6, "modo": "reglas"}, "simulado": true}],
 "propuestas": [ /* propuestas pendientes de esta conversación */ ]}
```

- `POST /api/mensajes/conversaciones/{id}/proponer` con `{"plantilla": "info_llegada", "slots": {"nombre": "Ana"}}` crea una propuesta pendiente (nunca envía). Devuelve la propuesta o 422 con `{"problemas": [...]}`.
- `POST /api/correo/simular` con `{"de": "claire.dubois@example.com", "nombre": "Claire Dubois", "asunto": "Factura de mi estancia", "cuerpo": "…"}` simula un correo entrante con la forma de un mensaje de la API de Gmail (`payload.headers`, `payload.body.data` en base64url, `snippet`, `internalDate`), pasa por el mismo lector que WhatsApp y puede generar una propuesta. Devuelve `[{"evento": "ev-…", "propuesta": "pr-…"|null}]` igual que `/api/whatsapp/simular`.

### 4.4 Documentos: facturas y albaranes (agente `back-documentos`)

**Aviso fiscal que hay que respetar en todo el producto.** Una factura emitida por este sistema sería software de facturación sujeto a Verifactu (en vuestro `docs/02-investigacion.md`: sociedades desde el 1 de enero de 2027, autónomos desde el 1 de julio de 2027). Por eso en la demo **toda factura es un borrador no fiscal**: lleva `fiscal: false`, el texto "Documento de demostración sin validez fiscal" y una numeración de demostración (`DEMO-F-0001`). Las facturas con validez las sigue emitiendo OfiHotel. El producto real tiene dos caminos legales: subir la factura que ya emitió OfiHotel para enviarla (origen `subido`), o integrar un servicio de facturación homologado. Los albaranes no son documentos fiscales.

Modelo (`db["documentos"]`, indexado por `id`):

```json
{
  "id": "doc-0003", "tipo": "factura|albaran", "estado": "borrador|emitido|enviado|anulado", "numero": null,
  "origen": "generado|subido", "fiscal": false, "aviso_fiscal": "Documento de demostración sin validez fiscal",
  "expediente_id": "1-BK-4471920", "fecha": "2026-10-24",
  "emisor": {"razon_social": "Hotel Demo SL", "nif": "B00000000", "direccion": "Rúa Demo 1, 15000 A Coruña", "email": "recepcion@hoteldemo.example"},
  "receptor": {"nombre": "Atlántico Consultores SL", "nif": "B15000000", "direccion": "Rúa Real 1, A Coruña", "email": "facturas@atlantico.example"},
  "lineas": [{"concepto": "Alojamiento DBL-STD, 2 noches", "cantidad": 2, "precio_unitario": 96.36, "iva_pct": 10}],
  "totales": {"base": 192.73, "iva": 19.27, "total": 212.00, "moneda": "EUR"},
  "archivo": null,
  "envios": [{"hora": "2026-10-24T09:00", "destinatario": "facturas@atlantico.example", "evento_id": "ev-0012", "simulado": true, "actor": "Flor"}],
  "registro": [{"hora": "2026-10-24T09:00", "actor": "Sistema", "accion": "Borrador creado desde el expediente"}]
}
```

`numero` es `null` mientras sea borrador. Al emitir se asigna el siguiente de la serie del tipo, sin saltos (`DEMO-F-0001`, `DEMO-A-0001`). El IVA del alojamiento es un valor de configuración de demostración (`fixtures/hotel.json`), no un dato fiscal verificado. Un albarán no necesita precios.

Endpoints:

- `GET /api/documentos?tipo=&estado=&expediente=` devuelve `{"documentos": [{"id", "tipo", "estado", "numero", "expediente_id", "receptor_nombre", "total", "fecha", "enviado", "fiscal", "origen"}]}`.
- `GET /api/documentos/{id}` devuelve el documento completo.
- `POST /api/documentos/borrador` con `{"tipo": "factura|albaran", "expediente_id": "…", "lineas": [...]|null}` crea un borrador (las líneas por defecto salen de la estancia: noches por tarifa media del importe total) y devuelve el documento.
- `PUT /api/documentos/{id}` con `{"lineas": [...], "receptor": {...}}` edita un borrador. Un documento emitido no se edita (409).
- `POST /api/documentos/{id}/emitir` con `{"actor": "Flor"}` asigna número y pasa a `emitido`. Es una acción humana con confirmación en pantalla.
- `GET /api/documentos/{id}/html` devuelve el documento como HTML imprimible (con estilos de impresión) y `GET /api/documentos/{id}/pdf` como PDF (`fpdf2`). Los dos llevan visible el aviso fiscal.
- `POST /api/documentos/{id}/enviar` con `{"actor": "Flor", "destinatario": "…"|null, "confirmar_destinatario_nuevo": false}` envía por correo (simulado) con el PDF adjunto. Solo documentos emitidos. Si `destinatario` no es un correo conocido de la estancia, responde 409 salvo que venga `confirmar_destinatario_nuevo: true`, y esa confirmación queda en el registro.
- `POST /api/documentos/subir` con `{"tipo": "factura", "expediente_id": "…", "numero": "2026/0123", "nombre_archivo": "factura.pdf", "contenido_b64": "…"}` guarda un PDF ya emitido fuera (límite de 5 MB, debe empezar por `%PDF`) como documento de origen `subido`, estado `emitido` y `fiscal: true`.

### 4.5 Chat (agente `back-chat`)

- `POST /api/chat` con `{"mensaje": "…", "historial": [{"role": "user|assistant", "content": "…"}]}` devuelve `{"respuesta": "texto plano", "modo": "…", "propuestas": ["pr-0007"], "bloques": [ … ]}`.
- `GET /api/chat/bloques-muestra` devuelve un bloque de cada tipo con datos de ejemplo (para desarrollar el pintado sin depender del resto).
- `GET /api/chat/sugerencias` devuelve `{"categorias": [{"id": "llegadas", "titulo": "Llegadas", "icono": "key", "preguntas": ["¿Qué llegadas hay hoy?"]}], "flujos": [{"id": "checkin", "titulo": "Hacer un check-in", "descripcion": "…", "icono": "door", "pregunta": "Quiero hacer el check-in de Ana"}]}` para la pantalla de bienvenida.

**Seguridad del chat (obligatoria).** Los bloques y sus acciones los construye el servidor a partir de lo que devuelven las herramientas, nunca a partir del texto que escribe el modelo. El modelo solo elige herramientas. Sus herramientas son de lectura salvo `proponer_accion`, que solo crea una propuesta validada. El texto de `respuesta` se pinta siempre como texto, sin HTML.

Herramientas del asistente: `reservas_hoy`, `ocupacion`, `partes_pendientes`, `mensajes_recientes`, `propuestas_pendientes`, `documentos` (listar y estado), `previsualizar_documento` (calcula líneas y totales sin guardar nada), `mostrar_formulario` (devuelve un bloque de formulario), `flujo_estancia` (pasos de una estancia) y `proponer_accion`.

## 5. Bloques del chat

Cada bloque tiene `tipo` y los campos que siguen. Todos los textos son texto plano. `tono` es `neutro|ok|aviso|critico|info`.

```json
{"tipo": "resumen_kpi", "titulo": "Hoy", "items": [{"etiqueta": "Llegadas", "valor": "3", "detalle": "", "tono": "neutro"}]}

{"tipo": "tarjeta_reserva", "id": "1-BK-4471920", "titulo": "Ana Pereira Lage", "subtitulo": "24/10 a 26/10 · DBL-STD",
 "chips": [{"texto": "pendiente de llegada", "tono": "aviso"}],
 "campos": [{"etiqueta": "Origen", "valor": "RoomCloud"}, {"etiqueta": "Viaja por trabajo", "valor": "Sí"}],
 "acciones": [{"tipo": "abrir_expediente", "etiqueta": "Abrir", "id": "1-BK-4471920"}]}

{"tipo": "tabla_ocupacion", "fechas": ["2026-10-24"], "filas": [{"tipo": "DBL-STD", "capacidad": 3,
 "celdas": [{"fecha": "2026-10-24", "ocupadas": 3, "libres": 0, "cerrado": false}]}]}

{"tipo": "flujo", "titulo": "Check-in de Ana Pereira", "pasos": [
 {"id": "huesped", "titulo": "Documento y datos", "estado": "hecho|actual|pendiente|bloqueado", "detalle": "NIF 12345678Z",
  "accion": {"tipo": "abrir_expediente", "etiqueta": "Abrir paso", "id": "1-BK-4471920", "paso": "documento"}}]}

{"tipo": "propuesta", "id": "pr-0003", "texto": "Hola Ana, el check-in empieza a las 14:00 …", "plantilla": "info_llegada", "destino": "whatsapp",
 "origen": "enrutador", "destinatario": "34600111222", "estado": "pendiente|aprobada|rechazada",
 "acciones": [{"tipo": "aprobar_propuesta", "etiqueta": "Aprobar", "id": "pr-0003"}, {"tipo": "rechazar_propuesta", "etiqueta": "Rechazar", "id": "pr-0003"}]}

{"tipo": "lista_mensajes", "titulo": "Últimos mensajes", "mensajes": [{"de": "Ana", "canal": "whatsapp", "hora": "09:00", "texto": "…", "intencion": "pregunta_checkin_horario",
 "accion": {"tipo": "abrir_conversacion", "etiqueta": "Abrir", "id": "wa:34600111222"}}]}

{"tipo": "formulario", "id": "walkin", "titulo": "Reserva física", "campos": [
 {"nombre": "nombre", "etiqueta": "Nombre", "tipo": "texto|select|fecha|numero", "opciones": ["DBL-STD", "SGL-STD"], "valor": "", "obligatorio": true}],
 "envio": {"tipo": "enviar_formulario", "etiqueta": "Añadir reserva", "formulario": "walkin"}}

{"tipo": "documento", "id": "doc-0003", "documento": "factura", "estado": "borrador|emitido|enviado", "numero": null, "titulo": "Factura de Ana Pereira",
 "receptor": "Atlántico Consultores SL", "total": "212,00 EUR", "fiscal": false, "aviso": "Documento de demostración sin validez fiscal",
 "lineas": [{"concepto": "Alojamiento DBL-STD, 2 noches", "importe": "212,00 EUR"}],
 "acciones": [{"tipo": "abrir_documento", "etiqueta": "Abrir", "id": "doc-0003"}, {"tipo": "emitir_documento", "etiqueta": "Emitir", "id": "doc-0003"},
              {"tipo": "enviar_documento", "etiqueta": "Enviar por correo", "id": "doc-0003", "destinatario": "facturas@atlantico.example"}]}

{"tipo": "aviso", "tono": "info", "titulo": "…", "texto": "…"}

{"tipo": "sugerencias", "items": ["¿Cómo está la ocupación?", "¿Qué partes están pendientes?"]}
```

**Acciones** (el pintado solo ejecuta estos tipos, en una lista cerrada):

| Tipo | Campos | Efecto en el front |
|---|---|---|
| `preguntar` | `texto` | Envía ese texto al chat como si lo hubiera escrito el usuario |
| `abrir_seccion` | `seccion`, `params` | Navega a una sección |
| `abrir_expediente` | `id`, `paso` (opcional) | Navega a `#/recepcion?id=…&paso=…` |
| `abrir_documento` | `id` | Navega a `#/documentos?id=…` |
| `abrir_conversacion` | `id` | Navega a `#/mensajes?conv=…` |
| `aprobar_propuesta` | `id` | `POST /api/propuestas/{id}/aprobar` con confirmación previa |
| `rechazar_propuesta` | `id` | `POST /api/propuestas/{id}/rechazar` |
| `enviar_formulario` | `formulario` y los valores | `walkin` envía `POST /api/walkin` y, si hay conflicto (409), ofrece forzar |
| `sincronizar` | `fuente` (`roomcloud` o `ofihotel`) | `POST /api/sync/{fuente}` |
| `emitir_documento` | `id` | `POST /api/documentos/{id}/emitir` con confirmación previa |
| `enviar_documento` | `id`, `destinatario` | `POST /api/documentos/{id}/enviar` con confirmación que muestra el destinatario |

Cada acción ejecutada devuelve al bloque `{ok, mensaje, estado, detalle}` para que el bloque se vea actualizado (por ejemplo, una propuesta aprobada pasa a "Aprobada por Flor").
El módulo `asistente-bloques.js` exporta `renderBloque(bloque, { ejecutar, ui, el })` y devuelve un `HTMLElement`. El `ejecutar(accion, valores)` lo implementa `asistente.js` y devuelve una promesa de `{ok, mensaje, estado, detalle}`.

## 6. Plantillas, validación y ejecución

`app/plantillas.py` define el catálogo cerrado. Cada variable se valida contra un formato antes de rellenar el texto, y `hub.contexto_valido(store, plantilla, slots)` comprueba además que lo referido existe.

| Plantilla | Destino | Variables |
|---|---|---|
| `confirmar_reserva` | whatsapp | `nombre`, `entrada`, `salida` |
| `pedir_documentos` | whatsapp | `nombre` |
| `info_llegada` | whatsapp | `nombre` |
| `correo_info_llegada` | correo | `nombre`, `destinatario` |
| `cerrar_disponibilidad` | roomcloud | `tipo`, `entrada`, `salida` |
| `emitir_factura` | documentos | `expediente` |
| `emitir_albaran` | documentos | `expediente` |
| `enviar_documento` | correo | `documento`, `destinatario` |
| `revision_humana` | interno | `motivo` |

**Regla anti fuga de datos:** `enviar_documento` solo es válida si `destinatario` es un correo conocido de la estancia del documento (correo de la reserva, del huésped, de la empresa o del receptor). Si alguien pide enviarlo a otra dirección, la propuesta no se crea y el caso va a `revision_humana`; recepción puede enviarlo a mano desde Documentos con la confirmación explícita del destinatario nuevo.

Intenciones del lector: `pregunta_checkin_horario`, `solicita_cambio_fechas`, `cancelacion`, `envia_documento`, `solicita_factura`, `solicita_albaran`, `pregunta_general`, `otro`. `solicita_factura` y `solicita_albaran` generan una propuesta `emitir_factura` o `emitir_albaran` si el mensaje se enlaza con una estancia, y si no, `revision_humana`.

Ejecución de una propuesta aprobada (`hub.EJECUTORES`, un registro de funciones `(store, propuesta, actor)`): `whatsapp`, `roomcloud` e `interno` ya existen. `correo` lo implementa `back-mensajes` en `adapters/correo.py` (`ejecutar` y `enviar_simulado`). `documentos` lo implementa `back-documentos` en `documentos.py` (`ejecutar`). Cada ejecución deja un evento en `db["eventos"]`.

## 7. Rutas del front (hash)

`#/<seccion>?clave=valor`. Parámetros reconocidos:

| Ruta | Parámetros |
|---|---|
| `#/asistente` | `q` (pregunta inicial) |
| `#/hoy` | ninguno |
| `#/recepcion` | `id` (expediente), `paso` (`documento`, `pago`, `parte`, `ofihotel`, `checkout`), `filtro` (`hoy`, `en_casa`, `salidas`, `todos`) |
| `#/ocupacion` | `nuevo=1`, `tipo`, `fecha` |
| `#/documentos` | `id`, `tipo` (`factura` o `albaran`), `nuevo` (id de expediente) |
| `#/bandeja` | `propuesta`, `evento`, `vista` (`pendientes`, `todo`) |
| `#/mensajes` | `conv`, `canal` (`todos`, `whatsapp`, `correo`) |
| `#/integraciones` | ninguno |
| `#/galeria` | ninguno |

## 8. Orden de datos de demostración

`POST /api/demo/semilla?nivel=completa` produce siempre el mismo estado con el reloj en `2026-10-24T09:00`. Todos los agentes capturan pantallas con ese estado para que se pueda comparar.
