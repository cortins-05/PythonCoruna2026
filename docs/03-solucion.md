# Solución posible

> Propuesta condicionada: depende de las respuestas del cuestionario de
> `01-problema.md`. Donde la decisión depende de un dato que aún no tenemos, se plantean
> las dos ramas.

## Principio rector

**Cuanto menos código propio quede en producción, mejor sale este proyecto.**

Tres razones, todas de `01-problema.md`:

- Un intermediario propio con RoomCloud recibe **datos de tarjeta en claro** (problema 7).
- **Solo un sistema puede leer las reservas** de RoomCloud sin perder ninguna (problema 12).
- Lo que se construye **hay que mantenerlo durante años** (problema 20).

El trabajo propio rinde donde el fabricante no llega: el **rediseño del proceso**, el
formulario, el orden de los pasos, y que el sistema no permita olvidarse de nada.

---

## Fase 0 — Antes de construir nada (sin coste)

### 0.1 Rellenar el cuestionario

<https://claude.ai/code/artifact/1bc71cfb-6e7f-4424-8b71-0fd90e7a295a>

Las preguntas 2 (módulos contratados) y 5 (quién factura RoomCloud) deciden el proyecto.
La respuesta a la 2 debe salir **de la factura**, no de memoria.

### 0.2 Corregir el envío a la policía

Si los partes se envían en el check-out, **pasar el envío al check-in ya**, aunque sea a
mano. No depende de ninguna otra decisión y es el riesgo más caro.

Comprobar además que el BIENVENIDO recoge el **medio de pago**, obligatorio en el parte.

### 0.3 Medir la línea base

Antes de cambiar nada, durante dos semanas:

- Minutos diarios que dedica Flor al volcado y a la disponibilidad.
- Check-ins por día.
- Errores de transcripción detectados y overbookings (y los del último año, si constan).
- Tiempo medio de un check-in y de un check-out en recepción.

Sin estos números no se puede justificar el gasto ni saber si el cambio ha funcionado.

### 0.4 Meter a Flor en el proyecto

Es quien conoce el proceso real. Entrevistarla sobre los casos raros (cancelaciones,
modificaciones, grupos, no shows) y dejar claro que el objetivo es quitarle trabajo
repetitivo, no el puesto. Su tiempo liberado se recoloca en atención al cliente.

### 0.5 Llamar a Ofimática

Pedir presupuesto y confirmación por escrito de:

1. **OfiChannel vía RoomCloud / Parity Rate** para la versión del hotel. ¿Es bidireccional?
   ¿Las reservas bajan solas o "con un clic"? ¿La disponibilidad sube sola?
2. **OfiEFirma** con tablet.
3. **Registro de huéspedes con envío automático a SES.Hospedajes.**
4. **OfiScan / OfiCheckin** para leer el DNI o pasaporte.
5. Fecha en la que OfiHotel estará **homologado para Verifactu**.
6. Si existe **algún mecanismo de integración** (importación de ficheros, servicio web,
   interfaz para partners) por si hay que construir algo propio.

---

## Fase 1 — Activar lo que ya existe

Si Ofimática confirma que los módulos están disponibles:

| Problema | Solución | Quién mantiene |
|---|---|---|
| Volcado manual RoomCloud → OfiHotel | OfiChannel vía RoomCloud | Ofimática + RoomCloud |
| Disponibilidad a mano OfiHotel → RoomCloud | OfiChannel (bidireccional) | Ofimática + RoomCloud |
| Firma en tablet | OfiEFirma | Ofimática |
| Teclear el BIENVENIDO | OfiScan / OfiCheckin | Ofimática |
| Parte a la policía | Registro de huéspedes → SES.Hospedajes | Ofimática |

### Puesta en marcha

1. **Mapeo de habitaciones y tarifas** entre RoomCloud y OfiHotel, revisado tipo por tipo
   con Flor antes de activar nada. Es lo que más falla en estas conexiones.
