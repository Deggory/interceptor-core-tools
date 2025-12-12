#!/usr/bin/env python3
"""
Override Threshold Calibration Tool
Helps determine optimal override threshold based on normal vs manual intervention
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
    pattern = r"ADC0:([0-9a-fA-F]+)\s+ADC1:([0-9a-fA-F]+).*Mag:([0-9a-fA-F]+)"
    match = re.search(pattern, line)

    if match:
        adc0 = int(match.group(1), 16)
        adc1 = int(match.group(2), 16)
        magnitude = int(match.group(3), 16)

        return {"adc0": adc0, "adc1": adc1, "magnitude": magnitude}
    return None


def collect_samples(panda, duration, scenario_name):
    """Collect magnitude samples for specified duration"""
    print(f"{CYAN}Collecting samples for {duration} seconds...{RESET}")
    print(f"{YELLOW}{scenario_name}{RESET}\n")

    samples = []
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
                        samples.append(parsed["magnitude"])

                        # Show progress
                        elapsed = time.time() - start_time
                        remaining = duration - elapsed
                        print(
                            f"\r  Samples: {len(samples):4d} | "
                            f"Current magnitude: {parsed['magnitude']:4d} | "
                            f"Time: {remaining:.1f}s  ",
                            end="",
                            flush=True,
                        )
            except:
                pass

        time.sleep(0.01)

    print(f"\n{GREEN}✓ Collected {len(samples)} samples{RESET}\n")
    return samples


def analyze_samples(samples, scenario_name):
    """Analyze magnitude samples"""
    if not samples:
        return None

    samples_sorted = sorted(samples)
    count = len(samples)

    min_val = min(samples)
    max_val = max(samples)
    avg_val = sum(samples) / count
    median_val = samples_sorted[count // 2]

    # Calculate percentiles
    p95 = samples_sorted[int(count * 0.95)]
    p99 = samples_sorted[int(count * 0.99)]

    print(f"{BOLD}{scenario_name} Statistics:{RESET}")
    print(f"  Minimum: {min_val}")
    print(f"  Maximum: {max_val}")
    print(f"  Average: {avg_val:.1f}")
    print(f"  Median: {median_val}")
    print(f"  95th percentile: {p95}")
    print(f"  99th percentile: {p99}\n")

    return {
        "min": min_val,
        "max": max_val,
        "avg": avg_val,
        "median": median_val,
        "p95": p95,
        "p99": p99,
    }


def recommend_threshold(normal_stats, intervention_stats):
    """Recommend override threshold based on collected data"""
    print(f"{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}Override Threshold Recommendation{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}\n")

    # Calculate safe threshold
    # Should be above normal operation but below manual intervention
    normal_max = normal_stats["p99"]  # Use 99th percentile of normal operation
    intervention_min = intervention_stats["min"] if intervention_stats else None

    # Recommended threshold: 150% of normal max, or midpoint if intervention data available
    if intervention_stats:
        # Use midpoint between normal max and intervention min
        recommended = int((normal_max + intervention_min) / 2)

        print(f"{BOLD}Analysis:{RESET}")
        print(f"  Normal operation (99th percentile): {normal_max}")
        print(f"  Manual intervention (minimum): {intervention_min}")
        print(
            f"  Gap between normal and intervention: {intervention_min - normal_max}\n"
        )

        print(
            f"{BOLD}Recommended Threshold:{RESET} {CYAN}{recommended}{RESET} (0x{recommended:X})"
        )
        print(f"  This is the midpoint between normal and intervention\n")

        # Safety margins
        margin_below = recommended - normal_max
        margin_above = intervention_min - recommended

        print(f"{BOLD}Safety Margins:{RESET}")
        if normal_max > 0:
            print(
                f"  Above normal operation: {margin_below} counts ({(margin_below / normal_max) * 100:.1f}%)"
            )
        else:
            print(f"  Above normal operation: {margin_below} counts")

        if intervention_min > 0:
            print(
                f"  Below intervention: {margin_above} counts ({(margin_above / intervention_min) * 100:.1f}%)\n"
            )
        else:
            print(f"  Below intervention: {margin_above} counts\n")

    else:
        # No intervention data, use conservative estimate
        recommended = int(normal_max * 1.5)

        print(f"{BOLD}Analysis:{RESET}")
        print(f"  Normal operation (99th percentile): {normal_max}")
        print(f"  No manual intervention data collected\n")

        print(
            f"{BOLD}Recommended Threshold:{RESET} {CYAN}{recommended}{RESET} (0x{recommended:X})"
        )
        print(f"  This is 150% of normal operation maximum\n")

        print(f"{YELLOW}Note: This is a conservative estimate{RESET}")
        print(
            f"{YELLOW}Run test again with manual intervention for better calibration{RESET}\n"
        )

    # Compare to default
    default_threshold = 336
    print(f"{BOLD}Comparison to Default:{RESET}")
    print(f"  Default threshold: {default_threshold} (0x{default_threshold:X})")
    print(f"  Recommended: {recommended} (0x{recommended:X})")

    if recommended < default_threshold:
        print(f"  {YELLOW}Recommended is lower (more sensitive){RESET}")
    elif recommended > default_threshold:
        print(f"  {YELLOW}Recommended is higher (less sensitive){RESET}")
    else:
        print(f"  {GREEN}Matches default{RESET}")

    print(f"\n{BOLD}Configuration Command:{RESET}")
    print(f"  Run: {CYAN}python3 stm_flash_config.py{RESET}")
    print(f"  Select: System Config")
    print(f"  Set override threshold to: {CYAN}{recommended}{RESET}\n")

    return recommended


def main():
    print(f"{BOLD}{CYAN}")
    print("╔════════════════════════════════════════════════════════╗")
    print("║   Override Threshold Calibration Tool                 ║")
    print("║   Determine optimal threshold for your application    ║")
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

    print(f"{BOLD}Calibration Process:{RESET}")
    print(f"  1. Collect data during NORMAL operation (no manual input)")
    print(f"  2. Collect data during MANUAL INTERVENTION (apply force)")
    print(f"  3. Calculate optimal threshold between the two\n")

    print(f"{BOLD}Step 1: Normal Operation{RESET}")
    print(f"  Keep sensors in typical operating conditions")
    print(f"  Allow normal vibrations, movements, etc.")
    print(f"  Do NOT apply manual force\n")

    input(f"{YELLOW}Press Enter when ready to collect normal operation data...{RESET}")
    print()

    normal_samples = collect_samples(
        panda, duration=15, scenario_name="Scenario: Normal operation (no manual input)"
    )

    if not normal_samples:
        print(f"{RED}✗ No samples collected{RESET}")
        sys.exit(1)

    normal_stats = analyze_samples(normal_samples, "Normal Operation")

    print(f"{BOLD}Step 2: Manual Intervention (Optional but Recommended){RESET}")
    print(f"  Apply the MINIMUM force you want to detect as override")
    print(f"  This represents the threshold of manual intervention\n")

    response = (
        input(f"{YELLOW}Collect manual intervention data? (y/n): {RESET}")
        .strip()
        .lower()
    )

    intervention_stats = None
    if response == "y":
        print()
        print(f"{CYAN}Prepare to apply manual force...{RESET}\n")
        input(
            f"{YELLOW}Press Enter when ready, then apply force during collection...{RESET}"
        )
        print()

        intervention_samples = collect_samples(
            panda,
            duration=10,
            scenario_name="Scenario: Manual intervention (apply force)",
        )

        if intervention_samples:
            intervention_stats = analyze_samples(
                intervention_samples, "Manual Intervention"
            )

    # Recommend threshold
    recommended = recommend_threshold(normal_stats, intervention_stats)

    print(f"{BOLD}Next Steps:{RESET}")
    print(f"  1. Run: {CYAN}python3 stm_flash_config.py{RESET}")
    print(f"  2. Select Interceptor Core device")
    print(f"  3. Configure System Config")
    print(f"  4. Set override threshold to: {CYAN}{recommended}{RESET}")
    print(f"  5. Test with: {CYAN}./test_override_threshold.py{RESET}\n")


if __name__ == "__main__":
    main()
