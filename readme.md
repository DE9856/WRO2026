# WRO 2026 Future Engineers — Autonomous Self-Driving Car

![WRO](https://img.shields.io/badge/WRO-2026-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.9+-yellow?style=for-the-badge)
![OpenCV](https://img.shields.io/badge/OpenCV-Vision-green?style=for-the-badge)
![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-4B-red?style=for-the-badge)
![Arduino](https://img.shields.io/badge/Arduino-UNO-success?style=for-the-badge)

Autonomous vehicle system developed for the **WRO 2026 Future Engineers – Self-Driving Cars** category.

This project combines **Raspberry Pi 4B**, **Arduino Uno**, **OpenCV computer vision**, **world-model based planning**, **PID steering control**, and **Ackermann steering** to build a fully autonomous self-driving car capable of completing both WRO challenge formats.

---

## Team Information

| Role | Name |
|------|------|
| **Team** | Sky Flyers (#1090) |
| **Team Leader** | Deepesh Kumar Kotta |
| **Member** | Bade Hari Preetham |
| **Member** | Abhishek K |
| **Coach** | Saurav Kumar Topo |

---

## Project Goal

The objective of this project is to develop a **fully autonomous WRO Future Engineers vehicle** capable of:

- Completing **3 autonomous laps** in the **Open Challenge**.
- Detecting and obeying **red and green traffic-sign pillars** in the **Obstacle Challenge**.
- Performing **parallel parking** after completing the required laps.
- Operating **without any human intervention** after the official start button is pressed.

The vehicle is designed according to the **WRO 2026 Future Engineers regulations**, including the use of a **single drive motor**, **Ackermann steering**, and **no caster or omni wheels**.

---

## Current Development Status

> ⚠️ **Important Development Notice**

The car is **not completely working yet**. The software architecture, vision pipeline, planner, and Arduino firmware have already been implemented and tested in **simulation and dry-run mode**, but the final competition vehicle is still under active development.

We are currently in the process of **3D printing a new custom chassis** specifically designed for the WRO 2026 Future Engineers competition. The earlier prototype chassis was used mainly for validating the software stack, camera processing, serial communication, sensor integration, and basic motion control.

### What Is Already Implemented

- ✅ OpenCV vision pipeline
- ✅ Bird's-eye perspective transformation
- ✅ HSV colour segmentation
- ✅ Red and green pillar detection
- ✅ Corridor and wall-edge detection
- ✅ World-model and section tracking
- ✅ Lap counting logic
- ✅ Planner state machine
- ✅ PID steering controller
- ✅ Speed scheduling system
- ✅ Parallel parking controller
- ✅ Arduino firmware for servo, stepper motor, ultrasonic sensors, and IMU
- ✅ Telemetry logging and debugging tools
- ✅ Dry-run mode for testing without hardware

### Work Currently In Progress

- 🔄 Final **3D-printed competition chassis fabrication**
- 🔄 Mounting electronics onto the new chassis
- 🔄 Camera position and angle adjustment
- 🔄 Real-track calibration of HSV colour ranges
- 🔄 Steering PID tuning on the physical robot
- 🔄 Speed and acceleration tuning for corners
- 🔄 Full 3-lap autonomous validation
- 🔄 Recording official WRO submission videos

Once the new chassis is completed, the remaining effort will be **primarily running the existing code on the real robot and performing final fine-tuning and calibration**. The core software system is already in place; the current phase focuses mainly on **mechanical integration, tuning, and reliability testing rather than writing major new functionality**.

We intentionally document the project in this honest manner so that the repository accurately reflects the **real engineering state of the vehicle** rather than claiming that the robot is already fully competition-ready.

---

## Hardware Architecture

### Main Controllers

- **Raspberry Pi 4 Model B (8 GB)** — computer vision and high-level planning
- **Arduino Uno R3** — real-time motor, servo, ultrasonic, and IMU control

### Actuation

- **STH-39D219 NEMA14 stepper motor**
- **A4988 / DRV8825 stepper driver**
- **MG996R steering servo**
- **Ackermann steering linkage**

### Sensors

- **Logitech C270 USB webcam**
- **3× HC-SR04 ultrasonic sensors**
- **MPU-6050 IMU**
- **IR line sensor** for backup lap detection

### Power System

- **7.4 V Li-Ion / LiPo battery**
- **5 V buck converter** for Raspberry Pi and Arduino
- **6 V buck converter** for the steering servo

---

## Software Architecture

### Vision Pipeline

The OpenCV-based vision system performs:

- ROI cropping
- Perspective warp (bird's-eye view)
- HSV colour thresholding
- Morphological filtering
- Pillar contour detection
- Distance estimation using camera geometry
- Corridor-centering error extraction
- Parking-marker detection

### World Model

The world model keeps track of:

- Current track section
- Lap number
- Expected obstacle positions
- Obstacle memory between frames
- Parking phase activation

### Planner State Machine

```text
WAIT
  ↓
OPEN_DRIVE / OBS_DRIVE
  ↓
PARK_SEEK
  ↓
PARK_EXEC
  ↓
DONE
```

### Control Layer

- PID steering correction
- Speed scheduling for straights, corners, and parking
- Serial communication protocol between Pi and Arduino
- Automatic watchdog stop if communication is lost

---

## Repository Structure

```text
WRO2026/
├── main.py
├── firmware/
│   └── vehicle_controller.ino
├── camera/
├── control/
├── world_model/
├── planner/
├── tests/
├── docs/
│   ├── index.html
│   └── camera_processing.html
├── cad/
├── media/
└── ENGINEERING_JOURNAL.md
```

---

## Installation

### Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/WRO2026.git
cd WRO2026
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Running the Project

### Obstacle Challenge

```bash
python3 main.py --port /dev/ttyACM0
```

### Open Challenge

```bash
python3 main.py --port /dev/ttyACM0 --challenge OPEN
```

### Dry-Run Mode (No Hardware Required)

```bash
python3 main.py --dry-run --headless --frames 200
```

This executes the **entire software pipeline** using synthetic frames and a mock serial backend, allowing development and debugging even without the physical robot connected.

---

## Last-Minute Tuning & Pre-Competition Checks

After the new 3D-printed chassis is assembled, the following **final tuning and verification steps** will be performed before the competition. These are critical because they depend on the **actual physical robot, camera mounting position, battery voltage, wheel alignment, and competition lighting conditions**.

### Camera Calibration

- Verify camera height and tilt angle
- Recalculate perspective-warp corner points
- Measure the real horizontal field of view
- Confirm that lane boundaries remain visible through the entire cornering range

### HSV Colour Tuning

- Adjust **red pillar** thresholds
- Adjust **green pillar** thresholds
- Adjust **magenta parking-marker** thresholds
- Verify robustness under bright and dim lighting
- Save the final calibrated values to `config/hsv_ranges.json`

### Steering System Checks

- Center the servo mechanically
- Verify equal left and right steering angles
- Check for linkage backlash or binding
- Tune PID values (`KP`, `KI`, `KD`) to eliminate oscillation and under-steer
- Confirm that the vehicle returns smoothly to center after a turn

### Drive System Tuning

- Verify stepper motor direction
- Adjust maximum step frequency for stable acceleration
- Tune cruise speed for straight sections
- Reduce corner-entry speed to prevent wall contact
- Check belt tension and pulley alignment

### Ultrasonic Sensor Verification

- Confirm front sensor stopping distance
- Validate left/right sensor readings against actual wall distances
- Check for cross-talk between sensors during round-robin pinging
- Verify that parking-stop logic triggers before contacting the wall

### IMU Calibration

- Zero the gyro bias at startup
- Verify yaw-heading stability over a 3-minute run
- Tune parking-heading correction gain
- Confirm that the car remains parallel to the wall while reversing into the parking area

### Chassis Reliability Checks

- Tighten all wheel and pulley fasteners
- Verify battery mounting security
- Check cable routing to prevent interference with steering movement
- Confirm adequate cooling and airflow for the Raspberry Pi and motor driver
- Ensure that the total dimensions remain within **300 × 200 × 300 mm**

### Full Autonomous Validation Checklist

Before competition submission, we will perform the following sequence:

- [ ] Power-on self-check
- [ ] Camera stream verification
- [ ] Serial communication verification
- [ ] Start-button test
- [ ] Single-lap Open Challenge test
- [ ] Three-lap Open Challenge test
- [ ] Single-lap Obstacle Challenge test
- [ ] Three-lap Obstacle Challenge test
- [ ] Parallel parking validation
- [ ] Telemetry log review after each run

These checks are expected to be the **final engineering phase** after the new chassis is completed. At that stage, the project should require **primarily tuning, calibration, and reliability testing rather than major software rewrites**.

---

## Engineering Transparency

This repository intentionally separates:

- **Implemented software components**
- **Mechanical components still under fabrication**
- **Calibration tasks requiring the real competition field**

As of this commit:

- The **software architecture is substantially complete**.
- The **new custom 3D-printed chassis is still being fabricated**.
- Real-track calibration and tuning are still pending.
- The robot should currently be considered a **working software prototype integrated with a partially completed physical platform**, not a fully validated competition vehicle.

---

## WRO Compliance

The final competition design is intended to comply with the following WRO 2026 Future Engineers requirements:

| Requirement | Status |
|---|---|
| Single drive motor | ✅ |
| Mechanically linked rear axle | ✅ |
| Ackermann steering | ✅ |
| No caster or omni wheels | ✅ |
| Autonomous operation | ✅ |
| Start-button-only interaction | ✅ |
| No wireless communication during the round | ✅ |

---

## Documentation

### Build Guide

Open in a browser:

```text
docs/index.html
```

### Engineering Journal

The detailed design rationale, trade-offs, testing history, and future improvements are documented in:

```text
ENGINEERING_JOURNAL.md
```

---

## Future Improvements

After chassis completion and successful competition testing, the following enhancements are planned:

- Sensor-fusion based corridor centering
- Adaptive PID parameter tuning
- Wheel-encoder odometry
- Improved parking accuracy using IMU feedback
- Dynamic obstacle trajectory prediction
- More modular ROS2-style architecture for future research

---

## Acknowledgements

We would like to thank:

- **World Robot Olympiad Association**
- **WRO 2026 Future Engineers**
- The **OpenCV community**
- The **Raspberry Pi Foundation**
- The **Arduino Project**

for the tools, documentation, and open-source ecosystem that made this project possible.

---

## Final Note

This repository represents our **ongoing WRO 2026 Future Engineers development effort**. The most important point is that **the software side of the project is already largely implemented**, while the **new custom 3D-printed chassis is currently being fabricated**. Once the chassis is completed, the remaining work will focus mainly on **running the existing code on the physical robot, performing the final calibration and fine-tuning steps listed above, and validating reliable autonomous performance on the official competition track**.

By documenting both the completed work and the remaining tuning tasks, we aim to present an **accurate and transparent engineering record** of the project's current development stage.
