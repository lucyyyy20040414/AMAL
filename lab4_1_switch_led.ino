/*
 * Lab 4.1 - ESP32 Switch and LED Control
 * 
 * Description: This program reads the state of a push button switch
 * and controls an external LED accordingly. When the button is pressed,
 * the LED lights up.
 * 
 * Hardware Setup:
 * - Switch: Connected to GPIO 4 with internal pull-up resistor
 *   (One side to GPIO 4, other side to GND)
 * - LED: Connected to GPIO 2 through a 220-330Ω resistor
 *   (GPIO 2 -> Resistor -> LED Anode -> LED Cathode -> GND)
 */

// Pin Definitions
const int SWITCH_PIN = 4;  // GPIO pin for the switch input
const int LED_PIN = 2;     // GPIO pin for the LED output

void setup() {
  // Initialize serial communication for debugging
  Serial.begin(115200);
  
  // Configure the switch pin as input with internal pull-up resistor
  // When button is not pressed: pin reads HIGH
  // When button is pressed: pin reads LOW (connected to GND)
  pinMode(SWITCH_PIN, INPUT_PULLUP);
  
  // Configure the LED pin as output
  pinMode(LED_PIN, OUTPUT);
  
  // Ensure LED starts in OFF state
  digitalWrite(LED_PIN, LOW);
  
  Serial.println("ESP32 Switch and LED Control Started");
  Serial.println("Press the button to light the LED");
}

void loop() {
  // Read the state of the switch
  // Note: With INPUT_PULLUP, the logic is inverted:
  // - LOW (0) = button pressed
  // - HIGH (1) = button not pressed
  int switchState = digitalRead(SWITCH_PIN);
  
  // Control LED based on switch state
  if (switchState == LOW) {
    // Button is pressed - turn LED ON
    digitalWrite(LED_PIN, HIGH);
    Serial.println("Button Pressed - LED ON");
  } else {
    // Button is not pressed - turn LED OFF
    digitalWrite(LED_PIN, LOW);
  }
  
  // Small delay for stability and to reduce serial output spam
  delay(50);
}
