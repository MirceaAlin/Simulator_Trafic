"""
Modelul Bando et al. (1995): Optimal Velocity Model (OVM).

Ecuatia de miscare:
    x''_n = a * (V(dx_n) - v_n)

Fiecare sofer accelereaza spre o "viteza optima" V care depinde de
distanta dx pana la masina din fata. Functia folosita aici:

    V(dx) = V_max / (1 + tanh(2)) * (tanh(dx/scale - 2) + tanh(2))
    cu scale = b/2 si b = L/N (distanta de echilibru)

Proprietati: V(0) = 0, V(b) ~ V_max/2 (~25 km/h), V(inf) = V_max (50 km/h).

Conditia de instabilitate (Bando 1995): fluxul uniform devine instabil cand

    f = V'(b) > a/2

unde a este sensibilitatea soferului. f creste cand traficul e mai dens
(b mai mic), deci ambuteiajele apar la N mare. Practic, ca sa se vada
clar ambuteiaje stop-and-go e nevoie de N >= 75-100.

Referinta: Bando, Hasebe, Nakayama, Shibata, Sugiyama (1995), Dynamical
Model of Traffic Congestion and Numerical Simulation. Phys. Rev. E 51(2).
"""

import numpy as np

V_MAX_MS   = 50.0 / 3.6           # 50 km/h in m/s
_1_P_TANH2 = 1.0 + np.tanh(2.0)   # constanta din formula, ~1.9640


class SimulatorBando:
    """Simuleaza N masini pe un circuit de lungime L dupa modelul Bando."""

    def __init__(self, N, L, a=1.0, dt=0.05):
        """
        N:  numarul de vehicule
        L:  lungimea traseului (m)
        a:  sensibilitatea soferului (1/s)
        dt: pasul de integrare (s)
        """
        self.N  = N
        self.L  = L
        self.a  = a
        self.dt = dt

        self.b = L / N                # distanta de echilibru (m)
        self._scale = self.b / 2.0    # la dx = b argumentul tanh devine 0

        # Derivata functiei de viteza optima in punctul de echilibru.
        self.f = V_MAX_MS / (self._scale * _1_P_TANH2)

        self._initializare_uniforma()
        self.t = 0.0

    
    def _V_optimal(self, dx):
        """Viteza optima pentru o distanta dx pana la masina din fata."""
        u = dx / self._scale - 2.0
        return (V_MAX_MS / _1_P_TANH2) * (np.tanh(u) + np.tanh(2.0))

    
    def _initializare_uniforma(self):
        """Masini la distante egale, toate cu viteza de echilibru V(b)."""
        self.x = np.array([i * self.b for i in range(self.N)], dtype=np.float64)
        self.v_initial = float(self._V_optimal(self.b))
        self.v = np.full(self.N, self.v_initial, dtype=np.float64)

    
    def _calculeaza_acceleratii(self, x, v):
        """Acceleratia fiecarei masini: a * (V(dx) - v).

        Traseul e circular, deci distanta se corecteaza cu L cand masina
        din fata a trecut deja de km 0.
        """
        acc = np.empty(self.N, dtype=np.float64)
        for n in range(self.N):
            n_fata = (n + 1) % self.N
            dx = x[n_fata] - x[n]
            if dx <= 0:
                dx += self.L
            if dx < 0.1:
                dx = 0.1   # evitam impartiri/valori extreme la bara in bara
            acc[n] = self.a * (self._V_optimal(dx) - v[n])
        return acc

    
    def step(self):
        """Avanseaza simularea cu un pas dt (schema RK4 clasica)."""
        dt, x, v = self.dt, self.x, self.v

        a1 = self._calculeaza_acceleratii(x, v)
        k1x, k1v = v.copy(), a1

        x2 = x + 0.5*dt*k1x;  v2 = v + 0.5*dt*k1v
        a2 = self._calculeaza_acceleratii(x2, v2)
        k2x, k2v = v2, a2

        x3 = x + 0.5*dt*k2x;  v3 = v + 0.5*dt*k2v
        a3 = self._calculeaza_acceleratii(x3, v3)
        k3x, k3v = v3, a3

        x4 = x + dt*k3x;      v4 = v + dt*k3v
        a4 = self._calculeaza_acceleratii(x4, v4)
        k4x, k4v = v4, a4

        self.x = x + (dt/6.0)*(k1x + 2*k2x + 2*k3x + k4x)
        self.v = v + (dt/6.0)*(k1v + 2*k2v + 2*k3v + k4v)

        # Masinile nu merg cu spatele in acest model.
        self.v = np.maximum(self.v, 0.0)
        # Traseul e circular: pozitiile raman in [0, L).
        self.x = np.mod(self.x, self.L)

        self.t += dt

    
    def aplica_perturbatie(self, indice_vehicul, delta_v):
        """Schimba viteza unei masini cu delta_v m/s (negativ = franare).

        Rezultatul ramane intre 0 si V_max.
        """
        if 0 <= indice_vehicul < self.N:
            self.v[indice_vehicul] = float(np.clip(
                self.v[indice_vehicul] + delta_v, 0.0, V_MAX_MS
            ))

    
    def get_stare(self):
        """Starea curenta a simularii (unitati SI)."""
        distante = np.empty(self.N)
        for n in range(self.N):
            n_fata = (n + 1) % self.N
            dx = self.x[n_fata] - self.x[n]
            if dx <= 0:
                dx += self.L
            distante[n] = dx

        prag = self.a / 2.0

        return {
            "t":            self.t,
            "pozitii":      self.x.tolist(),
            "viteze":       self.v.tolist(),
            "distante":     distante.tolist(),
            "viteza_medie": float(np.mean(self.v)),
            "viteza_min":   float(np.min(self.v)),
            "viteza_max":   float(np.max(self.v)),
            "f":            float(self.f),
            "prag":         float(prag),
            "stabil":       bool(self.f < prag),
            "b":            float(self.b),
        }

    def get_diagnostic_stabilitate(self):
        """Un rand de text care spune in ce regim e simularea."""
        f, prag = self.f, self.a / 2.0
        if f < prag * 0.9:
            return (f"STABIL (f={f:.3f} < a/2={prag:.3f}, "
                    f"margine {(prag-f)/prag*100:.1f}%)")
        elif f < prag * 1.1:
            return f"MARGINAL (f={f:.3f} ~ a/2={prag:.3f})"
        else:
            return (f"INSTABIL (f={f:.3f} > a/2={prag:.3f}, "
                    f"raport 2f/a = {f/prag:.2f}x)")
