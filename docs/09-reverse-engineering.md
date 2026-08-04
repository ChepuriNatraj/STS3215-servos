# Chapter 9 — Reverse Engineering

> How to investigate the SO-101's electronics the professional way: inspect, identify,
> trace, capture, and *prove* — always separating **confirmed facts** from **informed
> hypotheses**. The two PCBs in this system (Waveshare adapter, STS3215 control board)
> are both tractable: the adapter even ships a public schematic, which turns "guess"
> into "verify".

## 9.0 Rules of engagement

1. **Evidence hierarchy** (strongest first):
   official datasheet/schematic > your own measurement > LeRobot/community source >
   inference > guess. Only the first two ever become `[VERIFIED]`.
2. **Photograph everything** before and during disassembly; name per ch04 §4.7.
3. **Power-off probing only** unless you have a scope/DMM and a plan.
4. Every finding lands in `docs/00-hardware-inventory.md` (§3 rules) so later readers
   can retrace confidence.

## 9.1 PCB inspection (visual)

| Task | Method | Outcome |
|---|---|---|
| Identify board | silkscreen marks: "Bus Servo Adapter (A)", rev letter | confirm rev |
| Bill-of-ICs | read every package marking (magnifier/macro photo) | part list |
| Power path | follow V-in → trace → servo port V pins on both sides | confirm pass-through |
| Signal path | follow CH340 UART → transceiver → D pins | confirm bridge |
| Protection parts | look for fuse/ferrite/TVS near power input | present/absent (`[INFERRED]` until measured) |

**What to expect on the adapter** ([VERIFIED] schematic in `datasheets/` + Waveshare
FAQ): CH340-class USB-uart, bus transceiver/buffer, jumpers A/B, DC5521 + screw
terminal, dual servo ports, UART header. The schematic shows a small power-buffer
section — verify against your unit's silkscreen.

## 9.2 IC identification & datasheet lookup

1. Mark part number (e.g. `CH340G`, `B5819WS`…).
2. Search manufacturer site first (WCH for CH340), then distributors (Mouser/DigiKey),
   then PDF aggregators. Record URL + retrieval date in `docs/10-reference-library.md`.
3. Map each IC's pinout back to the copper: which pin is D, which is the UART
   direction-control pin (half-duplex DE/gate) — the *gate* pin is the interesting one
   on this adapter.
4. **Servo control board** (inside STS3215): markings often silkscreen-only; MCU
   usually a Feetech-labeled or masked part (`[UNKNOWN]` until you open one). Expected
   blocks by function, not by part: MCU + 12-bit magnetic encoder (rotary magnet,
   `[UNKNOWN]` vendor — not documented by Feetech), H-bridge, current sense, temp
   sense, bus transceiver, regulator. Verify by tracing, not by assuming.

## 9.3 Signal tracing (power off → power on)

| Probe | Tool | What you should see |
|---|---|---|
| D pin quiescent | DMM | ~0 V (idle-low) |
| D high during frame | scope/LA | 2–5 V pulses at 1 Mbps |
| V pin | DMM | bus rail (7.4 V) |
| G continuity | DMM | 0 Ω to PSU − |
| UART DE/gate (adapter) | scope | toggles before every transmit burst |

Method: start at the USB connector, follow D+ / D− through the CH340, find the UART
TX/RX into the transceiver, then the D pin to the servo port. Mark the trace map on a
photo; it becomes your adapter block diagram (`[VERIFIED]`-level evidence).

## 9.4 Communication capture (logic analyzer)

Setup: 3 channels — **D** (servo port), plus V and G for reference. LA sample rate
≥ 4 MS/s (1 Mbps × 4) — any 24 MHz Saleae-class clone suffices.

Procedure:
1. Trigger on D rising edge.
2. Run `bench.py ping` / `read` / `move` — capture tx+rx in one window.
3. Decode 8N1 async at 1 000 000 baud; verify header `FF FF`, ID, length, checksum.
4. Match your captured bytes against ch05 §5.4-5.6. Any mismatch = your mental model
   must change, not the scope.

Bonus: capture a full LeRobot session to watch `sync_write` (0x83) and `sync_read`
(0x92) frame shapes and the bus turnaround timing.

## 9.5 Oscilloscope work

Where a LA shows *which* bits, the scope shows *how* the line behaves:
- rise/fall times and levels at 1 Mbps (ringing → stub/termination issues; a long loom
  to the arm is your worst stub),
- turnaround gap between tx and rx (protocol manual implies ≥1 char),
- voltage during multi-servo motion (power sag = scope on V pin, ch03 §3.3).

## 9.6 Firmware exploration

- **Adapter:** the USB-serial bridge is **CH340-class** per Waveshare FAQ — however, the
  public schematic's pin labels (`A1/B12`, `VBUS`, `A4/B9`) hint at a small MCU (e.g.
  STM32-class) in the control path, and LeRobot's *reference* board enumerates as CDC
  `ttyACM`. Firm truth: the FAQ confirms **no user-facing firmware to flash**, but
  whether your board has a programmable MCU between the CH340 and the bus must be
  decided by teardown/IC-ID — `[BENCH-CHECK]`, do **not** assert either way yet.
- **Servo:** Feetech publishes **no** servo firmware; the *registers* are the
  interface (ch05 §5.6). Reconstructing beyond the datasheet = reading every
  version/status register (0x00–0x04, 0x41, 0x42) on your units and correlating with
  behavior. Treat firmware *revision differences* as a debugging axis (ch08 §8.7).
- **LeRobot:** fully open — read `lerobot/motors/feetech/` in your installed checkout;
  that's the authoritative description of what the host does on the wire.

## 9.7 CAN analyzers — explicitly out of scope

No CAN node exists on the SO-101 (ch05 §5.1). CAN analyzers, `candump`, SocketCAN
`can0` and CAN terminators belong to your DAMIAO DM-J4310 bench (`~/Desktop/motor/
damiao-j4310-bringup`). Using one on the SO-101 bus will not work and may load the
line — don't.

## 9.8 Confirmed vs hypothesis ledger (current state)

| Claim | Status | Evidence |
|---|---|---|
| Adapter bridge chip | CH340-class (USB-serial) | `[VERIFIED]` | Waveshare FAQ |
| Adapter has no programmable MCU | — | `[INFERRED]`/`[BENCH-CHECK]` | FAQ says no user firmware; schematic hints at MCU — verify by IC-ID |
| No fuse on adapter | `[INFERRED]` | schematic (no fuse part found); confirm with scope-on-fault test later |
| Servo MCU identity | `[UNKNOWN]` | not documented; needs teardown |
| Encoder IC identity | `[UNKNOWN]` | needs teardown |
| 0x41 bit mapping | `[INFERRED]` | community memory table; bench-verify by forcing faults |
| SYNC-READ (0x92) | `[INFERRED]` | seen in LeRobot traffic; confirm on your unit |

## 9.9 Suggested teardown experiments (order)

1. Adapter schematic walkthrough vs your board (an afternoon, no risk).
2. D-line LA capture of ping/read/move (an hour).
3. Scope capture of a 6-motor LeRobot session (sag + turnaround).
4. Servo teardown + block-level tracing (careful, PA+GF case; gear train is fiddly —
   photograph before removing anything).