// static/js/harta.js
// Harta Leaflet: trasee predefinite + rute custom (OSRM via leaflet-routing-machine).
// Animăm mașinile ca markeri-puncte pe polilinia traseului.

let map = null;
let currentPolyline = null;
let predefinedRoutes = {};
let routingControl = null;
let customRouteMode = false;
let startMarker = null;
let endMarker = null;

// Markeri vehicule pe hartă
let carMarkers = [];   // L.CircleMarker[]

// Globale folosite din main.js
window.currentRouteLength   = 5000;
window.currentRouteId       = 'calea_turzii';
window.currentPathPoints    = [];   // [[lat,lng], ...]
window.currentPathDistances = [];   // distanțe cumulative (m)


function initMap() {
    map = L.map('map').setView([46.7712, 23.6236], 13);
    window.map = map;

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    map.on('click', function (e) {
        if (!customRouteMode) return;

        if (!startMarker) {
            startMarker = L.marker(e.latlng, { draggable: true }).addTo(map);
            startMarker.bindPopup('Start').openPopup();
        } else if (!endMarker) {
            endMarker = L.marker(e.latlng, { draggable: true }).addTo(map);
            endMarker.bindPopup('End').openPopup();
            calculateCustomRoute();
        } else {
            resetCustomRoute();
            startMarker = L.marker(e.latlng, { draggable: true }).addTo(map);
            startMarker.bindPopup('Start').openPopup();
        }
    });

    loadPredefinedRoutes();
}


function loadPredefinedRoutes() {
    fetch('/api/trasee')
        .then(r => r.json())
        .then(data => {
            const select = document.getElementById('traseu-select');
            select.innerHTML = '';

            data.forEach(route => {
                predefinedRoutes[route.id] = route;
                const opt = document.createElement('option');
                opt.value = route.id;
                opt.textContent = route.nume;
                select.appendChild(opt);
            });

            if (data.length > 0) {
                drawPredefinedRoute(data[0].id);
            }
        })
        .catch(err => console.error('Error loading routes:', err));
}


function drawPredefinedRoute(routeId) {
    if (currentPolyline) {
        map.removeLayer(currentPolyline);
        currentPolyline = null;
    }
    if (routingControl) {
        map.removeControl(routingControl);
        routingControl = null;
    }
    resetCustomRoute();
    customRouteMode = false;
    document.getElementById('routing-tools').classList.add('hidden');

    const route = predefinedRoutes[routeId];
    if (!route) return;

    window.currentRouteId     = routeId;
    window.currentRouteLength = route.lungime_m;

    // Lungimea traseului influențează f (Bando) → reactualizăm indicatorii
    if (window.calculateIndicators) window.calculateIndicators();

    document.getElementById('route-length').textContent =
        `Lungime: ${(route.lungime_m / 1000).toFixed(2)} km`;
    document.getElementById('route-speed').textContent =
        `Viteza limită: ${route.viteza_limita_kmh} km/h`;

    if (route.start && route.end) {
        getOSRMRoute(route.start, route.end, route.culoare);
    }
}


function getOSRMRoute(start, end, color) {
    const url = `https://router.project-osrm.org/route/v1/driving/` +
                `${start[1]},${start[0]};${end[1]},${end[0]}` +
                `?overview=full&geometries=geojson`;

    fetch(url)
        .then(r => r.json())
        .then(data => {
            if (data.code === 'Ok' && data.routes.length > 0) {
                const coords = data.routes[0].geometry.coordinates.map(c => [c[1], c[0]]);
                updatePathGeometry(coords, color);
            } else {
                updatePathGeometry([start, end], color);
            }
        })
        .catch(() => updatePathGeometry([start, end], color));
}


function updatePathGeometry(coords, color) {
    if (currentPolyline) map.removeLayer(currentPolyline);
    currentPolyline = L.polyline(coords, {
        color: color || '#3b82f6', weight: 6, opacity: 0.7
    }).addTo(map);
    map.fitBounds(currentPolyline.getBounds(), { padding: [50, 50] });

    window.currentPathPoints    = coords;
    window.currentPathDistances = [0];

    let total = 0;
    for (let i = 0; i < coords.length - 1; i++) {
        const p1 = L.latLng(coords[i][0],   coords[i][1]);
        const p2 = L.latLng(coords[i+1][0], coords[i+1][1]);
        total += p1.distanceTo(p2);
        window.currentPathDistances.push(total);
    }
    window.currentRouteLength = total;

    document.getElementById('route-length').textContent =
        `Lungime: ${(total / 1000).toFixed(2)} km`;

    // Lungimea reală (OSRM/rută desenată) influențează f (Bando)
    if (window.calculateIndicators) window.calculateIndicators();
}


function getLatLngAtDistance(dist_m) {
    const pts   = window.currentPathPoints;
    const dists = window.currentPathDistances;
    if (pts.length < 2) return null;

    const L_total = dists[dists.length - 1];
    if (L_total <= 0) return null;

    let d = dist_m % L_total;
    if (d < 0) d += L_total;

    // căutare binară simplă
    let lo = 0, hi = dists.length - 1;
    while (lo < hi - 1) {
        const mid = (lo + hi) >> 1;
        if (dists[mid] <= d) lo = mid;
        else hi = mid;
    }

    const d1 = dists[lo];
    const d2 = dists[lo + 1];
    const p1 = pts[lo];
    const p2 = pts[lo + 1];

    const ratio = (d2 === d1) ? 0 : (d - d1) / (d2 - d1);
    return [
        p1[0] + (p2[0] - p1[0]) * ratio,
        p1[1] + (p2[1] - p1[1]) * ratio
    ];
}

