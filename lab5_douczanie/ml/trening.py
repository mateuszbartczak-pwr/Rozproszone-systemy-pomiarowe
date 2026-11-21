"""Laboratorium 4: TinyML na ESP32 -- dwa stany płytki: leży / podniesiony (+ „nieznany” w firmware).
Kroki: dane -> cechy okna -> model -> trening i ocena -> kwantyzacja int8 -> eksport do model.h.
Laboratorium 5 (krok 7): ten sam model zapisany też jako float (model_float.h, do douczania na ESP32)
i jako model_l4.keras (do douczania w kontenerze, doucz.py). Trening jest deterministyczny: na tych samych
danych powstaje dokładnie ten sam model co w Laboratorium 4.

Uruchomienie w kontenerze (WSL, katalog ml/ repozytorium, bez instalowania czegokolwiek):
    docker run --rm -v "$PWD":/ml -w /ml tensorflow/tensorflow:2.18.0 python trening.py
Potrzebne tylko: numpy i tensorflow (są w obrazie).
"""
import glob, os, sys
import numpy as np

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")   # mniej komunikatów TensorFlow
import tensorflow as tf

sys.stdout.reconfigure(encoding="utf-8")   # polskie znaki także w konsoli Windows

KLASY = ["lezy", "podniesiony"]
OKNO, KROK = 10, 5          # okno 10 próbek = 1 s przy 10 Hz, nowe okno co 0,5 s
N_ODNIESIENIE = 50          # pierwsze 5 s nagrania: płytka leży, z nich poziom odniesienia
PEWNOSC_MIN = 0.75          # poniżej tej pewności firmware odpowiada „nieznany”
MARGINES = 10               # 1 s przed i po zmianie przycisku: płytka w ruchu, pomijamy w treningu

# --- Krok 1: dane -----------------------------------------------------------------------------
def wczytaj(plik):
    """Zwraca tablicę [ms, p_pa, t_c, btn]; bierze tylko linie z czterema liczbami (pomija komunikaty monitora)."""
    wiersze = []
    for linia in open(plik, encoding="utf-8", errors="ignore"):
        pola = linia.strip().split(",")
        if len(pola) == 4:
            try:
                wiersze.append([float(x) for x in pola])
            except ValueError:
                pass
    return np.array(wiersze)

# --- Krok 2: cechy okna (te same liczy firmware, funkcja cechy() w main.cpp) -----------------
def cechy(p_okno, p_ref):
    return [p_okno.mean() - p_ref,     # f0: średnie ciśnienie względem poziomu „na stole” [Pa]
            p_okno.std()]              # f1: rozrzut w oknie [Pa] -- ruch daje duży rozrzut

X, y, czesc, X_ruch = [], [], [], []
for plik in sorted(glob.glob("dane/*.log")):
    d = wczytaj(plik)
    p, b = d[:, 1], d[:, 3].astype(int)
    p_ref = p[:N_ODNIESIENIE].mean()
    starts = list(range(N_ODNIESIENIE, len(d) - OKNO + 1, KROK))
    zmiany = np.flatnonzero(np.diff(b) != 0)   # chwile wciśnięcia i puszczenia BOOT
    pominiete = 0
    for k, s in enumerate(starts):
        bo = b[s:s + OKNO]
        # okno blisko zmiany przycisku = płytka w ruchu (podnoszenie, opuszczanie): nie uczymy na nim
        if np.any((zmiany >= s - MARGINES) & (zmiany < s + OKNO + MARGINES)):
            pominiete += 1
            X_ruch.append(cechy(p[s:s + OKNO], p_ref))   # zachowujemy do sprawdzenia „nieznany”
            continue
        X.append(cechy(p[s:s + OKNO], p_ref))
        y.append(int(bo[0]))                   # 0 = leży, 1 = podniesiony (BOOT wciśnięty)
        czesc.append("test" if k >= 0.7 * len(starts) else "trening")   # podział w czasie
    print(f"{plik}: {len(d)} próbek, {len(starts)} okien, pominięte (ruch przy zmianie BOOT): {pominiete}")

