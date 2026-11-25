#pragma once
// Skopiuj jako secrets.h i wpisz własne dane. secrets.h jest w .gitignore.
#define WIFI_SSID     "nazwa_sieci"
#define WIFI_PASSWORD "haslo_sieci"
#define MQTT_HOST     "192.168.1.10"     // IP komputera z Dockerem (ipconfig) -- TEN SAM, który podałeś w broker/przygotuj.sh
#define MQTT_PORT     8883               // informacyjnie: port wybiera TRYB_TLS w main.cpp (0 -> 1883, 1-2 -> 8883)
#define GROUP_ID      "g03"
#define MQTT_PASSWORD "zmien-haslo-esp32" // hasło konta esp32-xxxxxxxx z broker/uzytkownicy
