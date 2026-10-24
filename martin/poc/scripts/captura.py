#!/usr/bin/env python3
"""Conductor de capturas y pruebas de interacción para la interfaz web del hub.

El script arranca el servidor de la demo en un puerto libre con su propia base de datos temporal, siembra los datos de demostración, lanza un Chrome
headless con un perfil temporal y lo maneja por el protocolo DevTools, así que cada agente puede verificar su sección por su cuenta, sin chocar con
los demás y sin tocar el navegador del usuario. Al terminar imprime por stdout un único informe JSON y borra todo lo que creó, incluidos los procesos.

Código de salida: 0 si no hay errores de consola, excepciones ni peticiones fallidas, 1 si la página o algún paso tiene errores y 2 si falla el entorno
(servidor, Chrome, argumentos o tiempo). La guía de uso con ejemplos está en design/VERIFICAR.md.
"""
from __future__ import annotations

import argparse
import asyncio
import atexit
import base64
import json
import os
import re
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ES_WINDOWS = os.name == "nt"
RAIZ_POC = Path(__file__).resolve().parent.parent
PREFIJO_TMP = "captura_hotel_"
CARPETA_DIAGNOSTICOS = "diagnosticos_captura_hotel"
ESPERA_SELECTOR_S = 5.0
ESPERA_ARRANQUE_SERVIDOR_S = 25.0
ESPERA_ARRANQUE_CHROME_S = 20.0
ALTO_MAXIMO_CAPTURA = 16000
LIMITE_CONSOLA = 200
LIMITE_TEXTO = 1500
LIMITE_RESULTADO_JS = 10000
FECHA_DEMO = "2026-10-24T09:00:00"

T0 = time.monotonic()
VERBOSO = False


def trazar(mensaje: str) -> None:
    """Escribe una traza por stderr solo si se pidió --verboso, para depurar el propio script sin ensuciar el JSON de stdout."""
    if VERBOSO:
        print(f"[captura {time.monotonic() - T0:6.2f}s] {mensaje}", file=sys.stderr, flush=True)


