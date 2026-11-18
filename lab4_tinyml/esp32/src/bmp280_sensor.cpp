#include "bmp280_sensor.h"
#include <Wire.h>
#include <math.h>

bool Bmp280Sensor::begin(int sda, int scl, uint8_t address, uint8_t chipId) {
  Wire.begin(sda, scl);
  ready_ = bmp_.begin(address, chipId);
  if (!ready_) return false;
  bmp_.setSampling(Adafruit_BMP280::MODE_NORMAL, Adafruit_BMP280::SAMPLING_X2,
                   Adafruit_BMP280::SAMPLING_X16, Adafruit_BMP280::FILTER_X16,
                   Adafruit_BMP280::STANDBY_MS_500);
  return true;
}

void Bmp280Sensor::setMlMode() {
  bmp_.setSampling(Adafruit_BMP280::MODE_NORMAL,
                   Adafruit_BMP280::SAMPLING_X2,    // temperatura
                   Adafruit_BMP280::SAMPLING_X16,   // ciśnienie: szum ok. 1,3 Pa RMS
                   Adafruit_BMP280::FILTER_OFF,     // bez IIR: szybka reakcja na zdarzenie
                   Adafruit_BMP280::STANDBY_MS_1);  // pomiar ok. 38 ms -> 10 Hz się mieści
}

BmpReading Bmp280Sensor::read() {
  BmpReading r{NAN, NAN, false};
  if (!ready_) return r;
  r.temperature_c = bmp_.readTemperature();
  r.pressure_hpa  = bmp_.readPressure() / 100.0f;
  r.ok = !isnan(r.temperature_c) && !isnan(r.pressure_hpa) &&
         r.pressure_hpa > 300.0f && r.pressure_hpa < 1100.0f;
  return r;
}