X, y, czesc = np.array(X, dtype=np.float32), np.array(y), np.array(czesc)
Xtr, ytr = X[czesc == "trening"], y[czesc == "trening"]
Xte, yte = X[czesc == "test"], y[czesc == "test"]
srednia, odch = Xtr.mean(axis=0), Xtr.std(axis=0) + 1e-6
norm = lambda a: (a - srednia) / odch
STD_MAX = float(np.percentile(Xtr[:, 1], 99) * 1.5)   # większy rozrzut niż w treningu: „nieznany”
print("okna trening/test:", len(ytr), len(yte), " leży/podniesiony (trening):", np.bincount(ytr, minlength=2))
np.savetxt("cechy.csv", np.column_stack([X, y, czesc == "test"]), delimiter=",", fmt=["%.3f", "%.3f", "%d", "%d"],
           header="f0,f1,klasa,test", comments="")

# --- Krok 3: model -------------------------------------------------------------------------
tf.keras.utils.set_random_seed(1)                 # te same wagi początkowe i kolejność próbek...
tf.config.experimental.enable_op_determinism()    # ...i deterministyczne obliczenia: powtarzalny wynik
model = tf.keras.Sequential([
    tf.keras.layers.Input(shape=(2,)),
    tf.keras.layers.Dense(4, activation="relu"),
    tf.keras.layers.Dense(2, activation="softmax"),
])
model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])

# --- Krok 4: trening i ocena ---------------------------------------------------------------
model.fit(norm(Xtr), ytr, epochs=200, batch_size=16, verbose=0)
print("parametry modelu:", model.count_params())

def macierz(nazwa, prawda, przew):
    m = np.zeros((2, 2), dtype=int)
    for a, c in zip(prawda, przew):
        m[a, c] += 1
    print(f"\n{nazwa}, trafność na teście: {(prawda == przew).mean():.3f}")
    print(f"{'prawda / przewidywanie':>24} {KLASY[0]:>12} {KLASY[1]:>12}")
    for i in range(2):
        print(f"{KLASY[i]:>24} {m[i, 0]:>12} {m[i, 1]:>12}")

pf = model.predict(norm(Xte), verbose=0).argmax(axis=1)
macierz("Sieć float32", yte, pf)
pr = (Xte[:, 0] < -6.0).astype(int)                       # reguła: ciśnienie niższe o ponad 6 Pa
macierz("Reguła (f0 < -6 Pa)", yte, pr)

# „nieznany”: płytka w ruchu (okna pominięte w treningu) -- jak często firmware nie zgadnie na ślepo?
X_ruch = np.array(X_ruch, dtype=np.float32)
if len(X_ruch):
    pr_ruch = model.predict(norm(X_ruch), verbose=0)
    nieznany = (X_ruch[:, 1] > STD_MAX) | (pr_ruch.max(axis=1) < PEWNOSC_MIN)
    print(f"\nOkna z ruchem: {len(X_ruch)}, z nich „nieznany”: {nieznany.sum()} ({nieznany.mean():.0%})")

# Dryf ciśnienia: poziom odniesienia przesunięty o +-5 Pa (pogoda po kilkunastu minutach)
for przes in (-5.0, 5.0):
    Xd = Xte.copy()
    Xd[:, 0] += przes
    pd_ = model.predict(norm(Xd), verbose=0).argmax(axis=1)
    pr_ = (Xd[:, 0] < -6.0).astype(int)
    print(f"Dryf {przes:+.0f} Pa: trafność sieci {(pd_ == yte).mean():.3f}, reguły {(pr_ == yte).mean():.3f}")

# --- Krok 5: kwantyzacja int8 --------------------------------------------------------------
def reprezentatywne():
    for x in norm(Xtr)[:200]:
        yield [x.reshape(1, 2).astype(np.float32)]

conv = tf.lite.TFLiteConverter.from_keras_model(model)
conv.optimizations = [tf.lite.Optimize.DEFAULT]
conv.representative_dataset = reprezentatywne
conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
conv.inference_input_type = tf.int8
conv.inference_output_type = tf.int8
tfl = conv.convert()
open("model.tflite", "wb").write(tfl)

