# Leer de OfiHotel sin depender de Ofimática: copia restaurada

> Investigación del 24 de octubre de 2026 con un agente de búsqueda web. Desarrolla la vía 1 de
> la pregunta "¿se puede leer de OfiHotel sin que Ofimática habilite nada?": mantener una
> **copia de solo lectura** restaurando copias de seguridad en una instancia aparte, y leerla
> con Python. Sirve de base para el panel en vivo de `07-fuente-de-verdad.md`.
>
> Leyenda: **[V]** verificado en documentación de Microsoft · **[P]** parcial o fuente
> secundaria · **[I]** inferido · **[NE]** no encontrado.
>
> Límites: no se ha encontrado nada público sobre el esquema, la versión de SQL Server ni el
> modelo de copias de OfiHotel. **Todo lo que sigue depende de lo que el servidor del hotel
> responda a las consultas del apartado 6.**

## Resumen

- **La mejora realista sin tocar la base de producción es hacer copias completas propias
  `COPY_ONLY` cada 15-30 minutos** y restaurarlas en otra instancia. Retraso estimado [I]: del
  orden de 15-30 minutos, según el tamaño de la base.
- **Bajar a minutos exige copias del log de transacciones**, y eso obliga a que la base esté en
  modelo de recuperación FULL. Si está en SIMPLE (el valor por defecto de SQL Server Express),
  cambiarlo es una intervención en la base de un tercero.
- **Si el servidor es Express, casi todas las técnicas rápidas quedan descartadas**: sin SQL
  Agent, sin log shipping, sin CDC, sin cifrado de copias.
- **Sin las consultas de diagnóstico, cualquier cifra es una suposición.**

## 1. Qué se sabe de las copias de OfiHotel

La página del manual `copia_de_seguridad.htm` **no parece describir OfiHotel**: habla de un
programa de gestión con empresas de gestión y tesorería, carpetas de copia y ZIP para Access, y
no menciona OfiHotel ni `BACKUP DATABASE` [P]. La lectura la hizo un modelo pequeño, así que
**hay que abrir la página directamente** antes de dar nada por cierto.

| Pregunta | Estado |
|---|---|
| ¿Usa `BACKUP DATABASE` de SQL Server? | [NE] para OfiHotel |
| ¿Dónde guarda los ficheros? | [P] carpeta accesible desde el servidor de base de datos (de una página de otro producto) |
| ¿Programa copias solas? | [P] no: recomienda regularidad sin intervalo |
| ¿Cambia el modelo de recuperación? | [NE] |

**Cómo salir de dudas desde el servidor:** la consulta 3 del apartado 6 lee `msdb.dbo.backupset`.
Si no devuelve filas, OfiHotel no usa `BACKUP` de SQL Server o el historial se ha borrado.

## 2. Modelo de recuperación: lo que decide todo

| Modelo | Copias del log | Consecuencia |
|---|---|---|
| **SIMPLE** | No | Solo copias completas o diferenciales. El retraso es el intervalo entre copias. Es el valor por defecto de Express [V] |
| **FULL** | Sí | Permite copias del log cada pocos minutos. **Si nadie hace copias del log, el log crece sin límite y puede llenar el disco** [V] |
| **BULK_LOGGED** | Sí, con limitaciones | No permite restaurar a un punto en el tiempo si hay cambios masivos [V] |

Se comprueba con `sys.databases.recovery_model_desc` y se cambia con `ALTER DATABASE ... SET
RECOVERY FULL`, que Microsoft permite en cualquier momento [V].

**Riesgos de cambiarlo en la base de un tercero:**

- Crecimiento del log si falla la copia [V].
- Altera la cadena de copias que usa el proveedor para restaurar [I].
- El soporte de Ofimática podría no aceptar el cambio [NE].

## 3. Estrategias, de menos a más invasivas

