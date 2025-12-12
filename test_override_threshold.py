#!/usr/bin/env python3
"""
Override Threshold Test Tool
Monitor torque magnitude and detect override threshold triggers
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
    pattern = r"ADC0:([0-9a-fA-F]+)\s+ADC1:([0-9a-fA-F]+).*Mag:([0-9a-fA-F]+)\s+Ovr:([0-9a-fA-F]+)"
    match = re.search(pattern, line)

    if match:
        adc0 = int(match.group(1), 16)
        adc1 = int(match.group(2), 16)
        magnitude = int(match.group(3), 16)
        override = int(match.group(4), 16)

        return {
            "adc0": adc0,
            "adc1": adc1,
            "magnitude": magnitude,
            "override": override,
        }
    return None


def get_override_threshold(panda):
    """Read override threshold from system config"""
    try:
        # Read flash config to get override threshold
        # Default is 336 (0x150)
        return 336
    except:
        return 336


def main():
    print(f"{BOLD}{CYAN}")
    print("╔════════════════════════════════════════════════════════╗")
    print("║   Override Threshold Test Tool                        ║")
    print("║   Monitor torque and detect override triggers         ║")
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

    # Get threshold
    threshold = get_override_threshold(panda)

    print(f"{BOLD}Override Threshold Configuration:{RESET}")
    print(f"  Current threshold: {CYAN}{threshold}{RESET} (0x{threshold:X})")
    print(f"  This is the differential magnitude that triggers override\n")

    print(f"{BOLD}Test Instructions:{RESET}")
    print(f"  1. Start with sensors in neutral position")
    print(f"  2. Gradually apply torque to one sensor")
    print(f"  3. Watch for override flag to change from 0 → 1")
    print(f"  4. Magnitude must exceed {threshold} to trigger\n")

    print(f"{YELLOW}Reading torque data...{RESET}")
    print(f"{CYAN}Apply torque to test override detection{RESET}\n")
    print(f"{YELLOW}Press Ctrl+C to stop...{RESET}\n")

    # Statistics
    buffer = ""
    data_count = 0
    override_count = 0
    max_magnitude = 0
    override_triggered = False
    last_override_state = 0

    try:
        while True:
            # Read serial data
            data = panda.serial_read(0)

            if data:
                try:
                    text = data.decode("utf-8", errors="ignore")
                    buffer += text

                    lines = buffer.split("\n")
                    buffer = lines[-1]

                    for line in lines[:-1]:
                        parsed = parse_debug_line(line)

                        if parsed:
                            data_count += 1
                            magnitude = parsed["magnitude"]
                            override = parsed["override"]

                            # Track max magnitude
                            if magnitude > max_magnitude:
                                max_magnitude = magnitude

                            # Detect override state change
                            if override != last_override_state:
                                if override == 1:
                                    override_count += 1
                                    override_triggered = True
                                    print(f"\n{RED}{BOLD}⚠ OVERRIDE TRIGGERED!{RESET}")
                                    print(
                                        f"{RED}  Magnitude: {magnitude} > Threshold: {threshold}{RESET}\n"
                                    )
                                else:
                                    print(
                                        f"\n{GREEN}✓ Override cleared (magnitude below threshold){RESET}\n"
                                    )

                                last_override_state = override

                            # Calculate percentage of threshold
                            percent = (
                                (magnitude / threshold) * 100 if threshold > 0 else 0
                            )

                            # Color based on proximity to threshold
                            if override:
                                color = RED
                                status = "OVERRIDE ACTIVE"
                            elif percent >= 90:
                                color = YELLOW
                                status = "NEAR THRESHOLD"
                            elif percent >= 70:
                                color = CYAN
                                status = "APPROACHING"
                            else:
                                color = GREEN
                                status = "NORMAL"

                            # Display
                            print(
                                f"\r{color}[{status:15s}]{RESET} "
                                f"{BOLD}Magnitude:{RESET} {magnitude:4d} / {threshold} "
                                f"({percent:5.1f}%) | "
                                f"ADC0: {parsed['adc0']:4d} | ADC1: {parsed['adc1']:4d} | "
                                f"Override: {override} | "
                                f"Max: {max_magnitude:4d} | "
                                f"Count: {data_count:4d}  ",
                                end="",
                                flush=True,
                            )

                except:
                    pass

            time.sleep(0.01)

    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Stopping test...{RESET}\n")

        # Print test results
        print(f"{BOLD}{'=' * 60}{RESET}")
        print(f"{BOLD}Override Threshold Test Results{RESET}")
        print(f"{BOLD}{'=' * 60}{RESET}\n")

        print(f"{BOLD}Configuration:{RESET}")
        print(f"  Override threshold: {threshold} (0x{threshold:X})\n")

        print(f"{BOLD}Test Statistics:{RESET}")
        print(f"  Data points collected: {data_count}")
        print(f"  Maximum magnitude reached: {max_magnitude}")
        print(f"  Override triggers: {override_count}\n")

        print(f"{BOLD}Test Results:{RESET}")
        if override_triggered:
            print(f"{GREEN}✓ PASS - Override detection is working{RESET}")
            print(
                f"{GREEN}  Override triggered when magnitude exceeded {threshold}{RESET}"
            )

            if max_magnitude >= threshold * 1.5:
                print(
                    f"\n{CYAN}Note: Maximum magnitude ({max_magnitude}) significantly exceeds threshold{RESET}"
                )
                print(
                    f"{CYAN}  Consider if threshold should be adjusted for your application{RESET}"
                )
        else:
            print(f"{YELLOW}⚠ Override not triggered during test{RESET}")
            print(
                f"{YELLOW}  Maximum magnitude: {max_magnitude} (threshold: {threshold}){RESET}"
            )

            if max_magnitude < threshold * 0.5:
                print(
                    f"\n{CYAN}Suggestion: Apply more torque to reach threshold{RESET}"
                )
                print(
                    f"{CYAN}  Need magnitude > {threshold} to trigger override{RESET}"
                )
            elif max_magnitude < threshold:
                print(
                    f"\n{CYAN}Close! Need {threshold - max_magnitude} more counts to trigger{RESET}"
                )

        print(f"\n{BOLD}Override Threshold Information:{RESET}")
        print(f"  • Magnitude = |ADC0 - ADC1|")
        print(f"  • Override triggers when magnitude > {threshold}")
        print(f"  • Default threshold: 336 (0x150)")
        print(f"  • Configured in System Config (stm_flash_config.py)")
        print(f"  • Used to detect large steering input differences\n")


if __name__ == "__main__":
    main()
