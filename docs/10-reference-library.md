# Chapter 10 — Reference Library

> Every source with URL + retrieval date. Prefer official/primary sources; community
> sources are flagged. "Not found" rows are deliberately recorded so nobody re-searches
> them.

## 10.1 Official documentation (offline copies in `datasheets/`)

| Doc | Source | Retrieved | Copies |
|---|---|---|---|
| STS3215 Product Specification (7.4 V 19 kg·cm, C001, ed. A/0 2020-04-10) | Shenzhen Feetech | 2026-08-04 | `datasheets/STS3215_datasheet.pdf` (+.txt) |
| Serial Bus Smart Control servo Communication Protocol Manual V1.01 (2019-02-19) | Feetech (mirror: Seeed) | 2026-08-04 | `datasheets/Feetech_Serial_Bus_Servo_Protocol_Manual.pdf` (+.txt) |
| Bus Servo Adapter (A) Schematic | Waveshare | 2026-08-04 | `datasheets/Bus_Servo_Adapter_A_Schematic.pdf` |
| Bus Servo Adapter (A) wiki: [product](https://www.waveshare.com/bus-servo-adapter-a.htm) / [wiki](https://www.waveshare.com/wiki/Bus_Servo_Adapter_(A)) / [FAQ](https://docs.waveshare.com/Bus_Servo_Adapter_A/FAQ) | Waveshare | 2026-08-04 | — |
| LeRobot SO-101 assembly/config docs | [huggingface.co/docs/lerobot/en/so101](https://huggingface.co/docs/lerobot/en/so101) | 2026-08-04 | — |
| LeRobot installation guide | [huggingface.co/docs/lerobot/installation](https://huggingface.co/docs/lerobot/en/installation) | 2026-08-04 | — |

## 10.2 Hardware / BOM / CAD

- **SO-101 / SO-ARM100 upstream**: [github.com/TheRobotStudio/SO-ARM100](https://github.com/TheRobotStudio/SO-ARM100) (CAD, STL, BOM; Apache 2.0) — retrieved 2026-08-04
- Your CAD mirror: Onshape doc 7715cc284bb430fe6dab4ffd (linked from `so101_core.urdf`)
- Your sim stack: `~/Desktop/s101` (URDF, MoveIt, Gazebo — commit 83be3ec)

## 10.3 Software / SDK

- [huggingface/lerobot](https://github.com/huggingface/lerobot) — `src/lerobot/robots/so_follower/`, `src/lerobot/motors/feetech/`, `pyproject.toml` (`feetech` extra = `feetech-servo-sdk>=1.0.0,<2.0.0`)
- [Mowibox/stm32-sts3215-lib](https://github.com/Mowibox/stm32-sts3215-lib) — protocol manual + STS3215 memory table V3.6 (community; cross-checked vs datasheet)
- Feetech SDK / tools: via LeRobot extra; direct vendor SDK mirrors exist (feetechrc.com) — verify before use
- ROS 2 (your path): `so101_description` + `so101_moveit_config` in `~/Desktop/s101/ros2_ws/src`

## 10.4 Academic & lecture material (concepts the handbook leans on)

- UART/serial fundamentals: *Digital Design and Computer Organization* (or any
  "serial communication" lecture set) — framing 8N1, baud, half-duplex turnaround
- Embedded sensor: magnetic rotary encoding (12-bit absolute) — vendor app notes
  (AS56xx/TLE50xx class) for principle
- Bus electrical: single-wire half-duplex topologies, stub/termination basics —
  *High-Speed Digital Design* (Howard Johnson) ch. on transmission lines
- (GATE RA prep tie-in: this whole repo is exercise for GATE 1 — Networks & Sensors,
  and GATE 3 — Embedded/Signals: half-duplex framing, encoder resolution, checksum
  arithmetic, timing budgets.)

## 10.5 YouTube / video (retrieved-2026-08-04, verify)

- LeRobot SO-101 setup videos (motor IDs, calibration) — embedded in the LeRobot docs
  page above (official, preferred)
- Feetech STS3215 evaluation video: [feetechrc.com 2020-05-13 post](https://www.feetechrc.com/2020-05-13_56655.html) — four operating modes demo

## 10.6 Example projects to read

- LeRobot's `examples/` (control your robot tutorial) — in your installed checkout
- Waveshare adapter demos (pyserial ping/read) — vendor wiki §"Demo"
- Community builds: Hugging Face Discord (SO-101 channel) for field experience
- This repo's own `scripts/bench.py` + `logs/` — your field notebook

## 10.7 Explicitly not found (avoid re-searching)

| Sought | Status |
|---|---|
| Official STS3215 memory-table PDF from Feetech (standalone) | not found 2026-08-04; only datasheet + community V3.6 table |
| Official SO-101 schematic (arm-level) | not published; arm is loom + servos (ch04) |
| Waveshare adapter user firmware / flashing | not applicable (CH340 bridge) |
| LeRobot C++ SDK for SO-101 | none (Python only) |

## 10.8 Citation hygiene

When adding a source: add the URL, retrieval date, and what it *proved* to
`docs/00-hardware-inventory.md` §3. Offline copies of primary PDFs live in
`datasheets/`. Don't link a source you haven't actually opened.