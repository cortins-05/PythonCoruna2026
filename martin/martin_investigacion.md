# Estado de la investigación (24 de octubre de 2026)

> Redactado a partir de la conversación de Martín con Claude para que cualquiera del equipo
> sepa en qué punto estamos. Lo observado va sin atenuar y lo deducido lleva su atenuador.
> Complementa a `01-problema.md`, `02-investigacion.md` y `03-solucion.md`. Las búsquedas de
> hoy fueron limitadas, así que "no lo he encontrado" no prueba que no exista.

## Resumen

- **Tiene sentido hacerlo.** La parte que nadie puede discutir es el control legal y de
  trámites: que ningún parte, alta o factura se quede sin hacer.
- **En la demo el envío a SES.Hospedajes es simulado.** El servicio web real exige
  credenciales técnicas propias que hoy nadie tiene, y la especificación solo se descarga
  dentro del portal oficial.
- **OfiHotel no tiene API ni MCP.** Tampoco lo tiene RoomCloud como MCP, aunque RoomCloud sí
  tiene API XML. Hoy no automatizamos la pantalla de OfiHotel.
- **La propuesta mínima es un expediente único por huésped** que captura los datos una vez,
  prepara el parte dentro de las 24 horas y no deja cerrar el check-out con trámites
  pendientes.
- **Todo entra aquí y todo sale de aquí.** Los datos viven en el sistema y se envían a cada
  programa por adaptadores. El único destino sin adaptador posible hoy es OfiHotel.

## Principio de diseño: todo entra aquí y todo sale de aquí

Los datos de cada estancia viven en este sistema y desde él salen hacia cada programa a través
de un adaptador por destino, de modo que nadie tiene que volver a meter a mano un dato que ya
está dentro. Cada destino es un adaptador independiente (SES.Hospedajes, RoomCloud, OfiHotel,
email), así que el hotel puede cambiar de proveedor sin cambiar su forma de trabajar.

| Destino | Adaptador de salida | Estado |
|---|---|---|
| SES.Hospedajes | Servicio web SOAP con XML del parte | Simulado en la demo, real cuando haya credenciales `_WS` |
| RoomCloud | API XML (`reservations` en lectura, `modify` en escritura) | Lectura en la demo, escritura fuera de alcance |
| OfiHotel | **Sin vía automática hoy** | Es el hueco que queda abierto (ver abajo) |
| Email al huésped | Envío desde el sistema | Fuera de la demo |

**El hueco de OfiHotel.** Como no tiene API, el único adaptador posible hoy es una pantalla de
copia asistida, que es justo lo que queremos evitar. Las salidas reales son tres, y ninguna
depende de nosotros: que Ofimática confirme un mecanismo de importación o servicio web para
partners, contratar sus módulos (OfiScan, OfiCheckin) para que el dato llegue desde ellos, o un
script de automatización de pantalla ejecutado en el PC del hotel. La demo debe decirlo en voz
alta.

**Qué manda sobre qué.** Los datos del huésped y de la estancia nacen aquí. La disponibilidad
sigue mandando OfiHotel (decisión de `03-solucion.md`), y como no podemos leerla sin API, el
sistema no la toca en esta fase.

## 1. Qué hemos comprobado hoy

### RoomCloud y OfiHotel frente a Claude y otros LLM

- Ninguno de los dos tiene MCP oficial ni conector para Claude. Sus webs oficiales no
  mencionan API pública, portal de developers ni funciones de IA.
- RoomCloud tiene una API XML bidireccional pensada para que PMS, CRS y RMS se conecten, con
  más de 200 PMS integrados según su web.
- OfiHotel es el PMS de Ofimática (`ofi.es` y `ofihotel.es`). El sitio `ofihotel.com` es
  otro y muestra un banner de "próximo lanzamiento".

### Qué existe ya en el mercado

- **PMS con MCP oficial:** Apaleo, con login de la propia cuenta y vista previa antes de cada
  escritura. roommaster lanzó un AI Connector para ChatGPT, Claude, Copilot y Gemini.
  Guesty tiene uno en beta y solo de lectura.
- **Conectores de terceros:** Truto y Peliqan generan servidores MCP sobre Cloudbeds y Mews,
  que no tienen uno oficial. Ambos son vendedores, así que sus guías son marketing.
- **Madurez:** un scorecard de 13 PMS encontró que solo 1 trae MCP oficial. Es de un blog de
  un tercero.
