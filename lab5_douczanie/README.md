# Laboratorium 5: douczanie modelu na ESP32 (Przetwarzanie brzegowe w systemach sensorycznych)

Ciśnienie w sali zmienia się z pogodą, więc model z Laboratorium 4 (leży / podniesiony) zaczyna się mylić.
Tu douczamy go **na ESP32** krokami SGD na oknach z etykietą z przycisku BOOT i porównujemy z douczaniem w kontenerze.
Pełny opis zadań jest w instrukcji do laboratorium.

```
lab5_douczanie/
  esp32/
    platformio.ini            espressif32@6.7.0, bez TFLM (sieć liczona w zwykłym C++)
    src/main.cpp              gotowy: dwie sieci (L4 zamrożona i douczana), symulowany dryf, etykiety BOOT, bufor powtórek
    src/siec.h, siec.cpp      sieć 2-4-2 float: przod() gotowe, krok() z TODO (zadanie 2)
    src/bmp280_sensor.*       moduł czujnika z setMlMode() (jak w Laboratorium 4)
    include/model_float.h     TYMCZASOWY -- zastąp wygenerowanym przez ml/trening.py
  ml/
    trening.py                trening z Laboratorium 4 + krok 7: model_float.h, model_l4.keras
    doucz.py                  douczanie w kontenerze: od wag L4 vs od zera, zapominanie
```

## Pliki (w Windows, `cmd`)

```bat
cd /d D:\123456\rsp-przedmiot
git pull
cd /d D:\123456\rsp-nazwisko-imie
set Z=D:\123456\rsp-przedmiot\lab5_douczanie
copy esp32\src\main.cpp esp32\src\main_lab4.cpp.txt
copy /Y %Z%\esp32\src\main.cpp esp32\src\
copy /Y %Z%\esp32\src\siec.h esp32\src\
copy /Y %Z%\esp32\src\siec.cpp esp32\src\
copy /Y %Z%\ml\trening.py ml\
copy /Y %Z%\ml\doucz.py ml\
```

## Model L4 jako float (WSL, katalog ml/ swojego repozytorium)

```bash
cd /mnt/d/123456/rsp-nazwisko-imie/ml
docker run --rm -v "$PWD":/ml -w /ml tensorflow/tensorflow:2.18.0 python trening.py
cp model_float.h ../esp32/include/
```

Trening jest deterministyczny: na tych samych seriach powstaje dokładnie model z Laboratorium 4.

## Komendy w monitorze (`pio device monitor -b 115200`, bez Entera)

| Klawisz | Działanie | Klawisz | Działanie |
|---|---|---|---|
| `-` / `+` | symulowany dryf −10 / +10 Pa | `u` | douczanie wł./wył. |
| `0` | bez dryfu | `r` | sieć douczana = L4, pusty bufor |
| `z` | zerowanie poziomu odniesienia | `?` | stan |

Po starcie firmware sprawdza `krok()`: linia `# Test gradientu: ... OK` oznacza, że gradient jest policzony dobrze.

## Douczanie w kontenerze

```bash
docker run --rm -v "$PWD":/ml -w /ml tensorflow/tensorflow:2.18.0 python doucz.py -10
docker run --rm -v "$PWD":/ml -w /ml tensorflow/tensorflow:2.18.0 python doucz.py -30
```
