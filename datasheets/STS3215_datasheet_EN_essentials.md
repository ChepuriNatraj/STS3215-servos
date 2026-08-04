# STS3215 — Essential Specs (EN)

**Manufacturer:** Feetech (SHENZHEN FEETECH RC MODEL CO., LTD.)
**Type:** 7.4 V, 19 kg·cm, plastic case / metal gear / magnetic encoder / dual-shaft / TTL serial bus servo
**Edition:** A/0 (2020-04-10)

---

## 1. Electrical

| Parameter | @ 6 V | @ 7.4 V |
|---|---|---|
| Operating voltage range | 4 V – 7.4 V | |
| No-load speed | 0.238 s/60° (42 RPM) | 0.192 s/60° (52 RPM) |
| No-load current | 130 mA | 150 mA |
| Stall torque | 16.5 kg·cm | **19.5 kg·cm** |
| Stall current | 2.0 A | 2.5 A |
| Rated load | 4 kg·cm | 5 kg·cm |
| Rated current | 500 mA | 650 mA |
| Idle current | 6 mA | 6 mA |
| Terminal resistance | 2.5 Ω | |
| Torque constant (Kt) | 8 kg·cm/A | |

---

## 2. Mechanical

- Size: 45.2 × 24.7 × 35 mm
- Weight: 55 ± 1 g
- Case: PA+GF (plastic); Gears: copper; Bearings: ball
- Gear ratio: **1/345**
- Backlash: ≤ 0.5°
- Output horn: 25T, OD 5.9 mm; screw M3×6
- Mechanical limit: none (relies on software limits)

---

## 3. Sensor

- 12-bit magnetic encoder, 360° range
- Resolution: **4096 steps/rev → 0.088°/pulse**
- Lifetime: unlimited

---

## 4. Control Interface

- **Protocol:** half-duplex async serial (8N1), digital packet
- **ID range:** 0–253
- **Baud rate:** 38400 bps – 1 Mbps (**default 1 Mbps**)
- **Control algorithm:** PID (tunable)
- **Max position update rate:** 1 ms
- **Signal voltage:** High 2–5 V, Low 0–0.45 V
- **Neutral position:** 180° (value 2048)
- **Rotation direction:** CW 0→4096 (reversible)

### Operating Modes

| Mode | Description |
|---|---|
| 0 | Angle servo — 0–360° absolute position (default) |
| 1 | Speed closed-loop motor — speed held under load |
| 2 | Speed open-loop motor — speed droops under load |
| 3 | Step mode — relative step from current position |
| Multi-turn | Up to ±7 turns absolute, but turns not saved on power-off |

### Electronic Protections

| Protection | Threshold | Behavior |
|---|---|---|
| Overload | >80% stall torque for 2 s | Output off (configurable %) |
| Overcurrent | >2 A for 2 s | Output off (configurable) |
| Overvoltage | >7.4 V or <4 V | Output off, auto-recover |
| Overtemperature | >70 °C | Torque output off |

> Cleared by sending a new position command.

---

## 5. Connector & Cable

- Connector: **5264-3P** (JST-style), cable length 15 cm
- Pinout:

| Pin | Signal |
|---|---|
| 1 | GND |
| 2 | VCC |
| 3 | Signal / TTL |

---

## 6. Environmental

- Storage: −30 °C to +80 °C
- Operating: −20 °C to +60 °C
- **No waterproofing**

---

## 7. Reliability

- Life test: >100 000 cycles (1/5 stall torque, ±60° sweep)
- Motor noise: 45 ± 5 dB @ 30 cm
- Gear noise: 60 ± 5 dB @ 30 cm
- Certifications: EMC, ROHS (no FCC/REACH/ASTM/EN71)
