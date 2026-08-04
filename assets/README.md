# assets/

Photographs of **your** unit, expected here per `docs/04-wiring-connectors.md` §4.7.

Status (2026-08-04): **no photos yet** — the arm is physically in the user's hands.
This directory is intentionally empty until the bench session provides images.

## Naming convention (add yours here)

| Prefix | Subject | Example |
|---|---|---|
| `adapter_top_` | adapter board top, jumpers visible | `adapter_top_B_jumpers.jpg` |
| `adapter_power_` | DC5521 + screw terminal wiring | `adapter_power_dc5521.jpg` |
| `servo_pigtail_` | 5264-3P pigtail, pin order labeled | `servo_pigtail_pins.jpg` |
| `loom_chain_` | daisy-chain path through the arm | `loom_chain_top.jpg` |
| `psu_` | bench PSU settings per bring-up gate | `psu_g3_7v4_2a.jpg` |
| `measure_` | multimeter / scope captures | `measure_vbus_port.jpg` |

Each photo should be a JPEG ≤ ~2000 px wide; reference it from the chapters as:

```md
![caption](./assets/<name>.jpg)
```

## Actual pins-per-photo targets (what to shoot during the first bench session)

1. Adapter top-down showing both jumper caps on **B**.
2. Adapter servo port close-up with **D/V/G** silk visible.
3. A servo pigtail connector, pin 1 (GND) side labeled.
4. The bench PSU panel at gate G3 settings (7.40 V, 2 A limit).
5. Meter reading at the adapter servo port V–G = 7.40 V.
6. Full bench layout (host cable, PSU, adapter, fastened single motor).

Drop files here → commit → chapters reference them. Symlinks to camera folders are also
fine; keep a `*.md` note if so.