- **Check-in con OCR y envío a SES.Hospedajes:** Chekin, Civitfun, BookCheckin y similares ya
  lo hacen, desde unos 3 a 4 € por propiedad al mes. Las cifras salen de blogs de comparación
  escritos por competidores, así que son indicativas. Vender solo eso es competir con un
  producto barato y maduro.
- **Lo que no encontramos** es una capa que siga los trámites de cada estancia a través de
  un PMS cerrado, un channel manager y el email, con alarma de plazo legal.

### Datos y límites verificados

- **SES.Hospedajes:** el servicio web usa credenciales distintas de las del portal (usuario
  con sufijo `_WS`), y la documentación técnica (v3.1.2) se descarga dentro del portal
  oficial. El XSD no es público, así que el generador de la demo sigue la lista de campos del
  RD 933/2021 y **no se puede afirmar que valide contra el esquema oficial**.
- **Computer use:** Anthropic no publica un coste por tarea. Una estimación de un tercero da
  unos 4 $ por una sesión de 100 pasos con Opus, y extrapolando linealmente (cálculo
  nuestro, probablemente corto) un check-in de 30 pasos cuesta como mínimo cerca de 1 €. No
  compensa a escala frente a los 3 o 4 € mensuales de Chekin.
- **Automatizar OfiHotel:** si es la versión SQL, el programa es de escritorio y el robot
  tendría que correr en el PC del hotel. pywinauto sirve para scripts deterministas, pero su
  propia documentación avisa de que escalar es difícil por identificadores de interfaz
  inestables. No sabemos si el hotel tiene la versión SQL o la cloud.
- **Firma en tablet:** una firma táctil es firma electrónica simple. Tiene validez, pero en
  un litigio necesita evidencias adicionales (marca de tiempo y vínculo al documento). No
  pudimos comprobar si el registro de viajeros exige firma.
- **Galicia:** según una fuente secundaria sigue las reglas estatales, y el envío va a
  Policía Nacional o Guardia Civil. Si es así, Mossos y Ertzaintza quedan fuera. No
  verificamos requisitos de la Xunta ni del INE.

### Corrección sobre el cursor de reservas de RoomCloud

Un MCP o integración de lectura que llame a `reservations` con `useDLM="true"` mueve el
cursor compartido por cuenta (problema 12) y le robaría reservas a OfiChannel sin que nadie
se enterase. Cualquier lectura nuestra debe usar `useDLM="false"` con fechas, y descartar
`ccData` (la tarjeta en claro) al parsear (problema 7).

## 2. Decisiones tomadas por Martín

- Producto pensado para muchos hoteles, pero el foco es la propuesta funcional y no el
  escalado.
- Evento de 3 horas: hay que montar una demo hoy.
- Reparto de trabajo: Claude para OCR, lectura de emails y seguimiento, y código
  determinista para los pasos legales.
- Automatización de pantalla de OfiHotel fuera de la demo.
- Capa de confirmación humana antes de cualquier acción que comprometa legalmente al hotel.
- Caso de Galicia, con un hotel genérico y los sistemas mínimos para demostrar la función.
- El mantenimiento queda fuera de alcance, pero el sistema debe ser lo más plug and play
  posible.

## 3. Propuesta mínima de valor

Cada llegada y cada salida tiene un **expediente único** que captura los datos una vez,
prepara el parte de viajeros dentro de las 24 horas y no permite cerrar el check-out hasta
que los trámites están hechos o justificados.

Cubre directamente el problema 22 (doble tecleo del BIENVENIDO) y el 23 (listado diario en
papel que se desfasa), que se añadieron a `01-problema.md` en la rama `docs/problema-hotel` y ya están en main, además
del 5 (plazo legal del parte) y el 6 (parte incompleto).

## 4. La historia de una estancia

Huésped ficticia **Ana Pereira**, que reserva por Booking y llega con factura a nombre de su
empresa. La recepcionista es Flor.

1. **La reserva entra.** El sistema lee RoomCloud en solo lectura y crea un expediente
   "pendiente de llegada". Si llega por email, Claude extrae los datos y deja un borrador que
   Flor confirma con un clic.
2. **Ana entrega el DNI.** Flor lo fotografía con la tablet, Claude rellena los campos del
   parte y el código determinista comprueba lo comprobable (letra del DNI, coherencia de
   fechas). Flor revisa solo lo dudoso y la foto se descarta tras la extracción.
