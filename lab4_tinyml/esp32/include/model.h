// TYMCZASOWY model.h -- pozwala skompilować i wgrać tryb zbierania (TRYB_ZBIERANIA 1).
// Zastąp go plikiem model.h wygenerowanym przez ml/trening.py (zadanie 3).
#pragma once

const float CECHY_SREDNIA[2] = {0, 0};
const float CECHY_ODCH[2] = {1, 1};
const float STD_MAX = 3.0f;
const float PEWNOSC_MIN = 0.75f;
const char *const KLASY[3] = {"lezy", "podniesiony", "nieznany"};

alignas(16) const unsigned char g_model[] = {0};
const unsigned int g_model_len = 1;
