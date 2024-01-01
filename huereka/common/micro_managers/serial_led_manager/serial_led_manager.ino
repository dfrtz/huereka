/*
 * Receiver for optimized byte operations from external driver via serial in order to maximize LED strip efficiency.
 *
 * Uses native low level libraries such as FastLED in order to provide smooth animations. Although refresh rate
 * limiters are provided in a similar manner to FastLED, additional safeguards in the driver code are recommended
 * to ensure best results.
 *
 * Guidelines for max speed of serial ops without flickering/mis-coloring on a 12V strand of WS2811 LEDs with 5V signal.
 * 100 LEDS + 2500 Refresh Rate (400 FPS): ~0.004 (250 OP/s)
 * 200 LEDS + 2500 Refresh Rate (400 FPS): ~0.008 (125 OP/s)
 * 300 LEDS + 2500 Refresh Rate (400 FPS): ~0.011 (90 OP/s)
 *
 * Recommended code style: https://docs.arduino.cc/learn/contributions/arduino-library-style-guide
 */

#include <FastLED.h>

// Default pin used for primary/single LED strip implementations, and setup testing.
// More pins can be added as needed, refer to addLeds() for details around compilation and memory limitations.
// Default pin is 0 for the Raspberry Pi Pico. Change to other GPIO pin based on the the device.
#define PRIMARY_LED_STRIP_PIN 0
// Default serial is "Serial1" for UART. Change to "Serial" for USB.
#define PRIMARY_SERIAL Serial1
// Default UART pins are 16 (TX) and 17 (RX) for the Raspberry Pi Pico. Change to other GPIO pins based on the device.
#define PRIMARY_SERIAL_TX_PIN 16
#define PRIMARY_SERIAL_RX_PIN 17

// ~1024 limit for 4K RAM controllers; can be set higher if system has more memory. Each LED uses 3 bytes.
#define MAX_LEDS 1024
#define MAX_STRIPS 16
#define LED_TYPE WS2811
#define BAUD 115200
#define BUFFER_SIZE 16
#define MAGIC 127

CRGB leds[MAX_LEDS]; // Shared LED array across strips to enforce strict memory usage and match FastLED design.
int ledTotal = 0;
int ledStrips = 0;

bool opStarted = false;
byte serialBuffer[BUFFER_SIZE];

/*
 * Stateful information about an LED strip
 *
 * firstLED: Index of the first LED in the shared LED memory space.
 * lastLED: Index of the last LED in the shared LED memory space.
 * brightness: Brightness level from 0 (off) to 255 (max).
 * refresh: Refresh rate in microseconds between allowed show() operations.
 * lastShow: Last time show() was called in microseconds to determine next allowed refresh.
 * pendingShow: Whether an outstanding show() request is waiting to run.
 */
struct LEDStrip {
  unsigned int firstLED;
  unsigned int lastLED;
  byte brightness;
  unsigned int refreshRate;
  unsigned long lastShow;
  bool pendingShow;
};

struct LEDStrip strips[MAX_STRIPS];

/*
 * Hard reset device.
 */
void(* reset) (void) = 0;

/*
 * Serial buffer management.
 */

/*
 * Read bytes from serial connection into the global buffer.
 *
 * count: Number of bytes to read into the buffer.
 *
 * Returns number of bytes read if successful, or 0 if timeout is reached.
 */
int bufferRead(int count) {
  return PRIMARY_SERIAL.readBytes(serialBuffer, count);
}

/*
 * FastLED helpers (LED Strip aliases for standard global calls with same name).
 */

/*
 * Setup an LED controller and states on a specific GPIO pin.
 *
 * ledPin: GPIO pin where the LED data line is connected
 * ledCount: Number of LEDs on the strip to reserve from the LED array.
 * refresh: Refresh rate in microseconds (e.g. 5000 == 200 FPS, 16000 == ~60 FPS, 33000 == ~30 FPS, etc.).
 */
void addLeds(byte ledPin, unsigned int ledCount, unsigned int refresh) {
  strips[ledStrips].brightness = 255;
  strips[ledStrips].firstLED = ledTotal;
  strips[ledStrips].lastLED = ledTotal + ledCount - 1; // Minus 1 due to 0 base offset for first strip.
  strips[ledStrips].lastShow = 0;
  strips[ledStrips].pendingShow = true;
  for (int i = strips[ledStrips].firstLED; i <= strips[ledStrips].lastLED; i++) {
    leds[i] = CRGB::Black;
  }
  // Add pins here only as needed. Each pin takes ~1500 bytes.
  switch (ledPin) {
    case PRIMARY_LED_STRIP_PIN:
      FastLED.addLeds<LED_TYPE, PRIMARY_LED_STRIP_PIN>(leds, strips[ledStrips].firstLED, strips[ledStrips].lastLED);
      setMaxRefreshRate(ledStrips, refresh, true);
      break;
    default:
      break;
  }
  ledTotal += ledCount;
  ledStrips++;
}

