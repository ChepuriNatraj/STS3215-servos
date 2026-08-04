# Chapter 3 — Power System

> **The one-sentence law of this robot:** every servo sees the bench PSU voltage
> directly — there is no converter, no fuse, no regulator between them. Whatever you
> set at the PSU is what the servos' H-bridges and logic get. Set it wrong once and
> you can destroy up to six servos.

## 3.1 Power input

| Item | Value | Evidence |
|---|---|---|
| Connector on adapter | DC5521 (5.5 × 2.1 mm) jack **and** green 2-way screw terminal (parallel entry, either works) | Waveshare wiki |
| Polarity | `[BENCH-CHECK]` — verify center pin vs sleeve with meter before first power-up; datasheet convention is center-positive for DC5521, verify on *your* PSU lead | — |
| Voltage window (this servo variant) | **4.0 – 7.4 V**; typical 6.0 / 7.4 V | STS3215 datasheet §5-1, §5-7 |
| Adapter input label | 9 – 12.6 V — that is for the *12 V* STS3215 variant; it is **not** your max | Waveshare wiki + datasheet |
| Current source | Bench PSU (variable, current-limited), e.g. OWON SPE-series | your bench |

> ⚠️ **Over-voltage budget:** the 7.4 V variant's protection trips > 7.4 V (§0x0E
> default 80 × 0.1 V) and *auto-clears*; if the over-voltage persists long enough, the
> H-bridge and MCU take the abuse. Cap the PSU at **7.40 V** and set a hard current
> limit before enabling the output.

## 3.2 Voltage rails

```
PSU  ──►  adapter V_in  ──►  bus V  ──►  [each servo]
             │                │              ├──► servo logic rail (on-board 3.3 V-class)
             │                │              └──► motor (raw bus V, H-bridge)
             └──► G          G ──► G
```

- **Bus V rail:** raw input, pass-through, shared by all six servos.
- **Logic rails:** created *inside* each servo; no external 3.3 V exists on the loom.
- **USB 5 V (VUSB):** powers the adapter's bridge electronics only — the servo ports'
  V pin is *not* fed from USB (adapter requires external supply to move motors).
  `[VERIFIED]` Waveshare wiring docs; `[BENCH-CHECK]` with a meter: V pin ≈ 0 V with
  only USB connected.

## 3.3 Current budget (plan the PSU)

| Load case | Current | Evidence |
|---|---|---|
| 6 servos, idle/stopped | ~36 mA total (6 mA each) | datasheet §5-6 |
| 6 servos, free motion | ~900 mA total (150 mA each @7.4 V) | datasheet §5-3 |
| 6 servos, rated torque | ~3.9 A total (650 mA each) | datasheet §5-9 |
| 1 servo, stalled | 2.5 A | datasheet §5-5 |
| 6 servos, simultaneous stall | ~15 A theoretical (H-bridges limit individually; brief) | derived from §5-5 |

**Engineering rules**
1. Bench PSU: set **7.4 V**, current limit **2 A** for single-motor experiments,
   5 A for the full arm, **output OFF** until wiring is verified.
2. If the PSU current-limit trips on rapid multi-joint moves, you are driving a real
   load — raise the limit only after checking load/current registers (ch05) and
   temperatures; do not paper over a mechanical jam.
3. Voltage sag under load is your earliest failure symptom: if a motor drops below
   its min voltage limit, it faults. Watch the *current voltage* register (§0x3E).
4. No bulk capacitance, no brake resistor, no fuse on the adapter ([VERIFIED] no
   regulation; fuse absent from schematic `[INFERRED]`). Treat inrush when you first
   enable a cold chain: limit current during the first power-on of the day.

## 3.4 Protection circuits (what actually protects you)

| Layer | What protects | Details | Evidence |
|---|---|---|---|
| PSU current limit (you) | servos + loom | set before output ON | — |
| PSU over-voltage cap (you) | servos | 7.40 V max | datasheet §5-7 |
| Servo over-current protection | each motor | >2 A for 2 s → torque off (default) | datasheet §7-11 |
| Servo over-voltage/under-voltage | each motor | >7.4 / <4 V → alarm, auto-clear | datasheet §7-11 |
| Servo over-temp | each motor | >70 °C → torque off | datasheet §7-11 |
| LeRobot `disable_torque_on_disconnect` | operator | torque OFF when driver disconnects | LeRobot config |

There is **no host-side fuse** — a reversed PSU lead or a V/G short becomes your PSU's
problem, so **the PSU current limit is the primary hardware protection**.

## 3.5 Grounding

- One ground network: PSU G → adapter G → bus G → every servo → (via USB cable
  shield/G) → host GND.
- The USB G tie means the PSU G and the host ground are at the same potential;
  floating PSUs are fine, but never power the servo bus from a rail that is already
  referenced elsewhere without checking common-mode voltage first (`[BENCH-CHECK]`:
  measure PSU G vs USB G — expect ~0 V).
- Ground loops: single-point star at the adapter is the design; do *not* also ground
  the arm frame to mains.

## 3.6 Safe power-up sequence (gate 1 of bring-up)

```
1. PSU: voltage knob to 0, current limit 2 A, output OFF
2. Connect PSU → adapter (DC5521 or screw terminal), polarity verified with meter
3. Connect USB-C (data cable) to host
4. Meter on adapter servo-port V/G: ~0 V
5. Set PSU voltage to 7.4 V (still OFF)
6. Enable PSU output
7. Meter servo-port V/G: 7.40 ± 0.05 V      ← gate check
8. THEN plug the (single) motor 3-pin cable and run PING (ch07)
```

Servos power up with **torque disabled** (torque-switch SRAM initial value 0 —
`[VERIFIED]` memory table), so nothing moves on power-on. Verify this before trusting
it: read §0x28 on a freshly-powered servo and expect 0.

## 3.7 Safe shutdown sequence

```
1. Software: disable torque (write 0x28 = 0 to each ID; LeRobot does this on disconnect)
2. Stop the host process / close the port
3. PSU output OFF
4. (Optional) unplug USB
5. Then unplug servo cables / service
```

Emergency stop = **PSU output OFF** (hard kill, guaranteed) *and/or* `Ctrl-C` on the
LeRobot process (soft kill, torque-off on disconnect). Know which one you reached for;
if the PSU was the kill, the servo bus is depowered — start again from §3.6.

## 3.8 Regeneration (informed caution)

A falling arm or back-driven joint can regenerate energy into the bus. With no brake
resistor, that energy raises Vbus — the over-voltage protection *will* trip and
auto-clear, which reads as a momentary fault on a heavy joint move. Bench PSUs usually
sink some of this. Practical mitigations: command smooth slow profiles (acceleration
register §0x29, or `max_relative_target` in LeRobot) and don't command fast descents
with the arm fully extended. `[INFERRED]` — no official statement; observed behavior
class.

## 3.9 Failure diagnostics — power

| Symptom | Measure | Expect | Fix |
|---|---|---|---|
| Nothing on bus, no LED on adapter | V at servo port | 7.4 V | PSU output/limit, cable, polarity |
| Servos glitch/jump | V while moving | stays within ±0.2 V | PSU too weak, sag; raise limit/PSU class |
| Over-voltage alarm bit | §0x41 status | 0 | PSU trim down to 7.40 V |
| Torque dead but bus alive | §0x28, §0x41 | torque=1, no fault bits | protection latch → send new position cmd |
| Smoke at adapter/servo | — | — | Kill power now; inspect for reversed polarity |