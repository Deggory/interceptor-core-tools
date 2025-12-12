#!/usr/bin/env python3
"""
Torque Response Monitor
Send CAN commands and monitor DAC output changes in real-time
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

# CAN addresses
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


def send_can_command(panda, target_0, target_1, enable, counter, lut):
    """Send CAN control command to Interceptor Core"""
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

    try:
        panda.can_send(CAN_DIFFERENTIAL_INPUT, bytes(data), 0)
        return True
    except:
        return False


def parse_debug_line(line):
    """Parse debug output line from Interceptor Core"""
    pattern = r"ADC0:([0-9a-fA-F]+)\s+ADC1:([0-9a-fA-F]+)\s+DAC0:([0-9a-fA-F]+)\s+DAC1:([0-9a-fA-F]+).*Mag:([0-9a-fA-F]+)"
    match = re.search(pattern, line)

    if match:
        return {
            "adc0": int(match.group(1), 16),
            "adc1": int(match.group(2), 16),
            "dac0": int(match.group(3), 16),
            "dac1": int(match.group(4), 16),
            "magnitude": int(match.group(5), 16),
        }
    return None


def main():
    print(f"{BOLD}{CYAN}")
    print("╔════════════════════════════════════════════════════════╗")
    print("║   Torque Response Monitor                             ║")
    print("║   Send CAN commands and monitor DAC output changes    ║")
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

    print(f"{BOLD}Test Scenarios:{RESET}")
    print(f"  1. Neutral (0, 0) - Both targets at 0")
    print(f"  2. Positive torque (+100, -100)")
    print(f"  3. Negative torque (-100, +100)")
    print(f"  4. Large positive (+200, -200)")
    print(f"  5. Large negative (-200, +200)")
    print(f"  6. Return to neutral (0, 0)\n")

    print(f"{YELLOW}This test will cycle through different torque commands{RESET}")
    print(f"{YELLOW}and show how the DAC outputs respond{RESET}\n")

    input(f"{CYAN}Press Enter to start test...{RESET}")
    print()

    # Test scenarios
    scenarios = [
        ("Neutral", 0, 0, 5),
        ("Positive Torque +100", 100, -100, 5),
        ("Negative Torque -100", -100, 100, 5),
        ("Large Positive +200", 200, -200, 5),
        ("Large Negative -200", -200, 200, 5),
        ("Return to Neutral", 0, 0, 5),
    ]

    lut = generate_crc8_lut()
    counter = 0
    buffer = ""

    for scenario_name, target_0, target_1, duration in scenarios:
        print(f"\n{BOLD}{CYAN}{'=' * 60}{RESET}")
        print(f"{BOLD}Scenario: {scenario_name}{RESET}")
        print(f"{CYAN}Command: target_0={target_0:+4d}, target_1={target_1:+4d}{RESET}")
        print(f"{BOLD}{CYAN}{'=' * 60}{RESET}\n")

        # Track DAC changes
        initial_dac0 = None
        initial_dac1 = None
        final_dac0 = None
        final_dac1 = None
        samples = 0

        start_time = time.time()

        while time.time() - start_time < duration:
            # Send CAN command
            success = send_can_command(panda, target_0, target_1, True, counter, lut)
            if not success:
                print(f"{RED}Warning: CAN send failed{RESET}")

            counter = (counter + 1) % 16

            # Read response
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
                            samples += 1

                            # Track initial values
                            if initial_dac0 is None:
                                initial_dac0 = parsed["dac0"]
                                initial_dac1 = parsed["dac1"]

                            # Update final values
                            final_dac0 = parsed["dac0"]
                            final_dac1 = parsed["dac1"]

                            # Calculate changes
                            delta_dac0 = parsed["dac0"] - initial_dac0
                            delta_dac1 = parsed["dac1"] - initial_dac1

                            # Display
                            elapsed = time.time() - start_time
                            remaining = duration - elapsed

                            print(
                                f"\r{GREEN}[{remaining:4.1f}s]{RESET} "
                                f"{BOLD}DAC0:{RESET} {parsed['dac0']:4d} ({delta_dac0:+4d}) | "
                                f"{BOLD}DAC1:{RESET} {parsed['dac1']:4d} ({delta_dac1:+4d}) | "
                                f"{BOLD}ADC:{RESET} {parsed['adc0']:4d}/{parsed['adc1']:4d} | "
                                f"{BOLD}Mag:{RESET} {parsed['magnitude']:3d} | "
                                f"Samples: {samples:3d}  ",
                                end="",
                                flush=True,
                            )

                except:
                    pass

            time.sleep(0.01)

        # Summary for this scenario
        if initial_dac0 is not None and final_dac0 is not None:
            total_change_0 = final_dac0 - initial_dac0
            total_change_1 = final_dac1 - initial_dac1

            print(f"\n\n{BOLD}Scenario Summary:{RESET}")
            print(f"  Command: target_0={target_0:+4d}, target_1={target_1:+4d}")
            print(
                f"  DAC0 change: {initial_dac0} → {final_dac0} ({total_change_0:+4d})"
            )
            print(
                f"  DAC1 change: {initial_dac1} → {final_dac1} ({total_change_1:+4d})"
            )
            print(f"  Samples collected: {samples}")

            # Analyze response
            expected_direction_0 = -1 if target_0 > 0 else (1 if target_0 < 0 else 0)
            expected_direction_1 = 1 if target_1 < 0 else (-1 if target_1 > 0 else 0)

            actual_direction_0 = (
                1 if total_change_0 > 0 else (-1 if total_change_0 < 0 else 0)
            )
            actual_direction_1 = (
                1 if total_change_1 > 0 else (-1 if total_change_1 < 0 else 0)
            )

            if target_0 == 0 and target_1 == 0:
                print(f"  {GREEN}✓ Neutral command - DAC should stabilize{RESET}")
            elif (
                actual_direction_0 == expected_direction_0
                and actual_direction_1 == expected_direction_1
            ):
                print(f"  {GREEN}✓ DAC responded correctly to command{RESET}")
            else:
                print(
                    f"  {YELLOW}⚠ DAC response may not match expected direction{RESET}"
                )
        else:
            print(f"\n{RED}✗ No data received for this scenario{RESET}")

    # Send disable command
    print(f"\n\n{YELLOW}Sending disable command...{RESET}")
    for i in range(5):
        send_can_command(panda, 0, 0, False, counter, lut)
        counter = (counter + 1) % 16
        time.sleep(0.01)

    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}Test Complete{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}\n")

    print(f"{GREEN}✓ Torque response test completed{RESET}")
    print(f"\n{BOLD}Key Observations:{RESET}")
    print(f"  • DAC outputs should change in response to CAN commands")
    print(f"  • Positive target_0 should decrease DAC0, increase DAC1")
    print(f"  • Negative target_0 should increase DAC0, decrease DAC1")
    print(f"  • Neutral (0,0) should return DAC to center values\n")


if __name__ == "__main__":
    main()
