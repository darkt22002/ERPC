/*
 * ERPC - Entropy-Regulated Power Control
 * Guided Entropy Principle (GEP) Implementation for Arduino
 * 
 * Hardware Requirements:
 * - Arduino Nano/Uno (16MHz)
 * - Analog inputs for Vout and Iload sensing
 * - PWM output for gate drive
 * 
 * Pin Configuration:
 * A0 - Vout sensing (0-5V via voltage divider)
 * A1 - Iload sensing (via current sense resistor)
 * D9 - PWM gate output (100kHz capable)
 * D13 - Status LED
 * 
 * Serial Debug: 115200 baud
 * 
 * Author: Gary W. Floyd / Lumiea Systems Research
 * Theory: Guided Entropy Principle (GEP)
 * Date: December 24, 2024
 */

// ============================================================================
// CONFIGURATION
// ============================================================================

// GEP Parameters (tunable)
const float ALPHA = 0.3;        // Salience weight
const float BETA = 0.5;         // Gradient weight
const float THRESHOLD = 0.5;    // Entropy threshold (Volts)

// Hardware Configuration
const int PIN_VOUT = A0;        // Voltage sensing
const int PIN_ILOAD = A1;       // Current sensing
const int PIN_PWM = 9;          // PWM output (Timer1, supports high freq)
const int PIN_LED = 13;         // Status indicator

// ADC Configuration
const float VREF = 5.0;         // Arduino Vref
const int ADC_MAX = 1023;       // 10-bit ADC

// Voltage divider ratios (adjust for your circuit)
const float VOUT_SCALE = 2.4;   // If using 10k/10k divider for 12V → 5V
const float ISENSE_SCALE = 1.0; // Amps per volt (depends on sense resistor)

// Timing
const int SAMPLE_RATE_HZ = 10000;  // 10kHz sampling (100us period)
const int PWM_FREQ_HZ = 100000;    // 100kHz PWM base frequency

// Moving average filter
const int FILTER_SIZE = 4;

// ============================================================================
// GLOBAL VARIABLES
// ============================================================================

// Sensor readings
float vout_volts = 0;
float iload_amps = 0;

// Previous readings for gradient calculation
float vout_prev = 0;
float iload_prev = 0;

// GEP components
float error_signal = 0;         // E(t)
float salience_signal = 0;      // A(t)
float gradient_signal = 0;      // |∇S(t)|
float correction_term = 0;      // [1 + α·A - β·|∇S|]
float entropy_field = 0;        // ΔS(t)

// Gate control
bool gate_enabled = false;
int pwm_duty = 0;               // 0-255 for analogWrite

// Timing
unsigned long last_sample_us = 0;
unsigned long sample_count = 0;

// Debug
bool debug_enabled = true;
unsigned long last_debug_ms = 0;

// ============================================================================
// SETUP
// ============================================================================

void setup() {
  // Serial for debugging
  Serial.begin(115200);
  Serial.println("========================================");
  Serial.println("ERPC - Entropy-Regulated Power Control");
  Serial.println("GEP Algorithm Active");
  Serial.println("========================================");
  
  // Pin configuration
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_PWM, OUTPUT);
  
  // Configure Timer1 for high-frequency PWM on D9
  // Fast PWM mode, non-inverted
  // Frequency = 16MHz / (prescaler * (TOP+1))
  // For 100kHz: prescaler=1, TOP=159
  TCCR1A = _BV(COM1A1) | _BV(WGM11);  // Non-inverting mode, Fast PWM
  TCCR1B = _BV(WGM13) | _BV(WGM12) | _BV(CS10);  // Fast PWM, no prescaling
  ICR1 = 159;  // TOP value for 100kHz (16MHz/100kHz - 1)
  OCR1A = 0;   // Start with 0% duty cycle
  
  // Initial ADC read
  vout_volts = readVout();
  iload_amps = readIload();
  vout_prev = vout_volts;
  iload_prev = iload_amps;
  
  Serial.println("Initialization complete.");
  Serial.println("GEP Parameters:");
  Serial.print("  Alpha (salience): "); Serial.println(ALPHA, 3);
  Serial.print("  Beta (gradient): "); Serial.println(BETA, 3);
  Serial.print("  Threshold: "); Serial.print(THRESHOLD, 3); Serial.println("V");
  Serial.println("Ready.");
  Serial.println();
  
  delay(100);
  last_sample_us = micros();
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop() {
  unsigned long now_us = micros();
  
  // Check if it's time for next sample
  if (now_us - last_sample_us >= (1000000 / SAMPLE_RATE_HZ)) {
    last_sample_us = now_us;
    
    // Read sensors
    vout_volts = readVout();
    iload_amps = readIload();
    
    // Calculate GEP components
    calculateGEP();
    
    // Update gate control
    updateGate();
    
    // Increment counter
    sample_count++;
    
    // Debug output every 100ms
    if (debug_enabled && (millis() - last_debug_ms >= 100)) {
      printDebug();
      last_debug_ms = millis();
    }
  }
}

