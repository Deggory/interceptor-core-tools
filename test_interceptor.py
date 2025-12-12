#!/usr/bin/env python3
"""
Combined Interceptor Core Test - Send CAN input and monitor output
This avoids USB conflicts by using a single process for both operations
"""

import sys
import time
import struct
from firmware.python import Panda

# Colors
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"

# CAN addresses
CAN_DIFFERENTIAL_INPUT = 0x300
CAN_DIFFERENTIAL_OUTPUT = 0x301


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


def send_differential_control(
    panda, target_0=0, target_1=0, enable=True, counter=0, lut=None
):
    """Send control message to Interceptor Core"""
    if lut is None:
        lut = generate_crc8_lut()

    data = bytearray(
        [
            0,  # Checksum placeholder
            target_0 & 0xFF,
            (target_0 >> 8) & 0xFF,
            target_1 & 0xFF,
            (target_1 >> 8) & 0xFF,
            ((1 if enable else 0) << 7) | (counter & 0xF),
        ]
    )

    data[0] = calculate_checksum(data[1:6], lut)
    panda.can_send(CAN_DIFFERENTIAL_INPUT, bytes(data), 0)
    return data


def parse_differential_output(data):
    """Parse CAN output from Interceptor Core"""
    if len(data) < 8:
        return None

    adc_input_0 = data[1] | (data[2] << 8)
    adc_input_1 = data[3] | (data[4] << 8)
    ctrl_override = data[5]
    state = (data[7] >> 4) & 0xF
    pkt_idx = data[7] & 0xF

    torque_magnitude = abs(int(adc_input_0) - int(adc_input_1))

    return {
        "adc0": adc_input_0,
        "adc1": adc_input_1,
        "torque": torque_magnitude,
        "override": ctrl_override,
        "state": state,
        "pkt_idx": pkt_idx,
    }


def get_state_name(state):
    """Get human-readable state name"""
    states = {
        0: "NO_FAULT",
        1: "FAULT_BAD_CHECKSUM",
        2: "FAULT_SEND",
        3: "FAULT_SCE",
        4: "FAULT_STARTUP",
        5: "FAULT_TIMEOUT",
        6: "FAULT_SENSOR",
        7: "FAULT_INVALID_CKSUM",
        8: "FAULT_ADC_UNCONFIGURED",
        9: "FAULT_TIMEOUT_VSS",
    }
    return states.get(state, f"UNKNOWN({state})")


def main():
    print(f"{BOLD}{CYAN}")
    print("╔════════════════════════════════════════════════════════╗")
    print("║   Interceptor Core Test - Send Input & Monitor Output ║")
    print("╚════════════════════════════════════════════════════════╝")
    print(f"{RESET}\n")

    # Connect
    print(f"{CYAN}Connecting to Interceptor Core...{RESET}")
    serials = Panda.list()

    if not serials:
        print(f"{RED}No devices found!{RESET}")
        sys.exit(1)

    panda = Panda(serial=serials[0])
    print(f"{GREEN}✓ Connected: {serials[0]}{RESET}\n")

    # Get mode
    try:
        mode_data = panda._handle.controlRead(Panda.REQUEST_IN, 0xDD, 0, 0, 1)
        mode = mode_data[0] if mode_data else 0
        print(
            f"{CYAN}Mode: {['Unconfigured', 'Differential', 'Gas Pedal'][mode]}{RESET}\n"
        )
    except:
        mode = 1
        print(f"{YELLOW}Could not read mode, assuming Differential{RESET}\n")

    print(f"{BOLD}This script will:{RESET}")
    print(f"  1. Send enable commands on CAN 0x300 (input)")
    print(f"  2. Monitor responses on CAN 0x301 (output)")
    print(f"  3. Display torque data in real-time\n")
    print(f"{YELLOW}Press Ctrl+C to stop...{RESET}\n")

    counter = 0
    output_count = 0
    send_count = 0
    lut = generate_crc8_lut()
    last_output_time = time.time()

    try:
        while True:
            # Send enable command
            send_differential_control(
                panda, target_0=0, target_1=0, enable=True, counter=counter, lut=lut
            )
            send_count += 1
            counter = (counter + 1) % 16

            # Try to receive CAN messages
            try:
                can_messages = panda.can_recv()

                for can_id, timestamp, data, bus in can_messages:
                    if can_id == CAN_DIFFERENTIAL_OUTPUT:
                        parsed = parse_differential_output(data)
                        if parsed:
                            output_count += 1
                            last_output_time = time.time()

                            print(
                                f"\r{GREEN}[0x{can_id:03X}]{RESET} "
                                f"{BOLD}Torque:{RESET} {CYAN}{parsed['torque']:4d}{RESET} | "
                                f"ADC0: {parsed['adc0']:4d} | ADC1: {parsed['adc1']:4d} | "
                                f"Ovr: {parsed['override']} | "
                                f"State: {get_state_name(parsed['state'])} | "
                                f"Out: {output_count} | Sent: {send_count}  ",
                                end="",
                                flush=True,
                            )

                # Check if we're getting output
                if time.time() - last_output_time > 5 and output_count == 0:
                    print(
                        f"\n{YELLOW}⚠ No CAN output received yet (sent {send_count} commands){RESET}"
                    )
                    print(
                        f"{YELLOW}  Check: CAN bus wiring, device configuration{RESET}\n"
                    )
                    last_output_time = time.time()

            except Exception as e:
                if "BAD RECV" not in str(e):
                    print(f"\n{RED}Error receiving CAN: {e}{RESET}")

            time.sleep(0.01)  # 100 Hz

    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Stopping...{RESET}")

        # Send disable
        for i in range(5):
            send_differential_control(
                panda, target_0=0, target_1=0, enable=False, counter=counter, lut=lut
            )
            counter = (counter + 1) % 16
            time.sleep(0.01)

        print(f"\n{BOLD}Statistics:{RESET}")
        print(f"  Commands sent: {send_count}")
        print(f"  Outputs received: {output_count}")

        if output_count > 0:
            print(f"{GREEN}✓ Interceptor Core is working!{RESET}")
        else:
            print(f"{RED}✗ No output received from Interceptor Core{RESET}")
            print(f"\n{YELLOW}Troubleshooting:{RESET}")
            print(f"  - Check CAN bus wiring between Interceptor Core and Chimera")
            print(f"  - Verify 'can_out_en = 1' in system config")
            print(f"  - Run: python3 debug_console.py to see firmware debug output")


if __name__ == "__main__":
    main()
