#pragma once
#include <Adafruit_BMP280.h>

struct BmpReading {
  float temperature_c;   // °C
  float pressure_hpa;    // hPa
  bool ok;
};

class Bmp280Sensor {
public:
  bool begin(int sda, int scl, uint8_t address, uint8_t chipId = BMP280_CHIPID);
  void setMlMode();      // Laboratorium 4: x16 ciśnienie, x2 temperatura, bez IIR, do 10 Hz
  BmpReading read();
private:
  Adafruit_BMP280 bmp_;
  bool ready_ = false;
};