// ============================================================================
// SENSOR READING
// ============================================================================

float readVout() {
  int raw = analogRead(PIN_VOUT);
  float voltage = (raw / (float)ADC_MAX) * VREF;
  return voltage * VOUT_SCALE;  // Scale to actual voltage
}

float readIload() {
  int raw = analogRead(PIN_ILOAD);
  float voltage = (raw / (float)ADC_MAX) * VREF;
  return voltage * ISENSE_SCALE;  // Convert to amps
}

// ============================================================================
// GEP CALCULATION
// ============================================================================

void calculateGEP() {
  // Target voltage (12V system regulated to 5V logic)
  const float VREF_TARGET = 5.0;
  
  // 1. ERROR SIGNAL E(t)
  // Difference between target and actual voltage
  error_signal = VREF_TARGET - vout_volts;
  
  // 2. SALIENCE SIGNAL A(t)
  // Rate of power change (P = V × I)
  float power_now = vout_volts * iload_amps;
  float power_prev = vout_prev * iload_amps;  // Approximate
  salience_signal = abs(power_now - power_prev);
  
  // 3. GRADIENT SIGNAL |∇S(t)|
  // Rate of voltage change (time derivative approximation)
  gradient_signal = abs(vout_volts - vout_prev);
  
  // 4. CORRECTION TERM
  // [1 + α·A(t) - β·|∇S(t)|]
  correction_term = 1.0 + (ALPHA * salience_signal) - (BETA * gradient_signal);
  
  // 5. ENTROPY FIELD ΔS(t)
  // ΔS = E(t) × correction_term
  entropy_field = error_signal * correction_term;
  
  // Store current readings for next iteration
  vout_prev = vout_volts;
  iload_prev = iload_amps;
}

// ============================================================================
// GATE CONTROL
// ============================================================================

void updateGate() {
  // Compare entropy field to threshold
  if (entropy_field > THRESHOLD) {
    // High entropy → Enable switching
    gate_enabled = true;
    pwm_duty = 128;  // 50% duty cycle (adjust as needed)
    digitalWrite(PIN_LED, HIGH);
  } else if (entropy_field < -THRESHOLD) {
    // Negative entropy (undershoot) → Also enable
    gate_enabled = true;
    pwm_duty = 128;
    digitalWrite(PIN_LED, HIGH);
  } else {
    // Low entropy → Skip cycles (light load, good regulation)
    gate_enabled = false;
    pwm_duty = 0;
    digitalWrite(PIN_LED, LOW);
  }
  
  // Update PWM output
  // OCR1A controls duty cycle: 0 to ICR1 (159)
  if (gate_enabled) {
    OCR1A = map(pwm_duty, 0, 255, 0, ICR1);
  } else {
    OCR1A = 0;  // No pulses
  }
}

// ============================================================================
// DEBUG OUTPUT
// ============================================================================

void printDebug() {
  Serial.print("Samples: "); Serial.print(sample_count);
  Serial.print(" | Vout: "); Serial.print(vout_volts, 3);
  Serial.print("V | Iload: "); Serial.print(iload_amps, 3);
  Serial.print("A | E: "); Serial.print(error_signal, 4);
  Serial.print(" | A: "); Serial.print(salience_signal, 4);
  Serial.print(" | ∇S: "); Serial.print(gradient_signal, 4);
  Serial.print(" | Corr: "); Serial.print(correction_term, 4);
  Serial.print(" | ΔS: "); Serial.print(entropy_field, 4);
  Serial.print(" | Gate: "); Serial.print(gate_enabled ? "ON " : "OFF");
  Serial.print(" | PWM: "); Serial.println(pwm_duty);
}

// ============================================================================
// SERIAL COMMAND INTERFACE (Optional)
// ============================================================================

void serialEvent() {
  while (Serial.available()) {
    char cmd = Serial.read();
    
    switch(cmd) {
      case 'd':  // Toggle debug
        debug_enabled = !debug_enabled;
        Serial.print("Debug: ");
        Serial.println(debug_enabled ? "ON" : "OFF");
        break;
        
      case 'r':  // Reset counters
        sample_count = 0;
        Serial.println("Counters reset.");
        break;
        
      case '?':  // Help
        Serial.println("Commands:");
        Serial.println("  d - Toggle debug output");
        Serial.println("  r - Reset counters");
        Serial.println("  ? - This help");
        break;
    }
  }
}
