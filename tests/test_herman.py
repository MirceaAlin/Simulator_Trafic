"""Teste pentru modelul Herman (1959)."""

import numpy as np
import pytest

from simulare.herman import SimulatorHerman, V_COLIZIUNE_PRAG


def _ruleaza(sim, secunde):
    for _ in range(int(secunde / sim.dt)):
        sim.step()



# Initializare

def test_initializare():
    sim = SimulatorHerman(N=20, L=1000.0, lam=0.3, Delta=1.0, dt=0.05)
    assert sim.C == pytest.approx(0.3)
    assert sim.m_delay == 20                  # 1.0 / 0.05
    assert sim.b == pytest.approx(50.0)       # 1000 / 20
    assert np.all(sim.v == 10.0)
    # Masinile sunt la distante egale.
    assert np.allclose(np.diff(sim.x), 50.0)


def test_m_delay_minim_un_pas():
    sim = SimulatorHerman(N=5, L=500.0, Delta=0.001, dt=0.05)
    assert sim.m_delay == 1



# Fizica

def test_echilibrul_ramane_neperturbat():
    sim = SimulatorHerman(N=10, L=500.0, lam=0.3)
    _ruleaza(sim, 10)
    assert np.allclose(sim.v, 10.0)
    st = sim.get_stare()
    assert st["viteza_max"] - st["viteza_min"] == pytest.approx(0.0, abs=1e-9)


def test_pozitiile_raman_pe_circuit():
    sim = SimulatorHerman(N=10, L=500.0, lam=0.3)
    _ruleaza(sim, 60)   # 10 m/s * 60 s = 600 m > L, deci trec de km 0
    assert np.all(sim.x >= 0.0)
    assert np.all(sim.x < 500.0)


def test_regim_stabil_amortizeaza():
    sim = SimulatorHerman(N=20, L=1000.0, lam=0.3, Delta=1.0)
    sim.aplica_perturbatie(0, -3.0)
    amp_initial = np.max(np.abs(sim.v - 10.0))
    _ruleaza(sim, 60)
    amp_final = np.max(np.abs(sim.v - 10.0))
    assert amp_final < amp_initial / 2
    assert not sim.get_stare()["coliziuni"]


def test_regim_asimptotic_instabil_creste():
    sim = SimulatorHerman(N=20, L=1000.0, lam=0.8, Delta=1.0)
    sim.aplica_perturbatie(0, -3.0)
    _ruleaza(sim, 30)
    amp_30 = np.max(np.abs(sim.v - 10.0))
    _ruleaza(sim, 30)
    amp_60 = np.max(np.abs(sim.v - 10.0))
    assert amp_60 > amp_30 > 3.0


def test_regim_critic_produce_coliziuni():
    sim = SimulatorHerman(N=20, L=1000.0, lam=1.8, Delta=1.0)
    sim.aplica_perturbatie(0, -6.0)
    _ruleaza(sim, 30)
    st = sim.get_stare()
    assert st["coliziuni"] is True
    assert st["nr_coliziuni"] > 0
    # Coliziune inseamna viteza sub prag la un moment dat.
    assert np.any(sim.coliziuni)
    assert V_COLIZIUNE_PRAG < 0



# Perturbatii

def test_perturbatia_nu_duce_sub_zero_in_regim_stabil():
    sim = SimulatorHerman(N=10, L=500.0, lam=0.3)   # C < pi/2
    sim.aplica_perturbatie(0, -100.0)
    assert sim.v[0] == 0.0


def test_perturbatia_permite_negativ_in_regim_critic():
    sim = SimulatorHerman(N=10, L=500.0, lam=1.8)   # C >= pi/2
    sim.aplica_perturbatie(0, -100.0)
    assert sim.v[0] < 0.0


def test_perturbatia_cu_indice_invalid_e_ignorata():
    sim = SimulatorHerman(N=10, L=500.0)
    v_inainte = sim.v.copy()
    sim.aplica_perturbatie(-1, -5.0)
    sim.aplica_perturbatie(10, -5.0)
    assert np.array_equal(sim.v, v_inainte)



# Starea si diagnosticul

def test_get_stare_flaguri():
    flaguri = {
        0.3:  (True, True, True),     # local, asimptotic, neoscilator
        0.45: (True, True, False),
        0.8:  (True, False, False),
        1.8:  (False, False, False),
    }
    for lam, (loc, asim, neosc) in flaguri.items():
        st = SimulatorHerman(N=5, L=500.0, lam=lam).get_stare()
        assert st["stabil_local"] is loc
        assert st["stabil_asimptotic"] is asim
        assert st["stabil_neoscilator"] is neosc


def test_diagnostic_toate_regimurile():
    cazuri = {
        0.3:   "STABIL NEOSCILATORIU",
        0.45:  "STABIL OSCILATORIU",
        0.505: "MARGINAL",
        0.8:   "ASIMPTOTIC INSTABIL",
        1.8:   "LOCAL INSTABIL",
    }
    for lam, text in cazuri.items():
        diag = SimulatorHerman(N=5, L=500.0, lam=lam).get_diagnostic_stabilitate()
        assert diag.startswith(text)
