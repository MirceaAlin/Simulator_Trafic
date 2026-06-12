"""
Server Flask + SocketIO pentru aplicatia Simulator Trafic.

Pagini: / (Acasa) si /simulator.
API REST: lista trasee, start/stop simulare, perturbatie manuala,
schimbare viteza simulare.
WebSocket: serverul emite 'tick' cu starea simularii la 30 fps.

Modele suportate: Herman (1959) si Bando (1995).
"""

import os
import secrets
import threading
import time

import numpy as np
from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO, join_room

from simulare.bando import SimulatorBando
from simulare.herman import SimulatorHerman
from simulare.trasee import TRASEE, get_lista_trasee
from simulare.utilitar import genereaza_id_sesiune, kmh_to_ms, m_to_km, ms_to_kmh

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

socketio = SocketIO(app, async_mode='threading')

# Limite pentru datele primite de la client. Orice valoare din afara
# intervalului e adusa la capatul cel mai apropiat, iar valorile care nu
# sunt numere intorc eroare 400. Fara aceste limite, un client ar putea
# porni simulari cu N urias si bloca serverul.
LIMITE = {
    'N':           (2,     300),
    'lambda':      (0.05,  3.0),
    'delta':       (0.1,   5.0),
    'a':           (0.05,  3.0),
    'lungime_m':   (200.0, 50000.0),
    'sim_speed':   (0.5,   10.0),
    'delta_v_kmh': (-60.0, 60.0),
}

# Cate simulari pot rula in acelasi timp.
MAX_SESIUNI = 10

# O simulare fara niciun client conectat se opreste singura dupa acest timp.
GRACE_FARA_CLIENTI_S = 30.0

# Durata maxima de viata a unei simulari (timp real), ca plasa de siguranta.
MAX_DURATA_S = 15 * 60.0


def _numar(data, cheie, implicit, ca_int=False):
    """Citeste un numar din JSON-ul cererii si il aduce in limitele lui.

    Arunca ValueError daca valoarea nu e un numar.
    """
    brut = data.get(cheie, implicit)
    try:
        val = float(brut)
    except (TypeError, ValueError):
        raise ValueError(f"Valoare invalida pentru '{cheie}': {brut!r}")
    lo, hi = LIMITE[cheie]
    val = max(lo, min(hi, val))
    return int(val) if ca_int else val



# Sesiuni de simulare. Fiecare ruleaza in propriul thread.

class SimulationSession:
    def __init__(self, sim_id):
        self.sim_id      = sim_id
        self.simulator   = None
        self.running     = False
        self.thread      = None
        self.model_type  = ""
        self.sim_speed   = 5.0
        self.created_at  = time.time()
        # Clientii (sid-uri Socket.IO) abonati la aceasta simulare.
        # Cand multimea e goala mai mult de GRACE_FARA_CLIENTI_S secunde,
        # bucla de simulare se opreste singura.
        self.subscribers = set()
        self.ultim_client_la = time.time()


sessions    = {}
global_lock = threading.Lock()



# Pagini HTML

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/simulator')
def simulator_page():
    return render_template('simulator.html')



# API REST

@app.route('/api/trasee', methods=['GET'])
def api_trasee():
    """Lista traseelor predefinite."""
    return jsonify(get_lista_trasee())


