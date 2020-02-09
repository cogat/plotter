#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Configuration file for SVG to GCODE converter
# For printing single layers with adhesive

# A4 area:               210mm x 297mm
# Printer Cutting Area: ~178mm x ~344mm
# Testing Area:          150mm x 150mm  (for now)
# Print bed width in mm
bed_area_mm = (389, 274)

# Feed Rate
feed_rate = 5000.00

#  Used to control the smoothness/sharpness of the curves.
#     Smaller the value greater the sharpness.
smoothness = 0.2

TOOL_ON_CMD = 'M03 S55 (pen down)'
TOOL_OFF_CMD = 'M03 S35 (pen up)'

# G-code emitted before processing a SVG shape
shape_preamble = TOOL_OFF_CMD

# G-code emitted after processing a SVG shape
shape_postamble = ""

# G-code prepended at the start of processing the SVG file
preamble = """; For EleksMaker A3 Plotter
G21 ;metric values
G90 ;absolute positioning
"""

#'''G-code emitted at the end of processing the SVG file'''
postamble = f"""{TOOL_OFF_CMD}
G00 X00 Y00
"""

DEBUG = False