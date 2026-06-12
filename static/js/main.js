// static/js/main.js
// Controlează UI-ul: slidere, switching între modele, start/stop simulare,
// indicatori live de stabilitate, statistici.

document.addEventListener('DOMContentLoaded', () => {

    // --- Slidere ---
    const sliders = {
        n:     document.getElementById('slider-n'),
        lam:   document.getElementById('slider-lam'),
        delta: document.getElementById('slider-delta'),
        a:     document.getElementById('slider-a'),
    };
    const vals = {
        n:     document.getElementById('val-n'),
        lam:   document.getElementById('val-lam'),
        delta: document.getElementById('val-delta'),
        a:     document.getElementById('val-a'),
    };

    function updateSliderVals() {
        if (sliders.n)     vals.n.textContent     = sliders.n.value;
        if (sliders.lam)   vals.lam.textContent   = sliders.lam.value;
        if (sliders.delta) vals.delta.textContent = sliders.delta.value;
        if (sliders.a)     vals.a.textContent     = sliders.a.value;

        calculateIndicators();
    }

    Object.values(sliders).forEach(s => {
        if (s) s.addEventListener('input', updateSliderVals);
    });
    updateSliderVals();

    // --- Switching între modele ---
    const radios = document.querySelectorAll('input[name="model-type"]');
    radios.forEach(r => {
        r.addEventListener('change', (e) => {
            const isHerman = e.target.value === 'herman';
            document.getElementById('params-herman').classList.toggle('hidden', !isHerman);
            document.getElementById('params-bando').classList.toggle('hidden', isHerman);
            calculateIndicators();
        });
    });

    // --- Start / Stop ---
    const btnStart = document.getElementById('btn-start');
    const btnStop  = document.getElementById('btn-stop');

    btnStart.addEventListener('click', () => {
        const modelType = document.querySelector('input[name="model-type"]:checked').value;

        const simSpeedEl = document.getElementById('slider-sim-speed');
        const simSpeed   = simSpeedEl ? parseFloat(simSpeedEl.value) : 5.0;

        const config = {
            model:           modelType,
            N:               parseInt(sliders.n.value, 10),
            traseu:          window.currentRouteId,
            lungime_m:       window.currentRouteLength,
            perturbatie_tip: document.getElementById('perturbatie-select').value,
            sim_speed:       simSpeed,
        };

        if (modelType === 'herman') {
            config.lambda = parseFloat(sliders.lam.value);
            config.delta  = parseFloat(sliders.delta.value);
        } else {
            config.a = parseFloat(sliders.a.value);
        }

        if (window.resetCharts) window.resetCharts();
        if (window.startSimulationCall) window.startSimulationCall(config);
    });

    btnStop.addEventListener('click', () => {
        if (window.stopSimulationCall) window.stopSimulationCall();
    });

    // --- Slider viteză simulare: trimite update live ---
    const sliderSpeed = document.getElementById('slider-sim-speed');
    const valSpeed    = document.getElementById('val-sim-speed');
    if (sliderSpeed && valSpeed) {
        sliderSpeed.addEventListener('input', () => {
            valSpeed.textContent = sliderSpeed.value;
            // Dacă o simulare e activă, trimitem update
            if (window.currentSimId && window.setSimSpeedCall) {
                window.setSimSpeedCall(parseFloat(sliderSpeed.value));
            }
        });
    }
});


// Recalculează indicatorii de stabilitate (înainte de Start, după Start sunt
// înlocuiți de valorile reale primite prin WebSocket).
function calculateIndicators() {
    // --- Herman: C = λ·Δ/M ---
    const lam   = parseFloat(document.getElementById('slider-lam')?.value || 0.3);
    const delta = parseFloat(document.getElementById('slider-delta')?.value || 1.0);
    const C = lam * delta;

    const elC    = document.getElementById('calc-c');
    const badgeH = document.getElementById('herman-color-indicator');
    if (elC) elC.textContent = C.toFixed(2);

    if (badgeH) {
        badgeH.className = 'color-badge';
        if (C <= 1.0 / Math.E) {
            badgeH.classList.add('green');
            badgeH.textContent = 'C ≤ 1/e (stabil neoscilatoriu)';
        } else if (C < 0.5) {
            badgeH.classList.add('yellow');
            badgeH.textContent = '1/e < C < 1/2 (stabil oscilatoriu)';
        } else if (C < Math.PI / 2) {
            badgeH.classList.add('orange');
            badgeH.textContent = '1/2 ≤ C < π/2 (instabil)';
        } else {
            badgeH.classList.add('red');
            badgeH.textContent = 'C ≥ π/2 (critic - coliziuni)';
        }
    }

    // --- Bando: f = V'(b) si pragul a/2 ---
    // f depinde doar de N si de lungimea traseului, deci se poate calcula
    // direct in browser, fara simulare (la fel ca C la Herman).
    const a = parseFloat(document.getElementById('slider-a')?.value || 0.5);
    const N = parseInt(document.getElementById('slider-n')?.value || 50, 10);
    const L = window.currentRouteLength || 3500;

    const V_MAX_MS    = 50.0 / 3.6;            // 13.889 m/s
    const ONE_P_TANH2 = 1.0 + Math.tanh(2.0);  // ≈ 1.9640
    const scale = (L / N) / 2.0;
    const f = (scale > 0) ? V_MAX_MS / (scale * ONE_P_TANH2) : 0;

    _updateBandoBadge(f, a / 2.0);
}
// Folosit si din harta.js: cand se schimba traseul, f trebuie recalculat.
window.calculateIndicators = calculateIndicators;


