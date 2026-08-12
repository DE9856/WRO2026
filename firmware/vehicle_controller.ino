/*
 * vehicle_controller.ino
 * WRO 2026 Future Engineers -- Arduino UNO real-time co-processor.
 *
 * Counterpart to control/serial_link.py on the Raspberry Pi side. The Pi
 * does all vision/planning and sends drive commands down; this sketch's
 * only job is to turn those into servo/motor PWM and to report the
 * physical-world sensor data the Pi can't get any other way.
 *
 * DRIVE MOTOR:
 *     1x Shinano Kenshi STH-39D219 (NEMA14, 6-wire, 1.8 deg/step -- 200
 *     full steps/rev), wired bipolar (center-tap wires left disconnected)
 *     through an A4988/DRV8825-family STEP/DIR driver. Replaces the
 *     earlier single-channel L298N + brushed DC gearmotor -- see
 *     CHANGELOG.md. Speed is commanded as a step-pulse frequency instead
 *     of a PWM duty cycle; see writeDriveMotor()/serviceStepperPulse()
 *     below. Direction/"single motor channel" WRO compliance argument is
 *     unchanged: exactly one motor, one driver, driving the rear axle.
 *
 *     DRIVER CURRENT LIMIT (set on the physical board, not in this
 *     sketch -- there is no firmware control over Vref): motor is rated
 *     3.5V / 0.7A per phase. Driver board in hand is a Pololu-footprint
 *     DRV8825 clone (marked "DRV8825 92TC5 A588"), assumed 0.1 ohm
 *     sense resistors per the common convention for this board family
 *     (not yet directly measured). Vref = I_limit * 5 * R_sense =
 *     0.7 * 5 * 0.1 = 0.35V, set via the on-board trim pot (black probe
 *     GND, red probe trim-pot wiper). See ENGINEERING_JOURNAL.md ->
 *     "Stepper driver current-limit calibration" for the full derivation
 *     and the risk noted if the sense-resistor assumption is wrong.
 *
 *     MOTOR SUPPLY (VMOT): fed from a separate 4S Li-ion pack (two 2S
 *     sub-packs in series, ~14.8V nominal), NOT the same 7.4V 2S LiPo
 *     that feeds the 5V/6V logic+servo regulators -- the DRV8825's 8.2V
 *     floor left too little margin against LiPo sag on a single 2S
 *     supply. The two supplies' grounds MUST still be tied together
 *     (STEP/DIR/ENABLE are ground-referenced logic signals). See
 *     ENGINEERING_JOURNAL.md -> "Drive-motor supply battery".
 *
 * SENSOR LOADOUT (matches the actual build, not just the BOM sheet):
 *     3x HC-SR04 ultrasonic -- front, left, right
 *     1x MPU-6050 IMU (I2C)  -- yaw-rate integration for heading
 *     1x IR reflectance sensor (analog) -- backup lap-line detection
 *     1x camera (Pi side only, not read by this sketch)
 *
 * ---------------------------------------------------------------------
 * DOWNLINK (Pi -> Arduino), matches control/serial_link.py exactly:
 *
 *     "S<steer_deg>,<speed_pwm>,<flag>\n"
 *
 *     steer_deg : signed float, degrees, positive = steer RIGHT
 *     speed_pwm : signed float, 0-100 magnitude, negative sign = reverse
 *     flag      : single ASCII char -- 'D' driving / 'P' parking /
 *                 'S' stopped-waiting. Currently informational only
 *                 (no LED/buzzer is in the BOM); stored in case you
 *                 wire one up later.
 *
 * UPLINK (Arduino -> Pi), one event per line, matches what
 * main.py's read_events() loop understands:
 *
 *     "BTN"            -- start button was just pressed (edge, not level)
 *     "LINE"           -- backup lap-line sensor tripped (edge, debounced)
 *     "DIST_F=<cm>"    -- front HC-SR04 range
 *     "DIST_L=<cm>"    -- left HC-SR04 range
 *     "DIST_R=<cm>"    -- right HC-SR04 range
 *     "IMU=<deg>"      -- integrated yaw heading, degrees, relative to
 *                         wherever the sketch booted (0.0 at power-on).
 *                         Positive = clockwise (yaw right), matching the
 *                         steer_deg sign convention above.
 *
 *     Older firmware revisions sent a single "DIST=<cm>" (front only).
 *     main.py accepts both DIST_F= and the legacy DIST= as the forward
 *     reading, so a Pi running slightly-older code still works, but new
 *     code should key off DIST_F=/DIST_L=/DIST_R=.
 *
 * NOTE ON MODE=OPEN / MODE=OBSTACLE:
 *     serial_link.py's docstring and main.py both know how to handle a
 *     "MODE=OPEN" / "MODE=OBSTACLE" uplink event, but this firmware does
 *     NOT send it. Reason: the BOM only lists two switches -- the main
 *     power rocker and the single momentary start button (WRO 9.10/9.11,
 *     and the rulebook's own recurring-violation note: "one button to
 *     turn the robot on and another button to start the program.
 *     Additional interactions are not permitted"). Wiring a third
 *     physical selector switch to drive MODE= would (a) require hardware
 *     that isn't in the BOM, and (b) risks being read as "entering data
 *     through physical adjustments" under rule 9.9. Set the challenge
 *     type from the Pi side instead, e.g. `python3 main.py --challenge
 *     OPEN`. If you later want a physical mode switch, treat it as a
 *     *manufacturing-time* jumper read once at Arduino boot (before
 *     waiting for BTN) rather than a runtime toggle, and re-read WRO 9.9
 *     before trusting that interpretation.
 *
 * NOTE ON HC-SR04 USAGE:
 *     main.py's uplink loop parses DIST_F=/DIST_L=/DIST_R= and feeds the
 *     front reading into control/proximity.py's ParkingCollisionGuard
 *     (used to detect the vehicle touching/near-touching a parking
 *     marker during PARK_EXEC, WRO 9.24.7). Left/right readings are
 *     logged and available on the telemetry HUD; they are NOT yet fused
 *     into camera/corridor.py's lane-centering fallback -- that fusion
 *     needs on-track calibration against the real corridor widths (see
 *     the project punch-list item on camera/corridor.py's fallback
 *     half-width constant) which cannot be done from a laptop, only on
 *     the physical field.
 *
 * NOTE ON MPU-6050 (IMU= uplink):
 *     Read directly over I2C using bare register access (no external
 *     library dependency -- just Wire.h, which ships with the Arduino
 *     IDE). Gyro Z is integrated over time into a running yaw estimate,
 *     zeroed against a short at-rest calibration window at boot. This
 *     is a simple integrator, not a full complementary/Kalman filter --
 *     it WILL drift over a multi-minute run, which is fine for a
 *     3-minute WRO round but is called out here so nobody mistakes it
 *     for an absolute-heading sensor. control/parking_maneuver.py uses
 *     the heading delta since PARK_EXEC started to keep the vehicle
 *     parallel to the wall while reversing into the parking lot
 *     (WRO Section1.8.2's parallel-parking requirement).
 *
 * PIN MAP (matches docs/index.html Section 4, "Wiring Reference" --
 * keep both in sync if you change this):
 *     D2   Start button              (INPUT_PULLUP, momentary, debounced)
 *     D3   (spare -- not used by this sketch)
 *     D4   Stepper DIR                (A4988/DRV8825 direction input)
 *     D5   Stepper STEP               (A4988/DRV8825 step-pulse input)
 *     D6   HC-SR04 (left) Trig
 *     D7   HC-SR04 (left) Echo
 *     D8   HC-SR04 (right) Trig
 *     D9   Servo signal              (Ackermann steering, MG996R or similar)
 *     D10  Stepper ENABLE             (A4988/DRV8825 nENBL, active LOW)
 *     D11  HC-SR04 (right) Echo
 *     D12  HC-SR04 (front) Trig
 *     D13  HC-SR04 (front) Echo
 *     A0   IR line sensor (analog)   (backup lap-line detection)
 *     A4   MPU-6050 SDA (I2C)
 *     A5   MPU-6050 SCL (I2C)
 *     MS1 / MS2 / MS3 on the driver MUST be explicitly wired to GND (not
 *     left floating) for full-step mode, no microstepping. A4988/DRV8825
 *     breakout boards typically leave these pins unconnected with no
 *     onboard pull resistor -- floating them is not the same as pulling
 *     them low, and a floating digital input can pick up noise and put
 *     the driver into an unintended microstep mode mid-run. This sketch
 *     does not drive these pins itself. Only one stepper axis (one driver, one motor) is ever
 *     wired or coded -- WRO 11.5/11.13 forbid a second independently-
 *     driven motor channel, and there is no second driver/motor on the
 *     harness to accidentally command.
 * ---------------------------------------------------------------------
 */

