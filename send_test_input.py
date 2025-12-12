#!/usr/bin/env python3
"""
Send test CAN input to Interceptor Core
This will trigger the Interceptor to start outputting CAN data
"""

import sys
import time
from firmware.python import Panda

# CAN addresses for differential mode
CAN_DIFFERENTIAL_INPUT = 0x300


def generate_crc8_lut(poly=0x1D):
    """Generate CRC8 lookup table"""
    lut = []
    for i in range(256):
        crc = i
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ poly) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
        lut.append(crc)
    return lut


def calculate_checksum(data, lut):
    """Calculate CRC8 checksum"""
    crc = 0xFF
    for byte in data:
        crc = lut[crc ^ byte]
    return crc ^ 0xFF


def send_differential_control(panda, target_0=0, target_1=0, enable=True, counter=0):
    """
    Send control message to Interceptor Core (differential mode)
    Format matches what the firmware expects on CAN ID 0x300
    """
    lut = generate_crc8_lut()

    # Build the packet (6 bytes for checksum calculation)
    data = bytearray(
        [
            0,  # Placeholder for checksum (byte 0)
            target_0 & 0xFF,  # target_0 low byte
            (target_0 >> 8) & 0xFF,  # target_0 high byte
            target_1 & 0xFF,  # target_1 low byte
            (target_1 >> 8) & 0xFF,  # target_1 high byte
            ((1 if enable else 0) << 7) | (counter & 0xF),  # enable bit + counter
        ]
    )

    # Calculate checksum over bytes 1-5
    data[0] = calculate_checksum(data[1:6], lut)

    # Send on CAN bus 0, address 0x300
    panda.can_send(CAN_DIFFERENTIAL_INPUT, bytes(data), 0)

    return data


def main():
    print("Connecting to Interceptor Core...")
    serials = Panda.list()

    if not serials:
        print("No devices found!")
        sys.exit(1)

    # Connect to first device
    panda = Panda(serial=serials[0])
    print(f"Connected to: {serials[0]}\n")

    print("Sending test CAN input to Interceptor Core...")
    print("This will enable the device and allow it to output CAN data.\n")
    print("Press Ctrl+C to stop...\n")

    counter = 0

    try:
        while True:
            # Send neutral command (0,0) with enable=True
            # This tells the Interceptor we're in control and it should output data
            data = send_differential_control(
                panda,
                target_0=0,  # Start with 0,0 (neutral position)
                target_1=0,
                enable=True,
                counter=counter,
            )

            print(
                f"\rSent packet #{counter:4d}: enable=1, target_0=0, target_1=0, checksum=0x{data[0]:02X}",
                end="",
                flush=True,
            )

            counter = (counter + 1) % 16
            time.sleep(0.01)  # Send at ~100 Hz

    except KeyboardInterrupt:
        print("\n\nStopping CAN input...")

        # Send disable command before exiting
        for i in range(5):
            data = send_differential_control(
                panda, target_0=0, target_1=0, enable=False, counter=counter
            )
            counter = (counter + 1) % 16
            time.sleep(0.01)

        print("Sent disable command. Interceptor Core should stop outputting.")


if __name__ == "__main__":
    main()
