// Laboratorium 5: douczanie modelu na ESP32 -- ciśnienie dryfuje z pogodą, model z Laboratorium 4 przestaje pasować.
// Dwie sieci 2-4-2 obok siebie: L4 (zamrożona, jak wgrana w produkcie) i douczana na płytce krokami SGD.
// Komendy w monitorze (pio device monitor -b 115200), bez Entera:
//   -  /  +  : symulowany dryf o -10 / +10 Pa      0 : bez dryfu
//   u        : douczanie wł./wył.                    r : sieć douczana z powrotem = L4, pusty bufor
//   z        : zerowanie poziomu odniesienia (5 s na stole)   ? : stan
// Etykiety jak w Laboratorium 4: BOOT wciśnięty, gdy płytka jest w górze i się nie rusza.
#include <Arduino.h>
#include <math.h>
#include "bmp280_sensor.h"
#include "model_float.h"
#include "siec.h"

const int I2C_SDA = 21, I2C_SCL = 22;
const int PRZYCISK = 0;                // BOOT (GPIO0), wciśnięty = LOW
const uint8_t BMP_ADDR = 0x76;
const unsigned long OKRES_MS = 100;    // 10 Hz
const int OKNO = 10, KROK = 5;         // okno 1 s, decyzja co 0,5 s -- jak w Laboratorium 4
const int N_ODNIESIENIE = 50;          // 5 s na stole: poziom odniesienia
const int STALY_BOOT = 20;             // etykieta tylko, gdy BOOT bez zmian od 2 s (okno 1 s + margines 1 s)
const float LR = 0.05f;                // tempo uczenia (learning rate)
const int KROKI = 50;                  // kroki SGD po każdym nowym oknie z etykietą (ok. 0,2 ms przy 22 parametrach)
const int BUF = 32;                    // bufor powtórek: ostatnie 32 okna każdej klasy (16 s)

Bmp280Sensor sensor;
Siec siecL4, siecU;                    // L4: bez zmian; U: douczana
unsigned long ostatni = 0;
float bufP[OKNO];
int pozycja = 0;
long ile = 0;
double sumaRef = 0;
int ileRef = 0;
float pRef = NAN;
float dryfPa = 0;                      // symulowany dryf dodawany do każdego odczytu [Pa]
bool uczenie = false;
bool bylWcisniety = false;
int stalyBoot = 0;                     // ile odczytów z rzędu BOOT jest w tym samym stanie
float bufX[2][BUF][2];                 // [klasa][pozycja][cecha znormalizowana]
int bufN[2] = {0, 0}, bufI[2] = {0, 0};
long krokiSGD = 0;

void cechy(float f[2]) {               // jak w Laboratorium 4
  float s = 0, s2 = 0;
  for (int i = 0; i < OKNO; i++) {
    float d = bufP[i] - pRef;
    s += d; s2 += d * d;
  }
  float m = s / OKNO;
  f[0] = m;
  f[1] = sqrtf(max(0.0f, s2 / OKNO - m * m));
}

int regula(const float f[2]) {
  if (f[1] > STD_MAX) return 2;
  return f[0] < -6.0f ? 1 : 0;
}

int decyzja(Siec &s, const float f[2], const float x[2]) {   // klasa albo 2 = nieznany (jak w L4)
  int k = s.przod(x);
  return (f[1] > STD_MAX || s.p[k] < PEWNOSC_MIN) ? 2 : k;
}

void zerujOdniesienie() {
  sumaRef = 0; ileRef = 0; pRef = NAN; ile = 0;
  Serial.println("# Poziom odniesienia: poloz plytke na stole i nie ruszaj przez 5 s");
}

void dodajDoBufora(const float x[2], int y) {    // bufor kołowy: najstarsze okno danej klasy wypada
  bufX[y][bufI[y]][0] = x[0];
  bufX[y][bufI[y]][1] = x[1];
  bufI[y] = (bufI[y] + 1) % BUF;
  if (bufN[y] < BUF) bufN[y]++;
}

void doucz() {                         // KROKI kroków SGD na losowych oknach z bufora, na przemian klasy
  for (int s = 0; s < KROKI; s++) {
    int y = s % 2;                     // leżenia jest dużo więcej niż podniesień -- bez tego model „zapomni” klasę 1
    if (bufN[y] == 0) continue;
    siecU.krok(bufX[y][random(bufN[y])], y, LR);
    krokiSGD++;
  }
}

// Sprawdzenie krok() z zadania 2: zmiana wag po kroku z małym lr = -lr * gradient, porównana z pochodną
// numeryczną straty (różnica skończona). Nie wymaga czujnika -- wynik widać zaraz po starcie.
float strataDla(Siec &s, const float x[2], int y) {
  s.przod(x);
  return -logf(s.p[y]);
}

