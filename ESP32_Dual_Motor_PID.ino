// ====== ESP32-S2 + L298N Dual Motor PID (counts/s) + AP Web UI ======
// DEBUGGED VERSION with fixes for:
// - Missing web_ui.h (now created)
// - ESP32-S2 pin compatibility warnings
// - Deprecated LEDC API (added compatibility layer)
// - Improved PID anti-windup logic
// - Better error handling

// 0) Core + Wi-Fi/Web
#include <Arduino.h>
#include <math.h>
#include <WiFi.h>
#include <WebServer.h>
#include "web_ui.h"   // provides: const char INDEX_HTML[] PROGMEM

// 1) Pin map
// ⚠️ WARNING for ESP32-S2 users:
// - GPIO 35, 36 do NOT exist on ESP32-S2 (they exist on ESP32 classic only)
// - GPIO 11, 10 are FLASH pins on ESP32-S2 and may cause boot issues
// - Please verify your actual hardware pin assignments!
// 
// Recommended safe ESP32-S2 pins for encoders:
// - Use GPIO 1-9, 12-14, 18, 21, 33, 34, 37-42 (avoid 11, 19, 20)

// Motor A (left)
#define ENA    17    // PWM capable
#define IN1    15
#define IN2    16
#define ENC_A1 11    // ⚠️ FLASH pin on ESP32-S2! Consider using GPIO 12 or 13
#define ENC_B1 10    // ⚠️ FLASH pin on ESP32-S2! Consider using GPIO 14 or 18

// Motor B (right)
#define ENB    39    // PWM capable
#define IN3    41
#define IN4    40
#define ENC_A2 35    // ⚠️ Does NOT exist on ESP32-S2! Use GPIO 37 or 38 instead
#define ENC_B2 36    // ⚠️ Does NOT exist on ESP32-S2! Use GPIO 42 or 33 instead

// 2) PWM / control params
const int PWM_BITS = 10;
const int PWM_MAX  = (1 << PWM_BITS) - 1;  // 1023
const int PWM_FREQ = 5000;                 // 5 kHz
const int LEDC_CH_A = 0;
const int LEDC_CH_B = 1;

const uint32_t SAMPLE_MS = 50;             // Control period (50ms = 20Hz)
const int MIN_DUTY_START = 180;            // Minimum duty for motor startup (tune as needed)
const int DUTY_MIN = 0;
const int DUTY_MAX = PWM_MAX;

// PID gains (Ki, Kd already scaled by Ts)
// These gains work well for typical DC motors at 50ms sample time
// Tune these values based on your specific motors!
float Kp = 1.0f;      // Proportional gain
float Ki = 0.40f;     // Integral gain (= Ki_continuous * Ts, where Ts=0.05s)
float Kd = 0.004f;    // Derivative gain (= Kd_continuous / Ts)

const float Ts   = SAMPLE_MS / 1000.0f;    // 0.05 s
const float I_MAX = 300.0f;                // Integral clamp (tune as needed)

// 3) Encoder state
volatile long encCount1 = 0;
volatile long encCount2 = 0;

// 4) Motor structure
struct Motor {
  // pins
  int inA, inB, en, ledc_ch;
  // encoder
  volatile long* pCount;
  long lastCount = 0;
  // speed & PID
  float target = 0.0f;   // Target speed (counts/s) - can be positive or negative
  float speed  = 0.0f;   // Actual speed (counts/s)
  float err    = 0.0f, errPrev = 0.0f;
  float integ  = 0.0f;
  float deriv  = 0.0f;
  float u      = 0.0f;   // Unclamped control signal (with sign)
  int   duty   = 0;      // 0..1023
  int   dir    = 1;      // +1 FWD, -1 REV
};

// 5) Create motors
Motor M1{IN1, IN2, ENA, LEDC_CH_A, &encCount1};
Motor M2{IN3, IN4, ENB, LEDC_CH_B, &encCount2};

