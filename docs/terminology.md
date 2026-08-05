# FOUNDATIONS — Terms to Re-Learn (Grounded in the STS3215 Project)

> Personal notes, written from scratch, anchored to the Feetech STS3215 (the
> servo at the heart of the SO-101 arm). Keep them terse. Skim, don't read.

---

## 1. Gear Ratio

### What it is

A gear ratio describes how many **input shaft turns** it takes to produce
**one output shaft turn** in a gear train. It is written either as:

- **N:1** — driver has N teeth / driven has 1 equivalent tooth → N driver revs per 1 driven rev.
- **1/N** — N driven revs per 1 driver rev (the convention used in the STS3215 datasheet).

### Physics in one paragraph

For an ideal (lossless) gear pair, **power is conserved** and the tradeoff is
between **torque and speed**:

```
ω_out = ω_in / N           (speed divides by the ratio)
τ_out = τ_in × N × η       (torque multiplies by the ratio × efficiency)
```

Where:

- `ω` = angular speed (rev/s or rad/s)
- `τ` = torque (N·m)
- `N` = ratio (driver:driven)
- `η` = efficiency (0.85–0.95 for a single spur stage, ~0.7 for a multi-stage planetary)

### Worked example — STS3215

Datasheet states **Gear ratio: 1/345** and **Kt (motor) = 8 kg·cm / A**.

Interpretation:

- The brushed DC motor spins internally.
- The 345:1 reduction (typically a multi-stage spur + planetary box) slows
  the output shaft **345×** and multiplies available torque by ~345 (minus losses).
- So if the raw motor produces 8 kg·cm per amp at high speed, the output
  shaft delivers ~345 × 8 = **2760 kg·cm per amp at the output (theoretical)**.
- Real datasheet stall torque is **19.5 kg·cm @ 7.4 V → 2.5 A stall** → ~19.5/2.5
  ≈ 7.8 kg·cm/A at the output. Vs theoretical 2760 kg·cm/A at the *motor* → divide
  by 345 → ~8 kg·cm/A at the output. The numbers line up → this is the ratio's
  purpose: convert a small fast motor into a slow strong actuator.

### Why it matters for servo selection

- **Higher ratio** → more torque, slower speed, often more backlash.
- **Lower ratio** → faster, weaker.
- STS3215 is mid-range: 345:1, 0.192 s/60° = 52 RPM no-load, 19.5 kg·cm stall.

### Mental checklist when you see "gear ratio X"

- Convert between X:1 and 1/X notation.
- Torque-out ≈ torque-in × ratio × efficiency.
- Speed-out ≈ speed-in / ratio.
- Backlash ≠ ratio. Backlash is the small angular slack when you reverse direction
  (STS3215: ≤ 0.5°). It comes from gear tooth clearance, not from the ratio.

---

## 2. TTL Half-Duplex Asynchronous Serial (UART)

Three concepts are bundled in the phrase — they are not the same thing.

### a. UART (what the controller silicon speaks)

A **Universal Asynchronous Receiver/Transmitter** is a piece of hardware inside
a microcontroller that converts a parallel byte into a serial bit stream (and back).
"Async" = no shared clock line; both sides agree in advance on **baud rate**.

A typical UART frame for one byte, the **8N1** the STS3215 uses:

```
idle HIGH ─┐                        ┌──── idle HIGH
           │  START(0)  D0..D7 (8)  STOP(1)
           └────────────┴───────────┘
```

- 1 **start** bit (always LOW) — synchronizes the receiver.
- 8 **data** bits, LSB first.
- **No parity** bit (the "N" in 8N1).
- 1 **stop** bit (always HIGH).
- Total: 10 bit-times per byte.

At 1 000 000 baud, one byte takes **10 µs** on the wire.

### b. TTL (what voltage "high" and "low" mean)

**TTL** = Transistor-Transistor Logic levels:

| Logic | TTL voltage |
|---|---|
| HIGH (1) | 2.0 V – 5.0 V (anything above 2 V reads as a 1) |
| LOW (0) | 0 V – 0.45 V (anything below 0.45 V reads as a 0) |

