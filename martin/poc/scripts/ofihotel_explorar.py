"""Explorador del esquema de OfiHotel, para rellenar el mapeo de la lectura.

Solo ejecuta SELECT sobre INFORMATION_SCHEMA (o sqlite_master en las pruebas) y conteos, y nunca
escribe. Imprime un informe Markdown con las tablas candidatas ordenadas por relevancia.

Uso con SQL Server:  python scripts/ofihotel_explorar.py --conn "<cadena>" --muestra 3
La cadena también puede venir de la variable OFIHOTEL_SQL_CONN, que es lo recomendable porque así no
queda en el historial de la terminal. Uso contra un fichero de prueba:  --sqlite ruta.db
Los valores de muestra salen enmascarados (solo los 2 primeros caracteres) salvo con --sin-mascara.
"""
import argparse
import os
import re
import sqlite3
import sys
import unicodedata

BUSCAR_POR_DEFECTO = "reserva,estancia,cliente,habitacion,huesped,entrada,salida,folio"


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar sin distinguir mayúsculas ni acentos."""
    base = unicodedata.normalize("NFD", str(texto).lower())
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def enmascarar(valor, visibles: int = 2) -> str:
    if valor is None:
        return "NULL"
    if isinstance(valor, (bytes, bytearray)):
        return "<binario>"
    texto = str(valor)
    return texto[:visibles] + "***" if len(texto) > visibles else texto[:1] + "***"


def _ident(nombre: str, dialecto: str) -> str:
    if dialecto == "sqlite":
        return '"' + nombre.replace('"', '""') + '"'
    return "[" + nombre.replace("]", "]]") + "]"


def listar_esquema(conn, dialecto: str) -> list[dict]:
    """Devuelve [{tabla, esquema, tipo, columnas:[(nombre, tipo)], filas}] solo con SELECT."""
    cur = conn.cursor()
    tablas = []
    if dialecto == "sqlite":
        cur.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','view') "
                    "AND name NOT LIKE 'sqlite_%' ORDER BY name")
        for nombre, tipo in cur.fetchall():
            tablas.append({"esquema": "", "tabla": nombre, "tipo": "VIEW" if tipo == "view" else "TABLE"})
    else:
        cur.execute("SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE FROM INFORMATION_SCHEMA.TABLES "
                    "ORDER BY TABLE_SCHEMA, TABLE_NAME")
        for esquema, nombre, tipo in cur.fetchall():
            tablas.append({"esquema": esquema, "tabla": nombre, "tipo": "VIEW" if "VIEW" in tipo else "TABLE"})
    for t in tablas:
        if dialecto == "sqlite":
            cur.execute("SELECT name, type FROM pragma_table_info(?)", (t["tabla"],))
            t["columnas"] = [(n, ty or "") for n, ty in cur.fetchall()]
            destino = _ident(t["tabla"], dialecto)
        else:
            cur.execute("SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
                        "WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ? ORDER BY ORDINAL_POSITION",
                        (t["esquema"], t["tabla"]))
            t["columnas"] = [(n, ty) for n, ty in cur.fetchall()]
            destino = f"{_ident(t['esquema'], dialecto)}.{_ident(t['tabla'], dialecto)}"
        t["destino"] = destino
        try:
            cur.execute(f"SELECT COUNT(*) FROM {destino}")
            t["filas"] = cur.fetchone()[0]
        except Exception:
            t["filas"] = None
    cur.close()
    return tablas


def puntuar(tablas: list[dict], palabras: list[str]) -> list[dict]:
    """Añade 'puntos' y 'coincidencias' a cada tabla: el nombre de tabla pesa 3 y cada columna 1."""
    claves = [normalizar(p.strip()) for p in palabras if p.strip()]
    for t in tablas:
        puntos, coinc = 0, []
        nombre = normalizar(t["tabla"])
        for k in claves:
            if k in nombre:
                puntos += 3
                coinc.append(f"tabla~{k}")
        for col, _tipo in t["columnas"]:
            nc = normalizar(col)
            for k in claves:
                if k in nc:
                    puntos += 1
                    coinc.append(f"{col}~{k}")
        t["puntos"], t["coincidencias"] = puntos, coinc
    return sorted(tablas, key=lambda t: (-t["puntos"], t["tabla"]))


def muestra_de(conn, t: dict, dialecto: str, n: int, mascara: bool) -> list[list[str]]:
    cur = conn.cursor()
    if dialecto == "sqlite":
        cur.execute(f"SELECT * FROM {t['destino']} LIMIT {int(n)}")
    else:
        cur.execute(f"SELECT TOP {int(n)} * FROM {t['destino']}")
    filas = [[enmascarar(v) if mascara else ("NULL" if v is None else str(v)) for v in f] for f in cur.fetchall()]
    cur.close()
    return filas


def _celda(texto) -> str:
    return re.sub(r"\s+", " ", str(texto)).replace("|", "\\|")


def generar_informe(conn, dialecto: str, buscar=BUSCAR_POR_DEFECTO, muestra: int = 0, mascara: bool = True) -> str:
    palabras = buscar.split(",") if isinstance(buscar, str) else list(buscar)
    tablas = puntuar(listar_esquema(conn, dialecto), palabras)
    candidatas = [t for t in tablas if t["puntos"] > 0]
    out = ["# Informe de esquema de OfiHotel", "",
           f"Tablas y vistas encontradas: {len(tablas)}. Candidatas por las palabras `{', '.join(p.strip() for p in palabras)}`: {len(candidatas)}.",
           "", "## Tablas candidatas (por relevancia)", ""]
    if candidatas:
        out += ["| Tabla | Tipo | Filas | Puntos | Coincidencias |", "|---|---|---|---|---|"]
        for t in candidatas:
            nombre = f"{t['esquema']}.{t['tabla']}" if t["esquema"] else t["tabla"]
            filas = "?" if t["filas"] is None else t["filas"]
            out.append(f"| {_celda(nombre)} | {t['tipo']} | {filas} | {t['puntos']} | {_celda(', '.join(t['coincidencias']))} |")
    else:
        out.append("Ninguna tabla coincide con las palabras buscadas.")
    out += ["", "## Columnas de las candidatas", ""]
    for t in candidatas:
        out += [f"### {t['tabla']}", "", "| Columna | Tipo |", "|---|---|"]
        out += [f"| {_celda(c)} | {_celda(ty)} |" for c, ty in t["columnas"]]
        if muestra > 0:
            out += ["", f"Muestra de {muestra} filas ({'enmascarada' if mascara else 'SIN enmascarar'}):", ""]
            filas = muestra_de(conn, t, dialecto, muestra, mascara)
            cabecera = [c for c, _ in t["columnas"]]
            out += ["| " + " | ".join(_celda(c) for c in cabecera) + " |", "|" + "---|" * len(cabecera)]
            out += ["| " + " | ".join(_celda(v) for v in f) + " |" for f in filas]
        out.append("")
    otras = [t for t in tablas if t["puntos"] == 0]
    out += ["## Resto de tablas y vistas", ""]
    out += [f"- {t['tabla']} ({'?' if t['filas'] is None else t['filas']} filas)" for t in otras] or ["- Ninguna"]
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Explora el esquema de OfiHotel en solo lectura")
    ap.add_argument("--conn", help="cadena de conexión ODBC (por defecto, la variable OFIHOTEL_SQL_CONN)")
    ap.add_argument("--sqlite", help="ruta de un fichero sqlite, para probar el explorador")
    ap.add_argument("--muestra", type=int, default=0, help="filas de muestra por tabla candidata")
    ap.add_argument("--sin-mascara", action="store_true", help="muestra los valores completos (datos personales)")
    ap.add_argument("--buscar", default=BUSCAR_POR_DEFECTO, help="palabras separadas por comas")
    args = ap.parse_args(argv)
    if args.sqlite:
        conn, dialecto = sqlite3.connect(f"file:{args.sqlite}?mode=ro", uri=True), "sqlite"
    else:
        cadena = args.conn or os.environ.get("OFIHOTEL_SQL_CONN")
        if not cadena:
            print("Falta --conn o la variable OFIHOTEL_SQL_CONN", file=sys.stderr)
            return 2
        try:
            import pyodbc
        except ImportError:
            print("Falta pyodbc: pip install pyodbc", file=sys.stderr)
            return 2
        conn, dialecto = pyodbc.connect(cadena, autocommit=True, timeout=5), "sqlserver"
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        print(generar_informe(conn, dialecto, args.buscar, args.muestra, not args.sin_mascara))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
