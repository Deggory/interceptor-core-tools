#!/usr/bin/env python3
"""
Joystick Control for Interceptor Core with GUI
Uses a USB Gamepad connected to the PC to send steering commands via Chimera.
Displays a rotating steering wheel for visual feedback.

Requirements:
  pip install pygame
  Copy 'wheel.png' to this directory.

Usage:
  ./joystick_steer.py
"""

import sys
import time
import struct
import pygame
import os
from firmware.python import Panda

# --- CONFIGURATION ---
TORQUE_MAX = 500       # Max torque target (safe default)
AXIS_STEER = 0         # Axis 0 is usually Left Stick X
BUTTON_ENABLE = 0      # Button 0 is usually A or Cross
CAN_ID = 0x300         # Interceptor Control ID
BUS_NUM = 0            # Bus 0 on Chimera

# --- CRC Logic ---
def generate_crc8_lut(poly=0x1D):
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
    crc = 0xFF
    for byte in data:
        crc = lut[crc ^ byte]
    return crc ^ 0xFF

def send_control_packet(panda, torque, enable, counter, lut):
    # Differential Mode: Target 0 = +Torque, Target 1 = -Torque
    target_0 = int(torque)
    target_1 = int(-torque)

    t0_bytes = struct.pack('<h', target_0)
    t1_bytes = struct.pack('<h', target_1)
    
    # Enable bit is 0x80 (Bit 7) of Byte 5
    byte5 = (0x80 if enable else 0x00) | (counter & 0x0F)

    data = bytearray([
        0,              # Checksum holder
        t0_bytes[0], t0_bytes[1],
        t1_bytes[0], t1_bytes[1],
        byte5
    ])
    
    data[0] = calculate_checksum(data[1:], lut)
    
    try:
        panda.can_send(CAN_ID, bytes(data), BUS_NUM)
    except Exception as e:
        pass # Ignore sporadic USB errors in loop

def main():
    print("\033[36m=== Joystick Steer for Interceptor Core (GUI) ===\033[0m")
    
    # 1. Initialize Pygame & Screen
    pygame.init()
    pygame.joystick.init()
    
    # Setup Window
    size = (600, 600)
    screen = pygame.display.set_mode(size)
    pygame.display.set_caption("RetroPilot Steering Control")
    
    # Load Image
    try:
        if os.path.exists("wheel.png"):
            wheel_img = pygame.image.load("wheel.png")
        else:
            # Fallback: Create a simple red circle if image missing
            wheel_img = pygame.Surface((400, 400), pygame.SRCALPHA)
            pygame.draw.circle(wheel_img, (200, 50, 50), (200, 200), 190, 20)
            pygame.draw.line(wheel_img, (200, 50, 50), (200, 200), (200, 10), 20)
            print("Warning: wheel.png not found, using fallback graphic.")
            
        # Scale if necessary
        wheel_img = pygame.transform.scale(wheel_img, (400, 400))
        wheel_rect = wheel_img.get_rect(center=(300, 300))
    except Exception as e:
        print(f"Graphics Error: {e}")
        sys.exit(1)

    # font = pygame.font.Font(None, 36)

    # 2. Check Joystick
    if pygame.joystick.get_count() == 0:
        print("\033[31mNo joystick found! Plug in a USB controller.\033[0m")
        # sys.exit(1) 
        # Don't exit, allow testing GUI without joystick if needed
    else:
        js = pygame.joystick.Joystick(0)
        js.init()
        print(f"\033[32mInitialized: {js.get_name()}\033[0m")

    # 3. Connection
    panda = None
    try:
        serials = Panda.list()
        if serials:
            panda = Panda(serials[0])
            panda.set_safety_mode(Panda.SAFETY_ALLOUTPUT)
            print(f"\033[32mConnected to: {serials[0]}\033[0m")
        else:
            print("\033[31mNo Chimera found! Running in offline mode.\033[0m")
    except Exception as e:
        print(f"Connection Error: {e}")

    lut = generate_crc8_lut()
    counter = 0
    clock = pygame.time.Clock()
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Read Input
        axis_val = 0.0
        enable = False
        
        if pygame.joystick.get_count() > 0:
            axis_val = js.get_axis(AXIS_STEER) # -1.0 to 1.0
            enable = js.get_button(BUTTON_ENABLE) == 1
        
        # Logic
        torque_req = axis_val * TORQUE_MAX 
        if abs(torque_req) < 10: torque_req = 0
        
        # Send CAN
        if panda:
            send_control_packet(panda, torque_req, enable, counter, lut)
            counter = (counter + 1) & 0x0F

        # Render
        screen.fill((30, 30, 30)) # Dark Grey BG
        
        # Rotate Wheel
        # Input -1 (Left) -> Angle +90 (CCW)
        angle = axis_val * -90
        rotated_wheel = pygame.transform.rotate(wheel_img, angle)
        new_rect = rotated_wheel.get_rect(center=wheel_rect.center)
        screen.blit(rotated_wheel, new_rect)
        
        # Status Text
        # text_surf = font.render(f"Torque: {int(torque_req)}", True, (255, 255, 255))
        # screen.blit(text_surf, (10, 10))
        
        status_color = (0, 255, 0) if enable else (255, 100, 100)
        status_text = "ENABLED" if enable else "DISABLED"
        # status_surf = font.render(status_text, True, status_color)
        # screen.blit(status_surf, (10, 50))
        
        # Simple rect indicator for status if font fails
        pygame.draw.rect(screen, status_color, (20, 20, 20, 20))

        pygame.display.flip()
        clock.tick(100) # 100 FPS loop

    print("Closing...")
    if panda:
        # Safety disable
        send_control_packet(panda, 0, False, 0, lut)

if __name__ == "__main__":
    main()