STS3215 signal pins: **High 2–5 V, Low 0–0.45 V** (datasheet §4).

This is **not** RS-232 (which swings ±3 to ±15 V) and **not** RS-485
(differential, ±1.5 to ±5 V across a twisted pair). TTL = chip-to-chip,
short cable, single-ended.

### c. Half-duplex (who is allowed to talk)

- **Full-duplex** = two separate wires, both directions at the same time.
- **Half-duplex** = **one wire shared**, only one device talks at a time.
- The other device(s) must be in receive mode while one is transmitting.

The STS3215 uses **one signal wire** for all communication. Every servo on the
daisy-chain listens while one device transmits. The controller side **must**
switch its UART TX pin between output (TX) and high-impedance (RX) so its own
TX does not collide with the servo's reply.

### How the controller switches direction (the practical bit)

Most microcontroller USARTs have separate TX and RX pins. A simple
bidirectional half-duplex link needs either:

- An external **transceiver** (e.g. SN74LS241, MAX485, or a dedicated half-duplex
  UART bridge) that the firmware controls with a DIR pin — this is what the
  Waveshare Bus Servo Adapter uses.
- Or a single-wire GPIO that you bit-bang, toggling input/output mode per byte.
  Half-duplex UART mode in some MCUs (STM32 `USART_SINGLE_WIRE_HALF_DUPLEX`)
  does this in hardware.

### Why "asynchronous" matters

Because there is no clock wire, both ends must:

- Agree on baud rate to within ~2–3 % over the duration of a frame.
- Resync on each start bit.
- Match voltage levels (TTL ↔ TTL, no level shifter needed for short cables).

If you set your host to 115 200 but the servo is at 1 000 000 (the STS3215
factory default), every byte is garbage.

### Summary table

| Term | Means | STS3215 value |
|---|---|---|
| UART | Async serial hardware block | inside the servo MCU |
| 8N1 | 8 data, no parity, 1 stop bit | yes |
| Baud | Bits per second on the wire | 38400 – 1 000 000 (default 1 M) |
| TTL | 0–0.45 V = LOW, 2–5 V = HIGH | yes |
| Half-duplex | One wire, one direction at a time | yes (Signal/TTL pin only) |

---

## 3. Encoders (and where the STS3215's "magnetic encoder" sits)

### What an encoder does

An encoder is a sensor that reports **rotary position** (and, by differencing,
speed and direction). Two broad families:

1. **Incremental** — outputs pulses as the shaft turns. Counts pulses to know how far, uses two channels (A, B) in quadrature to know direction. **No absolute position** at power-up; you must home to a known reference.
2. **Absolute** — outputs a unique code for every angle in 360°. Knows its angle **the instant it powers on** (no homing needed).

The STS3215 uses an **absolute magnetic encoder** with **4096 steps/rev** →
0.088° per step.

### The big comparison matrix

| Type | What it senses | Absolute? | Contact? | Typical resolution | Notes |
|---|---|---|---|---|---|
| **Potentiometer (analog)** | Resistance change vs angle | Yes (single turn) | Wipers touch | Infinite (analog), 10–12 bit in practice | Cheap. Wears out. Limited to < 360° unless multi-turn pot. |
| **Optical (slotted disc + photodiode)** | Light through slots | Usually incremental; can be absolute with Gray-code disc | None | 100 – 10 000 ppr | Sensitive to dust / oil. Common in hobby servos. |
| **Magnetic (Hall + magnet)** | B-field angle, usually via 1D/2D Hall IC | Often absolute | None | 8 – 14 bit typical | STS3215 uses this. Robust, no optics, no wear. |
| **Inductive / resolver** | Coupling between coils | Absolute | None | 14 – 16 bit+ | Used in harsh / high-temp environments (motors, aerospace). Expensive. |
| **Capacitive** | Capacitance change vs angle | Can be absolute | None | 14 – 20 bit | High resolution, emerging. Used in some robot joints. |
| **Linear encoder** | Optical/magnetic on a strip | Incremental | None | µm scale | For *linear* position, not rotary. |

### How a magnetic encoder actually works (the STS3215 case)

