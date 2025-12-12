# Interceptor Core Debugging & Monitoring Guide

Complete guide for monitoring and debugging the Interceptor Core data output to Chimera via CAN bus.

---

## Quick Start (Recommended)

### Option 1: View Data Directly (No CAN Required) ✅ **WORKS ALWAYS**

```bash
./view_interceptor_data.py
```

**Best for**: Verifying the Interceptor Core is processing sensor data, even without CAN bus connection.

Shows:
- **Torque Input**: |ADC0 - ADC1| (differential magnitude)
- **Torque Output**: DAC0, DAC1 values  
- **CAN Bus ID**: 0x301 (what would be sent on CAN)
- System state and relay status

### Option 2: Monitor CAN Output (Requires Physical CAN Connection)

```bash
./monitor_interceptor.py
```

**Best for**: Verifying actual CAN bus communication between Interceptor Core and Chimera.

---

## Understanding the Scripts

### 📊 [view_interceptor_data.py](file:///home/d/retropilot/ocelot/view_interceptor_data.py) **(Primary Debug Tool)**

**Purpose**: Read Interceptor Core data directly from debug serial output

**How it works**:
- Bypasses CAN bus completely
- Reads from USB serial debug port (UART)
- Parses debug messages from firmware
- Shows the same data that would be sent on CAN ID 0x301

**When to use**:
- ✅ Testing without physical CAN connection
- ✅ Verifying Interceptor Core is processing sensor data
- ✅ Debugging when CAN bus has issues
- ✅ Always works if USB is connected

**Example output**:
```
[# 150] Torque Input:   12 (ADC0:2048 ADC1:2036) → Torque Out: 2048, 2048 | Relay: 0 | State: NO_FAULT
```

---

### 📡 [monitor_interceptor.py](file:///home/d/retropilot/ocelot/monitor_interceptor.py) **(CAN Monitor)**

**Purpose**: Monitor CAN output from Interceptor Core to Chimera

**How it works**:
- Connects via USB
- Listens for CAN messages on ID 0x301 (differential) or 0x201 (gas pedal)
- Parses and displays torque data

**When to use**:
- ✅ Verifying CAN bus communication
- ✅ Monitoring actual data Chimera receives
- ✅ When physical CAN connection exists

**Requirements**:
- Physical CAN bus wiring between Interceptor Core and Chimera
- CAN transceiver enabled and working
- Interceptor must be receiving CAN input to generate output

---

### 🔧 [test_interceptor.py](file:///home/d/retropilot/ocelot/test_interceptor.py) **(Combined Test)**

**Purpose**: Send CAN input AND monitor output in one process

**How it works**:
- Sends enable commands on CAN 0x300 (input)
- Monitors responses on CAN 0x301 (output)
- Avoids USB conflicts from multiple processes

**When to use**:
- ✅ Testing with CAN bus connected
- ✅ Avoiding USB device conflicts
- ✅ Full end-to-end CAN testing

---

### 📤 [send_test_input.py](file:///home/d/retropilot/ocelot/send_test_input.py) **(CAN Input Sender)**

**Purpose**: Send CAN control commands to activate the Interceptor Core

**How it works**:
- Sends messages on CAN ID 0x300
- Commands: target_0=0, target_1=0, enable=True
- Tells Interceptor Core to activate and output data

**When to use**:
- ✅ Enabling the Interceptor Core via CAN
- ✅ Running alongside monitor_interceptor.py (in separate terminal)

**Note**: Requires physical CAN connection. Use with monitor_interceptor.py in another terminal.

---

### 🔗 [test_chimera_integration.py](file:///home/d/retropilot/ocelot/test_chimera_integration.py) **(Integration Test)**

**Purpose**: Verify end-to-end data flow from Interceptor Core to Chimera

**How it works**:
- Connects to Chimera device
- Monitors CAN bus for Interceptor Core output (0x301)
- Verifies data integrity (checksums, packet sequence)
- Tracks statistics (rate, torque range, states)
- Provides PASS/FAIL test results

**When to use**:
- ✅ Testing complete integration
- ✅ Verifying Chimera receives Interceptor data
- ✅ Validating CAN bus communication
- ✅ Production readiness testing

**Example output**:
```
Integration Test Results
========================================
Connection:
  Interceptor Core: 440048001251333133333633
  Chimera: 3a0044001651333038373636
  Test Duration: 30.0 seconds

CAN Bus Statistics:
  Total CAN packets: 25000
  Interceptor packets (0x301): 22000
  Average rate: 733.3 Hz
  Expected rate: ~732 Hz

Data Integrity:
  Sequence errors: 0
  Checksum errors: 0

✓ PASS - Chimera successfully receives and processes Interceptor data
```

