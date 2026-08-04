# Chapter 6 — Programming the Robot

> The SO-101's officially supported stack is **LeRobot's `so101_follower` driver**, a
> pure-Python, pyserial+Feetech-SDK path. There is no vendor C++ SDK in the loop and no
> firmware to build — the "embedded software" you manage is: **servo EEPROM config**
> (IDs, baud, limits) + **host-side driver config** (PID, safety clips). This chapter
> covers both, then the ROS 2 path you already started in `~/Desktop/s101`.

## 6.1 Development environment

Target, verified 2026-08-04:

```
Ubuntu 24.04.4 LTS · Python 3.12.3 · x86_64
```

**Install:**

```bash
# isolated venv (3.12 is inside LeRobot's supported range)
python3 -m venv ~/Deployments/lerobot-venv        # or wherever you keep envs
source ~/Deployments/lerobot-venv/bin/activate
pip install --upgrade pip

# LeRobot source with the Feetech extra (also pulls pyserial + feetech-servo-sdk)
git clone https://github.com/huggingface/lerobot.git
cd lerobot
pip install -e ".[feetech]"
```

**Dependencies that end up in the loop** ([VERIFIED] pyproject):

| Package | Role |
|---|---|
| `pyserial` | UART/transport |
| `feetech-servo-sdk>=1.0.0,<2.0.0` | low-level feetech frame encoder/decoder used by `lerobot.motors.feetech` |
| `dragccus`/`draccus` | CLI + config parsing (`--robot.type=...`) |

**Permissions** (one-time):

```bash
sudo usermod -aG dialout $USER    # re-login after this
# or, quick and dirty:
sudo chmod 666 /dev/ttyUSB0
```

## 6.2 Driver architecture

```
Robot (abstract)                         lerobot.robots.robot
 └─ SO101Follower (SOFollower)           lerobot.robots.so_follower
      ├─ config: SO101FollowerConfig     port, id, PID, max_relative_target, calibration
      ├─ FeetechMotorsBus                lerobot.motors.feetech (Feetech SDK under the hood)
      │     sync_write("Goal_Position", {motor: deg})
      │     sync_read("Present_Position", ...)
      │     configure(), setup_motor(), write_calibration()
      └─ Cameras (not required for motor bring-up)
```

- **`config_so_follower.py`** — `SO101FollowerConfig` ([VERIFIED]):
  `port`, `disable_torque_on_disconnect=True`, `max_relative_target`,
  `position_p/i/d_coefficient = 16 / 0 / 32`, `num_read_retries = 2`.
- **`so_follower.py`** — `SO101Follower` ([VERIFIED]):
  - `connect(calibrate=True)`, `configure()`, `calibrate()`, `setup_motors()`
  - `get_observation()` → `{"Shoulder_Pan.pos": float, ...}` (degrees, `use_degrees`)
  - `send_action({...})` → sync-writes **Goal_Position** (register 0x2A) to all motors
  - `disconnect()` → torque-off by default
- Configure-time actions taken by `configure()` ([VERIFIED] source): operating mode →
  POSITION, write PID gains, and for the **gripper** special limits — **50 %** max
  torque, **50 %** max current, 25 % overload torque (to avoid gripper burnout).

## 6.3 CLI tools (come with LeRobot)

| Tool | Purpose | Flags |
|---|---|---|
| `lerobot-find-port` | discover USB ports for the arms | — |
| `lerobot-setup-motors` | one-time ID/baud setup, one motor at a time | `--robot.type=so101_follower --robot.port=...` |
| `lerobot-calibrate` | write calibration, map raw→real angle | `--robot.type=so101_follower --robot.port=... --robot.id=...` |

## 6.4 Configuration files

Configuration is **code-side** (draccus dataclass), not a YAML the bus reads. Two files
matter on disk:

- **Calibration file** — saved per `id` when you run `lerobot-calibrate`
  (JSON; default under `~/.cache/calibration/so101/<id>/...` `[INFERRED]`, verify on
  your install). Contains per-motor `homing_offset`, `sign`, `range_limits`.
- **Your script/config** — the `SO101FollowerConfig` you instantiate.

EEPROM-side config lives inside each servo (ch05 §5.6): ID (0x05), baud (0x06), angle
limits, voltages, PID, torque-limit — set via `lerobot-setup-motors` or raw writes.

## 6.5 Minimal working examples

> Port: your adapter's node (`[BENCH-CHECK]`, see ch00). The arm is currently
> unplugged, so tested outputs are pending first live run.

**Example A — connect, read state, move one joint (safe, tiny step):**

```python
from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig

motor = SO101Follower(
    SO101FollowerConfig(
        port="/dev/ttyUSB0",
        id="bench_single",
        num_read_retries=2,
        max_relative_target={"Shoulder_Pan": 0.1},  # ° per command — safety clip
    )
)
motor.connect(calibrate=False)      # we have not calibrated yet on the bench

obs = motor.get_observation()
print(obs)                          # {'Shoulder_Pan.pos': ..., 'Elbow_Flex.pos': ...}
# expected: six .pos keys, floats in degrees, near the servo's physical angle

# tiny absolute move (degrees); LeRobot wraps into Goal_Position (0x2A)
sent = motor.send_action({"Shoulder_Pan.pos": obs["Shoulder_Pan.pos"] - 5.0})
print(sent)                         # clipped to 5 ° if max_relative_target applies

motor.disconnect()                  # torque off (default)
```

**Example B — raw register-level equivalent (pyserial or pyserial+feetech SDK):**

```python
import serial
ser = serial.Serial("/dev/ttyUSB0", 1_000_000, timeout=0.1)
def frame(b: bytes):  # already-built instruction packet
    ser.write(b); return ser.read(16)

# PING id 1 → expect FF FF 01 02 00 FC  (healthy)
print(frame(bytes.fromhex("FF FF 01 02 01 FB")).hex(" "))
# READ current position id1 (addr 0x38, len 2) → expect ... 18 05 ... (0x0518=1304)
print(frame(bytes.fromhex("FF FF 01 04 02 38 02 BE")).hex(" "))
```

**Example C — the bring-up loop the handbook actually gates on (single motor):**
see `scripts/bench_ping.py` / `scripts/bench_move.py` and ch07.

## 6.6 ROS 2 integration (next layer)

Your `~/Desktop/s101/ros2_ws` already has `so101_description` + `so101_moveit_config`
(sim-level, URDF with `motor1..motor6`, joint limits, MoveIt) — verified in your repo.
Hardware integration needs a **hardware_interface plugin** that:
1. maps six joints ↔ six STS3215 motor registers,
2. runs the same pair of sync-read/sync-write each cycle,
3. exposes `joint_states` + a `JointGroupEffortController` (position interface).

Nothing official exists in LeRobot for this yet; the cleanest pattern is a
`hardware_interface::SystemInterface` wrapping `pyserial` (or the Feetech SDK) over
`/dev/ttyUSB0`. Design doc: `docs/09-reverse-engineering.md` §bridge-box; write-up left
for the ROS 2 phase of your s101 repo.

## 6.7 Where to learn more

- `~/Desktop/s101` — your ROS 2 sim stack (URDF, MoveIt, Gazebo)
- LeRobot: [docs/installation](https://huggingface.co/docs/lerobot/installation),
  [so101 docs](https://huggingface.co/docs/lerobot/en/so101),
  `src/lerobot/robots/so_follower/` **in your installed checkout** (read it!)
- Waveshare adapter demos (pyserial ping/read): the vendor wiki's Windows/STM32
  samples translate directly.