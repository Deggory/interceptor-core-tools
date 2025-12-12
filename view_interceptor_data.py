#!/usr/bin/env python3
"""
View Interceptor Core data via serial debug output
This bypasses CAN bus issues and reads data directly from debug UART
"""

import sys
import time
import re
from firmware.python import Panda

# Colors
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"


def parse_debug_line(line):
    """Parse debug output line from Interceptor Core"""
    # Example: ADC0:00000620 ADC1:00000608 DAC0:00000800 DAC1:00000800 Relay:00000000 State:0000000b ...

    pattern = r"ADC0:([0-9a-fA-F]+)\s+ADC1:([0-9a-fA-F]+)\s+DAC0:([0-9a-fA-F]+)\s+DAC1:([0-9a-fA-F]+)\s+Relay:([0-9a-fA-F]+)\s+State:([0-9a-fA-F]+)\s+Mag:([0-9a-fA-F]+)\s+Ovr:([0-9a-fA-F]+)"

    match = re.search(pattern, line)
    if match:
        adc0 = int(match.group(1), 16)
        adc1 = int(match.group(2), 16)
        dac0 = int(match.group(3), 16)
        dac1 = int(match.group(4), 16)
        relay = int(match.group(5), 16)
        state = int(match.group(6), 16)
        mag = int(match.group(7), 16)
        ovr = int(match.group(8), 16)

        return {
            "adc0": adc0,
            "adc1": adc1,
            "dac0": dac0,
            "dac1": dac1,
            "relay": relay,
            "state": state,
            "torque_magnitude": mag,
            "override": ovr,
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


def main():
    print(f"{BOLD}{CYAN}")
    print("╔═══════════════════════════════════════════════════════╗")
    print("║   Interceptor Core Data Viewer (via Debug UART)      ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print(f"{RESET}\n")

    print(f"{CYAN}Connecting to Interceptor Core...{RESET}")
    serials = Panda.list()

    if not serials:
        print(f"{RED}No devices found!{RESET}")
        sys.exit(1)

    panda = Panda(serial=serials[0])
    print(f"{GREEN}✓ Connected: {serials[0]}{RESET}\n")

    print(f"{YELLOW}Reading debug serial output...{RESET}")
    print(f"{BOLD}This shows the ACTUAL internal state of the Interceptor Core{RESET}")
    print(f"{CYAN}(No CAN bus required - direct from firmware debug output){RESET}\n")
    print(f"{YELLOW}Press Ctrl+C to stop...{RESET}\n")

    data_count = 0
    buffer = ""

    try:
        while True:
            # Read serial data from debug UART (port 0)
            data = panda.serial_read(0)

            if data:
                try:
                    text = data.decode("utf-8", errors="ignore")
                    buffer += text

                    # Process complete lines
                    lines = buffer.split("\n")
                    buffer = lines[-1]  # Keep incomplete line

                    for line in lines[:-1]:
                        # Parse debug line
                        parsed = parse_debug_line(line)

                        if parsed:
                            data_count += 1

                            # Calculate torque input (differential)
                            torque_input = abs(parsed["adc0"] - parsed["adc1"])

                            # Display
                            print(
                                f"\r{GREEN}[#{data_count:4d}]{RESET} "
                                f"{BOLD}Torque Input:{RESET} {CYAN}{torque_input:4d}{RESET} "
                                f"({BOLD}ADC0:{RESET}{parsed['adc0']:4d} {BOLD}ADC1:{RESET}{parsed['adc1']:4d}) → "
                                f"{BOLD}Torque Out:{RESET} {CYAN}{parsed['dac0']:4d}, {parsed['dac1']:4d}{RESET} | "
                                f"{BOLD}Relay:{RESET} {parsed['relay']} | "
                                f"{BOLD}State:{RESET} {get_state_name(parsed['state'])}  ",
                                end="",
                                flush=True,
                            )
                        else:
                            # Show other debug messages
                            if line.strip() and not line.startswith("ADC"):
                                print(f"\n{YELLOW}{line.strip()}{RESET}")

                except Exception as e:
                    pass  # Ignore decode errors

            time.sleep(0.01)

    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Stopped{RESET}")
        print(f"\n{BOLD}Summary:{RESET}")
        print(f"  Data points received: {data_count}")

        if data_count > 0:
            print(f"\n{GREEN}✓ Interceptor Core is processing sensor data{RESET}")
            print(f"\n{CYAN}Key observations:{RESET}")
            print(f"  • Torque Input = |ADC0 - ADC1| (differential magnitude)")
            print(f"  • Torque Out = DAC0, DAC1 (output control values)")
            print(
                f"  • These values would be sent on CAN ID 0x301 if CAN bus is connected"
            )
        else:
            print(f"\n{RED}No data received from Interceptor Core{RESET}")


if __name__ == "__main__":
    main()
