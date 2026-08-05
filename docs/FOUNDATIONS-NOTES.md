# FOUNDATIONS — Part 2: More Terms Worth Knowing (STS3215 / SO-101)

> Continuation of `FOUNDATIONS-NOTES.md`. Same idea: terse, anchored to your
> hardware, refreshed from scratch. A → D are escalating tiers, not chapters;
> skim in order the first time, then jump by topic later.

---

## A. Hardware around the servo you already own

### A1. Brushed DC motor

The motor inside an STS3215 is a tiny **brushed DC motor** — a permanent-magnet
stator, a wound rotor (armature), and a **commutator** with carbon brushes that
flip the current every half-turn so the rotor keeps spinning.

- Cheap, simple, high torque at low speed (in *motor* terms — not "output
  shaft" terms).
- Brushes **wear out** — the STS3215 datasheet promises "no-load speed" of
  ~52 RPM at 7.4 V; under stall the brushes carry 2.5 A and heat up.
- Speed is set by **PWM duty** from the H-bridge, not by varying voltage.

Why "Kt" matters: every brushed DC motor has a **torque constant Kt**
(N·m/A or kg·cm/A in the datasheet). STS3215 lists Kt = 8 kg·cm/A. Practically:

```
τ ≈ Kt × I        (torque ∝ current)
ω ≈ (V − I·R) / Kb  (speed ∝ supply voltage minus I·R drop)
```

That's why "stall current × Kt" gives you roughly the stall torque — and
why the Kt-reduced-to-output-shaft-after-345:1-gearing math in Part 1 §1
worked out.

### A2. H-bridge

The thing that drives the brushed motor. Four switches (usually MOSFETs) arranged
in an "H" around the motor. Closing diagonal pairs reverses the current; closing
both on one side brakes it (regenerative brake); opening all floats it (coast).

- The MCU inside the STS3215 generates **PWM** into the H-bridge — direction
  set by which pair is active, speed set by PWM duty.
- An H-bridge is **why you can have a stall current of 2.5 A** but also why you
  can **back-drive the servo** if you kill the PWM: the bridge floats and the
  motor acts as a generator, which the bulk cap on the bus tries to absorb.

### A3. PWM (Pulse-Width Modulation)

A square wave at a fixed frequency whose **duty cycle** (the fraction of time the
signal is HIGH) sets average power. The motor's mechanical time constant is much
longer than the PWM period, so the motor "sees" the average.

- At 1 MHz (H-bridge PWM frequency, typical), each cycle is 1 µs.
- 50% duty → motor sees "half voltage" → half speed (with caveats).
- Servo control loop output is a PWM duty command → H-bridge → motor.

The STS3215 exposes this indirectly through "Speed" and "Time" fields in the
protocol: maximum speed in steps/s, time to reach it = acceleration profile.

### A4. The "PID" the servo runs internally

STS3215's internal control algorithm is **PID**:
- **P**roportional: error × Kp. Pushes harder the further you are from target.
- **I**ntegral: integral of error × Ki. Eliminates steady-state error (offset).
- **D**erivative: d(error)/dt × Kd. Damps overshoot by braking as you approach.

```
output = Kp·e + Ki·∫e dt + Kd·de/dt
       e = (target_position − measured_position)
```

The STS3215 lets you tune P, I, D at addresses 0x15/16/17 (Ch05 §5.6).
Defaults work for unloaded bench moves; loaded joints creep, oscillate, or
buzz — symptoms are P/I/D misconfiguration.

> Reminder from Part 1 §3: PID is *inside the servo*. The host's job is to
> choose the *target*; the servo is what makes the *measured* value chase it.
> So your host loop is **not** PID — it's more like "setpoint generator + bus
> traffic". Don't conflate them.

### A5. Stall current, rated current, idle current

Three numbers you'll see in every smart-servo datasheet:

| Term | Meaning |
|---|---|
| **No-load current** | What the motor draws just spinning, no torque output (~150 mA on STS3215 @ 7.4 V) |
| **Rated current** | Continuous current while doing useful work (650 mA @ 7.4 V, ≈ 5 kg·cm load) |
| **Stall current** | Current when shaft is mechanically blocked (2.5 A @ 7.4 V) |

Stall current is the **maximum the H-bridge can deliver before tripping
protection**. A stalled arm + serial-bus command can briefly draw all six
servos at stall = **15 A**. PSU must be sized for that, or current-limited
to ~3 A and you'll just shut down on overload.

### A6. Bus transceiver (SN74LS241, MAX485, etc.)

The controller-side circuit that physically connects a normal full-duplex UART
(TX pin + RX pin) to the half-duplex bus (one wire). The classic implementations:

- **SN74LS241** — a non-inverting octal buffer; one DIR pin flips direction.
  Cheap, classic, what the older Feetech/Arduino tutorials use.
- **MAX485 / MAX3485** — an RS-485 transceiver. Differential, but can be wired
  single-ended to TTL. **The Waveshare Bus Servo Adapter for SMS (RS-485) servos
  uses a chip like this.** The STS3215 uses TTL, so the MAX485 is overkill but
  works.
- **Dedicated half-duplex UART bridge** — modern USB-serial chips (CH340G with
  extra glue, FT232H with bit-bang mode) can do this internally. The Waveshare
  Bus Servo Adapter (A) is built around a CH340-class chip.

The practical upshot: **you almost never wire STS3215 directly to a raw
microcontroller UART**. You go through a board like the Waveshare adapter
that handles TX/RX switching for you.

### A7. Bus terminator / pull-up resistor

Long wires + high baud = signal reflections and slow edges. Industrial bus
design (RS-485, CAN) adds **120 Ω termination** at both ends to dampen
reflections. The STS3215 bus doesn't (it's intentionally short and simple),
which is why the protocol manual warns about 1 Mbaud over long cables.

