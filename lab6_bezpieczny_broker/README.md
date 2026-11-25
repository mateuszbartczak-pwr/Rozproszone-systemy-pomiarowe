# Laboratorium 6: bezpieczny broker MQTT (Przetwarzanie brzegowe w systemach sensorycznych)

Broker z Laboratoriów 1–3 przyjmuje każdego, bez hasła, a pomiary płyną otwartym tekstem. Tu zamykamy go:
konto dla każdego klienta, lista kontroli dostępu (ACL), TLS na porcie 8883 z certyfikatem generowanym na każde
zajęcia (adres IP komputera w sali się zmienia). Pełny opis zadań jest w instrukcji do laboratorium.

```
lab6_bezpieczny_broker/
  broker/
    przygotuj.sh              NA KAŻDE ZAJĘCIA: certyfikat brokera dla bieżącego IP, hasła, ca_cert.h dla ESP32
    mosquitto.conf            konta, ACL, 1883 tylko w sieci Dockera, 8883 z TLS
    acl                       kto co może (urządzenie pisze tylko pod swoim device_id)
    uzytkownicy.example       wzór listy kont login:hasło -> skopiuj jako uzytkownicy
    Dockerfile                eclipse-mosquitto:2.0.20 (wersja przypięta)
  docker-compose.fragment.yml zmiany usług broker i ingestor
  ingestor/zmiana_ingestor.py dwie linie dla ingestora (login i hasło z .env)
  gitignore.dodaj             co dopisać do .gitignore
  esp32/                      firmware: konto MQTT, Last Will, TLS z przełącznikiem TRYB_TLS 0/1/2
```

## Na początku każdych zajęć (WSL, katalog `broker/` Twojego repozytorium)

```bash
bash przygotuj.sh                  # wypisuje adresy IPv4 komputera -- wybierz ten z sieci ESP32
bash przygotuj.sh 192.168.1.23     # certyfikat brokera dla tego adresu + hasła + ../esp32/include/ca_cert.h
docker compose up -d --build       # w katalogu głównym repozytorium
```

Potem w `esp32/include/secrets.h` ustaw `MQTT_HOST` na ten sam adres i wgraj firmware.
Urząd certyfikacji (`certs/ca.key`, `certs/ca.crt`) powstaje tylko za pierwszym razem; jeśli zniknie (np. po
odtworzeniu komputera), skrypt utworzy nowy, a firmware trzeba wgrać ponownie z nowym `ca_cert.h`.

## Gdy certyfikat nie działa, a zajęcia trwają

- W `main.cpp` ustaw `TRYB_TLS 1` (szyfrowanie bez sprawdzania brokera) albo `TRYB_TLS 0` (bez TLS)
  i w `docker-compose.yml` odkomentuj `- 1883:1883`. Konta i ACL działają dalej.
- Najczęstsza przyczyna: inny adres w `secrets.h` niż w `przygotuj.sh` albo certyfikat z poprzednich zajęć.

## Dlaczego w certyfikacie adres jest dwa razy

ESP32 (`espressif32@6.7.0`, mbedTLS 2.28) porównuje adres z certyfikatem tylko z wpisami DNS, nie z wpisami IP.
Skrypt wpisuje adres jako `IP:` (dla klientów z OpenSSL, np. MQTT Explorer) i jako `DNS:` (dla ESP32).
Sprawdzone na mbedTLS 2.28.0: certyfikat tylko z `IP:` jest odrzucany („CN does not match”).