| # | Estrategia | Retraso realista | Edición necesaria | Impacto en producción |
|---|---|---|---|---|
| 1 | Copiar los `.bak` que ya genera OfiHotel | La frecuencia del proveedor (horas o un día) [P] | Cualquiera | Nulo |
| **2** | **Copias completas `COPY_ONLY` propias cada 15-30 min** | **15-30 min [I]** | Cualquiera | Bajo: lectura de disco durante la copia; no cambia el modelo ni la cadena [V] |
| 3 | Diferenciales cada 5-10 min | 5-10 min [I] | Cualquiera | Bajo. Una `COPY_ONLY` no sirve de base de la diferencial [V], así que depende de las completas del proveedor |
| 4 | Log en FULL con copias cada 1-5 min | 1-5 min [I] | Cualquiera | Medio: cambia el modelo y exige vigilar el log |
| 5 | Log shipping | Minutos [P] | Standard o superior; **no Express** [V] | Medio-alto |
| 6 | Replicación transaccional | Segundos [P] | Publicador Standard o Enterprise; Express solo como suscriptor [V] | Alto: instala componentes en la base publicada [I] |
| 7 | Database snapshots | No replica a otra instancia | Express sí | — Solo sirve en la misma instancia |
| 8 | Always On | Segundos | Enterprise para el grupo completo [P] | Alto |
| 9 | Change Data Capture | Segundos-minutos [I] | Standard o superior; **no Express** [V] | Medio |
| 10 | Change Tracking | Depende del sondeo | Cualquiera, incluido Express [V] | Modifica la base y obliga a consultar producción [I] |
| 11 | Mirroring | — | Obsoleto | **No usar** [V] |

**Qué no hacer [I]:** copiar los ficheros `.mdf` y `.ldf` con la base abierta (el resultado es
inconsistente) y leer el log de transacciones con herramientas externas.

**La estrategia 2 es la única que da minutos sin instalar nada en producción ni cambiar el
modelo de recuperación.** Tiene dos matices que conviene decir en voz alta:

1. **Hacer una copia es una acción sobre el servidor de producción**, aunque no escriba en las
   tablas: consume lectura de disco y necesita un permiso de copia de seguridad. No es "solo
   lectura" en el sentido estricto. [I] La cuenta que la ejecuta necesita permisos de copia, no
   de administrador.
2. **Hay que contar con el permiso del hotel y revisar el contrato de Ofimática** (ver
   `docs/01` y `02`: lo descartado fue escribir; esto es leer, pero conviene tenerlo por
   escrito).

## 4. Restaurar en SQL Server Express

| Límite | Express 2022 | Express 2025 |
|---|---|---|
| Tamaño máximo por base de datos | 10 GB | 50 GB |
| Memoria (buffer pool) | 1.410 MB | 1.410 MB |
| Procesador | 1 socket o 4 núcleos | 1 socket o 4 núcleos |
| SQL Server Agent, log shipping, TDE, cifrado y compresión de copias | No | No |

Todos [V] (tablas oficiales de ediciones). El límite de 10 GB parece aplicarse a los ficheros de
datos y excluir el log [P, hilo de Microsoft Q&A].

**Versiones:**

- **No se puede restaurar hacia atrás** [V]. El destino debe ser la misma versión que
  producción o una más nueva.
- Una copia de 2008 R2 o 2014 **sí se restaura en una versión nueva**, y la base se actualiza
  automáticamente, **sin vuelta atrás** [V]. La base queda con el nivel de compatibilidad
  antiguo (100 para 2008 R2) hasta que se suba, y se puede mantener [V].
- SQL Server 2014 terminó su soporte extendido el 10-jul-2024 [V]. La fecha de 2008 R2 no se
  pudo confirmar [NE]. Si producción corre una versión sin parches, la copia no lo arregla.

**Lectura entre restauraciones:**

- `RESTORE ... WITH STANDBY` deja la base de solo lectura. No aparece restringido por edición, pero
  tampoco documentado para Express: **probarlo en la instancia** [I].
- Mientras se restaura, el motor expulsa a los usuarios tras una breve espera [V]. Un panel
  leyendo la misma base se cae.
- **Diseño recomendado [I]: dos bases alternas** (`OfiHotel_A` y `OfiHotel_B`). Se restaura
  sobre la que no se lee y luego se cambia la que lee el panel. Cada una cuenta contra el
  límite de tamaño de Express.
- Antes de leer, el panel comprueba `state_desc = 'ONLINE'` y `is_in_standby`, y muestra un
  aviso si la copia no está lista [V para los campos].