### A8. CH340 (and why you see `/dev/ttyUSB*`)

The Waveshare adapter is built around a **CH340** — a Chinese USB-to-serial
bridge IC that is functionally equivalent to the FTDI FT232 or Silicon Labs
CP2102. On Linux it shows up as `/dev/ttyUSB0`, *not* `/dev/ttyACM0` (that's the
CDC-ACM class used by some clones). LeRobot's `lerobot-find-port` walks the
list and lets you pick.

### A9. Connector naming — "5264-3P", "5264", "SM"…

The servo pigtail is a **5264-3P** (3-pin JST-style). You'll also meet:

| Name | What it is |
|---|---|
| **5264-3P** | 3-pin JST PH 2.0 mm pitch housing, the STS3215's pigtail |
| **3-pin servo cable** | Generic 3-wire lead, often labeled Signal / V+ / GND |
| **Dupont** | 0.1" pin headers used for jumpers |
| **JST-XH / PH** | Common balance-board / battery connectors |
| **DC5521** | 5.5 mm barrel jack (PSU output), center-positive |

"SW519A / SW520" / "JST-EH" etc. you may see — they are all just different
housings. The only thing that matters electrically is **pin order**.

### A10. GND / VCC / Signal — pin order

The pin order on the daisy-chain cable is critical. The STS3215 datasheet
defines 1 = GND, 2 = VCC, 3 = Signal. If you cross wires on a single servo,
that servo dies; if you cross wires on two servos that you plug into each other,
*both* can die. This is why Ch04 §1 says "D/D V/V G/G continuity" — pin-for-pin.

---

## B. Protocol vocabulary you'll see every time Ch05 opens

### B1. Synchronous vs asynchronous serial (revisited)

A reader of Part 1 might still wonder: "is 'async' bad?" No — it's just one
of two designs:

- **Asynchronous (UART):** no separate clock line; both ends know the baud rate
  and re-sync on each start bit. Cheap, popular, but per-byte overhead is 20 %
  (start + stop bit out of 10).
- **Synchronous (SPI, I²C):** separate clock line; higher bitrate, less
  overhead, but needs ≥ 3 wires (SCK + data + enable) per device or bus.

The STS3215 is asynchronous. CAN is asynchronous too (no clock line; bits are
re-synchronized using bit stuffing). USB is **polled, not serial-bit-banged**
— the bridge chip handles it for you.

### B2. Frame / packet / byte — the layered vocabulary

Don't get these mixed:

- **Byte** = 8 bits, the smallest addressable unit of data.
- **Frame** = the start/stop + one byte worth of bit-times; a UART "atom".
- **Packet** = the full logical message: header + ID + length + instruction +
  parameters + checksum. **This is what the protocol manual means by
  "packet".** The STS3215 instruction packet is always 6+ bytes.

### B3. ID, address, register — three different "addresses"

When you read code you'll see **three distinct meanings** of "address":

| Word | Refers to | Example |
|---|---|---|
| **Servo ID** | Which physical servo on the bus | ID=1 = shoulder_pan |
| **Memory address** | Where in the servo's control table | address 0x38 = current position |
| **Register** (loose usage) | A field in the control table | "PID_P register" = address 0x15 |