// 6) ISRs: x4 quadrature encoding
void IRAM_ATTR isrA1() {
  if (digitalRead(ENC_A1) == digitalRead(ENC_B1)) encCount1++;
  else                                            encCount1--;
}
void IRAM_ATTR isrB1() {
  if (digitalRead(ENC_A1) == digitalRead(ENC_B1)) encCount1--;
  else                                            encCount1++;
}
void IRAM_ATTR isrA2() {
  if (digitalRead(ENC_A2) == digitalRead(ENC_B2)) encCount2++;
  else                                            encCount2--;
}
void IRAM_ATTR isrB2() {
  if (digitalRead(ENC_A2) == digitalRead(ENC_B2)) encCount2--;
  else                                            encCount2++;
}

// 7) LEDC compatibility wrapper for different ESP32 Arduino Core versions
// Newer cores (3.x) use ledcAttach() instead of ledcSetup()+ledcAttachPin()
void setupLEDC(int pin, int channel, int freq, int resolution) {
  #if ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 0, 0)
    // New API (ESP32 Arduino Core 3.x+)
    ledcAttach(pin, freq, resolution);
  #else
    // Legacy API (ESP32 Arduino Core 2.x and earlier)
    ledcSetup(channel, freq, resolution);
    ledcAttachPin(pin, channel);
  #endif
}

void writeLEDC(int channel, int pin, int duty) {
  #if ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 0, 0)
    // New API - write directly to pin
    ledcWrite(pin, duty);
  #else
    // Legacy API - write to channel
    ledcWrite(channel, duty);
  #endif
}

// 8) GPIO & PWM setup
void setupPins() {
  // Check for problematic pins on ESP32-S2
  #ifdef CONFIG_IDF_TARGET_ESP32S2
    Serial.println(F("⚠️  WARNING: You are using ESP32-S2!"));
    Serial.println(F("⚠️  GPIO 35, 36 do NOT exist on ESP32-S2"));
    Serial.println(F("⚠️  GPIO 11, 10 are FLASH pins - may cause boot issues"));
    Serial.println(F("⚠️  Please verify your pin assignments!"));
  #endif

  // Motor direction pins
  pinMode(M1.inA, OUTPUT);
  pinMode(M1.inB, OUTPUT);
  pinMode(M2.inA, OUTPUT);
  pinMode(M2.inB, OUTPUT);
  
  // Enable pins (PWM outputs)
  pinMode(M1.en, OUTPUT);
  pinMode(M2.en, OUTPUT);

  // Encoders with pull-ups
  pinMode(ENC_A1, INPUT_PULLUP); 
  pinMode(ENC_B1, INPUT_PULLUP);
  pinMode(ENC_A2, INPUT_PULLUP); 
  pinMode(ENC_B2, INPUT_PULLUP);

  // Attach interrupts
  attachInterrupt(digitalPinToInterrupt(ENC_A1), isrA1, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENC_B1), isrB1, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENC_A2), isrA2, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENC_B2), isrB2, CHANGE);

  // PWM setup with compatibility wrapper
  setupLEDC(M1.en, LEDC_CH_A, PWM_FREQ, PWM_BITS);
  setupLEDC(M2.en, LEDC_CH_B, PWM_FREQ, PWM_BITS);
}

