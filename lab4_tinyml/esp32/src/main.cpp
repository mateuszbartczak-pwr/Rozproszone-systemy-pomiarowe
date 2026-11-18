// Laboratorium 4: TinyML na ESP32 -- stan płytki z BMP280: leży / podniesiony / nieznany (sieć int8, TFLM)
#include <Arduino.h>
#include <TensorFlowLite_ESP32.h>
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/micro_error_reporter.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/schema/schema_generated.h"
#include "bmp280_sensor.h"
#include "model.h"

#define TRYB_ZBIERANIA 0          // 1: wypisuj CSV do nagrania (zadanie 1), 0: inferencja (zadanie 4)

const int I2C_SDA = 21, I2C_SCL = 22;
const int PRZYCISK = 0;           // BOOT na płytce DevKit (GPIO0), wciśnięty = LOW
const uint8_t BMP_ADDR = 0x76;
const unsigned long OKRES_MS = 100;    // 10 Hz
const int OKNO = 10, KROK = 5;         // okno 1 s, decyzja co 0,5 s -- jak w trening.py
const int N_ODNIESIENIE = 50;          // 5 s na stole: poziom odniesienia

Bmp280Sensor sensor;
unsigned long ostatni = 0;
float bufP[OKNO];
int pozycja = 0;
long ile = 0;
double sumaRef = 0;
int ileRef = 0;
float pRef = NAN;                      // poziom odniesienia „na stole” [Pa]; NAN = jeszcze liczymy

tflite::MicroErrorReporter reporter;
constexpr int ARENA_B = 2 * 1024;
alignas(16) uint8_t arena[ARENA_B];
tflite::MicroInterpreter *interpreter = nullptr;

// Te same dwie cechy co cechy() w trening.py: średnia względem odniesienia i odchylenie standardowe.
void cechy(float f[2]) {
  // TODO (zadanie 4): policz dwie cechy z bufora bufP[0..OKNO-1] (kolejność próbek nie ma znaczenia):
  //   f[0] = średnie ciśnienie w oknie minus pRef [Pa]
  //   f[1] = odchylenie standardowe ciśnienia w oknie [Pa] (populacyjne, jak numpy.std)
  // Wskazówka: licz na różnicach bufP[i] - pRef -- małe liczby, mały błąd float.
}

int regula(const float f[2]) {         // porównanie: próg na ciśnieniu, ruch = nieznany
  if (f[1] > STD_MAX) return 2;
  return f[0] < -6.0f ? 1 : 0;
}

void zerujOdniesienie() {
  sumaRef = 0; ileRef = 0; pRef = NAN; ile = 0;
  Serial.println("# Poziom odniesienia: poloz plytke na stole i nie ruszaj przez 5 s");
}

void setup() {
  Serial.begin(115200);
  pinMode(PRZYCISK, INPUT_PULLUP);
  if (!sensor.begin(I2C_SDA, I2C_SCL, BMP_ADDR)) {
    Serial.println("Nie znaleziono BMP280");
    while (true) delay(1000);
  }
  sensor.setMlMode();
#if TRYB_ZBIERANIA
  Serial.println("ms,p_pa,t_c,btn");
#else
  const tflite::Model *model = tflite::GetModel(g_model);
  static tflite::MicroMutableOpResolver<2> resolver;
  resolver.AddFullyConnected();
  resolver.AddSoftmax();
  static tflite::MicroInterpreter interp(model, resolver, arena, ARENA_B, &reporter);
  interpreter = &interp;
  if (interpreter->AllocateTensors() != kTfLiteOk) {
    Serial.println("AllocateTensors() nie powiodlo sie -- za mala arena?");
    while (true) delay(1000);
  }
  Serial.printf("# Model: %u B, arena: %u z %d B\n", g_model_len,
                (unsigned)interpreter->arena_used_bytes(), ARENA_B);
  zerujOdniesienie();
#endif
}

void loop() {
  if (millis() - ostatni < OKRES_MS) return;
  ostatni += OKRES_MS;
  BmpReading r = sensor.read();
  if (!r.ok) return;
  float p = r.pressure_hpa * 100.0f;   // hPa -> Pa
  bool wcisniety = digitalRead(PRZYCISK) == LOW;
#if TRYB_ZBIERANIA
  Serial.printf("%lu,%.2f,%.3f,%d\n", millis(), p, r.temperature_c, wcisniety ? 1 : 0);
#else
  static bool byl = false;             // krótkie wciśnięcie BOOT: zeruj poziom odniesienia
  if (wcisniety && !byl) zerujOdniesienie();
  byl = wcisniety;

  if (isnan(pRef)) {                   // kalibracja: średnia z 5 s
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

  float f[2];
  cechy(f);
  // TODO (zadanie 4):
  //   1. weź tensory: interpreter->input(0), interpreter->output(0)
  //   2. dla każdej z 2 cech: x = (f[i] - CECHY_SREDNIA[i]) / CECHY_ODCH[i];
  //      q = round(x / in->params.scale) + in->params.zero_point; ogranicz do [-128, 127]; wpisz do in->data.int8[i]
  //   3. zmierz czas interpreter->Invoke() funkcją micros()
  //   4. best = indeks większej z out->data.int8[0], out->data.int8[1];
  //      pewnosc = (out->data.int8[best] - out->params.zero_point) * out->params.scale
  //   5. stan = 2 („nieznany”), jeśli f[1] > STD_MAX albo pewnosc < PEWNOSC_MIN; w przeciwnym razie best
  //   6. wypisz: f[0], f[1], KLASY[stan] z pewnością, KLASY[regula(f)] i czas inferencji
#endif
}