When reading LeRobot source you'll see `address=0x38, length=2` — that's
**memory address**, not servo ID. Mixing them up is a classic mistake.

### B4. Little-endian vs big-endian (one more time, now with a real example)

The STS3215 stores 12-bit position 1304 (= 0x518) as two bytes:

```
sent on the wire as:   0x18   0x05      ← low byte first
```

Same as how most x86 CPUs store a 16-bit int. The older SCS protocol (and the
SMS RS-485 protocol, per the manual) use the opposite order: **high byte first**.
Always check which series you're coding against.

A canonical "did I get the byte order right?" test: write 0x0800 = 2048 (the
neutral position, datasheet §4) and confirm the servo moves to "center".

### B5. Checksum vs CRC — what they each catch

The STS3215 uses a **1-byte bitwise-NOT sum** "checksum". It catches:

- Any single-byte corruption (single-bit flip in any byte).
- Some multi-bit patterns (because sum overflow triggers it).

It does **not** catch:

- Systematic corruption where two specific bytes are flipped together.
- Bit errors that happen to preserve the low-byte sum.

For real error checking (cable runs in industrial environments) you'd use
**CRC** — Cyclic Redundancy Check. CAN, USB, Ethernet all use CRCs. The STS3215
stays with a checksum because (a) it's a short cable, (b) the CPU inside the
servo is slow, (c) retransmits are cheap — the controller just re-reads.

### B6. Broadcast, unicast, multicast

- **Unicast** — one recipient (ID = 1..253).
- **Broadcast** — every recipient (ID = 0xFE). "Nobody replies."
- **Multicast** — a subset. **Not supported on STS3215.** The way to fake
  multicast is sequential unicasts or SYNC-WRITE (which is technically a
  broadcast payload but per-servo data).

If you ever see "multicast" referenced for Feetech servos, assume it's shorthand
for "SYNC-WRITE" or "multiple unicasts in a row".

### B7. Sync-Write vs Reg-Write + Action — when to use which

This trips up first-timers. Both let one frame move multiple servos. The
difference is **how the data travels**:

| | REG-WRITE + ACTION | SYNC-WRITE |
|---|---|---|
| **Frames** | N + 1 | 1 |
| **Wire traffic** | One register-write per servo, then one ACTION | One big broadcast |
| **Per-servo data** | Each frame carries only *that* servo's data | One frame carries *all* servos' data |
| **Memory block** | Can be anywhere | Must be same addr + length per servo |
| **Reply?** | No (broadcast) | No (broadcast) |

Rule of thumb: **SYNC-WRITE for high-rate control** (one position vector per
tick for all 6 joints), **REG-WRITE + ACTION for low-rate, full-table changes**
(e.g. set a new baud on all motors at once during provisioning).

### B8. Response level (address 0x08)

A servo register you might ignore at your peril. From Ch05 §5.6:

- `0` = only reply to **READ and PING**. Write/RegWrite/Ack still go out, but
  you get *nothing* back.
- `1` = reply to everything.

Why set it to 0? Less bus traffic. Why default is 1? Less surprise. If your
controller keeps firing "where are you?" messages and waiting for non-replies,
set this to 0 — but only after you've confirmed PING works at all.

### B9. EEPROM vs SRAM in the control table

Some addresses are in **EEPROM** (persist across power cycles, limited writes,
often "lockable" via 0x37), others are in **SRAM** (volatile, unlimited writes,
fast). Ch05 §5.6 marks each row `RW/EPROM` or `RW/SRAM` accordingly.

Write-idle patterns:
- `EEPROM`: change with caution, unlock first, expected to persist.
- `SRAM`: change freely each tick (target position, torque limit, acceleration).

Don't write PID gains or baud rate at 1 kHz. They live in EEPROM.

### B10. Lock mark (0x37) and EPROM discipline

The "lock" is a single-byte EPROM flag. If `0x37 = 1`, writes to EEPROM
addresses are silently dropped (the value resets on power cycle). Default = 0
(unlocked). Procedure when re-flashing servo params:

```
1. WRITE 0x37 = 0      (unlock)
2. WRITE new ID/baud/etc.
3. READ back the byte to confirm
4. Optionally WRITE 0x37 = 1 again to lock
```

This is the #1 silent-failure cause on first bring-up: "I changed the baud but
it didn't take after power-cycle."

### B11. Error / Status / Fault / Flag — overloaded vocabulary

