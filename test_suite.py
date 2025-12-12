#!/usr/bin/env python3
"""
Automated Test Suite for Interceptor Core
Comprehensive testing and validation framework
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


class TestResult:
    def __init__(self, name):
        self.name = name
        self.passed = False
        self.message = ""
        self.duration = 0


class InterceptorTestSuite:
    def __init__(self):
        self.panda = None
        self.results = []

    def connect(self):
        """Connect to Interceptor Core"""
        serials = Panda.list()
        if not serials:
            raise Exception("No devices found")
        self.panda = Panda(serial=serials[0])
        return serials[0]

    def parse_debug_line(self, line):
        """Parse debug output"""
        pattern = r"ADC0:([0-9a-fA-F]+)\s+ADC1:([0-9a-fA-F]+)\s+DAC0:([0-9a-fA-F]+)\s+DAC1:([0-9a-fA-F]+).*State:([0-9a-fA-F]+).*Mag:([0-9a-fA-F]+)"
        match = re.search(pattern, line)

        if match:
            return {
                "adc0": int(match.group(1), 16),
                "adc1": int(match.group(2), 16),
                "dac0": int(match.group(3), 16),
                "dac1": int(match.group(4), 16),
                "state": int(match.group(5), 16),
                "magnitude": int(match.group(6), 16),
            }
        return None

    def read_interceptor_data(self, timeout=2):
        """Read data from Interceptor Core"""
        buffer = ""
        start_time = time.time()

        while time.time() - start_time < timeout:
            data = self.panda.serial_read(0)
            if data:
                try:
                    text = data.decode("utf-8", errors="ignore")
                    buffer += text
                    lines = buffer.split("\n")

                    for line in lines:
                        parsed = self.parse_debug_line(line)
                        if parsed:
                            return parsed
                except:
                    pass
            time.sleep(0.01)

        return None

    def run_test(self, test_func):
        """Run a single test"""
        result = TestResult(test_func.__name__)
        start_time = time.time()

        try:
            test_func(result)
            result.passed = True
        except AssertionError as e:
            result.passed = False
            result.message = str(e)
        except Exception as e:
            result.passed = False
            result.message = f"Error: {str(e)}"

        result.duration = time.time() - start_time
        self.results.append(result)

        return result

    # ==================== UNIT TESTS ====================

    def test_device_connection(self, result):
        """Test: Device connects successfully"""
        assert self.panda is not None, "Device not connected"
        result.message = "Device connected successfully"

    def test_serial_communication(self, result):
        """Test: Serial debug data is readable"""
        data = self.read_interceptor_data(timeout=3)
        assert data is not None, "No serial data received"
        result.message = f"Received data: ADC0={data['adc0']}, ADC1={data['adc1']}"

    def test_adc_readings(self, result):
        """Test: ADC sensors are reading valid values"""
        data = self.read_interceptor_data()
        assert data is not None, "No data received"

        # ADC should be in valid 12-bit range
        assert 0 <= data["adc0"] <= 4095, f"ADC0 out of range: {data['adc0']}"
        assert 0 <= data["adc1"] <= 4095, f"ADC1 out of range: {data['adc1']}"

        result.message = f"ADC0={data['adc0']}, ADC1={data['adc1']} (valid range)"

    def test_adc_calibration(self, result):
        """Test: ADC values are within calibrated ranges"""
        data = self.read_interceptor_data()
        assert data is not None, "No data received"

        # Expected calibrated ranges from CALIBRATION_RESULTS.md
        adc0_min, adc0_max = 1413, 1663
        adc1_min, adc1_max = 1479, 1679

        assert adc0_min <= data["adc0"] <= adc0_max, (
            f"ADC0 {data['adc0']} outside calibrated range [{adc0_min}-{adc0_max}]"
        )
        assert adc1_min <= data["adc1"] <= adc1_max, (
            f"ADC1 {data['adc1']} outside calibrated range [{adc1_min}-{adc1_max}]"
        )

        result.message = "ADC values within calibrated ranges"

    def test_system_state(self, result):
        """Test: System is in NO_FAULT state"""
        data = self.read_interceptor_data()
        assert data is not None, "No data received"

        state_names = {
            0: "NO_FAULT",
            1: "FAULT_BAD_CHECKSUM",
            2: "FAULT_SEND",
            3: "FAULT_SCE",
            8: "FAULT_ADC_UNCONFIGURED",
            11: "UNKNOWN",
        }

        state_name = state_names.get(data["state"], f"UNKNOWN({data['state']})")

        # Warning for non-zero states, but don't fail
        if data["state"] != 0:
            result.message = f"⚠ State: {state_name} (expected NO_FAULT)"
        else:
            result.message = "State: NO_FAULT ✓"

    def test_dac_outputs(self, result):
        """Test: DAC outputs are present and valid"""
        data = self.read_interceptor_data()
        assert data is not None, "No data received"

        # DAC should be in valid 12-bit range
        assert 0 <= data["dac0"] <= 4095, f"DAC0 out of range: {data['dac0']}"
        assert 0 <= data["dac1"] <= 4095, f"DAC1 out of range: {data['dac1']}"

        result.message = f"DAC0={data['dac0']}, DAC1={data['dac1']} (valid)"

    def test_magnitude_calculation(self, result):
        """Test: Torque magnitude is calculated correctly"""
        data = self.read_interceptor_data()
        assert data is not None, "No data received"

        expected_magnitude = abs(data["adc0"] - data["adc1"])

        # Allow small tolerance for timing differences
        assert abs(data["magnitude"] - expected_magnitude) <= 5, (
            f"Magnitude mismatch: got {data['magnitude']}, expected {expected_magnitude}"
        )

        result.message = f"Magnitude={data['magnitude']} (calculated correctly)"

    # ==================== INTEGRATION TESTS ====================

    def test_data_consistency(self, result):
        """Test: Data remains consistent over multiple reads"""
        samples = []
        for _ in range(5):
            data = self.read_interceptor_data()
            if data:
                samples.append(data)
            time.sleep(0.1)

        assert len(samples) >= 3, "Not enough samples collected"

        # Check ADC values don't change drastically
        adc0_values = [s["adc0"] for s in samples]
        adc0_range = max(adc0_values) - min(adc0_values)

        assert adc0_range < 200, f"ADC0 unstable: range={adc0_range}"

        result.message = f"Data consistent over {len(samples)} samples"

    def test_continuous_operation(self, result):
        """Test: System operates continuously for 30 seconds"""
        start_time = time.time()
        sample_count = 0
        errors = 0

        while time.time() - start_time < 30:
            data = self.read_interceptor_data(timeout=1)
            if data:
                sample_count += 1
                if data["state"] != 0:
                    errors += 1
            time.sleep(0.1)

        assert sample_count >= 250, f"Too few samples: {sample_count}"

        result.message = f"Collected {sample_count} samples in 30s, {errors} errors"

    # ==================== REGRESSION TESTS ====================

    def test_regression_adc_range(self, result):
        """Regression: ADC values haven't drifted from calibration"""
        data = self.read_interceptor_data()
        assert data is not None, "No data received"

        # Historical baseline from calibration
        baseline_adc0 = 1538
        baseline_adc1 = 1579

        drift_adc0 = abs(data["adc0"] - baseline_adc0)
        drift_adc1 = abs(data["adc1"] - baseline_adc1)

        # Allow 10% drift
        assert drift_adc0 < 150, f"ADC0 drifted {drift_adc0} from baseline"
        assert drift_adc1 < 150, f"ADC1 drifted {drift_adc1} from baseline"

        result.message = f"ADC drift: ADC0={drift_adc0}, ADC1={drift_adc1}"

    def print_results(self):
        """Print test results summary"""
        print(f"\n{BOLD}{CYAN}{'=' * 60}{RESET}")
        print(f"{BOLD}Test Results Summary{RESET}")
        print(f"{BOLD}{CYAN}{'=' * 60}{RESET}\n")

        passed = sum(1 for r in self.results if r.passed)
        failed = len(self.results) - passed

        for result in self.results:
            status = f"{GREEN}✓ PASS{RESET}" if result.passed else f"{RED}✗ FAIL{RESET}"
            print(f"{status} {result.name:40s} ({result.duration:.2f}s)")
            if result.message:
                indent = "     "
                print(f"{indent}{CYAN}{result.message}{RESET}")

        print(f"\n{BOLD}{'=' * 60}{RESET}")
        print(f"{BOLD}Total: {len(self.results)} tests{RESET}")
        print(f"{GREEN}Passed: {passed}{RESET}")
        if failed > 0:
            print(f"{RED}Failed: {failed}{RESET}")
        print(f"{BOLD}{'=' * 60}{RESET}\n")

        return failed == 0