void testGradientu() {
  const float x[2] = {0.3f, 0.5f};
  const int y = 1;
  const float lr = 1e-3f, eps = 1e-2f;
  Siec a, b;
  a.wczytaj(L4_W1, L4_B1, L4_W2, L4_B2);
  b = a;
  b.krok(x, y, lr);
  float *pa[4] = {&a.W1[0][0], a.b1, &a.W2[0][0], a.b2}, *pb[4] = {&b.W1[0][0], b.b1, &b.W2[0][0], b.b2};
  const int ile[4] = {8, 4, 8, 2};
  float maxBlad = 0, maxGrad = 0;
  for (int t = 0; t < 4; t++) {
    for (int i = 0; i < ile[t]; i++) {
      float w = pa[t][i];
      pa[t][i] = w + eps; float Lp = strataDla(a, x, y);
      pa[t][i] = w - eps; float Lm = strataDla(a, x, y);
      pa[t][i] = w;
      float numeryczny = (Lp - Lm) / (2 * eps);
      float zKroku = (w - pb[t][i]) / lr;
      maxBlad = max(maxBlad, fabsf(numeryczny - zKroku));
      maxGrad = max(maxGrad, fabsf(numeryczny));
    }
  }
  bool ok = maxBlad < 0.02f * maxGrad + 1e-3f;
  Serial.printf("# Test gradientu: max |numeryczny - z krok()| = %.4f przy max |gradient| = %.4f -> %s\n",
                maxBlad, maxGrad, ok ? "OK" : "BLAD (popraw krok() w siec.cpp)");
}

void stan() {
  Serial.printf("# dryf %+.0f Pa | douczanie %s | bufor lezy/podn %d/%d | krokow SGD %ld | p_ref %.1f Pa\n",
                dryfPa, uczenie ? "WL" : "wyl", bufN[0], bufN[1], krokiSGD, pRef);
}

void komendy() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '-') dryfPa -= 10;
    else if (c == '+') dryfPa += 10;
    else if (c == '0') dryfPa = 0;
    else if (c == 'u') uczenie = !uczenie;
    else if (c == 'r') {
      siecU.wczytaj(L4_W1, L4_B1, L4_W2, L4_B2);
      bufN[0] = bufN[1] = bufI[0] = bufI[1] = 0;
      krokiSGD = 0;
    }
    else if (c == 'z') zerujOdniesienie();
    else if (c != '?') continue;
    stan();
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PRZYCISK, INPUT_PULLUP);
  delay(500);
  testGradientu();
  unsigned long t0 = micros();
  { Siec s; s.wczytaj(L4_W1, L4_B1, L4_W2, L4_B2); const float x[2] = {0.3f, 0.5f};
    for (int i = 0; i < 1000; i++) s.krok(x, i % 2, LR); }
  Serial.printf("# 1000 krokow SGD: %lu us\n", micros() - t0);
  if (!sensor.begin(I2C_SDA, I2C_SCL, BMP_ADDR)) {
    Serial.println("Nie znaleziono BMP280");
    while (true) delay(1000);
  }
  sensor.setMlMode();
  siecL4.wczytaj(L4_W1, L4_B1, L4_W2, L4_B2);
  siecU.wczytaj(L4_W1, L4_B1, L4_W2, L4_B2);
  randomSeed(esp_random());
  Serial.printf("# Siec 2-4-2: %u B wag float na kopie; bufor powtorek %u B\n",
                (unsigned)(sizeof(siecU.W1) + sizeof(siecU.b1) + sizeof(siecU.W2) + sizeof(siecU.b2)),
                (unsigned)sizeof(bufX));
  Serial.println("# Komendy: - + 0 (dryf), u (douczanie), r (reset), z (zerowanie), ? (stan)");
  zerujOdniesienie();
}

void loop() {
  komendy();
  if (millis() - ostatni < OKRES_MS) return;
  ostatni += OKRES_MS;
  BmpReading r = sensor.read();
  if (!r.ok) return;
  float p = r.pressure_hpa * 100.0f + dryfPa;    // symulacja: pogoda przesuwa wszystkie odczyty
  bool wcisniety = digitalRead(PRZYCISK) == LOW;
  stalyBoot = (wcisniety == bylWcisniety) ? stalyBoot + 1 : 0;
  bylWcisniety = wcisniety;

  if (isnan(pRef)) {
    sumaRef += p;
    if (++ileRef == N_ODNIESIENIE) {
      pRef = sumaRef / ileRef;
      Serial.printf("# p_ref = %.1f Pa\n", pRef);
    }
    return;
  }

  bufP[pozycja] = p;
  pozycja = (pozycja + 1) % OKNO;
  if (++ile < OKNO || ile % KROK != 0) return;

  float f[2], x[2];
  cechy(f);
  for (int i = 0; i < 2; i++) x[i] = (f[i] - CECHY_SREDNIA[i]) / CECHY_ODCH[i];
  bool pozaZakresem = fabsf(x[0]) > 3.0f;        // cecha daleko od danych treningowych: znak dryfu

  // Etykieta z przycisku: tylko okna bez ruchu i z BOOT niezmienionym od 2 s
  int etykieta = -1;
  if (stalyBoot >= STALY_BOOT && f[1] <= STD_MAX) etykieta = wcisniety ? 1 : 0;

  unsigned long dt = 0;
  if (uczenie && etykieta >= 0) {
    dodajDoBufora(x, etykieta);
    unsigned long t0 = micros();
    doucz();
    dt = micros() - t0;
  }

  int sL4 = decyzja(siecL4, f, x), sU = decyzja(siecU, f, x);
  Serial.printf("dp=%6.1f std=%4.1f | L4: %-11s (%.2f) | douczany: %-11s (%.2f) | regula: %-11s | etykieta: %-11s%s",
                f[0], f[1], KLASY[sL4], siecL4.p[siecL4.p[1] > siecL4.p[0]], KLASY[sU], siecU.p[siecU.p[1] > siecU.p[0]],
                KLASY[regula(f)], etykieta < 0 ? "-" : KLASY[etykieta], pozaZakresem ? " | POZA ZAKRESEM" : "");
  if (dt) Serial.printf(" | SGD %lu us", dt);
  Serial.println();
}
