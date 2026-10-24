# PMS propio: qué cubrir, qué construir y qué delegar

> Investigación del 24 de octubre de 2026 con tres agentes de búsqueda web. Parte de una
> premisa: **RoomCloud es un channel manager y motor de reservas, no un PMS.** Si se prescinde
> de OfiHotel, recepción, facturación local, registro legal de viajeros, housekeeping, cargos a
> habitación y contabilidad pasan a ser trabajo propio (rama C de `03-solucion.md`).
>
> Leyenda: **[V]** verificado en fuente primaria · **[P]** parcial, fuente secundaria o
> contradictoria · **[I]** inferido · **[NE]** no encontrado.
>
> Límites: casi todo lo de PMS sale de blogs y páginas de proveedores. Los textos del BOE se
> leyeron mediante extractores que truncan, y varias cifras de sanciones vienen de la FAQ de la
> AEAT y no del artículo de la ley. Antes de citar algo en un documento formal, confirmar el
> texto literal en el BOE.

## Resumen

| Área | Qué hay que hacer | Construir o delegar |
|---|---|---|
| Recepción | Rack, asignación, check-in y check-out, grupos, notas | **Construir** |
| Registro de viajeros | Parte a SES.Hospedajes en 24 h (o a Mossos y Ertzaintza) | **Construir**, pero sin la especificación técnica |
| Housekeeping | Estados, lista de limpiezas, bloqueos, incidencias | **Construir** (es sencillo) |
| Cargos a habitación | Folio, cargos, pagos, anulaciones por contrapartida | **Construir** |
| Facturación | Series, factura completa y simplificada, rectificativas | **Construir** la lógica; **delegar Verifactu** |
| Cobros con tarjeta | Redirección o tokenización | **Delegar** |
| Contabilidad | Exportación CSV y cierre de caja | **Exportar**; no construir contabilidad |
| Channel manager | Sincronización con RoomCloud | **Integrar**, pendiente de acceso a su API |

**Cinco hallazgos que condicionan el proyecto:**

1. **Un PMS propio con facturación convierte al hotel en productor** a efectos de Verifactu.
2. **No hay PMS completo y mantenido en Django o FastAPI** que sirva de base. Solo referencias
   de modelo, con licencias que impiden reutilizar código.
3. **No se debe guardar copia del DNI ni del pasaporte.** La AEPD lo dijo en junio de 2025.
4. **No se pudo leer la especificación técnica de SES.Hospedajes.** El envío no se puede
   diseñar con certeza todavía.
5. **Cataluña y País Vasco tienen canal autonómico propio** y no está resuelto si además hay que
   usar SES.

---

## 1. Registro legal de viajeros

### SES.Hospedajes (RD 933/2021)

| Punto | Estado |
|---|---|
| Comunicación telemática obligatoria. Excepción solo para hospedaje no profesional | [V] BOE, art. 6 |
| Plazo: "de manera inmediata y, en todo caso, en un plazo no superior a 24 horas", desde la reserva, formalización o anulación, y desde el inicio de los servicios | [V] BOE, art. 6.3 |
| Registro informático conservado **3 años** desde que acaba el servicio | [V] BOE, art. 5.3 |
| Comunicación previa de los datos del establecimiento antes de empezar la actividad | [P] art. 6.1 y 6.2 |
| Cualquier modificación exige nueva comunicación | [V] art. 6.1 |
| Obligatoriedad real: **2-dic-2024**. El 1-oct-2024 fue el fin de una moratoria, no la entrada en vigor | [P] |
| La disposición final tercera del BOE habla del 2-ene-2023, y no se ha podido saber qué norma lo pospuso | [P] conflicto sin resolver |

**Datos por viajero (anexo I) [V]:** nombre, dos apellidos, sexo, número de documento y de
soporte, tipo de documento, nacionalidad, fecha de nacimiento, residencia habitual (dirección,
localidad, país), teléfonos, correo, número de viajeros y relación de parentesco si hay menores.

**Datos de contrato y pago (anexo I, A.4) [V]:** número de referencia, fecha, hora de entrada
y salida, tipo de pago, identificación del medio de pago, titular, caducidad de la tarjeta y
fecha de pago. **El BIENVENIDO debe recoger el medio de pago** (problema 6 de `01-problema.md`).

