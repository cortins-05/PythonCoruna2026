# Investigación

> Hecha el 7 de septiembre de 2026 a partir de fuentes públicas: webs de los fabricantes,
> distribuidores, la especificación de la API de RoomCloud y el BOE. Nada de esto está
> confirmado todavía por Ofimática ni por RoomCloud directamente.

## Resumen

| Pregunta de partida | Respuesta |
|---|---|
| ¿OfiHotel es una API? | **No.** No publica API abierta. Sí tiene integraciones certificadas con terceros. |
| ¿RoomCloud es una API? | **Sí.** API XML documentada, con entorno de pruebas. |
| ¿Se pueden sincronizar? | **La conexión ya existe como producto**: OfiChannel, contratable vía Parity Rate (RoomCloud). |
| ¿Firma en tablet? | **Existe como módulo**: OfiEFirma. |
| ¿Envío a la policía automático? | **Existe en OfiHotel**: conexión directa con SES.Hospedajes, Mossos y Ertzaintza. |

---

## OfiHotel

PMS de **Ofimática** (Barcelona). Más de 1.000 establecimientos en España, Portugal y
Latinoamérica, desde cadenas hasta casas rurales. Modular.

### Arquitectura

- **OfiHotel SQL**: instalado en local sobre **SQL Server** (versiones 2008 R2 y 2014 en sus
  manuales de instalación).
- **OfiHotelCloud**: variante en la nube.

### Integración con terceros

- **No hay API pública documentada** ni portal de desarrolladores.
- **Sí hay integraciones certificadas** con terceros, lo que demuestra que la vía existe y
  que la abre Ofimática:
  - **Civitfun**: check-in online, con escaneo de documento, datos que se vuelcan al PMS y
    firma del contrato.
  - **ObeHotel**: channel manager, conexión bidireccional.
  - **Dataria**: revenue management.
- Acceder directamente a su SQL Server es técnicamente posible pero **queda descartado**:
  rompe el soporte y arriesga la integridad de la facturación.

### Módulos complementarios

| Módulo | Qué hace | Reto que cubre |
|---|---|---|
| **OfiEFirma** | Solicitud y captura digital de firmas con tableta | Firma en tablet |
| **OfiScan** | Escaneo de DNI y pasaporte; genera el parte de hospedería para la policía | Datos de check-in, parte |
| **OfiCheckin** | Pre-check-in y lectura de documentos por webcam | Check-in antes de llegar |
| **OfiKiosko** | Check-in 24 h en kioscos desatendidos | — |
| **OfiChannel** | Conexión con channel managers | Sincronización con RoomCloud |
| **OfiRedsys** | Pasarela de pago Redsys | Cobro |
| **OfiReservas** | Motor de reservas propio enlazado con el PMS | — |
| **OfiLlaves** | Llaves magnéticas | — |
| **OfiConta** | Traspaso a contabilidad | — |
| **OfiCRM** | Clientes, agencias y empresas | Fichas de empresa |

### Registro de huéspedes y policía

Según Ofimática, OfiHotel:

- Hace el check-in digital escaneando DNI o pasaporte, genera el parte y captura la firma.
- **Envía los datos a SES.Hospedajes en tiempo real**, y también a Mossos d'Esquadra y
  Ertzaintza si aplica.
- Guarda trazabilidad de los envíos, sin duplicados, para inspecciones.
- Requiere el **certificado digital** configurado en los parámetros de la aplicación y el
  alta previa del establecimiento en SES.Hospedajes.
- Permite plantillas de registro propias con logo y cláusulas RGPD.

---

## RoomCloud

Channel manager y motor de reservas de **Tecnes Milano Srl**. Más de 400 canales y más de
200 PMS integrados. Unos 7.000 establecimientos.

### Relación con Parity Rate

- Tecnes Milano lanzó **Parity Rate** en 2008, uno de los primeros channel managers de Italia.
- En 2015 Parity Rate se separó como empresa revendedora, con fuerte presencia en Italia y
  **España**. Tecnes siguió desarrollando el producto bajo la marca **RoomCloud**.
- En **2023 Tecnes Milano compró Parity Rate** y unificó las dos marcas.

Consecuencia práctica: si la factura del hotel la emite Parity Rate, es la misma plataforma.

### API XML (especificación v2.3.4)

Documento oficial: *RoomCloud XML API, versión 2.3.4*, de 2017.
<http://www.reservahotel.com/80/indexStarMR/en/RoomCloudXMLAPI_V234.pdf>
El certificado del servidor está caducado; se descarga con `curl -k`.

**Objetivo declarado de la API:** que un PMS use RoomCloud desde dentro de su software para
(1) descargar reservas, (2) leer el inventario y (3) actualizar el inventario, que a su vez
se propaga a los canales.

#### Transporte y autenticación

