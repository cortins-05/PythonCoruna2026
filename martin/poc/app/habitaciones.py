"""Vista del día por habitación: quién duerme en cada una, quién llega hoy y quién sale.

Une las estancias del sistema (RoomCloud, recepción y mensajes confirmados) con las de OfiHotel que no tienen reserva de canal. OfiHotel no da
números de habitación fiables para todo, así que la asignación a un número es de la aplicación: es estable (mismo orden siempre) y respeta el
inventario por tipo de `fixtures/habitaciones.json`.
"""
from . import disponibilidad, prioridades

NUMEROS = {"SGL-STD": [101, 102], "DBL-STD": [201, 202, 203], "TPL-STD": [301, 302, 303], "FAM-STD": [401, 402], "SUI-STD": [501, 502]}


def _estancias_del_dia(db: dict, dia: str) -> list[dict]:
    from . import estados
    salida, refs = [], set()
    for exp in db["expedientes"].values():
        refs.add(exp["referencia"])
        if exp["estado"] in ("cancelada", "cerrado") or not (exp["checkin_prevista"] <= dia <= exp["checkout_prevista"]):
            continue
        for h in exp["habitaciones"]:
            salida.append({"id": exp["id"], "nombre": estados.nombre_de(exp), "tipo": h["tipo"], "desde": exp["checkin_prevista"],
                           "hasta": exp["checkout_prevista"], "origen": prioridades.grupo_de_origen(exp["origen"]), "en_casa": exp["estado"] == "en_curso"})
    for f in db.get("ofihotel", {}).get("ocupaciones", []):
        if (f.get("ref_externa") and f["ref_externa"] in refs) or not (f["desde"] <= dia <= f["hasta"]):
            continue
        salida.append({"id": None, "nombre": f["huesped"], "tipo": f["tipo"], "desde": f["desde"], "hasta": f["hasta"], "origen": "ofihotel",
                       "en_casa": f["desde"] < dia})
    return sorted(salida, key=lambda s: (s["desde"], s["nombre"]))


def vista(store, dia: str | None = None) -> dict:
    db = store.db
    dia = dia or store.ahora().date().isoformat()
    estancias = _estancias_del_dia(db, dia)
    habitaciones = {tipo: [{"numero": n, "tipo": tipo, "noche": None, "sale": None} for n in numeros] for tipo, numeros in NUMEROS.items()}
    for s in (x for x in estancias if x["desde"] <= dia < x["hasta"]):
        sitio = next((h for h in habitaciones.get(s["tipo"], []) if h["noche"] is None), None)
        if sitio:
            sitio["noche"] = {**s, "estado": "en_casa" if s["en_casa"] or s["desde"] < dia else "llega_hoy"}
    for s in (x for x in estancias if x["hasta"] == dia):
        lista = habitaciones.get(s["tipo"], [])
        sitio = next((h for h in lista if h["noche"] is None and h["sale"] is None), None) or next((h for h in lista if h["sale"] is None), None)
        if sitio:
            sitio["sale"] = {**s, "estado": "sale_hoy"}
    todas = [h for lista in habitaciones.values() for h in lista]
    return {"fecha": dia, "habitaciones": todas,
            "resumen": {"habitaciones": len(todas), "ocupadas": sum(1 for h in todas if h["noche"]), "libres": sum(1 for h in todas if not h["noche"]),
                        "llegan": sum(1 for h in todas if h["noche"] and h["noche"]["estado"] == "llega_hoy"), "salen": sum(1 for h in todas if h["sale"])}}