**Sanciones [V]** (LO 4/2015, arts. 36.20, 37.9 y 39): leves de 100 a 600 € (datos
incompletos, incorrectos o fuera de plazo), graves de 601 a 30.000 € (no registrar o no
comunicar) y muy graves de 30.001 a 600.000 €.

### Documentación técnica: lo que falta

| Punto | Estado |
|---|---|
| "Interfaz de servicios externos v3.1.2" (PDF de 76 páginas) | Existe, **no se pudo leer** |
| Formato: XML comprimido y en Base64; modos síncrono y asíncrono; consulta de lotes | [P] fragmentos de buscador |
| Respuesta correcta: código 0 y número de lote | [P] |
| Códigos de error (10103, 10107, 10121…) | [P] fuentes de terceros |
| WSDL, XSD y tabla oficial de errores | [NE] |
| Entorno de pruebas | [NE] sin URL |
| Alta del establecimiento con Cl@ve y credenciales de servicio web | [P] |

`seshospedajes.es` es una web privada, no la del Ministerio. La página oficial dio error de
certificado al abrirla.

### Cataluña y País Vasco

| | Cataluña | País Vasco |
|---|---|---|
| Destinatario | Mossos d'Esquadra | Ertzaintza |
| Base | Orden IRP/418/2010 | Orden de 25-nov-2022 |
| Canal | Solo internet (`registreviatgers.mossos.gencat.cat`) | Aplicación electrónica, con certificado |
| Plazo | 24 h desde el inicio de cada estancia | No indicado en la página oficial |
| Conservación | 3 años | No indicada |
| Estado | [V] | [V] |

**Si además hay que comunicar a SES en estas comunidades: [NE].** Las páginas oficiales no lo
mencionan y los proveedores comerciales se contradicen. Galicia y Baleares: [NE].

### Otras obligaciones

- **INE, encuesta de ocupación hotelera [V]:** mensual, siete días aleatorios al mes, por envío
  telemático, XML o ARCE. Umbral mínimo de plazas: [NE]. [I] Si el hotel está inscrito y sale
  en la muestra, debe responder.
- **Tasa turística [P]:** régimen distinto por comunidad y municipio, con cifras contradictorias
  entre fuentes. Diseño: tarifas configurables por municipio y temporada.
- **Hojas de reclamaciones [P]:** el RD 2199/1976 es la referencia estatal y el formato lo fija
  cada comunidad. Diseño: guardar una referencia, no la hoja.

### Documento de identidad, firma y menores

- **Copia del DNI o pasaporte [V]:** la AEPD informó el 17-jun-2025 de que el RD 933/2021 no
  autoriza pedirla. Basta la verificación visual presencial. Diseño [I]: si se lee con OCR o
  NFC, extraer solo los campos del anexo y **descartar la imagen**.
- **Firma en tablet [P]:** el art. 25 de eIDAS impide negarle efecto por no ser cualificada. Una
  firma dibujada suele ser simple y su valor se decide caso por caso. Diseño [I]: guardar fecha,
  IP, dispositivo y el hash del texto aceptado.
- **Menores [P]:** el RD pide el parentesco. La edad de 16 años que citan guías comerciales no
  está verificada. Regla sobre quién puede ser viajero principal: [NE].

### RGPD [I, sin verificar el texto del reglamento]

Base legal: obligación legal (art. 6.1.c). La supresión no cabe durante los tres años de
conservación (art. 17.3.b) y sí después. El proveedor del PMS es encargado del tratamiento y
necesita contrato (art. 28). La comunicación al Ministerio es responsabilidad propia del hotel.
Hacen falta registro de actividades, cifrado, control de acceso por rol y registro de accesos.

---

## 2. Recepción

[I] A partir de la práctica del sector y comparativas de PMS (Little Hotelier, Cloudbeds,
Mews, Hotelogix, Sentaury, Clock PMS; funciones no contrastadas en documentación de los
fabricantes).

| Función | Descripción |
|---|---|
| Rack de habitaciones | Vista por planta y estado |
| Asignación y reasignación | Habitación libre del tipo reservado; mover con motivo |
| Check-in | Verificación de identidad, datos del anexo, firma, pago, llave |
| Check-out | Cierre de folio, factura, liquidación y habitación a sucia |
| Cambio de habitación | Mantener el histórico de estancia y cargos |
| No-show | Tras la hora límite, aplicando la política de cancelación |
| Early check-in y late check-out | Cargo o aprobación, ajustando la ocupación |
| Grupos | Reserva maestra con reservas hijas |
| Notas | De reserva, huésped y habitación, con visibilidad por rol |
| Llegadas y salidas del día | Con filtros (sustituye el listado en papel, problema 23) |
| Alerta de overbooking | Al asignar más reservas que habitaciones |

