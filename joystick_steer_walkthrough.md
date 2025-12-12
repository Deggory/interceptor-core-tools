# Joystick Steer Script Walkthrough

This document explains how `joystick_steer.py` transforms your USB controller inputs into CAN bus commands for the Interceptor Core.

## 1. System Overview

**Objective**: Manually control the car's steering servo (EPS) using a PC game controller.

*   **Input**: USB Joystick (Xbox/PS4 controller) connected to PC.
*   **Bridge**: Chimera (STM32F4) acting as a USB-to-CAN adapter.
*   **Output**: Interceptor Core (STM32F4) receiving torque commands on CAN Bus 0.

## 2. The Code Logic

The script operates in a continuous loop (100Hz):

1.  **Read Inputs (`pygame`)**:
    *   It checks the **Left Stick (Axis 0)** for position (-1.0 to +1.0).
    *   It checks **Button 0** (A/X) to see if you are holding it down.
2.  **Calculate Torque**:
    *   It multiplies the joystick axis (-1.0 to 1.0) by `TORQUE_MAX` (500).
    *   Result: A target value between -500 and +500.
3.  **Pack CAN Message (`0x300`)**:
    *   The Interceptor expects a specific format for Differential Mode.
    *   It packs the **Positive Torque** into Bytes 1-2.
    *   It packs the **Negative Torque** into Bytes 3-4 (required by Differential logic).
    *   It sets the **Enable Flag (Bit 7)** in Byte 5 *only* if you are holding the button.
4.  **Calculate Checksum**:
    *   It runs a CRC8 algorithm over the data to ensure validity. The Interceptor will ignore the packet if this is wrong.
5.  **Send via USB**:
    *   It uses the `Panda` library to shoot this packet to the Chimera device.

## 3. CAN Message Structure
The script generates this 6-byte payload on ID **0x300**:

| Byte | Value | Purpose |
| :--- | :--- | :--- |
| **0** | `CRC8` | Security Checksum |
| **1** | `Low` | **Target 0** (Low Byte) |
| **2** | `High` | **Target 0** (High Byte) |
| **3** | `Low` | **Target 1** (Low Byte - Inverted) |
| **4** | `High` | **Target 1** (High Byte - Inverted) |
| **5** | `Flags` | **Enable Bit** (0x80) + Rolling Counter |

## 4. How to Use

### Prerequisites
*   **Hardware**: Chimera (Plugged in), Interceptor Core (Wired to CAN), USB Joystick.
*   **Software**: Python 3, `pygame`, `libusb1`.
    ```bash
    pip install pygame libusb1
    ```

### Running It
1.  Open a terminal in `interceptor-core-tools`.
2.  Run the script:
    ```bash
    ./joystick_steer.py
    ```
3.  **Safety First**: The script starts in **DISABLED** mode.
4.  **Enable**: Hold **Button 0** (usually 'A' on Xbox, 'X' on PS4).
    *   The terminal status will change to **ENABLED**.
5.  **Steer**: Gently move the Left Analog Stick.
    *   You should see the steering wheel move.
6.  **Disengage**: Release Button 0 immediately to stop control.

## 5. Troubleshooting
*   **"No joystick found"**: Plug in your controller *before* running the script.
*   **"No Chimera found"**: Check your USB cable to the Chimera.
*   **"Status: ENABLED" but no movement**:
    *   Is the Interceptor configured? (Run `test_interceptor.py` to check).
    *   Is the car ON? (The EPS main motor needs 12V power).
    *   Is the torque too low? Verify `TORQUE_MAX` in the script.
