# Simulator Trafic

Aplicatie web care simuleaza traficul pe trei trasee din Cluj-Napoca
folosind doua modele matematice de tip car-following: Herman (1959) si
Bando (1995). Masinile circula pe un traseu inchis (circuit), iar
utilizatorul poate regla parametrii modelelor, poate introduce
perturbatii si urmareste in timp real cum se propaga ele prin convoi.

Aplicatia a fost scrisa ca parte a unei lucrari de licenta (UBB Cluj,
Matematica-Informatica).


## Ce face

- Simuleaza N masini care se urmaresc una pe alta pe un circuit.
- Doua modele la alegere:
  - **Herman** - fiecare sofer reactioneaza la diferenta de viteza fata
    de masina din fata, dar cu o intarziere (timp de reactie).
  - **Bando** - fiecare sofer tinde spre o viteza optima care depinde de
    distanta pana la masina din fata.
- Arata pe harta (Leaflet) traseul real, calculat prin OSRM.
- Deseneaza o animatie a masinilor pe o banda de drum, colorate dupa viteza.
- Doua grafice: evolutia vitezei (min/medie/max) si o diagrama spatiu-timp
  a ultimelor trei masini.
- Un indicator de stabilitate care se actualizeaza si inainte de pornire,
  pe masura ce schimbi parametrii.


## Cerinte

- Python 3.13.
- Un browser modern.
- Conexiune la internet pentru harta (tile-uri OpenStreetMap si rutare OSRM).

Dependintele Python sunt in `requirements.txt`: Flask, Flask-SocketIO,
NumPy.


## Instalare si rulare locala

```bash
unzip Simulator_Trafic-main.zip
cd Simulator_Trafic-main
pip install -r requirements.txt
python app.py
```

Deschide `http://127.0.0.1:5001/`.

## Cum se foloseste

1. Alege un traseu din lista (sau deseneaza unul propriu pe harta cu
   butonul "Ruta noua").
2. Alege modelul: Herman sau Bando.
3. Regleaza parametrii din slidere.
4. Alege tipul de perturbatie initiala.
5. Apasa "Start Simulare". Cat timp ruleaza, coloana de configurare e
   blocata, ca sa nu modifici parametri care oricum se citesc o singura
   data, la pornire.
6. Urmaresti harta, indicatorul de stabilitate, graficul de viteza si
   diagrama spatiu-timp.
7. Poti da click pe o masina in animatie ca sa-i aplici o franare manuala.
8. Sliderul de viteza simulare (din dreapta) merge de la 1x la 10x si
   poate fi schimbat in timp ce ruleaza.


## Parametri

Herman:
- `lambda` (sensibilitate), slider 0.1 - 2.0, implicit 0.3
- `delta` (timp de reactie, secunde), slider 0.5 - 3.0, implicit 1.0

Bando:
- `a` (sensibilitate), slider 0.1 - 2.0, implicit 0.5

Comun:
- `N` (numar de masini), slider 5 - 200, implicit 50
- perturbatie initiala: niciuna / franare usoara / franare brusca /
  masina care se opreste


## Modelele matematice

### Herman (1959)

Ecuatia de miscare pentru masina n:

    M * x''_n(t) = lambda * (v_{n+1}(t - Delta) - v_n(t - Delta))

Stabilitatea fluxului depinde de un singur numar adimensional:

    C = lambda * Delta / M

Cele patru regimuri:

| Conditie            | Regim                  | Ce se vede                                  |
|---------------------|------------------------|---------------------------------------------|
| C <= 1/e (~0.368)   | stabil neoscilatoriu   | franarea se stinge lin, fara unde           |
| 1/e < C < 1/2       | stabil oscilatoriu     | unda care trece prin convoi, apoi dispare   |
| 1/2 <= C < pi/2     | asimptotic instabil    | undele cresc, diferenta max-min se mareste  |
| C >= pi/2 (~1.571)  | local instabil         | apar viteze negative = coliziuni            |

Fiind o ecuatie cu intarziere, modelul tine un istoric al vitezelor
intr-un buffer circular si citeste din el vitezele de acum Delta
secunde. Integrarea se face cu RK4; intarzierea fiind constanta pe
durata unui pas, toate cele patru etape RK4 folosesc aceleasi viteze
intarziate.

### Bando (1995)

Ecuatia de miscare:

    x''_n = a * (V(dx_n) - v_n)

unde V este viteza optima, functie de distanta dx pana la masina din fata:

    V(dx) = V_max / (1 + tanh(2)) * (tanh(dx/scale - 2) + tanh(2))

cu `scale = b/2` si `b = L/N` (distanta de echilibru). Asa, V(0) = 0,
V(b) este aproximativ V_max/2 (~25 km/h), iar V(infinit) tinde la V_max
(50 km/h).

Fluxul uniform devine instabil cand

    f = V'(b) > a/2