---

## 3. Housekeeping

| Punto | Estado |
|---|---|
| Estado de limpieza (limpia, sucia, inspeccionada) **separado** de la ocupación (ocupada, vacía). Cualquier combinación es válida | [V] Oracle OPERA |
| Fuera de servicio y mantenimiento son bloqueos de inventario, no estados de limpieza | [V] Oracle OPERA |
| El check-out deja la habitación sucia y crea la tarea de limpieza | [V] varias fuentes |
| Lista de limpiezas de salida y de estancia, con prioridad a las salidas | [P] |
| La camarera ve solo sus habitaciones; la gobernanta aprueba o devuelve | [P] |
| Una incidencia durante la limpieza puede pasar la habitación a mantenimiento | [P] |
| Si housekeeping dice limpia y el PMS dice sucia, se retiene la habitación hasta revisarla | [P] |
| Frecuencias y tiempos de limpieza | [NE] |

**Mínimo viable [I]:** habitaciones con estado de limpieza y ocupación; cola de limpiezas;
bloqueo con motivo y fechas que cierre la venta en el canal; incidencias con foto; objetos
perdidos; vista móvil de "mis habitaciones" con botón de hecho. Se puede dejar para después
la inspección formal, el no molestar y los cronómetros.

---

## 4. Cargos a habitación

| Concepto | Detalle |
|---|---|
| Folio | Cuenta de una estancia. Variantes: individual, dividido entre pagadores, de grupo y de empresa que paga después [V] en varios glosarios |
| Línea de cargo | Importe, cantidad, departamento, fecha de negocio, usuario y origen [P] |
| Cargos de restaurante o bar | Se envían al folio en lugar de cobrarse [P] |
| División de cuenta | Habitación a la empresa y consumos personales al huésped [P] |
| Permisos | Quien contabiliza no puede reabrir un folio cerrado [P] |
| Traspasos entre folios | Procedimiento completo [NE] |

**Reglas de diseño [I]:**

- **Los cargos son inmutables.** Una anulación genera una contrapartida con motivo, usuario y
  referencia al original.
- **Un pago siempre va contra un folio concreto**, con identificador único.
- **El cierre de folio se bloquea** si el saldo no es cero o no hay autorización.
- **Auditoría nocturna idempotente:** ejecutarla dos veces no duplica cargos, registra cada
  ejecución y no avanza la fecha de negocio con cargos pendientes.
- **Conciliación diaria** con el TPV, si lo hay.

---

## 5. Facturación y Verifactu

### Calendario

| Elemento | Estado |
|---|---|
| RD 1007/2023, Orden HAC/1177/2024 y RDL 15/2025 (BOE 3-dic-2025) | [V] |
| Fechas vigentes: **1-ene-2027** sociedades y **1-jul-2027** resto | [V] BOE |
| Aplazamiento a octubre de 2028 anunciado por Hacienda el 5-oct-2026 | [P] solo prensa; no está en el BOE y la FAQ de la AEAT del 21-oct-2026 no lo recoge |

**Recomendación del agente:** planificar con el 1-jul-2027 como límite hasta que el BOE diga
otra cosa.

### Qué exige el software [V]

- **Registro de alta y de anulación** por factura, con huella SHA-256 encadenada a la anterior.
- **Registro de eventos**, con resumen al menos cada 6 horas.
- **XML en UTF-8**, de 1 a 1.000 registros por envío, con espera inicial de 60 segundos entre
  envíos.
- **QR** de 30 a 40 mm, ISO/IEC 18004, corrección M.
- **Modo VERI\*FACTU** (envío continuo a la AEAT, firma no obligatoria) frente a **modo
  general** (firma electrónica obligatoria; el envío no es obligatorio). El cambio de modo es
  irreversible durante el año natural del primer envío.
- **Declaración responsable del productor**, por versión, visible en el sistema.
- **La AEAT publica** esquemas, WSDL, validaciones y un portal de pruebas
  (`preportal.aeat.es`) en su página de información técnica [V].

