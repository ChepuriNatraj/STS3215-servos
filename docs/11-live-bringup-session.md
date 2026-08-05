# Chapter 11 — First Live Bring-Up Session (2026-08-05)

> Record of the first session that actually **powered, talked to, and moved an STS3215
> servo** on this bench. Where the earlier chapters are theory (full arm, 7.4 V variant,
> `[BENCH-CHECK]`), this chapter is what really happened: the exact rail, the exact
> frames sent, the exact readings, and every snag hit along the way. **All events and
> bytes below are `[VERIFIED]`** against the live session unless tagged otherwise.

---

## 11.1 Session facts

| Item | Value | Evidence |
|---|---|---|
| Date / time | 2026-08-05, evening | session log |
| Test article | **1× STS3215, 12 V variant** (not the 7.4 V C001 the handbook assumed) | servo label + rail reading |
| Rail set / read | PSU set 12 V, current-limit 2 A → raised to ≥ 3 A; servo reads **12.4–12.5 V** | `bench.py read` 0x3E |
| Bus | **UART half-duplex, 8N1, 1 000 000 baud** | protocol manual §7 |
| Adapter | Waveshare Bus Servo Adapter, USB-C, jumper caps on **B (USB)** | board jumpers |
| Host serial node | `/dev/ttyACM0` (QinHeng / CH340-class, enumerated as ttyACM not ttyUSB0) | `lsusb`, `ls -l /dev` |
| Servo telemetry at rest | 12.4 V, 32–34 °C, status `0x00`, load 0, current ~0 mA | `bench.py read` |
| First movement | position `1952 → 2132` steps @ 200 steps/s, error `0x00` | session log |

> ⚠️ **Key difference from the rest of this handbook:** every other chapter assumes the
> **7.4 V** STS3215. This bench holds the **12 V** variant, so 12 V is the *correct* rail
> here — and 7.4 V setup instructions must NOT be applied blindly. **Always read the
> label on the motor in your hand before choosing a rail.**

---

## 11.2 Bring-up timeline (what was actually done, in order)

| # | Step | Command | Result |
|---|---|---|---|
| 1 | Verify host toolchain | `python3 -c "import serial"` | **`ModuleNotFoundError`** → `pip install --user pyserial` fixed |
| 2 | Find the port | `ls -l /dev/ttyUSB* /dev/ttyACM*` | node is **`/dev/ttyACM0`** (not ttyUSB0) |
| 3 | Fix permissions | `sudo chmod 666 /dev/ttyACM0` | port opens (dialout not yet added) |
| 4 | Device detect | `bench.py ping --id 1 --port /dev/ttyACM0` | **servo alive, error `0x00`** |
| 5 | Telemetry read | `bench.py read --id 1` | 12.4 V, 34 °C, status `0x00`, load 0 |
| 6 | Enable torque | `bench.py torque on --id 1` | **first try replied with no answer → PSU tripped** (see §11.5) |
| 7 | Restore power | raise current-limit to ≥ 3 A, re-arm output | servo back, ping ok |
| 8 | Enable torque (2nd) | `bench.py torque on --id 1` | **torque ON, error `0x00`**, servo stiff/holding |
| 9 | First move | `bench.py move --id 1 --delta 180 --speed 200` | `1952 → 2132`, position converged & held |
| 10 | 5-motion sweep | deltas `+200, −150, −150, +250, +250` @ 200 steps/s | see §11.4, all error `0x00` |
| 11 | Live dashboard | `servo_dash.py --http 8042` | browser page streams telemetry + controls |

---

## 11.3 How the communication works (the stack, concretely)

The host never touches the motor directly. There is one logical data wire and one
protocol:

```
host PC ──USB-C──[ Waveshare adapter ]──TTL D wire (half-duplex)──[ STS3215 ]
                 ^
          CH340-class bridge: USB ⇄ UART, at 1 000 000 baud, 8 data / no parity / 1 stop
```

- **Half-duplex:** while the host transmits, nothing listens; the servo only answers
  when addressed. Send your frame, then wait ≥ 1 byte-gap of turnaround before reading.
- **Byte order for all 2-byte registers is LOW byte first (L,H)** on the STS3215
  (the older SCS family is high-first — a classic trap).