// Blocheaza/deblocheaza coloana de configurare cat timp ruleaza simularea.
// Parametrii se citesc o singura data, la Start, deci modificarea lor in
// timpul rularii nu ar avea niciun efect si doar ar induce in eroare.
function setConfigEnabled(enabled) {
    const panel = document.querySelector('.panel-left');
    if (!panel) return;

    panel.querySelectorAll('input, select, button').forEach(el => {
        // Butoanele Start/Stop rămân mereu funcționale
        if (el.id === 'btn-start' || el.id === 'btn-stop') return;
        el.disabled = !enabled;
    });

    panel.classList.toggle('config-locked', !enabled);
}


window.onSimulationStarted = function (simId) {
    document.getElementById('btn-start').classList.add('hidden');
    document.getElementById('btn-stop').classList.remove('hidden');

    // Blocăm configurarea: traseu, model, parametri, N, perturbație
    setConfigEnabled(false);
    // Dacă utilizatorul era în modul „Rută nouă", îl anulăm
    if (window.cancelCustomRouteMode) window.cancelCustomRouteMode();

    const circ = document.getElementById('main-stability-circle');
    circ.className = 'circle-indicator gray';
    document.getElementById('main-stability-text').textContent = 'Pornire...';
};

window.onSimulationStopped = function () {
    document.getElementById('btn-start').classList.remove('hidden');
    document.getElementById('btn-stop').classList.add('hidden');

    // Deblocăm configurarea
    setConfigEnabled(true);

    if (window.stopAnimation)     window.stopAnimation();
    if (window.clearCarMarkers)   window.clearCarMarkers();
};


window.updateStats = function (state) {
    // Clamping pentru afișare (în caz de coliziuni Herman, v poate exploda)
    const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
    const vMed = clamp(state.viteza_medie_kmh, -999, 999);
    const vMin = clamp(state.viteza_min_kmh, -999, 999);
    const vMax = clamp(state.viteza_max_kmh, -999, 999);

    document.getElementById('stat-vmed').textContent = `${vMed.toFixed(1)} km/h`;
    document.getElementById('stat-vdif').textContent =
        `${(vMax - vMin).toFixed(1)} km/h`;

    const stab = state.stabilitate;
    const nrCol = stab.nr_coliziuni || 0;
    document.getElementById('stat-coliziuni').textContent = nrCol;

    // --- Indicator stabilitate (cercul mare) ---
    const circ    = document.getElementById('main-stability-circle');
    const text    = document.getElementById('main-stability-text');
    const valText = document.getElementById('main-stability-val');

    // Mapăm starea la culoare
    let cls = 'gray', label = '?';
    switch (stab.stare) {
        case 'stabil':    cls = 'green';  label = 'STABIL';   break;
        case 'marginal':  cls = 'yellow'; label = 'MARGINAL'; break;
        case 'instabil':  cls = 'orange'; label = 'INSTABIL'; break;
        case 'critic':    cls = 'red';    label = 'CRITIC';   break;
    }
    circ.className = `circle-indicator ${cls}`;
    text.textContent = label;

    // Detaliu numeric
    if (stab.model === 'herman') {
        valText.textContent = `C = ${stab.valoare.toFixed(3)} (prag 1/2 = 0.5)`;
        _updateHermanBadge(stab.valoare);
    } else {
        valText.textContent =
            `f = ${stab.valoare.toFixed(3)} | a/2 = ${stab.prag.toFixed(3)}`;
        _updateBandoBadge(stab.valoare, stab.prag);
    }
};

function _updateHermanBadge(C) {
    const elC = document.getElementById('calc-c');
    if (elC) elC.textContent = C.toFixed(3);

    const badge = document.getElementById('herman-color-indicator');
    if (!badge) return;
    badge.className = 'color-badge';
    if (C <= 1.0 / Math.E) {
        badge.classList.add('green');
        badge.textContent = 'C ≤ 1/e';
    } else if (C < 0.5) {
        badge.classList.add('yellow');
        badge.textContent = '1/e < C < 1/2';
    } else if (C < Math.PI / 2) {
        badge.classList.add('orange');
        badge.textContent = '1/2 ≤ C < π/2';
    } else {
        badge.classList.add('red');
        badge.textContent = 'C ≥ π/2';
    }
}

function _updateBandoBadge(f, prag) {
    const elF = document.getElementById('calc-f');
    if (elF) elF.textContent = f.toFixed(3);

    const elPrag = document.getElementById('calc-a-half');
    if (elPrag) elPrag.textContent = prag.toFixed(3);

    const badge = document.getElementById('bando-color-indicator');
    if (!badge) return;

    const ratio = prag > 0 ? f / prag : 0;
    badge.className = 'color-badge';
    if (ratio < 0.9) {
        badge.classList.add('green');
        badge.textContent = 'f < a/2 (stabil)';
    } else if (ratio < 1.1) {
        badge.classList.add('yellow');
        badge.textContent = 'f ≈ a/2 (marginal)';
    } else if (ratio < 2.0) {
        badge.classList.add('orange');
        badge.textContent = `f > a/2 (${ratio.toFixed(2)}x)`;
    } else {
        badge.classList.add('red');
        badge.textContent = `f >> a/2 (${ratio.toFixed(2)}x)`;
    }
}
