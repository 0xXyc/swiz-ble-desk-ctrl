# SWIZ BLE Desk CTRL

> Your IKEA desk has zero security.

A BLE security research tool demonstrating zero-authentication control of IKEA IDASEN and other Linak-based standing desks. No pairing, app, or PIN. Just two bytes and your desk moves!

## The Vulnerability... or a Feature...

The Linak BLE motor controller inside millions of standing desks exposes GATT services with **zero authentication**. Any BLE-capable device within ~30 feet can:

- Connect without pairing or user confirmation
- Read the desk's exact height in real-time
- Send motor commands to raise or lower the desk
- No encryption, no allowlisting, no notification to the owner

This is not a software bug -- it's a design decision. The Linak BLE protocol has no authentication mechanism at all.

## Affected Devices

Any standing desk using a Linak BLE motor controller, including:

- **IKEA IDASEN** (confirmed)
- **Autonomous SmartDesk**
- **Uplift Desk**
- **Fully Jarvis**
- **FlexiSpot** (select models)

If your desk advertises BLE service UUID `99FA0001-338A-1024-8A49-009C0215F78A`, it's vulnerable.

## Installation

```bash
git clone https://github.com/0xXyc/swiz-ble-desk-ctrl.git
cd swiz-ble-desk-ctrl
pip install bleak
```

Requires Python 3.8+ and a BLE-capable device (built-in Bluetooth on Mac/Linux/Windows works).

## Usage

```
python3 desk_control.py <command> [options]
```

### Commands

| Command | Description |
|---------|-------------|
| `scan` | Discover Linak desks in BLE range |
| `status` | Read current desk height |
| `up [inches]` | Move desk up (default: 1 inch) |
| `down [inches]` | Move desk down (default: 1 inch) |
| `nudge` | Quick up-then-back demo |
| `hydraulics [seconds] [inches]` | Bounce mode (default: 10s, 3in) |
| `enumerate` | Full GATT service enumeration |
| `monitor` | Live height tracking |

### Examples

```bash
# Find nearby desks
python3 desk_control.py scan

# Check your desk's height
python3 desk_control.py status

# Move up 5 inches
python3 desk_control.py up 5

# Move down 3 inches
python3 desk_control.py down 3

# Gentle demo -- nudge up then back
python3 desk_control.py nudge

# Hydraulics mode -- bounce 3 inches for 10 seconds
python3 desk_control.py hydraulics 10 3

# Full GATT service dump
python3 desk_control.py enumerate

# Watch height in real-time
python3 desk_control.py monitor
```

## BLE Protocol

### Service UUIDs

| Service | UUID | Purpose |
|---------|------|---------|
| Control | `99fa0001-338a-1024-8a49-009c0215f78a` | Motor commands |
| DPG | `99fa0010-338a-1024-8a49-009c0215f78a` | Capabilities |
| Position | `99fa0020-338a-1024-8a49-009c0215f78a` | Height reporting |
| Reference | `99fa0030-338a-1024-8a49-009c0215f78a` | Stop control |

### Motor Commands

| Command | Bytes | Description |
|---------|-------|-------------|
| UP | `0x47 0x00` | Move desk up |
| DOWN | `0x46 0x00` | Move desk down |
| STOP | `0xFF 0x00` | Stop movement |

Commands must be sent repeatedly (~100ms interval) to sustain movement. Single commands produce only ~0.5cm of movement. This is the only safety mechanism in the protocol.

### Height Data

Read characteristic `99fa0021` for a 4-byte little-endian integer:

```
Raw bytes: BE 06 00 00
Integer:   0x06BE = 1726
Height:    (1726 / 100) + 62 = 79.3 cm = 31.2 inches
```

## Security Analysis

BLE allows one active connection at a time. If the owner's phone app is connected, an attacker can't connect simultaneously. However:

- Most users don't keep the desk app open
- The app disconnects when backgrounded on most phones
- There is no reconnection priority -- first device to connect wins
- No bonding or trusted device mechanism exists

## Recommended Mitigations

For Linak / IKEA:
1. Require BLE pairing with user confirmation
2. Implement device allowlisting
3. Use BLE Secure Connections (ECDH key exchange)
4. Add a physical BLE disable switch

For users:
1. Disconnect the desk app when not actively adjusting
2. Use the manual buttons on the desk controller instead of BLE
3. Unplug the BLE adapter if your desk has a removable one

## Ubertooth Capture

If you have an Ubertooth One, you can capture the desk's BLE traffic to prove there's no encryption:

```bash
bash desk_capture.sh up 3
```

This starts an Ubertooth BLE capture, moves the desk, then saves the pcap. Open in Wireshark to see the desk's advertisements and traffic in plaintext.

## Research Context

This tool was developed as part of IoT security research. The Linak BLE protocol was originally reverse-engineered by the home automation community for smart home integration. This project reframes the same protocol as a security vulnerability -- the lack of authentication means anyone can control anyone's desk.

### Special Thanks...

- [Linak Desk BLE Spec](https://github.com/anson-vandoren/linak-desk-spec/blob/master/spec.md)
- [ESPHome IDASEN Controller](https://github.com/j5lien/esphome-idasen-desk-controller)
- [LinakDeskApp](https://github.com/anetczuk/LinakDeskApp)

## Disclaimer

This tool is for authorized security research on devices you own. Do not use it against desks you do not own or have explicit permission to test. Unauthorized access to computer systems and devices is illegal.

## License

MIT