The protocol reply has **one byte called "ERROR"**. The names "error", "status",
"fault", "flag" all show up in different translations of the manual. They
mean the same thing: a bitfield. STS3215 status byte = address `0x41`:

- `0` = OK.
- non-zero bitfield = some protection tripped (overvoltage, overtemperature,
  overcurrent, encoder fault, overload).

Protocol reply's ERROR byte **is** the same value as address 0x41 — the reply
byte is a kind of "instant read of just the status byte".

### B12. Servo status / "moving" sign (0x42)

Address 0x42 = "mobile sign" in the manual = 1 if the servo is currently
moving, 0 if it has reached its target. Useful for sequencing — "wait until
every servo reports stationary before starting the next motion."

### B13. Voltage / current / temperature readouts

Three read-only telemetry addresses (0x3E, 0x45, 0x3F). Units:

- **Voltage** at 0x3E = **0.1 V units**. So `0x4A` = 7.4 V.
- **Current** at 0x45 = **6.5 mA units**. So `0x012C` = 300 × 6.5 mA = 1.95 A.
- **Temperature** at 0x3F = **°C**. So `0x46` = 70 °C.

Mixing these up is painful — the temperature register is plain °C, but voltage
*isn't* plain volts. Always **divide**.

---

## C. Terms you'll meet once you read the LeRobot code

### C1. Host, controller, adapter — three roles, one box

The "controller" in this project is **a Python script running on your host PC**.
The **adapter** is the Waveshare USB↔UART bridge. Don't conflate them.

| Role | Examples | Job |
|---|---|---|
| **Host** | Ubuntu PC + LeRobot | Reads trajectories; emits target poses |
| **Adapter** | Waveshare Bus Servo Adapter | Translates USB ↔ half-duplex TTL |
| **Servo MCU** | The microcontroller *inside* STS3215 | Runs PID, manages bus, drives H-bridge |

Sometimes people say "controller" when they mean "the controller chip inside
the servo". Both meanings exist. Read carefully.

### C2. Open-loop vs closed-loop

- **Open-loop control:** send commands, no feedback. A dumb RC PWM servo is open-loop
  from the host's perspective.
- **Closed-loop control:** send commands, **measure result**, compare to setpoint,
  correct. The PID inside the STS3215 is a closed-loop position controller.

The **arm as a whole** is also a closed-loop system from the host's POV if you
read encoders back — LeRobot does exactly this for the leader/follower pair
in teleop (an "impedance" or "admittance" loop in teleop jargon, technically).

### C3. Trajectory, waypoint, setpoint, target

All four are used in robotics for "where the actuator should go at time t":

- **Setpoint** — a generic engineering term (control theory). One point.
- **Target** — same as setpoint. STS3215 calls its setpoint register "target
  position".
- **Waypoint** — a scheduled point at a specific time.
- **Trajectory** — the whole sequence of waypoints over time, possibly
  parameterised by polynomial.

LeRobot's `send_action(...)` sends *one* setpoint per joint per tick.
Trajectory generation (interpolating between waypoints, time-parameterising it)
happens higher up — possibly in `lerobot`'s policy side, or in your own code.

### C4. Impedance / admittance / teleop control

