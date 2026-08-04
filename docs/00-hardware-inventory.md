# Chapter 0 — Hardware Inventory & Evidence Register

> **Purpose:** a verified, item-by-item inventory of the SO-101 electronics on the
> bench, and the single place that tracks the confidence behind every fact used later
> in the handbook. Update this file as you (re)confirm items; every `[BENCH-CHECK]`
> in the rest of the handbook should eventually resolve into a `[VERIFIED]` row here.

## 1. Verified platform facts (independent of the physical unit)

These were established from official sources on 2026-08-04 and are the load-bearing
facts the handbook is built on.

| # | Fact | Value | Evidence |
|---|---|---|---|
| F1 | Robot identity | SO-101 follower arm (The Robot Studio × Hugging Face LeRobot), 6-DOF + gripper | [LeRobot SO-101 docs](https://huggingface.co/docs/lerobot/en/so101) |
| F2 | Motor model | Feetech STS3215, 7.4 V 19 kg·cm, ST-3215-C001, gear ratio 1/345 | `datasheets/STS3215_datasheet.pdf` (edition A/0, 2020-04-10) |
| F3 | Motor bus physical layer | TTL half-duplex asynchronous serial, 8N1, single signal wire | datasheet §7-2 |
| F4 | Baud rate | 38400 – 1 Mbps, **factory default 1 Mbps** | datasheet §7-4 |
| F5 | Protocol | Feetech Serial Bus Smart Servo protocol (PING/READ/WRITE/SYNC-WRITE) | `datasheets/Feetech_Serial_Bus_Servo_Protocol_Manual.pdf` |
| F6 | Position feedback | 12-bit magnetic encoder, 360° over 0–4096 units, 0.088°/unit | datasheet §6-6, §7-7, §7-8 |
| F7 | Operating voltage (this variant) | **4 V – 7.4 V** (typ. 6 V / 7.4 V) | datasheet §5-7, §5-1 |
| F8 | Stall current | 2 A @6 V, 2.5 A @7.4 V | datasheet §5-5 |
| F9 | Connector on servo | `5264-3P`, 3 pin: 1 = GND, 2 = Vcc, 3 = Signal/TTL; ~15 cm pigtail | datasheet §6-7 |
| F10 | Adapter | Waveshare Bus Servo Adapter (A): USB-C + DC5521 + screw terminal, jumper A/B, no onboard regulation | Waveshare wiki + product page |
| F11 | Adapter power label | 9–12.6 V for ST servos; docs also accept 5–8.4 V — **must match servo voltage** | Waveshare wiki FAQ |
| F12 | Adapter jumpers for USB host | two jumper caps on **B** | LeRobot SO-101 docs |
| F13 | Motor IDs | shoulder_pan = 1 … gripper = 6 (board also drives id 2048 as neutral start) | LeRobot docs §set motors ids |
| F14 | Host | Ubuntu 24.04.4 LTS, x86_64, Python 3.12.3 | observed 2026-08-04 |
| F15 | Host serial device | none present on 2026-08-04 → everything downstream is `[BENCH-CHECK]` | observed |

## 2. Unit inventory — confirm on your bench

Check each row on **your** arm. Ticking a box promotes the row to `[VERIFIED]` and you
can note details (revision string, serial, measured quirks) alongside.

| [ ] | Item | Qty | How to verify | Notes |
|---|---|---|---|---|
|   | STS3215 bearing stains on servo bodies 1–6 (matching IDs 1–6) | 6 | Power one motor at a time using `docs/07`; read address 0x05 (ID) | Record each servo's factory ID before setup |
|   | Waveshare Bus Servo Adapter (A) present in base | 1 | Visual; 42×33 mm board | Confirm revision letter / board print |
|   | Jumper caps on **B** channel | 2 | Visual, adapter silk | LeRobot says both caps to B for USB |
|   | DC5521 jack wired to bench PSU | 1 | Follow PSU rules in ch03 | Polarity check with meter |
|   | USB-C data cable host ↔ adapter | 1 | `dmesg | tail` after plug; node in /dev | Charge-only cables fail silently |
|   | 3-pin daisy-chain cables 1→2→3→4→5→6 | 5 | Inspect lock/tabs; continuity D/D V/V G/G | See ch04 wiring tables |
|   | Twist/gender — servo header to servo header |  | Match D/V/G order pin-for-pin | Colors may vary by batch |

## 3. Evidence register growth rules

- Each chapter may promote facts here. Keep the **#Fxx** ids stable once assigned.
- New `[BENCH-CHECK]` items discovered during a bench session **must** be added here
  with the date and the `logs/` entry that resolves (or fails to resolve) them.
- Do not delete rows; mark superseded facts `[SUPERSEDED]` instead (datasheet rev change,
  hardware swap, etc.), preserving history.

## 4. Open questions — current log

| Date | Question | Impact | Resolution needed |
|---|---|---|---|
| 2026-08-04 | Which `/dev/tty*` node does the Waveshare unit enumerate as on Ubuntu 24.04 (CH340→ttyUSB* vs CDC→ttyACM*)? | All scripts/port examples | `dmesg` after first USB plug-in |
| 2026-08-04 | Actual servo cable connector pitch/gender on this batch (5264-3P per datasheet; measure pitch with calipers) | ch04 pinout table | Caliper measurement + photo |
| 2026-08-04 | Actual PSU output voltage the user runs (recommend 7.4 V max for this variant) | ch03 power budget | Bench session |
| 2026-08-04 | Whether motor IDs already set to 1–6 (they ship ID=1). | ch07 setup step | First `setup_motors` run |