3. **Se completa lo que falta.** Medio de pago (obligatorio en el parte) y datos fiscales de
   la empresa, recogidos ya en el check-in. Una lista de campos obligatorios impide avanzar
   mientras falte alguno.
4. **Sale el parte.** El sistema genera el XML y enseña un resumen legible. Flor pulsa
   confirmar, y el envío a SES.Hospedajes **se simula en la demo** guardando hora y
   justificante.
5. **Alta en OfiHotel.** Es la salida que hoy no se puede automatizar. Como solución
   provisional, una pantalla "copiar a OfiHotel" con los datos en el orden de su formulario y
   una casilla "hecho", hasta que exista un adaptador real (ver principio de diseño).
6. **Durante la estancia.** Panel para la dueña con llegadas, partes enviados y pendientes,
   y avisos (por ejemplo a las 20 horas si hay un parte sin enviar).
7. **Check-out.** Una lista con lo que queda: factura, liberar habitación y parte enviado.
   Como OfiHotel no tiene API, el sistema no puede comprobar la factura ni la liberación, y
   depende de que Flor marque las casillas.
8. **Cierre.** Registro de cada paso con hora y persona, útil ante una inspección y para
   medir minutos por check-in.

## 5. Antes y ahora

| Tema | Antes | Ahora |
|---|---|---|
| Reservas de OTA | Flor las vuelca a mano de RoomCloud a OfiHotel | El sistema las lee y crea el expediente |
| Reservas por email | Alguien las apunta a mano | Claude extrae los datos y Flor confirma |
| Datos del huésped | BIENVENIDO en papel y tecleo en OfiHotel | Foto del documento, campos rellenos y revisión de lo dudoso |
| Datos de empresa | Se piden en el check-out | Se recogen en el check-in |
| Parte a la policía | Probablemente en el check-out, fuera de plazo y quizá sin medio de pago | Al hacer el check-in, completo y con confirmación |
| Check-out | Tres acciones separadas y olvidables | Una lista que no deja cerrar con pendientes |
| Control | Nadie ve qué falta | Panel y avisos automáticos |
| Papel | BIENVENIDO y listado diario impresos | Desaparecen del check-in |

Lo que sigue igual: alguien sigue tecleando en OfiHotel (ahora con datos validados), el
sistema no ve lo que pasa dentro de OfiHotel, y la firma en tablet y la emisión de facturas
quedan fuera.

## 6. Alcance

- **Dentro:** OCR de DNI o pasaporte con confirmación humana, medio de pago, datos de empresa
  en el check-in, XML del parte con cuenta atrás de 24 horas y envío simulado, lectura de
  reservas de RoomCloud, y check-out con lista de pendientes.
- **Fuera, como trabajo futuro:** firma en tablet, emisión de facturas (Verifactu llega en
  2027), escritura de disponibilidad en RoomCloud (riesgo de overbooking), INE, Xunta, tasas,
  llaves, contabilidad y automatización real de OfiHotel.

## 7. Plan de 3 horas

1. **Primera hora:** modelo de datos y máquina de estados del expediente, y OCR con Claude
   vision hacia los campos del parte.
2. **Segunda hora:** generador del XML con envío simulado, panel con cuenta atrás, y check-out
   con la lista de pendientes.
3. **Última hora:** adaptador de RoomCloud (con XML grabado si no hay credenciales), lectura
   de emails y guion de la demo.

La demo de tres minutos enseña el paso 2 (foto a campos), el 4 (XML con confirmación) y el 6
(panel con alarma), que se entienden solos y no dependen de ninguna API del hotel. Hay que
decir en voz alta que hoy no elimina el tecleo en OfiHotel.

## 8. Qué falta

- **Clave de la API de Anthropic** para que el OCR funcione en vivo. Mientras tanto la demo
  usa un JSON de muestra.
- **Credenciales de pruebas de RoomCloud** (`apitest.roomcloud.net`). Si no llegan, se usa
  XML grabado.
- **Respuestas del cuestionario**, sobre todo la 2 (módulos contratados de OfiHotel) y la 5
  (quién factura RoomCloud), que deciden la rama del proyecto.
- **Saber si OfiHotel ya envía partes a SES.Hospedajes.** Si lo hace, enviar desde nuestro
  sistema duplicaría los partes.
- **RGPD:** pasar fotos de documentos por un LLM exige contrato de tratamiento de datos y no
  guardar la imagen. En la demo solo se usan documentos de muestra.

