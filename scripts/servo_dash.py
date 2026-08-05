#!/usr/bin/env python3
"""Live web dashboard for an STS3215 servo.

Reads telemetry in a background thread and serves it to a browser page
with position dial, gauges, status bits and control buttons.

Usage:
    python3 scripts/servo_dash.py [--port /dev/ttyACM0] [--baud 1000000]
                                  [--id 1] [--host 127.0.0.1] [--http 8000]

Then open http://127.0.0.1:8000 in your browser.
Never exceed the servo variant's max voltage. Hands clear when torque is on.
"""
from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import serial

BAUD = 1_000_000
TIMEOUT = 0.2
POLL_S = 0.2


def checksum(b: bytes) -> int:
    return (~sum(b)) & 0xFF


def frame(servo_id: int, cmd: int, params: bytes = b"") -> bytes:
    body = bytes([servo_id, len(params) + 2, cmd]) + params
    return b"\xff\xff" + body + bytes([checksum(body)])


def unpack_reply(reply: bytes) -> dict:
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


def parse_telemetry(d: bytes) -> dict:
    pos = d[0] | (d[1] << 8)
    speed = d[2] | (d[3] << 8)
    load = d[4] | (d[5] << 8)
    volt = d[6]
    temp = d[7]
    status = d[9]
    current = d[13] | (d[14] << 8)
    return {
        "position": pos,
        "position_deg": pos / 4096 * 360,
        "speed": speed,
        "load": load,
        "load_pct": load / 10.0,
        "voltage": round(volt * 0.1, 1),
        "temp": temp,
        "status": status,
        "current_ma": round(current * 6.5),
        "status_text": decode_status(status),
    }


def decode_status(s: int) -> list[str]:
    bits = {
        0: "over-voltage",
        1: "over-temperature",
        2: "over-current",
        4: "overload",
    }
    out = []
    for bit, name in bits.items():
        if s & (1 << bit):
            out.append(name)
    return out or ["ok"]


class ServoBus:
    def __init__(self, port: str, baud: int, servo_id: int):
        self.servo_id = servo_id
        self.ser = serial.Serial(port, baud, timeout=TIMEOUT)
        self.lock = threading.Lock()
        self.state = {
            "connected": False,
            "last_read": None,
            "torque": None,
            "log": [],
        }

    def _transaction(self, cmd: int, params: bytes = b"") -> dict:
        with self.lock:
            self.ser.reset_input_buffer()
            self.ser.write(frame(self.servo_id, cmd, params))
            self.ser.flush()
            time.sleep(0.01)
            reply = self.ser.read(32)
        return unpack_reply(reply)

    def ping(self) -> bool:
        r = self._transaction(0x01)
        return r.get("ok", False)

    def read_block(self) -> dict:
        r = self._transaction(0x02, bytes([0x38, 0x0F]))
        if not r.get("ok") or r.get("error") != 0:
            return {}
        return parse_telemetry(r["data"])

    def write_register(self, addr: int, value: int) -> dict:
        return self._transaction(0x03, bytes([addr, value & 0xFF]))

    def set_torque(self, on: bool) -> dict:
        r = self.write_register(0x28, 1 if on else 0)
        if r.get("ok") and r.get("error") == 0:
            self.state["torque"] = on
        return r

    def move_by(self, delta: int, speed: int) -> dict:
        with self.lock:
            self.ser.reset_input_buffer()
            self.ser.write(frame(self.servo_id, 0x02, bytes([0x38, 0x02])))
            self.ser.flush()
            time.sleep(0.01)
            reply = self.ser.read(32)
        r = unpack_reply(reply)
        if not r.get("ok"):
            return r
        cur = r["data"][0] | (r["data"][1] << 8)
        goal = (cur + delta) % 4096
        speed = max(0, min(int(speed), 1000))
        params = bytes([0x2A, goal & 0xFF, (goal >> 8) & 0xFF, 0, 0,
                        speed & 0xFF, (speed >> 8) & 0xFF])
        r = self._transaction(0x03, params)
        if r.get("ok") and r.get("error") == 0:
            self.log(f"move {cur} -> {goal} steps @ {speed} steps/s")
            return {"ok": True, "from": cur, "goal": goal}
        return r

    def estop(self) -> dict:
        with self.lock:
            self.ser.reset_input_buffer()
            self.ser.write(frame(0xFE, 0x03, bytes([0x28, 0x00])))
            self.ser.flush()
        self.state["torque"] = False
        self.log("ESTOP (broadcast torque off)")
        return {"ok": True, "note": "broadcast, no reply expected"}

    def log(self, msg: str) -> None:
        entry = {"t": time.strftime("%H:%M:%S"), "msg": msg}
        self.state["log"].append(entry)
        self.state["log"] = self.state["log"][-50:]


