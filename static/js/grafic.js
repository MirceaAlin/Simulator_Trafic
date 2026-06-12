// static/js/grafic.js
// Două grafice:
//   1. Evoluția vitezei (min / medie / max) cu tooltip
//   2. Diagrama spațiu-timp — afișează doar ultimele NUM_LAST_CARS mașini
//
// Axa de timp afișată în format "Mm SSs" (minute și secunde).

let speedChart = null;
let stChart    = null;

const ST_WINDOW_S    = 60;     // fereastră spațiu-timp (s simulat)
const MAX_PTS_SPEED  = 300;    // puncte pe graficul de viteză
const NUM_LAST_CARS  = 3;      // ultimele N mașini pe diagrama spațiu-timp

// Buffer pentru diagrama spațiu-timp
let stBuffer = [];   // [{ t, pozitii: number[] }]

// Pentru fiecare mașină afișată: momentul primei treceri prin km 0
// (când e prima dată „eligibilă" să apară pe grafic). Persistent între
// reconstrucții, se resetează doar la pornirea unei simulări noi.
let entryTimes = {};       // { carIdx: t_entry }
let lastSeenPoz = {};      // { carIdx: ultima poziție văzută }

// Pentru detectarea pornirii unei simulări noi
let lastSimTime = -1;


// Formatare timp: secunde -> "Mm SSs" (de ex. "1m 23s")
function formatTime(t_s) {
    const m = Math.floor(t_s / 60);
    const s = Math.floor(t_s % 60);
    return `${m}m ${s.toString().padStart(2, '0')}s`;
}


function initCharts() {
    const ctxSpeed = document.getElementById('chart-viteza');
    const ctxST    = document.getElementById('chart-spatiu-timp');
    if (!ctxSpeed || !ctxST) return;

    // --- Grafic viteză: max + medie + min cu zone umplute ---
    speedChart = new Chart(ctxSpeed, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Max',
                    data: [],
                    borderColor: '#ef4444',
                    backgroundColor: 'rgba(239,68,68,0.08)',
                    borderWidth: 1.5,
                    fill: false,
                    tension: 0.3,
                    pointRadius: 0,
                    pointHoverRadius: 4
                },
                {
                    label: 'Medie',
                    data: [],
                    borderColor: '#2563eb',
                    backgroundColor: 'rgba(37,99,235,0.12)',
                    borderWidth: 2,
                    fill: '-1',
                    tension: 0.3,
                    pointRadius: 0,
                    pointHoverRadius: 4
                },
                {
                    label: 'Min',
                    data: [],
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16,185,129,0.08)',
                    borderWidth: 1.5,
                    fill: '-1',
                    tension: 0.3,
                    pointRadius: 0,
                    pointHoverRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: true, position: 'bottom' },
                title:  { display: true, text: 'Evoluția vitezei (km/h)' },
                tooltip: {
                    enabled: true,
                    callbacks: {
                        title: function (items) {
                            if (!items.length) return '';
                            return `t = ${items[0].label}`;
                        },
                        label: function (ctx) {
                            return `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)} km/h`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    title: { display: true, text: 'Timp simulat' },
                    ticks: { maxTicksLimit: 7, autoSkip: true }
                },
                y: {
                    min: 0,
                    suggestedMax: 55,
                    title: { display: true, text: 'Viteză (km/h)' }
                }
            }
        }
    });

    // --- Diagrama spațiu-timp: linii continue pentru ultimele NUM_LAST_CARS mașini ---
    stChart = new Chart(ctxST, {
        type: 'line',
        data: { datasets: [] },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            interaction: { mode: 'nearest', axis: 'x', intersect: false },
            plugins: {
                legend: { display: true, position: 'bottom' },
                title:  {
                    display: true,
                    text: 'Diagrama spațiu-timp a 3 mașini consecutive'
                },
                tooltip: {
                    enabled: true,
                    mode: 'nearest',
                    axis: 'x',
                    intersect: false,
                    callbacks: {
                        title: function (items) {
                            if (!items.length) return '';
                            return `t = ${formatTime(items[0].parsed.x)}`;
                        },
                        label: function (ctx) {
                            return `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(2)} km`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    type: 'linear',
                    title: { display: true, text: 'Timp simulat' },
                    ticks: {
                        callback: function (value) { return formatTime(value); },
                        maxTicksLimit: 6
                    }
                },
                y: {
                    min: 0,
                    title: { display: true, text: 'Poziție pe traseu (km)' },
                    ticks: {
                        stepSize: 0.1,                          // tick la fiecare 100m
                        callback: function (value) {
                            return value.toFixed(1) + ' km';    // ex: "0.0 km", "0.1 km"
                        }
                    }
                }
            }
        }
    });
}


