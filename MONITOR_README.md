# Interceptor Core CAN Monitor

Monitor real-time CAN bus communication between Interceptor Core and Chimera.

## Features

- **Real-time CAN monitoring**: See live data output from Interceptor Core
- **CAN Bus ID display**: Shows which CAN address is being used (0x301 for Differential, 0x201 for Gas Pedal)
- **Torque Input**: Displays calculated torque magnitude from differential ADC readings
- **Torque Output**: Shows ADC0 and ADC1 values being sent to Chimera
- **Override detection**: Indicates when torque override is active
- **System state**: Shows current fault status
- **Colored output**: Easy-to-read terminal display with color coding

## Prerequisites

1. **Interceptor Core must be configured** - Run `stm_flash_config.py` first to set:
   - System Config: `can_out_en = 1` (enable CAN output)
   - Mode: Set to either Differential (1) or Gas Pedal (2)
   - ADC validation (optional but recommended)

2. **USB permissions** - Ensure you have USB device access

## Usage

### Basic Monitoring

```bash
./monitor_interceptor.py
```

or

```bash
python3 monitor_interceptor.py
```

### Understanding the Output

#### Differential Mode (CAN ID: 0x301)
```
[CAN ID: 0x301] Torque Input:  250 | ADC0: 2400 | ADC1: 2150 | Override: 0 | State: NO_FAULT | Pkt: 5 | Count: 1234
```

**Fields:**
- **CAN ID**: The CAN bus address (0x301 for differential mode)
- **Torque Input**: Calculated as `|ADC0 - ADC1|` - represents the differential torque magnitude
- **ADC0**: Raw ADC reading from sensor channel 0 (0-4095)
- **ADC1**: Raw ADC reading from sensor channel 1 (0-4095)
- **Override**: 1 if torque override threshold exceeded, 0 otherwise
- **State**: Current system state (NO_FAULT, FAULT_SENSOR, etc.)
- **Pkt**: Packet index (0-15, rolls over)
- **Count**: Total number of output packets received

#### Gas Pedal Mode (CAN ID: 0x201)
```
[CAN ID: 0x201] Pedal Position: 2048 | ADC0: 2048 | ADC1: 2050 | Count: 567
```

**Fields:**
- **Pedal Position**: Primary ADC sensor reading
- **ADC0/ADC1**: Raw sensor values

## Data Flow

```
┌──────────────────────┐
│  Interceptor Core    │
│                      │
│  ADC Input 0 ────────┼──┐
│  ADC Input 1 ────────┼──┼─→ Calculate Torque Magnitude
│                      │  │
│  Torque Processing   │  │
│  ↓                   │  │
│  DAC Output 0        │  │
│  DAC Output 1        │  │
└──────────────────────┘  │
         ↓ CAN Output     │
    (0x301 or 0x201)      │
         ↓                │
┌──────────────────────┐  │
│      Chimera         │  │
│  (Receives CAN data) │←─┘
└──────────────────────┘
```

## CAN Message Format

### Differential Mode (0x301)
| Byte | Description |
|------|-------------|
| 0    | CRC8 Checksum |
| 1    | ADC Input 0 (Low byte) |
| 2    | ADC Input 0 (High byte) |
| 3    | ADC Input 1 (Low byte) |
| 4    | ADC Input 1 (High byte) |
| 5    | Control Override flag |
| 6    | Reserved |
| 7    | State (upper nibble) \| Packet Index (lower nibble) |

### Gas Pedal Mode (0x201)
| Byte | Description |
|------|-------------|
| 0    | CRC8 Checksum |
| 1    | ADC Input 0 (Low byte) |
| 2    | ADC Input 0 (High byte) |
| 3    | ADC Input 1 (Low byte) |
| 4    | ADC Input 1 (High byte) |
| 5    | Reserved |

## Troubleshooting

### No Data Received

If you see "No data received..." repeatedly:

1. **Check Interceptor Core configuration**:
   ```bash
   python3 stm_flash_config.py
   ```
   Ensure:
   - System Config has `can_out_en = 1`
   - Mode is set to 1 (Differential) or 2 (Gas Pedal)

2. **Check mode setting**:
   The script will display current mode at startup. If it shows "Unconfigured", the device won't output CAN data.

3. **Verify USB connection**:
   - Check that the Interceptor Core is connected via USB
   - Verify USB permissions (you may need sudo or udev rules)

### No Devices Found

If you get "No devices found!":
- Check USB cable connection
- Verify device is powered on
- Check USB permissions:
  ```bash
  lsusb | grep bbaa
  ```
  Should show vendor ID 0xbbaa

### Permission Denied

If you get permission errors:
```bash
sudo ./monitor_interceptor.py
```

Or set up udev rules for permanent access.

## System States

| State Code | Name | Description |
|------------|------|-------------|
| 0 | NO_FAULT | Normal operation |
| 1 | FAULT_BAD_CHECKSUM | CAN checksum error |
| 2 | FAULT_SEND | CAN send error |
| 3 | FAULT_SCE | CAN bus error |
| 4 | FAULT_STARTUP | Initial startup state |
| 5 | FAULT_TIMEOUT | No CAN input received |
| 6 | FAULT_SENSOR | ADC sensor fault |
| 7 | FAULT_INVALID_CKSUM | Invalid checksum |
| 8 | FAULT_ADC_UNCONFIGURED | ADC not configured |
| 9 | FAULT_TIMEOUT_VSS | Vehicle speed timeout |

## Technical Details

- **Update Rate**: ~732 Hz (controlled by TIM3 interrupt)
- **CAN Speed**: 500 kbps
- **ADC Resolution**: 12-bit (0-4095)
- **Voltage Range**: 0-3.3V
- **ADC Conversion**: 1 count ≈ 0.8 mV

## Related Files

- `stm_flash_config.py` - Configure Interceptor Core settings
- `debug_console.py` - View debug serial output
- `firmware/RetroPilot_Cores/interceptor_core/` - Interceptor Core firmware source

## Example Session

```bash
$ ./monitor_interceptor.py
╔════════════════════════════════════════════════════════╗
║   Interceptor Core → Chimera CAN Monitor              ║
║   Monitor torque input and output data                ║
╚════════════════════════════════════════════════════════╝

Searching for Interceptor Core...
Connected to device: ABC123456789

=== Interceptor Core CAN Monitor ===
Mode: Differential (Torque Interceptor)
Monitoring CAN ID: 0x301

Press Ctrl+C to stop...

[CAN ID: 0x301] Torque Input:   12 | ADC0: 2048 | ADC1: 2036 | Override: 0 | State: NO_FAULT | Pkt: 3 | Count: 150
^C
Monitoring stopped by user

Statistics:
  Total CAN packets received: 2450
  Interceptor output packets: 150
✓ Interceptor Core is outputting data to Chimera
```