#include <Servo.h>
#include <Wire.h>
#include <string.h>   // strchr()
#include <stdlib.h>   // atof()
#include <math.h>     // fabs()

// ---------------------------------------------------------------------
// Pin assignments
// ---------------------------------------------------------------------
const uint8_t PIN_START_BTN     = 2;   // INPUT_PULLUP, LOW when pressed
const uint8_t PIN_STEPPER_DIR   = 4;   // A4988/DRV8825 DIR
const uint8_t PIN_STEPPER_STEP  = 5;   // A4988/DRV8825 STEP (pulse)
const uint8_t PIN_US_LEFT_TRIG  = 6;
const uint8_t PIN_US_LEFT_ECHO  = 7;
const uint8_t PIN_US_RIGHT_TRIG = 8;
const uint8_t PIN_SERVO         = 9;
const uint8_t PIN_STEPPER_ENABLE = 10; // A4988/DRV8825 nENBL, active LOW
const uint8_t PIN_US_RIGHT_ECHO = 11;
const uint8_t PIN_US_FRONT_TRIG = 12;
const uint8_t PIN_US_FRONT_ECHO = 13;
const uint8_t PIN_LINE_SENSOR   = A0;  // analog IR
// A4 (SDA) / A5 (SCL) used implicitly by Wire.h for the MPU-6050.

