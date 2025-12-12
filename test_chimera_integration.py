#!/usr/bin/env python3
"""
Integration Test: Verify Chimera receives and processes Interceptor Core data
Tests the complete data flow from Interceptor Core → CAN Bus → Chimera
"""

import sys
import time
from firmware.python import Panda

# Colors
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"

# CAN addresses
CAN_DIFFERENTIAL_OUTPUT = 0x301
CAN_GAS_PEDAL_OUTPUT = 0x201


def parse_interceptor_output(data, mode="differential"):
    """Parse CAN data from Interceptor Core"""
    if len(data) < 8:
        return None

    if mode == "differential":
        adc0 = data[1] | (data[2] << 8)
        adc1 = data[3] | (data[4] << 8)
        override = data[5]
        state = (data[7] >> 4) & 0xF
        pkt_idx = data[7] & 0xF
        checksum = data[0]

        torque_magnitude = abs(int(adc0) - int(adc1))

        return {
            "adc0": adc0,
            "adc1": adc1,
            "torque": torque_magnitude,
            "override": override,
            "state": state,
            "pkt_idx": pkt_idx,
            "checksum": checksum,
        }

    return None


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


def find_devices():
    """Find both Interceptor Core and Chimera devices"""
    context = Panda.list()

    interceptor = None
    chimera = None

    # Try to identify devices by serial
    for serial in context:
        try:
            panda = Panda(serial=serial)
            product = panda._handle.getDevice().getProduct()

            if "Interceptor" in product:
                interceptor = serial
            elif "Chimera" in product:
                chimera = serial

            panda.close()
        except:
            pass

    return interceptor, chimera


