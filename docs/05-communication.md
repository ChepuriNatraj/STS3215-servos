# Chapter 5 — Communication

> The SO-101's entire communication stack is: **USB → (CH340-class bridge) → one TTL
> half-duplex wire → six servos addressed by ID**. There is no CAN, no Ethernet, no
> RPC on the arm. This chapter gives you the byte-level protocol so you can talk to
> motors with nothing but a serial terminal.

## 5.1 Stack layers

```
┌─────────────────────────────────────────────────────────────────┐
│ APPLICATION   LeRobot SO101Follower / your script               │
├─────────────────────────────────────────────────────────────────┤
│ LOGICAL       Feetech Serial Bus Smart Servo protocol (frames)  │
├─────────────────────────────────────────────────────────────────┤
│ TRANSPORT     host serial port, 8N1 @ 1 000 000 baud            │
├─────────────────────────────────────────────────────────────────┤
│ PHYSICAL      USB-C (host↔adapter) → TTL D wire (adapter↔servo) │
│               half-duplex, idle-low, 2–5 V high / 0–0.45 V low  │
└─────────────────────────────────────────────────────────────────┘
```

## 5.2 USB layer

- Adapter enumerates as a standard serial device (CH340-class → `/dev/ttyUSB*`;
  some boards CDC → `/dev/ttyACM*`). `[BENCH-CHECK]` which on your unit.
- Nothing exotic: LeRobot and `pyserial` open it like any serial port.
- Permissions: `sudo usermod -aG dialout $USER` (then re-login) or
  `sudo chmod 666 /dev/ttyUSB0` for a quick session.

## 5.3 Bus physical layer

- Single wire **D**, **half-duplex**: the adapter cannot receive while transmitting,
  and servos only talk when addressed. Line turnaround is implicit — wait for your own
  frame's stop bits, then listen.
- 8 data bits, no parity, 1 stop bit. 10 bits per byte ⇒ **100 µs per 10 bytes** at
  1 Mbps.
- Idle level low; frame pulses high. Voltages: high 2–5 V, low 0–0.45 V (`[VERIFIED]`
  datasheet §11) — a 3.3 V host UART is directly compatible.

## 5.4 Frame formats (all `[VERIFIED]` from the protocol manual)

**Instruction packet:**

```
0xFF  0xFF  ID   Length   Instruction  Param1 ... ParamN   Checksum
```

- `0xFF 0xFF` — sync header (two consecutive 0xFF).
- `ID` — 0x00–0xFD (0–253); **0xFE = broadcast** (no reply, except PING);
  ID 254/255 reserved (`[INFERRED]` from manual: 254 broadcast, 255 unused).
- `Length` = N + 2 (parameters + 2).
- `Instruction` — see table below.
- `Checksum` = ~( ID + Length + Instruction + ΣParam ) low byte.

**Reply packet (from servo):**

```
0xFF  0xFF  ID   Length   ERROR   Param1 ... ParamN   Checksum
```

- `ERROR` — 0 = no error; non-zero = fault bits (see §5.7).

**Instruction set:**

| Cmd | Byte | Params | Purpose |
|---|---|---|---|
| PING | 0x01 | — | status query |
| READ | 0x02 | addr, len | read memory table |
| WRITE | 0x03 | addr, data… | write memory table |
| REG-WRITE | 0x04 | addr, data… | write, execute on ACTION |
| ACTION | 0x05 | — | execute REG-WRITE |
| RESET | 0x06 | — | restore EPROM defaults |
| SYNC-WRITE | 0x83 | addr, L, id1, data…, id2, data… | multi-servo write, broadcast |
| SYNC-READ | 0x92 | addr, L, ids… | multi-servo read (`[INFERRED]` — community firmware; verify) |

## 5.5 Worked examples (checksums verified by hand)

**PING servo 1:**
```
FF FF 01 02 01 FB        checksum = ~(01+02+01) = ~0x04 = 0xFB
reply:  FF FF 01 02 00 FC   → ERROR=0, healthy
```

