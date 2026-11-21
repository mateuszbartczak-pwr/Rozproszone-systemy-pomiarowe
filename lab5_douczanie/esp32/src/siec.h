// Laboratorium 5: sieć 2-4-2 z Laboratorium 4 w zwykłym C++ (float) -- wnioskowanie i douczanie (SGD).
// TFLM z Laboratorium 4 umie tylko wnioskować: nie liczy gradientów, a wagi int8 trzyma we flashu (tylko do odczytu).
// Do douczania potrzebne są wagi float w RAM i własne wzory na gradient -- przy 22 parametrach to kilkadziesiąt linii.
#pragma once

struct Siec {
  float W1[4][2], b1[4];   // warstwa ukryta:   h = relu(W1 x + b1)
  float W2[2][4], b2[2];   // warstwa wyjściowa: z = W2 h + b2,  p = softmax(z)
  float h[4], p[2];        // wynik ostatniego przejścia w przód -- potrzebny do gradientu

  void wczytaj(const float w1[4][2], const float c1[4], const float w2[2][4], const float c2[2]);
  int przod(const float x[2]);                     // zwraca klasę 0/1, wypełnia h[] i p[]
  float krok(const float x[2], int y, float lr);   // jeden krok SGD dla przykładu (x, y); zwraca stratę przed krokiem
};