Picture a diametrically magnetized disc (a small cylinder magnet, N on one face
flat, S on the opposite face flat) mounted on the motor shaft, **above the PCB**.

A **Hall-effect IC** sits under the magnet. The IC contains one or more
**vertical Hall** elements that sense **B-field components in the plane of the IC**.
As the magnet rotates:

- The in-plane B-field components (Bx, By) trace a **sine and cosine** of the angle.
- The IC computes `atan2(By, Bx)` internally → a digital angle that repeats every 360°.
- A multi-pole magnet on the motor shaft, combined with the IC's internal
  interpolation, multiplies the per-revolution count → here 4096 counts per shaft rev.

Common magnetic encoder ICs you will see referenced: AS5600 (12-bit, I²C),
MA730, TLE5012B, AM4096. The STS3215's exact IC is not named in the public
datasheet, but the resolution and "magnetic" label match this family.

### How it differs from an optical encoder (the one most people picture)

| | Magnetic | Optical |
|---|---|---|
| Moving part | Magnet on shaft (no contacts) | Slotted / coded disc on shaft |
| Sensing element | Hall IC | Photodiode + LED |
| Fragile to dust/oil | No | Yes |
| Fragile to shock/vibration | Magnet can shift if adhesive fails | Disc can crack |
| Resolution per rev | 12 – 14 bit typical, can be 16+ bit | 13 – 21 bit common (driven by disc pattern) |
| Cost | Low–medium | Medium |
| Lifetime | "Unlimited" (datasheet: STS3215) | Limited by LED wear / disc contamination |

### How it differs from a potentiometer

A pot is a **variable resistor** with a wiper that slides on a carbon or
cermet track. Magnetic encoder:

- **No contact, no wear.**
- **True 360° plus multi-turn** (with gearing, the *servo* reports multiple
  turns; the raw IC usually does one).
- **Digital output** (often SPI, I²C, ABZ, or PWM) → noise-tolerant.
- **Cheap to read** — microcontroller just parses a register.

Pots are still used in cheap RC servos and as human-input devices (volume knobs,
joysticks). They are not used inside a smart servo like the STS3215 because
they wear out, drift, and limit resolution.

### Why "magnetic encoder" matters for the SO-101

- Holds position without an optical disc that can fog/contaminate in a workshop.
- Provides absolute angle on power-up → the servo boots and immediately knows
  where it is; no need to home every reboot.
- High enough resolution (0.088°) to drive a 1/345 geartrain without visible
  jitter on the output shaft.

---

## 4. The Bus (TTL) and the Serial Bus Smart Servo Protocol

### What a "bus" is

A **bus** is a shared communication line that **multiple devices** connect to and
take turns using. Three properties define a bus:

- **Physical** — what carries the bits (wire, fiber, RF).
- **Topological** — how devices hang off it (daisy-chain, star, multi-drop).
- **Protocol** — who talks when, how frames are structured, how errors are handled.

The STS3215 bus:

- **Physical:** 3 wires — VCC, GND, Signal/TTL.
- **Topological:** **multi-drop daisy-chain.** Each servo has a 3-pin JST
  output that you plug into the next servo's input. All servos tap the same
  Signal line simultaneously.
- **Protocol:** Feetech's "Serial Bus Smart Servo" protocol — a packet
  protocol layered on top of half-duplex UART, described below.

### Why one wire is enough (and why collisions are the price)

Because the bus is half-duplex, only one transmitter is allowed on the line at a
time. The controller and each servo take turns. If two devices ever overlap,
their bits XOR on the wire — every receiver sees garbage and the frame is lost.

This is exactly why the protocol has:

- **Unique IDs (0–253)** — so the controller can address one specific servo.
- **A broadcast ID (0xFE)** — for "all of you" commands that don't need replies.
- **Clear instruction/reply semantics** — defined by the packet layout.

### Packet format (the wire-level rules)

Every packet begins with **two `0xFF` bytes in a row** — that's how a receiver
recognizes the start of a frame.