// ---------------------------------------------------------------------
// Tunables
// ---------------------------------------------------------------------
const long    BAUD_RATE               = 115200;   // matches main.py --baud default

const uint8_t SERVO_CENTER_DEG        = 90;        // mechanical center of the linkage
const uint8_t SERVO_STEER_LIMIT_DEG   = 35;         // firmware-side hard safety clamp
                                                     // (Pi/PID already clamps to ~30 deg;
                                                     // this is a second, independent floor
                                                     // so a bad packet can't over-steer
                                                     // the linkage even if the Pi glitches)
const bool    SERVO_REVERSE           = false;      // flip to true if "steer right" on the
                                                     // wire actually turns the wheels left
                                                     // on your linkage -- no code logic
                                                     // change needed, just this flag

// --- Drive stepper (STH-39D219 via A4988/DRV8825, STEP/DIR, full step) ---
// The Pi still sends speed as a 0-100 "PWM-style" magnitude (unchanged
// wire protocol -- see control/serial_link.py); this sketch maps that
// magnitude onto a step-pulse frequency instead of an H-bridge duty
// cycle. Linear map: 0 -> STEP_FREQ_MIN_HZ (just above stall), 100 ->
// STEP_FREQ_MAX_HZ. RECALIBRATE both bounds on the actual chassis --
// STEP_FREQ_MAX_HZ is limited by the motor's torque/speed curve at your
// supply voltage and wheel load, not by the Arduino.
const bool     STEPPER_DIR_FORWARD_LEVEL = HIGH;    // flip if "forward" on the wire
                                                     // drives the wheels backward --
                                                     // no logic change needed, just this
