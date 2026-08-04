# Chapter 2 — Electronics Architecture

A subsystem-by-subsystem walkthrough answering, for every element: **what / why /
how / connects / fails / debug**. Two physical PCBs exist in the system (Waveshare
adapter, and each servo's internal control board); everything else is wire and power.

---

## 2.1 The Waveshare Bus Servo Adapter (A) — the only host-side board

**What it is** — a 42 × 33 mm bridge board: USB Type-C input, DC5521 + screw-terminal
power input, two identical 3-pin bus-servo ports, and an A/B control-mode jumper — one
header actually has two jumper positions (A = UART on the 4-pin header, B = USB).
[VERIFIED: Waveshare product page + LeRobot SO-101 docs]

**Why it exists** — the host has no native TTL half-duplex bus transceiver. The adapter
converts USB into the 1 Mbps single-wire bus and, importantly, forwards the servo
supply voltage that the stars, servos, need — routed through the same 3-wire cables.

**How it works**
- USB side: CH340-family USB-uart (Waveshare FAQ confirms CH340) → enumerates as a
  serial port (`/dev/ttyUSB*` on Linux; some units/boards enumerate as CDC `ttyACM*` —
  `[BENCH-CHECK]` your board, see inventory F15).
- Bus side: TTL single wire D. Transmit gate reversed under software — the adapter
  cannot receive while it is transmitting (half-duplex), so every host frame is
  followed by a line turnaround before the servo replies.
- **No onboard regulation** ([VERIFIED] FAQ) — the V pin on the servo port is the raw
  input voltage. **No protection fuse** visible in the public schematic ([INFERRED]
  from `Bus_Servo_Adapter_A_Schematic.pdf` — confirm with the schematic when needed).

**How it connects** — jumpers on **B**; USB-C to host; PSU to DC5521 or the green
barrier terminal (both feed the same node, either is fine — [VERIFIED] FAQ);
servo(s) on either 3-pin port (identical, either may be used [VERIFIED] FAQ).

**Failure modes**
- Charge-only / faulty USB cable → no device node or device vanishing under load.
- Wrong jumper position (A) → board drives UART header instead, US B bridge silent.
- Overvoltage on V input kills attached servos (pass-through is unregulated).
- Under-sized PSU → voltage sag on bus, erratic encoder reads, brown-outs.
- D pin short to GND → every frame garbled, all IDs see collision noise.

**Debugging**
- `dmesg | tail` after plugging → look for the CH340/`cdc_acm` registration and the
  tty node.
- `ls -l /dev/ttyUSB* /dev/ttyACM*`.
- Loopback: with power off, short the D pin of a servo port to itself is not
  meaningful — instead check V/G with a meter (expect Vbus) and check D quiescent
  level ≈ GND (line idle-low at TTL — `[BENCH-CHECK]`, expect ~0 V idle).

---

## 2.2 STS3215 internal electronics (motor + control board) — 6× per arm

**What it is** — each servo body holds: core motor, 1/345 gear train, 12-bit magnetic
encoder, and a control PCB with MCU, H-bridge/current sense, voltage sense,
temperature sense, and an RS-style line driver for the D wire.
[VERIFIED: datasheet §6-14, §7-8, §7-10, §5]

**Why it exists** — local PID (P/I/D coefficients are registers, §0x15–0x17),
protections, and telemetry mean the host only writes *targets*; servo loops run at
1 kHz internally (max position update rate 1 ms — [VERIFIED] datasheet §11/interface).

**How it works** — a packet addressed to its ID is decoded, CRC/checksum-checked, a
registers action (position/velocity/param write) is taken, and the encoder/sense
registers are updated continuously. Load/current/voltage/temperature are *readable*
registers (ch05 memory table), and several can trigger autonomous protections
(§2.6).

**How it connects** — one 3-pin `5264-3P` pigtail (pin 1 GND, 2 Vcc, 3 D — [VERIFIED]
datasheet §6-7) transitions into the daisy-chain loom. V and G pass straight through
every servo; D is tapped by the servo's bus transceiver. 15 cm default pigtail,
which the SO-101 loom extends with in-line 3-pin cables ([BENCH-CHECK] length in your
build).

**Failure modes**
- Burned input (over-7.4 V) — smoke/heat, sticky or dead output, Vcc-short.
- Stripped gear teeth after overtorque — mechanical, sounds like grinding, loads low,
  position tracks to commanded but horn does not.
- Encoder/magnet slip — reads drift or jump at the mechanical wrap.
- D input latch-up from ESD — dead receive but alive power LEDs.

**Debugging** — isolate: one motor + one fresh cable + bench PSU at 6 V, 500 mA limit,
then PING (ch07/08). Compare voltage/temperature/load registers against expected
values in ch05 tables.

---

## 2.3 Power electronics

- **Bench PSU** (host-side) is the only sourced energy — rules and budgets in ch03.
- **Adapter pass-through** — V/G to bus, nothing else.
- **Servo internal regulators** — each STS3215 board converts bus V to its logic rail;
  the motor runs from raw bus V through its H-bridge. There is *no* central 3.3 V rail;
  each servo is independent and galvanically only connected via V/G/D.
- **Line discipline** — the live D wire during high-CPU activity can radiate; keep the
  loom away from the PSU mains leads.

**Failure modes / debug** — see ch03 tables (color code: GND/V/D shorts, cold joints at
the DC5521, PSU over-current trips during rapid multi-joint moves).

---

## 2.4 Sensors

| Sensor | Location | Access | Range/unit | Evidence |
|---|---|---|---|---|
| 12-bit magnetic encoder | every servo | 2-byte read @0x38 | 0–4096 | datasheet §6-6 |
| Current (motor) | every servo | 2-byte read @0x45/0x46 | unit 6.5 mA, max ~3250 mA | memory-table V3.6 |
| Voltage | every servo | 1-byte read @0x3E | 0.1 V units | memory-table V3.6 |
| Temperature | every servo | 1-byte read @0x3F | °C | memory-table V3.6 |
| Load (torque duty) | every servo | 2-byte read @0x3C | 0.001 of max | memory-table V3.6 |

> Addresses are cross-checked against the datasheet's "address 40 = 128 one-key
> mid-point" hint (0x28) and the community V3.6 table; byte-order is **L then H**.
> Any discrepancy between the two sources is `[BENCH-CHECK]`.

---

## 2.5 Communication interfaces

- **USB (host↔adapter)**: 12 Mbps full-speed, CH340-class → tty node.
- **TTL bus (adapter↔servos)**: single wire D, half-duplex, 8N1, up to 1 Mbps.
- **No CAN / I²C / SPI** on the motor side. Host⇄servo is entirely UART-packet.
  LeRobot's `so101_motor_driver` is a pure serial driver (no swap port_hub, no extra
  board) — [VERIFIED] LeRobot source/config.

