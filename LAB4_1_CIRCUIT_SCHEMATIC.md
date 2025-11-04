# Lab 4.1 - Circuit Schematic and Report Notes

## Circuit Schematic

```
                    ESP32
          ┌──────────────────┐
          │                  │
          │              3.3V├────┐
          │                  │    │
          │                  │   ┌┴┐
    ┌─────┤ GPIO 4           │   │ │ 10kΩ (optional, internal pull-up used)
    │     │                  │   └┬┘
    │     │                  │    │
   ╱─╲    │                  │    ╱
   ╲ ╱ SW │                  │    
    │     │                  │    
    │     │                  │    
    └──┬──┤ GND              │
       │  │                  │
       │  │                  │
    ┌──┼──┤ GPIO 2           ├────┐
    │  │  │                  │    │
   GND │  │                  │   ┌┴┐
       │  │                  │   │ │ 220Ω Resistor
       │  └──────────────────┘   └┬┘
       │                           │
       │                          ┌▼┐ LED
       │                          └┬┘
       │                           │
       └───────────────────────────┘
```

## Component List

1. **ESP32 Development Board** (1x)
2. **Push Button / Switch** (1x) - SPST (Single Pole Single Throw)
3. **LED** (1x) - Any color (Red, Green, Blue, etc.)
4. **220Ω Resistor** (1x) - For LED current limiting
5. **Jumper Wires** - For connections
6. **Breadboard** (1x) - For prototyping

## Pin Connections

| Component | Pin | Connection |
|-----------|-----|------------|
| Button (Side 1) | - | GPIO 4 |
| Button (Side 2) | - | GND |
| LED Anode (+) | Long Leg | Via 220Ω resistor to GPIO 2 |
| LED Cathode (-) | Short Leg | GND |

## Key Differences from ATmega328P (Arduino Uno)

### 1. **Voltage Levels**
- **ESP32**: 3.3V logic
  - GPIO pins are NOT 5V tolerant
  - External components must be 3.3V compatible
- **ATmega328P**: 5V logic
  - Most external components work at 5V
  - More robust voltage tolerance

### 2. **GPIO Pin Availability**
- **ESP32**: 
  - 30+ GPIO pins available
  - More flexibility in pin selection
  - Some pins have restrictions (boot pins, input-only pins)
- **ATmega328P**: 
  - 14 digital I/O pins (6 PWM)
  - More straightforward pin usage
  - No special boot restrictions

### 3. **Internal Pull-up/Pull-down Resistors**
- **ESP32**: 
  - Has both internal pull-up and pull-down resistors
  - Configurable via `INPUT_PULLUP` or `INPUT_PULLDOWN`
- **ATmega328P**: 
  - Only has internal pull-up resistors
  - No native pull-down option

### 4. **Processing Power**
- **ESP32**: 
  - Dual-core Xtensa LX6 @ 240 MHz
  - 520 KB SRAM
  - 4 MB Flash (typical)
  - Can handle complex tasks, WiFi, Bluetooth simultaneously
- **ATmega328P**: 
  - Single-core AVR @ 16 MHz
  - 2 KB SRAM
  - 32 KB Flash
  - Limited multitasking capability

### 5. **Connectivity**
- **ESP32**: 
  - Built-in WiFi (802.11 b/g/n)
  - Built-in Bluetooth (Classic & BLE)
  - Ideal for IoT applications
- **ATmega328P**: 
  - No built-in wireless connectivity
  - Requires external modules for wireless communication

### 6. **ADC Resolution**
- **ESP32**: 12-bit ADC (0-4095)
- **ATmega328P**: 10-bit ADC (0-1023)

### 7. **PWM Capability**
- **ESP32**: 
  - 16 PWM channels
  - Flexible PWM configuration
  - LED Control (LEDC) peripheral
- **ATmega328P**: 
  - 6 PWM pins
  - Standard timer-based PWM

### 8. **Boot Mode and Special Pins**
- **ESP32**: 
  - GPIO 0, 2, 12, 15 affect boot mode
  - GPIO 34-39 are input-only
  - GPIO 6-11 typically connected to flash (avoid)
- **ATmega328P**: 
  - All digital pins are general-purpose
  - No boot mode concerns
  - Simpler pin functionality

### 9. **Power Consumption**
- **ESP32**: 
  - Higher power consumption (80-160mA active)
  - Deep sleep modes available (10μA)
  - Better for powered applications
- **ATmega328P**: 
  - Lower active power consumption (15-20mA)
  - Lower sleep current (0.1μA)
  - Better for battery applications

### 10. **Programming**
- **ESP32**: 
  - Uses USB-UART bridge (typically CP2102 or CH340)
  - Requires ESP32 board package in Arduino IDE
  - Automatic bootloader entry via DTR/RTS
- **ATmega328P**: 
  - Uses FTDI or ATMEGA16U2 for USB
  - Native Arduino support
  - Well-established programming tools

## Practical Implications for This Lab

For this simple button and LED control:
- **ESP32 is overkill** - Its advanced features (WiFi, dual-core, etc.) are unused
- **Voltage consideration** - Must ensure all components are 3.3V compatible
- **Pin selection matters** - Need to avoid special function pins
- **Debugging is easier** - Faster serial output (115200 baud typical vs 9600)
- **Future expansion** - Easy to add wireless features later

The **ATmega328P would be more appropriate** for this basic task due to:
- Lower cost
- Lower power consumption
- Simpler pin configuration
- More robust voltage tolerance (5V)

However, **ESP32 is better if**:
- You plan to add WiFi/Bluetooth later
- You need more GPIO pins
- You want to do IoT projects
- You need faster processing

## Testing Procedure

1. Upload the `lab4_1_switch_led.ino` file to your ESP32
2. Open Serial Monitor at 115200 baud
3. Press the button - LED should turn ON
4. Release the button - LED should turn OFF
5. Serial monitor should display button state changes

## Safety Notes

- **Never apply 5V to ESP32 GPIO pins** - They are 3.3V only!
- Use appropriate resistor for LED (220Ω for 3.3V)
- Check LED polarity (long leg = anode/positive)
- Ensure proper connections to avoid short circuits
