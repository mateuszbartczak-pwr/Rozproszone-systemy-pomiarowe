# Laboratorium 4: TinyML na ESP32 (Przetwarzanie brzegowe w systemach sensorycznych)

Kod startowy do Laboratorium 4: ESP32 z czujnikiem BMP280 rozpoznaje, czy płytka **leży** na stole,
czy jest **podniesiona** (ok. 1 m wyżej), a w trakcie ruchu albo przy niskiej pewności modelu odpowiada
**„nieznany”**. Pełny opis zadań jest w instrukcji do laboratorium.

```
lab4_tinyml/
  esp32/                      projekt PlatformIO
    platformio.ini            espressif32@6.7.0 (wersja przypięta) + biblioteka TensorFlowLite_ESP32 (TFLM)
    src/main.cpp              szkielet: tryb zbierania i inferencja, miejsca TODO do uzupełnienia
    src/bmp280_sensor.*       moduł czujnika z Laboratorium 1 + setMlMode() (x16, bez filtra IIR, 10 Hz)
    include/model.h           TYMCZASOWY model -- zastąp wygenerowanym przez ml/trening.py
  ml/
    pokaz.py                  wykres i ocena jednej serii pomiarowej (tylko biblioteka standardowa Pythona)
    trening.py                cechy okna, trening, ocena, kwantyzacja int8, eksport do model.h
    dane/                     serie z płytki: seria1.log, seria2.log, ...
```

## Jak przenieść do własnego repozytorium

Repozytoria klonujesz **w Windows** (`cmd` albo terminal VS Code, tam jesteś zalogowany do GitHuba).
WSL służy tylko do uruchomienia kontenera z treningiem. Zamień ścieżki na swoje:

```bat
cd /d D:\123456
git clone --depth 1 https://github.com/mateuszbartczak-pwr/Rozproszone-systemy-pomiarowe.git rsp-przedmiot
cd /d D:\123456\rsp-nazwisko-imie
set Z=D:\123456\rsp-przedmiot\lab4_tinyml
copy esp32\src\main.cpp esp32\src\main_lab2.cpp.txt
copy /Y %Z%\esp32\src\main.cpp esp32\src\
copy /Y %Z%\esp32\include\model.h esp32\include\
mkdir ml\dane
copy /Y %Z%\ml\trening.py ml\
copy /Y %Z%\ml\pokaz.py ml\
```

W `esp32/platformio.ini` ustaw `platform = espressif32@6.7.0` (bez numeru wersji część stanowisk nie budowała
projektu) i dopisz bibliotekę `tanakamasayuki/TensorFlowLite_ESP32@^1.0.0`. Do swojego modułu `bmp280_sensor`
dodaj metodę `setMlMode()` (wzór w `esp32/src/bmp280_sensor.cpp`). Jeśli nie masz własnego modułu,
skopiuj też `esp32/src/bmp280_sensor.h` i `.cpp`.

## Nagrywanie krótkimi seriami

Jedna seria trwa ok. 1 minuty: 5 s płytka leży, potem 3 razy: leży 8-10 s, podniesienie ok. 1 m, BOOT wciśnięty
6-10 s, puszczenie, opuszczenie. W terminalu PlatformIO, w katalogu `esp32/`:

```bash
pio device monitor -b 115200 --filter log2file   # seria, potem Ctrl+C
python ../ml/pokaz.py                            # log -> ml/dane/seriaN.log, wykres seriaN.svg, ocena
```

Seria oceniona jako „DO POWTÓRZENIA” dostaje nazwę `seriaN.log.odrzucona` i nie trafia do treningu.
Zbierz co najmniej 4 dobre serie.

## Trening (lokalnie, bez kont w chmurze)

W WSL, w katalogu `ml/` swojego repozytorium (obraz ma ok. 2,6 GB, pierwsze pobranie trwa kilka minut):

```bash
cd /mnt/d/123456/rsp-nazwisko-imie/ml
docker run --rm -v "$PWD":/ml -w /ml tensorflow/tensorflow:2.18.0 python trening.py
cp model.h ../esp32/include/
```

Alternatywy: własny Python (`python -m venv .venv`, `pip install tensorflow numpy`, `python trening.py`)
albo Google Colab (wymaga prywatnego konta Google).

## Wgrywanie

Pierwsza kompilacja trwa 4-5 minut (z pobraniem platformy ok. 8 minut). Jeśli wgrywanie kończy się
`Failed to connect to ESP32`, trzymaj przycisk BOOT, naciśnij EN i trzymaj BOOT do napisu `Writing`.
