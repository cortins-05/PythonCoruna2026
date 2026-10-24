# Comparativa de enfoques y recomendación

> Síntesis del 24 de octubre de 2026 a partir de `01` a `08`. No es una investigación nueva:
> es una comparación razonada para que el equipo decida. Las apreciaciones propias están
> marcadas **[I]** (inferido); lo demás remite al documento donde está la fuente.

## Dato nuevo: el hotel está en Galicia

Cambia varios puntos abiertos de `08-pms-propio.md`:

| Punto | Antes | Con Galicia |
|---|---|---|
| Destino del parte de viajeros | Dudoso entre SES, Mossos y Ertzaintza | **[I] SES.Hospedajes.** Mossos y Ertzaintza solo aplican en Cataluña y País Vasco, y no se encontró ningún canal autonómico gallego |
| Régimen propio de Galicia | [NE] | Sigue sin verificarse. Hay que confirmarlo, pero el escenario por defecto es el estatal |
| Tasa turística | Contradictoria | [P] En Galicia solo se aplica donde el concello aprueba el recargo. Hay que comprobar si el del hotel lo ha hecho |
| Hojas de reclamaciones | Dependía de la comunidad | [P] Decreto 148/2013 de Galicia |

**Consecuencia:** desaparece la necesidad de adaptadores por territorio. Un solo destino para
el parte simplifica el diseño. Queda la parte que depende de un tercero: la especificación
técnica de SES, que no se ha podido leer.

---

## Los tres enfoques

| | **A. Activar lo que ya existe** | **D. Capa central sobre OfiHotel** | **C. PMS propio** |
|---|---|---|---|
| Documento | `03`, fase 1 y rama A | `07` | `03` rama C y `08` |
| Idea | Contratar OfiChannel, OfiEFirma, OfiScan y el registro de huéspedes | Un panel en vivo con estados donde confluyen RoomCloud, correo, WhatsApp y OfiHotel | Sustituir OfiHotel por una app propia |
| Quién mantiene | Ofimática y RoomCloud | El equipo | El equipo |

### Comparación

| Criterio | A | D | C |
|---|---|---|---|
| **¿Se puede empezar hoy sin llamar a nadie?** | **No** (depende de Ofimática) | **Sí**, con RoomCloud y alta manual | Solo el núcleo; lo regulado necesita terceros |
| **Volcado manual RoomCloud ↔ OfiHotel** | Lo elimina, **si** OfiChannel baja reservas (sin confirmar, `06`) | No lo elimina; lo ordena y avisa | Lo elimina, si RoomCloud da acceso a su API |
| **Doble tecleo del BIENVENIDO** (problema 22) | Lo elimina con OfiScan u OfiCheckin | Lo reduce (datos validados) | Lo elimina |
| **Listado en papel** (problema 23) | No lo trata | **Lo sustituye** | Lo sustituye |
| **Parte a SES en 24 h** (problema 5) | Cubierto por el módulo, sin documentar cómo falla | Cola con alertas, sin enviar al principio | Se construye; falta la especificación |
| **Check-out en una acción** | Parcial | No: depende de lo que marque recepción | Sí |
| **Verifactu y facturación** | Ofimática, sin homologación pública | Sigue en OfiHotel | **Entra en el proyecto**: hotel como productor |
| **Riesgo de cambiar el PMS en un hotel que no puede parar** | Bajo | Bajo | **Alto** (migración y paralelo) |
| **Coste y plazo** | Presupuesto de Ofimática [NE] | Semanas, sobre la POC de `martin/` | **De 6 a 10 meses** y de 60.000 a 120.000 € [P, `08`] |
| **Dependencia de terceros** | **Alta** (Ofimática) | Baja | Media (RoomCloud, SES, proveedor de Verifactu) |
| **Dependencia de una persona técnica** (problema 20) | Baja | Media | **Alta** |
| **Aprovecha lo ya hecho** | — | **La POC de `martin/`** | Parcialmente |

