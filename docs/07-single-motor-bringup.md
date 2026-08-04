# Chapter 7 — Single Motor Bring-Up

> The laboratory sequence: from a servo on the desk to closed-loop position control of
> **one** joint. Every gate has: objective → theory → hardware → wiring → commands →
> expected output → verification → failures → troubleshooting. **Do not skip gates.**
> The arm is currently unplugged (no tty on 2026-08-04); all "expected" rows are
> `[BENCH-CHECK]` until your first live run, and every run should be logged in
> `logs/` using `logs/bench-log-template.md`.

**Test article:** 1× STS3215 (7.4 V variant), 1× 5264-3P pigtail, 1× Waveshare
adapter, 1× USB-C data cable, 1× bench PSU (0–7.4 V, current-limit), 1× DMM.

---

## G0 — Motor on the desk, power disconnected

**Objective:** safe starting condition, tools staged.
**Theory:** first rule of bench work — no stored energy, verified by meter.
**Wiring:** nothing connected.
**Verify:** PSU output OFF, leads free, USB unplugged.
**Troubleshoot:** if the servo was *just* powered: it holds no torque on power-on
(torque switch SRAM default 0 — ch03 §3.6), so a hot motor is safe to handle; let it
cool before holding it anyway.

## G1 — Hardware inspection

**Objective:** verify the test article matches inventory F2–F9.
**Theory:** datasheet §6 dimensions, §6-7 connector, §5-7 voltage window.
**Commands/checks:**

| Check | Method | Pass |
|---|---|---|
| Model marking | visual (cable/box): STS3215, C001 7.4 V | match |
| Spline/horn | 25T, horn optional | — |
| Pigtail intact | visual + continuity: pin1–G, pin2–V, pin3–D | all continuous |
| No burn marks / smell | visual | none |
| Encoder homing | rotate output by hand; position feedback (G6) tracks 0–4096 wrap | monotonic |

## G2 — Cable verification

**Objective:** prove the 3-pin loom is pin-for-pin D/V/G.
**Theory:** ch04 §4.6 — color is not truth; continuity is.
**Method (DMM, power off):** ring out adapter servo-port pins to the loose end of each
loom segment; also check no D–V or D–G shorts (should be open).
**Pass:** V↔V, G↔G, D↔D continuous; D↔V, D↔G, V↔G open.

## G3 — Power supply setup (bench PSU)

**Objective:** correct rail, protection in place.
**Theory:** ch03 — pass-through rail; 7.4 V max.
**Commands:**

```
PSU: voltage 0 → current-limit 2 A → output OFF
wire PSU → adapter DC5521 (polarity pre-checked with DMM)
set PSU to 7.40 V (still OFF)
enable output
```

**Expected:** DMM at adapter servo port = 7.40 ± 0.05 V; adapter LED (if fitted) lit.
**Failures:**
| Symptom | Cause | Fix |
|---|---|---|
| 0 V at port | output OFF, tripped limit, polarity | re-check sequence |
| >7.5 V | PSU set wrong | **stop, trim to 7.40 V** |
| PSU folds back | short in loom | unplug servo, ring out loom |

## G4 — Communication setup (USB)

**Objective:** host sees the adapter as a serial port.
**Commands:**

```bash
ls -l /dev/ttyUSB* /dev/ttyACM*        # expect your node
dmesg | tail -5                        # expect CH340/ACM registration
sudo usermod -aG dialout $USER         # one-time; re-login
```

**Expected:** exactly one tty node appears after plugging USB-C.
**Failures:** no node → data cable? (charge-only is the classic), hub, jumper caps not
on B, `chmod`/dialout missing.

## G5 — Device detection (PING)

**Objective:** prove the servo answers on the bus; measure the round-trip.
**Theory:** ch05 §5.4 — PING frame `FF FF ID 02 01 CHK`; only matching ID replies.
**Commands:**

```bash
source ~/Deployments/lerobot-venv/bin/activate   # or your venv
python3 scripts/bench.py ping --id 1
```

**Expected:**
```
tx: ff ff 01 02 01 fb
rx: ff ff 01 02 00 fc     (17 bytes echoed by the adapter, servo reply embedded)
```
PING 0xFE (broadcast) on a 1-servo bus answers with the servo's ID in the reply.
**Failures:**
| Symptom | Cause | Fix |
|---|---|---|
| no rx | wrong port/baud, idle line, dead servo | check port, baud=1e6, D continuity |
| garbled rx | baud mismatch (servo was re-configured) | re-set baud (ch05 §5.6, 0x06) |
| timeout on ID1 | servo not ID1 (factory=1, but check) | PING all IDs 0–253 scan |

## G6 — Status read

**Objective:** confirm telemetry registers look sane.
**Theory:** memory table §0x38/0x3E/0x3F/0x3C/0x45/0x41 (ch05 §5.6).
**Commands:**

```bash
python3 scripts/bench.py read --id 1
```

**Expected (7.4 V rail, unloaded, stationary):**

| Register | Value | Rationale |
|---|---|---|
| 0x38 position | any 0–4095 | free rotor |
| 0x3E voltage | 74 (×0.1 V) | rail 7.40 V |
| 0x3F temperature | 20–40 °C | ambient |
| 0x3C load | ≈ 0 | unloaded, torque off |
| 0x41 status | 0x00 | no faults |
| 0x45 current | ≈ 6–150 | mA units |