In LeRobot (and `lerobot`'s remote teleop in particular), "impedance control"
or "admittance control" describes how the leader arm drives the follower arm:

- **Position-position (impedance):** measure leader position → follower setpoint.
  Force is what the follower pushes back; that's the "impedance".
- **Force-position (admittance):** measure forces on the leader → derive follower's
  desired motion.

You don't need the math to read LeRobot code; you do need to know the difference
because the loop frequencies and write patterns differ.

### C5. Pose, joint state, action, observation

Standard ML-for-robotics vocabulary (used in LeRobot, ACT, GRPO docs):

- **Pose** — (x, y, z, roll, pitch, yaw) of an end-effector. *Cartesian* description.
- **Joint state** — {angle, velocity, torque} per joint. *Per-joint* description.
- **Action** — the robot's commanded control input. Could be joint positions or
  Cartesian targets.
- **Observation** — the sensor readings the *policy* sees (joint positions, images,
  force readings). NOT the ground truth — observation noise matters.

LeRobot's `motor.get_observation()` returns observation dicts; `motor.send_action(...)`
takes an action dict. Don't conflate them.

### C6. Calibration

LeRobot's calibrate step discovers each joint's **min and max angles**, the **zero
position**, the **direction sign**. The PID's address 0x09 (min) and 0x0B (max) get
written here. "Calibration" is what gives meaningful "joint angle in degrees" instead
of raw encoder ticks. It's NOT in the servo firmware — it's pure **host-side state**
that maps tick ↔ degree.

### C7. Watchdog timeout, return delay

`Return delay` (address 0x07): the time the servo waits before sending its reply,
in 2 µs ticks. If set too small on a slow bus, the host misses the start of the
reply. If set too large, the loop is slow for no reason. 0 = 0 µs (a common
default — host waits the bus turnaround by software).

### C8. Telemetry, logging, bench log

| Word | Meaning in this project |
|---|---|
| **Telemetry** | Round-tripped status (position, load, V, T) you read from servo |
| **Logging** | Persisting telemetry to disk |
| **Bench log** | Your hand-written notebook entry from a session — `logs/bench-log-...md` |

Some LeRobot drivers have verbose `--debug` log modes. Use them. They are how
you'll catch a slipped ID or a wrong baud before burning a finger.

### C9. Motor torque switch (0x28) — including the magic 128

Writing:

- `0` → torque OFF (no PWM, motor is back-drivable).
- `1` → torque ON, drive to current target.
- `128` → **set the current position as the new "neutral" (value 2048)**. This is
  the "re-zero on the fly" trick used during calibration.

This is the single most useful obscure register in the STS3215 control table.

### C10. Acceleration register (0x29)

Sets how fast the servo is allowed to *change* its speed in 100 step/s² units.
Without this, going from "stand still" to "full speed" instant-starts and
slams the gear train. It's a "ramp" — like a trapezoidal motion profile in a
single byte.

### C11. Backlash, hysteresis, dead-zone

- **Backlash** — small angle lost when reversing direction (caused by gear-tooth
  clearance). STS3215: ≤ 0.5°. Important for absolute-reposition accuracy.
- **Hysteresis** — the path the servo takes going up doesn't match going down
  at the same command. Often caused by backlash + friction + magnetic field lag.
- **Dead-zone** — the smallest command change that actually produces a move.
  Any smaller and the servo doesn't react. Useful for noise immunity.

You can't software-correct backlash; you live with it or use dual-encoder setups
(motor side + joint side). Hysteresis can be partly handled with PID tuning. Dead-zone
is usually addressed by the PID coefficients inside the servo.

### C12. Overvoltage / undervoltage window

The servo's regulator settings (addresses 0x0E/0x0F) define the safe operating
window. Defaults: **8.0 V max, 4.0 V min** (units are 0.1 V). Feed 7.4 V
nominally; anything above 8.0 V trips over-voltage protection within ~2 s.
Anything below 4.0 V trips under-voltage. **This is why the bench PSU ceiling
matters even more than the label on the barrel jack.**

---

## D. PID and control theory — what you'll actually need to tune

### D1. The PID equation

```
u(t) = Kp·e(t) + Ki·∫₀ᵗ e(τ)dτ + Kd·de(t)/dt
```

- `e(t) = setpoint − measured` — the error.
- `u(t)` — the controller output (PWM duty into the H-bridge).
- `Kp, Ki, Kd` — gains; how hard each term pushes.

What each term does to a step response:

```
           ┌── setpoint
           │
response ──┤                ┌── overshoot (P too high, D too low)
           │              ╱   ╲
           │            ╱       ╲
           │          ╱           ╲─────────── settled (Ki removes offset)
           │        ╱
           │     ╱
           │──╱
           └───────────────────────────────── t
```

### D2. Symptoms that map to PID fixes

| Symptom | Likely cause | Fix |
|---|---|---|
| Slow to reach setpoint, no overshoot | Kp too low | Increase Kp |
| Reaches setpoint but oscillates | Kp too high, Kd too low | Reduce Kp or increase Kd |
| Offset between commanded and actual | Ki too low | Increase Ki slowly |
| Buzzes at setpoint (chatter) | Kd too low, or electrical noise | Increase Kd, filter input |
| Sluggish under load | Insufficient Kp or torque limit | Raise Kp or check torque limit (0x30) |

### D3. Bode plot / root locus / Nyquist

These are the diagrams control engineers draw to *design* PID gains without
trial-and-error. You don't need to draw them for STS3215 (defaults are reasonable)
but you should recognise the terms if they appear on GATE RA:

- **Bode plot:** magnitude & phase vs frequency. Shows stability margin.
- **Root locus:** where closed-loop poles go as gain varies. Predicts instability.
- **Nyquist criterion:** how to tell from a Bode plot whether a closed loop will be stable.

### D4. Stability, bandwidth, overshoot — three numbers that describe a servo

- **Bandwidth** — the highest frequency at which the closed loop can still track
  a command. STS3215 doesn't publish this directly, but position update is ≤ 1 ms,
  so bandwidth ≈ tens of Hz.
- **Overshoot** — how far the response exceeds the setpoint on its first arrival.
  Often expressed as a percentage.
- **Settling time** — how long to reach and stay within, say, 1 % of the setpoint.

You tune PID by adjusting these three to fit the mechanical system.

### D5. Discrete vs continuous time

A real MCU runs the loop at a fixed **Δt** (sample period). PID becomes:

```
integral += e[k] * Δt
derivative = (e[k] - e[k-1]) / Δt
output = Kp*e[k] + Ki*integral + Kd*derivative
```

- The servo MCU presumably runs this discrete version internally at its 1 ms
  update rate.
- The HOST loop (your Python script) is a separate discrete loop, usually 50 Hz
  to 200 Hz (LeRobot's typical range). It's NOT a PID; it generates **target
  positions** for the servo's PID. Don't multiply these loops.

### D6. Anti-windup (Ki integral clamp)

A pure integrator winds up to infinity if the servo is stalled (can't reach
target) — the next time it can move, it sprints to correct the absurd sum and
overshoots badly. **Anti-windup** clamps the integral term. Many servo PIDs do
this; STS3215's control table doesn't expose the clamp value directly, so it's
probably fixed in firmware.

### D7. Feed-forward

Speeding up a PID by adding a `Kv * v_desired` term that bypasses P for expected
behaviour. Not exposed on STS3215; mentioned for completeness.

### D8. Trajectory profile (trapezoidal / S-curve)

When you specify "position + time + speed" in the WRITE to address 0x2A, the
servo internally generates a profile:

- **Trapezoidal** — accelerate at fixed rate, cruise, decelerate at fixed rate.
- **S-curve** — like trapezoidal but acceleration ramps smoothly (less jerk).

The "Acceleration" register (0x29) is what sets the acceleration part of the
trapezoid.

### D9. Step response, impulse response, frequency response

Three ways to characterise a closed loop:

- **Step:** how the system reacts to an instant setpoint change. Most useful for
  PID tuning — see overshoot/settling time.
- **Impulse:** like step but duration is infinitesimal. Used for identifying
  damping.
- **Frequency response:** how the system reacts to sinusoidal commands at various
  frequencies. Used for bandwidth estimation.

---

## E. Power and PCB vocabulary you'll meet sooner than you think

### E1. Bulk capacitor / decoupling capacitor

- **Bulk capacitor** — big electrolytic cap on the Vbus rail near the connector.
  Absorbs motor-generated back-EMF surges when the H-bridge decelerates.
- **Decoupling cap** — small ceramic cap across an IC's V/G pins, right at the
  IC. Quenches high-frequency noise on the supply.

Every STS3215 has at least one of each. The bus wire doesn't carry
short current spikes because the caps locally provide them.

### E2. Back-EMF, regen, dynamic braking

When a motor spins down with the H-bridge still active, it acts as a generator.
The current has to go somewhere — into the bus cap, into the PSU's input cap,
or into the air as heat. On the SO-101:

- Back-EMF from **decelerating** a whole arm can push the bus above the PSU's set
  voltage for milliseconds.
- The bench PSU's current-limit/absorb rating determines whether the PSU eats
  this (good) or the bus voltage spikes (bad).

### E3. Logic level / level shifter

TTL is 0–5 V. Modern MCUs (ESP32, Raspberry Pi Pico, STM32) often run at
3.3 V. STS3215's "HIGH = 2–5 V" includes 3.3 V, so a 3.3 V MCU talks
**directly** to an STS3215 with **no level shifter**. That's why the Waveshare
adapter has no level-shifting IC — it's all TTL.

### E4. Pull-up / pull-down resistor

The signal wire is idle HIGH in the STS3215 bus (per Ch05 §5.3 "idle-low":
actually, idle is the bus-recessive state, which the protocol manual calls
"idle low" because the UART idles HIGH... clarify in your own notes; what
matters is that the bus has a defined idle level). A **pull-up resistor**
to V holds the line at that idle level when nobody is driving it. The
Waveshare adapter includes one for you; if you make your own board, add one
(4.7 kΩ–10 kΩ).

### E5. ESD (Electrostatic Discharge)

A static zap can kill ICs. The bench guidance in your README §safety calls
for a grounded mat. STS3215 itself has no ESD rating published (datasheet
§environmental is silent on it).

### E6. USB-C data vs charge-only

A "charge-only" cable lacks the D+/D− wires. Plugging the SO-101 in via
such a cable → host sees nothing in `lsusb`, then nothing in `dmesg`. Easy
diagnostic trap. Any cable labeled "data" or with the USB-IF trident works.

### E7. Slew rate, edge rate

How fast the signal line transitions from LOW to HIGH (or back). At 1 Mbaud,
each bit-time is 1 µs; the edges must occur within ~100 ns to keep the
receiver happy. Long cables + capacitive loads slow the edge — another
reason to keep the SO-101 wiring short (< 30 cm between motors is fine).

### E8. daisy-chain vs star

- **Daisy-chain** — device A → device B → device C, on the same wire.
- **Star** — all devices home-run back to a central point.

The SO-101 bus is a daisy-chain. A fault in any one servo blocks the bus
past it. Industrial RS-485 sometimes uses a star with termination; hobby
smart servos don't.

---

## F. Robotics-control vocabulary for the bigger picture

### F1. Degree of freedom (DOF)

The number of independent ways a robot can move. SO-101 = **6 DOF + gripper =
7 controlled axes, 6 DOF in the pose sense**. Why "6 DOF" matters: a rigid
body in 3D needs 6 numbers to fully specify its pose (x, y, z, roll, pitch,
yaw). An arm with < 6 DOF can only reach *some* poses — underactuated arms.

### F2. Workspace / reachable set

The set of positions the end-effector can reach. For a 6-DOF arm in 3D, this
is a 3D region; for the SO-101 it's mostly a forward hemisphere of ~30 cm
radius, with yaw roll constrained by the wrist.

### F3. Kinematics (forward / inverse)

- **Forward kinematics** — given joint angles, where is the end-effector? A
  pure trigonometry problem.
- **Inverse kinematics** — given a desired end-effector pose, what joint angles?
  Harder; generally multiple solutions; numerical solvers iterate.

LeRobot doesn't ship a full kinematic stack; it operates in *joint space*
(send angles directly). IK shows up when you want the arm to track a
Cartesian trajectory.

### F4. Jacobian

A matrix that maps "small change in joint angle" → "small change in end-effector
pose". The bridge between joint-space control and Cartesian-space control.

### F5. Force / torque sensor

SO-101 doesn't have one. STS3215 reports "current load" (a proxy for torque,
from the motor current), but it's not a real force sensor — it can't feel
external forces. For that you'd add a wrist F/T sensor.

### F6. Compliance vs rigidity

A **compliant** arm gives way under external force. A **rigid** arm fights it.
The SO-101 is rigid in software (PID tries to hold position). Adding a torque
estimator for gravity-compensation makes it *appear* compliant. Adding a
Force/Torque sensor makes it actually compliant.

### F7. Singularity

A pose where the Jacobian loses rank — the arm loses a DOF momentarily.
"Shoulder lock" is the most common 6-DOF singularity. STS3215 doesn't care
about this directly, but a control law that gets stuck at a singularity can
command huge torques. Good controllers add singularity avoidance.

---

## G. Quick reference table — STS3215 register cheat-sheet

| Address | Size | Name | Notes |
|---|---|---|---|
| 0x05 | 1 | ID | 0–253, EPROM |
| 0x06 | 1 | Baud | 0=1M, 1=500k, ... 7=38400 |
| 0x07 | 1 | Return delay | 2 µs units |
| 0x08 | 1 | Response level | 0=READ/PING only, 1=all |
| 0x09–0x0A | 2 | Min angle limit | L,H, EPROM |
| 0x0B–0x0C | 2 | Max angle limit | L,H, EPROM |
| 0x0D | 1 | Max temp | °C, default 70 |
| 0x0E | 1 | Max voltage | 0.1 V, default 80 = 8.0 V |
| 0x0F | 1 | Min voltage | 0.1 V, default 40 = 4.0 V |
| 0x10 | 2 | Max torque | 0–1000 (1000 = 100 %) |
| 0x15 | 1 | P coefficient | PID |
| 0x16 | 1 | D coefficient | PID |
| 0x17 | 1 | I coefficient | PID |
| 0x21 | 1 | Operation mode | 0=position, 1=speed c.l., 2=PWM o.l., 3=step |
| 0x28 | 1 | Torque switch | 0=off, 1=on, **128=zero-to-2048** |
| 0x29 | 1 | Acceleration | 100 step/s² units |
| 0x2A | 2 | Target position | L,H, SRAM, signed-16 |
| 0x2C | 2 | Running time | 0.001 s |
| 0x2E | 2 | Running speed | steps/s |
| 0x30 | 2 | Torque limit | 0–1000 |
| 0x37 | 1 | Lock mark | 1 = EPROM writes ignored |
| 0x38 | 2 | Current position | L,H, RO |
| 0x3C | 2 | Current load | 0.001 of max |
| 0x3E | 1 | Voltage | 0.1 V, RO |
| 0x3F | 1 | Temperature | °C, RO |
| 0x41 | 1 | Servo status | fault bits, RO |
| 0x42 | 1 | Mobile sign | 1=moving, RO |
| 0x45 | 2 | Current | 6.5 mA units, RO |

---

## H. One-page mental model

```
                      ┌────────────────────────────────────────┐
                      │              BENCH                     │
                      │                                          │
                      │   ┌────────┐    5 V via 3-pin cable      │
                      │   │  PSU   │──────────────────────────┐  │
                      │   └────────┘     5–7.4 V              │  │
                      │                                    ▼  ▼  │
                      │   ┌─────────────────────────────────────┐ │
                      │   │  Waveshare Bus Servo Adapter (A)    │ │
                      │   │   USB-C ←→ CH340 ←→ DIR pin ←→ D   │ │
                      │   └────────────────┬────────────────────┘ │
                      │                    │  TTL, half-duplex     │
                      │                    ▼  @ 1 Mbps, 8N1       │
                      │   ┌────┐    ┌────┐    ┌────┐  ...  ┌────┐ │
                      │   │ ID1│    │ ID2│    │ ID3│        │ ID6│ │
                      │   │brus│    │brus│    │brus│        │brus│ │
                      │   │hed │    │hed │    │hed │        │hed │ │
                      │   │ DC │    │ DC │    │ DC │        │ DC │ │
                      │   │+H- │    │+H- │    │+H- │        │+H- │ │
                      │   │brid│    │brid│    │brid│        │brid│ │
                      │   │ +  │    │ +  │    │ +  │        │ +  │ │
                      │   │gear│    │gear│    │gear│        │gear│ │
                      │   │ 1/ │    │ 1/ │    │ 1/ │        │ 1/ │ │
                      │   │345 │    │345 │    │345 │        │345 │ │
                      │   │+PID│    │+PID│    │+PID│        │+PID│ │
                      │   │+mag│    │+mag│    │+mag│        │+mag│ │
                      │   │enc │    │enc │    │enc │        │enc │ │
                      │   └────┘    └────┘    └────┘        └────┘ │
                      │                                          │
                      │                                          │
                      └────────────────────────────────────────┘
                                  ▲
                                  │ USB
                                  │
                      ┌───────────────────────┐
                      │   HOST (PC)           │
                      │   Ubuntu 24.04        │
                      │   Python + LeRobot    │
                      │   SO101Follower       │
                      │   - runs at ~50–200 Hz│
                      │   - reads encoders    │
                      │   - writes targets    │
                      │   - PID lives BELOW   │
                      └───────────────────────┘
```

In one sentence: **a host PC tells each smart servo where to go via a shared
half-duplex TTL wire using a packet protocol; each servo enforces its own
position with its own PID loop, driving a geared brushed DC motor with an
H-bridge and reading its own magnetic encoder.**

That's all of it. Everything in Ch02–Ch09 is one layer of detail on this
picture.

---

## Cross-reference index (Part 1 ↔ Part 2)

| Part 1 section | Part 2 follow-up |
|---|---|
| §1 Gear ratio | §A1 DC motor, §A2 H-bridge, §D PID |
| §2 TTL half-duplex UART | §A6 Bus transceiver, §B1 Async vs sync, §E4 Pull-up |
| §3 Encoder comparison | §A5 Stall / rated / no-load current |
| §4 Serial Bus Smart Servo protocol | §A6 Bus transceiver, §B2 Frame/packet, §B9 EEPROM discipline, §B11 Error/status, §C2 Open/closed loop, §C3 Setpoint/joint state |

(GATE 0 — Linear Algebra: §F4 Jacobian is exactly the matrix you'll need to relate joint velocities to end-effector velocities; worth deriving a 2-link example by hand.)

(GATE 3 (B1) — Control Systems: §D PID isn't just "tune until it works" — for the GATE you'll be asked to compute closed-loop TF and stability margins. STS3215 default PID gains correspond to a particular damping ratio; the table in §D2 maps symptoms → terms you manipulate.)