# STS3215 — Communication Protocol (EN Essentials)

**Source:** Feetech Serial Bus Smart Servo Communication Protocol Manual (V1.01, 2019-02-19)
**Applies to:** SCS series (TTL, single-bus) and SMS series (RS485). The STS3215 is an **SCS-series** servo.

---

## 1. Physical / Link Layer

| Parameter | Value |
|---|---|
| Topology | Single bus, half-duplex, time-multiplexed on one signal line |
| Wires | 3 (VCC, GND, Signal/TTL) |
| Frame format | 1 start bit, 8 data bits, 1 stop bit — **8N1, 10 bits total**, no parity |
| Baud rate | 38400 bps – 1 Mbps (default 1 Mbps) |
| IDs | 0–253 (0x00–0xFD); **0xFE = broadcast**; 0xFF reserved (header byte) |

> **SCS vs SMS byte order:** SCS sends two-byte values **low byte first, then high byte**. SMS does the opposite. The STS3215 follows the SCS convention.

---

## 2. Packet Structure

### 2.1 Instruction packet (controller → servo)

| Field | Size | Value |
|---|---|---|
| Header | 2 B | `0xFF 0xFF` (two consecutive 0xFF mark start of frame) |
| ID | 1 B | 0x00–0xFD, or 0xFE broadcast |
| Length | 1 B | **N + 2** (N = number of parameter bytes) |
| Instruction | 1 B | See §3 |
| Parameters | N B | Instruction-specific |
| Checksum | 1 B | `~ (ID + Length + Instruction + Param1 + … + ParamN)`, low byte of sum, then bitwise NOT |

### 2.2 Reply packet (servo → controller)

Same shape as instruction, but the byte after Length is **ERROR** (status):

| ERROR | Meaning |
|---|---|
| 0 | OK — no error |
| ≠ 0 | Error flag (see servo-specific memory table) |

For read instructions, the parameters carry the returned data.

---

## 3. Instruction Set

| Code | Name | Parameters | Function |
|---|---|---|---|
| `0x01` | PING | 0 | Query working status / presence |
| `0x02` | READ DATA | 2 | Read from control table (addr, length) |
| `0x03` | WRITE DATA | ≥1 | Write to control table (addr, data…) |
| `0x04` | REG WRITE | ≥2 | Write, but execute later on `ACTION` |
| `0x05` | ACTION | 0 | Trigger all pending REG WRITEs simultaneously |
| `0x06` | RESET | 0 | Reset control table to factory defaults |
| `0x83` | SYNC WRITE | ≥2 | Write the same block to multiple servos in one frame |

### 3.1 PING (`0x01`)

```
TX:  FF FF  ID  02  01  CHK
RX:  FF FF  ID  02  ERR CHK
```

Broadcast PING is allowed, but **do not** broadcast-PING with multiple servos on the bus (collisions).

### 3.2 READ DATA (`0x02`)

```
TX:  FF FF ID 04 02 [addr] [len] CHK
RX:  FF FF ID LEN 00 [data...] CHK
```

For two-byte values, **low byte is sent before high byte** (SCS order).

### 3.3 WRITE DATA (`0x03`)

```
TX:  FF FF ID (N+3) 03 [addr] [data...] CHK
RX:  FF FF ID 02 00 CHK      (no return on broadcast ID 0xFE)
```

> **EEPROM note:** the ID lives in EEPROM. If the lock switch in the control table is on, the new ID is **not persisted across power cycles** — unlock first, change, then optionally re-lock.

### 3.4 REG WRITE (`0x04`) + ACTION (`0x05`)

- REG WRITE stores the write in a buffer and sets a "registered" flag per servo.
- ACTION (`FF FF FE 02 05 FA`) is sent to broadcast ID so all buffered writes fire **at the same instant** → all servos start moving synchronously.
- Use this when you need synchronized multi-servo motion without bus chatter.

### 3.5 SYNC WRITE (`0x83`)

One frame, one trip on the bus, writes the same memory block to N servos with different data.

```
Length = (L + 1) * N + 4
         L = bytes written per servo
         N = number of servos

Layout:
  [addr] [L] [ID1] [data1...dataL] [ID2] [data1...dataL] ... [IDn] [data1...dataL]
```