const bool     STEPPER_ENABLE_ACTIVE_LOW = true;    // true for typical A4988/DRV8825 nENBL
const float    STEP_FREQ_MIN_HZ       = 60.0f;      // pulses/sec at speed_pwm magnitude ~1
const float    STEP_FREQ_MAX_HZ       = 900.0f;     // pulses/sec at speed_pwm magnitude 100
                                                     // Drivetrain: 20T (motor) -> 60T (axle)
                                                     // timing belt, 3:1 reduction (6mm belt,
                                                     // 202mm length -- see ENGINEERING_JOURNAL.md
                                                     // "Why the 3:1 belt reduction"). Convert to
                                                     // axle RPM for tuning: axle_rpm =
                                                     // (step_hz / 200) * 60 / 3, e.g. 900 pps ->
                                                     // 4.5 rev/s motor -> 90 RPM at the axle.
                                                     // Purely informational here -- this sketch
                                                     // only ever commands motor-shaft step rate,
                                                     // never axle RPM directly.
const uint16_t STEP_PULSE_HIGH_US_MIN = 3;          // documentation only, see note below --
                                                     // DRV8825 needs STEP HIGH >=1.9us, A4988
                                                     // >=1us; not used as a delay anywhere in
                                                     // this sketch because serviceStepperPulse()
                                                     // toggles a 50%-duty square wave whose
                                                     // shortest HIGH dwell (at STEP_FREQ_MAX_HZ)
                                                     // is still >500us -- two orders of magnitude
                                                     // above this minimum, so no explicit
                                                     // delayMicroseconds() is needed to meet it.
                                                     // Kept here so the margin is visible if
                                                     // STEP_FREQ_MAX_HZ is ever raised a lot.
const float    MOTOR_DEG_PER_STEP     = 1.8f;       // datasheet value for STH-39D219
                                                     // (200 full steps/rev) -- informational,
                                                     // not used in the frequency math below

const uint16_t BUTTON_DEBOUNCE_MS     = 40;
const uint16_t LINE_REFRACTORY_MS     = 300;        // min gap between two LINE events, so
                                                      // one physical crossing can't spam
                                                      // multiple lines while the sensor
                                                      // dithers across the threshold
const int      LINE_THRESHOLD         = 500;         // 0-1023 raw ADC -- RECALIBRATE against
                                                       // your actual IR sensor + track surface
                                                       // before trusting this (see punch-list
                                                       // item on lighting-dependent thresholds,
                                                       // same caveat as the HSV ranges)

const uint16_t HCSR04_INTERVAL_MS     = 60;           // one sensor is pinged per tick, round-
                                                       // robin (front/left/right), so all
                                                       // three refresh roughly every 180 ms --
                                                       // keeps any single loop() call short
                                                       // instead of blocking on 3 pulseIn()s
                                                       // back to back.
const uint32_t HCSR04_TIMEOUT_US      = 15000UL;      // ~2.5 m round-trip cap -- plenty for a
                                                       // 3 m-wide WRO field, keeps the blocking
                                                       // window on pulseIn() short

const uint16_t IMU_INTERVAL_MS        = 50;           // 20 Hz yaw report
const uint16_t IMU_CALIBRATION_SAMPLES = 200;         // at-rest gyro-Z bias samples at boot

const uint32_t COMMAND_TIMEOUT_MS     = 500;          // fail-safe: stop the drive motor if no
                                                       // valid S-command has arrived for this
                                                       // long (covers USB unplug / Pi crash --
                                                       // mirrors serial_link.py's own
                                                       // "never leave the vehicle silently
                                                       // uncommanded" philosophy)

// MPU-6050 register map (bare I2C access, no external library)
const uint8_t MPU_ADDR           = 0x68;
const uint8_t MPU_REG_PWR_MGMT_1 = 0x6B;
const uint8_t MPU_REG_GYRO_ZOUT_H = 0x47;
const float   MPU_GYRO_LSB_PER_DPS = 131.0f;  // datasheet value for the default +/-250 dps range