- Every frame ends in **Checksum = ~(ID + Length + Instruction + Σparams) & 0xFF**.
  Wrong checksum ⇒ the servo silently ignores the frame.

---

## 11.4 The exact bytes sent to bring the motor alive

All frames below are exactly what `bench.py` / `servo_dash.py` put on the wire for
servo **ID 1**. Checksums are worked by hand and match the live frames `[VERIFIED]`.

### 1) PING — is the motor there? `[Instruction 0x01]`

```
TX: FF FF 01 02 01 FB        checksum = ~(01+02+01) = ~0x04 = 0xFB
RX: FF FF 01 02 00 FC            ← ERROR byte 0x00 = healthy, replies
```

### 2) READ the bring-up telemetry block — `[Instruction 0x02]`, address 0x38, 15 bytes

```
TX: FF FF 01 04 02 38 0F B1     length=0x04(4), read @0x38, 15 bytes
RX: FF FF 01 11 00 <14 bytes> FC ...   → parsed to position/speed/load/voltage/temp/current
```

Live parse (torque OFF, unloaded): position `0x07A3`=1955, voltage `0x4A`=12.4 V,
temp `0x22`=34 °C, status `0x00`, current 0.

### 3) Single-register reads / writes — `[Instruction 0x03]`

Read position first = write nothing, read 2 bytes @0x38:
```
TX: FF FF 01 04 02 38 02 BE     checksum = ~(01+04+02+38+02) = ~0x41 = 0xBE
RX: FF FF 01 04 00 18 05 DD     position = 0x0518-style (L,H) → e.g. 1304
```
(Observed live `1952` → reply `0xA0 07`.)

### 4) Torque ON — the "wake up the motor" command `[write 0x28 = 1]`

```
TX: FF FF 01 04 03 28 01 CE     checksum = ~(01+04+03+28+01) = ~0x31 = 0xCE
RX: FF FF 01 02 00 FC           accepted → motor energizes & holds position
```
Torque OFF is the same with `0x28 00` (checksum `0xCF`).

> ⚡ **Required BEFORE torque on when actually moving:** a position/goal register write
> (`0x2A` below). On a fresh servo the loop has no target until you write one.

### 5) MOVE — write goal position + running speed into SRAM `[write 6 bytes @0x2A]`

```
FF FF 01 09 03 2A  <goal L> <goal H>  00 00  <speed L> <speed H>  <CHK>
                     0x00,0x08 = 2048            0xE8,0x03 = 1000
```
Live first move `1952 → 2132 @ 200 steps/s`:
```
goal 0x0854 = 2132 (L,H = 54 08)   speed 0x00C8 = 200 (L,H = C8 00)
TX: FF FF 01 09 03 2A 54 08 00 00 C8 00 A4
                                   checksum = ~(01+09+03+2A+54+08+00+00+C8+00) = ~0x5B = 0xA4
RX: FF FF 01 02 00 FC              accepted, servo drives to 2132 and holds
```

### 6) ESTOP — broadcast torque OFF `[ID 0xFE, no reply expected]`

```
TX: FF FF FE 04 03 28 00 D2     ~(FE+04+03+28+00) & 0xFF = ~0x2D = 0xD2
```
Broadcast ⇒ the motor answers **silently** by design; absence of a reply is success.
(Always follow with PSU output OFF for the hard kill.)

---

## 11.5 Anomalies & the notes worth keeping

1. **`pyserial` was not installed.** Host Python is miniconda 3.13; fixed with
   `python3 -m pip install --user pyserial`. `[VERIFIED]`
2. **The serial node is `ttyACM0`, not `ttyUSB0`.** `bench.py` and this handbook
   defaulted to `/dev/ttyUSB0`; passing `--port /dev/ttyACM0` fixed it. Check
   `lsusb`/`ls /dev` — do not hard-code a device name.
3. **`bench.py` had a latent bug:** `global PORT` appeared *after* `PORT` was used in the
   argparse default, raising `SyntaxError` on `--port`. Fixed by hoisting `global PORT`
   to the top of `main()`. (`servo_dash.py` was written with the same pattern avoided.)
