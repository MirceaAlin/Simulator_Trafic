"""Teste pentru serverul Flask: pagini, API, validare input, WebSocket."""

import time

import pytest

import app as modul_app
from app import (
    MAX_SESIUNI,
    SimulationSession,
    _aplica_perturbatie_initiala,
    _build_payload,
    _build_stabilitate,
    _numar,
    app,
    run_simulation,
    sessions,
    socketio,
)
from simulare.bando import SimulatorBando
from simulare.herman import SimulatorHerman


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c
    # Curatam orice sesiune ramasa dupa fiecare test.
    for sid in list(sessions):
        sessions[sid].running = False
    timeout = time.time() + 3
    while sessions and time.time() < timeout:
        time.sleep(0.05)
    sessions.clear()


def _porneste(client, **override):
    body = {"model": "bando", "N": 10, "lungime_m": 1000,
            "a": 1.0, "perturbatie_tip": "niciuna", "sim_speed": 1.0}
    body.update(override)
    return client.post('/api/simulare/start', json=body)


def _opreste_si_asteapta(client, sim_id):
    client.post('/api/simulare/stop', json={"sim_id": sim_id})
    timeout = time.time() + 3
    while sim_id in sessions and time.time() < timeout:
        time.sleep(0.05)



# Pagini si trasee

def test_paginile_raspund(client):
    assert client.get('/').status_code == 200
    assert client.get('/simulator').status_code == 200


def test_api_trasee(client):
    rasp = client.get('/api/trasee')
    assert rasp.status_code == 200
    trasee = rasp.get_json()
    assert len(trasee) == 3
    assert {t["id"] for t in trasee} == \
        {"calea_turzii", "vivo_centru", "iulius_centru"}



# Validarea inputului (_numar)

def test_numar_aduce_in_limite():
    assert _numar({"N": 99999}, "N", 30, ca_int=True) == 300
    assert _numar({"N": -5}, "N", 30, ca_int=True) == 2
    assert _numar({"a": 0.7}, "a", 1.0) == pytest.approx(0.7)
    assert _numar({}, "a", 1.0) == pytest.approx(1.0)   # valoarea implicita


def test_numar_respinge_text():
    with pytest.raises(ValueError):
        _numar({"N": "abc"}, "N", 30)
    with pytest.raises(ValueError):
        _numar({"a": None}, "a", 1.0)



# Start / stop simulare

def test_start_si_stop_bando(client):
    rasp = _porneste(client)
    assert rasp.status_code == 200
    date = rasp.get_json()
    assert date["status"] == "ok"
    sim_id = date["sim_id"]
    assert sim_id in sessions
    assert isinstance(sessions[sim_id].simulator, SimulatorBando)

    time.sleep(0.2)   # lasam bucla sa faca macar un frame
    _opreste_si_asteapta(client, sim_id)
    assert sim_id not in sessions   # thread-ul si-a sters sesiunea


def test_start_herman_cu_traseu(client):
    rasp = _porneste(client, model="herman", traseu="calea_turzii",
                     **{"lambda": 0.4, "delta": 1.0})
    sim_id = rasp.get_json()["sim_id"]
    sim = sessions[sim_id].simulator
    assert isinstance(sim, SimulatorHerman)
    assert sim.C == pytest.approx(0.4)
    _opreste_si_asteapta(client, sim_id)


def test_start_foloseste_lungimea_traseului(client):
    # Fara lungime_m in cerere, se ia lungimea traseului ales.
    body = {"model": "bando", "N": 10, "traseu": "vivo_centru",
            "perturbatie_tip": "niciuna"}
    rasp = client.post('/api/simulare/start', json=body)
    sim_id = rasp.get_json()["sim_id"]
    assert sessions[sim_id].simulator.L == pytest.approx(7000.0)
    _opreste_si_asteapta(client, sim_id)


def test_start_cu_parametri_invalizi(client):
    rasp = _porneste(client, N="abc")
    assert rasp.status_code == 400
    assert rasp.get_json()["status"] == "error"


def test_start_limiteaza_N(client):
    rasp = _porneste(client, N=99999)
    sim_id = rasp.get_json()["sim_id"]
    assert sessions[sim_id].simulator.N == 300
    _opreste_si_asteapta(client, sim_id)


def test_start_refuza_peste_limita_de_sesiuni(client):
    # Umplem registrul cu sesiuni fictive.
    for i in range(MAX_SESIUNI):
        sessions[f"fictiv{i}"] = SimulationSession(f"fictiv{i}")
    try:
        rasp = _porneste(client)
        assert rasp.status_code == 429
    finally:
        for i in range(MAX_SESIUNI):
            sessions.pop(f"fictiv{i}", None)


def test_stop_sesiune_inexistenta(client):
    rasp = client.post('/api/simulare/stop', json={"sim_id": "nu-exista"})
    assert rasp.status_code == 404



# Perturbatia initiala

def test_perturbatie_initiala_toate_tipurile():
    for model, cls, scaderi in [
        ("herman", SimulatorHerman, {"usoara": 2.0, "brusca": 6.0}),
        ("bando", SimulatorBando, {"usoara": 1.5, "brusca": 4.0}),
    ]:
        for tip, scadere in scaderi.items():
            sim = cls(N=10, L=1000.0)
            v0 = sim.v[0]
            _aplica_perturbatie_initiala(sim, model, tip)
            assert sim.v[0] == pytest.approx(v0 - scadere)

        sim = cls(N=10, L=1000.0)
        _aplica_perturbatie_initiala(sim, model, "oprire")
        assert sim.v[0] == 0.0

        sim = cls(N=10, L=1000.0)
        v0 = sim.v[0]
        _aplica_perturbatie_initiala(sim, model, "niciuna")
        _aplica_perturbatie_initiala(sim, model, "tip-necunoscut")
        assert sim.v[0] == v0