```
Instruction (host → servo):
[0xFF][0xFF][ID][Length][Instruction][Param 1]...[Param N][Checksum]

Status / reply (servo → host):
[0xFF][0xFF][ID][Length][Error]    [Data...]          [Checksum]
```

Field notes:

- **ID** = 0x00–0xFD = unique servo. 0xFE = broadcast (no reply). 0xFF is the
  header byte and must not appear as an ID.
- **Length** = `N + 2` for an instruction (N = number of param bytes), so the
  receiver knows when the frame ends even before it sees the checksum.
- **Checksum** = `~(ID + Length + Instr + Param1 + ... + ParamN)`, low byte of
  the sum, then bitwise-NOT. Cheap, not cryptographic. Catches bus errors.
- **Two-byte values** are sent **little-endian** (low byte first, then high
  byte) — SCS-series convention. Different from SMS-series (RS-485) which is
  big-endian.

### The instruction set (what you can ask a servo to do)

| Code | Name | Job |
|---|---|---|
| `0x01` | **PING** | "Are you there?" returns ERROR byte. Used to discover / verify servos. |
| `0x02` | **READ DATA** | Read bytes from the control table (e.g. current position, temperature, load). |
| `0x03` | **WRITE DATA** | Write bytes immediately (e.g. set target position, change baud rate). |
| `0x04` | **REG WRITE** | Stage a write; it executes only on the next `0x05 ACTION`. |
| `0x05` | **ACTION** | Trigger all pending REG WRITEs across all servos at the same instant — synchronized multi-servo move. |
| `0x06` | **RESET** | Restore factory defaults. |
| `0x83` | **SYNC WRITE** | One broadcast frame writes the same block to many servos with **different** per-servo data. |

### The control table (what addresses mean)

A smart servo exposes its state as a small memory map: address → meaning.
A partial view of the STS3215 control table:

| Address | Size | Name | Meaning |
|---|---|---|---|
| `0x05` | 1 | ID | servo ID (0–253) |
| `0x06` | 1 | Baud | 0=1M, 1=500k, 2=250k, 3=128k, 4=115200, 5=76800, 6=57600, 7=38400 |
| `0x2A` | 6 | Target pos/time/speed | Three packed values to start a move |
| `0x38` | 2 | Current position | Read-only |
| `0x3C` | 2 | Current load | Read-only |
| `0x3F` | 1 | Temperature (°C) | Read-only |
| `0x41` | 1 | Current (mA) | Read-only |

A "READ DATA" gives you the value at an address; a "WRITE DATA" sets it.

### Timing, errors, and gotchas (the part the datasheet hides)

- **Half-duplex turnaround.** After the host finishes transmitting, the line must
  "turn around" before the servo's reply starts. The host's UART bridge (e.g.
  Waveshare adapter) handles this with its DIR pin; sloppy transceivers cause
  lost first bytes.
- **Checksum = only error detection.** It catches single-bit flips, not
  systematic corruption. If your CRC keeps failing, suspect baud mismatch or
  cable length / capacitance — drop to 115 200 for bring-up.
- **`0xFF 0xFF` is sacred.** Anything that emits two `0xFF` bytes in a row on
  the line (noise, ground bounce) will desync the parser into thinking a new
  frame started. Long cables + motors = ground bounce, hence the 1 M baud
  bring-up warning in the protocol manual.
- **EEPROM lock bit.** Some registers (notably ID, baud) live in EEPROM and
  have a lock bit. You must explicitly unlock before changing them, and EEPROM
  has limited write endurance — don't toggle ID/baud in a tight loop.
- **Broadcast PING collides.** Never PING on broadcast ID with more than one
  servo on the bus — every servo replies at once, all replies XOR together,
  every checksum fails.

### Why this protocol exists (the design rationale)

| Need | Mechanism |
|---|---|
| Talk to many servos from one wire | ID + broadcast ID + half-duplex bus |
| Get specific feedback (position, load, temp) | Control table, READ DATA |
| Command many servos to move **together** | REG WRITE + ACTION, or SYNC WRITE |
| Detect corruption | Length byte + checksum |
| Reverse direction / change ID / change baud | WRITE DATA to those addresses |

### How this differs from "dumb" RC servos