### Responsabilidad y sanciones

Las cifras vienen de la FAQ de la AEAT [P], sin haber leído el art. 201 bis de la LGT:

- Productor de un sistema no conforme: 150.000 € por ejercicio y tipo de sistema.
- Comercialización sin certificar: 1.000 € por sistema.
- Tenencia o uso de un sistema no conforme o alterado: 50.000 € por ejercicio.

**¿Obliga a un software hecho por el propio hotel?** La AEAT no responde expresamente [NE].
Varias fuentes secundarias coinciden en que sí: quien desarrolla su propio software de
facturación, aunque no lo venda, es productor y debe emitir la declaración [P]. **[I] Asumir
que sí y cumplir todo.**

### Construir o delegar

| Opción | Valoración |
|---|---|
| **Delegar el módulo Verifactu** (hash, QR, XML, envío, declaración) en un servicio con API y declaración vigente | Riesgo bajo; el proveedor firma la declaración |
| Construir el generador propio | Riesgo alto: hay que asumir la declaración, probar contra la AEAT y mantenerlo en cada versión |

Servicios con API y sandbox gratuito que aparecen en las fuentes [P, precios de las webs de
los proveedores o de comparativas]: Verifacti (2,90 € por NIF al mes), verifactu.co (de 49 a
399 € al mes), BeeL. (desde 15,90 € al mes), veribai y verifactuapi.es. **No hay lista oficial
de software homologado**: la certificación es una declaración del productor.

Librerías Python abiertas [P, solo README]: `huella` (Apache-2.0), `verifactu-python` (MIT) y
`pyverifactu`. Ninguna está certificada. **Una librería no equivale a una declaración
responsable.**

### Facturación hotelera

| Tema | Estado |
|---|---|
| Factura simplificada hasta **400 €** IVA incluido | [V] RD 1619/2012, art. 4.1 |
| Límite de 3.000 € para "hostelería y restauración" | [V] Pero el listado **no incluye el alojamiento**. [I] La estancia solo iría simplificada hasta 400 €. **Confirmar con la gestoría** |
| Contenido de factura completa y simplificada | [V] arts. 6 y 7 |
| IVA del alojamiento: 10 % | [P] |
| RDL 26/2026 que podría cambiar el IVA de servicios hoteleros | [P] fuentes contradictorias, sin verificar |
| Tasa turística: cómo se factura | [NE]. [I] Línea aparte no sujeta a IVA; confirmar con la gestoría |
| Suplidos, descuentos y anticipos | [NE] |
| Facturación electrónica B2B: RD 238/2026 y Orden HAC/1028/2026 | [V] existen. Calendario del 6-oct-2027 (más de 8 M€) y 6-oct-2028 (resto): [P] |

---

## 6. Cobros y contabilidad

**Cobros [V el modelo, I la consecuencia]:**

| Integración de Redsys | Dónde se capturan los datos | Carga PCI |
|---|---|---|
| Redirección | Página de Redsys | Baja |
| InSite (iframe) | Iframe de Redsys | Media |
| REST | El servidor propio | Alta |

**El PMS nunca debe guardar el número de tarjeta**: usar redirección o un token de la
pasarela. Sobre las tarjetas virtuales de Booking no hay documentación oficial [NE]; una fuente
secundaria avisa de que meter el número en un sistema inseguro lo pone en alcance PCI.

**Contabilidad.** El PMS exporta; no hace contabilidad.

- **Construir:** exportación CSV en el formato que pida la gestoría, informes y cierre de turno
  (buena práctica, sin obligación legal concreta encontrada [I]).
- **No construir:** importadores de A3, Sage o Contasol (cambian y los define la gestoría; la
  especificación de A3 y Contasol no es pública [NE]), libros registro de IVA, modelos fiscales
  ni arqueos legales.

---

## 7. Proyectos de referencia y arquitectura

### Código abierto

**No se encontró ningún PMS completo y mantenido en Django o FastAPI [NE].** Lo que hay:

| Proyecto | Licencia | Para qué sirve |
|---|---|---|
| Kamra PMS (Frappe, Python y React) | AGPL-3.0 | La más completa: folios, auditoría nocturna, POS, housekeeping, objetos perdidos. Referencia de modelo |
| OCA/vertical-hotel (Odoo) | AGPL-3.0 | Folio y housekeeping |
| OCA/pms (Odoo) | AGPL-3.0 | Propiedades, reservas y contabilidad |
| QloApps (PHP) | OSL-3.0 | Referencia de funciones |
| Módulo de housekeeping de Odoo | **OPL-1, propietaria** | **No reutilizable** |

