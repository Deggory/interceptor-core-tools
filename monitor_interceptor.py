#!/usr/bin/env python3
"""
Monitor Interceptor Core CAN Output to Chimera
Shows CAN bus ID, torque input, and torque output in real-time
"""

import sys
import time
import struct
from firmware.python import Panda

# Color codes for terminal output
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"

# CAN addresses based on interceptor mode
CAN_DIFFERENTIAL_OUTPUT = 0x301
CAN_GAS_PEDAL_OUTPUT = 0x201

# Mode definitions
MODE_UNCONFIGURED = 0
MODE_DIFFERENTIAL = 1
MODE_GAS_PEDAL = 2

MODE_NAMES = {0: "Unconfigured", 1: "Differential (Torque Interceptor)", 2: "Gas Pedal"}


def parse_differential_can_output(data):
    """
    Parse CAN output from differential mode (0x301)
    Data format from differential.h:
    dat[1-2]: adc_input_0 (torque input sensor 0)
    dat[3-4]: adc_input_1 (torque input sensor 1)
    dat[5]: ctrl_override (override flag)
    dat[6]: reserved
    dat[7]: state (upper nibble) | pkt_idx (lower nibble)
    dat[0]: checksum
    """
    if len(data) < 8:
        return None

    adc_input_0 = data[1] | (data[2] << 8)
    adc_input_1 = data[3] | (data[4] << 8)
    ctrl_override = data[5]
    state = (data[7] >> 4) & 0xF
    pkt_idx = data[7] & 0xF
    checksum = data[0]

    # Calculate torque magnitude (differential between sensors)
    torque_magnitude = abs(int(adc_input_0) - int(adc_input_1))

    return {
        "adc_input_0": adc_input_0,
        "adc_input_1": adc_input_1,
        "torque_input": torque_magnitude,
        "ctrl_override": ctrl_override,
        "state": state,
        "pkt_idx": pkt_idx,
        "checksum": checksum,
    }


