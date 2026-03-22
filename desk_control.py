#!/usr/bin/env python3
"""
IKEA IDASEN / Linak Standing Desk BLE Controller
Demonstrates zero-authentication BLE control of standing desks.

Usage:
    python3 desk_control.py scan          # Find desks
    python3 desk_control.py status        # Read current height
    python3 desk_control.py up [inches]   # Move up (default 1 inch)
    python3 desk_control.py down [inches] # Move down (default 1 inch)
    python3 desk_control.py nudge         # Tiny nudge up then back (demo)
    python3 desk_control.py hydraulics [seconds] [inches]  # Bounce between two heights (default 10s, 3in)
    python3 desk_control.py enumerate     # Full GATT service enumeration
    python3 desk_control.py monitor       # Live height monitoring
"""

# Please refer to https://github.com/anson-vandoren/linak-desk-spec/blob/master/spec.md for the same spec that I used to create this tool and aid in reverse engineering this smart desk. 

import asyncio
import sys
from bleak import BleakScanner, BleakClient

# Linak BLE UUIDs
SERVICE_UUID = '99fa0001-338a-1024-8a49-009c0215f78a'
COMMAND_UUID = '99fa0002-338a-1024-8a49-009c0215f78a'
STATUS_UUID = '99fa0003-338a-1024-8a49-009c0215f78a'
DPG_UUID = '99fa0011-338a-1024-8a49-009c0215f78a'
HEIGHT_UUID = '99fa0021-338a-1024-8a49-009c0215f78a'
REF_STATUS_UUID = '99fa0029-338a-1024-8a49-009c0215f78a'
REF_INPUT_UUID = '99fa0031-338a-1024-8a49-009c0215f78a'

# Motor commands
CMD_UP = bytearray([0x47, 0x00])
CMD_DOWN = bytearray([0x46, 0x00])
CMD_STOP = bytearray([0xFF, 0x00])

# Height conversion
LINAK_OFFSET_CM = 62.0


def raw_to_cm(raw_bytes):
    raw = int.from_bytes(raw_bytes[:2], 'little')
    return (raw / 100) + LINAK_OFFSET_CM


def raw_to_inches(raw_bytes):
    return raw_to_cm(raw_bytes) / 2.54


def inches_to_units(inches):
    return int(inches * 254)


async def find_desk():
    print('Scanning for Linak desks...')
    devices = await BleakScanner.discover(timeout=10, return_adv=True)
    for addr, (dev, adv) in devices.items():
        name = dev.name or adv.local_name or ''
        if 'desk' in name.lower() or SERVICE_UUID.lower() in [u.lower() for u in (adv.service_uuids or [])]:
            return dev, adv
    return None, None


async def cmd_scan():
    devices = await BleakScanner.discover(timeout=10, return_adv=True)
    found = False
    for addr, (dev, adv) in devices.items():
        name = dev.name or adv.local_name or ''
        if 'desk' in name.lower() or SERVICE_UUID.lower() in [u.lower() for u in (adv.service_uuids or [])]:
            found = True
            print("______________________________________")
            print(f'DESK FOUND: {name}')
            print(f'  Address: {addr}')
            print(f'  RSSI: {adv.rssi} dBm')
            print(f'  TX Power: {adv.tx_power}')
            print(f'  Service UUIDs: {adv.service_uuids}')
            print(f'  Connectable: YES')
            print(f'  Authentication Required: NONE')
            print("______________________________________")
            print()
    if not found:
        print('No desks found. Make sure that you are within range and that the desk is powered on and no other device is connected to it.')


async def cmd_status():
    dev, _ = await find_desk()
    if not dev:
        print('No desk found.')
        return
    async with BleakClient(dev, timeout=20) as client:
        h = await client.read_gatt_char(HEIGHT_UUID)
        print(f'Desk: {dev.name}')
        print(f'Height: {raw_to_cm(h):.1f} cm / {raw_to_inches(h):.1f} inches')
        print(f'Raw: {h.hex()}')


async def cmd_enumerate():
    dev, _ = await find_desk()
    if not dev:
        print('No desk found.')
        return
    print(f'Connecting to {dev.name}...')
    async with BleakClient(dev, timeout=20) as client:
        print(f'Connected: {client.is_connected}')
        print(f'Authentication: NONE REQUIRED')
        print()
        for service in client.services:
            print(f'Service: {service.uuid}')
            print(f'  Description: {service.description}')
            for char in service.characteristics:
                props = ', '.join(char.properties)
                print(f'  Characteristic: {char.uuid}')
                print(f'    Properties: [{props}]')
                if 'read' in char.properties:
                    try:
                        val = await client.read_gatt_char(char.uuid)
                        print(f'    Value: {val.hex()}')
                    except Exception as e:
                        print(f'    Read error: {e}')
            print()


