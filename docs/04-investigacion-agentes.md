# Investigación con agentes: enfoques y productos existentes

> Hecha el 24 de octubre de 2026 con dos agentes de búsqueda web, desde una reunión de
> desarrolladores, sin poder llamar a Ofimática ni a RoomCloud. Complementa a
> `02-investigacion.md`. La cobertura pública es escasa y casi todo sale de fuentes
> secundarias o de muestras pequeñas.
>
> Leyenda: **[V]** verificado en una página leída · **[P]** parcial, fuente secundaria o
> fragmento de búsqueda · **[I]** inferencia · **[N]** no encontrado.

## Lo que no se encontró

No hay documentación pública de:

- La API ni el esquema SQL de **OfiHotel**.
- La especificación XML v2.3.4 de **RoomCloud**, ni del parámetro `useDLM`.
- El WSDL, el XSD y el manual técnico de **SES.Hospedajes**.
- Repositorios de GitHub que integren RoomCloud o SES.

Hay que pedirlos a los proveedores antes de diseñar nada.

---

## Parte 1 — Maneras de abordar el problema

| Enfoque | Valoración | Riesgo principal |
|---|---|---|
| **A. Pedir la integración a Ofimática** (API, importación, canal RoomCloud, SES) | Encaje excelente, esfuerzo bajo | Puede no existir; no se puede hacer hoy |
| **B. Check-in con conector ya hecho (Civitfun)** | Evita construir OCR y firma. Conector con OfiHotel **[V]** | Dependencia de un SaaS; mecanismo opaco; no se sabe si envía a SES |
| **C. RPA con `pywinauto` sobre la interfaz de OfiHotel** | Único camino de escritura si el proveedor no ofrece nada. Transitorio, con revisión humana | Frágil ante cualquier actualización; necesita sesión de Windows abierta **[I]** |
| **D. `pyodbc` en solo lectura sobre SQL Server** | Cubre OfiHotel → RoomCloud (disponibilidad) sin escribir en la base de datos | Esquema desconocido **[N]**; la licencia puede prohibirlo **[N]** |
| **E. Importación o exportación de ficheros** | Simple y auditable | No consta que OfiHotel tenga importación **[N]** |
| **F. Servicio Python único sobre la API XML de RoomCloud** | Cumple "solo un sistema lee `useDLM`". Se desarrolla contra `apitest` | Sin la especificación no se puede estimar; `ccData` en claro |
| **G. iPaaS (Make, n8n, Zapier…)** | Prototipado rápido | Sin conectores públicos **[N]**; los datos de tarjeta pasarían por un tercero |
| **H. Cambiar a un channel manager con API abierta (Beds24)** | API documentada con `modifiedSince` y webhooks **[V]** (V1) | Migración grande, y OfiHotel seguiría sin conexión |
| **I. Ingeniería inversa** | — | Riesgo legal y de soporte. **Descartado** |
| **J. Check-in propio en tablet** | Control total del flujo | Esfuerzo alto; validez legal de la firma sin verificar **[N]** |
| **K. Cliente Python para SES (`zeep`)** | Viable si se consigue el XSD | Sin especificación pública **[N]** |

### Hechos del RD 933/2021 verificados en el BOE **[V]**

- Plazo: transmisión inmediata y, como máximo, **24 horas** (art. 6.3).
- Registro informático conservado **3 años** (art. 5.3).
- Los campos por viajero están en el anexo I.
- El sistema de transmisión lo fija el Ministerio del Interior.

El BOE no detalla servicios web. Las sanciones y las diferencias de Cataluña y País Vasco
siguen sin verificar en el BOE **[P]**.

### Recomendación del agente

1. Sin código: preguntar a Ofimática y a RoomCloud (ver `01-problema.md`).
2. Fase 1: leer ocupación con `pyodbc` (D) y empujar disponibilidad a RoomCloud (F). Elimina
   la actualización manual sin escribir en la base de datos.
3. Fase 2 (reservas RoomCloud → OfiHotel): vía del proveedor (A o E); si no, RPA (C)
   transitorio, con cola y revisión humana, en paralelo hasta validar.
4. Check-in: evaluar Civitfun (B) antes de construir el propio (J).
5. Cliente SES propio (K): solo si el proveedor no cubre el envío y se consigue la
   especificación.
6. Cambio de channel manager (H): último recurso.

---

## Parte 2 — Productos que ya existen y sus fallos

