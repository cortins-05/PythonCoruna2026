# Conexión RoomCloud ↔ OfiHotel: lo que se sabe

> Investigación del 24 de octubre de 2026 con un agente de búsqueda web. Sirve tanto para
> entender la conexión actual como para saber qué falta si se sustituye OfiHotel por una app
> propia (`03-solucion.md`, rama C).
>
> Leyenda: **[V]** verificado en una página leída · **[P]** parcial, fragmento de buscador o
> fuente secundaria · **[I]** inferido · **[NE]** no encontrado.
>
> Límites: la especificación XML de RoomCloud no se pudo abrir (error de conexión y PDF en
> binario), así que su contenido viene de fragmentos de buscador. Es de 2017. Las páginas de
> Ofimática son comerciales y se contradicen. No hay fuentes independientes sobre fallos,
> precios ni casos reales.

## Resumen

- **Confirmado:** OfiHotel lista a "Roomcloud (Parity Rate)" entre sus channel managers, y
  RoomCloud incluye a "Ofimatica" en su lista de PMS integrados. El manual de OfiHotel
  describe un flujo de reservas automáticas con el alta manual como plan B.
- **Sin confirmar:** qué datos viajan en cada sentido, si cancelaciones y modificaciones se
  sincronizan, la frecuencia, y si OfiChannel usa la API XML de RoomCloud.
- **Las dos páginas de Ofimática se contradicen** sobre si la conexión es bidireccional.
- **Para una app propia:** no hay programa público de partners PMS de RoomCloud, ni
  documentación vigente, ni proceso de certificación publicado, ni sandbox documentado.
  Hay que contactar con RoomCloud.

## 1. OfiChannel

| Punto | Estado |
|---|---|
| Channel manager de Ofimática, usable con OfiHotel o de forma independiente | [V] |
| La misma página dice "bidireccional con OfiHotel (escritorio y cloud)" y más abajo "OfiHotel (one way) u OfiHotelcloud (two way)" | [V] la contradicción |
| Las reservas se importan a OfiHotel "con un solo clic" | [V] texto de marketing |
| Disponibilidad: cupo por canal o inventario común | [V] |
| Cancelaciones, modificaciones y no-shows | [NE] |
| Push, polling o frecuencia | [NE] |
| Que "un solo clic" signifique importación manual | [I] |
| Que OfiChannel use la API XML de RoomCloud | [NE] |
| OfiHotelCloud recibe reservas de forma automática | [P] |

**Manual de OfiHotel (antiguo, probablemente de escritorio) [V]:** si una reserva de Parity
Rate no llega sola, se da de alta a mano. En "Número Reserva Externo" se escribe
`localizadorexterno-xx`, donde `xx` es el número de portal Parity. Sirve para localizar el alta
cuando después llega una anulación. Existe una opción "Captura de Reservas Externas" que
requiere un módulo y un parámetro activos. Es lo más cercano a un dato de cancelaciones.

## 2. API XML de RoomCloud (v2.3.4, 18-may-2017) [P]

Alojada en un mirror de terceros. Lo que se pudo ver:

- Cada llamada es un HTTPS POST con el login del extranet de RoomCloud.
- Operaciones: descargar reservas, leer inventario y enviar actualizaciones de inventario.
- En `reservations`, `hotelId` es obligatorio; `useDLM`, `startDate` y `endDate` son
  opcionales. Con `useDLM=true` y sin fechas devuelve lo creado o modificado desde la
  última llamada.
- El changelog menciona correcciones de `useDLM` en las versiones 2.2.0 y 2.2.1.
- El documento describe como clientes a un PMS o un CRS. Que OfiHotel sea ese cliente
  **no está confirmado en ninguna fuente**.
- No se encontró una versión posterior a la 2.3.4 [NE].

## 3. Cómo se contrata y se activa

