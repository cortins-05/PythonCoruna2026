# Funciones de OfiHotel a clonar en una app propia

> Investigación del 24 de octubre de 2026 con un agente de búsqueda web. Surge de una
> decisión nueva: **prescindir de OfiHotel** y construir una app propia, integrada por API con
> RoomCloud, con solo los servicios necesarios para una gestión sencilla y automatizada.
>
> Leyenda: **[V]** verificado en fuente abierta · **[P]** fuente promocional del fabricante o
> de comparativas · **[I]** inferido · **[NE]** no encontrado.
>
> Límites: los manuales de facturación, TPV, housekeeping y partes de viajeros solo se vieron
> como títulos. El manual de `clientes.ofi.es` parece de 2012. No hay precios públicos de
> OfiHotel. El RGPD no se investigó a fondo.

## Qué cambia con esta decisión

| Desaparece | Aparece |
|---|---|
| El problema 1: OfiHotel sin API pública | La **facturación y Verifactu** pasan a ser responsabilidad propia |
| La dependencia de Ofimática | Sustituir un PMS en un hotel que no puede parar (problema 17) |
| El riesgo de duplicar OfiChannel | La migración de los datos históricos |
| | El **RGPD** de los DNI y pasaportes guardados |

El principio rector se mantiene con otro sentido: **construir el núcleo y delegar lo
regulado** (facturación, pagos con tarjeta).

---

## 1. Inventario de funciones de OfiHotel

| Área | Qué hace | Estado |
|---|---|---|
| **Reservas** | Búsqueda por fecha, número, cliente o agencia; estados Pendiente, Anulada y Entrada; tipos Confirmada, Provisional y Cupo; grupos y congresos; preasignación de habitación; anular libera la habitación | [V] manual |
| **Cuadro de habitaciones** (rack) | Vista de estados: libre, ocupada, limpieza, bloqueada, salida hoy. Desde la habitación: check-in, check-out, cargos, limpieza, bloqueo, llaves, ficha de bienvenida | [V] manual |
| **Check-in** | Entrada directa o desde reserva, con NIF o pasaporte y datos de empresa | [V] |
| **Check-out** | Tres variantes: salida completa (factura al pagador), salida directa y anulación de check-in | [V] |
| **Cargos y consumos** | Manuales y automáticos por habitación, entregas a cuenta, estado de cuenta, cierre automático de estancia | [V] |
| **Limpieza** | Por habitación, planta o todas; limpiezas periódicas. El módulo de gobernanta con PDA se menciona sin detalle | [V] / [P] |
| **Facturación** | Factura directa, proforma, modificación, diario de facturas emitidas; series de facturación | [V] títulos |
| **Cobros y TPV** | Listado de cobros, caja, punto de venta con cargo a habitación, OfiRedsys | [V] títulos / [P] |
| **Partes de viajeros** | Parte de Hospedería y Ficha de Policía; OfiScan lee DNI y pasaporte | [V] títulos / [P] |
| **Estadísticas y administración** | Ocupación, producción, nacionalidades, INE; tesorería y OfiConta | [V] / [P] |
| **Clientes, agencias y empresas** | Fichas, contratos, cupos, bloqueo de tarifas | [P] |
| **Temporadas y tarifas** | Temporadas; valoración por día dentro de la reserva | [V] parcial |
| **Listados de recepción** | Llegadas, no presentados, salidas, reservas fallidas | [V] títulos |
| **Almacén y copia de seguridad** | Movimientos entre almacenes; respaldo de la base de datos | [P] / [V] título |
| **19 módulos complementarios** | OfiReservas, OfiChannel, OfiCheckin, OfiEFirma, OfiKiosko, OfiLlaves, OfiComanda, OfiEventos, OfiVIP, OfiCRM, OfiActiv… | [P] |

---

## 2. Clasificación para un hotel familiar con RoomCloud

### Imprescindible para el MVP

| Función | Por qué |
|---|---|
| Reservas: crear, modificar, anular, estados | Núcleo. Sustituye el volcado manual |
| Disponibilidad por tipo de habitación | Es lo que RoomCloud necesita recibir |
| **Sincronización bidireccional con RoomCloud** | Dolor principal |
| Ficha de cliente con documento | Necesaria para el parte y la factura |
| Check-in digital con firma táctil | Sustituye el BIENVENIDO en papel y el doble tecleo (problema 22) |
| **Parte a SES.Hospedajes** con alerta de 24 h | Obligación legal [V] |
| **Check-out en una acción** | Cierra estancia, factura y libera la habitación |
| **Vista diaria** de llegadas, salidas y ocupación | Sustituye el listado en papel desfasado (problema 23) |
| Tarifas y temporadas básicas | Necesarias para publicar precios en RoomCloud |
| Facturación compatible con Verifactu | Obligación legal. Ver sección 4: delegar |
| Registro de cobros | Mínimo para cerrar la cuenta |

### Útil después

Cargos y consumos · housekeeping · cobro con Redsys · pre-check-in web · exportación contable
para la gestoría · informes básicos · motor de reservas propio · copias de seguridad
automáticas.

### Prescindible para un hotel familiar

TPV de restauración y comandas · eventos, spa y almacén · centralita · kiosco · cadenas ·
fidelización con puntos · llaves magnéticas (es hardware) · funciones de otros países.

---

## 3. Qué no copiar de OfiHotel, y qué hacer mejor

**No copiar:**

- **Los tres tipos de salida** (completa, directa, anulación). Es el dolor de las tres acciones
  manuales.
- **El modelo de módulos sueltos con precio opaco**, y la conexión de canales como producto
  aparte.
