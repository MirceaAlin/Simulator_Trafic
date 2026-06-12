"""Teste pentru functiile de conversie si ID-uri."""

from simulare.utilitar import genereaza_id_sesiune, kmh_to_ms, m_to_km, ms_to_kmh


def test_ms_to_kmh():
    assert ms_to_kmh(10.0) == 36.0
    assert ms_to_kmh(0.0) == 0.0


def test_kmh_to_ms():
    assert kmh_to_ms(36.0) == 10.0
    assert abs(kmh_to_ms(50.0) - 13.889) < 0.001


def test_conversiile_sunt_inverse():
    assert abs(kmh_to_ms(ms_to_kmh(7.3)) - 7.3) < 1e-12


def test_m_to_km():
    assert m_to_km(3500.0) == 3.5


def test_id_sesiune():
    id1 = genereaza_id_sesiune()
    id2 = genereaza_id_sesiune()
    assert len(id1) == 8
    assert id1 != id2
