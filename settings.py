#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Configuration file for SVG to GCODE converter
# For printing single layers with adhesive

# A4 area:               210mm x 297mm
# Printer Cutting Area: ~178mm x ~344mm
# Testing Area:          150mm x 150mm  (for now)
# Print bed width in mm
bed_max_x = 389

# Print bed height in mm
bed_max_y = 274

# Feed Rate
feed_rate = 5000.00

#  Used to control the smoothness/sharpness of the curves.
#     Smaller the value greater the sharpness. Make sure the
#     value is greater than 0.1
smoothness = 0.2

PEN_DOWN_CMD = 'M03 S55 (pen down)'
PEN_UP_CMD = 'M03 S35 (pen up)'

# G-code emitted before processing a SVG shape
shape_preamble = PEN_UP_CMD

# G-code emitted after processing a SVG shape
shape_postamble = ""

# G-code prepended at the start of processing the SVG file
preamble = """; For EleksMaker Plotter
G21 ;metric values
G90 ;absolute positioning
"""

#'''G-code emitted at the end of processing the SVG file'''
postamble = f"""{PEN_UP_CMD}
G00 X00 Y00
"""

DEBUG = False