f depinde doar de distanta de echilibru b = L/N, deci de cate masini
sunt pe traseu. Cu cat N e mai mare (trafic mai dens), cu atat f e mai
mare si fluxul mai usor de destabilizat. Ca sa se vada clar ambuteiaje
stop-and-go e nevoie de N mare (in jur de 75-100 sau mai mult), chiar
daca matematic conditia f > a/2 e indeplinita si la N mai mic.

Integrarea se face tot cu RK4 (clasic, fara intarziere). Vitezele sunt
tinute la minim 0 (masinile nu merg cu spatele).

V_max este fixat la 50 km/h (limita urbana).


## Trasee

Toate trei pornesc dintr-un capat al orasului si se termina in acelasi
punct, in centru:

- **Calea Turzii - Centru** - dinspre sud
- **Vivo Mall - Centru** - dinspre vest (Floresti), prin Manastur
- **Iulius Mall - Centru** - dinspre est (Gheorgheni)

Coordonatele de start si final sunt in `simulare/trasee.py`. Geometria
reala a drumului se obtine in browser prin OSRM, iar lungimea afisata se
recalculeaza din ruta gasita (valoarea `lungime_m` din fisier e doar o
estimare folosita ca rezerva). Se poate desena si un traseu propriu pe
harta.

Intern se lucreaza in metri si m/s; afisarea e in km si km/h.


## Structura proiectului

```
app_final/
├── app.py                  server Flask + SocketIO, bucla de simulare
├── requirements.txt        dependinte pentru rulare
├── requirements-dev.txt    dependinte pentru teste
├── pytest.ini, .coveragerc configurare teste
├── simulare/
│   ├── herman.py           modelul Herman
│   ├── bando.py            modelul Bando
│   ├── trasee.py           cele trei trasee
│   └── utilitar.py         conversii de unitati, id de sesiune
├── static/
│   ├── css/style.css
│   └── js/
│       ├── socket.js       WebSocket + apeluri REST
│       ├── grafic.js       cele doua grafice Chart.js
│       ├── animatie.js     animatia pe canvas
│       ├── harta.js        harta Leaflet si rutarea OSRM
│       └── main.js         controale UI, slidere, indicatori
├── templates/
│   ├── base.html           navbar
│   ├── index.html          pagina Acasa
│   └── simulator.html      pagina simulatorului
└── tests/                  teste pytest
```


## API

Pagini:
- `GET /` - pagina Acasa
- `GET /simulator` - simulatorul

REST (cereri si raspunsuri JSON):
- `GET /api/trasee` - lista traseelor predefinite
- `POST /api/simulare/start` - porneste o simulare. Camp `model`, `N`,
  `traseu`, `lungime_m`, `lambda`/`delta` (Herman) sau `a` (Bando),
  `perturbatie_tip`, `sim_speed`. Intoarce `sim_id`.
- `POST /api/simulare/stop` - opreste simularea (`sim_id`)
- `POST /api/simulare/perturbatie` - franeaza o masina (`sim_id`,
  `masina_idx`, `delta_v_kmh`)
- `POST /api/simulare/viteza` - schimba viteza simularii (`sim_id`,
  `sim_speed`)

WebSocket:
- clientul trimite `subscribe_simulare` cu `sim_id` ca sa primeasca
  starea simularii lui
- serverul emite `tick` la 30 fps cu pozitiile, vitezele si datele de
  stabilitate

Toate valorile numerice primite de la client sunt limitate la intervale
rezonabile (de exemplu N intre 2 si 300). Valorile in afara intervalului
se aduc la capat, iar cele care nu sunt numere intorc eroarea 400. Numarul
de simulari care ruleaza in acelasi timp e limitat la 10.


## Cum ruleaza simularea

Fiecare simulare porneste intr-un thread separat pe server. Thread-ul
avanseaza modelul cu pasi de `dt = 0.05 s` si trimite starea la frontend
de 30 de ori pe secunda. `sim_speed` spune cate secunde simulate trec
intr-o secunda reala: la 1x simularea merge in timp real (bun pentru a
vedea propagarea perturbatiilor masina cu masina), la 10x merge rapid
(ambuteiajele Bando apar in 30-60 de secunde reale). Cand simularea e
oprita, thread-ul se termina singur si sterge sesiunea.


## Testare

Testele sunt in `tests/`, scrise cu pytest.

```bash
pip install -r requirements-dev.txt
python -m pytest --cov
```

Acopera modelele (fizica si regimurile de stabilitate), traseele,
functiile utilitare si serverul Flask (toate endpoint-urile, validarea
inputului, WebSocket-ul). Acoperirea pe codul Python este 100%.


## Note despre securitate

- Cheia secreta Flask vine din variabila de mediu `SECRET_KEY`. Daca nu e
  setata, se genereaza una aleatoare la pornire. Pentru productie trebuie
  setata una fixa:

  ```bash
  export SECRET_KEY="random-key"
  ```

- WebSocket-ul accepta implicit doar conexiuni din aceeasi origine
  (pagina servita de acest server).
- Parametrii primiti de la client sunt verificati si limitati, ca o
  cerere sa nu poata porni o simulare cu N urias si bloca serverul.