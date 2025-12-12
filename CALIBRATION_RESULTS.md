# Sensor Calibration Results

**Date**: 2025-12-12  
**Device**: Interceptor Core (440048001251333133333633)  
**Mode**: Differential

## Calibration Data

**Samples Collected**: 85 samples over 10 seconds

### ADC Channel 0 Statistics
- **Center (median)**: 1538
- **Average**: 1540.3
- **Range**: 1454 - 1697 (span: 243)
- **Std deviation**: 25.0
- **95% range**: 1524 - 1558

### ADC Channel 1 Statistics
- **Center (median)**: 1579
- **Average**: 1580.3
- **Range**: 1557 - 1611 (span: 54)
- **Std deviation**: 8.0
- **95% range**: 1570 - 1600

## Recommended Configuration

### ADC Channel 0
```
Center value (adc1): 1538
Tolerance (adc_tolerance): 125
Valid range: 1413 to 1663
Enable validation (adc_en): 1
```

### ADC Channel 1
```
Center value (adc1): 1579
Tolerance (adc_tolerance): 100
Valid range: 1479 to 1679
Enable validation (adc_en): 1
```

## Configuration Steps

1. Run: `python3 stm_flash_config.py`
2. Select Interceptor Core device
3. Choose option 1 (Configure device)
4. Configure **ADC Channel 0 Validation** (option 1):
   - adc1 (center): **1538**
   - adc2: **0**
   - adc_tolerance: **125**
   - Enable: **1**

5. Run `stm_flash_config.py` again
6. Configure **ADC Channel 1 Validation** (option 2):
   - adc1 (center): **1579**
   - adc2: **0**
   - adc_tolerance: **100**
   - Enable: **1**

## Verification

After configuration, run:
```bash
./view_interceptor_data.py
```

**Expected result**: State should change from `UNKNOWN(11)` or `FAULT_ADC_UNCONFIGURED` to `NO_FAULT`

## Notes

- ADC0 has higher variance (std dev: 25.0) compared to ADC1 (std dev: 8.0)
- Tolerance values are set to 3x standard deviation + margin for safety
- Current readings are within normal range for torque sensors
- Differential torque magnitude: ~41 counts (|1538 - 1579|)