// ---------------------------------------------------------------------
// State
// ---------------------------------------------------------------------
Servo steeringServo;

char    rxBuf[48];
uint8_t rxLen = 0;

float   lastSteerDeg = 0.0f;
float   lastSpeedPwm = 0.0f;
char    lastFlag      = 'S';
uint32_t lastCommandMs = 0;
bool     everReceivedCommand = false;

bool     btnLastRaw   = HIGH;   // INPUT_PULLUP idle = HIGH
bool     btnStableState = HIGH;
uint32_t btnLastChangeMs = 0;

bool     lineLastState  = false;   // false = below threshold (no line)
uint32_t lineLastEventMs = 0;

uint32_t lastPingMs = 0;
uint8_t  pingSensorIndex = 0;       // 0 = front, 1 = left, 2 = right

// Stepper drive state -- see writeDriveMotor()/serviceStepperPulse().
// Non-blocking square-wave generator: toggle PIN_STEPPER_STEP every
// stepHalfPeriodUs microseconds. stepHalfPeriodUs == 0 means "not moving".
bool     stepperEnabled     = false;   // mirrors PIN_STEPPER_ENABLE level
uint32_t stepHalfPeriodUs   = 0;       // 0 = stopped
uint32_t lastStepEdgeUs     = 0;
bool     stepPinHigh        = false;

bool     mpuAvailable = false;
float    gyroZBiasDps = 0.0f;
float    yawDeg = 0.0f;
uint32_t lastImuMs = 0;
uint32_t lastImuReportMs = 0;

// ---------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------
void setup() {
  Serial.begin(BAUD_RATE);

  pinMode(PIN_START_BTN, INPUT_PULLUP);
  pinMode(PIN_STEPPER_DIR, OUTPUT);
  pinMode(PIN_STEPPER_STEP, OUTPUT);
  pinMode(PIN_STEPPER_ENABLE, OUTPUT);
  digitalWrite(PIN_STEPPER_STEP, LOW);
  digitalWrite(PIN_STEPPER_DIR, STEPPER_DIR_FORWARD_LEVEL);

  pinMode(PIN_US_FRONT_TRIG, OUTPUT);
  pinMode(PIN_US_FRONT_ECHO, INPUT);
  pinMode(PIN_US_LEFT_TRIG, OUTPUT);
  pinMode(PIN_US_LEFT_ECHO, INPUT);
  pinMode(PIN_US_RIGHT_TRIG, OUTPUT);
  pinMode(PIN_US_RIGHT_ECHO, INPUT);
  digitalWrite(PIN_US_FRONT_TRIG, LOW);
  digitalWrite(PIN_US_LEFT_TRIG, LOW);
  digitalWrite(PIN_US_RIGHT_TRIG, LOW);

  pinMode(PIN_LINE_SENSOR, INPUT);

  // Rule 9.6: the vehicle must sit still, switched-off-equivalent, until
  // the round actually starts. Boot into a fully stopped/centered state
  // and stay there until the Pi explicitly sends a nonzero command --
  // never move on our own initiative.
  stopMotor();
  steeringServo.attach(PIN_SERVO);
  writeSteeringDeg(0.0f);

  setupImu();

  lastCommandMs = millis();
}

// ---------------------------------------------------------------------
// Main loop
// ---------------------------------------------------------------------
void loop() {
  serviceSerialDownlink();
  serviceStartButton();
  serviceLineSensor();
  serviceUltrasonic();
  serviceImu();
  serviceCommandTimeout();
  serviceStepperPulse();
}

// =======================================================================
// DOWNLINK: read "S<steer>,<speed>,<flag>\n" from the Pi and drive
// the actuators. Non-blocking -- accumulates into rxBuf until '\n'.
// =======================================================================
void serviceSerialDownlink() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();

    if (c == '\n') {
      rxBuf[rxLen] = '\0';
      parseAndApplyCommand(rxBuf);
      rxLen = 0;
      continue;
    }

    if (c == '\r') {
      continue;  // tolerate CRLF, ignore bare CR
    }

    if (rxLen < sizeof(rxBuf) - 1) {
      rxBuf[rxLen++] = c;
    } else {
      // Line too long / garbage -- drop and resync on the next '\n'
      // rather than let a corrupted packet steer the wheel forever.
      rxLen = 0;
    }
  }
}