2. **Fuente de verdad única para la disponibilidad: OfiHotel.** RoomCloud la recibe y la
   reparte a los canales; nadie la toca a mano en RoomCloud.
3. **Convivencia de una a dos semanas**: la conexión automática activa y Flor revisando cada
   mañana que lo volcado coincide con RoomCloud. Se retira la revisión cuando haya varios
   días seguidos sin diferencias.
4. Desactivar cualquier otra cosa que lea reservas de RoomCloud: **solo un sistema** puede
   usar el cursor de reservas.

### Cómo quedan los flujos

**Check-in** (los dos flujos):

1. Si la reserva viene de una OTA, ya está en OfiHotel.
2. Escanear DNI o pasaporte; los datos se rellenan solos.
3. Si viaja por trabajo, **seleccionar o dar de alta la empresa** en este momento.
4. Recoger el medio de pago.
5. Firma en la tablet.
6. **El parte sale a SES.Hospedajes en este momento**, dentro de plazo.

**Check-out:**

1. Factura, con los datos de empresa ya rellenos desde el check-in.
2. Liberar la habitación. *Probablemente lo hace el propio check-out de OfiHotel; verificar.*

El parte a la policía **desaparece del check-out**: ya se envió al entrar. De tres acciones
manuales quedan una o dos, y la disponibilidad vuelve a RoomCloud sola.

---

## Fase 2 — Construir solo los huecos

Lo que quede sin cubrir después de la fase 1. Las ramas más probables:

### Rama A: OfiChannel cubre la sincronización

Lo que queda por construir es pequeño y no toca datos sensibles:

- **Panel de control** para la dueña: ocupación, reservas del día, check-outs pendientes,
  partes enviados y no enviados.
- **Avisos**: reserva que no bajó al PMS, parte sin enviar a las 20 horas, habitación sin
  liberar tras el check-out.
- **Guía de recepción** paso a paso para personal nuevo o temporal.

### Rama B: OfiChannel no es viable

(Versión antigua, coste inasumible, o integración que ya falló antes.)

Primero, valorar **cambiar de vía antes que construir**: actualizar OfiHotel, o un channel
manager distinto que sí tenga conexión con OfiHotel (ObeHotel la anuncia bidireccional).

Si aun así hay que construir, un **sincronizador en Python**:

```
             ┌────────────────────────────┐
 RoomCloud   │  sincronizador (Python)    │   OfiHotel
 ──────────► │                            │ ──────────►
 reservations│ 1. lee reservas (delta)    │ vía oficial de
 useDLM      │ 2. descarta datos tarjeta  │ Ofimática
             │ 3. traduce habitación      │
 ◄────────── │ 4. escribe en el PMS       │ ◄──────────
 modify      │ 5. sube disponibilidad     │ ocupación
             └────────────────────────────┘
                          │
                  avisos a recepción
                   si algo falla
```

Reglas de diseño:

- **Escritura en OfiHotel solo por la vía que dé Ofimática** (importación, servicio web o
  interfaz de partners). Nunca escribir directamente en su SQL Server.
- **OfiHotel es la fuente de verdad** de la disponibilidad.
- **`ccData` se descarta al parsear**: nunca se guarda, nunca se escribe en un log.
- **Idempotente**: cada reserva se identifica por `portalId` + `id` + `dlm`. Procesar la
  misma dos veces no duplica nada.
- **Respeta las cuotas**: lecturas de reservas espaciadas; disponibilidad agrupada en
  pocas llamadas `modify`, solo con los días que cambian.
- **Se desarrolla contra `apitest.roomcloud.net`**, nunca contra producción.
- **Modo simulación**: en las primeras semanas calcula lo que haría y lo enseña, sin
  escribir. Flor lo compara con lo que hace a mano.
- **Si falla, avisa a una persona**, y el proceso manual sigue siendo posible. El hotel nunca
  depende de que el programa funcione.
- **Logs sin datos personales**.
- **Documentado** para que otra persona pueda mantenerlo.

