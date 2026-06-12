// static/js/animatie.js
// Vizualizare canvas a vehiculelor pe o bandă orizontală.
// Click pe o mașină = perturbație manuală (frânare).

let canvas = null;
let ctx    = null;

let currentState = null;   // ultima stare primită prin WebSocket
let routeLength_km = 5;    // se actualizează din /api/trasee + currentRouteLength

const CAR_RADIUS_PX = 8;


function initAnimation() {
    canvas = document.getElementById('anim-canvas');
    if (!canvas) return;
    ctx = canvas.getContext('2d');

    // Sincronizăm rezoluția internă a canvas-ului cu dimensiunea afișată
    _resizeCanvas();
    window.addEventListener('resize', _resizeCanvas);

    // Click pe canvas → găsim mașina cea mai apropiată și aplicăm perturbație
    canvas.addEventListener('click', (ev) => {
        if (!currentState) return;

        const rect = canvas.getBoundingClientRect();
        // Convertim coordonatele click-ului la rezoluția internă a canvas-ului
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        const cx = (ev.clientX - rect.left) * scaleX;
        const cy = (ev.clientY - rect.top) * scaleY;

        const idx = _findNearestCar(cx, cy);
        if (idx >= 0 && window.applyManualPerturbation) {
            window.applyManualPerturbation(idx);
            _flashCar(idx);
        }
    });

    // Buclă de randare independentă (60 fps) pentru fluiditate
    requestAnimationFrame(_renderLoop);
}


// Sincronizează rezoluția internă (canvas.width/height) cu dimensiunea CSS.
function _resizeCanvas() {
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
        canvas.width  = Math.round(rect.width);
        canvas.height = Math.round(rect.height);
    }
}


function updateAnimationData(state) {
    currentState = state;

    // Actualizăm lungimea traseului din variabila globală (vine din harta.js)
    if (window.currentRouteLength) {
        routeLength_km = window.currentRouteLength / 1000.0;
    }
}


function _renderLoop() {
    if (canvas && ctx) {
        // Verificăm dacă dimensiunea afișată s-a schimbat (ex: după layout)
        const rect = canvas.getBoundingClientRect();
        if (rect.width > 0 &&
            Math.abs(canvas.width - Math.round(rect.width)) > 1) {
            _resizeCanvas();
        }
        _render();
    }
    requestAnimationFrame(_renderLoop);
}

function _render() {
    const W = canvas.width;
    const H = canvas.height;

    // Curățăm
    ctx.fillStyle = '#f8fafc';
    ctx.fillRect(0, 0, W, H);

    // Banda de drum
    const roadY = H / 2;
    const roadH = 60;

    // Asfalt
    ctx.fillStyle = '#374151';
    ctx.fillRect(20, roadY - roadH/2, W - 40, roadH);

    // Linii laterale
    ctx.strokeStyle = '#fbbf24';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(20, roadY - roadH/2);
    ctx.lineTo(W - 20, roadY - roadH/2);
    ctx.moveTo(20, roadY + roadH/2);
    ctx.lineTo(W - 20, roadY + roadH/2);
    ctx.stroke();

    // Linie mediană punctată
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    ctx.setLineDash([12, 12]);
    ctx.beginPath();
    ctx.moveTo(20, roadY);
    ctx.lineTo(W - 20, roadY);
    ctx.stroke();
    ctx.setLineDash([]);

    if (!currentState) {
        // Mesaj inițial
        ctx.fillStyle = '#94a3b8';
        ctx.font = '14px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(
            'Pornește simularea pentru a vedea vehiculele',
            W / 2, H / 2 + 50
        );
        return;
    }

    // Desenăm mașinile
    const margin = 25;
    const usableW = W - 2 * margin;

    for (let i = 0; i < currentState.pozitii_km.length; i++) {
        const pos_km   = currentState.pozitii_km[i];
        const v_kmh    = currentState.viteze_kmh[i];

        // Poziție normalizată [0, 1]
        const u = (pos_km / Math.max(0.01, routeLength_km)) % 1.0;
        const cx = margin + u * usableW;
        const cy = roadY;

        _drawCar(cx, cy, v_kmh, i);
    }
}


// Desenează o mașină colorată după viteza ei.
function _drawCar(x, y, v_kmh, idx) {
    const r = CAR_RADIUS_PX;

    // Culoare după viteză: roșu (0) → galben (~25) → verde (50+)
    const color = _speedColor(v_kmh);

    ctx.fillStyle = color;
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = 1;

    ctx.beginPath();
    ctx.arc(x, y, r, 0, 2 * Math.PI);
    ctx.fill();
    ctx.stroke();

    // Marcaj „flash" pentru click recent
    if (_flashIdx === idx && (performance.now() - _flashStart) < 600) {
        ctx.strokeStyle = '#fbbf24';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(x, y, r + 4, 0, 2 * Math.PI);
        ctx.stroke();
    }
}

function _speedColor(v_kmh) {
    // 0 km/h -> #ef4444 (roșu)
    // 25 km/h -> #fbbf24 (galben)
    // 50 km/h -> #10b981 (verde)
    const v = Math.max(0, Math.min(50, v_kmh));
    if (v < 25) {
        const t = v / 25;
        return _lerpColor('#ef4444', '#fbbf24', t);
    } else {
        const t = (v - 25) / 25;
        return _lerpColor('#fbbf24', '#10b981', t);
    }
}

function _lerpColor(c1, c2, t) {
    const a = _hexToRgb(c1);
    const b = _hexToRgb(c2);
    const r = Math.round(a.r + (b.r - a.r) * t);
    const g = Math.round(a.g + (b.g - a.g) * t);
    const bb = Math.round(a.b + (b.b - a.b) * t);
    return `rgb(${r},${g},${bb})`;
}

function _hexToRgb(hex) {
    const v = hex.replace('#', '');
    return {
        r: parseInt(v.substring(0, 2), 16),
        g: parseInt(v.substring(2, 4), 16),
        b: parseInt(v.substring(4, 6), 16),
    };
}


function _findNearestCar(cx, cy) {
    if (!currentState) return -1;

    const W = canvas.width;
    const margin = 25;
    const usableW = W - 2 * margin;
    const roadY = canvas.height / 2;

    let bestIdx = -1;
    let bestDist = 20 * 20;   // 20 px

    for (let i = 0; i < currentState.pozitii_km.length; i++) {
        const u = (currentState.pozitii_km[i] / Math.max(0.01, routeLength_km)) % 1.0;
        const x = margin + u * usableW;
        const dx = x - cx;
        const dy = roadY - cy;
        const d = dx*dx + dy*dy;
        if (d < bestDist) {
            bestDist = d;
            bestIdx = i;
        }
    }
    return bestIdx;
}


let _flashIdx = -1;
let _flashStart = 0;
function _flashCar(idx) {
    _flashIdx = idx;
    _flashStart = performance.now();
}


function stopAnimation() {
    currentState = null;
}

window.updateAnimationData = updateAnimationData;
window.stopAnimation       = stopAnimation;

document.addEventListener('DOMContentLoaded', initAnimation);
