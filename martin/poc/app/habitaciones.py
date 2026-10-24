"""Habitaciones: a cada estancia se le asigna un número que conserva durante toda su estancia, y la vista del día dice quién hay en cada una.

Une las estancias del sistema (RoomCloud, recepción y mensajes confirmados) con las de OfiHotel que no tienen reserva de canal. OfiHotel no da
números de habitación fiables para todo, así que la asignación es de la aplicación: estable (mismo orden siempre) y respeta el inventario por
tipo. Se reparten por orden de llegada y una habitación se reutiliza el mismo día en que sale su huésped.
"""
from . import prioridades

NUMEROS = {"SGL-STD": [101, 102], "DBL-STD": [201, 202, 203], "TPL-STD": [301, 302, 303], "FAM-STD": [401, 402], "SUI-STD": [501, 502]}


def _estancias(db: dict) -> list[dict]:
    from . import estados
    salida, refs = [], set()
    for exp in db["expedientes"].values():
        refs.add(exp["referencia"])
        if exp["estado"] in ("cancelada", "cerrado"):
            continue
        for i, h in enumerate(exp["habitaciones"]):
            salida.append({"clave": f"{exp['id']}#{i}", "id": exp["id"], "nombre": estados.nombre_de(exp), "tipo": h["tipo"], "desde": exp["checkin_prevista"],
                           "hasta": exp["checkout_prevista"], "origen": prioridades.grupo_de_origen(exp["origen"]), "en_casa": exp["estado"] == "en_curso"})
    for n, f in enumerate(db.get("ofihotel", {}).get("ocupaciones", [])):
        if f.get("ref_externa") and f["ref_externa"] in refs:
            continue
        salida.append({"clave": f"oh#{n}", "id": None, "nombre": f["huesped"], "tipo": f["tipo"], "desde": f["desde"], "hasta": f["hasta"],
                       "origen": "ofihotel", "en_casa": False})
    return sorted(salida, key=lambda s: (s["desde"], s["hasta"], s["nombre"], s["clave"]))


def asignar(db: dict) -> tuple[list[dict], dict[str, int | None]]:
    """Devuelve las estancias y {clave: número}. Primero van las habitaciones fijadas por recepción (`habitacion_fija`) y después el reparto automático.

    Si un tipo está en overbooking, la estancia sobrante queda sin número (None)."""
    estancias = _estancias(db)
    ocupadas: dict[int, list[tuple[str, str]]] = {n: [] for numeros in NUMEROS.values() for n in numeros}
    asignadas: dict[str, int | None] = {}

    def libre(n: int, desde: str, hasta: str) -> bool:
        return all(hasta <= d or h <= desde for d, h in ocupadas[n])

    for s in estancias:
        fija = db["expedientes"].get(s["id"] or "", {}).get("habitacion_fija") if s["clave"].endswith("#0") else None
        if fija in ocupadas and fija in NUMEROS.get(s["tipo"], []) and libre(fija, s["desde"], s["hasta"]):
            ocupadas[fija].append((s["desde"], s["hasta"]))
            asignadas[s["clave"]] = fija
    for s in estancias:
        if s["clave"] in asignadas:
            continue
        sitio = next((n for n in NUMEROS.get(s["tipo"], []) if libre(n, s["desde"], s["hasta"])), None)
        if sitio is not None:
            ocupadas[sitio].append((s["desde"], s["hasta"]))
        asignadas[s["clave"]] = sitio
    return estancias, asignadas


def habitacion_de(db: dict, exp_id: str) -> int | None:
    """Número de la primera habitación de una estancia del sistema."""
    _, asignadas = asignar(db)
    return asignadas.get(f"{exp_id}#0")


def vista(store, dia: str | None = None) -> dict:
    db = store.db
    dia = dia or store.ahora().date().isoformat()
    estancias, asignadas = asignar(db)
    habitaciones = {n: {"numero": n, "tipo": tipo, "noche": None, "sale": None} for tipo, numeros in NUMEROS.items() for n in numeros}
    for s in estancias:
        n = asignadas[s["clave"]]
        if n is None:
            continue
        if s["desde"] <= dia < s["hasta"]:
            habitaciones[n]["noche"] = {**s, "habitacion": n, "estado": "en_casa" if s["en_casa"] or s["desde"] < dia else "llega_hoy"}
        elif s["hasta"] == dia:
            habitaciones[n]["sale"] = {**s, "habitacion": n, "estado": "sale_hoy"}
    todas = list(habitaciones.values())
    return {"fecha": dia, "habitaciones": todas,
            "resumen": {"habitaciones": len(todas), "ocupadas": sum(1 for h in todas if h["noche"]), "libres": sum(1 for h in todas if not h["noche"]),
                        "llegan": sum(1 for h in todas if h["noche"] and h["noche"]["estado"] == "llega_hoy"), "salen": sum(1 for h in todas if h["sale"])}}


def quien_ocupa(store, numero: int, dia: str | None = None) -> dict | None:
    """La ficha de una habitación un día: tipo, quién duerme y quién sale. None si el número no existe."""
    for h in vista(store, dia)["habitaciones"]:
        if h["numero"] == numero:
            return h
    return None