### Check-in propio (solo si no hay OfiEFirma ni OfiCheckin)

Un BIENVENIDO digital en tablet: formulario con los 14 campos del parte, medio de pago,
datos de empresa opcionales y firma. Antes de construirlo, comparar con soluciones de
check-in online ya integradas con OfiHotel, como **Civitfun**. La firma con validez legal
(vinculada al documento y sellada en el tiempo) es lo más difícil de hacer bien.

---

## Rama C: sustituir OfiHotel por una app propia

> Decisión del equipo del 24 de octubre de 2026. Detalle y fuentes en `05-funciones-a-clonar.md`.
> Cambia el planteamiento de las fases 0 a 2: ya no se busca activar módulos de Ofimática
> ni construir un puente, sino reemplazar el PMS.

**Qué cambia:**

- Desaparecen el problema 1 (OfiHotel sin API), la dependencia de Ofimática y el riesgo de
  duplicar OfiChannel.
- Aparecen la facturación y Verifactu, el RGPD de los documentos guardados, la migración de
  datos y el cambio de PMS en un hotel que no puede parar (problema 17).

**El principio rector sigue, con otro sentido:** construir el núcleo y **delegar lo regulado**.

| Se construye | Se delega |
|---|---|
| Reservas y disponibilidad | Facturación: proveedor Verifactu certificado con API |
| Sincronización con RoomCloud | Pagos con tarjeta: Redsys o similar, sin tocar datos de tarjeta |
| Check-in digital con firma táctil | |
| Parte a SES.Hospedajes con alerta de 24 h | |
| Check-out en una acción | |
| Vista diaria de llegadas, salidas y ocupación | |

**Reglas de la rama B que se mantienen:** descartar `ccData` al parsear, idempotencia por
`portalId` + `id` + `dlm`, un solo consumidor del cursor `useDLM`, desarrollo contra
`apitest.roomcloud.net`, modo simulación al principio, avisos a una persona si algo falla,
logs sin datos personales, documentación para que otra persona pueda mantenerlo, y proceso
manual siempre posible.

**Migración sin parar el hotel:** funcionar en paralelo con OfiHotel durante un periodo
(la app propia en modo lectura o simulación) y cortar solo cuando los resultados coincidan
varios días seguidos. Con vuelta atrás. *Cómo se extraen los datos históricos de OfiHotel
sin tocar su SQL Server está sin resolver.*

**Por verificar antes de construir, por orden:**

1. El calendario de Verifactu en el BOE.
2. Si el hotel comunica a SES.Hospedajes o a los Mossos d'Esquadra.
3. Cómo da de alta RoomCloud un PMS propio y qué permisos concede.
4. Un proveedor de facturación Verifactu con API y declaración responsable por escrito.
5. Una revisión específica del RGPD.

---

## Criterios de éxito

Comparados con la línea base de la fase 0:

| Indicador | Objetivo |
|---|---|
| Minutos diarios de volcado manual | 0 |
| Overbookings | 0 |
| Partes enviados en menos de 24 h | 100 % |
| Partes con datos completos | 100 % |
| Acciones manuales en el check-out | 1 |
| Facturas de empresa rehechas | 0 |
| Recepción trabaja sin papel | Sí |
| Una persona nueva hace un check-in con una sola explicación | Sí |

---

## Riesgos que quedan abiertos

- **Dependencia de Ofimática**: el calendario lo marcan ellos.
- **Coste de los módulos**: hay que compararlo con las horas de Flor que libera.
- **Adopción**: formar a todo el personal, no solo a quien está en el arranque.
- **Verifactu**: la facturación no se toca hasta que OfiHotel esté homologado.

## Orden de trabajo

1. Cuestionario completo.
2. Envío a la policía pasado al check-in.
3. Dos semanas de línea base.
4. Llamada y presupuesto de Ofimática.
5. Decisión: fase 1, rama A o rama B.
