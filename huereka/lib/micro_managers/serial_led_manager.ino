/*
 * Receiver for optimized byte operations from external driver via serial in order to maximize LED strip efficiency.
 *
 * Uses native low level libraries such as FastLED in order to provide smooth animations. Although refresh rate
 * limiters are provided in a similar manner to FastLED, additional safeguards in the driver code are recommended
 * to ensure best results.
 */

#include <FastLED.h>

#define MAX_LEDS 1024
#define MAX_STRIPS 16
#define LED_TYPE WS2811
#define BAUD 115200
#define BUFFER_SIZE 64

bool op_started = false;
byte serial_buffer[BUFFER_SIZE];

CRGB leds[MAX_LEDS]; // Shared LED array across strips to enforce strict memory usage.
int led_total = 0;
int led_strips = 0;

/*
 * Stateful information about an LED strip
 *
 * first_led: Index of the first LED in the shared LED memory space.
 * last_led: Index of the last LED in the shared LED memory space.
 * brightness: Brightness level from 0 (off) to 255 (max).
 * refresh: Refresh rate in microseconds between allowed show() operations.
 * last_show: Last time show() was called in microseconds to determine next allowed refresh.
 * pending_show: Whether an outstanding show() request is waiting to run.
 */
typedef struct led_strip {
  int first_led;
  int last_led;
  uint8_t brightness;
  uint32_t refresh_rate;
  uint32_t last_show;
  bool pending_show;
} led_strip_t;

struct led_strip strips[MAX_STRIPS];

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
int buffer_read(int count) {
  int waited = 0;
  while (waited < 100) {
    if (Serial.available() < count) {
      delay(1);
      waited += 1;
      continue;
    }
    Serial.readBytes(serial_buffer, count);
    return count;
  }
  return 0;
}

/*
 * FastLED helpers (LED Strip aliases for standard global calls with same name).
 */

/*
 * Setup an LED controller and states on a specific GPIO pin.
 *
 * led_pin: GPIO pin where the LED data line is connected
 * led_count: Number of LEDs on the strip to reserve from the LED array.
 */
void addLeds(uint8_t led_pin, int led_count) {
  strips[led_strips].brightness = 255;
  strips[led_strips].first_led = led_total;
  strips[led_strips].last_led = led_total + led_count;
  for (int i = strips[led_strips].first_led; i < strips[led_strips].last_led; i++) {
    leds[i] = CRGB::Black;
  }
  // Add pins here only as needed. Each pin takes ~1500 bytes.
  switch (led_pin) {
    case 5:
      FastLED.addLeds<LED_TYPE, 5>(leds, strips[led_strips].first_led, strips[led_strips].last_led);
      setMaxRefreshRate(led_strips, FastLED[led_strips].getMaxRefreshRate(), true);
      strips[led_strips].last_show = 0;
      strips[led_strips].pending_show = false;
      break;
    default:
      break;
  }
  show(led_strips);
  led_total += led_count;
  led_strips++;
}

/*
 * Set the brightness on an LED strip.
 *
 * strip: Which LED strip to adjust the brightness on (FastLED index).
 * brightness: Brightness level from 0 (off) to 255 (max).
 */
void setBrightness(uint8_t strip, uint8_t brightness) {
  strips[strip].brightness = brightness;
}

/*
 * Set the max refresh rate on an LED strip.
 *
 * strip: Which LED strip to adjust the refresh on (FastLED index).
 * refresh: Refresh rate in khz (e.g. 400 or 800).
 * constrain: Whether to enforce the value can only be set higher.
 */
void setMaxRefreshRate(uint8_t strip, uint16_t refresh, bool constrain) {
  if(constrain) {
    if(refresh > 0) {
      strips[strip].refresh_rate = ((1000000 / refresh) > strips[strip].refresh_rate) ? (1000000 / refresh) : strips[strip].refresh_rate;
    }
  } else if(refresh > 0) {
    strips[strip].refresh_rate = 1000000 / refresh;
  } else {
    strips[strip].refresh_rate = 0;
  }
}

/*
 * Schedule an update to display all pending LED changes within max refresh rate.
 *
 * strip: Which LED strip to schedule the update on (FastLED index).
 */
void show(uint8_t strip) {
  strips[strip].pending_show = true;
}

/*
 * Display all pending updates on an LED strip if within safe refresh rate.
 *
 * strip: Which LED strip to apply the update to (FastLED index).
 */
