# Bench log template

Fill one run per session. Copy to `logs/<date>-<experiment>.md` (gitignored).

## Session meta

- **Date / time:** 
- **Operator:** 
- **Repo commit:** `git rev-parse --short HEAD`
- **Test article:** servo serial/marking: 
- **Adapter serial/node:**  (e.g. `/dev/ttyUSB0`, `[BENCH-CHECK]`)
- **PSU:** voltage set ____ V · current limit ____ A · output on/off
- **Ambient temp:** ____ °C

## Pre-checks (gate G0–G2)

| Check | Result | Notes |
|---|---|---|
| Servo marking matches C001 7.4 V | ok / fail | |
| Pigtail continuity V/G/D | ok / fail | |
| D–V / D–G shorts | open / short | |
| PSU polarity at port | correct / reversed | |

## Gate results

| Gate | Command | Expected | Actual | Pass |
|---|---|---|---|---|
| G3 power | PSU 7.40 V on, limit 2 A | 7.40±0.05 V | ____ V | ☐ |
| G4 USB | `dmesg`/`ls` | tty node | | ☐ |
| G5 ping | `bench.py ping --id 1` | FF FF 01 02 00 FC | | ☐ |
| G6 read | `bench.py read --id 1` | table ch07 | see below | ☐ |
| G7 torque | `bench.py torque on` | stiff + load ↑ | | ☐ |
| G8 move | `bench.py move --delta 180` | monotonic pos | | ☐ |
| G9 velocity | `bench.py mode 1` + `speed` | rotates @ cmd rate | | ☐ |
| G10 current | read 0x45 | ~150 mA @7.4 V free | | ☐ |
| G11 estop | soft + hard kill | limp / V=0 | | ☐ |

## G6 telemetry snapshot

```
position 0x____ (____ steps)   voltage ____ V   temp ____ C
load ____/1000   speed ____   status 0x____   current ____ mA
```

## Anomalies / notes

(timestamped entries; every non-pass row must get a row in docs/08-debugging mapping)

## Sign-off

- [ ] torque left OFF
- [ ] PSU output OFF, leads disconnected
- [ ] session logged back into `docs/00-hardware-inventory.md` open questions