**Aviso de licencia [I]:** el código AGPL obliga a publicar las modificaciones si se ofrece el
sistema como servicio por red. Sirve de inspiración de modelo, no de base de código.

### Alternativas comerciales ligeras

Little Hotelier, Clock PMS, Cloudbeds, Smoobu y Hostaway: precios contradictorios entre
fuentes o no públicos [P]. Little Hotelier, Smoobu y Hostaway están más orientados al alquiler
vacacional que al hotel con recepción y housekeeping. Pedir presupuesto en euros antes de
decidir.

### Arquitectura recomendada [I, a partir de artículos de diseño]

- **Disponibilidad:** PostgreSQL con **restricción de exclusión** sobre habitación y rango de
  fechas (`EXCLUDE USING gist (room_id WITH =, stay WITH &&)`, con la extensión `btree_gist` y
  límites `[)` para que el check-out y el check-in del mismo día no se solapen). Es el patrón
  verificado en la documentación de Django; el SQL exacto está reconstruido.
- **Overbooking:** la causa principal es el retraso de sincronización con los canales y el mapeo
  incorrecto, no el cálculo. Una única fuente de verdad, bloqueo de fila al confirmar y reserva
  en dos fases (pendiente con caducidad y confirmada).
- **Auditoría y eventos:** log de cada cambio de reserva, folio y estado; eventos internos que
  alimentan RoomCloud, SES y la auditoría nocturna.
- **Framework:** Django, por su administración, autenticación y migraciones para el panel de
  recepción. FastAPI encaja mejor para un servicio de integración.
- **Copias:** copia de base más archivado de WAL (PITR), con **restauración probada al menos una
  vez al mes**. Alta disponibilidad en caliente: [NE] para un hotel pequeño; empezar con copias
  y un servidor de reserva en frío.
- **Pruebas:** concurrencia de dos reservas sobre la última habitación, idempotencia de la
  auditoría y sincronización contra un entorno de pruebas de RoomCloud.

---

## 8. Riesgos de construir un PMS propio

| Riesgo | Estado |
|---|---|
| Cumplimiento legal cambiante (Verifactu, SES) | [V] existen los cambios |
| Sincronización con canales y overbooking | [P] |
| Copias sin restauración probada | [P] |
| Dependencia de una sola persona técnica (problema 20) | [I] |
| Seguridad de datos de huéspedes (RGPD, documentos, pago) | [P] |
| Resistencia del personal y mal ajuste con el hotel (problema 18) | [P] |
| No hay un caso documentado de un hotel pequeño que lo construyera y lo abandonara, ni opiniones independientes de hoteleros | [NE] |

**Esfuerzo [P, dos empresas que venden desarrollos a medida, con interés comercial]:** de 6 a
10 meses y de 60.000 a 120.000 € para un PMS completo, y de 3 a 4 meses para una primera
versión con reservas, facturación y pagos. De 3 a 6 semanas para migrar los datos.

**Lectura [I]:** construir lo que es propio del hotel (recepción, SES, cargos, housekeeping) y
**comprar o delegar lo que es commodity o regulado** (channel manager, Verifactu, pasarela de
pago). Mantener un procedimiento manual o un PMS de respaldo hasta tener el sistema probado en
paralelo.

---

## 9. Orden de trabajo propuesto

| Fase | Contenido | Antes de empezar |
|---|---|---|
| 0. Validación | Pedir a RoomCloud acceso a su API para un PMS propio. Pedir a la gestoría la lectura de Verifactu y la regla de la factura simplificada del alojamiento. Leer el RD 933/2021 en el BOE y conseguir la documentación técnica de SES. Confirmar con la Generalitat o el Gobierno Vasco si SES se aplica | Sin esto no hay arquitectura válida |
| 1. Núcleo | Habitaciones, reservas, disponibilidad con restricción de exclusión, bloqueos, copias y pruebas de concurrencia | Base de datos y estructura de tests |
| 2. Recepción y viajeros | Check-in y check-out, cola de partes con adaptadores por territorio. Manual primero y servicio web después | Especificación de SES |
| 3. Housekeeping | Estados, cola de limpiezas, incidencias y vista móvil | |
| 4. Folio y cargos | Cargos, pagos, traspasos y cierre | |
| 5. Facturación | Series y facturas con un proveedor de Verifactu | Confirmación fiscal |
| 6. RoomCloud | Sincronización de disponibilidad y reservas | Acceso a la API |

