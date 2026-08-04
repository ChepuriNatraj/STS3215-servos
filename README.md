# SO-101 Robotic Arm — Electronics & Hardware Engineering Handbook

A graduate-level, reverse-engineering-oriented handbook for the **SO-101** open-source
robot arm, focused entirely on **electronics, embedded systems, wiring, power, and
communications**. This is a hardware bring-up and debugging reference — not an assembly
or usability guide.

> The SO-101 is the 6-DOF follower arm designed by **The Robot Studio** in collaboration
> with **Hugging Face / LeRobot**, built around six **Feetech STS3215** serial-bus smart
> servos daisy-chained on a single half-duplex UART bus. Everything structural is
> 3D-printed and Apache-2.0 licensed; the CAD is mirrored in
> [TheRobotStudio/SO-ARM100](https://github.com/TheRobotStudio/SO-ARM100).

## Project purpose

The goal is total understanding of the SO-101's electronic architecture so that an
engineer can:

- identify every PCB, connector, cable, and voltage rail;
- power and bring the hardware up safely from a bench power supply;
- detect, interrogate, and control **one motor**, then scale to all six;
- debug communication, power, configuration, and fault-state failures;
- and reverse-engineer the bus with logic analyzers / oscilloscopes if needed.

Every claim in this handbook carries an **evidence tag** so confirmed facts are never
confused with inferences (see [Evidence tags](#evidence-tags)).

## Hardware overview

| Item | Detail | Evidence |
|---|---|---|
| Robot | SO-101 follower arm, 6 DOF + parallel-jaw gripper | [LeRobot docs](https://huggingface.co/docs/lerobot/en/so101) |
| Actuators | 6× Feetech STS3215 (7.4 V, 19 kg·cm variant, model ST-3215-C001, gear 1/345) | URDF `~/Desktop/s101/ros2_ws/src/so101_description/urdf/so101_core.urdf`, Feetech datasheet `datasheets/STS3215_datasheet.pdf` |
| Joint layout | motor 1 = shoulder_pan (base), 2 = shoulder_lift, 3 = elbow_flex, 4 = wrist_flex, 5 = wrist_roll, 6 = gripper | LeRobot docs §"Set the motors ids", URDF |
| Motor bus | TTL half-duplex serial, 8N1, **1 Mbps** factory default, IDs 1–6 | STS3215 datasheet §7-2/7-4 |
| Controller | **Waveshare Bus Servo Adapter (A)** — USB-C ↔ servo bus bridge + power inlet | User-supplied hardware, LeRobot docs |
| Coupling to host | USB Type-C from adapter to host PC (CH340-class USB-serial) | Waveshare FAQ, LeRobot docs |
| Servo power | Bench PSU → DC5521 jack or screw terminal on adapter (no onboard regulation — output = input) | Waveshare Bus Servo Adapter wiki |
| Host | Ubuntu 24.04.4 LTS desktop, Python 3.12.3 | Local `uname`/`python3` (2026-08-04) |
| Software | LeRobot `so101_follower` motor driver (primary); ROS 2 integration as a later layer | LeRobot repo, `docs/06-programming.md` |

## Required equipment

**Robotics & electrical (to follow this handbook):**

- SO-101 with Waveshare Bus Servo Adapter (or plain USB-TTL serial adapter)
- Bench power supply, adjustable 0–10 V, current-limiting, ≥ 5 A capability
  (an OWON SPE-series or equivalent) — see `docs/03-power-system.md`
- Digital multimeter (volt / ohm / continuity / current)
- USB-C cable (data, not charge-only)
- **Optional but recommended:** USB oscilloscope / logic analyzer for Chapter 9

**Tools & consumables:** small philips/hex drivers, calipers, jumper leads,
spare 3-pin servo cables.

## Software prerequisites

| Dependency | Purpose | Evidence / source |
|---|---|---|
| Python ≥ 3.10 (3.12 OK) | LeRobot host code | local `python3 --version` |
| LeRobot (`pip install -e ".[feetech]"`) | `so101_follower` motor driver + CLI tools | LeRobot installation guide |
| `pyserial` (installed with LeRobot extra) | UART access to the adapter | Waveshare wiki: demo uses only `pyserial` |
| `pip`, `venv` | isolated environment | standard |
| (Later) ROS 2 Jazzy + `ros2_control` | ROS 2 driver path | `docs/06-programming.md` §ROS 2 |

**Not needed:** CAN adapters, SocketCAN, `candump`. The SO-101 motor bus is **UART**,
not CAN. (Your `dm-usb2fdcan` / DAMIAO DM-J4310 work is a *different* robot's toolchain and is out of scope here.)

## Safety precautions

> Read `docs/03-power-system.md` in full before applying power.

1. **Voltage ceiling is the #1 kill cause.** The 7.4 V STS3215 variant has an input
   range of **4 V – 7.4 V max** (datasheet §5-7). The Waveshare adapter delivers input
   voltage straight to the servos (no regulation). **Never** exceed 7.4 V on a
   7.4 V servo, even though the adapter's jack is labeled 9–12.6 V.
2. **Set the PSU current limit first** (~2 A for single-motor experiments, ≤ 5 A for
   the full arm) with the output off. Stall current is 2.5 A; a stalled chain can draw
   far more.
3. **Keep hands clear.** With torque enabled, a joint will drive to its commanded
   position; the arm can pinch and the gripper can clamp. Never hold a driven joint.
4. **Enable torque only when you intend to move.** A motor that is holding position
   loads the bus and heats up in ~100 % duty.
5. **Watch temperature.** The servo reports internal °C; over 70 °C torque cuts out.
6. **Remove power before unplugging/replugging** 3-pin servo cables.
7. **5 V from a USB port is for logic, not servos.** A burst of 6 stalled servos

   can exceed 10 A briefly — far beyond a host port's budget.
8. ESD: handle the adapter/PCBs at a grounded mat; servos are PA+GF plastic but the
   internal electronics are exposed on the cable ends.

## Development environment

The handbook targets the environment actually in place (verified 2026-08-04):

```
Linux botforgelabs2-MS-7D99 7.0.0-28-generic  x86_64
Ubuntu 24.04.4 LTS
Python 3.12.3 (/usr/bin/python3)
```

LeRobot is **not yet installed** on the host — see `docs/06-programming.md` for the
venv setup, and `docs/07-single-motor-bringup.md` for the first live session.

## Repository structure

```
STS3215 servos/
├── README.md                       ← this file
├── docs/
│   ├── 00-hardware-inventory.md    ← verified inventory + evidence register
│   ├── 01-system-overview.md       ← architecture, block + signal/power flow diagrams
│   ├── 02-electronics-architecture.md
│   ├── 03-power-system.md          ← rails, bench PSU rules, safe power sequencing
│   ├── 04-wiring-connectors.md     ← every connector, pinout, cable, common mistakes
│   ├── 05-communication.md         ← UART bus, protocol frames, memory table, command trace
│   ├── 06-programming.md           ← LeRobot driver + APIs + minimal examples
│   ├── 07-single-motor-bringup.md  ← the laboratory bring-up sequence
│   ├── 08-debugging.md             ← troubleshooting handbook
│   ├── 09-reverse-engineering.md   ← probing, capturing, IC identification methodology
│   └── 10-reference-library.md     ← datasheets, manuals, repos, lectures
├── datasheets/                     ← official PDFs (offline copies cited by the docs)
├── diagrams/                       ← mermaid + ASCII diagrams (.mmd / .txt)
├── assets/                         ← photographs (add yours; naming convention in ch04)
├── scripts/                        ← safe bring-up scripts (Python 3, pyserial)
└── logs/                           ← bench-log templates; local logs are gitignored
```

## Recommended reading order

1. `README.md` (this file) — orientation, safety
2. `docs/00-hardware-inventory.md` — confirm what is on *your* bench
3. `docs/01-system-overview.md` — whole-system mental model
4. `docs/05-communication.md` — the protocol level you will live at
5. `docs/03-power-system.md` — rules you must respect before powering
6. `docs/04-wiring-connectors.md` — exactly what connects where
7. `docs/07-single-motor-bringup.md` — the hands-on sequence (do this first on hardware)
8. `docs/06-programming.md` — the software layer + minimal examples
9. `docs/02-electronics-architecture.md` — deep dive per subsystem
10. `docs/08-debugging.md` — when things break
11. `docs/09-reverse-engineering.md` — going beyond the datasheet
12. `docs/10-reference-library.md` — sources, forever

For a strictly minimal hands-on loop: **03 → 04 → 07 → 05 → 06**.
For pure reading: **01 → 05 → 02 → 03 → 04**.

## Quick start

> Full procedure with expected outputs: `docs/07-single-motor-bringup.md`. The arm is
> not currently connected to the host (no serial device present on 2026-08-04), so the
> commands below are given with `[BENCH-CHECK]` expected outputs until the first live run.

```bash
# 1. Feed only ONE motor on the bench
#    PSU: 7.4 V, current limit 2 A, output OFF
#    PSU → DC5521/Screw terminals on the Waveshare adapter
#    adapter jumper caps on B (USB); servo on 3-pin D/V/G port
#    USB-C from adapter to host

# 2. Serial device (CH340-class → ttyUSB*; ADS board → ttyACM*)
ls /dev/ttyUSB* /dev/ttyACM*          # [BENCH-CHECK] pick your node
sudo chmod 666 /dev/ttyUSB0           # add yourself to dialout instead, if you prefer

pip install -e ".[feetech]"           # from the LeRobot source checkout
```

```python
# scripts/ or a REPL — drive servo ID 1 to 2048 at slow speed
from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
motor = SO101Follower(SO101FollowerConfig(port="/dev/ttyUSB0", id="bench"))
motor.connect()
motor.write("Shoulder_Pan", {"position": 2048})   # [BENCH-CHECK] moves to 2048
motor.disconnect()
```

Expected result: the single servo drives slowly to neutral (2048) and holds, then
unloads on `disconnect()` (torque-off is default). If it does not — `docs/08-debugging.md`.

## Common beginner mistakes

1. **Overvoltage on a 7.4 V servo** (datasheet max 7.4 V). The adapter label says
   9–12.6 V — that label assumes the *12 V* STS3215 variant. Feed your variant's voltage.
2. **Daisy-chaining more servos before testing one** — a wiring fault then faults all six.
3. **USB charge-only cable** — host sees no device, or a device that disconnects under load.
4. **Wrong jumper position** — jumper caps must be on **B (USB)**; on A, the board
   listens on the UART header and ignores the USB bridge.
5. **Forgetting `chmod` / dialout** — `serial.serialutil.SerialException: could not open port`.
6. **Enabling torque with the arm against a stop or hand in the way.**
7. **Expecting CAN tools to work** — this is UART; there is no `can0` for the SO-101.
8. **Trusting PID defaults before movement safety** — tune `position_*_coefficient` and
   set `max_relative_target` before moving a loaded chain.
9. **Reading two-byte registers with wrong byte order** — STS3215 is **low byte first**
   (L, H), unlike the older SCS high-byte-first ordering.
10. **Out-of-range reads** (address 0x3C vs 0x40/0x41 for load vs current) — the STS3215
    memory table differs from the generic SCS/SMS manual, verify addresses in ch05.

## Evidence tags

All chapters use the same tags your DAMIAO bench project uses, extended with one:

| Tag | Meaning |
|---|---|
| `[VERIFIED]` | Stated in an official document or directly observed (source given) |
| `[INFERRED]` | Derived from an official source / community source, source named |
| `[BENCH-CHECK]` | Must be confirmed on your hardware; procedure given |
| `[UNKNOWN]` | No reliable info; deliberately not guessed |

## License & posture

Documentation mirrors the hardware's open posture (Apache-2.0 upstream). The datasheets
are © Shenzhen Feetech; the adapter wiki/schematic are © Waveshare — they are kept
offline as *citations*, not redistributed content. No license is asserted over this
handbook yet; ask before external publication.