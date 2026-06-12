"""Conversii de unitati si generare de ID-uri de sesiune."""

import uuid


def ms_to_kmh(v_ms: float) -> float:
    """m/s -> km/h."""
    return v_ms * 3.6


def kmh_to_ms(v_kmh: float) -> float:
    """km/h -> m/s."""
    return v_kmh / 3.6


def m_to_km(d_m: float) -> float:
    """metri -> kilometri."""
    return d_m / 1000.0


def genereaza_id_sesiune() -> str:
    """ID unic de 8 caractere pentru o sesiune de simulare."""
    return uuid.uuid4().hex[:8]