## 9. Cruce con `docs/04-investigacion-agentes.md`

Lo leído en ese documento (24 de octubre, hecho con dos agentes de búsqueda) confirma buena
parte de lo anterior y corrige algunos puntos de este.

**Correcciones a este documento**
- **`seshospedajes.es` es una web privada con una API de pago, no la del Ministerio.** Este
  documento la cita como fuente de la versión 3.1.2 de la documentación técnica, y esa versión
  hay que confirmarla en el portal oficial.
- **OfiChannel no está confirmado como solución.** La página oficial se contradice sobre si es
  bidireccional, y si solo sube disponibilidad el volcado manual de Flor sigue existiendo. Es
  la pregunta decisiva para Ofimática, y pesa más que lo que dijimos de que "ya existe".
- **Civitfun** tiene 3,3/5 con 7 reseñas (costes no comunicados, implantaciones de hasta 6
  meses) y es solo cloud. Hay que tenerlo en cuenta como competidor y como alternativa.

**Lo que aporta y no teníamos**
- **Lectura de OfiHotel con `pyodbc` en solo lectura sobre su SQL Server** (enfoque D). Si el
  esquema se consigue y la licencia lo permite, resolvería la limitación principal de nuestra
  demo (que el sistema no ve lo que pasa dentro de OfiHotel) y haría falta para la
  disponibilidad. El documento lo marca como no encontrado y pendiente de confirmar.
- **Conservación de 3 años** del registro informático (RD 933/2021, art. 5.3, verificado en el
  BOE). Nuestra demo guarda el parte en un JSON local sin política de conservación, y un
  sistema real tiene que cumplirla.
- **Cola de envíos a SES con reintentos y registro.** Ofimática no documenta qué pasa cuando
  un envío falla, y la POC hoy envía una vez y no reintenta.
- **Conciliación entre OfiHotel y el canal**, con aviso de reservas no importadas. Es otro
  hueco sin cubrir, y la POC no lo hace.

**Cómo encaja la POC**
- Cubre el hueco 3 (check-out en un solo paso) y el listado del día, y deja sin tocar el
  servicio de disponibilidad y el conciliador, que son lo que el agente propone como primer
  paso sin llamar a nadie.
- Las dos líneas se pueden combinar sin chocar: el expediente es la capa de procesos, y el
  servicio de disponibilidad sería otro adaptador de salida hacia RoomCloud.

## 10. Fuentes

- [SES.HOSPEDAJES Credentials (RegistroViajero)](https://registroviajero.com/en/blog/ses-hospedajes-credentials/)
- [Recursos SES Hospedajes](https://seshospedajes.es/en/recursos/)
- [Apaleo MCP](https://apaleo.dev/mcp/)
- [Apaleo launches industry's first MCP server](https://shorttermrentalz.com/news/apaleo-launches-industrys-first-mcp-server/)
- [roommaster AI Connector](https://www.hospitalitynet.org/news/4134994/roommaster-introduces-ai-connector-bringing-live-hotel-pms-data-into-chatgpt-claude-microsoft-copilot-and-google-gemini)
- [Which Hotel PMS Platforms Have Open APIs? 2026 Scorecard](https://rapideyeinspections.com/blog/hotel-pms-open-api-comparison/)
- [Mews Claude MCP (Peliqan)](https://peliqan.io/blog/mews-claude-mcp/)
- [Connect Cloudbeds to Claude (Truto)](https://truto.one/blog/connect-cloudbeds-to-claude-automate-billing-and-folio-accounting/)
- [Best SES Hospedajes guest registration apps 2026](https://bookcheckin.com/en/blog/best-ses-guest-registration-apps-2026)
- [Civitfun](https://www.civitfun.com/)
- [Claude Computer Use Token Cost](https://claudecodeguides.com/claude-computer-use-token-cost-breakdown/)
- [Windows Apps GUI Test Automation Using PyWinAuto](https://dzone.com/articles/windows-apps-gui-test-automation-using-pywinauto)
- [Tipos de firmas electrónicas según eIDAS](https://focus.namirial.com/es/tipos-de-firmas-electronica-y-sus-diferencias/)
- [Registro de viajeros obligatorio (Mews)](https://www.mews.com/es/blog/es-obligatorio-el-registro-de-viajeros)
- [RoomCloud](https://www.roomcloud.net)
- [Integraciones Ofimática](https://www.ofi.es/software/integraciones/)
