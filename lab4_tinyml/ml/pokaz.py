"""Laboratorium 4: podgląd jednej krótkiej serii pomiarowej -- czy nadaje się do treningu?

Użycie: terminal PlatformIO w VS Code, katalog esp32/, zaraz po zatrzymaniu monitora (Ctrl+C):
    python ../ml/pokaz.py                       # najnowszy logs/*.log -> ml/dane/seriaN.log + wykres seriaN.svg
    python ../ml/pokaz.py ../ml/dane/seria2.log # ponowna ocena zapisanej serii
Tylko biblioteka standardowa: działa w Pythonie z PlatformIO, w WSL (python3) i w kontenerze TensorFlow.
Seria z błędem dostaje nazwę seriaN.log.odrzucona -- trening.py czyta tylko pliki *.log.
"""
import glob, os, shutil, statistics as st, sys, webbrowser

sys.stdout.reconfigure(encoding="utf-8")   # polskie znaki także przy przekierowaniu wyjścia

N_ODNIESIENIE = 50   # pierwsze 5 s: płytka leży, poziom odniesienia (tak samo jak w trening.py)
OKNO = 10            # okno 1 s, jak w trening.py i firmware
MARGINES = 10        # 1 s wokół zmiany BOOT: płytka w ruchu
PROG = -6.0          # reguła z zadania 2: podniesiony, gdy f0 < -6 Pa
PA_NA_METR = 11.8    # rho * g dla powietrza: ok. 12 Pa na 1 m wysokości
TU = os.path.dirname(os.path.abspath(__file__))
DANE = os.path.join(TU, "dane")


def wczytaj(plik):
    """Linie z czterema liczbami: ms, p_pa, t_c, btn (komunikaty monitora i nagłówki są pomijane)."""
    w = []
    for linia in open(plik, encoding="utf-8", errors="ignore"):
        pola = linia.strip().split(",")
        if len(pola) == 4:
            try:
                w.append([float(x) for x in pola])
            except ValueError:
                pass
    return w


def najnowszy_log():
    kandydaci = glob.glob(os.path.join("logs", "*.log")) + glob.glob(os.path.join(TU, "..", "esp32", "logs", "*.log"))
    return max(kandydaci, key=os.path.getmtime) if kandydaci else None


def do_danych(log):
    """Kopiuje log monitora do ml/dane/seriaN.log (kolejny wolny numer); ten sam log nie jest kopiowany dwa razy."""
    os.makedirs(DANE, exist_ok=True)
    tresc = open(log, "rb").read()
    for f in glob.glob(os.path.join(DANE, "seria*.log*")):
        if open(f, "rb").read() == tresc:
            print(f"Ten log jest już zapisany jako {os.path.relpath(f)}")
            return f
    n = 1
    while glob.glob(os.path.join(DANE, f"seria{n}.log*")):
        n += 1
    cel = os.path.join(DANE, f"seria{n}.log")
    shutil.copyfile(log, cel)
    print(f"Log monitora {os.path.relpath(log)} zapisany jako {os.path.relpath(cel)}")
    return cel


def odcinki(btn):
    """Przedziały [a, b) z wciśniętym BOOT."""
    w, i = [], 0
    while i < len(btn):
        if btn[i]:
            j = i
            while j < len(btn) and btn[j]:
                j += 1
            w.append((i, j))
            i = j
        else:
            i += 1
    return w


