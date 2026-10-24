# Fuente única de la verdad (rama D)

> Propuesta del equipo del 24 de octubre de 2026. **No es una investigación con fuentes**: es un
> diseño razonado a partir de `01` a `06` y de la POC de `martin/poc/`. Lo que depende de datos
> que no tenemos está marcado como decisión abierta.

## La idea

Todo lo que llega al hotel confluye en **un único sitio, en vivo**: OfiHotel, RoomCloud,
WhatsApp y correo. Ese sitio sustituye al papel con las reservas que se rellenaba a mano
(problema 23) y muestra con **colores** qué hay que hacer: migrar algo a OfiHotel, resolver un
conflicto, enviar un parte.

**Diferencia con la rama C** (`03-solucion.md`): aquí **OfiHotel se conserva**. La app es una
capa por encima. Desaparecen el riesgo de sustituir el PMS y la responsabilidad de
facturación y Verifactu. A cambio, OfiHotel sigue sin API.

```
 RoomCloud ─┐
 Correo ────┤
 WhatsApp ──┼──►  FUENTE ÚNICA (en vivo, con estados)  ──►  recepción
 Puerta ────┤              │
 OfiHotel ──┘              └──►  RoomCloud (disponibilidad), SES (parte)
```

## Relación con la POC de `martin/poc`

La POC ya implementa un expediente único de estancia con: lectura de reservas de RoomCloud,
listado del día, validaciones, cuenta atrás de 24 h del parte, registro de quién hizo qué y
bloqueo del cierre con trámites pendientes.

**Lo que falta para esta propuesta:** correo y WhatsApp, estado por sistema con colores,
detección de conflictos, canal en vivo, usuarios y permisos, y un almacén real en lugar del
JSON local. Conviene construir sobre la POC, no en paralelo.

## Modelo: un estado por sistema

Cada reserva lleva un estado **por cada sistema**, no uno solo.

| Campo | Valores |
|---|---|
| Origen | RoomCloud (Booking, Expedia, web), OfiHotel, WhatsApp, correo, puerta |
| En RoomCloud | no aplica · sincronizado · pendiente |
| En OfiHotel | no está · **por migrar** · migrado |
| Documentación | sin datos · completa · parte enviado |

## Colores

El de mayor gravedad manda en la tarjeta.

| Color | Significado | Quién actúa |
|---|---|---|
| **Rojo** | Conflicto: orígenes que no coinciden o riesgo de overbooking | Recepción, ya |
| **Naranja** | Parte a SES sin enviar con el plazo de 24 h corriendo | Recepción |
| **Amarillo** | Por migrar a OfiHotel | Recepción |
| **Azul** | Entrada nueva sin confirmar (WhatsApp o correo) | Recepción |
| **Gris** | Cancelación o modificación pendiente de reflejar | Recepción |
| **Verde** | Todo cuadrado | Nadie |

### Conflictos que se detectan

- Misma habitación con dos reservas solapadas.
- Modificación en RoomCloud sobre una reserva ya migrada, con datos distintos.
- Reserva presente en un origen y ausente en otro pasadas X horas.
- Cancelación en RoomCloud con la habitación todavía asignada.

---

## Decisiones abiertas

1. **Identidad de la reserva.** RoomCloud trae `portalId` + `id`. Un correo o un WhatsApp no
   traen identificador. Hay que casar por nombre, fechas y tipo de habitación, con
   confirmación humana cuando haya duda.
2. **WhatsApp.** Un número normal no se puede automatizar. Hace falta **WhatsApp Business
   Platform** (API de Meta), con plantillas aprobadas y consentimiento, y es un trámite que
   lleva tiempo. *No se ha investigado ni verificado en esta ronda.* Propuesta: empezar solo
   con el correo.
3. **Correo.** Leer el buzón (IMAP o API de Gmail) y extraer nombre, fechas y habitación con
   un modelo. **Siempre entra como azul, nunca como confirmado**: un error de extracción no
   debe crear una reserva.
4. **Cómo sabe la app que algo está migrado a OfiHotel.** Es la decisión más importante y
   depende del hotel. Opciones: lo marca recepción; se infiere de un listado exportado de
   OfiHotel; o lectura ODBC en solo lectura (esquema desconocido, ver `04`).
5. **Quién manda sobre la disponibilidad.** Una única fuente de verdad (`03`, fase 1). Aquí
   sería la app, que la sube a RoomCloud. Hay que confirmar que RoomCloud la acepta como
   cliente de la API (`06`).
6. **Tiempo real.** SSE o WebSocket sobre FastAPI, como la POC. Para un hotel pequeño basta,
   sin colas.
7. **RGPD y accesos.** Un panel con datos de huéspedes y mensajes personales exige usuarios,
   permisos, trazabilidad y plazos de conservación. La POC no los tiene.

## Límites que se mantienen

- **OfiHotel no tiene API**, así que alguien sigue pasando datos a OfiHotel. La app lo
  ordena, valida y recuerda; no lo elimina.
- **Factura y liberación de habitación** dependen de que recepción las marque, porque la app
  no ve dentro de OfiHotel.
- Se mantienen las reglas de diseño de `03`: descartar `ccData`, idempotencia por
  `portalId` + `id` + `dlm`, un solo consumidor de `useDLM`, desarrollo contra
  `apitest.roomcloud.net`, avisos a una persona si algo falla, logs sin datos personales y
  proceso manual siempre posible.

## Por dónde empezar

1. **Panel en vivo con estados y colores** sobre la POC, con los orígenes que ya existen
   (RoomCloud y alta manual).
2. **Detección de conflictos** entre ellos.
3. **Correo** con un buzón de prueba y mensajes ficticios.
4. **WhatsApp** solo después de investigar la API de Meta.

## Criterios de éxito

| Indicador | Objetivo |
|---|---|
| Reservas con origen en papel o en un mensaje sin registrar | 0 |
| Entradas por WhatsApp o correo sin reflejar en el panel | 0 |
| Conflictos detectados antes de la llegada del cliente | 100 % |
| Datos de una reserva tecleados más de una vez | Los de OfiHotel solo |
| Una persona nueva interpreta el panel con una sola explicación | Sí |