- **Facturación autodeclarada para Verifactu.** La página de Ofimática no describe huella ni QR.
- Rastros de documentación antigua: el manual encontrado parece de 2012.

**Hacer mejor o más simple:**

- Un único flujo de check-out con validación previa: factura, habitación y parte.
- Sincronización con RoomCloud con reintentos y registro de errores.
- Check-in sin papel, con la firma y los datos enviados directamente al parte.
- Un tablero único que siempre refleja el estado real.
- Alertas de plazo: parte sin enviar, reserva que no bajó, habitación sin liberar.
- Auditoría sencilla de quién cambió qué.
- Exportación limpia a la gestoría.

---

## 4. Riesgos legales y de complejidad

### Verifactu: el mayor riesgo

- **Calendario (RDL 15/2025):** 1-ene-2027 para sociedades y 1-jul-2027 para el resto [V].
- **Un anuncio del 5-oct-2026** habla de trasladarlo a octubre de 2028. No consta formalizado
  en el BOE según una fuente. **Verificar en el BOE antes de decidir.**
- **Requisitos del software [V]:** huella (hash) por registro, encadenamiento con el hash
  anterior, QR de 30x30 a 40x40 mm, y una **declaración responsable del productor** por
  versión. No hay homologación previa de la AEAT.
- **Sanciones citadas [P, sin verificar en el BOE]:** 50.000 € por ejercicio al usuario con
  sistemas no certificados o alterados, y 1.000 € por sistema vendido sin declaración. Un
  desarrollo a medida también debe tener su declaración.

**Recomendación del agente: delegar la facturación** en un proveedor certificado con API y
pedirle su declaración responsable por escrito. Si se hace en casa, consultar antes con una
asesoría fiscal. Esto es una decisión que el equipo debe confirmar.

### SES.Hospedajes: riesgo medio, muy automatizable

- Plazo de 24 h [V]. Servicio web con XML comprimido en ZIP y Base64, con entornos de
  pruebas y producción. Documento técnico v3.1.2 [V]. Operaciones de alta, anulación y
  consulta.
- **Conflictos sin resolver:** fecha de inicio (1-oct-2024 o 2-dic-2024) y si el segundo
  apellido es obligatorio.
- **Cataluña:** una fuente dice que se sigue comunicando a los Mossos d'Esquadra y no a SES
  [P, sin verificar]. Solo importa si el hotel está en Cataluña.
- La web oficial dio error de certificado al leerla. Lo anterior se apoya en fuentes
  secundarias y en el documento técnico.

### RGPD: sin investigar

Los DNI y pasaportes son datos personales. Hay que documentar base legal, plazo de
conservación (el de SES es de tres años [P]), encargados del tratamiento (RoomCloud,
proveedor de facturación, hosting) y medidas de seguridad.

### Integración con RoomCloud

No se encontró la documentación de cómo dar de alta un PMS propio ni los permisos que
concede. Es lo único que exige hablar con RoomCloud.

### Complejidad técnica

| Área | Complejidad | Comentario |
|---|---|---|
| Reservas y disponibilidad | Media | Lo difícil es la sincronización |
| Check-in, firma, ficha | Baja | Formularios y almacenamiento |
| Parte SES | Baja-media | XML, ZIP y Base64; validar campos |
| Facturación | **Alta** | Verifactu: delegar |
| Cobros con tarjeta | **Alta** | PCI-DSS: delegar |
| Housekeeping | Baja | Estados simples |
| Tarifas y temporadas | Media | Qué publicar a RoomCloud |
| Informes | Baja | Consultas sobre reservas |

---

## 5. MVP por prioridad

1. Reservas y disponibilidad.
2. Sincronización con RoomCloud: primero lectura de reservas y luego escritura de
   disponibilidad y tarifas.
3. Ficha de cliente y check-in digital con firma táctil.
4. Parte a SES.Hospedajes con alerta de 24 h.
5. Check-out en una acción.
6. Facturación mediante proveedor Verifactu certificado.
7. Vista diaria.
8. Registro de cobros, sin pasarela propia.

**Verificar antes de empezar, por orden:**

1. El calendario de Verifactu en el BOE.
2. Si el hotel comunica a SES o a los Mossos.
3. El acceso a la API de RoomCloud para un PMS propio.
4. Un proveedor de facturación Verifactu con API y declaración responsable.
5. Una revisión específica del RGPD.

## Fuentes principales

- [Manual OfiHotel — índice](https://clientes.ofi.es/manuales/ofihotel/ofihotel_content_static.html)
- [Manual — Reservas](https://clientes.ofi.es/manuales/ofihotel/reservas.htm)
- [Manual — Cuadro de habitaciones](https://clientes.ofi.es/manuales/ofihotel/cuadro_de_habitaciones.htm)
- [OfiHotel — módulos](https://www.ofihotel.es/modulos)
- [Ofimática — Verifactu para hoteles](https://www.ofi.es/software/hoteles/verifactu-hoteles/)
- [ComparaSoftware — OfiHotel](https://www.comparasoftware.es/ofihotel)
- [BOE — Orden HAC/1177/2024](https://www.boe.es/buscar/act.php?id=BOE-A-2024-22138)
- [SES.Hospedajes — documento técnico v3.1.2](https://seshospedajes.es/wp-content/uploads/2024/12/MIR-HOSPE-DSI-WS-Servicio-de-Hospedajes-Comunicaciones-v3.1.2.pdf)
- [Verifactu — declaración responsable](https://www.verifactu.com/declaracion-responsable-verifactu/)
- [RoomCloud — integraciones](https://www.roomcloud.net/what-is-channel-manager/integrations/crs/)