- **Dumb RC servo:** host sends a 50 Hz PWM pulse (1 ms–2 ms), servo drives
  to that setpoint. No position feedback to the host. No ID. No bus.
- **STS3215 (this protocol):** host sends a packet, servo has an MCU, encoder,
  PID loop, can report position / load / temp back. Many servos share one wire.
  This is a **smart bus servo**, not an RC servo. The Pulse mode is *also*
  available, but it's the legacy/dumb fallback, not the normal operating mode.

### How this differs from CAN / RS-485 / I²C

| Bus | Signal wires | Topology | Arbitration | Used by |
|---|---|---|---|---|
| **Feetech SCS (STS3215)** | 1 (half-duplex TTL) | Multi-drop daisy | Master-initiated only | Hobby smart servos |
| **RS-485 (SMS series)** | 1 differential pair | Multi-drop | Master-initiated (often) | Industrial, longer cables |
| **CAN** | 1 differential pair | Multi-drop | CSMA/CA, non-destructive bit arbitration | Cars, robots |
| **I²C** | 2 (SCL+SDA) | Multi-drop | Open-drain, clock-mastered | Sensors, low-speed peripherals |

The big idea: the STS3215's bus is **the simplest multi-drop protocol that
still gives you position feedback** — perfect for a 6-servo arm, useless for a
production line.

---

## Cross-Reference — How the Four Terms Connect on the STS3215

```
┌────────────────────────────────────────────────────────────┐
│           brushed DC motor (high speed, low torque)        │
│                       │                                    │
│                  1/345 gear ratio  ◄── §1                  │
│                       │                                    │
│              magnetic encoder (4096 steps/rev) ◄── §3      │
│                       │                                    │
│            MCU + PID loop + bus transceiver                │
│                       │                                    │
└───────── one Signal wire (TTL, half-duplex, 1 Mbps) ───────┤
                         ▲                          ▲       │
                         │                          │       │
              ┌──────────┴──────┐          ┌────────┴─────┐ │
              │  Controller     │          │  Other 5     │ │
              │  (Waveshare     │          │  STS3215s    │ │
              │   adapter)      │          │  on the bus  │ │
              └─────────────────┘          └──────────────┘ │
                         ▲                                  │
                         │   packet protocol ◄── §2 + §4    │
                         │   (8N1 @ 1 Mbps, SCS layout)    │
                         └──────────────────────────────────┘
```

Every term in this doc appears, with its role, in that single picture:
**gear ratio** shapes the mechanical side; **TTL half-duplex async serial**
is the physical/logical layer; **magnetic encoder** is the feedback; the
**Serial Bus Smart Servo protocol** is the conversation layer on top.

---

## Mini-Glossary (for quick lookup)

| Term | One-line meaning |
|---|---|
| Gear ratio | Input revs per output rev; trades speed for torque. STS3215 = 1/345. |
| TTL | 0–0.45 V = LOW, 2–5 V = HIGH. Chip-to-chip voltage standard. |
| UART | Async serial hardware block; no shared clock. |
| 8N1 | 8 data, no parity, 1 stop bit — the per-byte frame shape. |
| Baud | Bits per second on the wire; both ends must match. |
| Half-duplex | One shared wire, one direction at a time. |
| Incremental encoder | Pulses; must home for absolute position. |
| Absolute encoder | Unique code per angle; known on power-up. |
| Magnetic encoder | Hall IC senses a magnet on the shaft → angle. STS3215 = 12-bit, 0.088°. |
| Optical encoder | Photodiode + slotted disc; can fog/contaminate. |
| Potentiometric encoder | Resistive wiper; cheap, wears out, <360°. |
| Multi-drop | Many devices on one bus. |
| Daisy-chain | Wire runs from device to device to device. |
| Packet | Header + ID + length + payload + checksum. |
| Control table | Servo's address → meaning memory map. |
| REG WRITE / ACTION / SYNC WRITE | Three ways to move multiple servos in lock-step. |
| Broadcast ID | 0xFE — every servo accepts, none reply. |
| Little-endian | Low byte first; SCS convention for two-byte values. |