// 9) Apply direction & duty to one motor
void applyMotor(Motor& m) {
  // Determine direction from control signal sign
  m.dir = (m.u >= 0.0f) ? +1 : -1;

  // Calculate duty with deadzone compensation
  float mag = fabsf(m.u);
  
  if (mag < 1.0f) {
    // Dead zone - stop motor
    m.duty = 0;
  } else {
    // Clamp magnitude
    if (mag > PWM_MAX) mag = PWM_MAX;
    
    // Linear mapping with deadzone compensation:
    // duty = MIN_DUTY_START + (mag / PWM_MAX) * (PWM_MAX - MIN_DUTY_START)
    float dutyF = MIN_DUTY_START + (mag * (PWM_MAX - MIN_DUTY_START)) / PWM_MAX;
    if (dutyF > PWM_MAX) dutyF = PWM_MAX;
    m.duty = (int)(dutyF + 0.5f);
  }

  // Set L298N direction pins
  if (m.duty == 0) {
    // Coast mode
    digitalWrite(m.inA, LOW);
    digitalWrite(m.inB, LOW);
  } else if (m.dir > 0) {
    // Forward
    digitalWrite(m.inA, HIGH);
    digitalWrite(m.inB, LOW);
  } else {
    // Reverse
    digitalWrite(m.inA, LOW);
    digitalWrite(m.inB, HIGH);
  }

  // Write PWM with compatibility wrapper
  writeLEDC(m.ledc_ch, m.en, m.duty);
}

// 10) PID step with improved anti-windup
void pidStep(Motor& m) {
  // Calculate error
  m.err = m.target - m.speed;
  
  // Proportional term
  float P = Kp * m.err;

  // Integral term with back-calculation anti-windup
  // Only integrate when:
  // 1. Not saturated, OR
  // 2. Saturated but error would reduce saturation
  bool saturatingHigh = (m.duty >= PWM_MAX && m.u >= PWM_MAX);
  bool saturatingLow  = (m.duty >= PWM_MAX && m.u <= -PWM_MAX);
  
  bool shouldIntegrate = true;
  if (saturatingHigh && m.err > 0) shouldIntegrate = false;  // Don't wind up further
  if (saturatingLow && m.err < 0)  shouldIntegrate = false;  // Don't wind down further
  
  if (shouldIntegrate) {
    m.integ += Ki * m.err;          // Ki already includes Ts scaling
    // Clamp integral
    if (m.integ >  I_MAX) m.integ =  I_MAX;
    if (m.integ < -I_MAX) m.integ = -I_MAX;
  }

  // Derivative term (on error)
  m.deriv   = Kd * (m.err - m.errPrev);   // Kd already includes Ts scaling
  m.errPrev = m.err;

  // Total control signal
  m.u = P + m.integ + m.deriv;
  
  // Apply to motor
  applyMotor(m);
}

// 11) Speed estimate: counts/s over Ts
void updateSpeed(Motor& m) {
  noInterrupts();
  long nowCnt = *(m.pCount);
  interrupts();
  
  long delta = nowCnt - m.lastCount;   // Signed difference
  m.lastCount = nowCnt;
  m.speed = (float)delta / Ts;         // counts per second
}

// 12) Serial command helper: "<L> <R>" or "stop"
void handleSerial() {
  if (!Serial.available()) return;

  String s = Serial.readStringUntil('\n');
  s.trim();
  if (!s.length()) return;

  if (s.equalsIgnoreCase("stop")) {
    M1.target = 0; 
    M2.target = 0;
    Serial.println(F("STOP command received"));
    return;
  }

  // Parse two integers
  int spL, spR;
  if (sscanf(s.c_str(), "%d %d", &spL, &spR) == 2) {
    M1.target = (float)spL;
    M2.target = (float)spR;
    Serial.printf("Serial CMD: L=%d R=%d\n", spL, spR);
  } else {
    Serial.println(F("Invalid format. Use: <left> <right> or stop"));
  }
}

// 13) AP + HTTP (Web UI + endpoints)
WebServer server(80);
const char* AP_SSID = "DD-DRIVE";
const char* AP_PSWD = "";  // Open AP (no password). Set password for security.
IPAddress   AP_IP(192,168,4,1), GW(192,168,4,1), NET(255,255,255,0);
const int   CMD_CLAMP = 2000;  // Safety clamp for incoming l/r targets

