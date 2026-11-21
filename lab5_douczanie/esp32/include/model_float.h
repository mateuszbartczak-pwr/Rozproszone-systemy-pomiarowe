// TYMCZASOWY model_float.h -- tylko żeby projekt się kompilował. Sieć z zerowymi wagami odpowiada zawsze „nieznany”.
// Zastąp go plikiem wygenerowanym przez ml/trening.py z Laboratorium 5 (zadanie 0): wagi Twojego modelu z Laboratorium 4.
#pragma once

const float CECHY_SREDNIA[2] = {0.0f, 0.0f};
const float CECHY_ODCH[2]    = {1.0f, 1.0f};
const float STD_MAX = 3.0f;
const float PEWNOSC_MIN = 0.75f;
const char *const KLASY[3] = {"lezy", "podniesiony", "nieznany"};

const float L4_W1[4][2] = {{0.0f, 0.0f}, {0.0f, 0.0f}, {0.0f, 0.0f}, {0.0f, 0.0f}};
const float L4_B1[4]    = {0.0f, 0.0f, 0.0f, 0.0f};
const float L4_W2[2][4] = {{0.0f, 0.0f, 0.0f, 0.0f}, {0.0f, 0.0f, 0.0f, 0.0f}};
const float L4_B2[2]    = {0.0f, 0.0f};
