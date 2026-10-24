# Uniroom: una sola plataforma que bebe de todas las fuentes

Uniroom es una capa que se sitúa por encima de OfiHotel y RoomCloud, lee todo lo que entra al hotel (reservas de canal, el programa del hotel, reservas físicas, correo y WhatsApp), lo unifica y lo deja en un único sitio que hace de fuente única de verdad. Recepción solo confirma: cada petición llega ya contrastada con las demás fuentes y la respuesta sale por el mismo canal por el que llegó. Contexto, decisiones y el giro del 24/10 en `martin/martin_investigacion.md`.

## Qué se ve

| Pantalla | Qué enseña |
|---|---|
| **Fuente única** (inicio) | Las cinco fuentes que entran (RoomCloud, OfiHotel, recepción, correo y WhatsApp) con su prioridad, la escalera que decide quién gana cuando compiten, la cola de trabajo y la actividad unificada |
| **Comunicaciones** | Los mensajes recibidos, entendidos y contrastados noche a noche con RoomCloud, OfiHotel y recepción. Recepción edita el borrador, confirma y la respuesta sale por el canal de origen |
| **Estancias** | Estado de cada estancia en RoomCloud, OfiHotel y documentación, con el semáforo de seis colores y los conflictos entre fuentes |
| **Ocupación** | Habitaciones ocupadas por tipo y noche con el desglose por fuente, las peticiones que todavía compiten y los cierres de venta propuestos para RoomCloud |
| **Asistente** | Chat con OpenAI que consulta todo lo anterior, enseña los procesos paso a paso y permite navegar la aplicación hablando |

## Prioridad de las fuentes

| Nivel | Fuente | Tipo | Qué significa |
|---|---|---|---|
| 1 | RoomCloud | firme | Reservas de Booking, Expedia y la web, con garantía de pago |
| 2 | OfiHotel | firme | Lo registrado en el programa del hotel, con los datos de ayer |
| 3 | Recepción | firme | Walk-ins y peticiones que recepción ya ha confirmado |
| 4 | Correo | petición | Petición de fechas sin confirmar |
| 5 | WhatsApp | petición | Petición de fechas sin confirmar |

Lo firme (1 a 3) bloquea la habitación y una petición nunca lo desplaza. Entre dos peticiones gana el nivel más alto y, a igual nivel, la que llegó antes. Si entra una reserva de RoomCloud que ocupa el hueco de una petición, la petición pasa a "No disponible" y la pantalla avisa. La escalera vive en `app/prioridades.py` y es la regla de negocio que habría que configurar por hotel.

## Qué es real y qué está simulado

| Pieza | Estado en la demo |
|---|---|
| Contraste de peticiones con las fuentes, escalera de prioridades, estados por sistema, semáforo, conflictos, ocupación, overbooking, propuestas y aprobaciones | Real, sobre los datos del almacén |
| Asistente (chat) | Real con `OPENAI_API_KEY` (gpt-5.4-mini con herramientas y streaming). Sin clave, o si la API falla, enruta por palabras clave a las mismas herramientas y lo indica en el modo |
| Comprensión de los mensajes de clientes | Reglas deterministas en español, francés e inglés (fechas, personas, tipo de habitación), para que la demo no dependa de la red |
| Lectura de RoomCloud | XML grabado y reconstruido a partir de `docs/02-investigacion.md`. El parser descarta `ccData` (tarjeta) |
| Lectura de OfiHotel | Solo lectura, con la forma de una copia diaria de SQL Server (datos de ayer). Por defecto un JSON de ejemplo (`OFIHOTEL_MODO=fixture`); con `OFIHOTEL_MODO=sql`, `OFIHOTEL_SQL_CONN` y `OFIHOTEL_MAPEO` lee de verdad (ver `design/OFIHOTEL_SQL.md`). Nunca se escribe en OfiHotel |
| WhatsApp y correo | Simulados: los mensajes entrantes se inyectan (semilla o botón "Simular un mensaje") y los envíos quedan registrados como simulados |
| Cierre de disponibilidad en RoomCloud | Simulado y siempre con aprobación |
| Envío a SES.Hospedajes | Simulado, con justificante falso `SIM-…` |
| Alta en OfiHotel | Copia asistida: recepción la marca en la aplicación y la lectura del día siguiente la confirma |