def ocen(d):
    """Zwraca słownik z wynikami i listy błędów (seria do powtórzenia) oraz uwag."""
    ms, p, btn = [r[0] for r in d], [r[1] for r in d], [int(r[3]) for r in d]
    n = len(d)
    bledy, uwagi = [], []
    if n < 2 * N_ODNIESIENIE:
        return {"n": n}, [f"tylko {n} próbek -- czy firmware jest w trybie zbierania (TRYB_ZBIERANIA 1)?"], []
    dt = [b - a for a, b in zip(ms, ms[1:])]
    dt_med = st.median(dt)
    hz = 1000.0 / dt_med if dt_med > 0 else 0.0
    luki = sum(1 for x in dt if x > 2.5 * dt_med or x < 0)
    p_ref = st.mean(p[:N_ODNIESIENIE])
    szum_ref = st.pstdev(p[:N_ODNIESIENIE])
    dp = [x - p_ref for x in p]
    zmiany = [i for i in range(1, n) if btn[i] != btn[i - 1]]
    daleko = [all(abs(i - z) > MARGINES for z in zmiany) for i in range(n)]

    # okna 1 s z dala od zmian BOOT: średnia (f0) i rozrzut (f1), jak w trening.py
    okna = []
    for s in range(N_ODNIESIENIE, n - OKNO + 1, OKNO // 2):
        if all(daleko[s:s + OKNO]) and len(set(btn[s:s + OKNO])) == 1:
            okna.append((s, st.mean(dp[s:s + OKNO]), st.pstdev(p[s:s + OKNO]), btn[s]))
    szum = st.median([o[2] for o in okna if o[3] == 0] or [0.0])
    bez_boot = [o for o in okna if o[3] == 0 and o[1] < PROG]        # płytka w górze, a BOOT puszczony
    lezy_koniec = [dp[i] for i in range(n - 1, N_ODNIESIENIE, -1) if btn[i] == 0 and daleko[i]][:N_ODNIESIENIE]
    dryf = st.mean(lezy_koniec) if lezy_koniec else 0.0

    podn = []
    for a, b in odcinki(btn):
        sr = st.mean(dp[a:b])
        rozrzut = max([o[2] for o in okna if a <= o[0] < b] or [0.0])
        podn.append({"a": a, "b": b, "dp": sr, "h": -sr / PA_NA_METR, "s": (b - a) / hz, "rozrzut": rozrzut})

    # --- błędy: seria do powtórzenia ---
    if n < 400:
        bledy.append(f"seria trwa tylko {n / hz:.0f} s (potrzeba co najmniej 40 s)")
    if not 8 <= hz <= 12:
        bledy.append(f"częstotliwość {hz:.1f} Hz zamiast 10 Hz -- czy setMlMode() jest wywołane?")
    if any(btn[:N_ODNIESIENIE]):
        bledy.append("BOOT wciśnięty w pierwszych 5 s -- wtedy płytka ma leżeć (poziom odniesienia)")
    if szum_ref > 3.0:
        bledy.append(f"rozrzut {szum_ref:.1f} Pa w pierwszych 5 s -- płytka się ruszała, poziom odniesienia niepewny")
    powtorzone = sum(1 for a, b in zip(p, p[1:]) if a == b) / (n - 1)
    if szum < 0.5 or powtorzone > 0.3:
        bledy.append(f"szum na stole {szum:.1f} Pa (oczekiwane ok. 1,3 Pa), powtórzone odczyty {powtorzone:.0%} -- "
                     "czujnik nadal z filtrem IIR / STANDBY_MS_500 z Lab. 1: czy setMlMode() jest wywołane?")
    if not podn:
        bledy.append("ani jednego wciśnięcia BOOT -- brak etykiet „podniesiony”")
    for k, q in enumerate(podn, 1):
        if q["dp"] > -3.0:
            bledy.append(f"podniesienie {k}: tylko {q['dp']:+.1f} Pa -- czujnik z filtrem IIR (setMlMode()?) "
                         "albo BOOT wciśnięty bez podniesienia")
    if podn and all(q["dp"] > PROG for q in podn):
        bledy.append(f"żadne podniesienie nie przekracza progu {PROG:.0f} Pa -- podnoś płytkę ok. 1 m (nad głowę)")
    if len(bez_boot) >= 3:
        bledy.append(f"{len(bez_boot) // 2} s płytki w górze bez wciśniętego BOOT -- błędne etykiety „leży”")

    # --- uwagi: seria przydatna, ale można lepiej ---
    if 0 < len(podn) < 3:
        uwagi.append(f"tylko {len(podn)} podniesienia (zalecane 3 na serię)")
    for k, q in enumerate(podn, 1):
        if -6.0 < q["dp"] <= -3.0:
            uwagi.append(f"podniesienie {k}: {q['dp']:+.1f} Pa, czyli ok. {q['h']:.1f} m -- podnoś ok. 1 m (nad głowę)")
        if q["s"] < 3.0:
            uwagi.append(f"podniesienie {k}: BOOT trzymany tylko {q['s']:.1f} s (zalecane 6--10 s)")
        if q["rozrzut"] > 4.0:
            uwagi.append(f"podniesienie {k}: rozrzut do {q['rozrzut']:.1f} Pa -- płytka ruszała się z wciśniętym BOOT")
    if 0 < len(bez_boot) < 3:
        uwagi.append("krótka chwila płytki w górze bez BOOT (pojedyncze okno)")
    if szum > 2.5:
        uwagi.append(f"szum na stole {szum:.1f} Pa (oczekiwane ok. 1,3 Pa) -- drgania stołu, laptop, wentylator?")
    if abs(dryf) > 3.0:
        uwagi.append(f"dryf {dryf:+.1f} Pa od początku serii -- nagrywaj krótsze serie")
    if luki:
        uwagi.append(f"{luki} przerw w danych (zgubione linie albo reset płytki)")

    wynik = {"n": n, "hz": hz, "p_ref": p_ref, "szum_ref": szum_ref, "szum": szum, "dryf": dryf,
             "podn": podn, "bez_boot": bez_boot, "ms": ms, "dp": dp, "btn": btn}
    return wynik, bledy, uwagi


def svg(w, plik_svg, tytul, werdykt, kolor):
    """Wykres p - p_ref w czasie: surowe próbki, średnia z okna 1 s, BOOT, próg reguły."""
    W, H, L, R, T, B = 1000, 420, 70, 20, 50, 50
    t = [(m - w["ms"][0]) / 1000.0 for m in w["ms"]]
    dp, btn = w["dp"], w["btn"]
    tmax = max(t[-1], 1.0)
    ymin = min(-15.0, min(dp) - 2.0)
    ymax = max(5.0, max(dp) + 2.0)
    X = lambda x: L + (x / tmax) * (W - L - R)
    Y = lambda y: T + (ymax - y) / (ymax - ymin) * (H - T - B)
    e = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
         'font-family="Segoe UI, Arial, sans-serif" font-size="13">',
         f'<rect width="{W}" height="{H}" fill="white"/>',
         f'<text x="{L}" y="22" font-size="16" font-weight="bold">{tytul}</text>',
         f'<text x="{L}" y="40" fill="{kolor}" font-weight="bold">{werdykt}</text>']
    # tło: poziom odniesienia, wciśnięty BOOT, płytka w górze bez BOOT
    e.append(f'<rect x="{X(0):.1f}" y="{T}" width="{X(t[N_ODNIESIENIE]) - X(0):.1f}" height="{H - T - B}" fill="#e6e6e6"/>')
    e.append(f'<text x="{X(0) + 4:.1f}" y="{T + 14}" fill="#666">odniesienie</text>')
    for k, q in enumerate(w["podn"], 1):
        x0, x1 = X(t[q["a"]]), X(t[q["b"] - 1])
        e.append(f'<rect x="{x0:.1f}" y="{T}" width="{max(x1 - x0, 1):.1f}" height="{H - T - B}" fill="#ffb74d" fill-opacity="0.35"/>')
        e.append(f'<text x="{x0 + 3:.1f}" y="{T + 14}" fill="#b35c00">{k}: {q["dp"]:+.1f} Pa, ok. {q["h"]:.1f} m</text>')
    przedzialy = []                                   # nakładające się okna 1 s -> jeden prostokąt
    for o in w["bez_boot"]:
        a, b = o[0], min(o[0] + OKNO, len(t) - 1)
        if przedzialy and a <= przedzialy[-1][1]:
            przedzialy[-1][1] = b
        else:
            przedzialy.append([a, b])
    for a, b in przedzialy:
        e.append(f'<rect x="{X(t[a]):.1f}" y="{T}" width="{X(t[b]) - X(t[a]):.1f}" height="{H - T - B}" '
                 'fill="#e53935" fill-opacity="0.25"/>')
    # siatka i osie
    for y in range(int(ymin // 5) * 5 + 5, int(ymax) + 1, 5):
        e.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(y):.1f}" y2="{Y(y):.1f}" stroke="#ddd"/>')
        e.append(f'<text x="{L - 8}" y="{Y(y) + 4:.1f}" text-anchor="end">{y}</text>')
    krok_t = 10 if tmax <= 150 else 30
    for s in range(0, int(tmax) + 1, krok_t):
        e.append(f'<line x1="{X(s):.1f}" x2="{X(s):.1f}" y1="{H - B}" y2="{H - B + 5}" stroke="#333"/>')
        e.append(f'<text x="{X(s):.1f}" y="{H - B + 19}" text-anchor="middle">{s}</text>')
    e.append(f'<rect x="{L}" y="{T}" width="{W - L - R}" height="{H - T - B}" fill="none" stroke="#333"/>')
    e.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(0):.1f}" y2="{Y(0):.1f}" stroke="#555"/>')
    e.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(PROG):.1f}" y2="{Y(PROG):.1f}" stroke="#e53935" stroke-dasharray="6,4"/>')
    e.append(f'<text x="{W - R - 4}" y="{Y(PROG) - 4:.1f}" text-anchor="end" fill="#e53935">próg reguły {PROG:.0f} Pa</text>')
    e.append(f'<text x="{(L + W - R) / 2:.0f}" y="{H - 10}" text-anchor="middle">czas [s]</text>')
    e.append(f'<text x="16" y="{(T + H - B) / 2:.0f}" text-anchor="middle" transform="rotate(-90 16 {(T + H - B) / 2:.0f})">'
             'p − p_ref [Pa]</text>')
    # przebiegi: surowe próbki i średnia ruchoma z okna 1 s (to widzi model jako f0)
    surowe = " ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in zip(t, dp))
    sr = [st.mean(dp[max(0, i - OKNO + 1):i + 1]) for i in range(len(dp))]
    gladkie = " ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in zip(t, sr))
    e.append(f'<polyline points="{surowe}" fill="none" stroke="#90caf9" stroke-width="1"/>')
    e.append(f'<polyline points="{gladkie}" fill="none" stroke="#1565c0" stroke-width="2.2"/>')
    e.append(f'<text x="{W - R}" y="22" text-anchor="end"><tspan fill="#5c9ed6">próbki</tspan>'
             '<tspan fill="#1565c0" dx="12">średnia z 1 s (cecha f0)</tspan></text>')
    e.append(f'<text x="{W - R}" y="40" text-anchor="end"><tspan fill="#b35c00">BOOT wciśnięty</tspan>'
             '<tspan fill="#c62828" dx="12">w górze bez BOOT</tspan></text>')
    e.append("</svg>")
    with open(plik_svg, "w", encoding="utf-8") as f:
        f.write("\n".join(e))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        plik = args[0]
    else:
        log = najnowszy_log()
        if log is None:
            sys.exit("Nie ma logów monitora w logs/. Uruchom: pio device monitor -b 115200 --filter log2file")
        plik = do_danych(log)
    w, bledy, uwagi = ocen(wczytaj(plik))
    nazwa = os.path.basename(plik).split(".log")[0]
    print(f"\n=== {nazwa}: {w['n']} próbek", end="")
    if "hz" in w:
        print(f", {w['n'] / w['hz']:.0f} s, {w['hz']:.1f} Hz, p_ref = {w['p_ref']:.1f} Pa, "
              f"szum na stole {w['szum']:.1f} Pa, dryf {w['dryf']:+.1f} Pa")
        for k, q in enumerate(w["podn"], 1):
            print(f"  podniesienie {k}: {q['dp']:+6.1f} Pa (ok. {q['h']:.1f} m), BOOT {q['s']:4.1f} s, "
                  f"rozrzut do {q['rozrzut']:.1f} Pa")
    else:
        print()
    for b in bledy:
        print("  BŁĄD:", b)
    for u in uwagi:
        print("  uwaga:", u)
    if bledy:
        werdykt, kolor = "SERIA DO POWTÓRZENIA: " + bledy[0], "#c62828"
    elif uwagi:
        werdykt, kolor = f"SERIA PRZYDATNA (uwagi: {len(uwagi)}, szczegóły w konsoli)", "#ef6c00"
    else:
        werdykt, kolor = "SERIA DOBRA -- nadaje się do treningu", "#2e7d32"
    print(werdykt)
    if "hz" in w:
        plik_svg = os.path.join(os.path.dirname(plik), nazwa + ".svg")
        svg(w, plik_svg, f"{nazwa}: ciśnienie względem poziomu odniesienia", werdykt, kolor)
        print("Wykres:", os.path.relpath(plik_svg))
        if "--bez-okna" not in sys.argv:
            try:
                webbrowser.open("file://" + os.path.abspath(plik_svg))
            except Exception:
                pass
    if bledy and plik.endswith(".log") and os.path.dirname(os.path.abspath(plik)) == DANE:
        os.replace(plik, plik + ".odrzucona")
        print(f"Plik przemianowany na {os.path.basename(plik)}.odrzucona (trening.py go pominie). Nagraj serię jeszcze raz.")
    return 1 if bledy else 0


if __name__ == "__main__":
    sys.exit(main())