| Producto | Qué cubre | Fallos o limitaciones conocidos |
|---|---|---|
| **OfiChannel** | Channel manager de Ofimática | La página oficial **se contradice** sobre si es bidireccional. No nombra RoomCloud en la parte leída. No menciona reservas ni cancelaciones. Un usuario cuenta que contrató RoomCloud aparte y que la configuración fue muy larga **[P]**. Sin precio |
| **OfiHotel** | PMS de escritorio y cloud | Dos reseñas en ComparaSoftware, ambas 1/5 (2025): servicios extra sin aviso, soporte lento, trato descortés. Ofimática publica 4,8/5 con 301 valoraciones en su propia web |
| **Registro de huéspedes + SES** | Envío automático del parte, con certificado digital | No documenta versión mínima, formato técnico ni qué pasa si un envío falla |
| **OfiEFirma, OfiScan, OfiCheckin, OfiKiosko** | Firma, escáner de DNI, pre-check-in, kiosco | Sin páginas primarias ni reseñas **[P]**. Una fuente dice que la integración de OfiScan con el PMS requiere Windows |
| **Civitfun** | Check-in online integrado con OfiHotel **[V]** | 3,3/5 con 7 reseñas: costes no comunicados e implantaciones de hasta 6 meses. Son quejas de Civitfun en general, no de la integración con OfiHotel. Solo cloud |
| **RoomCloud** | Channel manager | 4,7/5 con 24 reseñas. Quejas: errores en conexiones XML que costaron reservas, una reserva de OTA no importada que dejó a un huésped sin habitación (de hace cuatro años), soporte deficiente en una reseña. Elogios: menos overbooking y soporte rápido |
| **Chekin** | Check-in y registro SES | Cifras de PMS integrados contradictorias entre sus páginas. Sin evidencia de OfiHotel **[P]** |
| **SiteMinder** | Channel manager | Sin evidencia de integración con OfiHotel **[P]** |
| **Dataria** | Revenue management | Anuncia más de 30 integraciones; Hotel Tech Report verifica 3 |
| **ObeHotel** | Citado como integración | Sin información **[N]** |

### Hallazgos que cambian el plan

- **OfiChannel no está confirmado como solución.** Si solo sube disponibilidad y no baja
  reservas, el volcado manual de Flor sigue existiendo. Es la pregunta decisiva para
  Ofimática.
- **Verifactu no está acreditado.** Solo se encontró un artículo promocional que dice que
  OfiHotel está "adaptado". No hay homologación pública.
- **`seshospedajes.es` no es la web oficial.** Es una web privada con una API de pago. No
  confundirla con la vía del Ministerio.
- **Dos fechas distintas de obligatoriedad de SES**: 2-dic-2024 según Ofimática y 1-oct-2024
  según otra fuente. Ninguna contrastada con el Ministerio.
- **Las quejas más repetidas son costes ocultos y soporte lento.** Afectan a Ofimática,
  Civitfun y RoomCloud.

### Huecos que podría cubrir una solución propia **[I]**

1. **Conciliación entre OfiHotel y el canal**, con aviso de reservas no importadas. Ninguna
   fuente describe una.
2. **Cola de envíos a SES con reintentos y registro.** Ofimática no documenta qué ocurre
   cuando un envío falla.
3. **Check-out en un solo paso** (factura, habitación y parte). Ninguna fuente lo trata como
   flujo único.
4. **Verifactu verificable**, solo si OfiHotel no lo cumple. Es el hueco más arriesgado y
   requiere validación que no se ha investigado.

---

## Qué se puede hacer sin llamar a nadie

Lo que depende solo de la API de RoomCloud y del BOE, que sí están al alcance:

1. **Servicio de disponibilidad y conciliador contra `apitest.roomcloud.net`**, en modo
   simulación.
2. **Cola de partes a SES**, diseñada con los campos del anexo I del RD 933/2021 y probada
   con datos ficticios.
3. **Dejar para después** el esquema SQL, la escritura de reservas en OfiHotel y el check-in,
   que dependen de Ofimática.

Reglas de diseño que se mantienen (de `03-solucion.md`): descartar `ccData` al parsear,
idempotencia por `portalId` + `id` + `dlm`, un solo consumidor del cursor `useDLM`, logs
sin datos personales y proceso manual siempre posible.

## Fuentes principales

- [Ofimática — channel manager](https://www.ofi.es/software/channel-manager-hotel/)
- [Ofimática — registro de huéspedes](https://www.ofi.es/software/hoteles/registro-de-huespedes/)
- [ComparaSoftware — OfiHotel](https://www.comparasoftware.es/ofihotel)
- [Civitfun — integración con OfiHotel](https://en.civitfun.com/pms-integrations/ofihotel)
- [Hotel Tech Report — Civitfun](https://hoteltechreport.com/guest-experience/contactless-checkin/civitfun)
- [Hotel Tech Report — RoomCloud](https://hoteltechreport.com/revenue-management/channel-managers/roomcloud-channel-manager)
- [Dataria — integración con PMS](https://dataria.com/en/pms-integration.html)
- [Beds24 — conectar un PMS con la API](https://wiki.beds24.com/index.php/Connect_PMS_with_API)
- [BOE — Real Decreto 933/2021](https://www.boe.es/eli/es/rd/2021/10/26/933)
- [pywinauto](https://pywinauto.readthedocs.io/en/latest/)
- [zeep](https://docs.python-zeep.org/en/latest/)