| Punto | Estado |
|---|---|
| Precio de OfiChannel y de la conexión con Parity Rate | [NE] |
| Se contrata por "Pide info" o "Solicita demo", a través de varios channel managers incluido Parity Rate | [V] |
| Quién da de alta la conexión (Ofimática, RoomCloud, Parity Rate o distribuidor) | [NE] |
| Versiones de OfiHotel soportadas: hay distinción entre escritorio y OfiHotelCloud, sin lista de versiones | [P] |
| Requisitos concretos para OfiHotel (mapeo, API key, hotelId) | [NE]; el manual cita el número de portal Parity |
| Plazos | [NE] |

Como ejemplo de proceso con otro PMS (Clock PMS+) [V, solo títulos]: el proveedor del PMS
configura la conexión, el hotel hace formación con RoomCloud, se configuran los mapeos y
después se activan las OTAs.

## 4. Cómo integra RoomCloud con un PMS

| Punto | Estado |
|---|---|
| Su página dice que se comunica "al instante" con el PMS para actualizar disponibilidad y tarifas | [V] |
| Lista de más de 150 PMS que incluye "Ofimatica" (otra ficha habla de 250+: cifras de marketing) | [V] |
| Nombres de tipos de partner: "Technology Integration Partner" y "Certified Implementation Partner", sin requisitos | [P] |
| Proceso de certificación o alta de un PMS nuevo | [NE] |
| Entorno de pruebas | [NE] como política pública (la especificación sí cita `apitest`, ver `02-investigacion.md`) |
| Quién paga y requisitos | [NE] |
| Contacto: info@roomcloud.net y +39 0267101036 | [V] |
| Informe PCI DSS de Tecnes (AOC) con fecha 22-nov-2024 | [V] la fecha |

## 5. Alternativas a OfiChannel

| Alternativa | Estado |
|---|---|
| **ObeHotel:** conexión bidireccional con OfiHotel, alianza desde 2020 y anuncio de 2022. Ofrece entorno de pruebas sin compromiso. Sin detalle de datos ni versiones | [V] anuncio del proveedor |
| ObeHotel y RoomCloud a la vez | [NE]. RoomCloud lista a ObeHotel como canal al que envía inventario, no como middleware [P] |
| **Civitfun:** integración con OfiHotel solo para check-in online | [V]; no es channel manager |
| Middleware o conectores de terceros OfiHotel–RoomCloud | [NE] |
| Casos reales de hoteles | [NE] |

Pendiente de confirmar: si el "Obehotel" de la lista de channel managers de OfiHotel es el
mismo que el de RoomCloud o un canal distinto.

## 6. Problemas conocidos

| Problema | Estado |
|---|---|
| Reservas de Parity Rate que no llegan solas y se dan de alta a mano | [V] lo documenta el manual de OfiHotel |
| Anulaciones que llegan antes que el alta y se localizan por el localizador externo | [V] manual, parcial |
| Opiniones negativas de las conexiones XML ("full of bugs") | [P] una reseña anónima en GetApp |
| Overbooking | Solo afirmaciones de RoomCloud, sin datos independientes |
| Desajustes de mapeo, soporte y retrasos | [NE] |
| Foros de usuarios de OfiHotel con RoomCloud | [NE]. Sugerido buscar en Hosteltur y grupos de gestores hoteleros |

## 7. Datos de tarjeta (`ccData`)

- El bloque es opcional en la especificación de 2017 y contiene CVC, número, caducidad y
  titular [P].
- Hay un control de autorización de segundo nivel para la interfaz XML [P].
- Si OfiHotel usa `ccData` en esta integración: [NE]. Si se almacena el CVC: [NE]. Tokenización:
  [NE].
- Regla general de PCI DSS (conocimiento general, no de las fuentes): el CVC no puede
  almacenarse tras la autorización.

## 8. Para una app propia que sustituya a OfiHotel