---

### 🧹 [cleanup_usb.sh](file:///home/d/retropilot/ocelot/cleanup_usb.sh) **(USB Cleanup)**

**Purpose**: Kill stale processes holding USB devices

**When to use**:
- ❌ Getting `LIBUSB_ERROR_BUSY [-6]` errors
- ❌ Multiple scripts can't access device
- ❌ Previous scripts left hanging

```bash
./cleanup_usb.sh
```

---

## Common Issues & Solutions

### ❌ Issue 1: `LIBUSB_ERROR_BUSY [-6]`

**Symptom**:
```
exception LIBUSB_ERROR_BUSY [-6]
usb1.USBErrorBusy: LIBUSB_ERROR_BUSY [-6]
```

**Cause**: Multiple processes trying to access the same USB device

**Solution**:
```bash
./cleanup_usb.sh
# OR if that doesn't work:
sudo pkill -9 -f 'stm_flash_config|monitor_interceptor|send_test_input'
```

Then run only ONE script at a time, or use `test_interceptor.py` which combines both.

---

### ❌ Issue 2: `CAN: BAD RECV, RETRYING`

**Symptom**:
```
CAN: BAD RECV, RETRYING
CAN: BAD RECV, RETRYING
...
```

**Cause**: 
- USB device conflict (multiple processes)
- CAN bus not outputting data

**Solution**:
1. Kill stale processes: `./cleanup_usb.sh`
2. Use the debug serial viewer instead: `./view_interceptor_data.py`

---

### ❌ Issue 3: `LIBUSB_ERROR_TIMEOUT [-7]` (CAN Send)

**Symptom**:
```
usb1.USBErrorTimeout: LIBUSB_ERROR_TIMEOUT [-7]
(when trying to send CAN data)
```

**Cause**:
- No physical CAN bus connection
- CAN transceiver not enabled or in error state
- CAN bus wiring issue

