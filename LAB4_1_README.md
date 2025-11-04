# Lab 4.1 - ESP32 Switch and LED Control

## Hardware Components Required
- ESP32 Development Board
- Push Button Switch
- LED (any color)
- 220Ω - 330Ω resistor (for LED current limiting)
- Breadboard
- Jumper wires

## Pin Configuration
- **Switch Input:** GPIO 4 (configured with internal pull-up)
- **LED Output:** GPIO 2

## Circuit Schematic Description

```
ESP32 GPIO 4 ----o/ o---- GND
                (Switch)

ESP32 GPIO 2 ----[220Ω]----►|---- GND
                (Resistor) (LED)

Legend:
o/ o = Push button switch
[R] = Resistor
►| = LED (arrow points from anode to cathode)
```

### Detailed Connections:

**Switch Circuit:**
1. One terminal of the switch → ESP32 GPIO 4
2. Other terminal of the switch → GND
3. Internal pull-up resistor enabled in software (no external resistor needed)

**LED Circuit:**
1. ESP32 GPIO 2 → 220Ω Resistor
2. Resistor → LED Anode (longer leg, positive side)
3. LED Cathode (shorter leg, negative side) → GND

## How It Works

1. **Switch Reading:**
   - The switch pin (GPIO 4) is configured with `INPUT_PULLUP`
   - When the button is **not pressed**: Pin reads HIGH (3.3V through internal pull-up)
   - When the button **is pressed**: Pin reads LOW (connected to GND)

2. **LED Control:**
   - When switch reads LOW (pressed): LED pin set to HIGH → LED turns ON
   - When switch reads HIGH (not pressed): LED pin set to LOW → LED turns OFF

## Uploading the Code

1. Open `lab4_1_switch_led.ino` in Arduino IDE
2. Select **Tools → Board → ESP32 Arduino → ESP32 Dev Module** (or your specific ESP32 board)
3. Select the correct COM port under **Tools → Port**
4. Click **Upload**
5. Open Serial Monitor (115200 baud) to see debug messages

## Key Differences: ESP32 vs ATmega328P (Arduino Uno)

| Feature | ESP32 | ATmega328P (Arduino Uno) |
|---------|-------|--------------------------|
| **Operating Voltage** | 3.3V | 5V |
| **GPIO Voltage** | 3.3V logic levels | 5V logic levels |
| **Clock Speed** | 160-240 MHz (dual core) | 16 MHz (single core) |
| **Flash Memory** | 4MB (typical) | 32 KB |
| **SRAM** | 520 KB | 2 KB |
| **Built-in WiFi/BT** | Yes (WiFi + Bluetooth) | No |
| **Number of GPIO** | 34 pins | 14 digital + 6 analog |
| **ADC Resolution** | 12-bit | 10-bit |
| **Internal Pull-ups** | Yes (typically 45kΩ) | Yes (typically 20-50kΩ) |
| **PWM Channels** | 16 channels | 6 channels |

### Important Voltage Considerations:
⚠️ **WARNING:** ESP32 GPIOs are **NOT 5V tolerant**! Always use 3.3V logic. The ATmega328P operates at 5V, so direct interfacing between the two requires level shifting.

### Programming Differences:

1. **Pull-up Resistors:** Both support internal pull-ups via `INPUT_PULLUP`, but ESP32's are typically weaker (45kΩ vs 20-50kΩ)

2. **Power Consumption:** ESP32 has higher power consumption due to more powerful processor and wireless capabilities

3. **Development Environment:** 
   - ATmega: Native Arduino IDE support
   - ESP32: Requires ESP32 board package installation in Arduino IDE

4. **Capabilities for This Lab:**
   - Both can easily handle simple digital I/O tasks like reading a switch and controlling an LED
   - ESP32 is overpowered for this task but offers room for expansion (WiFi control, web interface, etc.)
   - ATmega is more cost-effective for simple digital I/O applications

5. **Boot Considerations:**
   - ESP32 has specific boot mode pins (GPIO 0, GPIO 2) that should be considered when selecting pins
   - GPIO 2 is used in this example and is generally safe for LED output
   - ATmega has no such boot mode restrictions

## Testing

After uploading:
1. Press the button → LED should light up immediately
2. Release the button → LED should turn off
3. Monitor Serial output to see button state messages

## Troubleshooting

- **LED doesn't light up:** Check LED polarity (longer leg to resistor, shorter leg to GND)
- **LED always on/off:** Verify switch connections and that correct pins are used
- **Inverted behavior:** Check if pull-up logic is correct in code
- **ESP32 won't upload:** Hold BOOT button while uploading, or check USB drivers
