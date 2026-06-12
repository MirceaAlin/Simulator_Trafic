"""
Date despre traseele predefinite din Cluj-Napoca folosite în
aplicația de simulare a traficului.

Toate cele trei trasee converg spre Centrul Clujului (Piața Unirii),
modelând fluxurile reale de trafic dinspre periferie spre centru:
    - dinspre sud   (Calea Turzii)
    - dinspre vest  (Vivo Mall / Florești)
    - dinspre est   (Iulius Mall / Gheorgheni)

Coordonatele start/end sunt repere; geometria exactă a drumului este
obținută în frontend prin OSRM (router.project-osrm.org), iar lungimea
reală a rutei recalculate înlocuiește valoarea `lungime_m` de mai jos
(care servește doar ca fallback).
"""

# Centrul Clujului — punct comun de sosire al celor trei trasee
CENTRU = [46.772583, 23.595361]

TRASEE = {
    "calea_turzii": {
        "nume": "Calea Turzii - Centru",
        "descriere": "Intrarea în oraș dinspre sud, pe Calea Turzii, până în centru.",
        "start": [46.743417, 23.592194],   # Calea Turzii (sud)
        "end":   CENTRU,                    # Centru
        "viteza_limita_kmh": 50,
        "culoare": "#3388ff",
        "lungime_m": 3500,
    },
    "vivo_centru": {
        "nume": "Vivo Mall - Centru",
        "descriere": "Dinspre vest (Florești/Vivo Mall), prin Mănăștur, până în centru.",
        "start": [46.753722, 23.531472],   # Vivo Mall (Florești)
        "end":   CENTRU,                    # Centru
        "viteza_limita_kmh": 50,
        "culoare": "#ff8833",
        "lungime_m": 7000,
    },
    "iulius_centru": {
        "nume": "Iulius Mall - Centru",
        "descriere": "Dinspre est (Gheorgheni/Iulius Mall), pe direcția est-vest, până în centru.",
        "start": [46.771528, 23.625306],   # Iulius Mall (Gheorgheni)
        "end":   CENTRU,                    # Centru
        "viteza_limita_kmh": 50,
        "culoare": "#33cc33",
        "lungime_m": 3600,
    },
}


def get_lista_trasee():
    """Returnează lista cu informații sumare ale tuturor traseelor."""
    return [
        {
            "id":                id_t,
            "nume":              date["nume"],
            "descriere":         date["descriere"],
            "start":             date["start"],
            "end":               date["end"],
            "viteza_limita_kmh": date["viteza_limita_kmh"],
            "culoare":           date["culoare"],
            "lungime_m":         date["lungime_m"],
        }
        for id_t, date in TRASEE.items()
    ]