function updateCharts(state) {
    if (!speedChart || !stChart) return;

    const t = state.t;

    // Detectăm dacă s-a pornit o simulare nouă (t a scăzut sau a sărit la 0)
    if (t < lastSimTime - 0.1) {
        entryTimes  = {};
        lastSeenPoz = {};
    }
    lastSimTime = t;

    // --- 1. Grafic viteză ---
    speedChart.data.labels.push(formatTime(t));
    speedChart.data.datasets[0].data.push(state.viteza_max_kmh);
    speedChart.data.datasets[1].data.push(state.viteza_medie_kmh);
    speedChart.data.datasets[2].data.push(state.viteza_min_kmh);

    if (speedChart.data.labels.length > MAX_PTS_SPEED) {
        speedChart.data.labels.shift();
        speedChart.data.datasets.forEach(ds => ds.data.shift());
    }
    speedChart.update('none');

    // --- 2. Buffer spațiu-timp ---
    stBuffer.push({ t, pozitii: state.pozitii_km });

    const tMin = t - ST_WINDOW_S;
    while (stBuffer.length > 0 && stBuffer[0].t < tMin) {
        stBuffer.shift();
    }

    // --- 3. Detectăm prima trecere prin km 0 pentru fiecare mașină ---
    // (urmărit per frame, NU doar în fereastra de buffer)
    const L_km = (window.currentRouteLength || 5000) / 1000.0;
    const numCars = state.pozitii_km.length;
    const startIdx = Math.max(0, numCars - NUM_LAST_CARS);

    for (let carIdx = startIdx; carIdx < numCars; carIdx++) {
        const pozCurent = state.pozitii_km[carIdx];
        const pozPrev   = lastSeenPoz[carIdx];

        // Wrap-around: poziția a scăzut brusc cu mai mult de L/2
        if (pozPrev !== undefined && pozCurent < pozPrev - L_km / 2) {
            // Prima trecere prin km 0?
            if (entryTimes[carIdx] === undefined) {
                entryTimes[carIdx] = t;
            }
        }
        lastSeenPoz[carIdx] = pozCurent;
    }

    _rebuildSTChart(numCars);
}