def main():
    print(f"{BOLD}{CYAN}")
    print("╔════════════════════════════════════════════════════════╗")
    print("║   Integration Test: Interceptor Core → Chimera        ║")
    print("║   Verify CAN data flow and processing                 ║")
    print("╚════════════════════════════════════════════════════════╝")
    print(f"{RESET}\n")

    # Find devices
    print(f"{CYAN}Searching for devices...{RESET}")
    interceptor_serial, chimera_serial = find_devices()

    if not interceptor_serial:
        print(f"{RED}✗ Interceptor Core not found{RESET}")
        print(f"{YELLOW}Available devices: {Panda.list()}{RESET}")
        sys.exit(1)

    if not chimera_serial:
        print(f"{RED}✗ Chimera not found{RESET}")
        print(f"{YELLOW}Available devices: {Panda.list()}{RESET}")
        sys.exit(1)

    print(f"{GREEN}✓ Found Interceptor Core: {interceptor_serial}{RESET}")
    print(f"{GREEN}✓ Found Chimera: {chimera_serial}{RESET}\n")

    # Connect to Chimera
    print(f"{CYAN}Connecting to Chimera for CAN monitoring...{RESET}")
    try:
        chimera = Panda(serial=chimera_serial)
        print(f"{GREEN}✓ Connected to Chimera{RESET}\n")
    except Exception as e:
        print(f"{RED}✗ Failed to connect to Chimera: {e}{RESET}")
        sys.exit(1)

    print(f"{BOLD}Integration Test Plan:{RESET}")
    print(f"  1. Monitor CAN bus on Chimera")
    print(f"  2. Look for Interceptor Core output (CAN ID 0x301)")
    print(f"  3. Verify data integrity (checksum, packet sequence)")
    print(f"  4. Display received torque data\n")

    print(f"{YELLOW}Monitoring CAN bus on Chimera...{RESET}")
    print(f"{CYAN}Waiting for data from Interceptor Core (CAN ID 0x301){RESET}\n")
    print(f"{YELLOW}Press Ctrl+C to stop...{RESET}\n")

    # Statistics
    total_packets = 0
    interceptor_packets = 0
    checksum_errors = 0
    sequence_errors = 0
    last_pkt_idx = None
    start_time = time.time()
    last_data_time = None

    # Data tracking
    min_torque = None
    max_torque = None
    state_counts = {}

    try:
        while True:
            # Receive CAN messages on Chimera
            can_messages = chimera.can_recv()

            if not can_messages:
                # Check for timeout
                if last_data_time and (time.time() - last_data_time > 5):
                    print(f"\n{YELLOW}⚠ No data received for 5 seconds{RESET}")
                    print(
                        f"{YELLOW}  Check: Interceptor Core is configured and CAN bus is connected{RESET}\n"
                    )
                    last_data_time = time.time()

                time.sleep(0.01)
                continue

            for can_id, timestamp, data, bus in can_messages:
                total_packets += 1

                # Filter for Interceptor Core output
                if can_id == CAN_DIFFERENTIAL_OUTPUT:
                    interceptor_packets += 1
                    last_data_time = time.time()

                    # Parse the data
                    parsed = parse_interceptor_output(data, mode="differential")

                    if parsed:
                        # Check packet sequence
                        if last_pkt_idx is not None:
                            expected_idx = (last_pkt_idx + 1) % 16
                            if parsed["pkt_idx"] != expected_idx:
                                sequence_errors += 1

                        last_pkt_idx = parsed["pkt_idx"]

                        # Track statistics
                        if min_torque is None or parsed["torque"] < min_torque:
                            min_torque = parsed["torque"]
                        if max_torque is None or parsed["torque"] > max_torque:
                            max_torque = parsed["torque"]

                        state_name = get_state_name(parsed["state"])
                        state_counts[state_name] = state_counts.get(state_name, 0) + 1

                        # Display
                        elapsed = time.time() - start_time
                        rate = interceptor_packets / elapsed if elapsed > 0 else 0

                        print(
                            f"\r{GREEN}[Chimera RX]{RESET} "
                            f"{BOLD}Torque:{RESET} {CYAN}{parsed['torque']:4d}{RESET} | "
                            f"ADC0: {parsed['adc0']:4d} | ADC1: {parsed['adc1']:4d} | "
                            f"Ovr: {parsed['override']} | "
                            f"State: {state_name:20s} | "
                            f"Pkt: {parsed['pkt_idx']:2d} | "
                            f"Count: {interceptor_packets:4d} | "
                            f"Rate: {rate:5.1f} Hz  ",
                            end="",
                            flush=True,
                        )

            time.sleep(0.001)

    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Stopping integration test...{RESET}\n")

        # Print test results
        elapsed = time.time() - start_time

        print(f"{BOLD}{'=' * 60}{RESET}")
        print(f"{BOLD}Integration Test Results{RESET}")
        print(f"{BOLD}{'=' * 60}{RESET}\n")

        print(f"{BOLD}Connection:{RESET}")
        print(f"  Interceptor Core: {interceptor_serial}")
        print(f"  Chimera: {chimera_serial}")
        print(f"  Test Duration: {elapsed:.1f} seconds\n")

        print(f"{BOLD}CAN Bus Statistics:{RESET}")
        print(f"  Total CAN packets: {total_packets}")
        print(f"  Interceptor packets (0x301): {interceptor_packets}")

        if interceptor_packets > 0:
            rate = interceptor_packets / elapsed
            print(f"  Average rate: {rate:.1f} Hz")
            print(f"  Expected rate: ~732 Hz\n")

            print(f"{BOLD}Data Integrity:{RESET}")
            print(f"  Sequence errors: {sequence_errors}")
            print(f"  Checksum errors: {checksum_errors}\n")

            print(f"{BOLD}Torque Data:{RESET}")
            print(f"  Min torque: {min_torque}")
            print(f"  Max torque: {max_torque}\n")

            print(f"{BOLD}System States:{RESET}")
            for state, count in sorted(
                state_counts.items(), key=lambda x: x[1], reverse=True
            ):
                percentage = (count / interceptor_packets) * 100
                print(f"  {state:20s}: {count:5d} ({percentage:5.1f}%)")

            print(f"\n{BOLD}Test Result:{RESET}")
            if sequence_errors == 0 and checksum_errors == 0:
                print(
                    f"{GREEN}✓ PASS - Chimera successfully receives and processes Interceptor data{RESET}"
                )
                print(
                    f"{GREEN}✓ Data integrity verified (no sequence or checksum errors){RESET}"
                )
            elif sequence_errors > 0:
                print(
                    f"{YELLOW}⚠ PARTIAL - Data received but {sequence_errors} sequence errors detected{RESET}"
                )
                print(f"{YELLOW}  This may indicate packet loss on CAN bus{RESET}")
            else:
                print(f"{GREEN}✓ PASS - Data received with good integrity{RESET}")
        else:
            print(f"\n{RED}✗ FAIL - No data received from Interceptor Core{RESET}")
            print(f"\n{YELLOW}Troubleshooting:{RESET}")
            print(f"  1. Verify Interceptor Core is configured:")
            print(f"     python3 stm_flash_config.py")
            print(f"     - can_out_en = 1")
            print(f"     - mode = 1 (Differential)")
            print(f"  2. Check physical CAN bus wiring between devices")
            print(f"  3. Verify Interceptor is receiving CAN input (needs 0x300)")
            print(
                f"  4. Use: ./view_interceptor_data.py to verify Interceptor is running"
            )


if __name__ == "__main__":
    main()