| | |
|---|---|
| Producción | `https://api.roomcloud.net/be/search/xml.jsp` |
| Pruebas | `https://apitest.roomcloud.net/be/search/xml.jsp` |
| Método | `POST` HTTPS, cabecera `Content-Type: text/xml` |
| Credenciales | Usuario y contraseña de la extranet |
| Segundo factor | **API key** (recomendada) o IP en lista blanca |

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Request apikey="MiApiKey" userName="MiUsuario" password="MiPassword">
  ...
</Request>
```

#### Cola y cuotas (por establecimiento)

- Cola de espera: hasta **8** peticiones simultáneas.
- Cola activa: hasta **3** peticiones de distinto tipo a la vez.
- Las actualizaciones se procesan **de una en una**; ninguna empieza hasta que acaba la anterior.
- Máximo **15.000 filas de disponibilidad cada 180 minutos** (ampliable bajo petición).

#### Métodos

| Método | Para qué |
|---|---|
| `getHotels` | Establecimientos de la cuenta |
| `getRates` | Planes tarifarios |
| `getRooms` | Tipos de habitación |
| `getPortals` | Canales conectados (Booking, Expedia…) |
| `changePassword` | Actualizar la contraseña de un canal |
| `reservations` | **Descargar reservas** |
| `view` | Leer inventario: disponibilidad, precios, estancia mínima, cierres |
| `modify` | **Escribir inventario** y propagarlo a los canales |
| `getBusinessRules` | Reglas que derivan una habitación/tarifa de otra |

#### `reservations`: la llamada que sustituye el volcado manual

Tres modos según atributos:

| Atributos | Devuelve |
|---|---|
| `useDLM="true"`, sin fechas | Todo lo creado o modificado **desde la última llamada** |
| `useDLM="true"`, `startDate` + `endDate` | Lo creado o modificado entre dos fechas |
| `useDLM="false"`, `startDate` + `endDate` | Reservas con **llegada** entre dos fechas |

```xml
<Request apikey="..." userName="..." password="...">
  <reservations hotelId="3284" useDLM="true"/>