# Perturbatia manuala si viteza simularii

def test_perturbatie_manuala(client):
    sim_id = _porneste(client).get_json()["sim_id"]
    v0 = sessions[sim_id].simulator.v[3]
    rasp = client.post('/api/simulare/perturbatie',
                       json={"sim_id": sim_id, "masina_idx": 3,
                             "delta_v_kmh": -15})
    assert rasp.status_code == 200
    assert sessions[sim_id].simulator.v[3] < v0
    _opreste_si_asteapta(client, sim_id)


def test_perturbatie_sesiune_inexistenta(client):
    rasp = client.post('/api/simulare/perturbatie',
                       json={"sim_id": "nu-exista", "masina_idx": 0})
    assert rasp.status_code == 404


def test_perturbatie_parametri_invalizi(client):
    rasp = client.post('/api/simulare/perturbatie',
                       json={"sim_id": "x", "masina_idx": "abc"})
    assert rasp.status_code == 400


def test_schimbare_viteza(client):
    sim_id = _porneste(client).get_json()["sim_id"]
    rasp = client.post('/api/simulare/viteza',
                       json={"sim_id": sim_id, "sim_speed": 8})
    assert rasp.status_code == 200
    assert sessions[sim_id].sim_speed == 8.0
    # Valorile prea mari se aduc la limita.
    client.post('/api/simulare/viteza',
                json={"sim_id": sim_id, "sim_speed": 99})
    assert sessions[sim_id].sim_speed == 10.0
    _opreste_si_asteapta(client, sim_id)


def test_viteza_sesiune_inexistenta(client):
    rasp = client.post('/api/simulare/viteza',
                       json={"sim_id": "nu-exista", "sim_speed": 5})
    assert rasp.status_code == 404


def test_viteza_valoare_invalida(client):
    rasp = client.post('/api/simulare/viteza',
                       json={"sim_id": "x", "sim_speed": "rapid"})
    assert rasp.status_code == 400



# Payload si stabilitate

def test_build_payload():
    sim = SimulatorBando(N=5, L=1000.0)
    sim.step()
    payload = _build_payload("abc", sim, "bando")
    assert payload["sim_id"] == "abc"
    assert payload["t"] == pytest.approx(0.05)
    assert len(payload["pozitii_km"]) == 5
    assert len(payload["viteze_kmh"]) == 5
    assert payload["stabilitate"]["model"] == "bando"


def test_stabilitate_herman_toate_starile():
    asteptat = {0.3: "stabil", 0.45: "marginal", 0.8: "instabil", 1.8: "critic"}
    for lam, stare_txt in asteptat.items():
        sim = SimulatorHerman(N=5, L=500.0, lam=lam)
        rezultat = _build_stabilitate("herman", sim.get_stare(), sim)
        assert rezultat["stare"] == stare_txt
        assert rezultat["model"] == "herman"


def test_stabilitate_bando_toate_starile():
    sim = SimulatorBando(N=75, L=3500.0, a=1.0)
    f = sim.f
    asteptat = {
        1.0:       "stabil",     # ratio = 2f/a ~ 0.61
        2 * f:     "marginal",   # ratio = 1.0
        1.2 * f:   "instabil",   # ratio ~ 1.67
        0.5 * f:   "critic",     # ratio = 4.0
    }
    for a, stare_txt in asteptat.items():
        s = SimulatorBando(N=75, L=3500.0, a=a)
        rezultat = _build_stabilitate("bando", s.get_stare(), s)
        assert rezultat["stare"] == stare_txt, f"a={a}"


def test_stabilitate_bando_prag_zero():
    # Daca pragul ar fi 0, raportul devine 0 (nu impartim la zero).
    sim = SimulatorBando(N=10, L=500.0)
    stare = sim.get_stare()
    stare["prag"] = 0.0
    rezultat = _build_stabilitate("bando", stare, sim)
    assert rezultat["stare"] == "stabil"



# Bucla de simulare si WebSocket

def test_run_simulation_sesiune_inexistenta():
    # Trebuie sa iasa imediat, fara erori.
    run_simulation("nu-exista")


def test_websocket_subscribe():
    ws = socketio.test_client(app)
    assert ws.is_connected()
    ws.emit('subscribe_simulare', {"sim_id": "abc"})
    ws.emit('subscribe_simulare', {})          # fara sim_id: ignorat
    ws.emit('subscribe_simulare', None)        # fara date: ignorat
    ws.disconnect()


def test_websocket_primeste_tick(client):
    ws = socketio.test_client(app)
    sim_id = _porneste(client, sim_speed=5.0).get_json()["sim_id"]
    ws.emit('subscribe_simulare', {"sim_id": sim_id})

    primite = []
    timeout = time.time() + 3
    while not primite and time.time() < timeout:
        time.sleep(0.1)
        primite = [m for m in ws.get_received() if m["name"] == "tick"]

    assert primite, "nu a sosit niciun tick in 3 secunde"
    tick = primite[0]["args"][0]
    assert tick["sim_id"] == sim_id
    assert tick["t"] > 0

    _opreste_si_asteapta(client, sim_id)
    ws.disconnect()



# Securitate: configurare

def test_secret_key_nu_e_hardcodat():
    # Cheia e generata sau vine din mediu; nu e un text fix din cod.
    assert app.config['SECRET_KEY'] != 'secret_key_licenta'
    assert len(app.config['SECRET_KEY']) >= 32


def test_modulul_nu_porneste_serverul_la_import():
    # Importul lui app.py (facut deja sus) nu trebuie sa blocheze sau sa
    # porneasca serverul. Daca am ajuns aici, e in regula.
    assert modul_app is not None