### Qué no resuelve cada uno

- **A:** no ordena nada que llegue por correo o WhatsApp, ni sustituye al papel diario. Y su
  viabilidad es lo que no se sabe: la página de OfiChannel se contradice sobre si es
  bidireccional.
- **D:** OfiHotel sigue sin API, así que alguien sigue pasando datos a mano. Factura y
  liberación de habitación dependen de que recepción las marque (`07`).
- **C:** exige hacerse cargo de la facturación, de Verifactu, del RGPD de los documentos y de
  una migración sin parar el hotel. Es lo que más pesa y lo que más tarda.

---

## Recomendación

**[I] Empezar por D y diseñarlo para que pueda crecer hacia C.** Con dos tareas en paralelo
que no cuestan nada.

### Por qué D primero

1. **Es lo único que no depende de otra empresa.** A espera a Ofimática y C espera a
   RoomCloud, SES y a un proveedor de Verifactu.
2. **Ataca dos problemas que ninguno de los otros trata tan directamente:** el listado en
   papel desfasado y las reservas que entran por correo o WhatsApp sin registrarse.
3. **Aprovecha una POC existente** (`martin/poc/`) con RoomCloud, expediente único, cuenta
   atrás de 24 h y bloqueo del cierre.
4. **No cierra ninguna puerta.** El registro de reserva con estado por sistema (`07`) es
   justo el modelo de datos que necesitaría un PMS propio. Si luego se decide C, no se tira
   nada. Si Ofimática responde bien, A se puede activar por debajo.
5. **Lo que decide C no se sabe todavía.** Con el hotel que no puede parar y sin acceso
   confirmado a la API de RoomCloud, empezar por C es apostar antes de tener datos.

### Dos tareas en paralelo

1. **Fase 0 de `03`:** pasar el parte a SES al check-in (aunque sea a mano), comprobar que el
   BIENVENIDO recoge el medio de pago y medir la línea base durante dos semanas.
   Es el riesgo legal más caro y no depende de ningún enfoque.
2. **Preparar las preguntas** a RoomCloud y a Ofimática (`06`), para cuando se pueda llamar.

### Qué haría cambiar a C

Si ocurre alguna de estas cosas, merece volver a valorar el PMS propio:

- Ofimática no ofrece OfiChannel bidireccional o el coste de los módulos supera el valor de
  las horas que liberan.
- OfiHotel no tiene homologación de Verifactu por escrito antes de la fecha límite.
- RoomCloud confirma acceso a su API para un PMS propio con condiciones razonables.
- Hay una persona o un proveedor que pueda mantener el sistema durante años.

### Lo que habría que comprobar antes de decidir C

Se mantienen las preguntas de `08`, ya sin las de territorio:

1. Acceso de RoomCloud a su API para un PMS propio.
2. Especificación técnica de SES y entorno de pruebas.
3. Lectura de Verifactu y de la factura simplificada del alojamiento por la gestoría.
4. Si Galicia tiene algún requisito propio de registro además de SES.
5. Si el concello del hotel aplica tasa turística.

---

## Orden de trabajo resultante

| Paso | Qué | Depende de |
|---|---|---|
| 1 | Fase 0 de `03`: parte al check-in, BIENVENIDO con medio de pago y línea base | Nada |
| 2 | Panel en vivo con estados y colores sobre la POC, con RoomCloud y alta manual | Nada |
| 3 | Detección de conflictos entre orígenes | Paso 2 |
| 4 | Correo con un buzón de prueba, entrando siempre como "sin confirmar" | Paso 2 |
| 5 | Cola de partes a SES en modo simulación, con los campos del anexo I | Nada |
| 6 | Llamadas a RoomCloud y Ofimática, y revisión de esta comparativa con las respuestas | Poder llamar |
| 7 | WhatsApp, solo después de investigar la API de Meta | Paso 4 |
| 8 | Decidir entre seguir con D, activar A o abordar C | Paso 6 |