## 10. Lo que no se pudo confirmar

1. Especificación técnica de SES (WSDL, XSD, operaciones, errores, sandbox).
2. Si SES se aplica también en Cataluña y País Vasco, y el régimen de Galicia y Baleares.
   *El hotel está en Galicia: ver `09-comparativa-enfoques.md`. Se asume SES, pendiente de
   confirmar que Galicia no tiene un canal propio.*
3. Qué norma fijó el 2-dic-2024 frente al 2-ene-2023 del BOE.
4. Aplazamiento de Verifactu a 2028 en el BOE, y el texto del art. 201 bis de la LGT.
5. Si un software propio de uso interno es "productor" a efectos de la AEAT.
6. Si el alojamiento hotelero entra en el límite de 3.000 € de la factura simplificada.
7. Cómo se factura la tasa turística, y el RDL 26/2026.
8. Acceso de RoomCloud a su API para un PMS propio (`06-conexion-roomcloud-ofihotel.md`).
9. Formatos de importación de A3 y Contasol.
10. Fechas del último commit de Kamra, OCA/pms y OCA/vertical-hotel.
11. Umbral de plazas del encuesta del INE, edad de referencia de menores y regla del viajero
    principal.

## Fuentes principales

- [BOE — RD 933/2021](https://www.boe.es/eli/es/rd/2021/10/26/933)
- [BOE — LO 4/2015](https://www.boe.es/eli/es/lo/2015/03/30/4)
- [BOE — RD 1007/2023](https://www.boe.es/buscar/act.php?id=BOE-A-2023-24840)
- [BOE — Orden HAC/1177/2024](https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-22138)
- [BOE — RDL 15/2025](https://www.boe.es/diario_boe/txt.php?id=BOE-A-2025-24446)
- [BOE — RD 1619/2012](https://www.boe.es/buscar/act.php?id=BOE-A-2012-14696)
- [BOE — RD 238/2026 (factura electrónica B2B)](https://www.boe.es/buscar/act.php?id=BOE-A-2026-7295)
- [AEAT — información técnica de Verifactu](https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/informacion-tecnica.html)
- [AEAT — preguntas frecuentes de Verifactu](https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/preguntas-frecuentes.html)
- [AEPD — copia del DNI en hospedajes (17-jun-2025)](https://www.aepd.es/prensa-y-comunicacion/notas-de-prensa/aepd-informa-de-que-no-esta-permitido-solicitar-copia-dni-o-pasaporte-en-hospedajes)
- [Mossos — registro de viajeros](https://canalempresa.gencat.cat/es/integraciodepartamentaltramit/tramit/PerTemes/Registre-de-viatgers-destabliments-dhostalatge)
- [Euskadi — comunicación de personas alojadas](https://www.euskadi.eus/comunicacion/registro-hostelero/web01-tramite/es/)
- [INE — encuesta de ocupación hotelera](https://www.ine.es/daco/daco42/ocuphotel/notaeoh.htm)
- [SES.Hospedajes — documentación v3.1.2 (privada, PDF no legible)](https://seshospedajes.es/wp-content/uploads/2024/12/MIR-HOSPE-DSI-WS-Servicio-de-Hospedajes-Comunicaciones-v3.1.2.pdf)
- [Oracle OPERA — estados de housekeeping](https://docs.oracle.com/en/industries/hospitality/integration-platform/hsooo/t_workflow_updating_housekeeping_room_status.htm)
- [Kamra PMS](https://github.com/Kamra-PMS/kamra-pms) · [OCA/vertical-hotel](https://github.com/OCA/vertical-hotel) · [OCA/pms](https://github.com/OCA/pms) · [QloApps](https://github.com/Qloapps/QloApps)
- [Redsys — integración por redirección](https://pagosonline.redsys.es/desarrolladores-inicio/documentacion-tipos-de-integracion/desarrolladores-redireccion/)
- [huella (Verifactu en Python)](https://github.com/huella-verifactu/huella) · [verifactu-python](https://github.com/ldiazcuadrado/verifactu-python)