// Reconstruieste diagrama spatiu-timp pentru ultimele NUM_LAST_CARS masini.
// La trecerea de capatul circuitului linia se intrerupe si reincepe de jos.
function _rebuildSTChart(numCars) {
    if (!stChart) return;

    const startIdx = Math.max(0, numCars - NUM_LAST_CARS);

    // indices ordonate de la mașina din FRUNTE (cel mai mare carIdx, cea mai
    // avansată pe traseu) spre mașina din SPATE (cel mai mic carIdx).
    // Astfel mașina conducătoare apare prima în legendă/tooltip și e numerotată #1.
    const indices = [];
    for (let i = numCars - 1; i >= startIdx; i--) {
        indices.push(i);
    }
    // indices = [49, 48, 47]  → #1 (frunte/verde), #2, #3 (spate)

    // (Re)inițializăm dataset-urile dacă s-a schimbat numărul de mașini afișate
    if (stChart.data.datasets.length !== indices.length) {
        stChart.data.datasets = indices.map((carIdx, i) => {
            // Paletă: #1 frunte = turcoaz, #2 = portocaliu, #3 = magenta
            const palette = ['#03fcd7', '#fca103', '#ec03fc', '#7c3aed', '#65a30d'];
            const color = palette[i % palette.length];
            return {
                label: `Mașina #${i + 1}`,   // numerotare relativă: #1 = frunte
                data: [],
                borderColor:     color,
                backgroundColor: color,
                pointRadius: 0,
                pointHoverRadius: 5,
                showLine: true,
                spanGaps: false,   // întrerupe linia la null (wrap-around)
                borderWidth: 2,
                tension: 0.2
            };
        });
    }

    // Lungimea traseului (km)
    const L_km = (window.currentRouteLength || 5000) / 1000.0;

    // Axa Y DINAMICĂ: zoom pe kilometrul curent al mașinii din spate (cea care
    // intră ultima pe traseu), dar limitat la lungimea reală a traseului.
    // Ex: dacă traseul are 1.9 km, axa nu trece de 1.9 (nu merge până la 2.0).
    let yMin = 0;
    let yMax = Math.min(1, L_km);   // implicit primul km (sau tot traseul dacă < 1km)

    const latestFrame = stBuffer[stBuffer.length - 1];

    // Mașina de referință: cea din spate (ultima din indices care a intrat)
    let pozReferinta = null;
    for (let j = indices.length - 1; j >= 0; j--) {
        const carIdx = indices[j];
        if (entryTimes[carIdx] !== undefined &&
            carIdx < latestFrame.pozitii.length) {
            pozReferinta = latestFrame.pozitii[carIdx];
            break;
        }
    }

    if (pozReferinta !== null) {
        yMin = Math.floor(pozReferinta);
        yMax = yMin + 1;
        // Limităm la lungimea reală a traseului — nu depășim capătul
        if (yMax > L_km) {
            yMax = L_km;
            yMin = Math.max(0, Math.floor(L_km * 10) / 10 - 1);
            // dacă intervalul devine prea mic, îl forțăm la cel puțin ultima zonă
            if (yMax - yMin < 0.3) {
                yMin = Math.max(0, yMax - 1);
            }
        }
    }

    stChart.options.scales.y.min = yMin;
    stChart.options.scales.y.max = yMax;

    // Reumplem datele
    stChart.data.datasets.forEach(ds => { ds.data = []; });

    if (stBuffer.length === 0) {
        stChart.update('none');
        return;
    }

    // Pentru fiecare mașină afișată: afișăm DOAR frame-urile începând cu
    // primul moment când a trecut prin km 0 (stocat în entryTimes).
    // Astfel toate liniile pornesc din colțul stânga-jos al graficului.
    // Dacă mașina face un nou tur în interiorul ferestrei, întrerupem linia
    // și o reîncepe de jos.
    indices.forEach((carIdx, i) => {
        const tEntry = entryTimes[carIdx];

        // Mașina nu a ajuns încă la km 0 → nu o afișăm
        if (tEntry === undefined) return;

        let pozPrev = null;
        let firstFrameAfterEntry = true;

        for (const frame of stBuffer) {
            if (carIdx >= frame.pozitii.length) continue;

            // Sărim peste frame-urile dinainte ca mașina să ajungă la km 0
            if (frame.t < tEntry) {
                pozPrev = frame.pozitii[carIdx];
                continue;
            }

            const pozRaw = frame.pozitii[carIdx];

            // Wrap-around în interiorul ferestrei (alt tur) → întrerupere linie
            if (!firstFrameAfterEntry &&
                pozPrev !== null &&
                pozRaw < pozPrev - L_km / 2) {
                stChart.data.datasets[i].data.push({ x: frame.t, y: null });
            }

            stChart.data.datasets[i].data.push({
                x: frame.t,
                y: pozRaw
            });

            pozPrev = pozRaw;
            firstFrameAfterEntry = false;
        }
    });

    stChart.update('none');
}


function resetCharts() {
    stBuffer    = [];
    entryTimes  = {};
    lastSeenPoz = {};
    lastSimTime = -1;

    if (speedChart) {
        speedChart.data.labels = [];
        speedChart.data.datasets.forEach(ds => { ds.data = []; });
        speedChart.update();
    }
    if (stChart) {
        stChart.data.datasets = [];
        stChart.update();
    }
}

window.updateCharts = updateCharts;
window.resetCharts  = resetCharts;

document.addEventListener('DOMContentLoaded', initCharts);
