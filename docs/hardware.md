# WRO 2026 Hardware Reference

**Team:** Sky Flyers #1090  
**Category:** WRO Future Engineers – Self-Driving Cars

This document explains **every hardware component used in our autonomous vehicle and the engineering reason it was selected**.

---

## System Overview

The vehicle uses a **dual-controller architecture**:

- **Raspberry Pi 4B** for vision processing, world modelling, and autonomous planning.
- **Arduino UNO R3** for deterministic real-time control (servo PWM, stepper pulses, ultrasonic timing, and watchdog safety logic).

This separation prevents camera-processing delays from affecting steering or motor control.

---

# 1. Computing Layer

## U1 — Raspberry Pi 4 Model B (8 GB)

**Role:** Vision pipeline, state machine, and motion planner

### Why we chose it

The autonomy stack uses Python and OpenCV for:

- HSV colour segmentation
- Contour and lane tracking
- Obstacle and parking-marker detection
- World-model memory
- Planner state transitions

The **8 GB version** was selected to provide enough headroom for concurrent vision processing, telemetry logging, and future lightweight ML experiments.

### Specifications

| Item | Value |
|------|------|
| CPU | Quad-core Cortex-A72 @ 1.8 GHz |
| RAM | 8 GB LPDDR4 |
| Camera input | USB 2.0 UVC webcam |
| Link to Arduino | USB serial @ 115200 baud |

---

## U2 — Arduino UNO R3

**Role:** Real-time I/O co-processor

### Responsibilities

- MG996R servo PWM generation
- Stepper STEP/DIR pulse generation
- Round-robin ultrasonic triggering
- MPU-6050 I²C reading
- Start-button interrupt handling
- Communication-loss watchdog

### Safety Feature

If the Raspberry Pi stops sending commands for **more than 500 ms**, the Arduino automatically disables the drive motor.

---

## U3 — 0.96" I²C OLED Display (SSD1306)

**Role:** On-vehicle status display

Displays:

- Planner state
- Section/lap count
- Ultrasonic distances
- IMU heading
- Battery voltage

This display is **only for debugging and monitoring** and is not used for autonomous decision-making.

---

# 2. Drive & Actuation

## M2 + D1 — Shinano Kenshi STH-39D219 + DRV8825/A4988

**Role:** Sole drive motor for the rear axle

### Why we switched from a DC gearmotor

A stepper motor provides:

- Repeatable velocity control
- No battery-voltage-dependent RPM drift
- Easier distance calibration
- Better consistency across a full WRO run

### Specifications

| Item | Value |
|------|------|
| Motor type | NEMA14 stepper |
| Step angle | 1.8° (200 steps/rev) |
| Wiring | 6-wire, used in bipolar mode |
| Driver | DRV8825 or A4988 |
| Arduino pins | D4 DIR, D5 STEP, D10 EN |

### WRO Compliance

- Only **one drive motor** is installed.
- Both rear wheels are mechanically linked.
- No second motor channel exists in the wiring harness.

---

## 20T → 60T Timing-Belt Reduction

**Role:** 3:1 torque multiplication between the motor and rear axle

### Benefits

- Roughly **3× axle torque**
- Lower required step rate
- Guaranteed mechanical synchronization of both rear wheels

### Formula

```text
axle_rpm = (step_hz / 200) × 60 / 3
```

---

## M1 — MG996R Servo Motor

**Role:** Ackermann front steering

### Specifications

| Item | Value |
|------|------|
| Control | 50 Hz PWM |
| Voltage | 4.8–7.2 V |
| Steering range | ±25° |

The servo is powered from a **dedicated 6 V regulator** to prevent steering current spikes from affecting the Raspberry Pi.

---

# 3. Sensor Suite

## S1 — Logitech C270 USB Webcam

**Role:** Primary perception sensor

### Used for

- Lane tracking
- Wall detection
- Pillar detection
- Parking-marker detection
- Corner-line recognition

### Mounting

| Item | Value |
|------|------|
| Height | 15–20 cm |
| Tilt | ~15° downward |
| Resolution | 640×480 @ 30 FPS |

---

## S2–S4 — HC-SR04 Ultrasonic Sensors

**Role:** Wall proximity and parking collision protection

### Placement

| Sensor | Purpose |
|------|------|
| Front | Collision guard |
| Left | Lateral wall monitoring |
| Right | Lateral wall monitoring |

### Wiring

| Sensor | Trig | Echo |
|------|------|------|
| Front | D12 | D13 |
| Left | D6 | D7 |
| Right | D8 | D11 |

The sensors are polled in a **round-robin schedule** so that one blocking echo measurement cannot stall the control loop.

---

## S5 — MPU-6050 IMU

**Role:** Yaw-heading estimation during parking

### Specifications

| Item | Value |
|------|------|
| Interface | I²C (A4 SDA / A5 SCL) |
| Gyro range | ±250 °/s |
| Usage | Gyro-Z integration for yaw estimation |

This sensor helps keep the vehicle **parallel to the parking wall**, which vision alone cannot guarantee.

---

## S6 — Analog IR Line Sensor

**Role:** Backup lap/corner line detection

| Item | Value |
|------|------|
| Output | Analog |
| Arduino pin | A0 |
| Purpose | Backup line-transition detection |

This sensor is **advisory only** and does not override the camera-based line detector.

