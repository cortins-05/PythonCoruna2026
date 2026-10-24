"""Comprueba los contrastes de los tokens de color (WCAG 2.2) en el tema claro y en el oscuro.

Uso: python scripts/contraste.py
Sale con código 1 si algún par de texto no llega a 4,5:1 o algún borde de control o foco no llega a 3:1.
"""
import re
import sys
from pathlib import Path

RUTA = Path(__file__).resolve().parents[1] / "app" / "static" / "css" / "tokens.css"
TONOS = ["ok", "aviso", "critico", "info", "neutro"]


def bloque(css: str, inicio: str) -> dict:
    i = css.index(inicio)
    abre = css.index("{", i)
    cierra = css.index("}", abre)
    return dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", css[abre:cierra]))


def a_rgb(valor: str, fondo=None):
    valor = valor.strip()
    if valor.startswith("#"):
        h = valor[1:]
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    m = re.match(r"rgba?\(([^)]+)\)", valor)
    partes = [float(p) for p in m.group(1).split(",")]
    r, g, b = partes[:3]
    if len(partes) == 4 and fondo is not None:
        a = partes[3]
        return tuple(round(a * c + (1 - a) * f) for c, f in zip((r, g, b), fondo))
    return (r, g, b)


def luminancia(rgb) -> float:
    def lin(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b) -> float:
    la, lb = luminancia(a), luminancia(b)
    claro, oscuro = max(la, lb), min(la, lb)
    return (claro + 0.05) / (oscuro + 0.05)


def pares(t: dict):
    c = lambda k, f=None: a_rgb(t[k], f)  # noqa: E731
    fondos = ["--c-bg", "--c-surface", "--c-surface-2", "--c-surface-3"]
    for f in fondos:
        yield "texto", 4.5, c("--c-texto"), c(f), f"texto sobre {f}"
        yield "texto-2", 4.5, c("--c-texto-2"), c(f), f"texto-2 sobre {f}"
        yield "texto-3", 4.5, c("--c-texto-3"), c(f), f"texto-3 sobre {f}"
    yield "enlace", 4.5, c("--c-enlace"), c("--c-surface"), "enlace sobre surface"
    yield "enlace", 4.5, c("--c-enlace"), c("--c-bg"), "enlace sobre bg"
    yield "acento", 4.5, c("--c-acento-texto"), c("--c-acento"), "texto sobre acento"
    yield "acento", 4.5, c("--c-acento-texto"), c("--c-acento-hover"), "texto sobre acento hover"
    yield "cta", 4.5, c("--c-cta-texto"), c("--c-cta"), "texto sobre cta"
    yield "cta", 4.5, c("--c-cta-texto"), c("--c-cta-hover"), "texto sobre cta hover"
    yield "fuerte", 4.5, c("--c-fuerte-texto"), c("--c-fuerte"), "texto sobre fuerte"
    yield "fuerte", 4.5, c("--c-fuerte-texto"), c("--c-fuerte-hover"), "texto sobre fuerte hover"
    yield "acento-suave", 4.5, c("--c-texto"), c("--c-acento-suave"), "texto sobre acento suave"
    yield "menta", 4.5, c("--c-texto"), c("--c-menta"), "texto sobre menta"
    yield "menta", 4.5, c("--c-texto-2"), c("--c-menta"), "texto-2 sobre menta"
    for tono in TONOS:
        yield f"tono {tono}", 4.5, c(f"--c-{tono}-texto"), c(f"--c-{tono}-bg"), f"texto del tono {tono}"
        yield f"punto {tono}", 3.0, c(f"--c-{tono}-punto"), c(f"--c-{tono}-bg"), f"punto del tono {tono}"
    for fondo in ("--c-bg", "--c-surface"):
        base = c(fondo)
        menu = a_rgb(t["--c-menu"], base)
        yield "menú", 4.5, c("--c-menu-texto"), menu, f"texto del menú sobre {fondo}"
        yield "menú", 4.5, c("--c-menu-texto-2"), menu, f"texto 2 del menú sobre {fondo}"
    yield "control", 3.0, c("--c-borde-control"), c("--c-surface"), "borde de control sobre surface"
    yield "control", 3.0, c("--c-borde-control"), c("--c-bg"), "borde de control sobre bg"
    yield "foco", 3.0, c("--c-enlace"), c("--c-surface"), "anillo de foco sobre surface"


def main() -> int:
    css = RUTA.read_text(encoding="utf-8")
    claro = bloque(css, ":root {")
    oscuro = dict(claro)
    oscuro.update(bloque(css, ':root[data-tema="oscuro"]'))
    fallos = 0
    for nombre, tema in (("claro", claro), ("oscuro", oscuro)):
        print(f"== Tema {nombre}")
        for _, minimo, fg, bg, desc in pares(tema):
            r = ratio(fg, bg)
            marca = "ok " if r >= minimo else "MAL"
            if r < minimo:
                fallos += 1
            print(f"  {marca} {r:5.2f}:1 (mínimo {minimo}) {desc}")
    print(f"\n{fallos} par(es) por debajo del mínimo")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
