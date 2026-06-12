"""Teste pentru modelul Bando (1995)."""

import numpy as np
import pytest

from simulare.bando import V_MAX_MS, SimulatorBando


def _ruleaza(sim, secunde):
    for _ in range(int(secunde / sim.dt)):
        sim.step()



# Functia de viteza optima

def test_V_optimal_proprietati():
    sim = SimulatorBando(N=50, L=1000.0)
    # V(0) = 0: la bara in bara nu se merge.
    assert sim._V_optimal(0.0) == pytest.approx(0.0, abs=1e-12)
    # V(b) ~ V_max/2 (25 km/h, mai exact V_max*tanh2/(1+tanh2)).
    v_b = sim._V_optimal(sim.b)
    assert v_b == pytest.approx(V_MAX_MS * np.tanh(2.0) / (1 + np.tanh(2.0)))
    assert 24.0 < v_b * 3.6 < 25.0
    # V(infinit) = V_max (50 km/h).
    assert sim._V_optimal(1e9) == pytest.approx(V_MAX_MS)


def test_f_este_derivata_lui_V_in_b():
    for N, L in [(50, 1000.0), (100, 3500.0), (30, 1500.0)]:
        sim = SimulatorBando(N=N, L=L)
        h = 1e-6
        derivata = (sim._V_optimal(sim.b + h) - sim._V_optimal(sim.b - h)) / (2 * h)
        assert sim.f == pytest.approx(derivata, rel=1e-6)


def test_viteza_initiala_este_V_de_b():
    sim = SimulatorBando(N=40, L=2000.0)
    assert sim.v_initial == pytest.approx(sim._V_optimal(sim.b))
    assert np.all(sim.v == sim.v_initial)



# Fizica

def test_echilibrul_ramane_neperturbat():
    sim = SimulatorBando(N=50, L=2000.0, a=0.5)
    _ruleaza(sim, 60)
    st = sim.get_stare()
    assert st["viteza_max"] - st["viteza_min"] == pytest.approx(0.0, abs=1e-6)


def test_pozitiile_raman_pe_circuit():
    sim = SimulatorBando(N=10, L=500.0)
    _ruleaza(sim, 120)
    assert np.all(sim.x >= 0.0)
    assert np.all(sim.x < 500.0)


def test_vitezele_nu_devin_negative():
    sim = SimulatorBando(N=100, L=1000.0, a=0.3)
    sim.aplica_perturbatie(0, -sim.v[0])   # oprire completa
    _ruleaza(sim, 30)
    assert np.all(sim.v >= 0.0)


def test_caz_stabil_amortizeaza():
    sim = SimulatorBando(N=30, L=3500.0, a=1.0)   # f mult sub a/2
    assert sim.f < sim.a / 2
    sim.aplica_perturbatie(0, -4.0)
    _ruleaza(sim, 60)
    st = sim.get_stare()
    assert (st["viteza_max"] - st["viteza_min"]) * 3.6 < 1.0


def test_caz_instabil_formeaza_ambuteiaj():
    sim = SimulatorBando(N=100, L=3500.0, a=0.5)   # f > a/2
    assert sim.f > sim.a / 2
    sim.aplica_perturbatie(0, -4.0)
    _ruleaza(sim, 180)
    st = sim.get_stare()
    assert (st["viteza_max"] - st["viteza_min"]) * 3.6 > 10.0


def test_garda_pentru_distante_foarte_mici():
    # Doua masini aproape lipite: distanta se limiteaza la 0.1 m,
    # iar acceleratia ramane finita.
    sim = SimulatorBando(N=3, L=300.0)
    sim.x = np.array([0.0, 0.05, 200.0])
    acc = sim._calculeaza_acceleratii(sim.x, sim.v)
    assert np.all(np.isfinite(acc))



# Perturbatii

def test_perturbatia_se_limiteaza_la_interval():
    sim = SimulatorBando(N=10, L=500.0)
    sim.aplica_perturbatie(0, -100.0)
    assert sim.v[0] == 0.0
    sim.aplica_perturbatie(0, +100.0)
    assert sim.v[0] == pytest.approx(V_MAX_MS)


def test_perturbatia_cu_indice_invalid_e_ignorata():
    sim = SimulatorBando(N=10, L=500.0)
    v_inainte = sim.v.copy()
    sim.aplica_perturbatie(-1, -5.0)
    sim.aplica_perturbatie(10, -5.0)
    assert np.array_equal(sim.v, v_inainte)



# Starea si diagnosticul

def test_get_stare_distante_si_flag():
    sim = SimulatorBando(N=10, L=500.0, a=2.0)   # f < a/2 -> stabil
    st = sim.get_stare()
    assert st["stabil"] == bool(sim.f < sim.a / 2)
    # La echilibru toate distantele sunt b.
    assert np.allclose(st["distante"], sim.b)
    assert st["b"] == pytest.approx(50.0)
    assert st["prag"] == pytest.approx(1.0)


def test_diagnostic_toate_regimurile():
    # f depinde doar de L/N, deci alegem a in jurul lui 2f.
    sim = SimulatorBando(N=75, L=3500.0, a=1.0)
    assert sim.get_diagnostic_stabilitate().startswith("STABIL")

    marginal = SimulatorBando(N=75, L=3500.0, a=2 * sim.f)
    assert marginal.get_diagnostic_stabilitate().startswith("MARGINAL")

    instabil = SimulatorBando(N=150, L=3500.0, a=0.3)
    assert instabil.get_diagnostic_stabilitate().startswith("INSTABIL")