---

# 4. Power System

The vehicle uses **two battery systems and three power rails** to prevent brownouts and motor-driver resets.

---

## BT1 — 7.4 V (2S) LiPo

**Feeds:** REG1 and REG2

| Item | Value |
|------|------|
| Voltage | 7.4 V nominal |
| Capacity | ≥ 2000 mAh recommended |

Used for the **logic and steering systems only**.

---

## BT2 — 14.8 V (4S) Li-ion Pack

**Feeds:** Stepper-driver VMOT directly

### Why it exists

The DRV8825 requires **at least 8.2 V** on VMOT. A 2S LiPo can sag below this threshold under load, so a separate **4S pack** is used for reliable stepper operation.

| Item | Value |
|------|------|
| Nominal voltage | 14.8 V |
| Full charge | ~16.8 V |
| Typical cutoff | ~12 V |

⚠️ **The two 2S sub-packs must be charged separately through their own balance connectors.**

---

## REG1 — 5 V Step-Down Converter

**Powers:** Raspberry Pi + Arduino

| Item | Value |
|------|------|
| Output | 5 V |
| Minimum current | 3 A |

---

## REG2 — 6 V Step-Down Converter

**Powers:** MG996R servo only

| Item | Value |
|------|------|
| Output | 6 V |
| Minimum current | 2 A |

Isolating the servo prevents steering transients from causing Raspberry Pi brownouts.

---

## SW1 + SW2 — User Interaction Controls

| Control | Function |
|------|------|
| SW1 | Main power switch |
| SW2 | Start-round push button |

No additional physical mode-selection switches are present, ensuring compliance with WRO interaction rules.

---

# 5. Structural System

## Custom 3D-Printed Chassis

### Why we designed our own chassis

A custom chassis allows precise control of:

- Camera height and angle
- Sensor placement symmetry
- Wheelbase geometry
- Belt-drive alignment
- WRO size and weight compliance

### Current Status

| Item | Status |
|------|------|
| CAD design | Complete |
| Physical print | In fabrication |
| Final weight verification | Pending |

---

# 6. Full Bill of Materials

| Ref | Component | Qty | Role | Est. Cost (₹) |
|------|------|------|------|------|
| U1 | Raspberry Pi 4B (8 GB) | 1 | Vision + planner | ~8,500 |
| U2 | Arduino UNO R3 | 1 | Real-time I/O | ~600 |
| U3 | SSD1306 OLED display | 1 | Status display | ~150 |
| M2 | STH-39D219 stepper motor | 1 | Sole drive motor | ~600 |
| — | 20T→60T timing belt + pulleys | 1 set | 3:1 reduction | ~250 |
| M1 | MG996R servo | 1 | Steering actuator | ~350 |
| D1 | DRV8825 / A4988 driver | 1 | Stepper control | ~180 |
| S1 | Logitech C270 webcam | 1 | Primary vision | ~1,200 |
| S2–S4 | HC-SR04 ultrasonic sensors | 3 | Proximity sensing | ~240 |
| S5 | MPU-6050 IMU | 1 | Yaw estimation | ~120 |
| S6 | Analog IR line sensor | 1 | Backup line detection | ~80 |
| BT1 | 7.4 V 2S LiPo | 1 | Logic/servo source | ~900 |
| BT2 | 14.8 V 4S Li-ion pack | 1 | Stepper VMOT source | ~1,200 |
| REG1 | 5 V buck converter | 1 | Logic regulator | ~120 |
| REG2 | 6 V buck converter | 1 | Servo regulator | ~120 |
| SW1 | Rocker power switch | 1 | Main power | ~40 |
| SW2 | Momentary push button | 1 | Start trigger | ~20 |
| W1–W4 | Rubber wheels | 4 | Mobility system | ~300 |
| — | Custom 3D-printed chassis | 1 | Structural frame | ~600 |

**Estimated total:** **₹15,500–16,000**

---

# 7. WRO Compliance Summary

| Requirement | Implementation |
|------|------|
| Single drive motor | One STH-39D219 stepper only |
| Mechanically linked axle | Belt-driven solid rear axle |
| No caster/omni wheels | Four standard rubber wheels |
| Limited user interaction | One power switch + one start button |
| Size envelope | Custom chassis designed for 300×200×300 mm limit |

---

# 8. Design Philosophy

Every component was included **only if it solved a clearly identified problem**:

- **Stepper motor:** solved speed-repeatability drift.
- **USB webcam:** removed dependence on Raspberry Pi–specific camera APIs.
- **IMU:** solved the parking-heading problem that vision alone could not.
- **Separate servo regulator:** eliminated steering-induced Raspberry Pi brownouts.
- **Arduino watchdog:** ensured that a vision-process failure could not leave the vehicle driving uncontrolled.

Where hardware decisions changed during development, the revision history has been preserved intentionally so that the repository reflects the **actual engineering process**, not just the final configuration.

---

## Repository Links

```text
docs/index.html                 → Build guide
ENGINEERING_JOURNAL.md          → Design reasoning and testing
cad/                            → CAD files
firmware/vehicle_controller.ino → Arduino firmware
camera/                         → Vision pipeline
control/parking_maneuver.py     → Parking controller
```

---

**Version:** WRO 2026 Hardware Reference  
**Last updated:** August 2026  
**Team:** Sky Flyers #1090