async def cmd_move(direction, inches=1.0):
    dev, _ = await find_desk()
    if not dev:
        print('No desk found.')
        return

    cmd = CMD_UP if direction == 'up' else CMD_DOWN
    units = inches_to_units(inches)

    async with BleakClient(dev, timeout=20) as client:
        h = await client.read_gatt_char(HEIGHT_UUID)
        start = int.from_bytes(h[:2], 'little')
        start_in = ((start / 100) + LINAK_OFFSET_CM) / 2.54
        print(f'Start: {start_in:.1f} inches')

        if direction == 'up':
            target = start + units
        else:
            target = start - units

        print(f'Moving {direction} {inches:.1f} inches...')
        for i in range(200):
            await client.write_gatt_char(COMMAND_UUID, cmd)
            await asyncio.sleep(0.1)
            if i % 5 == 0:
                h = await client.read_gatt_char(HEIGHT_UUID)
                now = int.from_bytes(h[:2], 'little')
                now_in = ((now / 100) + LINAK_OFFSET_CM) / 2.54
                print(f'  {now_in:.1f} inches')
                if direction == 'up' and now >= target:
                    break
                if direction == 'down' and now <= target:
                    break

        await client.write_gatt_char(COMMAND_UUID, CMD_STOP)
        await asyncio.sleep(0.3)
        h = await client.read_gatt_char(HEIGHT_UUID)
        end = int.from_bytes(h[:2], 'little')
        end_in = ((end / 100) + LINAK_OFFSET_CM) / 2.54
        moved = abs(end - start) / 254
        print(f'End: {end_in:.1f} inches (moved {moved:.1f} inches)')


async def cmd_nudge():
    dev, _ = await find_desk()
    if not dev:
        print('No desk found.')
        return

    async with BleakClient(dev, timeout=20) as client:
        h = await client.read_gatt_char(HEIGHT_UUID)
        start = int.from_bytes(h[:2], 'little')
        print(f'Start: {((start/100)+LINAK_OFFSET_CM)/2.54:.1f} inches')

        print('Nudge UP...')
        await client.write_gatt_char(COMMAND_UUID, CMD_UP)
        await asyncio.sleep(0.5)
        await client.write_gatt_char(COMMAND_UUID, CMD_STOP)
        await asyncio.sleep(1)

        h = await client.read_gatt_char(HEIGHT_UUID)
        mid = int.from_bytes(h[:2], 'little')
        print(f'Nudged to: {((mid/100)+LINAK_OFFSET_CM)/2.54:.1f} inches')

        print('Nudge back DOWN...')
        await client.write_gatt_char(COMMAND_UUID, CMD_DOWN)
        await asyncio.sleep(0.5)
        await client.write_gatt_char(COMMAND_UUID, CMD_STOP)
        await asyncio.sleep(0.5)

        h = await client.read_gatt_char(HEIGHT_UUID)
        end = int.from_bytes(h[:2], 'little')
        print(f'Back to: {((end/100)+LINAK_OFFSET_CM)/2.54:.1f} inches')