**Automatizar sin SQL Agent:** el Programador de tareas de Windows con `sqlcmd` (incluido en
Express [V]) está documentado por Microsoft para copias en Express [P, KB 2019698]. PowerShell
con dbatools y Python con `pyodbc`: [NE] en esta investigación.

## 5. Fidelidad, seguridad y RGPD

**Fidelidad:**

- Una copia es **consistente a nivel transaccional**: el motor aplica el log hasta dejar la
  base coherente antes de abrirla [V].
- **Cómo medir el retraso:** comparar `MAX(backup_finish_date)` con la hora actual para la
  frescura de la copia, y la fecha de la última transacción de una tabla de OfiHotel para la
  frescura de los datos [P]. La segunda depende del esquema, que no se conoce [NE].
- **Cómo detectar que se queda atrás:** una tarea que alerte si la copia supera un umbral. Ojo:
  `sp_delete_backuphistory` borra el historial de `msdb`, así que puede estar incompleto [V].

**Seguridad y RGPD** (la copia contiene datos personales y de documentos de los huéspedes):

- Express no cifra las copias ni tiene TDE [V]. La mitigación es cifrar el disco con BitLocker
  [I, no verificado en esta investigación].
- La AEPD recoge el cifrado como medida de seguridad y avisa de que un cifrado mal implantado
  da falsa seguridad [P].
- Acceso mínimo con una cuenta de Windows dedicada, retención definida por script y borrado de
  copias antiguas [I].
- **Los datos de pago:** si la base guarda números de tarjeta, la copia hereda el problema de
  PCI-DSS (problema 7 de `01-problema.md`). Hay que saberlo antes de restaurarla.
- **Licencia:** Express es gratuita según Microsoft [V]. Revisar la licencia vigente antes de
  desplegar.

## 6. Plan por niveles y consultas de diagnóstico

| Nivel | Qué se hace | Retraso | Requisito |
|---|---|---|---|
| **0** | Solo diagnóstico (consultas de abajo) | — | Acceso de lectura |
| 1 | Copiar los `.bak` que OfiHotel ya genera y restaurarlos en Express | Horas o diario | Que existan copias |
| **2** | `COPY_ONLY` completas propias cada 15-30 min | 15-30 min [I] | Base de menos de 10 GB y permiso del hotel |
| 3 | Diferenciales cada 5-10 min | 5-10 min [I] | Controlar la cadena completa |
| 4 | Log en FULL con copias cada 1-5 min | 1-5 min [I] | Cambiar el modelo y acuerdo con el proveedor |
| 5-6 | Log shipping, replicación, Always On o CDC | Minutos o segundos | Edición Standard o superior y licencias |

**Recomendación:** nivel 0 ahora; después nivel 2 si la base cabe y el hotel lo permite. El
nivel 4 solo con un acuerdo escrito con Ofimática. Los niveles 5 y 6 solo si producción es
Standard o Enterprise.

### Consultas de diagnóstico (solo lectura)

Ejecutar en el servidor del hotel con una cuenta de lectura. Sustituir `OfiHotel` por el nombre
real de la base. Fuentes: documentación de Microsoft de `SERVERPROPERTY`, `sys.databases` y
`msdb.dbo.backupset` [V].

```sql
-- 1. Edición y versión (EngineEdition = 4 indica Express)
SELECT SERVERPROPERTY('Edition')        AS Edicion,
       SERVERPROPERTY('EngineEdition')  AS EngineEdition,
       SERVERPROPERTY('ProductVersion') AS Version,
       SERVERPROPERTY('ProductLevel')   AS Nivel;

-- 2. Modelo de recuperación, compatibilidad, estado y motivo de retención del log
SELECT name, compatibility_level, recovery_model_desc, state_desc,
       is_read_only, is_in_standby, log_reuse_wait_desc
FROM sys.databases;

-- 3. Últimas copias registradas: tipo (D completa, I diferencial, L log), COPY_ONLY, ruta
SELECT TOP (20)
       bs.database_name, bs.type, bs.is_copy_only,
       bs.backup_start_date, bs.backup_finish_date,
       bs.backup_size, bs.compressed_backup_size,
       bmf.physical_device_name
FROM msdb.dbo.backupset AS bs
LEFT JOIN msdb.dbo.backupmediafamily AS bmf
       ON bs.media_set_id = bmf.media_set_id
ORDER BY bs.backup_finish_date DESC;

-- 4. Tamaño de la última copia completa, en MB
SELECT TOP (1) database_name, backup_size / 1024.0 / 1024.0 AS MB
FROM msdb.dbo.backupset
WHERE database_name = N'OfiHotel' AND type = 'D'
ORDER BY backup_finish_date DESC;

-- 5. Frescura de la última copia
SELECT MAX(backup_finish_date) AS ultima_copia
FROM msdb.dbo.backupset
WHERE database_name = N'OfiHotel';
```

