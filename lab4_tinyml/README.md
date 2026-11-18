# Laboratorium 4: TinyML na ESP32 (Przetwarzanie brzegowe w systemach sensorycznych)

Kod startowy do Laboratorium 4: ESP32 z czujnikiem BMP280 rozpoznaje, czy płytka **leży** na stole,
czy jest **podniesiona** (ok. 1 m wyżej), a w trakcie ruchu albo przy niskiej pewności modelu odpowiada
**„nieznany”**. Pełny opis zadań jest w instrukcji do laboratorium.

```
lab4_tinyml/
  esp32/                      projekt PlatformIO
    platformio.ini            + biblioteka TensorFlowLite_ESP32 (TFLM)
    src/main.cpp              szkielet: tryb zbierania i inferencja, miejsca TODO do uzupełnienia
    src/bmp280_sensor.*       moduł czujnika z Laboratorium 1 + setMlMode() (x16, bez filtra IIR, 10 Hz)
    include/model.h           TYMCZASOWY model -- zastąp wygenerowanym przez ml/trening.py
  ml/
    trening.py                cechy okna, trening, ocena, kwantyzacja int8, eksport do model.h
    dane/                     tu nagranie z płytki (nagranie.log)
```

## Jak przenieść do własnego repozytorium

W WSL (zamień ścieżkę na swoją):

```bash
git clone --depth 1 https://github.com/mateuszbartczak-pwr/Rozproszone-systemy-pomiarowe.git /tmp/rsp
cd /mnt/d/123456/rsp-nazwisko-imie
mkdir -p ml/dane
cp /tmp/rsp/lab4_tinyml/ml/trening.py ml/
cp /tmp/rsp/lab4_tinyml/esp32/src/main.cpp esp32/src/main.cpp          # najpierw zachowaj swój main.cpp!
cp /tmp/rsp/lab4_tinyml/esp32/include/model.h esp32/include/
```

Do `esp32/platformio.ini` dopisz bibliotekę `tanakamasayuki/TensorFlowLite_ESP32@^1.0.0`, a do swojego modułu
`bmp280_sensor` metodę `setMlMode()` (wzór w `esp32/src/bmp280_sensor.cpp`). Jeśli nie masz własnego modułu,
skopiuj też `esp32/src/bmp280_sensor.h` i `.cpp`.

## Trening (lokalnie, bez kont w chmurze)

W WSL, w katalogu `ml/` (obraz ma ok. 2,6 GB, pierwsze pobranie trwa kilka minut):

```bash
docker run --rm -v "$PWD":/ml -w /ml tensorflow/tensorflow:2.18.0 python trening.py
cp model.h ../esp32/include/
```

Alternatywy: własny Python (`python -m venv .venv`, `pip install tensorflow numpy`, `python trening.py`)
albo Google Colab (wymaga prywatnego konta Google).

## Wgrywanie

Pierwsza kompilacja trwa 4-5 minut. Jeśli wgrywanie kończy się `Failed to connect to ESP32`, trzymaj przycisk
BOOT, naciśnij EN i trzymaj BOOT do napisu `Writing`.