void parseAndApplyCommand(const char *line) {
  // Expect: S<steer_deg>,<speed_pwm>,<flag>
  if (line[0] != 'S') {
    return;  // not our packet type -- ignore silently
  }

  const char *p = line + 1;

  char *commaAfterSteer = strchr(p, ',');
  if (commaAfterSteer == NULL) return;

  char *commaAfterSpeed = strchr(commaAfterSteer + 1, ',');
  if (commaAfterSpeed == NULL) return;

  float steerDeg = atof(p);                       // up to first comma
  float speedPwm = atof(commaAfterSteer + 1);      // between the two commas
  char  flag     = *(commaAfterSpeed + 1);         // first char after 2nd comma

  if (flag == '\0') flag = 'S';

  lastSteerDeg = steerDeg;
  lastSpeedPwm = speedPwm;
  lastFlag     = flag;
  lastCommandMs = millis();
  everReceivedCommand = true;

  writeSteeringDeg(steerDeg);
  writeDriveMotor(speedPwm);
}

// =======================================================================
// ACTUATORS
// =======================================================================
void writeSteeringDeg(float steerDeg) {
  if (steerDeg > SERVO_STEER_LIMIT_DEG)  steerDeg = SERVO_STEER_LIMIT_DEG;
  if (steerDeg < -SERVO_STEER_LIMIT_DEG) steerDeg = -SERVO_STEER_LIMIT_DEG;

  if (SERVO_REVERSE) steerDeg = -steerDeg;

  int servoAngle = (int)(SERVO_CENTER_DEG + steerDeg);
  if (servoAngle < 0)   servoAngle = 0;
  if (servoAngle > 180) servoAngle = 180;

  steeringServo.write(servoAngle);
}

// speedPwm keeps the same 0-100-magnitude wire meaning as before (see
// control/serial_link.py); only the interpretation on this side changed,
// from H-bridge PWM duty to stepper step-pulse frequency.
void writeDriveMotor(float speedPwm) {
  float magnitude = fabs(speedPwm);
  if (magnitude > 100.0f) magnitude = 100.0f;

  if (magnitude < 1.0f) {
    stopMotor();
    return;
  }

  bool forward = (speedPwm >= 0.0f);
  digitalWrite(PIN_STEPPER_DIR, forward ? STEPPER_DIR_FORWARD_LEVEL
                                         : !STEPPER_DIR_FORWARD_LEVEL);

  setStepperEnabled(true);

  float freqHz = STEP_FREQ_MIN_HZ +
                 (magnitude / 100.0f) * (STEP_FREQ_MAX_HZ - STEP_FREQ_MIN_HZ);
  if (freqHz < 1.0f) freqHz = 1.0f;  // guard against divide-by-zero below

  // Full period = 1/freqHz seconds; we toggle the STEP pin twice per
  // period (once HIGH, once LOW), so each edge is half that apart.
  stepHalfPeriodUs = (uint32_t)((1000000.0f / freqHz) / 2.0f);
}

void stopMotor() {
  stepHalfPeriodUs = 0;
  stepPinHigh = false;
  digitalWrite(PIN_STEPPER_STEP, LOW);
  setStepperEnabled(false);  // de-energize coils between commands/at rest
}

void setStepperEnabled(bool enabled) {
  stepperEnabled = enabled;
  bool activeLevel = STEPPER_ENABLE_ACTIVE_LOW ? LOW : HIGH;
  bool idleLevel   = STEPPER_ENABLE_ACTIVE_LOW ? HIGH : LOW;
  digitalWrite(PIN_STEPPER_ENABLE, enabled ? activeLevel : idleLevel);
}