void showOrSkip(uint8_t strip) {
  if ((micros() - strips[strip].last_show) < strips[strip].refresh_rate) {
    return;
  }
  strips[strip].last_show = micros();
  strips[strip].pending_show = false;

  CLEDController *ctlr = &FastLED[strip];
  uint8_t d = ctlr->getDither();
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
  if (!op_started && Serial.available() >= 1) {
    uint8_t magic = Serial.read();
    if (magic != 127) {
      return;
    }
    op_started = true;
  }

  if (op_started && Serial.available() >= 2) {
    op_started = false;
    uint8_t op = Serial.read();
    switch (op) {
      // Setup/initialization related ops.
      case 1:
        op_init_strip();
        break;

      // Runtime ops.
      case 32:
        op_set_brightness();
        break;
      case 33:
        op_fill_leds();
        break;
      case 34:
        op_set_led();
        break;
      case 35:
        op_show();
        break;
      case 77:
        op_test();
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
void op_init_strip() {
  if (buffer_read(4)) {
    uint8_t led_type = serial_buffer[0];
    uint8_t led_pin = serial_buffer[1];
    uint8_t led_count = serial_buffer[2];
    uint8_t led_anim = serial_buffer[3];
    addLeds(led_pin, led_count);
    int stripIndex = led_strips - 1;
    switch (led_anim) {
      case 1:
        test_rainbow(stripIndex, 128, 255);
        break;
      case 2:
        test_red_alert(stripIndex);
        break;
      default:
        break;
    }
  }
}

/*
 * Fill every LED on an LED strip with the same value from an op stored in the buffer.
 */
void op_fill_leds() {
  if (buffer_read(5)) {
    uint8_t strip = serial_buffer[0];
    for (int i = strips[strip].first_led; i < strips[strip].last_led; i++) {
      leds[i].r = serial_buffer[1];
      leds[i].g = serial_buffer[2];
      leds[i].b = serial_buffer[3];
    }
    if (serial_buffer[4]) {
      show(strip);
    }
  }
}

/*
 * Set the brightness on an LED strip from an op stored in the buffer.
 */
void op_set_brightness() {
  if (buffer_read(3)) {
    uint8_t strip = serial_buffer[0];
    uint8_t brightness = serial_buffer[1];
    setBrightness(strip, brightness);
    if (serial_buffer[2]) {
      show(strip);
    }
  }
}

/*
 * Set the color on a single LED on an LED strip from an op stored in the buffer.
 */
void op_set_led() {
  if (buffer_read(6)) {
    uint8_t strip = serial_buffer[0];
    uint8_t pos = serial_buffer[1];
    leds[pos].r = serial_buffer[2];
    leds[pos].g = serial_buffer[3];
    leds[pos].b = serial_buffer[4];
    if (serial_buffer[5]) {
      show(strip);
    }
  }
}

/*
 * Request an LED strip update based on an op stored in the buffer.
 */
void op_show() {
  if (buffer_read(1)) {
    uint8_t strip = serial_buffer[0];
    show(strip);
  }
}

/*
 * Run an LED animation test from an op stored in the buffer.
 */
void op_test() {
  if (buffer_read(2)) {
    uint8_t strip = serial_buffer[0];
    uint8_t test = serial_buffer[1];
    switch (test) {
      case 1:
        test_rainbow(strip, 128, 255);
        break;
      case 2:
        test_red_alert(strip);
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
void test_rainbow(uint8_t strip, uint8_t brightness, uint8_t saturation) {
  strips[strip].brightness = brightness;
  for (int j = 0; j < 255; j++) {
    for (int i = strips[strip].first_led; i < strips[strip].last_led; i++) {
      leds[i] = CHSV(i - (j * 2), saturation, brightness);
    }
    show(strip);
    delay(33);
  }
}

/*
 * Run test animation to fill entire LED strip with red, and fade between min and max brightness.
 *
 * strip: Which LED strip to run the animation on (FastLED index).
 */
void test_red_alert(uint8_t strip) {
  for (int i = strips[strip].first_led; i < strips[strip].last_led; i++) {
    leds[i] = CRGB(255, 0, 0); /* The higher the value 4 the less fade there is and vice versa */
  }
  setBrightness(strip, 0);
  show(strip);
  for (int i = 0; i <= 255; i++) {
    setBrightness(strip, i);
    show(strip);
    delay(16);
  }
  for (int i = 255; i >= 0; i--) {
    setBrightness(strip, i);
    show(strip);
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
  Serial.begin(BAUD);
}

/*
 * Primary operation loop run repeatedly while system is powered on.
 *
 * Called automatically by Arduino runtime after setup().
 */
void loop() {
  listen();
  for (int i = 0; i < led_strips; i++) {
    if (strips[i].pending_show) {
      showOrSkip(i);
    }
  }
}