Fuera de alcance a propósito: OCR de documentos, facturas y albaranes (el código de documentos sigue en el repositorio pero no se expone) y el check-out, que se hace en OfiHotel.

## Modelo de seguridad

1. **El lector no tiene herramientas.** Lee el mensaje de un desconocido y devuelve una intención de una lista cerrada.
2. **El asistente solo lee y propone.** El modelo solo elige herramientas, casi todas de lectura. Las tarjetas que ve la persona las construye el servidor con datos del almacén y nunca salen del texto del modelo.
3. **Nada sale sin que lo confirme una persona.** Enviar una respuesta a un cliente exige pulsar Confirmar en la tarjeta, y cada variable de las plantillas se valida con un formato estricto.
4. **La clave de OpenAI solo existe como variable de entorno** del proceso (`OPENAI_API_KEY`). No se escribe en ningún fichero y las pruebas la eliminan.

## Arrancar

```
cd martin/poc
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8765
```

Abre <http://127.0.0.1:8765>. Para el chat real arranca con la clave en el entorno (`$env:OPENAI_API_KEY = "..."` en PowerShell). `POST /api/demo/semilla?nivel=completa` deja la demo en su estado inicial (reloj fijo en 24/10 09:00). Tests: `python -m pytest tests -q`. Capturas de pantalla: `design/VERIFICAR.md`. Respuestas reales de la API con la semilla: `design/muestras/`, que se regeneran con `python scripts/volcar_muestras.py`.

## Guion de la demo (unos 7 minutos)

1. **Fuente única.** "La aplicación bebe de cinco fuentes y las unifica": recorre las tarjetas, la escalera de prioridades y la cola de trabajo.
2. **Comunicaciones.** Hay seis mensajes. Abre el correo en francés de Sophie Martin: pide una doble del 24 al 27 y no hay hueco porque la ocupan RoomCloud (2) y OfiHotel (1), así que propone del 25 al 28. Confirma y sale la respuesta en francés por correo (simulada).
3. **Prioridad entre peticiones.** Marta (WhatsApp, 08:49) y Pablo (correo, 08:57) piden la última individual de esta noche. Gana Pablo porque el correo tiene más prioridad que WhatsApp. Confirma a Pablo: se crea la reserva con prioridad 3 y la petición de Marta pasa a "No disponible" con alternativa.
4. **RoomCloud manda.** Pulsa "Simular una reserva de Booking" con Lucía todavía sin confirmar y observa cómo una petición disponible cambia a "No disponible" con aviso. Confirma a Lucía si sigue habiendo hueco.
5. **Estancias.** El semáforo: Claire en rojo (RoomCloud dice 24 al 27 y OfiHotel 24 al 26), Marcos en naranja (parte con el plazo de 24 h corriendo), Ana en amarillo (falta pasarla a OfiHotel) y Luis en gris (cancelada en RoomCloud pero viva en OfiHotel).
6. **Ocupación.** La rejilla con el desglose por fuente, las peticiones que compiten y la propuesta de cierre de venta en RoomCloud (simulada, con aprobación).
7. **Asistente.** "¿Qué hay que atender primero?", "Enséñame cómo entra una petición por WhatsApp" (proceso animado), "Enséñame la petición de Pablo Rey" (confirmar desde el chat) y "Llévame a la ocupación".

## Límites y avisos

- El receptor `/api/webhook/whatsapp` no hace el handshake de verificación de Meta ni comprueba la firma `X-Hub-Signature-256`: tiene la forma del webhook, no la conexión de producción.
- Si recepción rechaza un cierre de disponibilidad, no se vuelve a proponer para ese tipo y día aunque la ocupación empeore.
- OfiHotel llega con los datos del día anterior: lo que recepción pasa hoy queda como "marcado" hasta que la lectura de mañana lo confirme.
- Si OfiChannel ya sube disponibilidad a RoomCloud, esta aplicación no puede escribir también: solo uno puede hacerlo.
- Los datos viven en un JSON local (`data/`, fuera de git), sin usuarios ni permisos, y el registro no tiene política de conservación (el RD 933/2021 exige 3 años).
- La lectura de emails y WhatsApp reales y la firma en tablet no están hechas.
