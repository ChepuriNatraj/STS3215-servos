# Chapter 8 — Debugging

> Symptom → hypotheses → measurements → expected values → tools → fix. Every row is
> actionable with what you already own (DMM + bench PSU + serial). Figure shorthand:
> **P** = power section, **C** = communication, **S** = servo-level, **H** = host.

## 8.1 No communication (host to adapter)

| Step | Measure | Expected | Tools |
|---|---|---|---|
| S1 | `ls /dev/ttyUSB* /dev/ttyACM*` after replug | node appears | shell |
| S2 | `dmesg | tail` | CH340/`cdc_acm` kernel msg | shell |
| S3 | DMM on adapter servo-port V/G | 0 V (USB only feeds bridge) | DMM |
| S4 | jumper caps position | **B** | eyes |
| S5 | try both servo ports | at least one responsive | bench.py |

**Causes / fixes:** charge-only USB cable → replace; dead hub/dock → plug direct;
`dialout` missing → `sudo usermod -aG dialout $USER`; port name guessed wrong → use the
`dmesg` node; caps on A → move to B.

## 8.2 Motor not detected (PING fails) — single motor on bench

| # | Hypothesis | Measurement | Expected | Fix |
|---|---|---|---|---|
| H1 | wrong ID | PING scan IDs 0–253 (`bench.py ping` each; or 0xFE broadcast on 1-servo bus) | one reply | set ID (ch05) |
| H2 | baud mismatch | `bench.py ping` at 1e6 | reply | rewrite 0x06=0 (EEPROM, unlock 0x37 first) |
| H3 | no power | DMM servo-port V, servo pigtail V | 7.4 V at pigtail | PSU/cable (ch03) |
| H4 | D wire broken | continuity pigtail + loom, D–D | closed | swap cable |
| H5 | servo latched | read 0x41 (can't — no comm) → opt: power-cycle servo alone | — | fresh power cycle to clear latch |
| H6 | servo dead (fet ruined) | pigtail V/G resistance through servo | finite magnet windings see ~Ω | replace |

**Rule of the bench:** one servo, one cable, known port, known baud — always isolate
before touching the arm's loom.

## 8.3 "CAN errors" — wrong toolchain expectation

The SO-101 bus is **TTL UART**, not CAN. If you reach for `candump`/`can0`/`ip link set
can0`, you are on the wrong protocol layer. There is no CAN node, no termination, no
CAN-ID map here. SocketCAN is for your separate DAMIAO DM-J4310 rig. Correct tool:
`pyserial`/`bench.py` on the adapter's tty node at 1 000 000 baud.

## 8.4 Power problems

| Symptom | Measure | Expected | Fix |
|---|---|---|---|
| Servo glitches / reset-spins | V at pigtail while moving | stays 7.4 ± 0.20 V | bigger/cleaner PSU; raise limit; shorter loom |
| PSU folds back on cold start | current draw on enable | < limit | pre-charge (brief) or raise limit deliberately |
| Over-voltage bit in 0x41 | rail voltage | ≤ 7.40 V | trim PSU |
| Under-voltage bit | rail during stall | ≥ 4.0 V | PSU headroom |
| Hot servo after hold | 0x3F temp | < 70 °C | reduce torque/limit, unload joint |
| Brown-out glitches on host | USB cable | solid | shielded/known-good cable |

## 8.5 Configuration mistakes (behavior wrong but comms alive)

| Symptom | Register | Expected | Fix |
|---|---|---|---|
| Moves wrong direction | 0x12 phase / direction bits | datasheet default | restore defaults or re-set direction |
| Reaches wrong angles | calibration file / homing offsets | LeRobot `get_observation` matches physical | re-run `lerobot-calibrate` |
| Hysteresis/overshoot | 0x15–0x17 PID | P~16 D~32 I~0 | rewrite gains at connect (LeRobot does) |
| Limp always | 0x28 torque | 1 when enabled | EEPROM lock didn't persist your write? check 0x28 again after power cycle |
| Ignores writes | EEPROM lock 0x37 =1 | 0 | write 0 |
| Weird huge position | byte order | L,H | verify read/write byte order (ch05) |

## 8.6 Fault states (status register 0x41 non-zero)

Decode bitfield (ch05 §5.7; `[INFERRED]` mapping): read each bit via
`bench.py read`. Common patterns:

| Status | Meaning | Next move |
|---|---|---|
| over-voltage | rail spiked or PSU too high | kill power, trim PSU, inspect loom for back-EMF source |
| over-temperature | stalled/held too long | cool down, reduce limit, unload |
| over-current | >2 A for 2 s | new position command clears; check mechanical jam |
| angle/encoder | magnet slip / homing drift | re-calibrate; check horn/gear meshing |
| overload | >80 % stall for 2 s | unload joint; reduce speed/accel |

## 8.7 Firmware mismatch

Real-world cases: **servo firmware rev** (read 0x00/0x01/0x03/0x04 version regs) — if a
servo ignores SYNC-READ or velocity commands that others accept, the firmware rev
differs; fall back to per-servo READ/WRITE for that unit, or replace with a matched
unit. **LeRobot vs feetech-sdk version** — if `lerobot-setup-motors`/configure throws
on an instruction, ensure `feetech-servo-sdk>=1.0.0,<2.0.0` (random old SDKs break
ops). **Adapter bridge firmware** — Waveshare ships as-is; no user firmware to manage
(`[VERIFIED]` Wiki: no firmware for the adapter).

## 8.8 Wiring errors

| Symptom | Typical cause |
|---|---|
| Multiple servos dead but first alive | broken loom segment downstream (continuity test per segment) |
| First servo resets/glares when a second plugs in | reversed segment (V↔G on brace) — ring out every segment |
| Intermittent during movement | cold joint / worn latch / chafed loom at a joint — inspect dress, re-test segment by segment |
| Smoke | polarity reversal or excessive rail — kill power, replace damaged part, re-verify before power |

## 8.9 Debugging kit (minimal)

1. DMM (continuity + V + A) — *the* primary tool
2. 2 A/5 A-limited bench PSU with display
3. Data USB-C + a second known-good cable
4. `bench.py` + `pyserial`
5. (later, ch09) logic analyzer to capture the D line

## 8.10 Decision tree (first failure of any gate)

```
                    any gate fails
                         │
       device node present? ──no──► 8.1 (USB/jumper/perms)
                         │yes
       ping replies? ────no──► 8.2 (ID/baud/power/D/broken servo)
                         │yes
       status 0x41 == 0? ──no──► 8.6 (decode fault bits)
                         │yes
       telemetry sane? ────no──► 8.4 (power) / 8.5 (config)
                         │yes
       rest of gate        ─► proceed / 8.8 (wiring) / 8.7 (firmware)
```