def parse_gas_pedal_can_output(data):
    """
    Parse CAN output from gas pedal mode (0x201)
    Similar structure to differential mode
    """
    if len(data) < 6:
        return None

    adc_input_0 = data[1] | (data[2] << 8)
    adc_input_1 = data[3] | (data[4] << 8)

    return {
        "adc_input_0": adc_input_0,
        "adc_input_1": adc_input_1,
        "pedal_position": adc_input_0,  # Primary sensor for gas pedal
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


def connect_to_interceptor():
    """Connect to Interceptor Core device"""
    print(f"{CYAN}Searching for Interceptor Core...{RESET}")

    # List all available devices
    serials = Panda.list()

    if not serials:
        print(f"{RED}No devices found!{RESET}")
        sys.exit(1)

    # Connect to first available device (you can modify this to select specific device)
    try:
        panda = Panda(serial=serials[0])
        print(f"{GREEN}Connected to device: {serials[0]}{RESET}\n")
        return panda
    except Exception as e:
        print(f"{RED}Failed to connect: {e}{RESET}")
        sys.exit(1)


def get_interceptor_mode(panda):
    """Get current interceptor mode"""
    try:
        mode_data = panda._handle.controlRead(Panda.REQUEST_IN, 0xDD, 0, 0, 1)
        if mode_data:
            mode = mode_data[0]
            return mode
    except Exception as e:
        print(f"{YELLOW}Warning: Could not read mode: {e}{RESET}")
    return MODE_UNCONFIGURED


def monitor_can_output(panda, mode):
    """Monitor CAN output from Interceptor Core"""
    print(f"{BOLD}=== Interceptor Core CAN Monitor ==={RESET}")
    print(f"{CYAN}Mode: {MODE_NAMES.get(mode, 'Unknown')}{RESET}")

    if mode == MODE_DIFFERENTIAL:
        print(f"{CYAN}Monitoring CAN ID: 0x{CAN_DIFFERENTIAL_OUTPUT:X}{RESET}")
        expected_can_id = CAN_DIFFERENTIAL_OUTPUT
    elif mode == MODE_GAS_PEDAL:
        print(f"{CYAN}Monitoring CAN ID: 0x{CAN_GAS_PEDAL_OUTPUT:X}{RESET}")
        expected_can_id = CAN_GAS_PEDAL_OUTPUT
    else:
        print(f"{YELLOW}Warning: Unconfigured mode - no CAN output expected{RESET}")
        expected_can_id = None

    print(f"{BOLD}\nPress Ctrl+C to stop...\n{RESET}")

    # Statistics
    total_packets = 0
    last_pkt_idx = None
    output_count = 0
    no_data_counter = 0

    try:
        while True:
            # Receive CAN messages
            can_messages = panda.can_recv()

            if not can_messages:
                no_data_counter += 1
                if no_data_counter >= 100:
                    print(
                        f"{YELLOW}No data received... (ensure Interceptor Core is configured and running){RESET}"
                    )
                    no_data_counter = 0
                time.sleep(0.01)
                continue

            no_data_counter = 0

            # Process each CAN message
            for can_id, timestamp, data, bus in can_messages:
                total_packets += 1

                # Filter for Interceptor Core output messages
                if expected_can_id is not None and can_id == expected_can_id:
                    output_count += 1

                    if mode == MODE_DIFFERENTIAL:
                        parsed = parse_differential_can_output(data)
                        if parsed:
                            # Clear line and print data
                            print(
                                f"\r{GREEN}[CAN ID: 0x{can_id:03X}]{RESET} "
                                f"{BOLD}Torque Input:{RESET} {CYAN}{parsed['torque_input']:4d}{RESET} "
                                f"| {BOLD}ADC0:{RESET} {parsed['adc_input_0']:4d} "
                                f"| {BOLD}ADC1:{RESET} {parsed['adc_input_1']:4d} "
                                f"| {BOLD}Override:{RESET} {parsed['ctrl_override']} "
                                f"| {BOLD}State:{RESET} {get_state_name(parsed['state'])} "
                                f"| {BOLD}Pkt:{RESET} {parsed['pkt_idx']} "
                                f"| {BOLD}Count:{RESET} {output_count}",
                                end="",
                                flush=True,
                            )
                            last_pkt_idx = parsed["pkt_idx"]

                    elif mode == MODE_GAS_PEDAL:
                        parsed = parse_gas_pedal_can_output(data)
                        if parsed:
                            print(
                                f"\r{GREEN}[CAN ID: 0x{can_id:03X}]{RESET} "
                                f"{BOLD}Pedal Position:{RESET} {CYAN}{parsed['pedal_position']:4d}{RESET} "
                                f"| {BOLD}ADC0:{RESET} {parsed['adc_input_0']:4d} "
                                f"| {BOLD}ADC1:{RESET} {parsed['adc_input_1']:4d} "
                                f"| {BOLD}Count:{RESET} {output_count}",
                                end="",
                                flush=True,
                            )

                # Show all CAN traffic if in debug mode
                # Uncomment the following line to see all CAN messages:
                # print(f"  [0x{can_id:03X}] Bus: {bus}, Data: {data.hex()}")

            time.sleep(0.001)

    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Monitoring stopped by user{RESET}")
        print(f"\n{BOLD}Statistics:{RESET}")
        print(f"  Total CAN packets received: {total_packets}")
        print(f"  Interceptor output packets: {output_count}")
        if output_count > 0:
            print(f"{GREEN}✓ Interceptor Core is outputting data to Chimera{RESET}")
        else:
            print(f"{RED}✗ No Interceptor Core output detected{RESET}")
            print(f"{YELLOW}  Make sure:{RESET}")
            print(
                f"    - Interceptor Core is properly configured (run stm_flash_config.py)"
            )
            print(f"    - System config has 'can_out_en' set to 1")
            print(f"    - Mode is set to Differential or Gas Pedal")


def main():
    """Main function"""
    print(f"{BOLD}{CYAN}")
    print("╔════════════════════════════════════════════════════════╗")
    print("║   Interceptor Core → Chimera CAN Monitor              ║")
    print("║   Monitor torque input and output data                ║")
    print("╚════════════════════════════════════════════════════════╝")
    print(f"{RESET}\n")

    # Connect to device
    panda = connect_to_interceptor()

    # Get current mode
    mode = get_interceptor_mode(panda)

    # Monitor CAN output
    monitor_can_output(panda, mode)


if __name__ == "__main__":
    main()