@app.route('/api/simulare/start', methods=['POST'])
def api_start_simulare():
    """Porneste o simulare noua.

    Body JSON:
        model:           'herman' sau 'bando'
        N:               numar de vehicule
        traseu:          id traseu predefinit (pentru lungimea implicita)
        lungime_m:       lungimea traseului in metri
        lambda, delta:   parametri Herman
        a:               parametru Bando
        perturbatie_tip: 'niciuna' / 'usoara' / 'brusca' / 'oprire'
        sim_speed:       multiplicator viteza simulare (1-10)
    """
    data   = request.json or {}
    sim_id = genereaza_id_sesiune()

    try:
        with global_lock:
            if len(sessions) >= MAX_SESIUNI:
                return jsonify({
                    "status": "error",
                    "message": "Prea multe simulari active. Opreste una intai.",
                }), 429

            session            = SimulationSession(sim_id)
            model_type         = data.get('model', 'bando')
            session.model_type = model_type
            session.sim_speed  = _numar(data, 'sim_speed', 5.0)

            N           = _numar(data, 'N', 30, ca_int=True)
            traseu_info = TRASEE.get(data.get('traseu'), {})
            lungime_m   = _numar(data, 'lungime_m',
                                 traseu_info.get('lungime_m', 3000))

            if model_type == 'herman':
                session.simulator = SimulatorHerman(
                    N=N, L=lungime_m, M=1.0,
                    lam=_numar(data, 'lambda', 0.3),
                    Delta=_numar(data, 'delta', 1.0),
                    dt=0.05,
                )
            else:
                session.simulator = SimulatorBando(
                    N=N, L=lungime_m, a=_numar(data, 'a', 1.0), dt=0.05,
                )

            _aplica_perturbatie_initiala(
                session.simulator, model_type,
                data.get('perturbatie_tip', 'niciuna'),
            )

            session.running  = True
            sessions[sim_id] = session
            session.thread = threading.Thread(
                target=run_simulation, args=(sim_id,), daemon=True,
            )
            session.thread.start()
    except ValueError as err:
        return jsonify({"status": "error", "message": str(err)}), 400

    return jsonify({"status": "ok", "sim_id": sim_id})


def _aplica_perturbatie_initiala(sim, model_type, tip):
    """Franeaza masina 0 la pornire, dupa tipul ales.

    Amplitudinile difera intre modele pentru ca vitezele de echilibru
    difera: Herman porneste de la 10 m/s, Bando de la ~6.9 m/s.
    """
    if tip == 'oprire':
        amplitudine = -float(sim.v[0])
    elif model_type == 'herman':
        amplitudine = {'usoara': -2.0, 'brusca': -6.0}.get(tip)
    else:
        amplitudine = {'usoara': -1.5, 'brusca': -4.0}.get(tip)

    if amplitudine is not None:
        sim.aplica_perturbatie(0, amplitudine)


@app.route('/api/simulare/stop', methods=['POST'])
def api_stop_simulare():
    """Opreste o simulare. Thread-ul ei se inchide singur si sterge sesiunea."""
    data   = request.json or {}
    sim_id = data.get('sim_id')
    with global_lock:
        if sim_id in sessions:
            sessions[sim_id].running = False
            return jsonify({"status": "ok"})
    return jsonify({"status": "error", "message": "Sesiune invalida"}), 404


@app.route('/api/simulare/perturbatie', methods=['POST'])
def api_aplicare_perturbatie():
    """Franeaza o masina aleasa de utilizator (click pe canvas)."""
    data = request.json or {}
    try:
        idx         = int(data.get('masina_idx', 0))
        delta_v_kmh = _numar(data, 'delta_v_kmh', -15.0)
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Parametri invalizi"}), 400

    sim_id = data.get('sim_id')
    with global_lock:
        if sim_id in sessions and sessions[sim_id].simulator:
            sessions[sim_id].simulator.aplica_perturbatie(
                idx, kmh_to_ms(delta_v_kmh),
            )
            return jsonify({"status": "ok"})

    return jsonify({"status": "error"}), 404


@app.route('/api/simulare/viteza', methods=['POST'])
def api_seteaza_viteza():
    """Schimba viteza simularii in timp ce ruleaza."""
    data = request.json or {}
    try:
        sim_speed = _numar(data, 'sim_speed', 5.0)
    except ValueError as err:
        return jsonify({"status": "error", "message": str(err)}), 400

    sim_id = data.get('sim_id')
    with global_lock:
        if sim_id in sessions:
            sessions[sim_id].sim_speed = sim_speed
            return jsonify({"status": "ok", "sim_speed": sim_speed})

    return jsonify({"status": "error"}), 404



# Bucla de simulare (un thread per sesiune)

