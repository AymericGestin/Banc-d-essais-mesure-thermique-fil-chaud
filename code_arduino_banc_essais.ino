/*
  Mesure fil chaud - Pont de Wheatstone + INA122
  Sortie série compatible GUI Python : time,temperature
*/

const int pinADC = A0;

// Paramètres ADC
const float VrefADC = 5.0;
const int ADCmax = 1023;

// Pont de Wheatstone
const float Vpont = 5.0;
const float R0 = 10.0;        // résistance fil à T0 (ohms)
const float T0 = 20.0;        // température de référence (°C)
const float alpha = 0.00385;  // platine (adapter au fil)

// INA122
const float VrefINA = 2.5;    // broche REF
const float Gain = 205.0;     // gain INA122 (selon RG)

unsigned long t0;

void setup() {
  Serial.begin(115200);
  t0 = millis();
}

void loop() {
  // Lecture ADC
  int adc = analogRead(pinADC);
  float Vout = adc * VrefADC / ADCmax;

  // Tension différentielle du pont
  float deltaV = (Vout - VrefINA) / Gain;

  // Calcul résistance fil (approx petites variations)
  float Rfil = R0 * (1.0 + (4.0 * deltaV / Vpont));

  // Conversion résistance → température
  float temperature = T0 + (Rfil - R0) / (R0 * alpha);

  // Temps en secondes
  float t = (millis() - t0) / 1000.0;

  // Envoi série (FORMAT STRICT)
  Serial.print(t, 4);
  Serial.print(",");
  Serial.println(temperature, 4);

  delay(50); // 20 Hz
}