async def cmd_hydraulics(duration=10.0, bounce_inches=3.0):
    dev, _ = await find_desk()
    if not dev:
        print('No desk found.')
        return

    units = inches_to_units(bounce_inches)

    async with BleakClient(dev, timeout=20) as client:
        h = await client.read_gatt_char(HEIGHT_UUID)
        home = int.from_bytes(h[:2], 'little')
        home_in = ((home / 100) + LINAK_OFFSET_CM) / 2.54
        top = home + units

        print(f'HYDRAULICS MODE')
        print(f'  Base: {home_in:.1f} inches')
        print(f'  Bounce: {bounce_inches:.1f} inches')
        print(f'  Duration: {duration:.0f} seconds')
        print(f'  LET\'S GO!')
        print()

        import time
        start_time = time.time()
        going_up = True

        while (time.time() - start_time) < duration:
            cmd = CMD_UP if going_up else CMD_DOWN
            target = top if going_up else home
            direction = 'UP' if going_up else 'DOWN'
            elapsed = time.time() - start_time
            print(f'  [{elapsed:.1f}s] {direction}')

            for i in range(200):
                if (time.time() - start_time) >= duration:
                    break
                await client.write_gatt_char(COMMAND_UUID, cmd)
                await asyncio.sleep(0.1)
                if i % 3 == 0:
                    h = await client.read_gatt_char(HEIGHT_UUID)
                    now = int.from_bytes(h[:2], 'little')
                    if going_up and now >= target:
                        break
                    if not going_up and now <= target:
                        break

            going_up = not going_up

        # Return to home position
        await client.write_gatt_char(COMMAND_UUID, CMD_STOP)
        print()
        print('Returning to start position...')
        h = await client.read_gatt_char(HEIGHT_UUID)
        now = int.from_bytes(h[:2], 'little')

        if now > home + 50:
            for i in range(200):
                await client.write_gatt_char(COMMAND_UUID, CMD_DOWN)
                await asyncio.sleep(0.1)
                if i % 3 == 0:
                    h = await client.read_gatt_char(HEIGHT_UUID)
                    now = int.from_bytes(h[:2], 'little')
                    if now <= home:
                        break
        elif now < home - 50:
            for i in range(200):
                await client.write_gatt_char(COMMAND_UUID, CMD_UP)
                await asyncio.sleep(0.1)
                if i % 3 == 0:
                    h = await client.read_gatt_char(HEIGHT_UUID)
                    now = int.from_bytes(h[:2], 'little')
                    if now >= home:
                        break

        await client.write_gatt_char(COMMAND_UUID, CMD_STOP)
        h = await client.read_gatt_char(HEIGHT_UUID)
        end_in = ((int.from_bytes(h[:2], 'little') / 100) + LINAK_OFFSET_CM) / 2.54
        print(f'Back to: {end_in:.1f} inches')
        print('HYDRAULICS COMPLETE')


async def cmd_monitor():
    dev, _ = await find_desk()
    if not dev:
        print('No desk found.')
        return

    print(f'Monitoring {dev.name} height (Ctrl+C to stop)...')
    async with BleakClient(dev, timeout=20) as client:
        try:
            while True:
                h = await client.read_gatt_char(HEIGHT_UUID)
                inches = raw_to_inches(h)
                cm = raw_to_cm(h)
                print(f'  {cm:.1f} cm / {inches:.1f} in (raw: {h.hex()})', end='\r')
                await asyncio.sleep(0.5)
        except KeyboardInterrupt:
            print('\nStopped.')


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    print("""
 ███████╗██╗    ██╗██╗███████╗███████╗    
██╔════╝██║    ██║██║╚══███╔╝██╔════╝    
███████╗██║ █╗ ██║██║  ███╔╝ ███████╗    
╚════██║██║███╗██║██║ ███╔╝  ╚════██║    
███████║╚███╔███╔╝██║███████╗███████║    
╚══════╝ ╚══╝╚══╝ ╚═╝╚══════╝╚══════╝    
                                         
██████╗ ██╗     ███████╗                 
██╔══██╗██║     ██╔════╝                 
██████╔╝██║     █████╗                   
██╔══██╗██║     ██╔══╝                   
██████╔╝███████╗███████╗                 
╚═════╝ ╚══════╝╚══════╝                 
                                         
██████╗ ███████╗███████╗██╗  ██╗         
██╔══██╗██╔════╝██╔════╝██║ ██╔╝         
██║  ██║█████╗  ███████╗█████╔╝          
██║  ██║██╔══╝  ╚════██║██╔═██╗          
██████╔╝███████╗███████║██║  ██╗         
╚═════╝ ╚══════╝╚══════╝╚═╝  ╚═╝         
                                         
 ██████╗████████╗██████╗ ██╗             
██╔════╝╚══██╔══╝██╔══██╗██║             
██║        ██║   ██████╔╝██║             
██║        ██║   ██╔══██╗██║             
╚██████╗   ██║   ██║  ██║███████╗        
 ╚═════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝""")

    cmd = sys.argv[1].lower()

    if cmd == 'scan':
        asyncio.run(cmd_scan())
    elif cmd == 'status':
        asyncio.run(cmd_status())
    elif cmd == 'enumerate':
        asyncio.run(cmd_enumerate())
    elif cmd == 'up':
        inches = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
        asyncio.run(cmd_move('up', inches))
    elif cmd == 'down':
        inches = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
        asyncio.run(cmd_move('down', inches))
    elif cmd == 'nudge':
        asyncio.run(cmd_nudge())
    elif cmd == 'hydraulics':
        duration = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
        inches = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0
        asyncio.run(cmd_hydraulics(duration, inches))
    elif cmd == 'monitor':
        asyncio.run(cmd_monitor())
    else:
        print(f'Unknown command: {cmd}')
        print(__doc__)


if __name__ == '__main__':
    main()