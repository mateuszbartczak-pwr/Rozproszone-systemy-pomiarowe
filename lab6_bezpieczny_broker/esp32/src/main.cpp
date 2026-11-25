// Laboratorium 6: ESP32 -> broker MQTT z kontem, listą kontroli dostępu (ACL) i TLS.
// Publikuje ciśnienie co 5 s (kontrakt danych v1) i status online/offline (Last Will).
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <sys/time.h>
#include "secrets.h"          // WIFI_SSID, WIFI_PASSWORD, MQTT_HOST, GROUP_ID, MQTT_PASSWORD
#include "bmp280_sensor.h"

// 0: bez TLS, port 1883 -- awaryjnie, gdy certyfikat nie działa (w docker-compose odkomentuj 1883:1883)
// 1: TLS bez sprawdzania brokera (setInsecure) -- szyfruje, ale łączy się z KAŻDYM, kto ma port 8883
// 2: TLS + sprawdzenie certyfikatu brokera: podpis naszego CA i adres z MQTT_HOST -- docelowo
#define TRYB_TLS 2
// 1: co drugi pomiar wysyłaj też na topik innego urządzenia (test ACL w zadaniu 3; broker ma go odrzucić)
#define TEST_ACL 0

#if TRYB_TLS == 2
#include "ca_cert.h"          // generuje broker/przygotuj.sh
#endif

const int I2C_SDA = 21, I2C_SCL = 22;
const uint8_t BMP_ADDR = 0x76;
const unsigned long PUBLISH_MS = 5000, RECONNECT_MS = 5000;
const uint16_t PORT = TRYB_TLS ? 8883 : 1883;

#if TRYB_TLS
WiFiClientSecure net;
#else
WiFiClient net;
#endif
PubSubClient mqtt(net);
Bmp280Sensor bmp;
String deviceId;
char statusTopic[96];
uint32_t seq = 0;
unsigned long lastPublishMs = 0, lastTryMs = 0;

long long timestampMs() {
  struct timeval tv;
  gettimeofday(&tv, NULL);
  return (long long)tv.tv_sec * 1000LL + tv.tv_usec / 1000;
}

const char *opisStanu(int s) {   // PubSubClient::state()
  switch (s) {
    case -4: return "brak odpowiedzi (timeout)";
    case -2: return "nie udało się połączyć (TCP/TLS)";
    case 4:  return "zły login lub hasło";
    case 5:  return "brak autoryzacji (login/hasło lub ACL)";
    default: return "inny błąd";
  }
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.printf("\nWi-Fi OK, IP: %s\n", WiFi.localIP().toString().c_str());
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");   // czas do ts_ms (i do sprawdzania ważności certyfikatu)
  struct tm t;
  while (!getLocalTime(&t)) { Serial.println("Czekam na NTP..."); delay(500); }
}

bool connectMqtt() {
  uint32_t heap0 = ESP.getFreeHeap();
  unsigned long t0 = millis();
  // login = device_id (ACL: urządzenie publikuje tylko pod lab/+/<device_id>/#); Last Will: "offline", retain
  bool ok = mqtt.connect(deviceId.c_str(), deviceId.c_str(), MQTT_PASSWORD, statusTopic, 1, true, "offline");
  unsigned long dt = millis() - t0;
  if (ok) {
    mqtt.publish(statusTopic, "online", true);
    Serial.printf("MQTT OK: %s:%u, TRYB_TLS %d, połączenie %lu ms, wolna pamięć %u -> %u B\n",
                  MQTT_HOST, PORT, TRYB_TLS, dt, (unsigned)heap0, (unsigned)ESP.getFreeHeap());
  } else {
    Serial.printf("MQTT błąd rc=%d: %s (%lu ms)\n", mqtt.state(), opisStanu(mqtt.state()), dt);
#if TRYB_TLS
    char err[128];
    if (net.lastError(err, sizeof(err))) Serial.printf("  TLS: %s\n", err);   // np. zły certyfikat lub adres
#endif
  }
  return ok;
}

void publishPressure(const char *device, float hpa) {
  char topic[96], payload[256];
  snprintf(topic, sizeof(topic), "lab/%s/%s/pressure", GROUP_ID, device);
  snprintf(payload, sizeof(payload),
           "{\"schema_version\":1,\"group_id\":\"%s\",\"device_id\":\"%s\",\"sensor\":\"pressure\","
           "\"value\":%.2f,\"unit\":\"hPa\",\"ts_ms\":%lld,\"seq\":%lu}",
           GROUP_ID, device, hpa, timestampMs(), (unsigned long)seq++);
  bool ok = mqtt.publish(topic, payload);   // QoS 0: true = wysłano, NIE znaczy, że broker przyjął (ACL)
  Serial.printf("%s %s\n", ok ? "PUB" : "ERR", topic);
}

void setup() {
  Serial.begin(115200);
  char id[24];
  snprintf(id, sizeof(id), "esp32-%08lx", (unsigned long)(ESP.getEfuseMac() & 0xFFFFFFFF));
  deviceId = id;
  Serial.printf("\ndevice_id (login MQTT): %s\n", id);
  snprintf(statusTopic, sizeof(statusTopic), "lab/%s/%s/status", GROUP_ID, id);
  if (!bmp.begin(I2C_SDA, I2C_SCL, BMP_ADDR)) Serial.println("Nie znaleziono BMP280");
  connectWiFi();
#if TRYB_TLS == 1
  net.setInsecure();
#elif TRYB_TLS == 2
  net.setCACert(CA_CERT);
#endif
  mqtt.setServer(MQTT_HOST, PORT);     // adres jako tekst: TLS porównuje go z certyfikatem brokera
  mqtt.setBufferSize(512);
}

void loop() {
  if (!mqtt.connected()) {
    if (millis() - lastTryMs >= RECONNECT_MS) {   // bez blokowania pętli (jak w Laboratorium 2)
      lastTryMs = millis();
      connectMqtt();
    }
  } else {
    mqtt.loop();
  }
  if (millis() - lastPublishMs >= PUBLISH_MS) {
    lastPublishMs = millis();
    BmpReading r = bmp.read();
    if (r.ok && mqtt.connected()) {
      publishPressure(deviceId.c_str(), r.pressure_hpa);
#if TEST_ACL
      if (seq % 2) publishPressure("esp32-obcy", r.pressure_hpa);   // cudzy device_id: broker odrzuci po cichu
#endif
    }
  }
}