// =======================================================================
// ACTUATOR: non-blocking STEP pulse generator. Call every loop(). Toggles
// PIN_STEPPER_STEP on a fixed cadence (stepHalfPeriodUs) derived from the
// last writeDriveMotor() call, instead of blocking with delay()/
// delayMicroseconds() the way a naive Stepper.h sketch would -- that
// would stall serviceUltrasonic()/serviceImu()/the serial downlink for
// the whole step period, which is unacceptable at this loop rate.
// =======================================================================
void serviceStepperPulse() {
  if (stepHalfPeriodUs == 0) return;  // stopped -- nothing to toggle

  uint32_t nowUs = micros();
  if (nowUs - lastStepEdgeUs < stepHalfPeriodUs) return;

  lastStepEdgeUs = nowUs;
  stepPinHigh = !stepPinHigh;
  digitalWrite(PIN_STEPPER_STEP, stepPinHigh ? HIGH : LOW);
  // STEP_PULSE_HIGH_US_MIN is comfortably shorter than any speed we command
  // here (min half-period ~= 1/(2*STEP_FREQ_MAX_HZ) seconds), and
  // digitalWrite()'s own call overhead already exceeds the driver's
  // minimum pulse width, so no extra delay is needed on the HIGH edge.
}

// =======================================================================
// FAIL-SAFE: if the Pi goes quiet mid-round (USB unplugged, vision loop
// crashed, etc.) stop driving rather than coasting on the last command
// forever. We do NOT re-center the servo -- an unexpected steering
// snap while coasting to a stop is its own hazard -- we just cut power
// to the drive motor.
// =======================================================================
void serviceCommandTimeout() {
  if (!everReceivedCommand) return;  // nothing to time out yet

  if (millis() - lastCommandMs > COMMAND_TIMEOUT_MS) {
    stopMotor();
  }
}

// =======================================================================
// UPLINK: start button, debounced edge-detect. Sends "BTN" exactly once
// per press, not once per loop() while held.
// =======================================================================
void serviceStartButton() {
  bool raw = digitalRead(PIN_START_BTN);  // LOW = pressed (INPUT_PULLUP)

  if (raw != btnLastRaw) {
    btnLastChangeMs = millis();
    btnLastRaw = raw;
  }

  if ((millis() - btnLastChangeMs) > BUTTON_DEBOUNCE_MS && raw != btnStableState) {
    btnStableState = raw;
    if (btnStableState == LOW) {  // falling edge = press
      Serial.print("BTN\n");
    }
  }
}

// =======================================================================
// UPLINK: backup lap-line sensor. Simple threshold crossing with a
// refractory period so one physical line crossing can't fire twice.
//
// LINE_THRESHOLD is a placeholder like the HSV ranges elsewhere in this
// project -- recalibrate against the real sensor + real track surface/
// lighting before trusting it (see hsv_tuner.py's on-site recalibration
// note; this needs the same treatment, just on the Arduino side).
// =======================================================================
void serviceLineSensor() {
  int raw = analogRead(PIN_LINE_SENSOR);
  bool onLine = (raw > LINE_THRESHOLD);

  if (onLine && !lineLastState) {
    uint32_t now = millis();
    if (now - lineLastEventMs > LINE_REFRACTORY_MS) {
      Serial.print("LINE\n");
      lineLastEventMs = now;
    }
  }

  lineLastState = onLine;
}

// =======================================================================
// UPLINK: 3x HC-SR04 (front/left/right), round-robin -- one sensor
// pinged per HCSR04_INTERVAL_MS tick so a single loop() call never
// blocks on more than one pulseIn(). Sends "DIST_F=<cm>" / "DIST_L=<cm>"
// / "DIST_R=<cm>"; sends nothing on a timed-out ping rather than a
// bogus 0 or -1 that could be misread as "very close".
// =======================================================================
float pingSensorCm(uint8_t trigPin, uint8_t echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  unsigned long durationUs = pulseIn(echoPin, HIGH, HCSR04_TIMEOUT_US);
  if (durationUs == 0) {
    return -1.0f;  // timed out / nothing in range
  }
  return (durationUs / 2.0f) / 29.1f;  // speed of sound ~343 m/s
}

