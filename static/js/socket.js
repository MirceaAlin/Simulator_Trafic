// static/js/socket.js
// Comunicare WebSocket + API REST pentru pornit/oprit simulare.

let socket = null;

window.currentSimId = null;

function initSocket() {
    socket = io();

    socket.on('connect', () => {
        console.log('WebSocket connected');
    });

    socket.on('tick', (data) => {
        if (data.sim_id !== window.currentSimId) return;

        // Distribuim datele către componente
        if (window.updateAnimationData) window.updateAnimationData(data);
        if (window.updateCharts)        window.updateCharts(data);
        if (window.updateStats)         window.updateStats(data);
        if (window.updateRouteCars)     window.updateRouteCars(data);

        // Actualizăm timpul (format "Xmin Ys")
        const timeEl = document.getElementById('sim-time');
        if (timeEl) {
            const totalSec = Math.floor(data.t);
            const m = Math.floor(totalSec / 60);
            const s = totalSec % 60;
            timeEl.textContent = `t = ${m}min ${s.toString().padStart(2, '0')}s`;
        }
    });

    socket.on('disconnect', () => {
        console.log('WebSocket disconnected');
    });
}

function startSimulationCall(config) {
    fetch('/api/simulare/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'ok') {
            window.currentSimId = data.sim_id;
            socket.emit('subscribe_simulare', { sim_id: data.sim_id });

            if (window.onSimulationStarted) {
                window.onSimulationStarted(data.sim_id);
            }
        } else {
            alert('Eroare la pornirea simulării: ' + (data.message || 'necunoscută'));
        }
    })
    .catch(err => {
        console.error('Error starting sim:', err);
        alert('Eroare de rețea la pornire.');
    });
}

function stopSimulationCall() {
    if (!window.currentSimId) return;

    fetch('/api/simulare/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sim_id: window.currentSimId })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'ok' && window.onSimulationStopped) {
            window.onSimulationStopped();
        }
    });
}

function sendManualPerturbation(idx) {
    if (!window.currentSimId) return;

    fetch('/api/simulare/perturbatie', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            sim_id: window.currentSimId,
            masina_idx: idx,
            delta_v_kmh: -15
        })
    });
}

function setSimSpeedCall(speed) {
    if (!window.currentSimId) return;

    fetch('/api/simulare/viteza', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            sim_id: window.currentSimId,
            sim_speed: speed
        })
    });
}

// Export global
window.startSimulationCall     = startSimulationCall;
window.stopSimulationCall      = stopSimulationCall;
window.applyManualPerturbation = sendManualPerturbation;
window.setSimSpeedCall         = setSimSpeedCall;

// La inchiderea/refresh-ul paginii trimitem un stop catre server,
// ca simularea sa nu ramana sa ruleze degeaba. sendBeacon e singura
// metoda fiabila intr-un eveniment de tip pagehide.
window.addEventListener('pagehide', () => {
    if (!window.currentSimId) return;
    const payload = new Blob(
        [JSON.stringify({ sim_id: window.currentSimId })],
        { type: 'application/json' }
    );
    navigator.sendBeacon('/api/simulare/stop', payload);
});

document.addEventListener('DOMContentLoaded', () => {
    initSocket();
});