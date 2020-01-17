#!/usr/bin/env python3
"""\

Stream g-code to grbl-based controller

Adapted from stream.py example in GRBL.

TODO:
Allow async stream
Clip/ensure coords won't extend beyond plotter
move pen up/down subs into preprocessor
Time process from start to finish
"""

import serial
import re
import time
import sys
import argparse
import fileinput

RX_BUFFER_SIZE = 128
DEFAULT_SERIAL_DEVICE = '/dev/tty.usbserial-14210'

SPEED = 'F5000'
SPEED_RE = r'F\d+'
PEN_DOWN_CMD = 'M03 S55'
PEN_UP_CMD = 'M03 S35'
PEN_DOWN_RES = (
    r'^G01 Z-0.125000 F',
)
PEN_UP_RES = (
    r'^G00 Z5.000000',
)

class GCodeStreamer():

    def __init__(self, serial_device, quiet):
        # Initialize
        self.ser = serial.Serial(serial_device, 115200)
        self.verbose = not quiet

        # Wake up grbl
        print('Initializing grbl...')
        self.ser.write(b"\r\n\r\n")

        # Wait for grbl to initialize and flush startup text in serial input
        time.sleep(2)
        self.ser.write(PEN_UP_CMD.encode() + b'\n')
        self.ser.flushInput()

    def stream_settings(self):
        # Send settings file via simple call-response streaming method. Settings must be streamed
        # in this manner since the EEPROM accessing cycles shut-off the serial interrupt.
        l_count = 0

        for line in fileinput.input():
            l_count += 1  # Iterate line counter    
            l_block = line.strip()  # Strip all EOL characters for consistency
            if self.verbose:
                print('SND: ' + str(l_count) + ':' + l_block,)
            self.ser.write(l_block.encode() + b'\n')  # Send g-code block to grbl
            grbl_out = self.ser.readline().strip()  # Wait for grbl response with carriage return
            if self.verbose:
                print('REC:',grbl_out)
        self.finish()

    def stream(self):
        # Stream g-code to grbl
        # Send g-code program via a more agressive streaming protocol that forces characters into
        # Grbl'self.ser serial read buffer to ensure Grbl has immediate access to the next g-code command
        # rather than wait for the call-response serial protocol to finish. This is done by careful
        # counting of the number of characters sent by the streamer to Grbl and tracking Grbl'self.ser 
        # responses, such that we never overflow Grbl'self.ser serial read buffer. 
        l_count = 0
        g_count = 0
        c_line = []

        for line in fileinput.input():
            # preprocess line to adapt gcode for other machines to this plotter
            for cmd in PEN_DOWN_RES:
                if re.match(cmd, line):
                    line = PEN_DOWN_CMD
            for cmd in PEN_UP_RES:
                if re.match(cmd, line):
                    line = PEN_UP_CMD
            re.sub(SPEED_RE, SPEED, line)

            l_count += 1  # Iterate line counter
            l_block = line.strip()
            c_line.append(len(l_block)+1)  # Track number of characters in grbl serial read buffer
            grbl_out = b'' 
            while sum(c_line) >= RX_BUFFER_SIZE-1 | self.ser.inWaiting():
                out_temp = self.ser.readline().strip()  # Wait for grbl response
                if b'ok' not in out_temp and b'error' not in out_temp:
                    print("  Debug: ", out_temp)  # Debug response
                else :
                    grbl_out += out_temp
                    g_count += 1  # Iterate g-code counter
                    grbl_out += str(g_count).encode()
                    del c_line[0]  # Delete the block character count corresponding to the last 'ok'
            if self.verbose:
                print("SND: " + str(l_count) + " : " + l_block,)
            self.ser.write(l_block.encode() + b'\n')  # Send g-code block to grbl
            if self.verbose:
                print("BUF:",str(sum(c_line)),"REC:",grbl_out)
        self.finish()

    def finish(self):
        # Wait for user input after streaming is completed
        print("G-code streaming finished!\n")
        print("WARNING: Wait until grbl completes buffered g-code blocks before exiting.")
        input("  Press <Enter> to exit and disable grbl.") 

        # Close serial port
        self.ser.close()


def main(gcode_file=None, device=DEFAULT_SERIAL_DEVICE, quiet_mode=False, settings_mode=False, **kwargs):
    streamer = GCodeStreamer(device, quiet_mode)
    print("Ensure plotter is at the zero position.")
    input("  Press <Enter> to start the plot.") 
    if settings_mode:
        streamer.stream_settings()
    else:
        streamer.stream()


if __name__=='__main__':
    # Define command line argument interface
    parser = argparse.ArgumentParser(description='Stream g-code file to grbl. (pySerial and argparse libraries required)')
    parser.add_argument('gcode_file', type=argparse.FileType('r'),
            help='g-code filename to be streamed. Use `-` for stdin.', default='-')
    parser.add_argument('-d', '--device',
            help='serial device path', default=DEFAULT_SERIAL_DEVICE)
    parser.add_argument('-q','--quiet_mode',action='store_true', default=False, 
            help='suppress output text')
    parser.add_argument('-s','--settings-mode',action='store_true', default=False, 
            help='settings write mode')        
    args = parser.parse_args()
    main(**dict(args._get_kwargs()))