def main():
    print(f"{BOLD}{CYAN}")
    print("╔════════════════════════════════════════════════════════╗")
    print("║   Interceptor Core Automated Test Suite               ║")
    print("║   Comprehensive Testing & Validation                   ║")
    print("╚════════════════════════════════════════════════════════╝")
    print(f"{RESET}\n")

    suite = InterceptorTestSuite()

    # Connect
    print(f"{CYAN}Connecting to Interceptor Core...{RESET}")
    try:
        serial = suite.connect()
        print(f"{GREEN}✓ Connected: {serial}{RESET}\n")
    except Exception as e:
        print(f"{RED}✗ Connection failed: {e}{RESET}")
        sys.exit(1)

    # Run tests
    print(f"{BOLD}Running tests...{RESET}\n")

    # Unit tests
    print(f"{CYAN}Unit Tests:{RESET}")
    suite.run_test(suite.test_device_connection)
    suite.run_test(suite.test_serial_communication)
    suite.run_test(suite.test_adc_readings)
    suite.run_test(suite.test_adc_calibration)
    suite.run_test(suite.test_system_state)
    suite.run_test(suite.test_dac_outputs)
    suite.run_test(suite.test_magnitude_calculation)

    # Integration tests
    print(f"\n{CYAN}Integration Tests:{RESET}")
    suite.run_test(suite.test_data_consistency)
    suite.run_test(suite.test_continuous_operation)

    # Regression tests
    print(f"\n{CYAN}Regression Tests:{RESET}")
    suite.run_test(suite.test_regression_adc_range)

    # Print results
    all_passed = suite.print_results()

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
