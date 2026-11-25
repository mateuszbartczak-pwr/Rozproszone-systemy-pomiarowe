#!/usr/bin/env bash
# Laboratorium 6: przygotowanie brokera na zajęcia -- certyfikat TLS z bieżącym adresem IP i plik haseł.
#
# Uruchom w WSL, w katalogu broker/ swojego repozytorium, na początku KAŻDYCH zajęć (adres IP komputera się zmienia):
#     ./przygotuj.sh 192.168.1.23        <- adres IPv4 komputera z ipconfig, w tej samej sieci co ESP32
#     ./przygotuj.sh                     <- bez argumentu: wypisuje adresy IPv4 tego komputera do wyboru
#
# Co robi:
#   1. urząd certyfikacji (CA) -- tylko jeśli go jeszcze nie ma (certs/ca.key, certs/ca.crt);
#   2. certyfikat brokera dla podanego IP, podpisany przez CA (certs/serwer.key, certs/serwer.crt), ważny 30 dni;
#   3. plik haseł brokera passwd ze skrótami haseł z pliku uzytkownicy (login:hasło w każdej linii);
#   4. ../esp32/include/ca_cert.h -- certyfikat CA dla firmware ESP32 (TRYB_TLS 2).
# Klucze prywatne (*.key), passwd i uzytkownicy są w .gitignore: nie trafiają do repozytorium ani do obrazu.
set -euo pipefail
cd "$(dirname "$0")"
MOSQUITTO=eclipse-mosquitto:2.0.20

IP="${1:-}"
if [[ -z "$IP" ]]; then
  echo "Użycie: ./przygotuj.sh <adres IPv4 komputera>"
  echo "Adresy IPv4 tego komputera (ipconfig w Windows) -- wybierz adres z sieci, w której jest ESP32"
  echo "(adresy 172.x z kart vEthernet/WSL nie są widoczne dla ESP32):"
  ipconfig.exe 2>/dev/null | tr -d '\r' | grep -a "IPv4" | sed -E 's/.*: *//; s/^/  /' || echo "  (nie udało się uruchomić ipconfig.exe)"
  exit 1
fi
if [[ ! "$IP" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]]; then
  echo "To nie jest adres IPv4: $IP"
  exit 1
fi
mkdir -p certs

# 1. Urząd certyfikacji -- raz. Nowy CA = trzeba ponownie wgrać firmware ESP32 (nowy ca_cert.h).
if [[ ! -f certs/ca.key || ! -f certs/ca.crt ]]; then
  openssl req -x509 -newkey rsa:2048 -nodes -days 365 -sha256 \
    -keyout certs/ca.key -out certs/ca.crt -subj "/CN=CA laboratorium RSP" 2>/dev/null
  echo "[1/4] Utworzono NOWY urząd certyfikacji: certs/ca.crt (ważny 365 dni) -- wgraj ponownie firmware ESP32."
else
  echo "[1/4] Urząd certyfikacji już istnieje: certs/ca.crt (bez zmian)."
fi

# 2. Certyfikat brokera dla bieżącego IP.
#    IP: <adres>  -- sprawdzają klienci z OpenSSL (Python, mosquitto_sub, MQTT Explorer);
#    DNS:<adres>  -- sprawdza ESP32: mbedTLS 2.x porównuje nazwę hosta tylko z wpisami DNS, nie z wpisami IP;
#    localhost, 127.0.0.1 -- testy na tym komputerze; broker -- nazwa usługi w sieci Dockera.
cat > certs/serwer.ext <<EOF
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = IP:${IP}, DNS:${IP}, DNS:localhost, IP:127.0.0.1, DNS:broker
EOF
openssl req -newkey rsa:2048 -nodes -sha256 -keyout certs/serwer.key -out certs/serwer.csr -subj "/CN=${IP}" 2>/dev/null
openssl x509 -req -in certs/serwer.csr -CA certs/ca.crt -CAkey certs/ca.key -CAcreateserial -days 30 -sha256 \
  -extfile certs/serwer.ext -out certs/serwer.crt 2>/dev/null
rm -f certs/serwer.csr
echo "[2/4] Certyfikat brokera dla ${IP}: certs/serwer.crt (ważny 30 dni)."

# 3. Hasła: plik uzytkownicy (login:hasło) -> passwd ze skrótami, narzędziem mosquitto_passwd z obrazu brokera.
if [[ ! -f uzytkownicy ]]; then
  echo "Brak pliku uzytkownicy -- skopiuj uzytkownicy.example jako uzytkownicy i wpisz własne hasła."
  exit 1
fi
grep -v -E '^\s*(#|$)' uzytkownicy | tr -d '\r' > passwd
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD":/w "$MOSQUITTO" mosquitto_passwd -U /w/passwd
echo "[3/4] Plik haseł passwd: $(wc -l < passwd) kont ($(cut -d: -f1 passwd | tr '\n' ' '))."

# 4. Certyfikat CA jako tablica znaków dla firmware ESP32.
mkdir -p ../esp32/include
{
  echo "// Wygenerowane przez broker/przygotuj.sh -- certyfikat urzędu certyfikacji (CA) brokera"
  echo "#pragma once"
  echo "const char CA_CERT[] ="
  sed 's/.*/"&\\n"/' certs/ca.crt
  echo ";"
} > ../esp32/include/ca_cert.h
echo "[4/4] ../esp32/include/ca_cert.h"

# Broker w kontenerze działa jako użytkownik mosquitto, nie jako Ty -- musi móc czytać pliki (na dysku D: i tak są czytelne).
chmod 644 certs/serwer.key certs/serwer.crt certs/ca.crt passwd acl
chmod 600 certs/ca.key

echo
echo "Dalej: w esp32/include/secrets.h ustaw MQTT_HOST \"${IP}\", wgraj firmware; w WSL: docker compose restart broker"