def telemetry_loop(bus: ServoBus) -> None:
    while True:
        try:
            data = bus.read_block()
            if data:
                bus.state["connected"] = True
                bus.state["last_read"] = data
                bus.state["last_read_at"] = time.time()
            else:
                bus.state["connected"] = False
        except serial.SerialException:
            bus.state["connected"] = False
        time.sleep(POLL_S)


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>STS3215 Servo Dashboard</title>
<style>
  :root { --bg:#0d1117; --panel:#161b22; --line:#30363d; --txt:#e6edf3;
          --dim:#8b949e; --ok:#3fb950; --warn:#d29922; --bad:#f85149; --acc:#58a6ff; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:"Segoe UI",system-ui,sans-serif; background:var(--bg); color:var(--txt); }
  header { display:flex; align-items:center; gap:16px; padding:14px 22px; border-bottom:1px solid var(--line); }
  header h1 { font-size:18px; margin:0; }
  .pill { padding:3px 10px; border-radius:999px; font-size:12px; border:1px solid var(--line); }
  .pill.ok { color:var(--ok); border-color:var(--ok); }
  .pill.bad { color:var(--bad); border-color:var(--bad); }
  main { display:grid; grid-template-columns: 380px 1fr; gap:20px; padding:20px 22px; max-width:1200px; margin:0 auto; }
  .panel { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:16px; }
  .panel h2 { font-size:13px; text-transform:uppercase; letter-spacing:.08em; color:var(--dim); margin:0 0 12px; }
  .dialwrap { position:relative; width:260px; margin:0 auto; }
  .dialwrap svg { width:100%; height:auto; display:block; }
  #posText { position:absolute; inset:auto 0 6px 0; text-align:center; }
  #posText .steps { font-size:22px; font-weight:600; }
  #posText .deg { font-size:12px; color:var(--dim); }
  .grid { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-top:14px; }
  .gauge { background:var(--bg); border:1px solid var(--line); border-radius:8px; padding:10px 12px; }
  .gauge .label { font-size:11px; color:var(--dim); text-transform:uppercase; letter-spacing:.05em; }
  .gauge .value { font-size:20px; font-weight:600; margin-top:2px; }
  .gauge .unit { font-size:11px; color:var(--dim); font-weight:400; margin-left:2px; }
  .gauge .bar { height:5px; background:var(--line); border-radius:3px; margin-top:6px; overflow:hidden; }
  .gauge .bar > i { display:block; height:100%; background:var(--acc); border-radius:3px; transition:width .3s; }
  .gauge.warn .value { color:var(--warn); }
  .gauge.bad .value { color:var(--bad); }
  .controls { display:flex; flex-direction:column; gap:12px; }
  .row { display:flex; gap:10px; align-items:center; }
  .row label { font-size:12px; color:var(--dim); width:110px; }
  input[type=number] { flex:1; background:var(--bg); border:1px solid var(--line); color:var(--txt);
    border-radius:6px; padding:8px 10px; font-size:14px; }
  button { background:#21262d; color:var(--txt); border:1px solid var(--line); border-radius:6px;
    padding:9px 14px; font-size:13px; cursor:pointer; }
  button:hover { background:#30363d; }
  button.primary { background:var(--acc); color:#0d1117; border-color:var(--acc); font-weight:600; }
  button.danger { background:var(--bad); color:#fff; border-color:var(--bad); font-weight:600; }
  .logbox { background:var(--bg); border:1px solid var(--line); border-radius:8px; height:170px;
    overflow-y:auto; padding:10px; font-family:monospace; font-size:12px; }
  .logbox div { padding:2px 0; border-bottom:1px dashed var(--line); }
  .logbox .t { color:var(--dim); margin-right:8px; }
  .footer { grid-column:1 / -1; color:var(--dim); font-size:12px; }
  #status { text-transform:capitalize; }
  @media (max-width:900px) { main { grid-template-columns:1fr; } }
</style>
</head>
<body>
<header>
  <h1>STS3215 Servo Dashboard</h1>
  <span class="pill" id="conn">connecting…</span>
  <span class="pill" id="status">status: —</span>
  <span class="pill" id="rail">— V</span>
</header>
<main>
  <section class="panel">
    <h2>Position</h2>
    <div class="dialwrap">
      <svg id="dial" viewBox="0 0 200 120">
        <path id="track" d="M20 105 A80 80 0 0 1 180 105" fill="none" stroke="#30363d" stroke-width="12" stroke-linecap="round"/>
        <path id="arc" d="M20 105 A80 80 0 0 1 180 105" fill="none" stroke="#58a6ff" stroke-width="12" stroke-linecap="round"/>
      </svg>
      <div id="posText"><div class="steps">—</div><div class="deg"></div></div>
    </div>
    <div class="grid">
      <div class="gauge"><div class="label">Speed</div><div class="value" id="speed">—</div><div class="unit">steps/s</div></div>
      <div class="gauge"><div class="label">Load</div><div class="value" id="load">—</div><div class="unit">%</div><div class="bar"><i id="loadBar"></i></div></div>
      <div class="gauge"><div class="label">Current</div><div class="value" id="cur">—</div><div class="unit">mA</div></div>
      <div class="gauge"><div class="label">Temp</div><div class="value" id="temp">—</div><div class="unit">°C</div></div>
      <div class="gauge"><div class="label">Voltage</div><div class="value" id="volt">—</div><div class="unit">V</div></div>
      <div class="gauge"><div class="label">Status</div><div class="value" id="stat2">—</div></div>
    </div>
  </section>

  <section class="panel">
    <h2>Controls</h2>
    <div class="controls">
      <div class="row"><label>Torque</label>
        <button id="tOn" class="primary">Torque ON</button>
        <button id="tOff">Torque OFF</button>
        <button id="estop" class="danger">ESTOP</button>
      </div>
      <div class="row"><label>Delta (steps)</label>
        <input type="number" id="delta" value="100" step="10">
        <button id="moveMinus">−</button>
        <button id="movePlus" class="primary">+</button>
      </div>
      <div class="row"><label>Speed (steps/s)</label>
        <input type="number" id="speedIn" value="200" step="50" min="0" max="1000">
      </div>
      <div class="row"><label>Go to step</label>
        <input type="number" id="absIn" value="2048" min="0" max="4095">
        <button id="goAbs">Go</button>
      </div>
      <h2>Motion log</h2>
      <div class="logbox" id="log"></div>
    </div>
  </section>

  <div class="footer">Raw Feetech protocol over USB · polling 5×/s · position dial is 0–4096 steps</div>
</main>
<script>
const $ = id => document.getElementById(id);
let lastPos = null;

async function action(body) {
  const r = await fetch("/api/action", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body)
  });
  return r.json();
}

async function tick() {
  try {
    const r = await fetch("/api/telemetry");
    const s = await r.json();
    render(s);
  } catch (e) {
    setConn(false);
  }
}

function setConn(ok) {
  const p = $("conn");
  p.textContent = ok ? "connected" : "disconnected";
  p.className = "pill " + (ok ? "ok" : "bad");
}

function dialPath(fromAngle, toAngle) {
  const a0 = fromAngle * Math.PI / 180, a1 = toAngle * Math.PI / 180;
  const x0 = 100 + 80 * Math.cos(a0), y0 = 105 - 80 * Math.sin(a0);
  const x1 = 100 + 80 * Math.cos(a1), y1 = 105 - 80 * Math.sin(a1);
  return `M${x0.toFixed(1)} ${y0.toFixed(1)} A80 80 0 0 1 ${x1.toFixed(1)} ${y1.toFixed(1)}`;
}

function render(s) {
  if (s.connected) {
    setConn(true);
    $("rail").textContent = s.voltage + " V";
    $("speed").textContent = s.speed;
    $("load").textContent = s.load_pct.toFixed(1);
    $("loadBar").style.width = Math.min(100, s.load_pct * 1.5) + "%";
    $("cur").textContent = s.current_ma;
    $("temp").textContent = s.temp;
    $("volt").textContent = s.voltage;
    const st = s.status_text.join(", ");
    $("stat2").textContent = st;
    $("status").textContent = "status: " + st;
    $("status").className = "pill " + (s.status ? "bad" : "ok");
    const pct = s.position / 4096;
    $("posText").querySelector(".steps").textContent = s.position + " steps";
    $("posText").querySelector(".deg").textContent = "= " + s.position_deg.toFixed(1) + "° (0–360)";
    const angle = 180 + pct * 360;
    if (lastPos === null) {
      $("arc").setAttribute("d", dialPath(180, Math.min(angle, 539.9)));
    } else {
      $("arc").setAttribute("d", dialPath(lastPos, angle));
    }
    lastPos = angle;
  } else {
    setConn(false);
  }
  if (s.log) renderLog(s.log);
}

function renderLog(log) {
  const el = $("log");
  el.innerHTML = log.slice().reverse().map(e =>
    `<div><span class="t">${e.t}</span>${escapeHtml(e.msg)}</div>`).join("");
}

function escapeHtml(s) {
  return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

$("tOn").onclick = () => action({type:"torque", state:true});
$("tOff").onclick = () => action({type:"torque", state:false});
$("estop").onclick = () => action({type:"estop"});
$("movePlus").onclick = () => action({type:"move", delta:+$("delta").value, speed:+$("speedIn").value});
$("moveMinus").onclick = () => action({type:"move", delta:-$("delta").value, speed:+$("speedIn").value});
$("goAbs").onclick = () => {
  const goal = +$("absIn").value;
  action({type:"goto", goal, speed:+$("speedIn").value});
};

tick();
setInterval(tick, 200);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    bus: ServoBus = None

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/telemetry":
            st = self.bus.state
            payload = dict(st["last_read"] or {})
            payload.update({
                "connected": bool(st["last_read"]) and st["connected"],
                "torque": st["torque"],
                "log": st["log"],
                "poll_s": POLL_S,
            })
            self._json(payload)
        elif self.path in ("/", "/index.html"):
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/api/action":
            self._json({"error": "not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            self._json({"error": "bad json"}, 400)
            return
        try:
            result = self.dispatch(req)
        except serial.SerialException as e:
            result = {"ok": False, "error": str(e)}
        self._json(result)

    def dispatch(self, req) -> dict:
        t = req.get("type")
        b = self.bus
        if t == "torque":
            r = b.set_torque(bool(req.get("state")))
            if r.get("ok") and r.get("error") == 0:
                b.log("torque " + ("ON" if req["state"] else "OFF"))
                return {"ok": True}
            return {"ok": False, "error": "servo reply " + r.get("raw", "")}
        if t == "estop":
            return b.estop()
        if t == "move":
            return b.move_by(int(req.get("delta", 0)), int(req.get("speed", 200)))
        if t == "goto":
            goal = int(req["goal"]) % 4096
            speed = max(0, min(int(req.get("speed", 200)), 1000))
            params = bytes([0x2A, goal & 0xFF, (goal >> 8) & 0xFF, 0, 0,
                            speed & 0xFF, (speed >> 8) & 0xFF])
            r = b._transaction(0x03, params)
            if r.get("ok") and r.get("error") == 0:
                b.log(f"goto {goal} steps @ {speed} steps/s")
                return {"ok": True, "goal": goal}
            return {"ok": False, "error": "servo reply " + r.get("raw", "")}
        return {"ok": False, "error": f"unknown type {t}"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", default="/dev/ttyACM0")
    ap.add_argument("--baud", type=int, default=BAUD)
    ap.add_argument("--id", type=int, default=1)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--http", type=int, default=8000)
    args = ap.parse_args()

    bus = ServoBus(args.port, args.baud, args.id)
    Handler.bus = bus
    threading.Thread(target=telemetry_loop, args=(bus,), daemon=True).start()

    httpd = ThreadingHTTPServer((args.host, args.http), Handler)
    print(f"servo dashboard: http://{args.host}:{args.http}  (servo id {args.id} on {args.port})")
    print("Ctrl-C to stop (servo returns to torque-off default on power cycle)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            bus.estop()
            print("estop sent")
        except Exception:
            pass


if __name__ == "__main__":
    main()
