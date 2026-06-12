"""Teste pentru traseele predefinite."""

from simulare.trasee import TRASEE, get_lista_trasee


def test_exista_trei_trasee():
    assert len(TRASEE) == 3
    assert set(TRASEE) == {"calea_turzii", "vivo_centru", "iulius_centru"}


def test_toate_se_termina_in_centru():
    finaluri = {tuple(t["end"]) for t in TRASEE.values()}
    assert len(finaluri) == 1   # acelasi punct final pentru toate


def test_lista_are_campurile_necesare():
    lista = get_lista_trasee()
    assert len(lista) == 3
    campuri = {"id", "nume", "descriere", "start", "end",
               "viteza_limita_kmh", "culoare", "lungime_m"}
    for traseu in lista:
        assert campuri <= set(traseu)
        assert traseu["viteza_limita_kmh"] == 50
        assert traseu["lungime_m"] > 0


def test_numele_folosesc_cratima():
    for traseu in get_lista_trasee():
        assert " - " in traseu["nume"]