window.getLatLngAtDistance = getLatLngAtDistance;


// Actualizează markerii vehiculelor pe hartă din starea curentă.
// Apelat din socket.js prin window.updateRouteCars.
function updateRouteCars(state) {
    if (!map) return;
    const pozitii_km = state.pozitii_km;
    const viteze_kmh = state.viteze_kmh;

    // Adăugăm markeri lipsă
    while (carMarkers.length < pozitii_km.length) {
        const m = L.circleMarker([46.77, 23.60], {
            radius: 5,
            color: '#1e293b',
            weight: 1,
            fillColor: '#10b981',
            fillOpacity: 0.95
        });
        m.addTo(map);
        carMarkers.push(m);
    }

    // Eliminăm cei în plus
    while (carMarkers.length > pozitii_km.length) {
        const m = carMarkers.pop();
        if (m) map.removeLayer(m);
    }

    // Actualizăm pozițiile și culorile
    for (let i = 0; i < pozitii_km.length; i++) {
        const dist_m = pozitii_km[i] * 1000;
        const latlng = getLatLngAtDistance(dist_m);
        if (latlng) {
            carMarkers[i].setLatLng(latlng);
            carMarkers[i].setStyle({ fillColor: _speedColorHex(viteze_kmh[i]) });
        }
    }
}

function clearCarMarkers() {
    for (const m of carMarkers) {
        if (m && map) map.removeLayer(m);
    }
    carMarkers = [];
}

function _speedColorHex(v_kmh) {
    const v = Math.max(0, Math.min(50, v_kmh));
    if (v < 25) {
        const t = v / 25;
        return _lerp('#ef4444', '#fbbf24', t);
    } else {
        const t = (v - 25) / 25;
        return _lerp('#fbbf24', '#10b981', t);
    }
}

function _lerp(c1, c2, t) {
    const a = _hex(c1), b = _hex(c2);
    const r = Math.round(a.r + (b.r - a.r) * t);
    const g = Math.round(a.g + (b.g - a.g) * t);
    const bb = Math.round(a.b + (b.b - a.b) * t);
    return `rgb(${r},${g},${bb})`;
}

function _hex(h) {
    const v = h.replace('#', '');
    return {
        r: parseInt(v.substring(0, 2), 16),
        g: parseInt(v.substring(2, 4), 16),
        b: parseInt(v.substring(4, 6), 16),
    };
}

window.updateRouteCars   = updateRouteCars;
window.clearCarMarkers   = clearCarMarkers;


function enableCustomRouteMode() {
    customRouteMode = true;
    if (currentPolyline) {
        map.removeLayer(currentPolyline);
        currentPolyline = null;
    }
    document.getElementById('routing-tools').classList.remove('hidden');
    resetCustomRoute();
}

function resetCustomRoute() {
    if (startMarker)    { map.removeLayer(startMarker);  startMarker = null; }
    if (endMarker)      { map.removeLayer(endMarker);    endMarker   = null; }
    if (routingControl) { map.removeControl(routingControl); routingControl = null; }
}

// Anuleaza modul de desenare ruta (apelat la Start Simulare).
function cancelCustomRouteMode() {
    if (!customRouteMode) return;
    customRouteMode = false;
    const tools = document.getElementById('routing-tools');
    if (tools) tools.classList.add('hidden');
    // Pastram traseul deja acceptat; stergem doar markerii de desenare.
    resetCustomRoute();
}
window.cancelCustomRouteMode = cancelCustomRouteMode;

function calculateCustomRoute() {
    if (!startMarker || !endMarker) return;
    if (routingControl) map.removeControl(routingControl);

    routingControl = L.Routing.control({
        waypoints: [startMarker.getLatLng(), endMarker.getLatLng()],
        routeWhileDragging: false,
        show: false,
        addWaypoints: false,
        lineOptions: { styles: [{ color: '#ef4444', opacity: 0.8, weight: 6 }] }
    }).addTo(map);

    routingControl.on('routesfound', function (e) {
        const route = e.routes[0];
        const coords = route.coordinates.map(c => [c.lat, c.lng]);
        updatePathGeometry(coords, '#ef4444');

        document.getElementById('route-length').textContent =
            `Lungime: ${(route.summary.totalDistance / 1000).toFixed(2)} km`;
        document.getElementById('route-speed').textContent = `Viteza limită: 50 km/h`;
    });
}


document.addEventListener('DOMContentLoaded', () => {
    if (!document.getElementById('map')) return;

    initMap();

    document.getElementById('traseu-select').addEventListener('change', (e) => {
        drawPredefinedRoute(e.target.value);
    });

    document.getElementById('btn-draw-route').addEventListener('click', () => {
        enableCustomRouteMode();
    });

    document.getElementById('btn-cancel-route').addEventListener('click', () => {
        customRouteMode = false;
        document.getElementById('routing-tools').classList.add('hidden');
        const select = document.getElementById('traseu-select');
        drawPredefinedRoute(select.value);
    });

    document.getElementById('btn-accept-route').addEventListener('click', () => {
        if (window.currentPathPoints.length > 0) {
            customRouteMode = false;
            document.getElementById('routing-tools').classList.add('hidden');
        } else {
            alert('Te rog plasează markerii Start și End pe hartă.');
        }
    });
});
