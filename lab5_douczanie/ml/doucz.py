"""Laboratorium 5, zadanie 4: douczanie w kontenerze -- model L4 bez zmian, douczanie (fine-tuning) i trening od zera.

Dane: Twoje serie z Laboratorium 4 (ml/dane/*.log). Dryf pogody symulujemy jak na ESP32: każde okno po kalibracji
ma średnie ciśnienie przesunięte o DRYF Pa. Pytanie: ile nowych okien z etykietą potrzeba, żeby model znów działał,
i co się wtedy dzieje ze starymi warunkami (zapominanie)?

Uruchomienie (WSL, katalog ml/, najpierw trening.py z Laboratorium 5 -- tworzy model_l4.keras):
    docker run --rm -v "$PWD":/ml -w /ml tensorflow/tensorflow:2.18.0 python doucz.py -10
"""
import glob, os, sys
import numpy as np

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
import tensorflow as tf

sys.stdout.reconfigure(encoding="utf-8")
DRYF = float(sys.argv[1]) if len(sys.argv) > 1 else -10.0
OKNO, KROK, N_ODNIESIENIE, MARGINES = 10, 5, 50, 10      # jak w trening.py
ILE_NOWYCH = [4, 8, 16, 32, 64]                           # nowe okna z etykietą (po połowie z każdej klasy)
EPOKI = 30


def wczytaj(plik):
    w = []
    for linia in open(plik, encoding="utf-8", errors="ignore"):
        pola = linia.strip().split(",")
        if len(pola) == 4:
            try:
                w.append([float(x) for x in pola])
            except ValueError:
                pass
    return np.array(w)


# --- okna i cechy dokładnie jak w trening.py ---
X, y, czesc = [], [], []
for plik in sorted(glob.glob("dane/*.log")):
    d = wczytaj(plik)
    p, b = d[:, 1], d[:, 3].astype(int)
    p_ref = p[:N_ODNIESIENIE].mean()
    starts = list(range(N_ODNIESIENIE, len(d) - OKNO + 1, KROK))
    zmiany = np.flatnonzero(np.diff(b) != 0)
    for k, s in enumerate(starts):
        if np.any((zmiany >= s - MARGINES) & (zmiany < s + OKNO + MARGINES)):
            continue
        okno = p[s:s + OKNO]
        X.append([okno.mean() - p_ref, okno.std()])
        y.append(int(b[s]))
        czesc.append("test" if k >= 0.7 * len(starts) else "trening")
X, y, czesc = np.array(X, dtype=np.float32), np.array(y), np.array(czesc)

n = np.load("normalizacja.npz")
srednia, odch = n["srednia"], n["odch"]
norm = lambda a: (a - srednia) / odch
przesun = lambda a: a + np.array([DRYF, 0.0], dtype=np.float32)   # dryf: tylko średnia, rozrzut bez zmian

Xtr, ytr = X[czesc == "trening"], y[czesc == "trening"]
Xte, yte = X[czesc == "test"], y[czesc == "test"]
stary_test = norm(Xte)                 # warunki z Laboratorium 4
nowy_test = norm(przesun(Xte))         # te same okna po dryfie
nowy_tren = norm(przesun(Xtr))         # z tego „zbieramy” nowe etykiety

l4 = tf.keras.models.load_model("model_l4.keras")
traf = lambda m, Xs, ys: float((m.predict(Xs, verbose=0).argmax(axis=1) == ys).mean())


def nowy_model():
    return tf.keras.Sequential([tf.keras.layers.Input(shape=(2,)),
                                tf.keras.layers.Dense(4, activation="relu"),
                                tf.keras.layers.Dense(2, activation="softmax")])


def ucz(model, Xn, yn, epoki):
    model.compile(optimizer=tf.keras.optimizers.Adam(0.01), loss="sparse_categorical_crossentropy")
    model.fit(Xn, yn, epochs=epoki, batch_size=8, verbose=0)
    return model


print(f"Dryf {DRYF:+.0f} Pa. Okna testowe: {len(yte)} (leży {np.sum(yte == 0)}, podniesiony {np.sum(yte == 1)})")
print(f"Model L4 bez zmian: stare warunki {traf(l4, stary_test, yte):.3f}, po dryfie {traf(l4, nowy_test, yte):.3f}\n")
print(f"{'nowych okien':>12} | {'douczanie L4':>14} | {'od zera':>10} | {'douczanie L4':>14} | {'od zera':>10}")
print(f"{'':>12} | {'po dryfie':>14} | {'po dryfie':>10} | {'stare warunki':>14} | {'stare':>10}")
wyniki = []
for ile in ILE_NOWYCH:
    tf.keras.utils.set_random_seed(1)
    tf.config.experimental.enable_op_determinism()
    rng = np.random.default_rng(ile)
    wyb = np.concatenate([rng.choice(np.flatnonzero(ytr == k), ile // 2, replace=False) for k in (0, 1)])
    Xn, yn = nowy_tren[wyb], ytr[wyb]
    dou = tf.keras.models.clone_model(l4)
    dou.set_weights(l4.get_weights())             # start z wag L4 (fine-tuning)
    ucz(dou, Xn, yn, EPOKI)
    zer = ucz(nowy_model(), Xn, yn, EPOKI)        # start z losowych wag
    r = [ile, traf(dou, nowy_test, yte), traf(zer, nowy_test, yte), traf(dou, stary_test, yte), traf(zer, stary_test, yte)]
    wyniki.append(r)
    print(f"{ile:>12} | {r[1]:>14.3f} | {r[2]:>10.3f} | {r[3]:>14.3f} | {r[4]:>10.3f}")

np.savetxt(f"doucz_{DRYF:+.0f}.csv", np.array(wyniki), delimiter=",", fmt=["%d", "%.3f", "%.3f", "%.3f", "%.3f"],
           header="nowych_okien,douczanie_po_dryfie,od_zera_po_dryfie,douczanie_stare,od_zera_stare", comments="")
print(f"\nZapisano doucz_{DRYF:+.0f}.csv (wykres w arkuszu: trafność po dryfie w funkcji liczby nowych okien)")