**READ current position (addr 0x38, 2 bytes) of servo 1:**
```
FF FF 01 04 02 38 02 BE   checksum = ~(01+04+02+38+02)=~0x41=0xBE
reply:  FF FF 01 04 00 18 05 DD   → position = 0x0518 = 1304 steps (L,H order)
```

**WRITE ID → 1 (broadcast, EEPROM unlocked first — see §5.6):**
```
FF FF FE 04 03 05 01 F4   checksum = ~(FE+04+03+05+01)=~0x0B=0xF4
(no reply: broadcast)
```

**Move servo 1 to position 2048, speed 1000, time 0 (write 6 bytes @0x2A):**
```
FF FF 01 09 03 2A 00 08 00 00 E8 03 D5
   address 0x2A → target 0x0800 (2048, L,H)
   address 0x2C → time   0x0000
   address 0x2E → speed  0x03E8 (1000)
checksum = ~(01+09+03+2A+00+08+00+00+E8+03) = ~0x2A = 0xD5
reply: FF FF 01 02 00 FC (accepted, executing)
```

**Enable/disable torque (write 1 / 0 @0x28, ID=1):**
```
FF FF 01 04 03 28 01 CE   torque ON  checksum=~(01+04+03+28+01)=~0x31=0xCE
FF FF 01 04 03 28 00 CF   torque OFF  checksum=~(01+04+03+28+00)=~0x30=0xCF
```

> ⚠️ Two-byte registers are **low byte first** (L,H) on STS3215 — unlike the older SCS
> series (H,L). The protocol manual's example (0x0518 read back for position 1304) is
> the canonical proof. Always cross-check an address against the memory table §5.6
> before writing.

## 5.6 STS3215 memory table (bring-up subset)

