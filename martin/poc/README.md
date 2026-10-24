# POC: expediente Ãºnico de estancia

Demo de una capa central donde viven los datos de cada estancia y desde la que salen hacia
cada programa. Contexto y decisiones en `martin/martin_investigacion.md`.

## QuÃ© es real y quÃ© estÃ¡ simulado

| Pieza | Estado en la demo |
|---|---|
| Expedientes, validaciones (letra del DNI y NIE, campos del parte), cuenta atrÃ¡s de 24 h, avisos, registro de quiÃ©n hizo quÃ©, bloqueo del cierre con trÃ¡mites pendientes | Real |
| Lectura de reservas de RoomCloud | XML grabado y **reconstruido** a partir de `docs/02-investigacion.md`, no es una respuesta real. El parser descarta `ccData` (tarjeta) |
| OCR del documento | Sin `ANTHROPIC_API_KEY` devuelve un documento de muestra. Con clave llama a Claude vision (`OCR_MODEL`, por defecto `claude-sonnet-5-5`). **El camino en vivo no se ha probado**, porque al montar la demo no habÃ­a clave |
| EnvÃ­o a SES.Hospedajes | **Simulado.** Genera un XML orientativo segÃºn el RD 933/2021, sin validar contra el XSD oficial (no es pÃºblico), y devuelve un justificante falso `SIM-â€¦` |
| Alta en OfiHotel | Copia asistida: OfiHotel no tiene API. Es el Ãºnico destino sin adaptador real |

El estado de las integraciones se ve siempre en la cabecera de la pÃ¡gina.

## Arrancar

```
cd poc
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8765
```

Abre <http://127.0.0.1:8765>, pulsa "Leer reservas de RoomCloud" y abre la llegada de Ana Pereira.
Para probar el OCR con una foto, `python scripts/crear_documento_muestra.py` genera
`fixtures/dni_muestra.png` (documento ficticio). `Reloj +6 h` avanza el reloj de la demo para
ver los avisos del plazo del parte.

Tests: `python -m pytest tests -q`

## Guion de 3 minutos

1. Leer reservas: aparece el listado del dÃ­a (sustituye al papel impreso).
2. Abrir a Ana: leer documento, ver los campos con poca confianza marcados, confirmar.
3. Pago y empresa: al viajar por trabajo, los datos fiscales se piden ya en el check-in.
4. Parte: revisar el XML, confirmar en el aviso y ver el justificante simulado.
5. Reloj +6 h varias veces en un expediente sin parte: salta el aviso de las 20 h y despuÃ©s el de fuera de plazo.
6. Intentar cerrar con trÃ¡mites pendientes: el sistema lo bloquea y dice quÃ© falta.

## LÃ­mites que hay que decir en voz alta

- Alguien sigue tecleando en OfiHotel, ahora con datos validados y en el orden de su formulario.
- El sistema no ve lo que pasa dentro de OfiHotel, asÃ­ que la factura y la liberaciÃ³n de la habitaciÃ³n dependen de que recepciÃ³n las marque.
- "Viaja por trabajo" se deduce buscando palabras en las notas de la reserva, y no es un dato fiable.
- La lectura de emails y la firma en tablet no estÃ¡n hechas.
- Los datos viven en un JSON local (`data/`, fuera de git) y no hay usuarios ni permisos.
