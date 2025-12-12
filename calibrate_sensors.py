#!/usr/bin/env python3
"""
Sensor Calibration Tool for Interceptor Core
Collects ADC readings and helps configure proper validation ranges
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
    pattern = r"ADC0:([0-9a-fA-F]+)\s+ADC1:([0-9a-fA-F]+)"
    match = re.search(pattern, line)

    if match:
        adc0 = int(match.group(1), 16)
        adc1 = int(match.group(2), 16)
        return {"adc0": adc0, "adc1": adc1}
    return None


def collect_samples(panda, duration=10):
    """Collect ADC samples for specified duration"""
    print(f"{CYAN}Collecting ADC samples for {duration} seconds...{RESET}")
    print(f"{YELLOW}Please keep sensors in neutral/center position{RESET}\n")

    samples_adc0 = []
    samples_adc1 = []
    buffer = ""
    start_time = time.time()

    while time.time() - start_time < duration:
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
                        samples_adc0.append(parsed["adc0"])
                        samples_adc1.append(parsed["adc1"])

                        # Show progress
                        elapsed = time.time() - start_time
                        remaining = duration - elapsed
                        print(
                            f"\r  Samples: {len(samples_adc0):4d} | "
                            f"ADC0: {parsed['adc0']:4d} | ADC1: {parsed['adc1']:4d} | "
                            f"Time: {remaining:.1f}s  ",
                            end="",
                            flush=True,
                        )
            except:
                pass

        time.sleep(0.01)

    print(f"\n{GREEN}✓ Collected {len(samples_adc0)} samples{RESET}\n")
    return samples_adc0, samples_adc1


def analyze_samples(samples, channel_name):
    """Analyze ADC samples and calculate statistics"""
    if not samples:
        return None

    samples_sorted = sorted(samples)
    count = len(samples)

    min_val = min(samples)
    max_val = max(samples)
    avg_val = sum(samples) / count
    median_val = samples_sorted[count // 2]

    # Calculate standard deviation
    variance = sum((x - avg_val) ** 2 for x in samples) / count
    std_dev = variance**0.5

    # Calculate 95th percentile range (remove outliers)
    p2_5 = samples_sorted[int(count * 0.025)]
    p97_5 = samples_sorted[int(count * 0.975)]

    return {
        "min": min_val,
        "max": max_val,
        "avg": avg_val,
        "median": median_val,
        "std_dev": std_dev,
        "p2_5": p2_5,
        "p97_5": p97_5,
        "range": max_val - min_val,
    }


def recommend_config(stats0, stats1, mode="differential"):
    """Recommend ADC validation configuration"""
    print(f"{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}Calibration Results & Recommendations{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}\n")

    print(f"{BOLD}ADC Channel 0 Statistics:{RESET}")
    print(f"  Center (median): {stats0['median']:.0f}")
    print(f"  Average: {stats0['avg']:.1f}")
    print(f"  Range: {stats0['min']} - {stats0['max']} (span: {stats0['range']})")
    print(f"  Std deviation: {stats0['std_dev']:.1f}")
    print(f"  95% range: {stats0['p2_5']} - {stats0['p97_5']}\n")

    print(f"{BOLD}ADC Channel 1 Statistics:{RESET}")
    print(f"  Center (median): {stats1['median']:.0f}")
    print(f"  Average: {stats1['avg']:.1f}")
    print(f"  Range: {stats1['min']} - {stats1['max']} (span: {stats1['range']})")
    print(f"  Std deviation: {stats1['std_dev']:.1f}")
    print(f"  95% range: {stats1['p2_5']} - {stats1['p97_5']}\n")

    if mode == "differential":
        # For differential mode, use median as center with tolerance
        center0 = int(stats0["median"])
        center1 = int(stats1["median"])

        # Tolerance should cover noise + some margin
        # Use 3x std dev + some margin for safety
        tolerance0 = int(stats0["std_dev"] * 3 + 50)
        tolerance1 = int(stats1["std_dev"] * 3 + 50)

        # Make sure tolerance is at least 100
        tolerance0 = max(tolerance0, 100)
        tolerance1 = max(tolerance1, 100)

        print(f"{BOLD}Recommended Configuration (Differential Mode):{RESET}\n")
        print(f"{CYAN}ADC Channel 0:{RESET}")
        print(f"  Center value (adc1): {center0}")
        print(f"  Tolerance (adc_tolerance): {tolerance0}")
        print(f"  Valid range: {center0 - tolerance0} to {center0 + tolerance0}")
        print(f"  Enable validation (adc_en): 1\n")

        print(f"{CYAN}ADC Channel 1:{RESET}")
        print(f"  Center value (adc1): {center1}")
        print(f"  Tolerance (adc_tolerance): {tolerance1}")
        print(f"  Valid range: {center1 - tolerance1} to {center1 + tolerance1}")
        print(f"  Enable validation (adc_en): 1\n")

        print(f"{BOLD}Configuration Commands:{RESET}\n")
        print(f"{YELLOW}Run: python3 stm_flash_config.py{RESET}")
        print(f"Then configure ADC Channel 0 with:")
        print(f"  adc1 (center): {center0}")
        print(f"  adc2: 0")
        print(f"  adc_tolerance: {tolerance0}")
        print(f"  Enable: 1\n")
        print(f"Then configure ADC Channel 1 with:")
        print(f"  adc1 (center): {center1}")
        print(f"  adc2: 0")
        print(f"  adc_tolerance: {tolerance1}")
        print(f"  Enable: 1\n")

        return {
            "adc0_center": center0,
            "adc0_tolerance": tolerance0,
            "adc1_center": center1,
            "adc1_tolerance": tolerance1,
        }


def main():
    print(f"{BOLD}{CYAN}")
    print("╔════════════════════════════════════════════════════════╗")
    print("║   Interceptor Core Sensor Calibration Tool            ║")
    print("║   Collect ADC data and configure validation ranges    ║")
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

    # Get current mode
    try:
        mode_data = panda._handle.controlRead(Panda.REQUEST_IN, 0xDD, 0, 0, 1)
        mode = mode_data[0] if mode_data else 1
        mode_names = {0: "Unconfigured", 1: "Differential", 2: "Gas Pedal"}
        print(f"{CYAN}Current mode: {mode_names.get(mode, 'Unknown')}{RESET}\n")
    except:
        mode = 1
        print(f"{YELLOW}Could not read mode, assuming Differential{RESET}\n")

    print(f"{BOLD}Calibration Process:{RESET}")
    print(f"  1. Keep sensors in neutral/center position")
    print(f"  2. Script will collect ADC readings for 10 seconds")
    print(f"  3. Statistics will be calculated")
    print(f"  4. Recommended configuration will be displayed\n")

    input(f"{YELLOW}Press Enter when sensors are in neutral position...{RESET}")
    print()

    # Collect samples
    samples_adc0, samples_adc1 = collect_samples(panda, duration=10)

    if not samples_adc0 or not samples_adc1:
        print(f"{RED}✗ No samples collected{RESET}")
        print(
            f"{YELLOW}Make sure Interceptor Core is running and outputting debug data{RESET}"
        )
        sys.exit(1)

    # Analyze
    stats0 = analyze_samples(samples_adc0, "ADC0")
    stats1 = analyze_samples(samples_adc1, "ADC1")

    # Recommend configuration
    config = recommend_config(stats0, stats1, mode="differential")

    print(f"\n{BOLD}Next Steps:{RESET}")
    print(f"  1. Run: {CYAN}python3 stm_flash_config.py{RESET}")
    print(f"  2. Select Interceptor Core device")
    print(f"  3. Choose option 1 (Configure device)")
    print(f"  4. Configure ADC Channel 0 with values above")
    print(f"  5. Configure ADC Channel 1 with values above")
    print(f"  6. Test with: {CYAN}./view_interceptor_data.py{RESET}")
    print(f"     (State should change from FAULT to NO_FAULT)\n")


if __name__ == "__main__":
    main()