def aviso_stderr(mensaje: str) -> None:
    print(f"[captura] {mensaje}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------------------------------------------------
# Errores propios
# ---------------------------------------------------------------------------------------------------------------------

class ErrorUso(Exception):
    """Argumentos o pasos mal escritos, que se detectan antes de arrancar nada."""


class ErrorEntorno(Exception):
    """Algo del entorno impide verificar, por ejemplo que el servidor no arranque, que no haya Chrome o que la conexión se caiga."""


class ErrorPaso(Exception):
    """Un paso de interacción no se pudo completar: el informe lo cuenta, se hace una captura de diagnóstico y el script sigue."""


class ErrorCDP(Exception):
    """Chrome contestó a un comando de DevTools con un error."""

    def __init__(self, metodo: str, error: dict):
        super().__init__(f"{metodo}: {error.get('message', error)}")
        self.metodo = metodo
        self.error = error


# ---------------------------------------------------------------------------------------------------------------------
# Utilidades de rutas y argumentos
# ---------------------------------------------------------------------------------------------------------------------

def _raices_msys() -> list[str]:
    """Carpetas donde Git Bash sitúa la barra inicial de Unix, que solo existen si el script se lanzó desde un shell MSYS (variable MSYSTEM)."""
    if not os.environ.get("MSYSTEM"):
        return []
    raices = ["C:/Program Files/Git", "C:/Program Files (x86)/Git", "C:/msys64", "C:/msys32"]
    exepath = os.environ.get("EXEPATH", "").replace("\\", "/").rstrip("/")
    if exepath:
        raices.insert(0, exepath[:-4] if exepath.lower().endswith("/bin") else exepath)
    return raices


def deshacer_msys(texto: str) -> str:
    """Git Bash convierte los argumentos que empiezan por barra, incluso '#/hoy' o '/api/x', en rutas como 'C:/Program Files/Git/hoy', y aquí se revierte."""
    for raiz in _raices_msys():
        texto = re.sub(re.escape(raiz) + r"(?=/)", "", texto, flags=re.IGNORECASE)
    return texto


def ruta_local(texto: str) -> Path:
    """Expande ~ y variables de entorno (%TEMP% o $TEMP) para que los mismos comandos sirvan en PowerShell y en Git Bash, y devuelve una ruta absoluta."""
    return Path(os.path.expandvars(os.path.expanduser(texto))).resolve()


def posix(ruta: Path) -> str:
    """Las rutas del informe llevan barras normales, que Windows acepta y no obligan a escapar nada en JSON."""
    return Path(ruta).resolve().as_posix()


def clave_unica(diccionario: dict, clave: str) -> str:
    """Si un selector o expresión se repite en el mismo flujo, la segunda lectura no pisa a la primera."""
    if clave not in diccionario:
        return clave
    n = 2
    while f"{clave} ({n})" in diccionario:
        n += 1
    return f"{clave} ({n})"


def recortar(texto: str, limite: int = LIMITE_TEXTO) -> str:
    texto = str(texto)
    return texto if len(texto) <= limite else texto[:limite] + f"… [recortado, {len(texto)} caracteres]"


# ---------------------------------------------------------------------------------------------------------------------
# Informe
# ---------------------------------------------------------------------------------------------------------------------

class Informe:
    """Acumula todo lo observado y lo imprime una sola vez como JSON, también cuando algo falla a medias."""

    def __init__(self, permitir_errores: bool):
        self.inicio = time.monotonic()
        self.permitir_errores = permitir_errores
        self.error: str | None = None
        self.url: str | None = None
        self.servidor: dict = {}
        self.navegador: str | None = None
        self.capturas: list[str] = []
        self.capturas_diagnostico: list[str] = []
        self.textos: dict = {}
        self.resultados_js: dict = {}
        self.existe: dict = {}
        self.consola: list[dict] = []
        self.consola_omitidas = 0
        self.excepciones: list[dict] = []
        self.peticiones_fallidas: list[dict] = []
        self.pasos: list[dict] = []
        self.avisos: list[str] = []
        self.log_servidor: str | None = None
        self.paso_actual: str | None = None
        self._impreso = False
        self._cerrojo = threading.Lock()

    def aviso(self, texto: str) -> None:
        if texto not in self.avisos:
            self.avisos.append(texto)

    def errores_consola(self) -> list[dict]:
        """Los errores de consola que cuentan para el código de salida: los de red ya salen en peticiones_fallidas, que sabe de las rutas permitidas."""
        return [c for c in self.consola if c["nivel"] == "error" and c["origen"] != "red"]

    def resumen(self) -> dict:
        return {"errores_consola": len(self.errores_consola()), "excepciones": len(self.excepciones),
                "peticiones_fallidas": len(self.peticiones_fallidas),
                "pasos_fallidos": len([p for p in self.pasos if p.get("ok") is False])}

    def codigo_salida(self) -> int:
        if self.error:
            return 2
        r = self.resumen()
        if r["pasos_fallidos"]:
            return 1
        if (r["errores_consola"] or r["excepciones"] or r["peticiones_fallidas"]) and not self.permitir_errores:
            return 1
        return 0

    def a_dict(self, codigo: int) -> dict:
        resumen = self.resumen()
        ok = self.error is None and not any(resumen.values())
        salida = {"ok": ok, "codigo_salida": codigo, "error": self.error, "resumen": resumen, "url": self.url, "servidor": self.servidor,
                  "navegador": self.navegador, "capturas": self.capturas, "capturas_diagnostico": self.capturas_diagnostico,
                  "textos": self.textos, "resultados_js": self.resultados_js, "existe": self.existe, "consola": self.consola,
                  "excepciones": self.excepciones, "peticiones_fallidas": self.peticiones_fallidas, "pasos": self.pasos,
                  "avisos": self.avisos, "duracion_ms": int((time.monotonic() - self.inicio) * 1000)}
        if self.permitir_errores:
            salida["errores_permitidos"] = True
        if self.consola_omitidas:
            salida["consola_omitidas"] = self.consola_omitidas
        if self.log_servidor:
            salida["log_servidor"] = self.log_servidor
        return salida

    def imprimir(self, codigo: int) -> None:
        with self._cerrojo:
            if self._impreso:
                return
            self._impreso = True
        try:
            sys.stdout.write(serializar(self.a_dict(codigo)))
            sys.stdout.flush()
        except (BrokenPipeError, OSError):
            pass  # quien lee cerró la tubería antes de tiempo y ya no hay a quién contárselo


def serializar(datos: dict) -> str:
    """JSON válido y legible con una línea por elemento de las listas y por clave de los diccionarios largos, que ocupa la mitad que indent=2 completo."""
    def uno(valor) -> str:
        return json.dumps(valor, ensure_ascii=False, default=str)

    lineas = []
    claves = list(datos)
    for i, clave in enumerate(claves):
        valor = datos[clave]
        coma = "," if i < len(claves) - 1 else ""
        compacto = uno(valor)
        if isinstance(valor, list) and valor and len(compacto) > 100:
            lineas.append(f"  {uno(clave)}: [")
            lineas.extend("    " + uno(e) + ("," if j < len(valor) - 1 else "") for j, e in enumerate(valor))
            lineas.append("  ]" + coma)
        elif isinstance(valor, dict) and valor and len(compacto) > 100:
            lineas.append(f"  {uno(clave)}: {{")
            elementos = list(valor.items())
            lineas.extend("    " + uno(a) + ": " + uno(b) + ("," if j < len(elementos) - 1 else "") for j, (a, b) in enumerate(elementos))
            lineas.append("  }" + coma)
        else:
            lineas.append(f"  {uno(clave)}: {compacto}{coma}")
    return "{\n" + "\n".join(lineas) + "\n}\n"


# ---------------------------------------------------------------------------------------------------------------------
# Procesos y directorios: limpieza garantizada
# ---------------------------------------------------------------------------------------------------------------------

_JOB = None  # el manejador del job object debe vivir tanto como el proceso, así que se guarda aquí


def proteger_con_job_object() -> None:
    """En Windows mete este proceso en un job object que mata a todos sus descendientes al cerrarse, así que Chrome y uvicorn mueren aunque el script caiga por la fuerza."""
    global _JOB
    if not ES_WINDOWS:
        return
    try:
        import ctypes
        from ctypes import wintypes

        class BasicLimit(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64), ("LimitFlags", wintypes.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t), ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", wintypes.DWORD), ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class Contadores(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                                                       "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class LimiteExtendido(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BasicLimit), ("IoInfo", Contadores), ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        k32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        k32.SetInformationJobObject.restype = wintypes.BOOL
        k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
        k32.AssignProcessToJobObject.restype = wintypes.BOOL
        k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        job = k32.CreateJobObjectW(None, None)
        if not job:
            return
        info = LimiteExtendido()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
            return
        if not k32.AssignProcessToJobObject(job, k32.GetCurrentProcess()):
            return
        _JOB = job
        trazar("job object activo: los procesos hijos morirán con este script")
    except Exception as e:  # es una red de seguridad extra, así que si falla basta con el taskkill del finally
        trazar(f"job object no disponible: {e}")


def proceso_vivo(pid: int) -> bool:
    if ES_WINDOWS:
        try:
            import ctypes
            from ctypes import wintypes
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.OpenProcess.restype = wintypes.HANDLE
            k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            k32.CloseHandle.argtypes = [wintypes.HANDLE]
            h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return ctypes.get_last_error() == 5  # acceso denegado quiere decir que existe
            codigo = wintypes.DWORD()
            ok = k32.GetExitCodeProcess(h, ctypes.byref(codigo))
            k32.CloseHandle(h)
            return bool(ok) and codigo.value == 259  # STILL_ACTIVE
        except Exception:
            return True
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def matar_arbol(proceso: subprocess.Popen) -> None:
    """Mata el proceso y todos sus descendientes: taskkill /T /F en Windows y el grupo de procesos en el resto."""
    try:
        if ES_WINDOWS:
            subprocess.run(["taskkill", "/PID", str(proceso.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            os.killpg(os.getpgid(proceso.pid), signal.SIGKILL)
    except Exception as e:
        trazar(f"no se pudo matar el árbol de {proceso.pid}: {e}")
    try:
        proceso.wait(timeout=5)
    except Exception:
        pass


def _quitar_solo_lectura(funcion, ruta, _info):
    try:
        os.chmod(ruta, stat.S_IWRITE)
        funcion(ruta)
    except OSError:
        pass


def borrar_directorio(ruta: Path, intentos: int = 10, pausa: float = 0.4) -> bool:
    """Chrome sigue unos instantes con ficheros abiertos tras morir, así que se reintenta antes de rendirse."""
    for _ in range(intentos):
        try:
            shutil.rmtree(ruta, onerror=_quitar_solo_lectura)
        except FileNotFoundError:
            return True
        except OSError:
            pass
        if not ruta.exists():
            return True
        time.sleep(pausa)
    shutil.rmtree(ruta, ignore_errors=True)
    return not ruta.exists()


def barrer_restos() -> None:
    """Borra carpetas temporales y capturas de diagnóstico de ejecuciones anteriores que murieron sin limpiar, sin tocar las de otras ejecuciones que siguen vivas."""
    try:
        base = Path(tempfile.gettempdir())
        ahora = time.time()
        for carpeta in base.glob(PREFIJO_TMP + "*"):
            m = re.match(re.escape(PREFIJO_TMP) + r"(\d+)_", carpeta.name)
            dueno = int(m.group(1)) if m else None
            try:
                edad = ahora - carpeta.stat().st_mtime
            except OSError:
                continue
            if dueno is not None and dueno != os.getpid() and proceso_vivo(dueno) and edad < 6 * 3600:
                continue
            if dueno == os.getpid():
                continue
            trazar(f"borro resto de una ejecución anterior: {carpeta.name}")
            borrar_directorio(carpeta, intentos=2, pausa=0.2)
        diag = base / CARPETA_DIAGNOSTICOS
        if diag.is_dir():
            for fichero in diag.iterdir():
                try:
                    if ahora - fichero.stat().st_mtime > 24 * 3600:
                        fichero.unlink()
                except OSError:
                    pass
    except Exception as e:
        trazar(f"barrido de restos con problemas: {e}")


class Limpieza:
    """Registro de lo que hay que matar y borrar, con una única función idempotente que sirve al finally, a las señales y al vigilante."""

    def __init__(self):
        self._cerrojo = threading.RLock()
        self._procesos: list[subprocess.Popen] = []
        self._directorios: list[Path] = []
        self._hecha = False

    def proceso(self, p: subprocess.Popen) -> None:
        with self._cerrojo:
            self._procesos.append(p)

    def directorio(self, d: Path) -> None:
        with self._cerrojo:
            self._directorios.append(d)

    def ejecutar(self) -> None:
        with self._cerrojo:
            if self._hecha:
                return
            self._hecha = True
            procesos, directorios = list(self._procesos), list(self._directorios)
        for p in procesos:
            matar_arbol(p)
        for d in directorios:
            if d.exists() and not borrar_directorio(d):
                aviso_stderr(f"No pude borrar la carpeta temporal {d}; bórrala a mano cuando Chrome haya terminado.")


# ---------------------------------------------------------------------------------------------------------------------
# HTTP sin proxy y puertos
# ---------------------------------------------------------------------------------------------------------------------

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def http(metodo: str, url: str, cuerpo=None, timeout: float = 10.0) -> tuple[int, bytes]:
    """Petición HTTP con la librería estándar y sin proxy, porque todo lo que se llama aquí es local."""
    datos = None
    cabeceras = {}
    if cuerpo is not None:
        datos = json.dumps(cuerpo).encode("utf-8")
        cabeceras["Content-Type"] = "application/json"
    peticion = urllib.request.Request(url, data=datos, method=metodo, headers=cabeceras)
    try:
        with _OPENER.open(peticion, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


async def http_async(metodo: str, url: str, cuerpo=None, timeout: float = 10.0) -> tuple[int, bytes]:
    return await asyncio.to_thread(http, metodo, url, cuerpo, timeout)


def puerto_libre() -> int:
    """Pide un puerto al sistema con un socket en el puerto 0, que es lo único que garantiza que dos ejecuciones simultáneas no elijan el mismo a la vez."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ---------------------------------------------------------------------------------------------------------------------
# Servidor de la demo
# ---------------------------------------------------------------------------------------------------------------------

def leer_cola(ruta: Path, lineas: int = 25, caracteres: int = 3000) -> str:
    """Últimas líneas del log del servidor, cortadas por línea para que el traceback no empiece a mitad de una."""
    try:
        cola = "\n".join(ruta.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-lineas:])
    except OSError:
        return ""
    return cola if len(cola) <= caracteres else cola[-caracteres:].split("\n", 1)[-1]


async def esperar_estado(base: str, proceso: subprocess.Popen | None, registro: Path | None, limite_s: float) -> None:
    """Sondea /api/estado hasta que responde 200, y falla rápido, con la cola del log, si el servidor propio muere antes."""
    fin = time.monotonic() + limite_s
    ultimo = "sin respuesta"
    while True:
        if proceso is not None and proceso.poll() is not None:
            cola = leer_cola(registro) if registro else ""
            raise ErrorEntorno(f"El servidor se cerró al arrancar (código {proceso.returncode}). Últimas líneas de su log:\n{cola}")
        try:
            estado, _ = await http_async("GET", base + "api/estado", timeout=3)
            if estado == 200 and (proceso is None or proceso.poll() is None):
                return
            ultimo = f"HTTP {estado}"
        except Exception as e:
            ultimo = f"{type(e).__name__}: {e}"
        if time.monotonic() > fin:
            cola = leer_cola(registro) if registro else ""
            raise ErrorEntorno(f"El servidor no respondió 200 en /api/estado tras {limite_s:.0f} s (último intento: {ultimo}).\n{cola}".strip())
        await asyncio.sleep(0.2)


async def arrancar_servidor(tmp: Path, limpieza: Limpieza, informe: Informe) -> str:
    """Lanza uvicorn desde martin/poc en un puerto libre con HOTEL_DB apuntando a un JSON temporal propio, y reintenta si otro proceso le roba el puerto."""
    entorno = dict(os.environ)
    for clave in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):  # sin clave el chat y el lector son deterministas, gratuitos y no salen a Internet
        entorno.pop(clave, None)
    entorno.update({"HOTEL_DB": str(tmp / "db.json"), "DEMO_START": FECHA_DEMO, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
                    "PYTHONUNBUFFERED": "1"})
    registro = tmp / "servidor.log"
    ultimo_error = ""
    for intento in range(1, 4):
        puerto = puerto_libre()
        with open(registro, "wb") as log:
            banderas = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW) if ES_WINDOWS else 0
            proceso = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(puerto), "--log-level", "warning"],
                cwd=str(RAIZ_POC), env=entorno, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                creationflags=banderas, start_new_session=not ES_WINDOWS)
        limpieza.proceso(proceso)
        base = f"http://127.0.0.1:{puerto}/"
        trazar(f"uvicorn lanzado (pid {proceso.pid}) en {base}, intento {intento}")
        try:
            await esperar_estado(base, proceso, registro, ESPERA_ARRANQUE_SERVIDOR_S)
        except ErrorEntorno as e:
            ultimo_error = str(e)
            matar_arbol(proceso)
            carrera = re.search(r"10048|10013|address already in use|Errno 98|Errno 48|JSONDecodeError|PermissionError|WinError 32", ultimo_error, re.IGNORECASE)
            cayo = "se cerró al arrancar" in ultimo_error
            if intento < 3 and (carrera or (cayo and intento < 2)):
                trazar("el servidor cayó al arrancar por una posible carrera (puerto o data/db.json), reintento")
                continue
            raise
        informe.servidor = {"url": base, "propio": True, "pid": proceso.pid, "hotel_db": posix(tmp / "db.json")}
        try:
            lee_hotel_db = "HOTEL_DB" in (RAIZ_POC / "app" / "store.py").read_text(encoding="utf-8", errors="replace")
        except OSError:
            lee_hotel_db = True
        if not lee_hotel_db:
            informe.aviso("app/store.py todavía no lee HOTEL_DB, así que el servidor usa data/db.json y dos ejecuciones simultáneas en este mismo árbol comparten ese fichero.")
        return base
    raise ErrorEntorno(ultimo_error or "No se pudo arrancar el servidor.")


async def post_ok(base: str, ruta: str, cuerpo=None) -> dict:
    estado, datos = await http_async("POST", base + ruta.lstrip("/"), cuerpo if cuerpo is not None else {}, timeout=30)
    if estado >= 400:
        raise ErrorEntorno(f"La siembra falló en POST {ruta}: HTTP {estado} {datos[:300].decode('utf-8', 'replace')}")
    try:
        return json.loads(datos or b"{}")
    except ValueError:
        return {}


def _ruta_inexistente(estado: int, datos: bytes) -> bool:
    """FastAPI contesta 404 con 'Not Found' (o 405) cuando la ruta no existe, y eso se distingue de un 404 que lance la propia lógica."""
    if estado not in (404, 405):
        return False
    try:
        detalle = json.loads(datos).get("detail", "")
    except (ValueError, AttributeError):
        return True
    return detalle in ("Not Found", "Method Not Allowed")


async def sembrar(base: str, nivel: str, informe: Informe) -> None:
    """Deja el servidor en el estado pedido, con respaldo a los endpoints antiguos mientras /api/demo/semilla no exista."""
    if nivel == "ninguna":
        informe.servidor["semilla"] = "ninguna"
        return
    via = "endpoint"
    if nivel in ("vacia", "completa", "demo"):
        estado, datos = await http_async("POST", base + f"api/demo/semilla?nivel={nivel}", {}, timeout=60)
        if _ruta_inexistente(estado, datos):
            via = "respaldo"
        elif estado >= 400:
            raise ErrorEntorno(f"La siembra falló en POST /api/demo/semilla?nivel={nivel}: HTTP {estado} {datos[:300].decode('utf-8', 'replace')}")
    else:
        via = "sync_roomcloud"
    if via != "endpoint":
        await post_ok(base, "/api/reiniciar")
        if nivel in ("basica", "completa"):
            await post_ok(base, "/api/sync/roomcloud")
        if nivel == "completa":
            await post_ok(base, "/api/sync/ofihotel")
            await post_ok(base, "/api/whatsapp/simular", {"wa_id": "34600111222", "nombre": "Ana", "texto": "Hola, ¿a qué hora es el check-in?"})
    informe.servidor["semilla"] = nivel
    informe.servidor["semilla_via"] = via
    trazar(f"semilla {nivel} aplicada ({via})")


# ---------------------------------------------------------------------------------------------------------------------
# Chrome
# ---------------------------------------------------------------------------------------------------------------------

def localizar_navegador() -> Path:
    candidatos: list[Path] = []
    if os.environ.get("CHROME_PATH"):
        candidatos.append(Path(os.environ["CHROME_PATH"]))
    if ES_WINDOWS:
        local = os.environ.get("LOCALAPPDATA", "")
        candidatos += [Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
                       Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe")]
        if local:
            candidatos.append(Path(local) / "Google" / "Chrome" / "Application" / "chrome.exe")
        candidatos += [Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
                       Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")]
    else:
        for nombre in ("google-chrome", "chromium", "chromium-browser", "chrome", "microsoft-edge"):
            encontrado = shutil.which(nombre)
            if encontrado:
                candidatos.append(Path(encontrado))
    for c in candidatos:
        if c.is_file():
            return c
    raise ErrorEntorno("No encuentro Chrome ni Edge en las rutas habituales. Instala Chrome o define la variable de entorno CHROME_PATH con la ruta de chrome.exe.")


async def lanzar_chrome(tmp: Path, args, limpieza: Limpieza, informe: Informe) -> tuple[int, subprocess.Popen]:
    """Lanza Chrome headless con perfil propio y deja que él elija el puerto de depuración (puerto 0), que lee de DevToolsActivePort sin carrera posible."""
    exe = localizar_navegador()
    perfil = tmp / "chrome"
    perfil.mkdir(parents=True, exist_ok=True)
    banderas = [str(exe), "--headless=new", f"--user-data-dir={perfil}", "--remote-debugging-port=0", "--no-first-run",
                "--no-default-browser-check", "--disable-gpu", "--hide-scrollbars", "--mute-audio", f"--window-size={args.ancho},{args.alto}",
                "--force-device-scale-factor=1", "--lang=es-ES", "--force-color-profile=srgb", "--font-render-hinting=none",
                "--disable-extensions", "--disable-background-networking", "--disable-sync", "--disable-default-apps",
                "--disable-component-update", "--disable-background-timer-throttling", "--disable-renderer-backgrounding",
                "--disable-backgrounding-occluded-windows", "--disable-ipc-flooding-protection", "--disable-hang-monitor",
                "--disable-features=Translate,MediaRouter,OptimizationHints", "--password-store=basic", "about:blank"]
    kwargs = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if ES_WINDOWS else {"start_new_session": True}
    proceso = subprocess.Popen(banderas, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs)
    limpieza.proceso(proceso)
    trazar(f"Chrome lanzado (pid {proceso.pid}): {exe.name}")
    fichero = perfil / "DevToolsActivePort"
    fin = time.monotonic() + ESPERA_ARRANQUE_CHROME_S
    while True:
        if proceso.poll() is not None:
            raise ErrorEntorno(f"{exe.name} se cerró al arrancar (código {proceso.returncode}).")
        try:
            lineas = fichero.read_text(encoding="utf-8").splitlines()
        except OSError:
            lineas = []
        if lineas and lineas[0].strip().isdigit():
            return int(lineas[0].strip()), proceso
        if time.monotonic() > fin:
            raise ErrorEntorno(f"{exe.name} no abrió el puerto de depuración en {ESPERA_ARRANQUE_CHROME_S:.0f} s.")
        await asyncio.sleep(0.05)


async def objetivo_de_pagina(puerto: int, informe: Informe) -> str:
    """Devuelve la URL websocket de la pestaña inicial, que se crea si Chrome arrancó sin ninguna."""
    base = f"http://127.0.0.1:{puerto}"
    fin = time.monotonic() + 10
    creada = False
    while True:
        try:
            estado, datos = await http_async("GET", base + "/json/list", timeout=3)
            if estado == 200:
                for t in json.loads(datos):
                    if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                        try:
                            _, version = await http_async("GET", base + "/json/version", timeout=3)
                            informe.navegador = json.loads(version).get("Browser")
                        except Exception:
                            pass
                        return t["webSocketDebuggerUrl"]
                if not creada:
                    creada = True
                    peticion = urllib.request.Request(base + "/json/new?about:blank", method="PUT")
                    await asyncio.to_thread(lambda: _OPENER.open(peticion, timeout=5).read())
        except Exception as e:
            trazar(f"esperando la pestaña de Chrome: {e}")
        if time.monotonic() > fin:
            raise ErrorEntorno("Chrome arrancó, pero no ofrece ninguna pestaña a la que conectarse.")
        await asyncio.sleep(0.1)


# ---------------------------------------------------------------------------------------------------------------------
# Cliente DevTools (CDP) sobre websockets
# ---------------------------------------------------------------------------------------------------------------------

class ClienteCDP:
    """Un único lector de websocket despacha las respuestas por id a sus futuros y los eventos a los oyentes, y nadie más llama a recv()."""

    def __init__(self, ws):
        self.ws = ws
        self._siguiente = 0
        self._pendientes: dict[int, asyncio.Future] = {}
        self._una_vez: dict[str, list[asyncio.Future]] = {}
        self.oyentes: list = []
        self.cerrado: str | None = None
        self._tarea = asyncio.get_running_loop().create_task(self._leer())

    @classmethod
    async def conectar(cls, url: str) -> "ClienteCDP":
        try:
            import websockets
        except ImportError as e:
            raise ErrorEntorno("Falta el paquete websockets (python -m pip install websockets).") from e
        try:
            ws = await websockets.connect(url, max_size=None, ping_interval=None, compression=None, open_timeout=10)
        except Exception as e:
            raise ErrorEntorno(f"No pude conectar con Chrome por DevTools: {type(e).__name__}: {e}") from e
        return cls(ws)

    async def _leer(self) -> None:
        motivo = "Chrome cerró la conexión de DevTools (¿se cayó la pestaña?)."
        try:
            async for crudo in self.ws:
                try:
                    mensaje = json.loads(crudo)
                except ValueError:
                    continue
                if "id" in mensaje:
                    futuro = self._pendientes.pop(mensaje["id"], None)
                    if futuro is not None and not futuro.done():
                        futuro.set_result(mensaje)
                else:
                    self._despachar(mensaje.get("method", ""), mensaje.get("params", {}))
        except Exception as e:
            motivo = f"Se perdió la conexión con Chrome: {type(e).__name__}: {e}"
        finally:
            self.cerrado = motivo
            for futuro in list(self._pendientes.values()) + [f for fs in self._una_vez.values() for f in fs]:
                if not futuro.done():
                    futuro.set_exception(ErrorEntorno(motivo))
                    futuro.exception()  # se marca como leída para que asyncio no proteste por un futuro que nadie esperaba
            self._pendientes.clear()
            self._una_vez.clear()

    def _despachar(self, metodo: str, params: dict) -> None:
        for futuro in self._una_vez.pop(metodo, []):
            if not futuro.done():
                futuro.set_result(params)
        for oyente in self.oyentes:
            try:
                oyente(metodo, params)
            except Exception as e:
                trazar(f"oyente con error en {metodo}: {e}")

    def una_vez(self, metodo: str) -> asyncio.Future:
        """Registra de antemano el futuro de un evento, para no perderse uno que llegue antes de empezar a esperar."""
        futuro = asyncio.get_running_loop().create_future()
        self._una_vez.setdefault(metodo, []).append(futuro)
        return futuro

    async def enviar(self, metodo: str, params: dict | None = None, timeout: float = 30.0) -> dict:
        if self.cerrado:
            raise ErrorEntorno(self.cerrado)
        self._siguiente += 1
        identificador = self._siguiente
        futuro = asyncio.get_running_loop().create_future()
        self._pendientes[identificador] = futuro
        try:
            await self.ws.send(json.dumps({"id": identificador, "method": metodo, "params": params or {}}))
        except Exception as e:
            self._pendientes.pop(identificador, None)
            raise ErrorEntorno(f"No pude enviar {metodo} a Chrome: {type(e).__name__}: {e}") from e
        try:
            mensaje = await asyncio.wait_for(futuro, timeout)
        except asyncio.TimeoutError:
            self._pendientes.pop(identificador, None)
            raise ErrorEntorno(f"Chrome no contestó a {metodo} en {timeout:.0f} s (¿la página está bloqueada por un bucle infinito?).") from None
        if "error" in mensaje:
            raise ErrorCDP(metodo, mensaje["error"])
        return mensaje.get("result", {})

    async def cerrar(self) -> None:
        try:
            await asyncio.wait_for(self.ws.close(), 3)
        except Exception:
            pass
        self._tarea.cancel()


# ---------------------------------------------------------------------------------------------------------------------
# Recolector de eventos: consola, excepciones y red
# ---------------------------------------------------------------------------------------------------------------------

def _texto_remoto(obj: dict) -> str:
    """Convierte un RemoteObject de consola en texto legible: valor primitivo, descripción o una vista previa de las propiedades."""
    if "value" in obj:
        v = obj["value"]
        return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    if "unserializableValue" in obj:
        return obj["unserializableValue"]
    if obj.get("type") == "undefined":
        return "undefined"
    if obj.get("subtype") == "null":
        return "null"
    descripcion = obj.get("description")
    vista = obj.get("preview", {}).get("properties")
    if vista and obj.get("subtype") not in ("error", "node"):
        cuerpo = ", ".join(f"{p['name']}: {p.get('value', '')}" for p in vista[:8])
        return f"{descripcion or 'Object'} {{{cuerpo}}}"
    return descripcion or obj.get("className") or obj.get("type", "")


def formatear_consola(argumentos: list[dict]) -> str:
    """Aplica los marcadores %s %d %o %c del primer argumento como hace la consola de Chrome, y une el resto con espacios."""
    if not argumentos:
        return ""
    textos = [_texto_remoto(a) for a in argumentos]
    primero = argumentos[0]
    if primero.get("type") == "string" and "%" in textos[0] and len(textos) > 1:
        resto = textos[1:]

        def sustituir(m):
            if m.group(1) == "%":
                return "%"
            if not resto:
                return m.group(0)
            valor = resto.pop(0)
            return "" if m.group(1) == "c" else valor

        base = re.sub(r"%([sdifoOc%])", sustituir, textos[0])
        return " ".join([base] + resto)
    return " ".join(textos)


class Recolector:
    """Traduce los eventos de DevTools a las listas del informe y lleva la cuenta de peticiones en vuelo para saber cuándo la red se calma."""

    def __init__(self, informe: Informe, permitidos_404: list[str]):
        self.informe = informe
        self.permitidos_404 = permitidos_404
        self.solicitudes: dict[str, dict] = {}
        self.en_vuelo: set[str] = set()
        self.ignoradas: set[str] = set()  # peticiones que ya hicieron esperar de más y no vuelven a retrasar ningún paso
        self.ultima_actividad = time.monotonic()
        self.cdp: ClienteCDP | None = None
        self.colgada = False
        self._tabla = {
            "Runtime.consoleAPICalled": self._consola_api, "Runtime.exceptionThrown": self._excepcion, "Log.entryAdded": self._log,
            "Network.requestWillBeSent": self._peticion, "Network.responseReceived": self._respuesta,
            "Network.loadingFinished": self._fin_carga, "Network.loadingFailed": self._carga_fallida,
            "Page.javascriptDialogOpening": self._dialogo, "Inspector.targetCrashed": self._caida}

    def __call__(self, metodo: str, p: dict) -> None:
        manejador = self._tabla.get(metodo)
        if manejador:
            manejador(p)

    # -- consola ------------------------------------------------------------------------------------------------------
    def _anotar(self, nivel: str, texto: str, url: str | None, linea: int | None, origen: str) -> None:
        grave = nivel in ("error", "warning")
        if len(self.informe.consola) >= (4 * LIMITE_CONSOLA if grave else LIMITE_CONSOLA):
            self.informe.consola_omitidas += 1
            return
        self.informe.consola.append({"nivel": nivel, "texto": recortar(texto), "url": url or None, "linea": linea, "origen": origen})

    def _consola_api(self, p: dict) -> None:
        tipo = p.get("type", "log")
        if tipo not in ("log", "debug", "info", "error", "warning", "dir", "dirxml", "table", "trace", "assert"):
            return
        nivel = {"error": "error", "assert": "error", "warning": "warning", "info": "info", "debug": "debug"}.get(tipo, "log")
        texto = formatear_consola(p.get("args", []))
        if tipo == "assert":
            texto = "Assertion failed: " + texto
        marcos = (p.get("stackTrace") or {}).get("callFrames") or [{}]
        marco = marcos[0]
        linea = marco.get("lineNumber")
        self._anotar(nivel, texto, marco.get("url"), (linea + 1) if isinstance(linea, int) else None, "console")

    def _log(self, p: dict) -> None:
        e = p.get("entry", {})
        if e.get("source") == "network" and "404" in e.get("text", "") and self._permitida(e.get("url", ""), 404):
            return
        nivel = {"verbose": "debug", "info": "info", "warning": "warning", "error": "error"}.get(e.get("level"), "info")
        origen = "red" if e.get("source") == "network" else "log:" + str(e.get("source", ""))
        linea = e.get("lineNumber")
        self._anotar(nivel, e.get("text", ""), e.get("url"), (linea + 1) if isinstance(linea, int) else None, origen)

    def _excepcion(self, p: dict) -> None:
        d = p.get("exceptionDetails", {})
        exc = d.get("exception", {})
        descripcion = exc.get("description") or d.get("text", "")
        pila = [f"{m.get('functionName') or '(anónima)'} ({m.get('url', '')}:{m.get('lineNumber', 0) + 1}:{m.get('columnNumber', 0) + 1})"
                for m in (d.get("stackTrace") or {}).get("callFrames", [])]
        linea = d.get("lineNumber")
        self.informe.excepciones.append({"texto": recortar(descripcion.split("\n")[0] if descripcion else d.get("text", "")),
                                         "detalle": recortar(descripcion), "pila": pila, "url": d.get("url"),
                                         "linea": (linea + 1) if isinstance(linea, int) else None})

    def _dialogo(self, p: dict) -> None:
        """El contrato prohíbe alert, confirm y prompt, así que un diálogo nativo cuenta como error y se cierra para que la página no se quede colgada."""
        self._anotar("error", f"Diálogo nativo prohibido ({p.get('type')}): {p.get('message', '')}", p.get("url"), None, "dialogo")
        if self.cdp is not None:
            asyncio.ensure_future(self._cerrar_dialogo())

    async def _cerrar_dialogo(self) -> None:
        try:
            await self.cdp.enviar("Page.handleJavaScriptDialog", {"accept": False}, timeout=5)
        except Exception:
            pass

    def _caida(self, _p: dict) -> None:
        self.colgada = True

    # -- red ----------------------------------------------------------------------------------------------------------
    def _permitida(self, url: str, estado: int | None) -> bool:
        if estado != 404:
            return False
        ruta = urllib.parse.urlsplit(url).path
        for patron in self.permitidos_404:
            if (ruta.startswith(patron) if patron.startswith("/") else patron in url):
                return True
        return False

    def _peticion(self, p: dict) -> None:
        identificador = p.get("requestId")
        peticion = p.get("request", {})
        url = peticion.get("url", "")
        self.solicitudes[identificador] = {"url": url, "metodo": peticion.get("method", "GET"), "tipo": p.get("type")}
        if p.get("type") in ("EventSource", "WebSocket") or url.startswith(("data:", "blob:")):
            return
        self.en_vuelo.add(identificador)
        self.ultima_actividad = time.monotonic()

    def _respuesta(self, p: dict) -> None:
        respuesta = p.get("response", {})
        estado = respuesta.get("status")
        url = respuesta.get("url", "")
        if isinstance(estado, int) and estado >= 400 and not url.startswith(("data:", "blob:")) and not self._permitida(url, estado):
            previa = self.solicitudes.get(p.get("requestId"), {})
            self.informe.peticiones_fallidas.append({"url": url, "estado": estado, "metodo": previa.get("metodo", "GET"),
                                                     "tipo": p.get("type") or previa.get("tipo"), "error": respuesta.get("statusText") or None})

    def _fin_carga(self, p: dict) -> None:
        self.en_vuelo.discard(p.get("requestId"))
        self.ultima_actividad = time.monotonic()

    def _carga_fallida(self, p: dict) -> None:
        self.en_vuelo.discard(p.get("requestId"))
        self.ultima_actividad = time.monotonic()
        error = p.get("errorText", "")
        previa = self.solicitudes.get(p.get("requestId"), {})
        url = previa.get("url", "")
        if p.get("canceled") or "ERR_ABORTED" in error or url.startswith(("data:", "blob:")) or p.get("type") in ("EventSource", "WebSocket"):
            return
        self.informe.peticiones_fallidas.append({"url": url, "estado": None, "metodo": previa.get("metodo", "GET"),
                                                 "tipo": p.get("type") or previa.get("tipo"), "error": error or p.get("blockedReason")})


# ---------------------------------------------------------------------------------------------------------------------
# Código que se ejecuta dentro de la página
# ---------------------------------------------------------------------------------------------------------------------

JS_PRELUDIO = r"""
const descr = (e) => {
  if (!e || !e.tagName) return String(e);
  let s = e.tagName.toLowerCase();
  if (e.id) s += '#' + e.id;
  const c = (typeof e.className === 'string' ? e.className : '').trim().split(/\s+/).filter(Boolean).slice(0, 2);
  if (c.length) s += '.' + c.join('.');
  const t = String(e.innerText || e.value || '').trim().replace(/\s+/g, ' ').slice(0, 30);
  return t ? s + ' «' + t + '»' : s;
};
const buscar = (sel) => {
  let base = sel, texto = null;
  const m = sel.match(/:texto\(\s*(["'])([\s\S]*?)\1\s*\)\s*$/);
  if (m) { base = sel.slice(0, m.index).trim() || '*'; texto = m[2].toLowerCase(); }
  let todos;
  try { todos = Array.from(document.querySelectorAll(base)); }
  catch (e) { return { invalido: String((e && e.message) || e) }; }
  if (texto !== null) {
    const coincide = (e) => String(e.innerText || e.value || e.getAttribute('aria-label') || e.title || '').toLowerCase().includes(texto);
    todos = todos.filter(coincide);
    todos = todos.filter((e) => !todos.some((o) => o !== e && e.contains(o)));
  }
  const visible = (e) => {
    const r = e.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    const s = getComputedStyle(e);
    return s.visibility !== 'hidden' && s.display !== 'none';
  };
  return { todos, vis: todos.filter(visible) };
};
"""

JS_CONTEO = r"""
const b = buscar(SEL);
if (b.invalido) return { invalido: b.invalido };
return { total: b.todos.length, visibles: b.vis.length };
"""

JS_TEXTO = r"""
const b = buscar(SEL);
if (b.invalido) return { invalido: b.invalido };
const res = { total: b.todos.length, visibles: b.vis.length };
const el = b.todos[0];
if (!el) return res;
const campo = ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName);
res.texto = (campo ? el.value : (el.innerText !== undefined && el.innerText !== '' ? el.innerText : el.textContent)) || '';
return res;
"""

JS_PUNTO = r"""
const b = buscar(SEL);
if (b.invalido) return { invalido: b.invalido };
const res = { total: b.todos.length, visibles: b.vis.length };
const el = b.vis[0];
if (!el) return res;
el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
const r = el.getBoundingClientRect();
const x0 = Math.max(r.left, 0), x1 = Math.min(r.right, innerWidth);
const y0 = Math.max(r.top, 0), y1 = Math.min(r.bottom, innerHeight);
if (x1 <= x0 || y1 <= y0) { res.fuera = true; return res; }
const x = Math.round((x0 + x1) / 2), y = Math.round((y0 + y1) / 2);
const arriba = document.elementFromPoint(x, y);
res.x = x; res.y = y; res.elemento = descr(el);
const dentro = !!arriba && (el === arriba || el.contains(arriba) ||
  (arriba.contains(el) && arriba !== document.body && arriba !== document.documentElement));
res.libre = dentro;
if (!dentro && arriba) res.tapado_por = descr(arriba);
return res;
"""

JS_RECTANGULO = r"""
const b = buscar(SEL);
if (b.invalido) return { invalido: b.invalido };
const res = { total: b.todos.length, visibles: b.vis.length };
const el = b.vis[0];
if (!el) return res;
el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
const r = el.getBoundingClientRect();
res.rect = { x: r.left + scrollX, y: r.top + scrollY, ancho: r.width, alto: r.height };
res.ventana = { ancho: innerWidth, alto: innerHeight };
res.elemento = descr(el);
return res;
"""

JS_SCROLL = r"""
const b = buscar(SEL);
if (b.invalido) return { invalido: b.invalido };
const res = { total: b.todos.length, visibles: b.vis.length };
const el = b.vis[0];
if (!el) return res;
el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
res.elemento = descr(el);
return res;
"""

JS_PREPARAR_ESCRITURA = r"""
const b = buscar(SEL);
if (b.invalido) return { invalido: b.invalido };
const res = { total: b.todos.length, visibles: b.vis.length };
const el = b.vis[0];
if (!el) return res;
el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
res.elemento = descr(el);
const tag = el.tagName.toLowerCase();
const tipo = (el.type || '').toLowerCase();
if (el.disabled) { res.error = 'está deshabilitado'; return res; }
if (el.readOnly) { res.error = 'es de solo lectura'; return res; }
const directos = ['date', 'time', 'datetime-local', 'month', 'week', 'color', 'range'];
if (tag === 'select' || directos.includes(tipo)) { res.directo = true; return res; }
const excluidos = ['checkbox', 'radio', 'button', 'submit', 'file', 'image', 'reset', 'hidden'];
const editable = tag === 'textarea' || (tag === 'input' && !excluidos.includes(tipo)) || el.isContentEditable;
if (!editable) { res.error = 'no es un campo de texto (' + tag + (tipo ? '[type=' + tipo + ']' : '') + ')'; return res; }
el.focus();
if (document.activeElement !== el && !el.contains(document.activeElement)) { res.error = 'no acepta el foco'; return res; }
if (tag === 'input' || tag === 'textarea') { try { el.select(); } catch (e) {} res.valor = el.value; }
else { getSelection().selectAllChildren(el); res.valor = el.innerText; }
res.listo = true;
return res;
"""

JS_ESCRIBIR_DIRECTO = r"""
const b = buscar(SEL);
const el = b.vis && b.vis[0];
if (!el) return { ok: false, motivo: 'el elemento desapareció' };
if (el.tagName === 'SELECT') {
  const ops = Array.from(el.options);
  const v = String(VALOR).toLowerCase();
  const op = ops.find((o) => o.value === VALOR) || ops.find((o) => o.text.trim() === VALOR) ||
             ops.find((o) => o.text.trim().toLowerCase().includes(v));
  if (!op) return { ok: false, motivo: 'no hay ninguna opción «' + VALOR + '» (opciones: ' + ops.map((o) => o.value || o.text.trim()).join(', ') + ')' };
  el.value = op.value;
} else { el.value = VALOR; }
el.dispatchEvent(new Event('input', { bubbles: true }));
el.dispatchEvent(new Event('change', { bubbles: true }));
return { ok: true, valor: el.value };
"""

JS_VALOR_ACTIVO = r"""
const e = document.activeElement;
if (!e) return '';
return ['INPUT', 'TEXTAREA'].includes(e.tagName) ? e.value : (e.innerText || '');
"""

JS_VACIAR_ACTIVO = r"""
const e = document.activeElement;
if (!e) return false;
if (e.tagName === 'INPUT' || e.tagName === 'TEXTAREA') {
  const proto = e.tagName === 'INPUT' ? HTMLInputElement.prototype : HTMLTextAreaElement.prototype;
  Object.getOwnPropertyDescriptor(proto, 'value').set.call(e, '');
} else { e.textContent = ''; }
e.dispatchEvent(new Event('input', { bubbles: true }));
return true;
"""

JS_VALOR_FINAL = r"""
const b = buscar(SEL);
const el = b.vis && b.vis[0];
if (!el) return null;
return ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName) ? el.value : (el.innerText || '');
"""

JS_FOCO = r"""
const e = document.activeElement;
if (!e || e === document.body || e === document.documentElement) return { tag: e ? e.tagName.toLowerCase() : null, en_cuerpo: true };
const cs = getComputedStyle(e);
const contorno = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0;
const sombra = cs.boxShadow && cs.boxShadow !== 'none';
return {
  elemento: descr(e), tag: e.tagName.toLowerCase(), id: e.id || null,
  rol: e.getAttribute('role'), etiqueta_aria: e.getAttribute('aria-label'),
  texto: String(e.innerText || e.value || '').trim().slice(0, 60),
  focus_visible: e.matches(':focus-visible'),
  anillo_visible: contorno || !!sombra,
  contorno: contorno ? cs.outlineStyle + ' ' + cs.outlineWidth + ' ' + cs.outlineColor : null,
  sombra: sombra ? cs.boxShadow : null
};
"""

JS_MEDIR = r"""
const de = document.documentElement;
let interno = 0, internoX = 0, elementoX = null;
for (const e of document.querySelectorAll('body *')) {
  const extraY = e.clientHeight >= 80 ? e.scrollHeight - e.clientHeight : 0;
  const extraX = e.clientWidth >= 100 ? e.scrollWidth - e.clientWidth : 0;
  if (extraY <= 1 && extraX <= 1) continue;
  const cs = getComputedStyle(e);
  if (extraY > 1 && (cs.overflowY === 'auto' || cs.overflowY === 'scroll')) interno = Math.max(interno, extraY);
  if (extraX > internoX && (cs.overflowX === 'auto' || cs.overflowX === 'scroll')) {
    internoX = extraX;
    elementoX = descr(e).replace(/ «.*»$/, '') + ' (contenido de ' + e.scrollWidth + ' px en una caja de ' + e.clientWidth + ' px)';
  }
}
return { alto: innerHeight, ancho: innerWidth, documento: Math.max(de.scrollHeight - innerHeight, 0),
         interno: interno, ancho_documento: de.scrollWidth, interno_x: internoX, elemento_x: elementoX };
"""

JS_ASENTAR = r"""
const tope = new Promise((r) => setTimeout(r, MAXIMO));
const trabajo = (async () => {
  try { await document.fonts.ready; } catch (e) {}
  for (let i = 0; i < 3; i++) {
    const vivas = document.getAnimations().filter((a) => {
      const t = a.effect && a.effect.getComputedTiming ? a.effect.getComputedTiming() : null;
      return a.playState === 'running' && t && isFinite(t.endTime);
    });
    if (!vivas.length) break;
    await Promise.allSettled(vivas.map((a) => a.finished));
  }
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
})();
await Promise.race([trabajo, tope]);
return true;
"""


def expresion(cuerpo: str, asincrona: bool = False, **argumentos) -> str:
    """Monta una expresión autocontenida para Runtime.evaluate, con los argumentos como literales JSON para que ningún selector rompa el código."""
    cabecera = "".join(f"const {nombre} = {json.dumps(valor, ensure_ascii=False)};\n" for nombre, valor in argumentos.items())
    marca = "async function" if asincrona else "function"
    return f"({marca}(){{\n{cabecera}{JS_PRELUDIO}\n{cuerpo}\n}})()"


# ---------------------------------------------------------------------------------------------------------------------
# Pasos: gramática y análisis
# ---------------------------------------------------------------------------------------------------------------------

NOMBRES_PASO = ("click", "hover", "escribir", "tecla", "esperar", "esperar-selector", "captura", "captura-elemento", "texto", "existe",
                "js", "scroll", "viewport", "tema", "navegar", "tab")


class Paso:
    def __init__(self, texto: str, nombre: str, arg: str, selector: str | None = None, valor: str | None = None):
        self.texto = texto
        self.nombre = nombre
        self.arg = arg
        self.selector = selector
        self.valor = valor


def dividir_igual(arg: str) -> tuple[str, str] | None:
    """Parte en el primer '=' que no esté dentro de corchetes, paréntesis ni comillas, para que los selectores de atributo como [name=x] sigan enteros."""
    corchetes = parentesis = 0
    comilla = None
    for i, c in enumerate(arg):
        if comilla:
            if c == comilla:
                comilla = None
            continue
        if c in "\"'":
            comilla = c
        elif c == "[":
            corchetes += 1
        elif c == "]":
            corchetes = max(corchetes - 1, 0)
        elif c == "(":
            parentesis += 1
        elif c == ")":
            parentesis = max(parentesis - 1, 0)
        elif c == "=" and corchetes == 0 and parentesis == 0:
            return arg[:i], arg[i + 1:]
    return None


def parsear_paso(texto: str) -> Paso:
    texto = texto.strip()
    if ":" not in texto:
        raise ErrorUso(f"El paso «{texto}» está mal escrito: la forma es nombre:argumento, por ejemplo click:#boton.")
    nombre, arg = texto.split(":", 1)
    nombre = nombre.strip().lower()
    if nombre not in NOMBRES_PASO:
        raise ErrorUso(f"El paso «{texto}» usa un nombre desconocido ({nombre}). Los válidos son: {', '.join(NOMBRES_PASO)}.")
    if not arg.strip() and nombre != "escribir":
        raise ErrorUso(f"El paso «{texto}» no lleva argumento.")
    if nombre in ("escribir", "captura-elemento"):
        partes = dividir_igual(arg)
        if partes is None or not partes[0].strip():
            forma = "escribir:SELECTOR=TEXTO" if nombre == "escribir" else "captura-elemento:SELECTOR=RUTA.png"
            raise ErrorUso(f"El paso «{texto}» necesita el formato {forma} (el '=' separa el selector del resto).")
        return Paso(texto, nombre, arg, selector=partes[0].strip(), valor=partes[1])
    if nombre in ("click", "hover", "esperar-selector", "texto", "existe", "scroll"):
        return Paso(texto, nombre, arg, selector=arg.strip())
    if nombre == "esperar":
        if not re.fullmatch(r"\d{1,6}", arg.strip()):
            raise ErrorUso(f"El paso «{texto}» necesita milisegundos enteros, por ejemplo esperar:500.")
    elif nombre == "viewport":
        if not re.fullmatch(r"\s*\d{2,5}\s*[xX×]\s*\d{2,5}\s*", arg):
            raise ErrorUso(f"El paso «{texto}» necesita el formato viewport:ANCHOxALTO, por ejemplo viewport:390x844.")
    elif nombre == "tema":
        if arg.strip().lower() not in ("claro", "oscuro"):
            raise ErrorUso(f"El paso «{texto}» solo admite tema:claro o tema:oscuro.")
    elif nombre == "tab":
        if not re.fullmatch(r"\d{1,3}", arg.strip()) or int(arg) < 1:
            raise ErrorUso(f"El paso «{texto}» necesita un número de pulsaciones mayor que cero, por ejemplo tab:3.")
    return Paso(texto, nombre, arg)


# Teclas con nombre en minúsculas: (key, code, código virtual de Windows, texto que producen)
TECLAS = {
    "enter": ("Enter", "Enter", 13, "\r"), "tab": ("Tab", "Tab", 9, ""), "escape": ("Escape", "Escape", 27, ""),
    "esc": ("Escape", "Escape", 27, ""), "backspace": ("Backspace", "Backspace", 8, ""), "delete": ("Delete", "Delete", 46, ""),
    "space": (" ", "Space", 32, " "), "arrowup": ("ArrowUp", "ArrowUp", 38, ""), "arrowdown": ("ArrowDown", "ArrowDown", 40, ""),
    "arrowleft": ("ArrowLeft", "ArrowLeft", 37, ""), "arrowright": ("ArrowRight", "ArrowRight", 39, ""), "home": ("Home", "Home", 36, ""),
    "end": ("End", "End", 35, ""), "pageup": ("PageUp", "PageUp", 33, ""), "pagedown": ("PageDown", "PageDown", 34, ""),
}
MODIFICADORES = {"alt": 1, "ctrl": 2, "control": 2, "meta": 4, "cmd": 4, "shift": 8}


def describir_tecla(texto: str) -> dict:
    """Traduce 'Enter', 'Shift+Tab' o 'a' a los parámetros de Input.dispatchKeyEvent, con texto solo cuando la tecla escribe algo."""
    partes = texto.strip().split("+")
    modificadores = 0
    while len(partes) > 1 and partes[0].strip().lower() in MODIFICADORES:
        modificadores |= MODIFICADORES[partes.pop(0).strip().lower()]
    nombre = "+".join(partes).strip() or "+"
    if nombre.lower() in TECLAS:
        key, code, virtual, producido = TECLAS[nombre.lower()]
    elif len(nombre) == 1:
        key = producido = nombre
        if nombre.isascii() and nombre.isalpha():
            code, virtual = "Key" + nombre.upper(), ord(nombre.upper())
        elif nombre.isdigit():
            code, virtual = "Digit" + nombre, ord(nombre)
        else:
            code, virtual = "", 0
    else:
        raise ErrorPaso(f"No conozco la tecla «{texto}». Usa Enter, Tab, Escape, Backspace, Delete, Space, ArrowUp, ArrowDown, ArrowLeft, "
                        "ArrowRight, Home, End, PageUp, PageDown o un carácter, con prefijos Shift+, Control+ o Alt+.")
    params = {"modifiers": modificadores, "key": key, "code": code, "windowsVirtualKeyCode": virtual, "nativeVirtualKeyCode": virtual}
    if producido and not modificadores & 7:
        params["text"] = producido.upper() if modificadores & 8 and len(producido) == 1 else producido
        params["unmodifiedText"] = producido
    if modificadores & 2 and key.lower() == "a":
        params["commands"] = ["selectAll"]
    return params


# ---------------------------------------------------------------------------------------------------------------------
# La página: navegación, esperas, interacción y capturas
# ---------------------------------------------------------------------------------------------------------------------

class Pagina:
    def __init__(self, cdp: ClienteCDP, rec: Recolector, informe: Informe, args):
        self.cdp = cdp
        self.rec = rec
        self.informe = informe
        self.args = args
        self.ancho = args.ancho
        self.alto = args.alto
        self.tema = args.tema
        self.reducido = args.movimiento_reducido
        self.diagnosticos = 0
        self.anchos_vigilados: set[int] = set()

    # -- arranque -----------------------------------------------------------------------------------------------------
    async def iniciar(self) -> None:
        """Activa los dominios de DevTools y fija viewport y medios emulados antes de navegar, para que el primer pintado ya sea el correcto."""
        c = self.cdp
        await c.enviar("Page.enable")
        await c.enviar("Runtime.enable")
        await c.enviar("Log.enable")
        await c.enviar("Network.enable")
        await c.enviar("Network.setCacheDisabled", {"cacheDisabled": True})
        try:
            await c.enviar("Inspector.enable")
        except ErrorCDP:
            pass
        await self._aplicar_viewport(self.ancho, self.alto)
        await self._aplicar_medios()
        try:
            await c.enviar("Emulation.setFocusEmulationEnabled", {"enabled": True})
        except ErrorCDP:
            pass

    async def _aplicar_viewport(self, ancho: int, alto: int) -> None:
        await self.cdp.enviar("Emulation.setDeviceMetricsOverride", {"width": ancho, "height": alto, "deviceScaleFactor": 1, "mobile": False,
                                                                       "screenWidth": ancho, "screenHeight": alto})

    async def _aplicar_medios(self) -> None:
        await self.cdp.enviar("Emulation.setEmulatedMedia", {"features": [
            {"name": "prefers-color-scheme", "value": "dark" if self.tema == "oscuro" else "light"},
            {"name": "prefers-reduced-motion", "value": "reduce" if self.reducido else "no-preference"}]})

    # -- evaluación ---------------------------------------------------------------------------------------------------
    async def _evaluar_en_bruto(self, parametros: dict, timeout: float) -> dict:
        """Si un clic provoca una navegación completa, el contexto de la página se destruye a mitad de la llamada, así que se reintenta sobre el documento nuevo."""
        for intento in range(8):
            try:
                return await self.cdp.enviar("Runtime.evaluate", parametros, timeout=timeout)
            except ErrorCDP as e:
                texto = str(e).lower()
                if intento < 7 and ("context" in texto or "navigated" in texto or "destroyed" in texto):
                    trazar(f"el contexto cambió durante la evaluación, reintento ({texto[:80]})")
                    await asyncio.sleep(0.25)
                    continue
                raise
        raise ErrorEntorno("La página no dejó de cambiar de documento durante la evaluación.")

    async def evaluar(self, codigo: str, promesa: bool = False, timeout: float = 20.0):
        r = await self._evaluar_en_bruto({"expression": codigo, "returnByValue": True, "awaitPromise": promesa, "userGesture": True}, timeout)
        if "exceptionDetails" in r:
            d = r["exceptionDetails"]
            exc = d.get("exception", {})
            raise ErrorPaso(f"La evaluación en la página lanzó una excepción: {recortar(exc.get('description') or d.get('text') or 'sin detalle', 600)}")
        return r.get("result", {}).get("value")

    # -- esperas ------------------------------------------------------------------------------------------------------
    async def esperar_red(self, quieto_s: float = 0.5, maximo_s: float = 10.0) -> None:
        """Espera a que no haya peticiones en vuelo durante un rato seguido, con un tope para no quedarse atascado con una conexión eterna."""
        fin = time.monotonic() + maximo_s
        while True:
            if self.rec.colgada:
                raise ErrorEntorno("La pestaña de Chrome se cayó (Inspector.targetCrashed).")
            ahora = time.monotonic()
            pendientes = self.rec.en_vuelo - self.rec.ignoradas
            if not pendientes and ahora - self.rec.ultima_actividad >= quieto_s:
                return
            if ahora > fin:
                self.informe.aviso(f"La red no se calmó en {maximo_s:.0f} s ({len(pendientes)} peticiones siguen en vuelo); sigo igualmente y no vuelvo a esperarlas.")
                self.rec.ignoradas |= pendientes
                return
            await asyncio.sleep(0.05)

    async def asentar(self, quieto_s: float = 0.3) -> None:
        """Deja que la interfaz termine de reaccionar: red en calma, fuentes cargadas, animaciones finitas acabadas y dos fotogramas pintados."""
        await self.esperar_red(quieto_s, 6.0)
        try:
            await self.evaluar(expresion(JS_ASENTAR, asincrona=True, MAXIMO=2500), promesa=True, timeout=10)
        except ErrorPaso:
            pass
        await self._vigilar_desbordamiento()

    async def _vigilar_desbordamiento(self) -> None:
        """Avisa del scroll horizontal del documento, que en móvil casi siempre indica un elemento que se sale de la ventana."""
        if self.ancho in self.anchos_vigilados:
            return
        try:
            m = await self.evaluar(expresion(JS_MEDIR))
        except (ErrorPaso, ErrorEntorno):
            return
        if not m:
            return
        if m["ancho_documento"] > m["ancho"] + 1:
            self.anchos_vigilados.add(self.ancho)
            self.informe.aviso(f"Hay desbordamiento horizontal con ventana de {m['ancho']} px: el documento mide {m['ancho_documento']} px de ancho.")
        elif m.get("interno_x", 0) > 1 and m["ancho"] <= 800:
            self.anchos_vigilados.add(self.ancho)
            self.informe.aviso(f"Con ventana de {m['ancho']} px hay scroll horizontal dentro de {m['elemento_x']}; si no es intencionado, algo se sale de su caja.")

    # -- navegación ---------------------------------------------------------------------------------------------------
    async def cargar(self, url: str) -> None:
        carga = self.cdp.una_vez("Page.loadEventFired")
        r = await self.cdp.enviar("Page.navigate", {"url": url})
        if r.get("errorText"):
            raise ErrorEntorno(f"Chrome no pudo abrir {url}: {r['errorText']}")
        await self._esperar_carga(carga)
        if self.args.esperar_ms:
            await asyncio.sleep(self.args.esperar_ms / 1000)
        await self.asentar()

    async def _esperar_carga(self, carga: asyncio.Future) -> None:
        try:
            await asyncio.wait_for(carga, 30)
        except asyncio.TimeoutError:
            self.informe.aviso("La página no disparó el evento load en 30 s; sigo igualmente.")
        await self.esperar_red(0.5, 10.0)

    async def navegar_paso(self, destino: str, base: str | None) -> dict:
        """Cambia de ruta como lo haría un usuario: un #hash dispara hashchange sin recargar, y una URL o ruta distinta carga el documento de nuevo."""
        destino = destino.strip()
        if destino.startswith("#"):
            await self.evaluar(f"location.hash = {json.dumps(destino)}; true")
            await self.asentar()
            return {"hash": destino}
        absoluta = re.match(r"^[a-z][a-z0-9+.-]*:", destino) is not None
        if not absoluta and base is None:
            raise ErrorPaso("navegar con una ruta relativa necesita un servidor; usa una URL completa o #/ruta.")
        completa = destino if absoluta else urllib.parse.urljoin(base, destino)
        actual = await self.evaluar("location.href")

        def sin_fragmento(u: str) -> str:
            return u.split("#", 1)[0]

        def fragmento(u: str) -> str:
            return u.split("#", 1)[1] if "#" in u else ""

        if sin_fragmento(actual) == sin_fragmento(completa):
            if fragmento(actual) != fragmento(completa):
                await self.evaluar(f"location.hash = {json.dumps('#' + fragmento(completa))}; true")
                await self.asentar()
                return {"hash": "#" + fragmento(completa)}
            carga = self.cdp.una_vez("Page.loadEventFired")
            await self.cdp.enviar("Page.reload", {"ignoreCache": True})
            await self._esperar_carga(carga)
            await self.asentar()
            return {"recargada": completa}
        await self.cargar(completa)
        return {"url": completa}

    # -- localización de elementos -----------------------------------------------------------------------------------
    async def esperar_elemento(self, selector: str, cuerpo_js: str, exigir=None, **extra) -> dict:
        """Repite la búsqueda hasta 5 s y, si no cumple, explica por qué: no existe, no es visible, está tapado o no se puede usar."""
        fin = time.monotonic() + ESPERA_SELECTOR_S
        ultimo: dict = {}
        while True:
            r = await self.evaluar(expresion(cuerpo_js, SEL=selector, **extra))
            if r.get("invalido"):
                raise ErrorPaso(f"El selector «{selector}» no es CSS válido: {r['invalido']}")
            ultimo = r
            if r.get("visibles", 0) > 0 and (exigir is None or exigir(r)):
                return r
            if time.monotonic() > fin:
                break
            await asyncio.sleep(0.1)
        if ultimo.get("total", 0) == 0:
            raise ErrorPaso(f"No existe ningún elemento que cumpla «{selector}» tras esperar {ESPERA_SELECTOR_S:.0f} s.")
        if ultimo.get("visibles", 0) == 0:
            raise ErrorPaso(f"«{selector}» existe ({ultimo['total']} elemento/s) pero ninguno es visible tras esperar {ESPERA_SELECTOR_S:.0f} s.")
        if ultimo.get("fuera"):
            raise ErrorPaso(f"«{selector}» ({ultimo.get('elemento')}) queda fuera de la ventana incluso tras hacer scroll.")
        if ultimo.get("tapado_por"):
            raise ErrorPaso(f"«{selector}» ({ultimo.get('elemento')}) está tapado por {ultimo['tapado_por']} en su punto central tras esperar {ESPERA_SELECTOR_S:.0f} s, así que un usuario no podría pulsarlo.")
        raise ErrorPaso(f"«{selector}» no llegó a estar listo tras esperar {ESPERA_SELECTOR_S:.0f} s ({ultimo}).")

    async def _mover_raton(self, x: float, y: float, tipo: str = "mouseMoved", pulsado: bool = False) -> None:
        params = {"type": tipo, "x": x, "y": y, "button": "left" if tipo != "mouseMoved" else "none",
                  "buttons": 1 if pulsado else 0, "clickCount": 1 if tipo != "mouseMoved" else 0}
        await self.cdp.enviar("Input.dispatchMouseEvent", params)

    # -- pasos de interacción ----------------------------------------------------------------------------------------
    async def click(self, selector: str) -> dict:
        r = await self.esperar_elemento(selector, JS_PUNTO, exigir=lambda r: r.get("libre"))
        await self._mover_raton(r["x"], r["y"])
        await self._mover_raton(r["x"], r["y"], "mousePressed", pulsado=True)
        await self._mover_raton(r["x"], r["y"], "mouseReleased")
        await self.asentar()
        return {"elemento": r["elemento"]}

    async def hover(self, selector: str) -> dict:
        r = await self.esperar_elemento(selector, JS_PUNTO, exigir=lambda r: r.get("libre"))
        await self._mover_raton(r["x"], r["y"])
        await self.asentar()
        return {"elemento": r["elemento"]}

    async def pulsar(self, texto: str) -> None:
        params = describir_tecla(texto)
        con_texto = "text" in params
        await self.cdp.enviar("Input.dispatchKeyEvent", {**params, "type": "keyDown" if con_texto else "rawKeyDown"})
        sin_texto = {k: v for k, v in params.items() if k not in ("text", "unmodifiedText", "commands")}
        await self.cdp.enviar("Input.dispatchKeyEvent", {**sin_texto, "type": "keyUp"})

    async def escribir(self, selector: str, texto: str) -> dict:
        r = await self.esperar_elemento(selector, JS_PREPARAR_ESCRITURA, exigir=lambda r: r.get("listo") or r.get("directo") or r.get("error"))
        if r.get("error"):
            raise ErrorPaso(f"No puedo escribir en «{selector}» ({r.get('elemento')}): {r['error']}.")
        if r.get("directo"):
            d = await self.evaluar(expresion(JS_ESCRIBIR_DIRECTO, SEL=selector, VALOR=texto))
            if not d.get("ok"):
                raise ErrorPaso(f"No puedo dar valor a «{selector}»: {d.get('motivo')}.")
        else:
            if r.get("valor"):
                await self.pulsar("Backspace")
                if await self.evaluar(expresion(JS_VALOR_ACTIVO)):
                    await self.evaluar(expresion(JS_VACIAR_ACTIVO))
            if texto:
                await self.cdp.enviar("Input.insertText", {"text": texto})
        await self.asentar()
        valor = await self.evaluar(expresion(JS_VALOR_FINAL, SEL=selector))
        return {"elemento": r.get("elemento"), "valor": recortar(valor if valor is not None else "", 200)}

    async def tecla(self, texto: str) -> dict:
        await self.pulsar(texto)
        await self.asentar()
        return {"tecla": texto}

    async def tab(self, veces: int) -> dict:
        for _ in range(veces):
            await self.pulsar("Tab")
            await asyncio.sleep(0.05)
        await self.asentar()
        foco = await self.evaluar(expresion(JS_FOCO))
        return {"foco": foco}

    async def esperar_selector(self, selector: str) -> dict:
        r = await self.esperar_elemento(selector, JS_CONTEO)
        return {"visibles": r["visibles"]}

    async def texto(self, selector: str) -> dict:
        fin = time.monotonic() + ESPERA_SELECTOR_S
        while True:
            r = await self.evaluar(expresion(JS_TEXTO, SEL=selector))
            if r.get("invalido"):
                raise ErrorPaso(f"El selector «{selector}» no es CSS válido: {r['invalido']}")
            if r.get("total", 0) > 0:
                break
            if time.monotonic() > fin:
                raise ErrorPaso(f"No existe ningún elemento que cumpla «{selector}» tras esperar {ESPERA_SELECTOR_S:.0f} s.")
            await asyncio.sleep(0.1)
        texto = r.get("texto", "").strip()
        self.informe.textos[clave_unica(self.informe.textos, selector)] = recortar(texto, LIMITE_RESULTADO_JS)
        return {"caracteres": len(texto)}

    async def existe(self, selector: str) -> dict:
        r = await self.evaluar(expresion(JS_CONTEO, SEL=selector))
        if r.get("invalido"):
            raise ErrorPaso(f"El selector «{selector}» no es CSS válido: {r['invalido']}")
        self.informe.existe[clave_unica(self.informe.existe, selector)] = r["total"] > 0
        return {"total": r["total"], "visibles": r["visibles"]}

    async def js(self, codigo: str) -> dict:
        try:
            r = await self._evaluar_en_bruto({"expression": codigo, "returnByValue": True, "awaitPromise": True, "userGesture": True}, 30)
        except ErrorCDP as e:
            if "reference chain" not in str(e) and "serializ" not in str(e).lower():
                raise
            r = await self._evaluar_en_bruto({"expression": codigo, "returnByValue": False, "awaitPromise": True, "userGesture": True}, 30)
            r["result"] = {"value": r.get("result", {}).get("description")}
        if "exceptionDetails" in r:
            d = r["exceptionDetails"]
            exc = d.get("exception", {})
            raise ErrorPaso(f"La expresión lanzó una excepción: {recortar(exc.get('description') or d.get('text') or 'sin detalle', 600)}")
        valor = r.get("result", {}).get("value")
        serializado = json.dumps(valor, ensure_ascii=False, default=str)
        if len(serializado) > LIMITE_RESULTADO_JS:
            valor = serializado[:LIMITE_RESULTADO_JS] + f"… [recortado, {len(serializado)} caracteres]"
        self.informe.resultados_js[clave_unica(self.informe.resultados_js, codigo)] = valor
        await self._vigilar_desbordamiento()
        return {}

    async def scroll(self, selector: str) -> dict:
        r = await self.esperar_elemento(selector, JS_SCROLL)
        await self.asentar()
        return {"elemento": r.get("elemento")}

    async def viewport(self, ancho: int, alto: int) -> dict:
        self.ancho, self.alto = ancho, alto
        await self._aplicar_viewport(ancho, alto)
        await self.asentar()
        return {"ventana": f"{ancho}x{alto}"}

    async def cambiar_tema(self, tema: str) -> dict:
        self.tema = tema
        await self._aplicar_medios()
        await self.asentar()
        return {"tema": tema}

    # -- capturas -----------------------------------------------------------------------------------------------------
    async def _tomar(self, ruta: Path, clip: dict | None = None) -> None:
        formato = {".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp"}.get(ruta.suffix.lower(), "png")
        params: dict = {"format": formato}
        if formato != "png":
            params["quality"] = 90
        if clip:
            params["clip"] = {**clip, "scale": 1}
            params["captureBeyondViewport"] = True
        r = await self.cdp.enviar("Page.captureScreenshot", params, timeout=45)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(base64.b64decode(r["data"]))

    async def captura(self, ruta: Path, completa: bool) -> str:
        """Captura la ventana o, con completa, la página entera: amplía temporalmente la ventana hasta que no quede nada por desplazar, también dentro de contenedores con scroll propio."""
        ampliada = False
        try:
            if completa:
                ampliada = await self._ampliar_a_contenido()
            await self._tomar(ruta)
        finally:
            if ampliada:
                await self._aplicar_viewport(self.ancho, self.alto)
        self.informe.capturas.append(posix(ruta))
        return posix(ruta)

    async def _ampliar_a_contenido(self) -> bool:
        alto = self.alto
        for _ in range(3):
            m = await self.evaluar(expresion(JS_MEDIR))
            extra = max(m["documento"], m["interno"])
            if extra <= 1:
                break
            nuevo = min(alto + extra, ALTO_MAXIMO_CAPTURA)
            if nuevo <= alto:
                self.informe.aviso(f"El contenido supera {ALTO_MAXIMO_CAPTURA} px de alto y la captura completa se recorta ahí.")
                break
            alto = nuevo
            await self._aplicar_viewport(self.ancho, alto)
            await self.asentar(0.15)
        return alto != self.alto

    async def captura_elemento(self, selector: str, ruta: Path) -> str:
        ampliada = False
        try:
            r = await self.esperar_elemento(selector, JS_RECTANGULO)
            if r["rect"]["alto"] > self.alto - 8:
                alto = min(int(r["rect"]["alto"]) + 48 + self.alto // 4, ALTO_MAXIMO_CAPTURA)
                await self._aplicar_viewport(self.ancho, alto)
                ampliada = True
                await self.asentar(0.15)
                r = await self.esperar_elemento(selector, JS_RECTANGULO)
            rect = r["rect"]
            if rect["ancho"] < 1 or rect["alto"] < 1:
                raise ErrorPaso(f"«{selector}» no tiene tamaño que capturar.")
            await self._tomar(ruta, {"x": rect["x"], "y": rect["y"], "width": rect["ancho"], "height": rect["alto"]})
        finally:
            if ampliada:
                await self._aplicar_viewport(self.ancho, self.alto)
        self.informe.capturas.append(posix(ruta))
        return posix(ruta)

    async def captura_diagnostico(self) -> str | None:
        """Tras un paso fallido deja una captura de lo que había en pantalla, junto a la de salida o en la carpeta temporal de diagnósticos."""
        self.diagnosticos += 1
        try:
            if self.args.salida:
                base = ruta_local(self.args.salida)
                ruta = base.with_name(f"{base.stem}.diagnostico-{self.diagnosticos}.png")
            else:
                ruta = Path(tempfile.gettempdir()) / CARPETA_DIAGNOSTICOS / f"diagnostico-{os.getpid()}-{self.diagnosticos}.png"
            await self._tomar(ruta)
            self.informe.capturas_diagnostico.append(posix(ruta))
            return posix(ruta)
        except Exception as e:
            trazar(f"no se pudo tomar la captura de diagnóstico: {e}")
            return None

    # -- despacho -----------------------------------------------------------------------------------------------------
    async def ejecutar(self, paso: Paso, base: str | None) -> dict | None:
        n = paso.nombre
        if n == "click":
            return await self.click(paso.selector)
        if n == "hover":
            return await self.hover(paso.selector)
        if n == "escribir":
            return await self.escribir(paso.selector, paso.valor)
        if n == "tecla":
            return await self.tecla(paso.arg)
        if n == "esperar":
            await asyncio.sleep(min(int(paso.arg), 60000) / 1000)
            return None
        if n == "esperar-selector":
            return await self.esperar_selector(paso.selector)
        if n == "captura":
            return {"ruta": await self.captura(ruta_local(paso.arg.strip()), self.args.pagina_completa)}
        if n == "captura-elemento":
            return {"ruta": await self.captura_elemento(paso.selector, ruta_local(paso.valor.strip()))}
        if n == "texto":
            return await self.texto(paso.selector)
        if n == "existe":
            return await self.existe(paso.selector)
        if n == "js":
            return await self.js(paso.arg)
        if n == "scroll":
            return await self.scroll(paso.selector)
        if n == "viewport":
            ancho, alto = re.split(r"[xX×]", paso.arg.strip())
            return await self.viewport(int(ancho), int(alto))
        if n == "tema":
            return await self.cambiar_tema(paso.arg.strip().lower())
        if n == "navegar":
            return await self.navegar_paso(paso.arg, base)
        if n == "tab":
            return await self.tab(int(paso.arg))
        raise ErrorPaso(f"Paso sin implementar: {n}")


# ---------------------------------------------------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------------------------------------------------

def normalizar_base(url: str) -> str:
    if not re.match(r"^https?://", url):
        raise ErrorUso(f"--servidor necesita una URL completa como http://127.0.0.1:8000 y recibí «{url}».")
    return url.rstrip("/") + "/"


def resolver_url(args, base: str | None) -> str:
    """Convierte --ruta (relativa a la raíz del servidor) o --url (completa) en la dirección que abrirá Chrome."""
    if args.url:
        return args.url
    ruta = args.ruta if args.ruta is not None else "#/hoy"
    if re.match(r"^[a-z][a-z0-9+.-]*:", ruta):
        return ruta
    if base is None:
        raise ErrorUso("Con --sin-servidor hace falta --url, porque --ruta es relativa a la raíz de un servidor.")
    return urllib.parse.urljoin(base, ruta)


async def ejecutar_pasos(pagina: Pagina, pasos: list[Paso], base: str | None, informe: Informe, continuar: bool) -> None:
    roto = False
    for numero, paso in enumerate(pasos, 1):
        registro: dict = {"n": numero, "paso": paso.texto}
        if roto:
            registro.update(ok=None, omitido=True)
            informe.pasos.append(registro)
            continue
        informe.paso_actual = paso.texto
        inicio = time.monotonic()
        try:
            detalle = await pagina.ejecutar(paso, base)
            registro["ok"] = True
            if detalle:
                registro["detalle"] = detalle
        except ErrorPaso as e:
            registro["ok"] = False
            registro["error"] = str(e)
            registro["diagnostico"] = await pagina.captura_diagnostico()
            roto = not continuar
        except ErrorCDP as e:
            registro["ok"] = False
            registro["error"] = f"Chrome rechazó el comando: {e}"
            registro["diagnostico"] = await pagina.captura_diagnostico()
            roto = not continuar
        registro["ms"] = int((time.monotonic() - inicio) * 1000)
        informe.pasos.append(registro)
        trazar(f"paso {numero} {paso.texto!r}: {'ok' if registro['ok'] else registro.get('error', 'omitido')}")
    informe.paso_actual = None


async def trabajo(args, pasos: list[Paso], informe: Informe, limpieza: Limpieza) -> None:
    tmp = Path(tempfile.mkdtemp(prefix=f"{PREFIJO_TMP}{os.getpid()}_"))
    limpieza.directorio(tmp)
    barrer_restos()
    propio = not args.sin_servidor and not args.servidor
    base: str | None = None
    if args.servidor:
        base = normalizar_base(args.servidor)
    tareas = [asyncio.ensure_future(lanzar_chrome(tmp, args, limpieza, informe))]
    if propio:
        tareas.append(asyncio.ensure_future(arrancar_servidor(tmp, limpieza, informe)))
    elif args.servidor:
        tareas.append(asyncio.ensure_future(esperar_estado(base, None, None, 10)))
    resultados = await asyncio.gather(*tareas, return_exceptions=True)
    for r in resultados:
        if isinstance(r, BaseException):
            raise r
    puerto_devtools, _chrome = resultados[0]
    if propio:
        base = resultados[1]
    elif args.servidor:
        informe.servidor = {"url": base, "propio": False}
    else:
        informe.servidor = {"modo": "sin servidor"}
    if base:
        await sembrar(base, args.semilla, informe)
    url = resolver_url(args, base)
    informe.url = url

    destino = await objetivo_de_pagina(puerto_devtools, informe)
    cdp = await ClienteCDP.conectar(destino)
    try:
        recolector = Recolector(informe, list(args.permitir_404) + ["/favicon.ico"])
        recolector.cdp = cdp
        cdp.oyentes.append(recolector)
        pagina = Pagina(cdp, recolector, informe, args)
        await pagina.iniciar()
        await pagina.cargar(url)
        await ejecutar_pasos(pagina, pasos, base, informe, args.continuar_tras_fallo)
        if args.salida:
            await pagina.captura(ruta_local(args.salida), args.pagina_completa)
    finally:
        await cdp.cerrar()
        if propio:
            if any((f.get("estado") or 0) >= 500 for f in informe.peticiones_fallidas):
                await asyncio.sleep(0.5)  # uvicorn escribe el traceback unos milisegundos después de enviar el 500
            informe.log_servidor = leer_cola(tmp / "servidor.log") or None


# ---------------------------------------------------------------------------------------------------------------------
# Línea de comandos
# ---------------------------------------------------------------------------------------------------------------------

_TRADUCCIONES = {
    "usage: ": "uso: ", "options": "opciones", "show this help message and exit": "muestra esta ayuda y termina",
    "unrecognized arguments: %s": "argumentos no reconocidos: %s", "the following arguments are required: %s": "faltan estos argumentos: %s",
    "expected one argument": "falta el valor de la opción", "%(prog)s: error: %(message)s\n": "%(prog)s: error de uso: %(message)s\n",
    "argument %(argument_name)s: %(message)s": "opción %(argument_name)s: %(message)s",
    "invalid choice: %(value)r (choose from %(choices)s)": "valor no válido %(value)r (elige entre %(choices)s)",
    "invalid %(type)s value: %(value)r": "valor no válido para %(type)s: %(value)r",
}


def _traducir(texto: str) -> str:
    return _TRADUCCIONES.get(texto, texto)


def _entero(minimo: int, maximo: int):
    def convertir(texto: str) -> int:
        try:
            valor = int(texto)
        except ValueError:
            raise argparse.ArgumentTypeError(f"«{texto}» no es un número entero") from None
        if not minimo <= valor <= maximo:
            raise argparse.ArgumentTypeError(f"debe estar entre {minimo} y {maximo}")
        return valor
    return convertir


def construir_parser() -> argparse.ArgumentParser:
    argparse._ = _traducir  # así los mensajes propios de argparse salen en español
    p = argparse.ArgumentParser(
        prog="captura.py", add_help=False, formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Abre la interfaz del hub en un Chrome headless propio, ejecuta pasos de interacción, hace capturas e imprime un informe JSON.",
        epilog=("Pasos (--paso, repetible): click:SEL | hover:SEL | escribir:SEL=TEXTO | tecla:Enter | esperar:MS | esperar-selector:SEL |\n"
                "captura:RUTA.png | captura-elemento:SEL=RUTA.png | texto:SEL | existe:SEL | js:EXPRESION | scroll:SEL | viewport:ANCHOxALTO |\n"
                "tema:claro|oscuro | navegar:#/ruta | tab:N. Un selector admite el filtro final :texto(\"...\") para elegir por el texto visible.\n"
                "Códigos de salida: 0 sin errores, 1 con errores en la página o en un paso, 2 si falla el entorno. Guía completa en design/VERIFICAR.md."))
    p.add_argument("-h", "--help", "--ayuda", action="help", help="muestra esta ayuda y termina")
    p.add_argument("--ruta", default=None, help="ruta relativa a la raíz del servidor, con o sin # (por defecto #/hoy)")
    p.add_argument("--url", default=None, help="URL completa en lugar de --ruta")
    p.add_argument("--salida", default=None, help="PNG de la captura final (se crean las carpetas que falten)")
    p.add_argument("--ancho", type=_entero(200, 5000), default=1440, help="ancho de la ventana en px (1440)")
    p.add_argument("--alto", type=_entero(200, 5000), default=900, help="alto de la ventana en px (900)")
    p.add_argument("--tema", choices=("claro", "oscuro"), default="claro", help="emula prefers-color-scheme (claro)")
    p.add_argument("--movimiento-reducido", action="store_true", help="emula prefers-reduced-motion: reduce")
    p.add_argument("--pagina-completa", action="store_true", help="las capturas de página incluyen todo el contenido desplazable")
    p.add_argument("--paso", action="append", default=[], metavar="PASO", help="paso de interacción, repetible (ver abajo)")
    p.add_argument("--pasos-json", default=None, metavar="FICHERO", help="fichero JSON con una lista de pasos como cadenas; corren antes que los --paso")
    p.add_argument("--esperar-ms", type=_entero(0, 60000), default=600, help="espera extra tras la carga y la calma de red (600)")
    p.add_argument("--timeout", type=_entero(5, 3600), default=90, help="tiempo máximo de toda la ejecución en segundos (90)")
    p.add_argument("--permitir-errores", action="store_true", help="el informe cuenta los errores de página pero el código de salida es 0")
    p.add_argument("--permitir-404", action="append", default=[], metavar="RUTA", help="prefijo de ruta cuyo 404 no cuenta como fallo, repetible")
    p.add_argument("--semilla", choices=("ninguna", "vacia", "basica", "completa", "demo"), default="completa", help="datos de demo antes de abrir (completa; demo añade relleno)")
    p.add_argument("--servidor", default=None, metavar="URL", help="reutiliza un servidor ya arrancado en lugar de lanzar uno")
    p.add_argument("--sin-servidor", action="store_true", help="no arranca servidor ni siembra (para --url externas o data:)")
    p.add_argument("--continuar-tras-fallo", action="store_true", help="tras un paso fallido sigue con los demás en lugar de omitirlos")
    p.add_argument("--verboso", action="store_true", help="trazas del propio script por stderr")
    return p


def preparar_pasos(args) -> list[Paso]:
    textos: list[str] = []
    if args.pasos_json:
        ruta = ruta_local(args.pasos_json)
        try:
            lista = json.loads(ruta.read_text(encoding="utf-8-sig"))
        except OSError as e:
            raise ErrorUso(f"No puedo leer --pasos-json {ruta}: {e}") from e
        except ValueError as e:
            raise ErrorUso(f"El fichero {ruta} no es JSON válido: {e}") from e
        if not isinstance(lista, list) or not all(isinstance(x, str) for x in lista):
            raise ErrorUso(f"El fichero {ruta} debe contener una lista JSON de cadenas, una por paso.")
        textos += lista
    textos += args.paso
    return [parsear_paso(t) for t in textos]


def validar_argumentos(args) -> None:
    if args.ruta is not None and args.url:
        raise ErrorUso("Usa --ruta o --url, pero no las dos a la vez.")
    if args.servidor and args.sin_servidor:
        raise ErrorUso("--servidor y --sin-servidor se excluyen entre sí.")
    if args.servidor:
        normalizar_base(args.servidor)
    if args.sin_servidor:
        resolver_url(args, None)


def main(argv: list[str] | None = None) -> int:
    global VERBOSO
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = construir_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    VERBOSO = args.verboso
    if args.ruta:
        args.ruta = deshacer_msys(args.ruta)
    args.permitir_404 = [deshacer_msys(x) for x in args.permitir_404]
    args.paso = [x if x.strip().lower().startswith("captura") else deshacer_msys(x) for x in args.paso]
    informe = Informe(args.permitir_errores)
    limpieza = Limpieza()
    atexit.register(limpieza.ejecutar)
    vigilante = None
    codigo = 2
    try:
        validar_argumentos(args)
        pasos = preparar_pasos(args)
        proteger_con_job_object()

        def al_cortar(_numero, _marco):
            raise KeyboardInterrupt

        for nombre in ("SIGBREAK", "SIGTERM"):
            senal = getattr(signal, nombre, None)
            if senal is not None:
                try:
                    signal.signal(senal, al_cortar)
                except (ValueError, OSError):
                    pass

        def emergencia():
            informe.error = informe.error or f"El script no terminó ni siquiera tras el aviso de tiempo ({args.timeout + 25} s) y se cortó por la fuerza."
            try:
                limpieza.ejecutar()
            finally:
                informe.imprimir(2)
                os._exit(2)

        vigilante = threading.Timer(args.timeout + 25, emergencia)
        vigilante.daemon = True
        vigilante.start()
        try:
            asyncio.run(asyncio.wait_for(trabajo(args, pasos, informe, limpieza), args.timeout))
        except asyncio.TimeoutError:
            ultimo = f" Último paso en curso: {informe.paso_actual}." if informe.paso_actual else ""
            informe.error = f"Tiempo agotado: la ejecución superó --timeout {args.timeout} s.{ultimo}"
    except ErrorUso as e:
        informe.error = str(e)
    except ErrorEntorno as e:
        informe.error = str(e)
    except ErrorCDP as e:
        informe.error = f"Chrome rechazó un comando de DevTools: {e}"
    except KeyboardInterrupt:
        informe.error = "Interrumpido por el usuario (Ctrl+C) antes de terminar."
    except Exception as e:
        informe.error = f"Fallo inesperado del script: {type(e).__name__}: {e}"
        aviso_stderr(traceback.format_exc())
    finally:
        if vigilante is not None:
            vigilante.cancel()
        limpieza.ejecutar()
    if informe.error:
        aviso_stderr(informe.error)
    codigo = informe.codigo_salida()
    informe.imprimir(codigo)
    return codigo


if __name__ == "__main__":
    sys.exit(main())
