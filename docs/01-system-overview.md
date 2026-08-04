# Chapter 1 — System Overview

> **TL;DR** The SO-101 is a 6-DOF serial-link arm whose *only* motor-side electronics is
> a chain of six Feetech STS3215 bus servos on one shared TTL UART wire, driven through a
> Waveshare Bus Servo Adapter from a host PC over USB. Power and signal share the same
> 3-wire bus. There are no servo drives, no CAN, no separate motor controllers, and no
> embedded robot controller on the arm — the *host* is the controller.

## 1.1 What is it

The SO-101 follower arm (The Robot Studio × LeRobot) vends torque through six
single-board "smart" servos. Each STS3215 is a complete servo system in one body:

13-bit class magnetic encoder + a motor + a gear train + a control board + a
temperature/voltage/current sense chain. All six share a **single half-duplex TTL
serial line** (the "bus") plus power and ground. One host UART bridges to that bus;
everything else is packet exchange.

Why multiple servos can share one wire: each servo has a unique **ID**. A frame starts
with `FF FF <ID>`; only the matching ID answers. Power (2-wire) is common to all.

## 1.2 Electronic subsystems

| # | Subsystem | Hardware | Role | Chapter |
|---|---|---|---|---|
| S1 | Host + software | Ubuntu PC, LeRobot `so101_follower` driver | Talks UART protocol, closes the feel/teleop loop | ch06 |
| S2 | USB → UART bridge | Waveshare Bus Servo Adapter (A) (CH340-class) | Turns USB-C into a TTL bus transceiver, exposes servo bus + power inlet | ch02, ch04 |
| S3 | Servo bus (signal) | single D wire, half-duplex 8N1 @1 Mbps | Packet transport to/from all six servos | ch05 |
| S4 | Actuators | 6× STS3215 (magnetic encoder, PID, protections) | Position/velocity servo on each joint | ch02 |
| S5 | Power inlet + distribution | DC5521 jack / screw terminal → adapter → bus V/G | Feeds 4–7.4 V to every servo (unregulated pass-through) | ch03 |
| S6 | Sensory/peripheral | 12-bit encoder in each servo; voltage/current/temp sense; (cameras out of electronics scope) | Feedback to host | ch02 |

## 1.3 Hardware block diagram

```
                      ┌──────────────────────────────────────────────┐
                      │                  HOST (PC)                    │
                      │   Ubuntu 24.04 · Python 3.12 · LeRobot        │
                      │   SO101Follower(port=...)                     │
                      └──────────────────────┬───────────────────────┘
                                             │ USB Type-C (data)
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │   Waveshare Bus Servo Adapter (A)           │
                      │   [jumpers: B=B channel/USB]                 │
                      │   ┌────────────┐   ┌────────────┐            │
                      │   │ USB-serial │──►│ bus xcvr   │            │
                      │   │ (CH340)    │   │ 1.2Mbp     │            │
                      │   └─────▲──────┘   └─────┬──────┘            │
                      │         │                │  D               │
                      │   ┌─────┴──────┐   ┌─────┴──────┐            │
                      │   │ DC5521 jack│   │ 3-pin servo│            │
                      │   │ screw term │   │ interface  │            │
                      │   └─────┬──────┘   └─────┬──────┘            │
                      └─────────┼───────────────┼────────────────────┘
                                │ V (servo sply) │  V, D, G  (one motor)
                                ▼               ▼
                      ┌──────────────────────────────────────────────┐
                      │  STS3215 ID1 ── D/V/G ── STS3215 ID2 ── ... │
                      │  (shoulder_pan)  daisy-chain  (shoulder_lift)│
                      │             ... ── STS3215 ID6 (gripper)     │
                      └──────────────────────────────────────────────┘
```

[Also as Mermaid: `diagrams/system.mmd`]

## 1.4 Signal flow — PC to motor and back

One position command, host software architecture view:

```
                USB                 UART bus                 inside STS3215
[LeRobot]  → [adapter: USB→TTL] →  FF FF 01 09 03 2A 00 08 00 00 E8 03 D5
  "Shoulder_Pan: pos 2048"        (write 6 bytes @0x2A ID1) →  decode frame, checksum
                                                                test, PID computes,
                                                                PWM→H-bridge→motor→
                                                                encoder reads back
        ←  FF FF 01 02 00 FC  ←  status/OK  ←  firmware
```

The return path for *telemetry* (position/load/voltage) uses READ (0x02) or
SYNC-READ (0x92) rounds; see `docs/05-communication.md` §5 for the byte-level trace.

## 1.5 Power flow

```
Bench PSU (Vset ≤ 7.4 V, I-limit 2 A) 
      │ DC leads → adapter DC5521 or screw terminal
      ▼
WaveShare adapter (no regulation) ──► bus V/G wires
                                      ▼  (3-wire pigtails, V & G pass through)
STS3215 #1 (motor driver, reg, sense)
   V/G pass-through ► STS3215 #2 ► ... ► STS3215 #6
```

Nothing is down-converted. Every servo sees Vbus directly; its internal 3.3 V is made
on-board. Max Vbus = 7.4 V (this variant). See ch03 for current budget and regen/ESD
notes.

## 1.6 Communication flow — command freshness

Because every frame is serialized on one wire, the practical cycle is:

| Operation | Approx. wire time @1 Mbps (8N1) | Note |
|---|---|---|
| SINGLE-POS WRITE to one motor | ~ 140 µs (13 bytes) | fastest; low-latency single-joint moves |
| SYNC-WRITE to 6 motors | ~ 300 µs (28 bytes + address+len) | all joints in one frame |
| SYNC-READ all 6 × 6 bytes | ~ 1 ms + 6 replies | what LeRobot's loop does each tick |

[Values: `[INFERRED]` — derived from frame sizes at 1 Mbps, see ch05 §7.]

## 1.7 What is NOT in this system

- No CAN bus, no CAN-FD (that's your *other* DAMIAO rig), no SocketCAN.
- No embedded MCU on the arm (no ESP32/STM32 running control) —
  [unless] a future build adds one; the stock build is purely host-driven.
- No fuses/regulation on the adapter ([VERIFIED] Waveshare FAQ: no onboard regulation).
- No endstop switches or torque/encoder wires beyond the D signal.

Keep that cleared mental model: **host is the controller, the bus is one wire, power
is raw pass-through.**