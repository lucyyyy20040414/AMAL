/*
 * Lab 4.1 - ESP32 Switch and LED Control
 * 
 * This program reads the state of a switch/button and controls an LED accordingly.
 * When the button is pressed, the LED turns on. When released, the LED turns off.
 * 
 * Hardware Setup:
 * ---------------
 * Button/Switch:
 *   - One side of switch connected to GPIO 4
 *   - Other side of switch connected to GND
 *   - Internal pull-up resistor enabled in code (no external resistor needed)
 * 
 * LED:
 *   - LED anode (longer leg/+) connected to 220Ω resistor
 *   - Resistor connected to GPIO 2
 *   - LED cathode (shorter leg/-) connected to GND
 * 
 * GPIO Pin Selection Notes:
 * -------------------------
 * - GPIO 2: Safe for output, commonly used for LED control
 * - GPIO 4: Safe for input, good for button/switch
 * - Avoid GPIO 6-11 (connected to flash memory)
 * - Avoid GPIO 0 (boot mode selection)
 * 
 * Circuit Diagram:
 * ----------------
 *           ESP32
 *            ___
 *           |   |
 *  Button --| 4 |  (with internal pull-up to 3.3V)
 *     |     |   |
 *    GND    | 2 |--- 220Ω --- LED --- GND
 *           |___|
 * 
 * Differences from ATmega328P (Arduino Uno):
 * ------------------------------------------
 * 1. Voltage Levels: ESP32 uses 3.3V logic vs 5V on ATmega328P
 *    - All GPIO pins are 3.3V tolerant only (NOT 5V tolerant!)
 * 2. GPIO Pins: ESP32 has more GPIO pins (30+ vs 14 digital on Uno)
 * 3. Processing Power: ESP32 has dual-core 240MHz vs single-core 16MHz
 * 4. Memory: ESP32 has more RAM (520KB vs 2KB) and Flash (4MB vs 32KB)
 * 5. Connectivity: ESP32 has built-in WiFi and Bluetooth (ATmega328P has none)
 * 6. ADC Resolution: ESP32 has 12-bit ADC vs 10-bit on ATmega328P
 * 7. Pin Restrictions: Some ESP32 pins have special functions and limitations
 *    - Some pins are input-only (GPIO 34-39)
 *    - Some pins affect boot mode (GPIO 0, 2, 12, 15)
 * 8. Programming: Both use Arduino IDE but different board packages
 */

// Pin Definitions
const int BUTTON_PIN = 4;  // GPIO 4 for button input
const int LED_PIN = 2;     // GPIO 2 for LED output

void setup() {
  // Initialize serial communication for debugging
  Serial.begin(115200);  // ESP32 typically uses 115200 baud rate
  
  // Configure button pin as input with internal pull-up resistor
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  
  // Configure LED pin as output
  pinMode(LED_PIN, OUTPUT);
  
  // Ensure LED starts in OFF state
  digitalWrite(LED_PIN, LOW);
  
  Serial.println("ESP32 Switch and LED Control Initialized");
  Serial.println("Press the button to turn ON the LED");
}

void loop() {
  // Read the button state (LOW = pressed due to pull-up configuration)
  int buttonState = digitalRead(BUTTON_PIN);
  
  // When button is pressed (reads LOW), turn LED ON
  // When button is released (reads HIGH), turn LED OFF
  if (buttonState == LOW) {
    digitalWrite(LED_PIN, HIGH);  // Turn LED ON
    Serial.println("Button PRESSED - LED ON");
  } else {
    digitalWrite(LED_PIN, LOW);   // Turn LED OFF
    Serial.println("Button RELEASED - LED OFF");
  }
  
  // Small delay to debounce and reduce serial output
  delay(100);
}
