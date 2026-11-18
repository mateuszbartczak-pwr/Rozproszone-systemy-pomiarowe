Tu trafiają serie z zadania 1: `seria1.log`, `seria2.log`, ... i ich wykresy `seriaN.svg`.
Zapisuje je `python ../ml/pokaz.py` (uruchomiony w `esp32/` po zatrzymaniu `pio device monitor --filter log2file`).
`trening.py` wczytuje wszystkie pliki `*.log` z tego katalogu; serie odrzucone (`*.log.odrzucona`) pomija.
