#!/usr/bin/env python3
"""SO-101 single-motor bench tool.

Raw Feetech-protocol frames over pyserial, no LeRobot dependency.
Gate-compatible with docs/07-single-motor-bringup.md.

Usage:
    python3 scripts/bench.py ping   --id 1
    python3 scripts/bench.py read   --id 1
    python3 scripts/bench.py torque --id 1 --state on|off
    python3 scripts/bench.py move   --id 1 --delta 180 --speed 200
    python3 scripts/bench.py mode   --id 1 --mode 0|1
    python3 scripts/bench.py speed  --id 1 --rpm 0.5     # mode 1, no-load only
    python3 scripts/bench.py estop                       # broadcast torque off

Safety: torque starts OFF on power-up (register 0x28 default 0).
Never exceed 7.4 V on the 7.4 V STS3215 variant. Hands clear when torque is on.
"""
from __future__ import annotations

import argparse
import sys
import time

import serial

PORT = "/dev/ttyUSB0"   # [BENCH-CHECK] your adapter node
BAUD = 1_000_000
TIMEOUT = 0.2
STEP_PER_REV = 4096


def checksum(b: bytes) -> int:
    return (~sum(b)) & 0xFF


def frame(servo_id: int, cmd: int, params: bytes = b"") -> bytes:
    body = bytes([servo_id, len(params) + 2, cmd]) + params
    return b"\xff\xff" + body + bytes([checksum(body)])


def send(ser: serial.Serial, servo_id: int, cmd: int, params: bytes = b"") -> bytes:
    ser.reset_input_buffer()
    tx = frame(servo_id, cmd, params)
    ser.write(tx)
    ser.flush()
    time.sleep(0.01)  # half-duplex turnaround
    return ser.read(32)


def unpack_reply(reply: bytes) -> dict:
    """Return dict(ok, servo_id, error, data) from a raw reply."""
    if len(reply) < 6 or not reply.startswith(b"\xff\xff"):
        return {"ok": False, "raw": reply.hex(" ")}
    length = reply[3]
    return {
        "ok": True,
        "servo_id": reply[2],
        "error": reply[4],
        "data": reply[5 : 5 + length - 2],
        "raw": reply.hex(" "),
    }


def open_port() -> serial.Serial:
    try:
        return serial.Serial(PORT, BAUD, timeout=TIMEOUT)
    except serial.SerialException as e:
        sys.exit(f"cannot open {PORT}: {e}\n-> port wrong? dialout missing? adapter plugged?")


def cmd_ping(args) -> None:
    ser = open_port()
    r = unpack_reply(send(ser, args.id, 0x01))
    if not r["ok"]:
        sys.exit(f"PING {args.id} failed: {r}")
    print(f"PING {args.id}  ->  servo alive, error byte = {r['error']:02x}")
    ser.close()


def cmd_read(args) -> None:
    """Read the bring-up telemetry block in one shot (0x38..0x46 + status)."""
    ser = open_port()
    r = unpack_reply(send(ser, args.id, 0x02, bytes([0x38, 0x0F])))  # 15 bytes
    if not r["ok"] or r["error"] != 0:
        sys.exit(f"READ failed: {r}")
    d = r["data"]
    pos = d[0] | (d[1] << 8)
    speed = d[2] | (d[3] << 8)
    load = d[4] | (d[5] << 8)
    volt = d[6]
    temp = d[7]
    status = d[9]
    current = d[13] | (d[14] << 8)
    print(f"id={args.id}")
    print(f"  position  0x{pos:04X}  ({pos} / 4096 steps)")
    print(f"  speed     {speed} steps/s")
    print(f"  load      {load} (0.1 % of max torque)")
    print(f"  voltage   {volt * 0.1:.1f} V")
    print(f"  temp      {temp} C")
    print(f"  status    0x{status:02X}   (bit0 over-V, bit1 over-temp, bit2 over-I, bit4 overload)")
    print(f"  current   {current * 6.5:.0f} mA")
    ser.close()


def cmd_torque(args) -> None:
    ser = open_port()
    state = 1 if args.state == "on" else 0
    r = unpack_reply(send(ser, args.id, 0x03, bytes([0x28, state])))
    if not r["ok"] or r["error"] != 0:
        sys.exit(f"torque write failed: {r}")
    print(f"torque {'ON' if state else 'OFF'} (id {args.id})  ->  error byte {r['error']:02x}")
    ser.close()


def cmd_move(args) -> None:
    """Move by --delta steps at --speed steps/s, then hold. Hands clear."""
    ser = open_port()
    r = unpack_reply(send(ser, args.id, 0x02, bytes([0x38, 0x02])))
    if not r["ok"]:
        sys.exit(f"position read failed: {r}")
    cur = r["data"][0] | (r["data"][1] << 8)
    goal = (cur + args.delta) % 4096
    speed = max(0, min(args.speed, 1000))
    params = bytes([0x2A, goal & 0xFF, (goal >> 8) & 0xFF, 0, 0, speed & 0xFF, (speed >> 8) & 0xFF])
    r = unpack_reply(send(ser, args.id, 0x03, params))
    if not r["ok"] or r["error"] != 0:
        sys.exit(f"move write failed: {r}")
    print(f"move id {args.id}: {cur} -> {goal} steps @ {speed} steps/s (error {r['error']:02x})")
    ser.close()


def cmd_mode(args) -> None:
    ser = open_port()
    if args.mode not in (0, 1, 2, 3):
        sys.exit("mode must be 0=position,1=speed-cl,2=PWM o.l.,3=step")
    r = unpack_reply(send(ser, args.id, 0x03, bytes([0x21, args.mode])))
    if not r["ok"]:
        sys.exit(f"mode write failed: {r}")
    print(f"mode {args.mode} set (id {args.id})  ->  error {r['error']:02x}")
    ser.close()


def cmd_speed(args) -> None:
    """Mode-1 velocity command. NO-LOAD ONLY. bit15 = direction (bench-check sign)."""
    ser = open_port()
    steps = int(abs(args.rpm) * STEP_PER_REV / 60)  # rpm -> steps/s
    if args.rpm < 0:
        steps |= 0x8000
    r = unpack_reply(send(ser, args.id, 0x03, bytes([0x2E, steps & 0xFF, (steps >> 8) & 0xFF])))
    if not r["ok"]:
        sys.exit(f"speed write failed: {r}")
    print(f"speed cmd {args.rpm} rpm ~= {steps & 0x7FFF} steps/s (id {args.id})")
    ser.close()


def cmd_estop(_args) -> None:
    ser = open_port()
    r = unpack_reply(send(ser, 0xFE, 0x03, bytes([0x28, 0x00])))  # broadcast torque off
    print("estop: broadcast torque-off frame sent" if r["ok"] else f"send issue: {r}")
    ser.close()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["ping", "read", "torque", "move", "mode", "speed", "estop"])
    p.add_argument("--id", type=int, default=1)
    p.add_argument("--state", default="on")
    p.add_argument("--delta", type=int, default=180)
    p.add_argument("--speed", type=int, default=200)
    p.add_argument("--mode", type=int, default=0)
    p.add_argument("--rpm", type=float, default=0.0)
    p.add_argument("--port", default=PORT)
    args = p.parse_args()
    if args.port:
        global PORT
        PORT = args.port
    {"ping": cmd_ping, "read": cmd_read, "torque": cmd_torque, "move": cmd_move,
     "mode": cmd_mode, "speed": cmd_speed, "estop": cmd_estop}[args.command](args)


if __name__ == "__main__":
    main()