void serviceUltrasonic() {
  uint32_t now = millis();
  if (now - lastPingMs < HCSR04_INTERVAL_MS) return;
  lastPingMs = now;

  float distanceCm;
  const char *label;

  switch (pingSensorIndex) {
    case 0:
      distanceCm = pingSensorCm(PIN_US_FRONT_TRIG, PIN_US_FRONT_ECHO);
      label = "DIST_F=";
      break;
    case 1:
      distanceCm = pingSensorCm(PIN_US_LEFT_TRIG, PIN_US_LEFT_ECHO);
      label = "DIST_L=";
      break;
    default:
      distanceCm = pingSensorCm(PIN_US_RIGHT_TRIG, PIN_US_RIGHT_ECHO);
      label = "DIST_R=";
      break;
  }
  pingSensorIndex = (pingSensorIndex + 1) % 3;

  if (distanceCm < 0.0f) {
    return;  // timed out this tick -- stay silent, don't send a bogus reading
  }

  Serial.print(label);
  Serial.print(distanceCm, 1);
  Serial.print('\n');
}

// =======================================================================
// UPLINK: MPU-6050 yaw heading, bare I2C register access (Wire.h only,
// no external MPU library dependency). Gyro-Z is integrated over time
// into yawDeg, zeroed against an at-rest bias measured during setup().
// This is a plain integrator (no accelerometer fusion), so it WILL
// drift slowly -- acceptable over one 3-minute WRO round, not meant for
// longer.
// =======================================================================
void setupImu() {
  Wire.begin();

  Wire.beginTransmission(MPU_ADDR);
  Wire.write(MPU_REG_PWR_MGMT_1);
  Wire.write(0x00);  // wake the MPU-6050 up out of sleep mode
  uint8_t result = Wire.endTransmission();

  mpuAvailable = (result == 0);
  if (!mpuAvailable) {
    // No MPU-6050 found on the bus (not wired yet, or a bad connection).
    // Degrade gracefully: no "IMU=" lines are ever sent, and
    // control/parking_maneuver.py already falls back to pixel-only
    // centering when heading_deg is never provided -- see its docstring.
    return;
  }

  delay(50);  // let the sensor settle after waking

  float sum = 0.0f;
  for (uint16_t i = 0; i < IMU_CALIBRATION_SAMPLES; i++) {
    sum += readGyroZDps();
    delay(3);
  }
  gyroZBiasDps = sum / (float)IMU_CALIBRATION_SAMPLES;

  yawDeg = 0.0f;
  lastImuMs = millis();
}

float readGyroZDps() {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(MPU_REG_GYRO_ZOUT_H);
  Wire.endTransmission(false);
  Wire.requestFrom((int)MPU_ADDR, 2, true);

  if (Wire.available() < 2) {
    return 0.0f;
  }

  int16_t raw = (Wire.read() << 8) | Wire.read();
  return raw / MPU_GYRO_LSB_PER_DPS;
}

void serviceImu() {
  if (!mpuAvailable) return;

  uint32_t now = millis();
  float dt = (now - lastImuMs) / 1000.0f;
  lastImuMs = now;

  float gyroZDps = readGyroZDps() - gyroZBiasDps;
  yawDeg += gyroZDps * dt;

  // Keep it wrapped to (-180, 180] purely for readability in logs/serial
  // monitor -- main.py's own heading-delta math re-wraps anyway, so this
  // isn't load-bearing, just tidy.
  while (yawDeg > 180.0f)  yawDeg -= 360.0f;
  while (yawDeg <= -180.0f) yawDeg += 360.0f;

  if (now - lastImuReportMs >= IMU_INTERVAL_MS) {
    lastImuReportMs = now;
    Serial.print("IMU=");
    Serial.print(yawDeg, 2);
    Serial.print('\n');
  }
}
