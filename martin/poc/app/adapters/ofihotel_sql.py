"""Lectura real de OfiHotel sobre SQL Server, en SOLO LECTURA.

OfiHotel no tiene API y no conocemos su esquema, así que la lectura se gobierna con un mapeo JSON
(consultas SELECT con alias normalizados, diccionarios de tipos y estados, formato de fecha y la
regex del número externo). La copia que se lee llega con los datos del día anterior.

Garantías de solo lectura: se rechaza cualquier consulta que no sea SELECT o WITH una vez quitados
comentarios y literales, y que contenga palabras de escritura o ejecución. La conexión se abre en
autocommit con timeout corto y se cierra siempre. La cadena de conexión sale de OFIHOTEL_SQL_CONN y
no se escribe nunca en ficheros ni en logs, y tampoco se registra ningún dato personal.
"""
import json
import logging
import os
import re
from datetime import date, datetime
from pathlib import Path

log = logging.getLogger("ofihotel_sql")

MAPEO_POR_DEFECTO = Path(__file__).resolve().parents[2] / "fixtures" / "ofihotel_mapeo.ejemplo.json"
COLUMNAS = ("id_ofihotel", "huesped", "habitacion", "tipo", "entrada", "salida", "estado",
            "numero_externo", "personas")
ESTADOS_VALIDOS = ("reservada", "en_casa", "salida", "anulada")
PALABRAS_PROHIBIDAS = ("INSERT", "UPDATE", "DELETE", "MERGE", "DROP", "ALTER", "CREATE", "TRUNCATE",
                       "EXEC", "EXECUTE", "GRANT", "REVOKE", "INTO", "OPENROWSET", "OPENQUERY",
                       "BULK", "BACKUP", "RESTORE", "SHUTDOWN", "DBCC")
TIMEOUT_SEGUNDOS = 5


class ConsultaNoPermitida(ValueError):
    """La consulta no es de solo lectura."""


class MapeoError(ValueError):
    """El mapeo o los datos leídos no encajan con lo esperado."""


def _sin_comentarios_ni_literales(sql: str) -> str:
    """Quita comentarios y literales de texto para inspeccionar solo las palabras del SQL."""
    salida, i, n = [], 0, len(sql)
    while i < n:
        par = sql[i:i + 2]
        if par == "--":
            fin = sql.find("\n", i)
            i = n if fin == -1 else fin
            salida.append(" ")
        elif par == "/*":
            fin = sql.find("*/", i + 2)
            if fin == -1:
                raise ConsultaNoPermitida("Comentario de bloque sin cerrar")
            i = fin + 2
            salida.append(" ")
        elif sql[i] == "'":
            i += 1
            while True:
                if i >= n:
                    raise ConsultaNoPermitida("Literal de texto sin cerrar")
                if sql[i] == "'":
                    if sql[i + 1:i + 2] == "'":
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            salida.append(" '' ")
        else:
            salida.append(sql[i])
            i += 1
    return "".join(salida)


def validar_solo_lectura(sql: str) -> str:
    """Devuelve la consulta si es de solo lectura y lanza ConsultaNoPermitida en caso contrario."""
    limpio = _sin_comentarios_ni_literales(sql).strip().rstrip(";").strip()
    if not limpio:
        raise ConsultaNoPermitida("Consulta vacía")
    if ";" in limpio:
        raise ConsultaNoPermitida("Solo se admite una sentencia por consulta")
    if not re.match(r"(?i)(select|with)\b", limpio):
        raise ConsultaNoPermitida("La consulta debe empezar por SELECT o WITH")
    mayus = limpio.upper()
    for palabra in PALABRAS_PROHIBIDAS:
        if re.search(rf"\b{palabra}\b", mayus):
            raise ConsultaNoPermitida(f"Palabra no permitida en una lectura: {palabra}")
    if re.search(r"\b(XP|SP)_", mayus):
        raise ConsultaNoPermitida("Procedimientos almacenados no permitidos (xp_ y sp_)")
    return sql