**Cómo leer las respuestas:**

| Resultado | Qué significa |
|---|---|
| `EngineEdition = 4` | Express: solo niveles 1 a 4 |
| `recovery_model_desc = SIMPLE` | No hay copias del log sin cambiar el modelo |
| `msdb.backupset` vacío | OfiHotel no usa `BACKUP` de SQL Server, o hay otro mecanismo |
| Tamaño de la copia por encima de 10 GB | No cabe en Express 2022 |
| `ProductVersion` empieza por 10.5 o 12 | SQL Server 2008 R2 o 2014: sin soporte, restaurar en una versión nueva |

## 7. Pendiente de comprobar

1. Abrir directamente la página de copias del manual de OfiHotel.
2. Ejecutar las cinco consultas en el servidor del hotel y recoger las respuestas.
3. Confirmar quién tiene credenciales en el servidor del hotel (¿el instalador, Ofimática?).
4. Probar `RESTORE ... WITH STANDBY` en Express con una copia de prueba.
5. Revisar el contrato de Ofimática en lo que toca a copias y acceso a la base.
6. Comprobar si la base guarda números de tarjeta.
7. Descubrir el esquema de las tablas de reservas, habitaciones y huéspedes, y de dónde sacar
   la fecha de la última transacción.
8. Fecha de fin de soporte de SQL Server 2008 R2.

## Fuentes principales

- [Ediciones y componentes de SQL Server 2022](https://learn.microsoft.com/en-us/sql/sql-server/editions-and-components-of-sql-server-2022)
- [Ediciones y componentes de SQL Server 2025](https://learn.microsoft.com/en-us/sql/sql-server/editions-and-components-of-sql-server-2025)
- [Modelos de recuperación](https://learn.microsoft.com/en-us/sql/relational-databases/backup-restore/recovery-models-sql-server)
- [Restauración y recuperación: descripción general](https://learn.microsoft.com/en-us/sql/relational-databases/backup-restore/restore-and-recovery-overview-sql-server)
- [RESTORE](https://learn.microsoft.com/en-us/sql/t-sql/statements/restore-statements-transact-sql)
- [Copias COPY_ONLY](https://learn.microsoft.com/en-us/sql/relational-databases/backup-restore/copy-only-backups-sql-server)
- [Log shipping](https://learn.microsoft.com/en-us/sql/database-engine/log-shipping/about-log-shipping-sql-server)
- [Replicación transaccional](https://learn.microsoft.com/en-us/sql/relational-databases/replication/transactional/transactional-replication)
- [Change Data Capture](https://learn.microsoft.com/en-us/sql/relational-databases/track-changes/about-change-data-capture-sql-server)
- [sys.databases](https://learn.microsoft.com/en-us/sql/relational-databases/system-catalog-views/sys-databases-transact-sql)
- [backupset](https://learn.microsoft.com/en-us/sql/relational-databases/system-tables/backupset-transact-sql)
- [SERVERPROPERTY](https://learn.microsoft.com/en-us/sql/t-sql/functions/serverproperty-transact-sql)
- [Ciclo de vida de SQL Server 2014](https://learn.microsoft.com/en-us/lifecycle/products/sql-server-2014)
- [Manual de OfiHotel — copia de seguridad](https://clientes.ofi.es/manuales/ofihotel/copia_de_seguridad.htm) (por verificar)
- [KB 2019698 — copias en Express con el Programador de tareas](https://support.microsoft.com/kb/2019698)
- [AEPD — orientaciones de criptografía](https://www.aepd.es/guias/orientaciones-criptografia-aepd-isms-apep.pdf)