/*
 * Set the brightness on an LED strip.
 *
 * strip: Which LED strip to adjust the brightness on (FastLED index).
 * brightness: Brightness level from 0 (off) to 255 (max).
 */
void setBrightness(byte strip, byte brightness) {
  strips[strip].brightness = brightness;
}

/*
 * Set the max refresh rate on an LED strip.
 *
 * strip: Which LED strip to adjust the refresh on (FastLED index).
 * refresh: Refresh rate in microseconds (e.g. 5000 == 200 FPS, 16000 == ~60 FPS, 33000 == ~30 FPS, etc.).
 * constrain: Whether to enforce the value can only be set higher.
 */
void setMaxRefreshRate(byte strip, unsigned int refresh, bool constrain) {
  if (constrain) {
    strips[strip].refreshRate = (refresh > strips[strip].refreshRate) ? refresh : strips[strip].refreshRate;
  } else {
    strips[strip].refreshRate = refresh;
  }
  if (strips[strip].refreshRate < 2500) {
    // Hard cap at 400 FPS (1 frame per 2500 usec/2.5 ms).
    strips[strip].refreshRate = 2500;
  }
}

/*
 * Schedule an update to display all pending LED changes within max refresh rate.
 *
 * strip: Which LED strip to schedule the update on (FastLED index).
 */
void show(byte strip) {
  strips[strip].pendingShow = true;
}

/*
 * Display all pending updates on an LED strip if within safe refresh rate.
 *
 * strip: Which LED strip to apply the update to (FastLED index).
 */
void showOrSkip(byte strip) {
  unsigned long current = micros();
  if (current < strips[strip].lastShow) {
    // Clock reset, update last show to tell if this is a valid next show.
    if (current > strips[strip].refreshRate) {
      strips[strip].lastShow = current - strips[strip].refreshRate;
    } else {
      // Remaining delay after a rollover is what would be left from the total required delay minus all time passed.
      // e.g., refresh rate (total time) - current time (time passed) - remaining time before rollover (time passed)
      strips[strip].lastShow = strips[strip].refreshRate - (current - (4294967296 - strips[strip].lastShow));
    }
  }
  if ((current - strips[strip].lastShow) < strips[strip].refreshRate) {
    return;
  }
  strips[strip].lastShow = current;
  strips[strip].pendingShow = false;

  CLEDController *ctlr = &FastLED[strip];
  byte d = ctlr->getDither();
  ctlr->setDither(0);
  ctlr->showLeds(strips[strip].brightness);
  ctlr->setDither(d);
}

/*
 * LED Operations from external driver.
 */

/*
 * Listen to the serial buffer for incoming operations.
 */
void listen() {
  // Drain buffer until the "magic" starter is found.
  if (!opStarted && PRIMARY_SERIAL.available() >= 1) {
    byte magic = PRIMARY_SERIAL.read();
    if (magic != MAGIC) {
      return;
    }
    opStarted = true;
  }

  if (opStarted && PRIMARY_SERIAL.available() >= 1) {
    opStarted = false;
    byte op = PRIMARY_SERIAL.read();
    switch (op) {
      // Setup/initialization related ops.
      case 1:
        opInitStrip();
        break;

      // Runtime ops.
      case 32:
        opSetBrightness();
        break;
      case 33:
        opFillLeds();
        break;
      case 34:
        opSetLed();
        break;
      case 35:
        opShow();
        break;
      case 77:
        opTest();
        break;

      // Hard reset device to clear all initialized strips.
      case 99:
        reset();
        break;

      // Unknown op, do nothing.
      default:
        break;
    }
  }
}

/*
 * Perform initialization of an LED strip's state on a specific pin from an op stored in the buffer.
 */
void opInitStrip() {
  if (bufferRead(7)) {
    byte ledType = serialBuffer[0];
    byte ledPin = serialBuffer[1];
    unsigned int ledCount = ((unsigned int) serialBuffer[2] << 8) | (unsigned int) serialBuffer[3];
    unsigned int refresh = ((unsigned int) serialBuffer[4] << 8) | (unsigned int) serialBuffer[5];
    byte ledAnim = serialBuffer[6];
    addLeds(ledPin, ledCount, refresh);
    int stripIndex = ledStrips - 1;
    switch (ledAnim) {
      case 1:
        testRainbow(stripIndex, 128, 255);
        break;
      case 2:
        testRedAlert(stripIndex);
        break;
      default:
        break;
    }
  }
}