Full source: `datasheets/` + [Mowibox sts3215 memory table](https://github.com/Mowibox/stm32-sts3215-lib) (V3.6);
cross-checked against datasheet hints ("address 40 → value 128 = set mid-point" ⇒ 0x28).

| Addr | Name | Bytes | R/W | Notes (units) |
|---|---|---|---|---|
| 0x05 | ID | 1 | RW/EPROM | 0–253, unique per bus |
| 0x06 | Baud rate | 1 | RW/EPROM | 0=1M,1=500k,2=250k,3=128k,4=115200,5=76800,6=57600,7=38400 |
| 0x07 | Return delay | 1 | RW/EPROM | 2 µs units |
| 0x08 | Response level | 1 | RW/EPROM | 0=only READ/PING reply; 1=all reply |
| 0x09/0x0B | Min/Max angle limit | 2 | RW/EPROM | 0–4095 steps |
| 0x0D | Max temp | 1 | RW/EPROM | °C, default 70 |
| 0x0E/0x0F | Max/Min voltage | 1 | RW/EPROM | 0.1 V units (default 80 → 8.0 V, 40 → 4.0 V) |
| 0x10 | Max torque | 2 | RW/EPROM | 0–1000 (1000 = 100 % of max) |
| 0x13 | Unloading condition | 1 | RW/EPROM | bitfield: which faults unload |
| 0x15/16/17 | P/D/I coefficients | 1 | RW/EPROM | position PID |
| 0x1C | Protection current | 2 | RW/EPROM | 6.5 mA/unit (default 500 ≈ 3.25 A) |
| 0x21 | Operation mode | 1 | RW/EPROM | 0=position, 1=speed c.l., 2=PWM o.l., 3=step |
| 0x22/23/24 | Prot. torque/time/overload-torque | 1 | RW/EPROM | % (0x24: 80 = 80 % stall) / 10 ms / % |
| 0x28 | Torque switch | 1 | RW/SRAM | 0=off (default), 1=on, **128=set current pos to 2048** |
| 0x29 | Acceleration | 1 | RW/SRAM | 100 step/s² units |
| 0x2A | Target position | 2 | RW/SRAM | steps, −32766…32766 |
| 0x2C | Running time | 2 | RW/SRAM | 0.001 s units |
| 0x2E | Running speed | 2 | RW/SRAM | steps/s — official manual example writes 1000; community table max 254 (`[BENCH-CHECK]` full scale) |
| 0x30 | Torque limit | 2 | RW/SRAM | 0–1000 (1000 = 100 % of max); RAM copy of 0x10 |
| 0x37 | Lock mark | 1 | RW/SRAM | 1 = EPROM writes not persisted |
| 0x38 | Current position | 2 | RO | steps, L,H |
| 0x3A | Current speed | 2 | RO | steps/s |
| 0x3C | Current load | 2 | RO | 0.001 of max torque |
| 0x3E | Current voltage | 1 | RO | 0.1 V units |
| 0x3F | Current temperature | 1 | RO | °C |
| 0x41 | Servo status | 1 | RO | fault bits (bit0…: voltage, temperature, current, angle, overload — order per table) |
| 0x42 | Mobile sign | 1 | RO | 1 = moving |
| 0x45 | Current current | 2 | RO | 6.5 mA units |

**EEPROM write discipline (critical):** EPROM values persist across power cycles only
when the **lock mark (0x37) is 0**. Default is unlocked, but after any prior session,
check: write 0x37=0 before changing ID/baud/limits. Procedure: write lock off → write
param → power-cycle → read back to confirm.

## 5.7 Status / fault byte (0x41)

`[INFERRED]` bit assignment (community table, consistent with protection list):
bit0 = over-voltage, bit1 = over-temperature, bit2 = over-current, bit3 = angle/encoder,
bit4 = overload. Treat non-zero as "protection latched": a **new position command**
clears load/current latches; voltage/temp clear automatically.

## 5.8 Command trace — PC to motor and back (one full round trip)

Goal: read current position of shoulder_pan (ID 1).

```
[LeRobot/pyserial]             [adapter]              [STS3215 #1]
      │  bytes over USB ───────►│  D wire pulses ─────►│
      │   FF FF 01 04 02 38 02 BE                       │ decode, checksum ok,
      │                          │                      │ read SRAM 0x38-0x39
      │  ◄──── reply ────────────│◄──── reply ──────────│ FF FF 01 04 00 18 05 DD
      │  position = 0x0518 = 1304                       
```

Total latency ≈ frame send (10 bytes ≈ 100 µs) + servo processing (1 ms update class)
+ reply (≈ 100 µs). For control loops, expect **~1–2 ms per single read/write
round-trip** and use SYNC-WRITE for multi-joint commands (`[INFERRED]` timing).

## 5.9 Device discovery

```bash
# what serial devices exist
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null

# LeRobot's helper — unplug each arm when asked, to map port → arm
lerobot-find-port

# raw PING from a Python one-liner (pyserial)
python3 - <<'EOF'
import serial
s = serial.Serial("/dev/ttyUSB0", 1000000, timeout=0.1)
s.write(bytes.fromhex("FF FF 01 02 01 FB"))
print(s.read(16).hex(" "))
EOF
```

Expected: `ff ff 01 02 00 fc` when servo ID 1 is present (all others silent).
PING ID 0xFE broadcasts — every servo answers → works as a bus census.

## 5.10 Common communication mistakes

| Mistake | Symptom | Fix |
|---|---|---|
| Wrong baud (e.g. 115200) | garbled/no replies | set 1 000 000 |
| Half-duplex violation (echo disabled / immediate listen) | read your own frame as reply | wait for turnaround (≥ 1 char gap) |
| Checksum errors | servo ignores frame silently | compute per §5.4 |
| Broadcast PING | chaos / bus collision on multi-servo | PING 0xFE only on a 1-servo bus |
| EEPROM locked | ID change "works" then reverts | 0x37=0 first |
| Byte-order swap | absurd position readbacks | L,H order on STS3215 |
| tty permissions | SerialException: could not open | dialout group / chmod |