**Failures:** status ≠ 0 → decode fault bits (ch05 §5.7) — e.g. over-voltage if rail
sagged/spiked; temperature high if it was previously stalled.

## G7 — Motor enable (torque on) — FIRST MOVEMENT GATE

**Objective:** transfer control to the servo loop safely.
**Theory:** torque switch 0x28; hold a position with no commanded move keeps the motor
stiff at its current spot. **Hands clear.**
**Commands:**

```bash
python3 scripts/bench.py torque on --id 1
python3 scripts/bench.py read --id 1    # watch: load ↑, mobile sign 0
```

**Expected:** servo becomes stiff (resist light finger deflection); load register rises
to a small holding value (a few % of 1000); no movement commanded.
**Failures:** servo stays limp → torque switch write rejected (EEPROM lock? wrong ID?),
or 0x41 shows a protection latch — clear by sending a new position command (G8).

## G8 — Slow movement (position control, small step)

**Objective:** closed-loop position control of one joint, cautiously.
**Theory:** Goal_Position 0x2A (L,H), Running_Speed 0x2E limits step rate,
Acceleration 0x29 ramps it — the *only* two settings between you and a fast actuator.
**Commands:**

```bash
# read current position first
python3 scripts/bench.py read --id 1
# move +180 steps (~16°) at 200 steps/s
python3 scripts/bench.py move --id 1 --delta 180 --speed 200
python3 scripts/bench.py read --id 1
```

**Expected:** after enable: position rises monotonically toward target, then holds
(mobile sign 0); load stays low (<200/1000) unless something loads the output.
**Failures:**
| Symptom | Cause | Fix |
|---|---|---|
| overshoot/oscillation | PID gains from prior session | rewrite P/D (0x15/0x17) sensible values |
| moves but wrong side | direction customization (0x12) | check phase byte / restore defaults |
| nothing moves, load spikes | mechanical jam or wrong delta | read load, disconnect, inspect |
| 0x41 protection latch | stalled too long | new position cmd clears; reduce speed/delta |

## G9 — Velocity control

**Objective:** operate mode 1 (speed closed-loop) — the "motor mode".
**Theory:** operation mode 0x21=1; Running_Speed 0x2E with bit15 = direction
(community table; direction semantics `[BENCH-CHECK]`).
**Commands:**

```bash
python3 scripts/bench.py mode --id 1 --mode 1
python3 scripts/bench.py speed --id 1 --rpm 0.5    # ~35 steps/s
# observe position register ramping
python3 scripts/bench.py speed --id 1 --rpm 0
python3 scripts/bench.py mode --id 1 --mode 0      # back to position servo
```

**Expected:** output rotates continuously at the commanded rate while position
increments; stopping command halts it. **Verify** no-load only; a loaded velocity run
can draw stall current quickly.
**Failures:** no rotation → baud/PID loop settings; direction reversed → sign flip.

## G10 — Current control (read-only; STS3215 has no current-command mode)

**Objective:** observe and bound motor current; verify the protection current trip.
**Theory:** current register 0x45 (6.5 mA/unit, max ~3250 mA); Protection_Current 0x1C
(default 500 counts ≈ 3.25 A — near stall, so the stock trip rarely fires before the
PSU does). LeRobot configures the **gripper** to 250 counts (~1.6 A) to avoid burnout.
**Commands:**

```bash
python3 scripts/bench.py read --id 1     # watch 0x45: free-spin ≈ 150 mA (23 counts)
# optional controlled stall probe: hold output, command slow move, watch current climb
```

**Expected:** free-run current ≈ 130–150 mA @7.4 V (datasheet §5-3). A brief stalled
probe raises current toward 2.5 A (385 counts) before protection time elapses — then
torque off + latch.
**Safety:** keep stall probes < 2 s; PSU limit 2 A as backstop.

## G11 — Emergency stop (know your kills)

**Objective:** both kill paths, verified before anything else on the arm.
**Theory:** hard kill = PSU output OFF; soft kill = torque-off write; LeRobot
disconnect defaults to torque-off.
**Commands:**

```bash
# soft kill: broadcast torque off (all IDs)
python3 scripts/bench.py estop
# hard kill: PSU output OFF (muscle memory!)
```

**Expected:** soft kill → servo goes limp within one frame; hard kill → servo
depowered (V=0 at port). Verify both while the motor is holding a position.
**Failures:** if soft kill does not limp the servo, the torque-off write is not
reaching it — treat bus health as suspect before continuing.

## G12 — Shutdown

**Order:** estop (soft) → PSU output OFF → close scripts → unplug USB → unplug servo
cable. Same discipline as ch03 §3.7. Log the session in `logs/` before walking away.

---

## After the single motor: scaling to six

- `lerobot-setup-motors` assigns IDs 1–6 (setup each motor individually — LeRobot's
  tool walks you through, one motor on the bus at a time).
- Calibrate (homing/limits) with `lerobot-calibrate` — required before LeRobot will
  accept commanded positions.
- Only then build the full chain (loom 1→2→…→6, ch04) and repeat G5 (PING all six) with
  the whole arm. Any servo that fails PING in-chain = loom segment suspect (ch08 §bus).