| Punto | Estado |
|---|---|
| Pasos de alta de un PMS propio en RoomCloud | [NE] |
| Qué pide RoomCloud a un desarrollador | [NE] |
| Programa de partners PMS o acceso API para terceros | [NE] públicamente |
| ¿Basta la API con las credenciales del hotel? | [NE] como política. La especificación indica usuario y contraseña del extranet [P], lo que sugiere credenciales por hotel |

Usar las credenciales del extranet de un hotel desde una app propia tiene implicaciones de
seguridad y contractuales que hay que aclarar con RoomCloud.

---

## Preguntas para Ofimática

*(Menos urgentes si se sustituye OfiHotel, pero útiles para entender la migración.)*

1. ¿OfiChannel con OfiHotel de escritorio es unidireccional o bidireccional? ¿Y con
   OfiHotelCloud? ¿Qué datos viajan en cada sentido?
2. ¿Las reservas de Parity Rate llegan solas o hay que importarlas con un clic? ¿Cada cuánto
   se sincronizan?
3. ¿Se sincronizan cancelaciones, modificaciones y no-shows? ¿Y tarifas y restricciones?
4. ¿Qué versión de OfiHotel y de OfiChannel hace falta? ¿Requiere el módulo de "Captura de
   Reservas Externas"?
5. ¿Se usa la API XML de RoomCloud o un conector propio?
6. ¿Precio de OfiChannel y de la conexión? ¿Quién la activa y en cuánto tiempo?
7. ¿Hay entorno de pruebas?
8. ¿Se transmiten y almacenan los datos de tarjeta (`ccData`)?
9. ¿Qué mapeo hace falta (habitaciones, tarifas, número de portal Parity)?

## Preguntas para RoomCloud

*(Estas son las que más importan para la rama C.)*

1. ¿Existe documentación vigente de la API XML para PMS partners, más allá de la v2.3.4? ¿Hay
   una versión posterior?
2. ¿Qué operaciones hay (`reservations`, `view`, `modify`, cancelación, disponibilidad,
   tarifas)? ¿Qué significa `useDLM` y cómo se usa en la práctica?
3. ¿Cómo se da de alta un PMS nuevo? ¿Requisitos, coste, certificación y entorno de pruebas?
4. ¿Una app propia puede conectarse con las credenciales del hotel, o necesita un acuerdo de
   partner? ¿Qué pide RoomCloud a un desarrollador?
5. ¿Se puede desactivar el envío de `ccData` o tokenizarlo?
6. ¿Qué cubre el PCI DSS de Tecnes y aplica a la ruta de `ccData` de la API?
7. ¿ObeHotel está conectado a RoomCloud como canal de venta o como channel manager?

## Fuentes principales

- [Ofimática — channel manager](https://www.ofi.es/software/channel-manager-hotel/)
- [Grupo Miranda — OfiChannel](https://www.grupomiranda.net/ofichannel/)
- [Manual OfiHotel — Reservas](https://clientes.ofi.es/manuales/ofihotel/reservas.htm)
- [RoomCloud — integraciones PMS](https://www.roomcloud.net/what-is-channel-manager/integrations/pms/)
- [RoomCloud — resellers y partners](https://www.roomcloud.net/what-is-channel-manager/integrations/resellers-partners/)
- [RoomCloud XML API v2.3.4 (PDF, mirror)](http://www.reservahotel.com/80/indexStarMR/en/RoomCloudXMLAPI_V234.pdf)
- [Tecnes — PCI DSS AOC](https://www.roomcloud.net/wp-content/uploads/2025/06/TECNES-PCI-DSS-v4-0-1-ROC-AOC-Service-Providers-QSA_signed.pdf)
- [ObeHotel — conexión con OfiHotel](https://obehotel.com/nueva-conexion-entre-el-pms-ofihotel-de-ofimatica-y-obehotel-2/)
- [Civitfun — integración con OfiHotel](https://en.civitfun.com/pms-integrations/ofihotel/)
- [Clock PMS+ — configuración con RoomCloud](https://support.clock-software.com/en/support/solutions/articles/9000191280-roomcloud-setup)