## 2.6 Protection circuitry & software protections

On the **servo** level — [VERIFIED] datasheet §7-11, memory-table V3.6:

| Protection | Trigger (default) | Behaviour | Auto-clear? |
|---|---|---|---|
| Over-load | load > 80 % stall sustained ≥ 2 s (§0x24/§0x23) | reduce to 20 % torque (§0x22) | new position cmd clears |
| Over-current | current > 2 A sustained ≥ 2 s (§0x1C/§0x26) | torque output off | new position cmd clears |
| Over/under-voltage | default trip 8.0 V / 4.0 V (§0x0E default 80 / §0x0F default 40, 0.1 V units); datasheet prose cites 7.4 V as variant's rated max | protect; alarm bit set | auto when back in range |
| Over-temperature | > 70 °C (§0x0D) | torque off | auto when cooled |
| Write-lock | EEPROM lock bit (§0x37) | EPROM writes not persisted | write 0 to unlock |

On the **host** level (LeRobot): `disable_torque_on_disconnect`, per-motor
`max_relative_target`, PID gains written at connect, and read-retries on corrupted
status packets — [VERIFIED] `config_so_follower.py`.

Adapter level: none beyond the pass-through connector (no fuse — `[INFERRED]`).

**Debugging protections** — each protection latches a bit in the *servo status*
register; read it before blaming the bus (ch05, ch08).

## 2.7 Where to learn more
- Official: `datasheets/STS3215_datasheet.pdf`, `datasheets/Feetech_Serial_Bus_Servo_Protocol_Manual.pdf`
- Community memory-table reference: [Mowibox/stm32-sts3215-lib](https://github.com/Mowibox/stm32-sts3215-lib)
- Adapter: [Waveshare Bus Servo Adapter (A) wiki](https://www.waveshare.com/wiki/Bus_Servo_Adapter_(A)) + public schematic in `datasheets/`