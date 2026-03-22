#!/bin/bash
# Ubertooth BLE capture while controlling the desk
# Usage: bash desk_capture.sh [up|down] [inches]

DIRECTION=${1:-up}
INCHES=${2:-3}

echo "=== Ubertooth + Desk Control ==="
echo "Starting BLE capture..."
ubertooth-btle -f -c /tmp/desk_capture.pcap > /tmp/ubertooth_desk.txt 2>&1 &
UBPID=$!
sleep 3

echo "Moving desk $DIRECTION $INCHES inches..."
python3 desk_control.py $DIRECTION $INCHES

sleep 2
echo "Stopping capture..."
kill $UBPID 2>/dev/null
wait $UBPID 2>/dev/null

echo ""
echo "=== Results ==="
echo "Pcap file: /tmp/desk_capture.pcap"
echo "Raw output: /tmp/ubertooth_desk.txt"
echo "Desk packets captured:"
grep -c "Desk 7849" /tmp/ubertooth_desk.txt
echo ""
echo "Open in Wireshark:"
echo "  open /tmp/desk_capture.pcap"