def cargar_mapeo(ruta=None) -> dict:
    ruta = Path(ruta or os.environ.get("OFIHOTEL_MAPEO") or MAPEO_POR_DEFECTO)
    mapeo = json.loads(ruta.read_text(encoding="utf-8"))
    for clave in ("consultas", "tipos_habitacion", "estados", "formato_fecha", "regex_numero_externo"):
        if clave not in mapeo:
            raise MapeoError(f"Falta la clave '{clave}' en el mapeo")
    if not mapeo["consultas"]:
        raise MapeoError("El mapeo no define ninguna consulta")
    for sql in mapeo["consultas"].values():
        validar_solo_lectura(sql)
    for codigo, estado in mapeo["estados"].items():
        if estado not in ESTADOS_VALIDOS:
            raise MapeoError(f"Estado '{estado}' no válido para el código '{codigo}'")
    re.compile(mapeo["regex_numero_externo"])
    return mapeo


def ref_externa_de(numero_externo: str, patron: str) -> str:
    """Convierte 'localizador-xx' en 'portal-localizador' (BK-4471920-1 pasa a 1-BK-4471920)."""
    m = re.match(patron, (numero_externo or "").strip())
    if not m:
        return ""
    try:
        localizador, portal = m.group("localizador"), m.group("portal")
    except IndexError:
        return ""
    return f"{portal}-{localizador}" if localizador and portal else ""


def _fecha_iso(valor, formato: str) -> str:
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    texto = str(valor).strip()
    try:
        return datetime.strptime(texto, formato).date().isoformat()
    except ValueError:
        try:
            return datetime.fromisoformat(texto).date().isoformat()
        except ValueError:
            raise MapeoError(f"Fecha ilegible con el formato '{formato}'") from None


def normalizar_fila(fila: dict, mapeo: dict) -> dict:
    """Pasa una fila con alias normalizados a la forma de estancia, sin escribir nada."""
    for col in COLUMNAS:
        if col not in fila:
            raise MapeoError(f"La consulta no devuelve la columna '{col}'")
    codigo_estado = str(fila["estado"]).strip()
    if codigo_estado not in mapeo["estados"]:
        raise MapeoError(f"Código de estado sin traducir: '{codigo_estado}'")
    codigo_tipo = str(fila["tipo"]).strip()
    numero = str(fila["numero_externo"] or "").strip()
    try:
        personas = int(fila["personas"] or 0)
    except (TypeError, ValueError):
        personas = 0
    return {
        "id_ofihotel": str(fila["id_ofihotel"]).strip(),
        "huesped": str(fila["huesped"] or "").strip(),
        "habitacion": str(fila["habitacion"] or "").strip(),
        "tipo": mapeo["tipos_habitacion"].get(codigo_tipo, codigo_tipo),
        "entrada": _fecha_iso(fila["entrada"], mapeo["formato_fecha"]),
        "salida": _fecha_iso(fila["salida"], mapeo["formato_fecha"]),
        "estado": mapeo["estados"][codigo_estado],
        "numero_externo": numero,
        "ref_externa": ref_externa_de(numero, mapeo["regex_numero_externo"]),
        "personas": personas,
    }


def _conectar_pyodbc():
    try:
        import pyodbc
    except ImportError as e:
        raise RuntimeError("Falta pyodbc: instálalo con 'pip install pyodbc' para leer OfiHotel por SQL") from e
    cadena = os.environ.get("OFIHOTEL_SQL_CONN", "")
    if not cadena:
        raise RuntimeError("Falta la variable de entorno OFIHOTEL_SQL_CONN con la cadena de conexión")
    return pyodbc.connect(cadena, autocommit=True, timeout=TIMEOUT_SEGUNDOS)


def leer_estancias(mapeo=None, conectar=None) -> list[dict]:
    """Ejecuta las consultas del mapeo (solo SELECT) y devuelve las estancias normalizadas."""
    mapeo = mapeo if isinstance(mapeo, dict) else cargar_mapeo(mapeo)
    consultas = [validar_solo_lectura(sql) for sql in mapeo["consultas"].values()]
    conexion = (conectar or _conectar_pyodbc)()
    estancias = []
    try:
        for sql in consultas:
            cursor = conexion.cursor()
            try:
                cursor.execute(sql)
                columnas = [d[0].lower() for d in cursor.description]
                for fila in cursor.fetchall():
                    estancias.append(normalizar_fila(dict(zip(columnas, fila)), mapeo))
            finally:
                cursor.close()
    finally:
        conexion.close()
    log.info("OfiHotel SQL: %d estancias leídas (solo lectura)", len(estancias))
    return estancias
