"""
Modelul Herman et al. (1959): car-following cu timp de reactie.

Ecuatia de miscare:
    M * x''_n(t) = lambda * (v_{n+1}(t - Delta) - v_n(t - Delta))

Fiecare sofer accelereaza proportional cu diferenta de viteza fata de
masina din fata, dar vede aceasta diferenta cu o intarziere Delta
(timpul de reactie). Stabilitatea depinde de un singur numar:

    C = lambda * Delta / M

    C <= 1/e (~0.368)   stabil neoscilatoriu (franarea se stinge lin)
    1/e < C < 1/2       stabil oscilatoriu (unde amortizate)
    1/2 <= C < pi/2     asimptotic instabil (undele cresc)
    C >= pi/2 (~1.571)  local instabil (viteze negative = coliziuni)

Referinta: Herman, Montroll, Potts, Rothery (1959), Traffic Dynamics:
Analysis of Stability in Car-Following. Operations Research 7(1), 86-106.
"""

import numpy as np

# Sub acest prag, viteza negativa e considerata coliziune.
V_COLIZIUNE_PRAG = -0.1


class SimulatorHerman:
    """Simuleaza N masini pe un circuit de lungime L dupa modelul Herman.

    Ecuatia e una cu intarziere (DDE), asa ca pastram un istoric al
    vitezelor intr-un buffer circular si citim din el vitezele de acum
    Delta secunde.
    """

    def __init__(self, N, L, M=1.0, lam=0.3, Delta=1.0, dt=0.05):
        """
        N:     numarul de vehicule
        L:     lungimea traseului (m)
        M:     masa (normalizata la 1)
        lam:   sensibilitatea soferului (1/s)
        Delta: timpul de reactie (s)
        dt:    pasul de integrare (s)
        """
        self.N     = N
        self.L     = L
        self.M     = M
        self.lam   = lam
        self.Delta = Delta
        self.dt    = dt

        self.C = (lam * Delta) / M
        # Cati pasi dt incap in intarzierea Delta.
        self.m_delay = max(1, int(round(Delta / dt)))

        # Buffer circular cu vitezele din ultimii pasi.
        self.history_size = self.m_delay + 100
        self.istoric_viteze = np.zeros((self.history_size, N), dtype=np.float64)
        self.idx_curent = 0

        # Ce masini au avut viteza negativa (coliziune).
        self.coliziuni = np.zeros(N, dtype=bool)

        self._initializare_uniforma()
        self.t = 0.0

    
    def _initializare_uniforma(self):
        """Masini la distante egale, toate cu 10 m/s (36 km/h)."""
        self.b = self.L / self.N
        self.v_initial = 10.0

        self.x = np.array([i * self.b for i in range(self.N)], dtype=np.float64)
        self.v = np.full(self.N, self.v_initial, dtype=np.float64)

        # Umplem istoricul cu starea de echilibru, ca primele citiri
        # intarziate sa fie corecte.
        self.istoric_viteze[:] = self.v_initial

    
    def _get_viteza_intarziata(self):
        """Vitezele de acum Delta secunde, citite din buffer."""
        idx = (self.idx_curent - self.m_delay) % self.history_size
        return self.istoric_viteze[idx].copy()

    
    def _calculeaza_acceleratii(self, v_intarziate):
        """Acceleratia fiecarei masini fata de masina din fata ei.

        Traseul e circular, deci masina N-1 urmareste masina 0.
        """
        acc = np.empty(self.N, dtype=np.float64)
        for n in range(self.N):
            n_fata = (n + 1) % self.N
            v_rel  = v_intarziate[n_fata] - v_intarziate[n]
            acc[n] = (self.lam / self.M) * v_rel
        return acc

    
    def step(self):
        """Avanseaza simularea cu un pas dt (schema RK4).

        Acceleratia depinde doar de vitezele de acum Delta secunde, care
        sunt aceleasi pe durata unui pas, deci toate cele 4 etape RK4
        folosesc aceleasi viteze intarziate.
        """
        # Salvam vitezele curente in istoric inainte de calcul.
        self.istoric_viteze[self.idx_curent] = self.v.copy()
        v_int = self._get_viteza_intarziata()

        dt = self.dt
        v  = self.v

        a1  = self._calculeaza_acceleratii(v_int)
        k1x = v.copy()
        k1v = a1

        v2  = v + 0.5*dt*k1v
        a2  = self._calculeaza_acceleratii(v_int)
        k2x = v2
        k2v = a2

        v3  = v + 0.5*dt*k2v
        a3  = self._calculeaza_acceleratii(v_int)
        k3x = v3
        k3v = a3

        v4  = v + dt*k3v
        a4  = self._calculeaza_acceleratii(v_int)
        k4x = v4
        k4v = a4

        self.x += (dt/6.0) * (k1x + 2*k2x + 2*k3x + k4x)
        self.v += (dt/6.0) * (k1v + 2*k2v + 2*k3v + k4v)

        # In modelul Herman viteza negativa inseamna coliziune.
        self.coliziuni |= (self.v < V_COLIZIUNE_PRAG)

        # Traseul e circular: pozitiile raman in [0, L).
        self.x = np.mod(self.x, self.L)

        self.t += dt
        self.idx_curent = (self.idx_curent + 1) % self.history_size

    
    def aplica_perturbatie(self, indice_vehicul, delta_v):
        """Schimba viteza unei masini cu delta_v m/s (negativ = franare).

        Sub pragul critic C < pi/2 nu lasam viteza sa devina negativa.
        Peste prag o lasam, ca sa se vada coliziunile.
        """
        if 0 <= indice_vehicul < self.N:
            self.v[indice_vehicul] += delta_v
            if self.C < np.pi / 2:
                self.v[indice_vehicul] = max(0.0, self.v[indice_vehicul])

    
    def get_stare(self):
        """Starea curenta a simularii (unitati SI)."""
        return {
            "t":                  self.t,
            "pozitii":            self.x.tolist(),
            "viteze":             self.v.tolist(),
            "viteza_medie":       float(np.mean(self.v)),
            "viteza_min":         float(np.min(self.v)),
            "viteza_max":         float(np.max(self.v)),
            "C":                  float(self.C),
            "stabil_local":       bool(self.C < np.pi / 2),
            "stabil_asimptotic":  bool(self.C < 0.5),
            "stabil_neoscilator": bool(self.C <= 1.0 / np.e),
            "coliziuni":          bool(np.any(self.coliziuni)),
            "nr_coliziuni":       int(np.sum(self.coliziuni)),
        }

    def get_diagnostic_stabilitate(self):
        """Un rand de text care spune in ce regim e simularea."""
        C = self.C
        e_inv = 1.0 / np.e
        if C <= e_inv:
            return f"STABIL NEOSCILATORIU (C={C:.3f} <= 1/e={e_inv:.3f})"
        elif C < 0.5:
            return f"STABIL OSCILATORIU (C={C:.3f}, unde amortizate)"
        elif np.isclose(C, 0.5, atol=0.01):
            return f"MARGINAL (C={C:.3f} ~ 1/2)"
        elif C < np.pi / 2:
            return f"ASIMPTOTIC INSTABIL (C={C:.3f}, unde crescatoare)"
        else:
            return f"LOCAL INSTABIL (C={C:.3f} >= pi/2, posibile coliziuni)"