void setupAPAndHTTP() {
  // Configure and start Access Point
  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(AP_IP, GW, NET);
  bool apOK = WiFi.softAP(AP_SSID, AP_PSWD);
  
  if (!apOK) {
    Serial.println(F("❌ Failed to start AP!"));
  } else {
    Serial.println(F("✓ AP started successfully"));
    Serial.print(F("   SSID: ")); Serial.println(AP_SSID);
    Serial.print(F("   IP: ")); Serial.println(WiFi.softAPIP());
  }

  // Serve the web UI page
  server.on("/", HTTP_GET, [](){
    server.send_P(200, "text/html; charset=utf-8", INDEX_HTML);
  });

  // Command: /cmd?l=<int>&r=<int>
  server.on("/cmd", HTTP_GET, [](){
    if (!server.hasArg("l") || !server.hasArg("r")) {
      server.send(400, "text/plain", "Error: missing l or r parameter");
      return;
    }
    int l = constrain(server.arg("l").toInt(), -CMD_CLAMP, CMD_CLAMP);
    int r = constrain(server.arg("r").toInt(), -CMD_CLAMP, CMD_CLAMP);
    M1.target = (float)l;
    M2.target = (float)r;
    
    char buf[64];
    snprintf(buf, sizeof(buf), "OK L=%d R=%d", l, r);
    server.send(200, "text/plain", buf);
    Serial.println(buf);
  });

  // Stop both motors
  server.on("/stop", HTTP_GET, [](){
    M1.target = 0; 
    M2.target = 0;
    server.send(200, "text/plain", "OK STOP");
    Serial.println(F("Web STOP command"));
  });

  // Telemetry JSON: targets + current speeds
  server.on("/telemetry", HTTP_GET, [](){
    char j[256];
    snprintf(j, sizeof(j),
      "{\"l\":{\"tgt\":%.1f,\"cur\":%.1f},\"r\":{\"tgt\":%.1f,\"cur\":%.1f}}",
      M1.target, M1.speed, M2.target, M2.speed);
    server.send(200, "application/json", j);
  });

  server.begin();
  Serial.println(F("✓ HTTP server started"));
}

// 14) Arduino entry points
uint32_t lastMs = 0;

void setup() {
  Serial.begin(115200);
  delay(500);  // Give serial time to initialize

  Serial.println(F("\n\n========================================"));
  Serial.println(F("  DD-DRIVE Dual Motor PID Controller"));
  Serial.println(F("  ESP32-S2 + L298N + Web UI"));
  Serial.println(F("========================================"));

  // Print version info
  Serial.print(F("ESP32 Arduino Core: "));
  Serial.println(ESP_ARDUINO_VERSION_MAJOR * 10000 + 
                 ESP_ARDUINO_VERSION_MINOR * 100 + 
                 ESP_ARDUINO_VERSION_PATCH);

  setupPins();
  setupAPAndHTTP();

  // Initialize targets
  M1.target = 0;
  M2.target = 0;

  Serial.println(F("\n[READY] System initialized"));
  Serial.println(F("[INFO] Serial commands: \"<L> <R>\" (counts/s) or \"stop\""));
  Serial.println(F("[INFO] Web UI: http://192.168.4.1"));
  Serial.println(F("========================================\n"));
}

void loop() {
  // Handle HTTP requests
  server.handleClient();
  
  // Handle serial commands
  handleSerial();

  // PID control loop at fixed rate
  uint32_t now = millis();
  if (now - lastMs >= SAMPLE_MS) {
    lastMs = now;

    // Update speed estimates
    updateSpeed(M1);
    updateSpeed(M2);

    // Run PID controllers
    pidStep(M1);
    pidStep(M2);

    // Print telemetry (comment out to reduce serial traffic)
    Serial.printf("[L] tgt=%6.1f cur=%6.1f err=%6.1f | u=%7.1f duty=%4d  ||  ",
                  M1.target, M1.speed, M1.err, M1.u, M1.duty);
    Serial.printf("[R] tgt=%6.1f cur=%6.1f err=%6.1f | u=%7.1f duty=%4d\n",
                  M2.target, M2.speed, M2.err, M2.u, M2.duty);
  }
}
