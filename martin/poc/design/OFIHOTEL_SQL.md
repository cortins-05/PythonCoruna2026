# Lectura de OfiHotel por SQL (solo lectura)

Este documento es para quien administra el servidor del hotel. OfiHotel no tiene API, así que nuestra aplicación lee su base SQL Server en solo lectura para saber qué ocupación hay y si una reserva de RoomCloud ya está pasada a OfiHotel, y la copia que leemos llega con los datos del día anterior. Nunca escribimos en OfiHotel y el check-out se sigue haciendo allí.

## Qué necesitamos

1. Un usuario de SQL Server con permiso solo de lectura (`db_datareader` o, mejor, `SELECT` únicamente sobre las tablas de reservas y estancias) sobre la copia diaria.
2. La cadena de conexión ODBC de ese usuario, que se entrega por un canal seguro y se guarda solo en la variable de entorno `OFIHOTEL_SQL_CONN`.
3. El nombre de las tablas (o vistas) de reservas y estancias, y en qué columnas están el apellido del huésped, la habitación, el tipo, las fechas de entrada y salida, el estado, el campo "Número Reserva Externo" y el número de personas.

## Cómo se usa el explorador

Como no conocemos el esquema, el explorador lo descubre sin escribir nada y solo con consultas `SELECT` sobre `INFORMATION_SCHEMA` y conteos.

1. Define la cadena en la terminal: `$env:OFIHOTEL_SQL_CONN = "<cadena>"` (así no queda en el historial como argumento).
2. Ejecuta `python scripts/ofihotel_explorar.py > esquema.md` para obtener el informe de tablas candidatas, ordenadas por relevancia.
3. Con `--muestra 3` añade tres filas por tabla candidata, con los valores enmascarados (solo se ven los 2 primeros caracteres). Usa `--sin-mascara` solo si es imprescindible y no compartas el resultado.
4. Con `--buscar palabra1,palabra2` cambias las palabras de búsqueda (por defecto reserva, estancia, cliente, habitacion, huesped, entrada, salida, folio), sin distinguir mayúsculas ni tildes.
5. Para probar la herramienta sin servidor, `--sqlite ruta.db` hace lo mismo contra un fichero sqlite.

## Cómo se rellena el mapeo

Copia `fixtures/ofihotel_mapeo.ejemplo.json` a un fichero propio fuera del repositorio y sustituye los marcadores (`TABLA_RESERVAS`, `COL_...`) por los nombres reales.

- `consultas`: uno o varios `SELECT` que devuelvan exactamente los alias `id_ofihotel, huesped, habitacion, tipo, entrada, salida, estado, numero_externo, personas`. La aplicación rechaza cualquier consulta que no sea `SELECT` o `WITH`, o que contenga palabras de escritura o ejecución.
- `tipos_habitacion`: código de OfiHotel a nuestro código (por ejemplo `"DB": "DBL-STD"`). Un código sin traducir se deja tal cual.
- `estados`: código de OfiHotel a `reservada`, `en_casa`, `salida` o `anulada`. Un código sin traducir detiene la lectura con un error, para no ocupar habitaciones por equivocación.
- `formato_fecha`: formato `strptime` de las fechas cuando la columna es texto (si es `datetime`, no hace falta).
- `regex_numero_externo`: con los grupos `localizador` y `portal`. El manual dice que el campo se rellena con `localizador-xx`, donde `xx` es el portal de Parity Rate/RoomCloud, así que `BK-4471920-1` produce la referencia `1-BK-4471920`. Si no encaja, la referencia queda vacía.

## Cómo se activa

```
OFIHOTEL_MODO=sql
OFIHOTEL_SQL_CONN=<cadena ODBC del usuario de solo lectura>
OFIHOTEL_MAPEO=<ruta del mapeo real>
```

Sin `OFIHOTEL_MODO` la aplicación usa la instantánea de ejemplo (`fixtures/ofihotel_ayer.json`). `OFIHOTEL_DATOS_HASTA` (ISO) fija el corte de los datos y, si falta, se toma el día anterior a las 23:59. Hace falta `pyodbc` y un driver ODBC de SQL Server instalado en la máquina.

## Protección de datos

- Solo lectura: guarda de consultas, conexión en autocommit con timeout de 5 segundos y cierre siempre.
- Solo las columnas necesarias: apellido, habitación, tipo, fechas, estado, número externo y personas.
- Nada de documentos de identidad ni direcciones, y el explorador enmascara por defecto.
- Nada en logs: solo se registra cuántas estancias se han leído, y la cadena de conexión no se escribe nunca en ficheros ni en trazas.