/*
 * Fill every LED on an LED strip with the same value from an op stored in the buffer.
 */
void opFillLeds() {
  if (bufferRead(5)) {
    byte strip = serialBuffer[0];
    for (int i = strips[strip].firstLED; i <= strips[strip].lastLED; i++) {
      leds[i].r = serialBuffer[1];
      leds[i].g = serialBuffer[2];
      leds[i].b = serialBuffer[3];
    }
    if (serialBuffer[4]) {
      show(strip);
    }
  }
}

/*
 * Set the brightness on an LED strip from an op stored in the buffer.
 */
void opSetBrightness() {
  if (bufferRead(3)) {
    byte strip = serialBuffer[0];
    byte brightness = serialBuffer[1];
    setBrightness(strip, brightness);
    if (serialBuffer[2]) {
      show(strip);
    }
  }
}

/*
 * Set the color on a single LED on an LED strip from an op stored in the buffer.
 */
void opSetLed() {
  if (bufferRead(7)) {
    byte strip = serialBuffer[0];
    unsigned int pos = ((unsigned int) serialBuffer[1] << 8) | (unsigned int) serialBuffer[2];
    leds[strips[strip].firstLED + pos].r = serialBuffer[3];
    leds[strips[strip].firstLED + pos].g = serialBuffer[4];
    leds[strips[strip].firstLED + pos].b = serialBuffer[5];
    if (serialBuffer[6]) {
      show(strip);
    }
  }
}

/*
 * Request an LED strip update based on an op stored in the buffer.
 */
void opShow() {
  if (bufferRead(1)) {
    byte strip = serialBuffer[0];
    show(strip);
  }
}

/*
 * Run an LED animation test from an op stored in the buffer.
 */
void opTest() {
  if (bufferRead(2)) {
    byte strip = serialBuffer[0];
    byte test = serialBuffer[1];
    switch (test) {
      case 1:
        testRainbow(strip, 128, 255);
        break;
      case 2:
        testRedAlert(strip);
        break;
      default:
        break;
    }
  }
}

/*
 * Test animations.
 */

/*
 * Run test animation to fill rotating hues across entire LED strip.
 *
 * strip: Which LED strip to run the animation on (FastLED index).
 * brightness: Brightness level from 0 (off) to 255 (max).
 * saturation: Saturation level of the HSV colors used.
 */
void testRainbow(byte strip, byte brightness, byte saturation) {
  strips[strip].brightness = brightness;
  for (int j = 0; j < 255; j++) {
    for (int i = strips[strip].firstLED; i <= strips[strip].lastLED; i++) {
      leds[i] = CHSV(i - (j * 2), saturation, brightness);
    }
    showOrSkip(strip);
    delay(33);
  }
}

/*
 * Run test animation to fill entire LED strip with red, and fade between min and max brightness.
 *
 * strip: Which LED strip to run the animation on (FastLED index).
 */
void testRedAlert(byte strip) {
  for (int i = strips[strip].firstLED; i <= strips[strip].lastLED; i++) {
    leds[i] = CRGB(255, 0, 0); /* The higher the value 4 the less fade there is and vice versa */
  }
  setBrightness(strip, 0);
  showOrSkip(strip);
  for (int i = 0; i <= 255; i++) {
    setBrightness(strip, i);
    showOrSkip(strip);
    delay(16);
  }
  for (int i = 255; i >= 0; i--) {
    setBrightness(strip, i);
    showOrSkip(strip);
    delay(16);
  }
}

/*
 * Arduino core functions.
 */

/*
 * Run one time initialization operations on startup.
 *
 * Called automatically by Arduino runtime.
 */
void setup() {
  gpio_set_function(PRIMARY_SERIAL_TX_PIN, GPIO_FUNC_UART);
  gpio_set_function(PRIMARY_SERIAL_RX_PIN, GPIO_FUNC_UART);
  PRIMARY_SERIAL.begin(BAUD);
  PRIMARY_SERIAL.setTimeout(100);
  // addLeds(PRIMARY_LED_STRIP_PIN, 100, 2500); // Uncomment to perform basic animation test
}

/*
 * Primary operation loop run repeatedly while system is powered on.
 *
 * Called automatically by Arduino runtime after setup().
 */
void loop() {
  // testRainbow(PRIMARY_LED_STRIP_PIN, 128, 255); // Uncomment to perform basic animation test.
  listen();
  for (int i = 0; i < ledStrips; i++) {
    if (strips[i].pendingShow) {
      showOrSkip(i);
    }
  }
}
