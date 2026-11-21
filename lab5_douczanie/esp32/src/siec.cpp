// Laboratorium 5: sieć 2-4-2 -- przejście w przód i krok SGD (entropia krzyżowa, softmax, ReLU).
#include "siec.h"
#include <math.h>
#include <string.h>

void Siec::wczytaj(const float w1[4][2], const float c1[4], const float w2[2][4], const float c2[2]) {
  memcpy(W1, w1, sizeof W1);
  memcpy(b1, c1, sizeof b1);
  memcpy(W2, w2, sizeof W2);
  memcpy(b2, c2, sizeof b2);
}

int Siec::przod(const float x[2]) {
  for (int j = 0; j < 4; j++) {
    float a = b1[j] + W1[j][0] * x[0] + W1[j][1] * x[1];
    h[j] = a > 0 ? a : 0;                      // ReLU
  }
  float z[2];
  for (int k = 0; k < 2; k++) {
    z[k] = b2[k];
    for (int j = 0; j < 4; j++) z[k] += W2[k][j] * h[j];
  }
  float m = z[0] > z[1] ? z[0] : z[1];         // odejmujemy maksimum: exp() bez przepełnienia
  float e0 = expf(z[0] - m), e1 = expf(z[1] - m);
  p[0] = e0 / (e0 + e1);
  p[1] = e1 / (e0 + e1);
  return p[1] > p[0] ? 1 : 0;
}

float Siec::krok(const float x[2], int y, float lr) {
  przod(x);
  float strata = -logf(p[y] > 1e-7f ? p[y] : 1e-7f);

  // TODO (zadanie 2): gradient i krok SGD -- wzory w instrukcji, kolejność:
  //   1. błąd na wyjściu dz[2] (softmax + entropia krzyżowa),
  //   2. błąd w warstwie ukrytej dh[4] -- policz go PRZED zmianą W2, pamiętaj o ReLU,
  //   3. zmiana wag: W2, b2, W1, b1 (w -= lr * gradient).
  // Po wgraniu firmware sprawdza Twój kod: linia „# Test gradientu: ... -> OK”.

  return strata;
}