**Solution**:
- **For testing**: Use `./view_interceptor_data.py` (doesn't need CAN)
- **For production**: Check physical CAN wiring between Interceptor Core and Chimera
- Verify CAN transceiver is enabled in hardware

---

### ❌ Issue 4: No Data Received

**Symptom**: Monitor shows "No data received..." or no output

**Possible causes**:
1. **Interceptor not configured**
   - Run: `python3 stm_flash_config.py`
   - Set: `can_out_en = 1`
   - Set: Mode to Differential (1) or Gas Pedal (2)

2. **Interceptor not receiving CAN input**
   - Interceptor waits for input on 0x300 before outputting on 0x301
   - Use `test_interceptor.py` or `send_test_input.py` to send input

3. **No physical CAN connection**
   - Use `view_interceptor_data.py` instead (works without CAN)

---

## Data Flow Overview

```
┌─────────────────────────────────────────────────────────┐
│                   Interceptor Core                       │
│                                                          │
│  ADC Sensors (Torque Input)                             │
│     ├─ ADC0 (Channel 0) ──┐                             │
│     └─ ADC1 (Channel 1) ──┼─→ Calculate |ADC0 - ADC1|   │
│                           │                              │
│  Processing               │                              │
│     ├─ Torque Magnitude   │                              │
│     ├─ Override Detection │                              │
│     └─ DAC Output         │                              │
│                           │                              │
│  Output Methods:          │                              │
│     ├─ Debug UART ────────┼─→ view_interceptor_data.py  │
│     └─ CAN Bus (0x301) ───┼─→ monitor_interceptor.py    │
└───────────────────────────┼──────────────────────────────┘
                            │
                            ↓
                    ┌──────────────┐
                    │   Chimera    │
                    │ (CAN Receive)│
                    └──────────────┘
```

---

## CAN Message Format (0x301 - Differential Mode)

| Byte | Field | Description |
|------|-------|-------------|
| 0 | Checksum | CRC8 checksum |
| 1-2 | ADC0 | Torque sensor 0 (16-bit LE) |
| 3-4 | ADC1 | Torque sensor 1 (16-bit LE) |
| 5 | Override | Override flag (0 or 1) |
| 6 | Reserved | Unused |
| 7 | State/Index | State (upper 4 bits) \| Packet index (lower 4 bits) |

**Torque Input** = `|ADC0 - ADC1|` (differential magnitude)

---

## Configuration Checklist

Before monitoring, ensure Interceptor Core is configured:

```bash
python3 stm_flash_config.py
```

**Required settings**:
- ✅ **System Config**:
  - `can_out_en = 1` (enable CAN output)
  - `mode = 1` (Differential) or `2` (Gas Pedal)
  - `iwdg_en = 0` (watchdog disabled for testing)
- ✅ **ADC Channel 0 Validation**: Configured for your sensors
- ✅ **ADC Channel 1 Validation**: Configured for your sensors

---

## Workflow Examples

### Example 1: Quick Test (No CAN Required)

```bash
# Step 1: View internal data
./view_interceptor_data.py
```

**Result**: See torque input/output data directly from firmware

---

### Example 2: Full CAN Testing (With Physical CAN)

```bash
# Step 1: Cleanup
./cleanup_usb.sh

# Step 2: Run combined test
./test_interceptor.py
```

**Result**: Sends CAN commands and monitors CAN responses

---

### Example 3: Separate Input/Output Monitoring

Terminal 1:
```bash
./send_test_input.py
```

Terminal 2:
```bash
./monitor_interceptor.py
```

**Result**: Send CAN input in one terminal, monitor output in another

⚠️ **Warning**: May cause USB conflicts. Use `test_interceptor.py` instead.

---

## System States

| Code | Name | Description |
|------|------|-------------|
| 0 | NO_FAULT | Normal operation |
| 1 | FAULT_BAD_CHECKSUM | CAN checksum error |
| 2 | FAULT_SEND | CAN send error |
| 3 | FAULT_SCE | CAN bus error (transceiver issue) |
| 4 | FAULT_STARTUP | Initial startup state |
| 5 | FAULT_TIMEOUT | No CAN input for 700 cycles |
| 6 | FAULT_SENSOR | ADC sensor validation failed |
| 7 | FAULT_INVALID_CKSUM | Invalid checksum in data |
| 8 | FAULT_ADC_UNCONFIGURED | ADC not configured |
| 9 | FAULT_TIMEOUT_VSS | Vehicle speed timeout |

---

## Technical Details

- **Update Rate**: ~732 Hz (TIM3 interrupt)
- **CAN Speed**: 500 kbps
- **ADC Resolution**: 12-bit (0-4095)
- **Voltage Range**: 0-3.3V (≈0.8mV per count)
- **CAN Input**: 0x300 (differential) or 0x200 (gas pedal)
- **CAN Output**: 0x301 (differential) or 0x201 (gas pedal)

---

## Troubleshooting Decision Tree

```
Can't get data from Interceptor Core?
│
├─ Try: ./view_interceptor_data.py
│  │
│  ├─ ✅ Works? → Interceptor is OK, CAN bus issue
│  │              Check physical CAN wiring
│  │
│  └─ ❌ Fails? → Check USB connection
│                 Run: python3 stm_flash_config.py
│                 Verify configuration
│
├─ Getting LIBUSB_ERROR_BUSY?
│  └─ Run: ./cleanup_usb.sh
│     Then try again
│
└─ CAN: BAD RECV errors?
   └─ Kill other processes
      Use only one script at a time
```

---

## Files Reference

| File | Purpose | When to Use |
|------|---------|-------------|
| `view_interceptor_data.py` | View data via serial | ✅ Always (primary debug tool) |
| `monitor_interceptor.py` | Monitor CAN output | CAN bus connected |
| `test_interceptor.py` | Send input + monitor | CAN testing |
| `send_test_input.py` | Send CAN commands | With monitor in separate terminal |
| `cleanup_usb.sh` | Kill stale processes | USB errors |
| `stm_flash_config.py` | Configure Interceptor | Initial setup |
| `debug_console.py` | Raw debug output | Low-level debugging |

---

## Summary

**Recommended approach**:
1. Start with `./view_interceptor_data.py` to verify Interceptor is working
2. If that works, the Interceptor Core is processing data correctly
3. If CAN monitoring fails, it's a CAN bus/wiring issue, not an Interceptor issue
4. The data shown in `view_interceptor_data.py` is what WOULD be sent on CAN ID 0x301

**Key insight**: The Interceptor Core outputs the same data two ways:
- **Debug UART**: Always available via USB (what `view_interceptor_data.py` reads)
- **CAN Bus**: Only if physically wired and transceiver working (what `monitor_interceptor.py` reads)

Both show the same torque input/output information!
