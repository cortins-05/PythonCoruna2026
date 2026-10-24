"""Genera fixtures/dni_muestra.png: un documento ficticio para probar el OCR en vivo.
Los datos son inventados (el 12345678Z es el DNI de ejemplo que cumple la letra de control)."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SALIDA = Path(__file__).resolve().parents[1] / "fixtures" / "dni_muestra.png"


def fuente(tam: int):
    for ruta in ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf"):
        try:
            return ImageFont.truetype(ruta, tam)
        except OSError:
            continue
    return ImageFont.load_default()


lienzo = Image.new("RGB", (860, 540), "#dfe8f2")
d = ImageDraw.Draw(lienzo)
d.rectangle((10, 10, 850, 530), outline="#1f4e79", width=4)
d.text((30, 24), "ESPAÑA · DOCUMENTO NACIONAL DE IDENTIDAD", font=fuente(26), fill="#1f4e79")
d.text((30, 64), "MUESTRA · DOCUMENTO FICTICIO · NO VÁLIDO", font=fuente(20), fill="#a12d1b")
filas = [("APELLIDOS", "PEREIRA LAGE"), ("NOMBRE", "ANA"), ("SEXO", "M"), ("NACIONALIDAD", "ESP"),
         ("FECHA DE NACIMIENTO", "17 04 1988"), ("DNI", "12345678Z"), ("Nº SOPORTE", "BAB123456"),
         ("DOMICILIO", "RÚA DO ORZÁN 12, 3º B"), ("LOCALIDAD", "A CORUÑA (15003)")]
y = 110
for etiqueta, valor in filas:
    d.text((30, y), etiqueta, font=fuente(16), fill="#55625a")
    d.text((260, y - 4), valor, font=fuente(28), fill="#10201a")
    y += 48
lienzo.save(SALIDA)
print("Escrito", SALIDA)