Sent with broadcast ID → no return packets. Better real-time behavior than REG WRITE + ACTION for time-critical moves; **all servos in the frame must write the same length block at the same starting address**.

### 3.6 RESET (`0x06`)

`FF FF ID 02 06 CHK` — restores control table to factory defaults. Behavior on memory (volatile vs EEPROM) is servo-specific.

---

## 4. Worked Examples

### 4.1 PING ID 1
```
TX:  FF FF 01 02 01 FB
RX:  FF FF 01 02 00 FC     ← ERROR=0, servo is alive
```

### 4.2 Read current position (addr 0x38, 2 bytes) from ID 1
```
TX:  FF FF 01 04 02 38 02 BE
RX:  FF FF 01 04 00 18 05 DD
                LSB  MSB  → 0x0518 = 1304 (decimal) ticks
```

### 4.3 Change a servo's ID to 1 (use broadcast — only one servo on bus!)
```
TX:  FF FF FE 04 03 05 01 F4      (write 0x01 to address 0x05)
```
⚠️ **Never** broadcast an ID change with more than one servo on the bus — every servo will adopt the new ID simultaneously and you lose the ability to address any of them individually.

### 4.4 Move ID 1 to position 2048, time 0, speed 1000 (addr 0x2A, 6 bytes)
```
Position = 0x0800 (2048), Time = 0x0000 (0), Speed = 0x03E8 (1000)
TX:  FF FF 01 09 03 2A 00 08 00 00 E8 03 D5
                addr  posL posH  tL  tH  sL  sH
RX:  FF FF 01 02 00 FC
```

### 4.5 REG WRITE for IDs 1–10, then ACTION
```
ID1:  FF FF 01 09 04 2A 00 08 00 00 E8 03 D4
ID2:  FF FF 02 09 04 2A 00 08 00 00 E8 03 D3
...
ID10: FF FF 0A 09 04 2A 00 08 00 00 E8 03 CB
ACT:  FF FF FE 02 05 FA     ← broadcast, all 10 servos start together
```

### 4.6 SYNC WRITE to IDs 1–4, 6 bytes per servo at addr 0x2A
```
Length = (6+1)*4 + 4 = 0x20 (32)
TX:  FF FF FE 20 83
     2A 06                     ← addr, length-per-servo
     01 00 08 00 00 E8 03       ← ID1 + pos/time/speed
     02 00 08 00 00 E8 03       ← ID2
     03 00 08 00 00 E8 03       ← ID3
     04 00 08 00 00 E8 03       ← ID4
     58                        ← checksum
```
No reply (broadcast).

---

## 5. Checksum Worked Example

For `FF FF 01 04 02 38 02 BE` (READ example):
```
ID + Length + Instr + P1 + P2
= 0x01 + 0x04 + 0x02 + 0x38 + 0x02
= 0x41
~0x41 = 0xBE  ✓
```

For the broadcast write `FF FF FE 04 03 05 01 F4`:
```
0xFE + 0x04 + 0x03 + 0x05 + 0x01 = 0x10B → low byte 0x0B
~0x0B = 0xF4  ✓
```

---

## 6. Gotchas

- **Bus contention:** the line is half-duplex. Only one device talks at a time. A direction-switching transceiver (e.g. SN74LS241 / MAX485) on the controller side is mandatory for any real bus length.
- **Header detection = two 0xFF in a row.** Anything that can produce a stray 0xFF 0xFF on the line (noise, ground bounce on a long cable) will desync the parser.
- **Broadcast PING collides** with multi-servo buses — use unicast PING when scanning.
- **EEPROM writes have a lock bit** and limited write endurance — don't put control loops that change ID/baud on every tick.
- **Returned two-byte values are little-endian (LSB first)** on the STS3215/SCS series.
- **The "working condition" byte is an error flag, not a status word.** Treat any non-zero value as a fault; the bit meanings live in the per-servo memory table.
- **Default baud 1 Mbps** — most cheap USB-TTL adapters and breadboard wiring can't sustain that cleanly past a few cm. If you see CRC/checksum errors only at 1 Mbps, drop to 115200 or 500 kbps for bring-up.