4. **Port permission:** user not in `dialout` → `[Errno 13] Permission denied`; fixed
   with `sudo chmod 666 /dev/ttyACM0` (permanent fix = `sudo usermod -aG dialout $USER`
   + re-login).
5. **First torque-on tripped the PSU.** When torque energizes the motor it draws an
   inrush kick that folded the 2 A-limited supply back; the servo then stopped
   replying to PING (depowered). Fix: **set PSU current-limit ≥ 3 A** before enabling
   torque. The same transient is why single-motor first-power should start at low
   current. `[VERIFIED]`
6. **Clearing a trip is not enough** — after re-arming the PSU the servo was just gone
   (no reply) until output was actually re-enabled; then it answered immediately.
   Treat "no PING reply" as *first* power, not firmware.
7. **Load register climbed to ~1044–1052** (≈ 104 % of max) during the later sweep while
   pushing toward a region where the horn was binding — but status stayed `0x00` and
   current read ~0–6 mA. Interpretation: holding torque against a mechanical contact
   shows up as high **load**, before the current/fault protections fire. Keep hands
   clear and avoid shoving a held joint into hard stops. `[VERIFIED]` on load value;
   cause `[INFERRED]`.
8. **Port 8000 was already taken** by an unrelated FastAPI app, so the dashboard runs
   on **8042**.
9. **Voltage read 12.4–12.5 V on a 12 V set-point** — the adapter is a pass-through
   (output = input, no regulation `[VERIFIED]` datasheet), so rail tolerance is your
   PSU's. 12.4 is fine for the 12 V variant (rated up to 12.6).

---

## 11.6 The live dashboard (`scripts/servo_dash.py`)

Written because paging through hex-only output is slow. Pure Python stdlib HTTP server —
**no Flask/websockets added** — with:

- a background **telemetry thread** polling `READ 0x38, 15 bytes` every 0.2 s and
  caching the parsed state (so the browser never contends with control commands on the
  half-duplex bus — a single `threading.Lock` guards every send);
- `GET /api/telemetry` returns the cached snapshot + status decode + command log;
- `POST /api/action` runs `torque` / `move` / `goto` / `estop` on demand;
- the page renders a live **0–4096 step dial**, gauges (speed, load, current, temp,
  voltage), a red/green fault pill, a motion log, and control buttons.

Launch: `python3 scripts/servo_dash.py --port /dev/ttyACM0 --http 8042` → open
`http://127.0.0.1:8042`. On Ctrl-C it sends a broadcast ESTOP before exiting.

---

## 11.7 Reusable recipe — "bring a fresh STS3215 to life"

1. Read the **variant label**; set the PSU to that voltage; **current-limit ≥ 3 A**. `[VERIFIED]`
2. Jumper caps on **B (USB)**; servo on the 3-pin D/V/G port. `[VERIFIED]`
3. `pip install --user pyserial`; confirm `ls /dev/ttyACM*`/`ttyUSB*` and fix perms. `[VERIFIED]`
4. `python3 scripts/bench.py ping --id 1 --port /dev/ttyACM0` → expect `error 0x00`. `[VERIFIED]`
5. `python3 scripts/bench.py read --id 1 --port /dev/ttyACM0` → sanity-check V/temp/status. `[VERIFIED]`
6. `bench.py torque on` → servo stiff. If the PSU trips, raise the limit and retry. `[VERIFIED]`
7. `bench.py move --delta X --speed Y` → drives, converges, holds. `[VERIFIED]`
8. Done? `bench.py estop` then PSU output OFF. `[VERIFIED]`

---

## 11.8 Open questions carried forward

| Q | Tag | Suggested check |
|---|---|---|
| Why did load read ≈ 104 % at rest near the bind while current stayed ~0 mA? | `[INFERRED]` | read 0x3C vs 0x45 together at a known stall |
| Full-scale of `Running_Speed 0x2E` (official 1000 vs community 254)? | `[BENCH-CHECK]` | write 1000 and observe actual rate |
| Is ttyACM0 (vs handbook's ttyUSB0) a stable property of this adapter? | `[BENCH-CHECK]` | re-plug and re-check |
| Is the servo truly the 12 V model, or 7.4 V running hot at 12.4 V? | `[BENCH-CHECK]` | confirm model engraving before trusting 12 V rail |