# Chapter 4 — Wiring & Connectors

> Complete connector census of the SO-101 motor-side wiring. **Wire colors vary by
> batch** — every table here lists the *pin* function first and treats color as
> `[BENCH-CHECK]`. Measure with a meter before trusting a color.
> Photos go in `assets/` using the naming table in §4.7.

## 4.1 Connector census (one arm)

| Ref | Connector | Where | Direction | Carries |
|---|---|---|---|---|
| C1 | USB Type-C | adapter ↔ host | host → adapter (data bidir) | USB 2.0 data, 5 V VUSB |
| C2 | DC5521 jack (5.5×2.1) | adapter input | PSU → adapter | servo power V/G |
| C3 | Green 2-way screw terminal | adapter input | PSU → adapter | servo power V/G (parallel to C2) |
| C4 | 4-pin jumper header, caps A/B | adapter | — | selects UART (A) vs USB (B) bridge |
| C5 | 3-pin servo port ×2 (marking D V G) | adapter | adapter → bus | D (signal, bidir), V, G |
| C6 | `5264-3P` pigtail on each servo | servo | bus → servo (and pass-through) | pin1 G, pin2 V, pin3 D |
| C7 | 3-pin daisy-chain loom segments | between servos | chain 1→2→3→4→5→6 | V, G pass-through + D bus |

## 4.2 C1 — USB Type-C (host ↔ adapter)

| | |
|---|---|
| Purpose | Transport for the bus protocol + (usually) adapter logic power |
| Pinout | Standard USB-C; use a **data** cable. Charge-only cables fail silently |
| Voltage | 5 V (VUSB), negligible current for bridge logic |
| Signal | USB 2.0 D+/D−, half-duplex at bus level is handled inside the adapter |
| Expected measurement | `dmesg` shows CH340/`cdc_acm`; node appears in `/dev` |
| Common mistakes | charge-only cable; hub without data lines; plugging into a 5 V-only charge port |

## 4.3 C2/C3 — Power input (DC5521 + screw terminal)

| | |
|---|---|
| Purpose | Feed the servo bus; **not** regulated, **not** fused |
| Wiring | C2: center pin ↔ sleeve (polarity `[BENCH-CHECK]`, meter before first use — convention: center **+**); C3: two screws, one + one −, check meter |
| Voltage | set to **7.40 V max** for the 7.4 V servo variant |
| Expected measurement | at adapter servo port: V=7.40 V, G=0 V |
| Common mistakes | reversed polarity; setting 9–12.6 V "because the label says so" (label assumes 12 V servos); leaving PSU output ON while changing the cable (spark/ESD) |

## 4.4 C4 — Jumper header (A/B)

| | |
|---|---|
| Purpose | Choose bridge input: **A** = UART 4-pin header (host MCU), **B** = USB-C |
| Required for this build | both caps on **B** ([VERIFIED] LeRobot docs) |
| Common mistakes | caps on A → USB silent, servo bus appears dead from the host |

## 4.5 C5 — 3-pin servo ports (adapter side, ×2)

| Pin | Marking | Function | Direction |
|---|---|---|---|
| 1 | **D** | bus data (TTL half-duplex) | bidir, idle low |
| 2 | **V** | servo supply (+4.0…7.4 V) | out |
| 3 | **G** | power ground | common |

- Both ports are identical and interchangeable ([VERIFIED] FAQ).
- D quiescent level: ~0 V (idle low); during a frame, pulses to 3.3–5 V TTL
  (`[BENCH-CHECK]` with scope — protocol manual cites 2–5 V high, 0–0.45 V low).

## 4.6 C6/C7 — Servo pigtail (5264-3P) and daisy-chain loom

**Servo pigtail** (15 cm stock, `[VERIFIED]` datasheet §6-7):

| Pin | Function | Datasheet |
|---|---|---|
| 1 | GND | `[VERIFIED]` |
| 2 | Vcc | `[VERIFIED]` |
| 3 | Signal / TTL | `[VERIFIED]` |

Color convention seen on Feetech bus-servo looms: red ≈ V, black ≈ G, white/yellow ≈ D
(`[INFERRED]` from product photos; **verify on your batch**). The connector housing is
marked `5264-3P`; measure pitch with calipers and record it in `docs/00-hardware-inventory.md`.

**Daisy-chain loom** (C7): segments connect servo_n's pigtail output to servo_{n+1}'s
pigtail input, pin-for-pin (D↔D, V↔V, G↔G). The SO-101 routes: adapter → motor 1
(shoulder_pan) → 2 → 3 → 4 → 5 → 6 (gripper). No terminators exist on this bus type;
the chain simply ends at servo 6.

**Order diagram:**

```
[adapter C5] ──C7──► [1 shoulder_pan] ──C7──► [2 shoulder_lift] ──C7──► [3 elbow_flex]
     ──C7──► [4 wrist_flex] ──C7──► [5 wrist_roll] ──C7──► [6 gripper]   (end)
```

**Common mistakes**
- Plugging the cable one row off (D/V/G misaligned) — instant short of V→D or V→G.
- Reversing a loom segment (G wired to V) — one servo gets polarity reversed.
- Using 2-wire power-only cables on a servo port — no D, silent servo.
- Breaking a latch while dressing the loom into the printed channels (arm rework
  needed; inspect continuity after any re-dress).
- Daisy-chain order ≠ IDs: the *bus* doesn't care, but the *loom path* must reach
  every servo; a single broken segment kills the downstream chain.

## 4.7 assets/ photo convention

When you photograph your unit, name files so chapters can reference them:

| Prefix | Subject |
|---|---|
| `adapter_top_` | adapter board top, jumpers visible |
| `adapter_power_` | DC5521 + screw terminal wiring |
| `servo_pigtail_` | 5264-3P pigtail, pin order labeled |
| `loom_chain_` | daisy-chain path through the arm |
| `psu_` | bench PSU settings (V, I) per bring-up gate |
| `measure_` | multimeter/scope captures (V, D line, waveforms) |

Example: `assets/adapter_top_B_jumpers.jpg`. Reference them from the chapters with
`![Adapter top](./assets/adapter_top_B_jumpers.jpg)`.