it = tf.lite.Interpreter(model_content=tfl)
it.allocate_tensors()
wej, wyj = it.get_input_details()[0], it.get_output_details()[0]
s_in, z_in = wej["quantization"]
s_out, z_out = wyj["quantization"]
pq = []
for x in norm(Xte):
    q = np.clip(np.round(x / s_in + z_in), -128, 127).astype(np.int8).reshape(1, 2)
    it.set_tensor(wej["index"], q)
    it.invoke()
    pq.append(it.get_tensor(wyj["index"])[0].argmax())
macierz("Sieć int8", yte, np.array(pq))
print(f"\nRozmiar .tflite: {len(tfl)} B;  wejście scale={s_in:.6f} zero_point={z_in};  "
      f"wyjście scale={s_out:.6f} zero_point={z_out};  STD_MAX={STD_MAX:.2f} Pa")

# --- Krok 6: eksport do model.h ------------------------------------------------------------
with open("model.h", "w", encoding="utf-8") as f:
    f.write("// Wygenerowane przez trening.py -- nie edytuj ręcznie\n#pragma once\n\n")
    f.write(f"const float CECHY_SREDNIA[2] = {{{srednia[0]:.6f}f, {srednia[1]:.6f}f}};\n")
    f.write(f"const float CECHY_ODCH[2]    = {{{odch[0]:.6f}f, {odch[1]:.6f}f}};\n")
    f.write(f"const float STD_MAX = {STD_MAX:.4f}f;      // większy rozrzut: ruch, odpowiedź „nieznany”\n")
    f.write(f"const float PEWNOSC_MIN = {PEWNOSC_MIN:.2f}f;   // mniejsza pewność: odpowiedź „nieznany”\n")
    f.write('const char *const KLASY[3] = {"lezy", "podniesiony", "nieznany"};\n\n')
    f.write("alignas(16) const unsigned char g_model[] = {\n")
    for i in range(0, len(tfl), 12):
        f.write("  " + ", ".join(f"0x{c:02x}" for c in tfl[i:i + 12]) + ",\n")
    f.write(f"}};\nconst unsigned int g_model_len = {len(tfl)};\n")
print("Zapisano model.tflite, model.h, cechy.csv")

# --- Krok 7 (Laboratorium 5): model float do douczania na ESP32 i model Keras do douczania w kontenerze ---
# TFLM umie tylko wnioskować, więc douczana sieć na ESP32 to zwykły kod C++ na liczbach float (siec.cpp).
model.save("model_l4.keras")
np.savez("normalizacja.npz", srednia=srednia, odch=odch, std_max=STD_MAX)
(W1, b1), (W2, b2) = model.layers[0].get_weights(), model.layers[1].get_weights()
tab = lambda a: "{" + ", ".join(f"{v:.7f}f" for v in a) + "}"
with open("model_float.h", "w", encoding="utf-8") as f:
    f.write("// Wygenerowane przez trening.py (krok 7) -- nie edytuj ręcznie. Sieć 2-4-2 z Laboratorium 4 jako float.\n")
    f.write("#pragma once\n\n")
    f.write(f"const float CECHY_SREDNIA[2] = {tab(srednia)};\n")
    f.write(f"const float CECHY_ODCH[2]    = {tab(odch)};\n")
    f.write(f"const float STD_MAX = {STD_MAX:.4f}f;\n")
    f.write(f"const float PEWNOSC_MIN = {PEWNOSC_MIN:.2f}f;\n")
    f.write('const char *const KLASY[3] = {"lezy", "podniesiony", "nieznany"};\n\n')
    f.write("// Keras trzyma wagi jako [wejście][wyjście]; tu [wyjście][wejście], jak we wzorach z instrukcji\n")
    f.write("const float L4_W1[4][2] = {" + ", ".join(tab(r) for r in W1.T) + "};\n")
    f.write(f"const float L4_B1[4]    = {tab(b1)};\n")
    f.write("const float L4_W2[2][4] = {" + ", ".join(tab(r) for r in W2.T) + "};\n")
    f.write(f"const float L4_B2[2]    = {tab(b2)};\n")
print("Laboratorium 5: zapisano model_float.h, model_l4.keras, normalizacja.npz")