</Request>
```

Cada `reservation` trae:

- Cabecera: `id` (código del canal), `portalId` (0 = motor propio), `dlm` (última
  modificación), `checkin`, `checkout`, `creation_date`, `status`.
- Cliente: `firstName`, `lastName`, `address`, `city`, `zipcode`, `country`, `telephone`, `email`.
- Importes: `price`, `prepaid`, `currencycode`, `paymentType` (1 transferencia, 2 giro postal,
  3 PayPal, 4 tarjeta), `offer`, `notes`.
- `ccData`: **número, CVC, caducidad y titular de la tarjeta, en claro**.
- `room` (una por habitación): tipo, fechas, tarifa, adultos, niños, extras, precio,
  **comisión del canal**, estado.
- `dayPrice`: precio por día y habitación.
- `supplement`: servicios extra.
- `guest`: huéspedes por habitación (nombre, contacto, dirección).

Estados:

| Código | Estado |
|---|---|
| 2 | Enviada |
| 3 | Cancelada (ya no se usa) |
| 4 | Confirmada |
| 5 | Rechazada |
| 6 | No show |
| 7 | Borrada / cancelada |
| 8 | Modificada |

RoomCloud intenta traducir la habitación de cada reserva a uno de sus tipos (*room
mapping*). Si lo consigue, el `roomId` devuelto es el de RoomCloud (el de `getRooms`).

#### Inventario: `view` y `modify`

El inventario es un calendario por tipo de habitación y día con: tarifas y precios, número
de habitaciones disponibles, estancia mínima, cierre a la llegada y cierre a la salida.
Cada habitación/tarifa de RoomCloud se mapea a una o varias de cada canal; al modificar el
calendario se actualizan los canales mapeados.

#### Observaciones sobre la API

- **El cursor de `useDLM` es único por cuenta.** Dos clientes llamando a la vez se reparten
  las reservas y cada uno ve solo una parte. Solo puede integrar un sistema.
- **Los datos de tarjeta llegan en claro.** Quien consuma la API está manejando el número de
  tarjeta completo.
- **La especificación es de 2017.** Hay que pedir a RoomCloud la vigente.
- **Existe entorno de pruebas**, lo que permite desarrollar sin tocar el inventario real.

---

## OfiChannel: la conexión que ya existe

Solución de Ofimática para gestionar la oferta online desde OfiHotel.

- Se contrata a través de un channel manager. Lista publicada por un distribuidor de
  Ofimática: **PARITY RATE (Roomcloud)**, SiteMinder, Neobooking, Yield Planet, TravelClick,
  Hotetec, Dingus, Reservit y ObeHotel.
- **Importación de reservas al PMS "con un clic"** e integración "100 %" con OfiHotel.
- La web de Ofimática habla de **conexión bidireccional** con OfiHotel, o unidireccional
  como alternativa.
- Disponibilidad y precio comunes a todos los canales o distintos por canal; control desde
  el PMS o desde el channel manager.

**Conclusión:** la sincronización OfiHotel ↔ RoomCloud que se quería construir aparece en el
catálogo de Ofimática. Queda por confirmar con ellos que está disponible para la versión
del hotel, si es realmente bidireccional, y su coste.

---

## Marco legal

### SES.Hospedajes — Real Decreto 933/2021

- Sustituye al antiguo parte de viajeros. **Obligatorio desde el 2 de diciembre de 2024**.
- Base de datos nacional del Ministerio del Interior (`hospedajes.ses.mir.es`), accesible
  para Policía Nacional, Guardia Civil y otros cuerpos.
- **Plazo: inmediato y nunca más de 24 horas** desde la reserva, su anulación o el inicio
  del servicio. No hay excepción por caídas del sistema.
- **14 campos por cada huésped adulto**, más datos de contacto y **del medio de pago**
  (antes eran 8).
- Envío por el portal web (con certificado digital) o por **servicio web SOAP** con
  credenciales técnicas propias. Se habilita marcando "Envío de comunicaciones por servicio
  web" en el portal. XML contra un esquema XSD del Ministerio; documentación técnica v3.1.2.
- Sanciones:
  - **Leves** (datos incorrectos, incompletos o fuera de plazo): **100–600 € por parte**.
  - **Graves** (no registrarse o no comunicar): **601–30.000 €**.

### Verifactu — Real Decreto 1007/2023

- Software de facturación homologado: encadenamiento criptográfico, código QR y trazabilidad.
- Aplazado por segunda vez por el **Real Decreto-ley 15/2025**:
  - **1 de enero de 2027** para sociedades (Impuesto sobre Sociedades).
  - **1 de julio de 2027** para autónomos y demás obligados.
- Los **fabricantes de software** están obligados desde el **29 de julio de 2025**: ya se le
  puede exigir a Ofimática.
- Sanciones que pueden superar los 50.000 € si el software permite ocultar ingresos.

---

## Conclusiones

1. **Tres de los cuatro retos son producto de catálogo de Ofimática**: firma en tablet
   (OfiEFirma), envío a la policía (registro de huéspedes) y sincronización con RoomCloud
   (OfiChannel). La pregunta deja de ser "¿cómo lo construimos?" y pasa a ser "¿por qué no
   está activado?".
2. **RoomCloud sí es una API**, bien documentada y con entorno de pruebas. Si hubiera que
   construir, la mitad RoomCloud es la fácil.
3. **OfiHotel es la mitad difícil**: sin API pública, la entrada pasa por Ofimática.
4. **SES.Hospedajes ya es obligatorio**, y su plazo de 24 horas es incompatible con enviar el
   parte en el check-out.

---

## Fuentes

- [OfiHotel — módulos complementarios](https://www.ofihotel.es/modulos)
- [Ofimática — registro de huéspedes](https://www.ofi.es/software/hoteles/registro-de-huespedes/)
- [Ofimática — integraciones](https://www.ofi.es/software/integraciones/)
- [Ofimática — channel manager](https://www.ofi.es/software/channel-manager-hotel/)
- [Grupo Miranda — OfiChannel](https://www.grupomiranda.net/ofichannel/)
- [Manual de OfiHotel — cambio de servidor SQL](https://clientes.ofi.es/manuales/ofihotel/cambioservidorsql.htm)
- [Civitfun — integración con OfiHotel](https://www.civitfun.com/integraciones-pms/ofihotel/)
- [ObeHotel — conexión con OfiHotel](https://obehotel.com/nueva-conexion-entre-el-pms-ofihotel-de-ofimatica-y-obehotel/)
- [RoomCloud](https://www.roomcloud.net/)
- [RoomCloud — integraciones PMS](https://www.roomcloud.net/what-is-channel-manager/integrations/pms/)
- [RoomCloud XML API v2.3.4 (PDF)](http://www.reservahotel.com/80/indexStarMR/en/RoomCloudXMLAPI_V234.pdf)
- [RoomCloud compra Parity Rate](https://www.roomcloud.net/es/roomcloud-compra-parity-rate/)
- [BOE — Real Decreto 933/2021](https://www.boe.es/diario_boe/txt.php?id=BOE-A-2021-17461)
- [SES.Hospedajes — recursos técnicos](https://seshospedajes.es/en/recursos/)
- [Chekin — SES.Hospedajes 2026](https://chekin.com/blog/todo-lo-que-necesitas-saber-sobre-ses-hospedajes/)
- [Verifactu — plazos](https://www.verifactu.com/plazos-verifactu/)