def run_simulation(sim_id):
    """Avanseaza simularea si trimite starea prin WebSocket la 30 fps.

    sim_speed spune cate secunde simulate trec intr-o secunda reala.
    Cand sesiunea e oprita, thread-ul se termina si sterge sesiunea.
    """
    FPS        = 30
    frame_time = 1.0 / FPS

    session = sessions.get(sim_id)
    if not session:
        return

    sim = session.simulator

    while session.running:
        t_start = time.time()

        # Auto-oprire: durata maxima depasita sau niciun client conectat.
        if session.subscribers:
            session.ultim_client_la = t_start
        if (t_start - session.created_at > MAX_DURATA_S
                or t_start - session.ultim_client_la > GRACE_FARA_CLIENTI_S):
            session.running = False
            break

        # Cati pasi dt incap intr-un frame la viteza curenta.
        steps = max(1, int(round(frame_time * session.sim_speed / sim.dt)))
        for _ in range(steps):
            sim.step()

        socketio.emit('tick', _build_payload(sim_id, sim, session.model_type),
                      room=f'sim_{sim_id}')

        # Pastram ritmul de 30 fps.
        time.sleep(max(0.0, frame_time - (time.time() - t_start)))

    with global_lock:
        sessions.pop(sim_id, None)


def _build_payload(sim_id, sim, model_type):
    """Pregateste datele trimise la frontend pentru un frame."""
    stare = sim.get_stare()

    return {
        "sim_id":           sim_id,
        "t":                round(stare['t'], 2),
        "pozitii_km":       [m_to_km(p) for p in stare['pozitii']],
        "viteze_kmh":       [ms_to_kmh(v) for v in stare['viteze']],
        "viteza_medie_kmh": ms_to_kmh(stare['viteza_medie']),
        "viteza_min_kmh":   ms_to_kmh(stare['viteza_min']),
        "viteza_max_kmh":   ms_to_kmh(stare['viteza_max']),
        "stabilitate":      _build_stabilitate(model_type, stare, sim),
    }


def _build_stabilitate(model_type, stare, sim):
    """Starea de stabilitate (text + valori) pentru indicatorul din dreapta."""
    diag = sim.get_diagnostic_stabilitate()

    if model_type == 'herman':
        C = stare.get('C', 0.0)
        if C <= 1.0 / np.e:
            stare_txt = 'stabil'
        elif C < 0.5:
            stare_txt = 'marginal'
        elif C < np.pi / 2:
            stare_txt = 'instabil'
        else:
            stare_txt = 'critic'

        return {
            "model":        "herman",
            "valoare":      round(C, 4),
            "prag":         0.5,
            "stare":        stare_txt,
            "diagnostic":   diag,
            "coliziuni":    stare.get('coliziuni', False),
            "nr_coliziuni": stare.get('nr_coliziuni', 0),
        }

    f    = stare.get('f', 0.0)
    prag = stare.get('prag', 0.25)

    ratio = f / prag if prag > 0 else 0.0
    if ratio < 0.9:
        stare_txt = 'stabil'
    elif ratio < 1.1:
        stare_txt = 'marginal'
    elif ratio < 2.0:
        stare_txt = 'instabil'
    else:
        stare_txt = 'critic'

    return {
        "model":      "bando",
        "valoare":    round(f, 4),
        "prag":       round(prag, 4),
        "stare":      stare_txt,
        "diagnostic": diag,
    }



# Evenimente WebSocket

@socketio.on('connect')
def handle_connect():
    pass


@socketio.on('subscribe_simulare')
def handle_subscribe(data):
    sim_id = (data or {}).get('sim_id')
    if not sim_id:
        return
    join_room(f'sim_{sim_id}')
    with global_lock:
        if sim_id in sessions:
            sessions[sim_id].subscribers.add(request.sid)
            sessions[sim_id].ultim_client_la = time.time()


@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    with global_lock:
        for session in sessions.values():
            session.subscribers.discard(sid)



if __name__ == '__main__':   # pragma: no cover
    socketio.run(
        app,
        debug=False,
        host='127.0.0.1',
        port=5001,
        allow_unsafe_werkzeug=True,
    )