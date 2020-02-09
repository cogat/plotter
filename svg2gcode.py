#!/usr/bin/env python3
"""
Take an SVG file and output a gcode equivalent.
"""

import os
import sys
import xml.etree.ElementTree as ET
import importlib
from lib import shapes
import numpy as np
from vectormath import Vector2
from utils import Rect, rotate
from math import pi

SVG_TAGS = set(['rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'path'])

import argparse
parser = argparse.ArgumentParser(description='Take an svg input and convert to gcode commands, '
    'using the parameters set in settings.py. By default the input will be maximised in size and '
    'centered in the work area.'
)
parser.add_argument('svg_path')
parser.add_argument('--settings', default='settings', help="use the settings file for a particular machine")
parser.add_argument('--plot-from-origin', action='store_true', help="position the lower left corner of the output at the corner of the work area")
parser.add_argument('--x-offset-mm', type=float, default=0.0, help="move the output right by x mm")
parser.add_argument('--y-offset-mm', type=float, default=0.0, help="move the output up by y mm")
parser.add_argument('--x-size-mm', type=float, help="set the x size of the output in mm")
parser.add_argument('--y-size-mm', type=float, help="set the y size of the output in mm")
parser.add_argument('--rotate', type=float, default=0.0, help="Rotate the SVG (about its origin) by this number of degrees")


class GCodeFile():
    """
    Wrapper round a file that writes GCode
    """
    def __init__(self, filename, settings):
        '''Open the file and write the preamble'''
        self.settings = settings
        self.file = open(filename, 'w')
        self.writeln(f'; Generated with `{" ".join(sys.argv)}`')
        self.writeln(self.settings.preamble)
        self.writeln(f'G01 F{self.settings.feed_rate}')

    def write(self, gcode):
        '''Write a string to the file'''
        self.file.write(gcode)

    def writeln(self, gcode):
        '''Write a string to the file, appending \\n'''
        self.file.write(gcode + '\n')

    def close(self):
        '''Write the postamble and close the file'''
        self.writeln(self.settings.postamble)
        self.file.close()


class SVG2GCodeConverter():
    def __init__(
        self,
        settings,
        svg_path,
        gcode_path,
        plot_from_origin,
        x_offset_mm,
        y_offset_mm,
        x_size_mm,
        y_size_mm,
        rotate,
    ):

        # Check File Validity
        if not os.path.isfile(svg_path):
            raise ValueError('File \''+svg_path+'\' not found.')

        if not svg_path.endswith('.svg'):
            raise ValueError('File \''+svg_path+'\' is not an SVG file.')

        self.settings = settings
        self.svg_path = svg_path
        self.gcode_path = gcode_path
        self.gcode_file = GCodeFile(self.gcode_path, self.settings)

        # Get the svg Input File
        input_file = open(self.svg_path, 'r')
        self.svg_root = ET.parse(input_file).getroot()
        input_file.close()

        self.rotate_rads = rotate * pi / 180

        self.svg_bounding_box = self.get_svg_bounding_box()

        bed_area_mm = Vector2(self.settings.bed_area_mm)
        self.plot_bed_mm = Rect(Vector2(), bed_area_mm)
        self.plot_size_mm = Vector2(x_size_mm or bed_area_mm.x, y_size_mm or bed_area_mm.y)
        self.offset_mm = Vector2(x_offset_mm, y_offset_mm)
        self.plot_from_origin = plot_from_origin

        self.scale, self.offset = self.get_transform()

    def path_to_gcode(self, path, mtx):
        '''Convert a single svg path to a gcode shape'''

        result = ''
        new_shape = True
        points = shapes.point_generator(path, mtx, self.settings.smoothness)

        for point in points:
            plot_point = self.scale * rotate(Vector2(point), self.rotate_rads) + self.offset

            if self.plot_bed_mm >= plot_point: # true if the plot point is within the plot bed
                result += f'G01 X{plot_point.x} Y{plot_point.y}\n'
                if new_shape:
                    # move to position, put the pen down
                    result += f'{self.settings.TOOL_ON_CMD}\n'
                    new_shape = False
            else:
                print(f'\t--POINT OUT OF RANGE: {plot_point}')
                import ipdb as pdb; pdb.set_trace()
                sys.exit(1)
        return result

    def svg_elem_to_gcode(self, elem):
        '''Transform an SVG element into gcode'''
        self.debug_log(f'--Found Elem: {elem}')
        tag_suffix = elem.tag.split('}')[-1]

        # Checks element is valid SVG_TAGS shape
        if tag_suffix not in SVG_TAGS:
            self.debug_log('  --No Name: '+tag_suffix)
            return

        self.debug_log(f'  --Name: {tag_suffix}')

        # Get corresponding class object from 'shapes.py'
        shape_class = getattr(shapes, tag_suffix)
        shape_obj = shape_class(elem)

        self.debug_log(f'\tClass : {shape_class}')
        self.debug_log(f'\tObject: {shape_obj}')
        self.debug_log(f'\tAttrs : {list(elem.items())}')
        self.debug_log(f'\tTransform: {elem.get("transform")}')

        ############ HERE'S THE MEAT!!! #############
        # Gets the Object path info in one of 2 ways:
        # 1. Reads the <tag>'s 'd' attribute.
        # 2. Reads the SVG_TAGS and generates the path itself.
        d_path = shape_obj.d_path()

        # The *Transformation Matrix* #
        # Specifies something about how curves are approximated
        # Non-essential - a default is used if the method below
        #   returns None.
        mtx = shape_obj.transformation_matrix()

        if d_path:
            if self.settings.shape_preamble:
                self.gcode_file.writeln(self.settings.shape_preamble)
            self.gcode_file.writeln(self.path_to_gcode(d_path, mtx))
            if self.settings.shape_postamble:
                self.gcode_file.writeln(self.settings.shape_postamble)
        else:
            self.debug_log('\tNO PATH INSTRUCTIONS FOUND!!')            

    def _get_elem_extents(self, elem):
        elem_extents = Rect.far_extents()
        tag_suffix = elem.tag.split('}')[-1]
        if tag_suffix not in SVG_TAGS:
            return elem_extents

        shape_class = getattr(shapes, tag_suffix)
        shape_obj = shape_class(elem)
        path = shape_obj.d_path()
        mtx = shape_obj.transformation_matrix()
        if path:
            points = shapes.point_generator(path, mtx, self.settings.smoothness)
            for point in points:
                elem_extents = elem_extents.expand_to(rotate(Vector2(point), self.rotate_rads))

        return elem_extents

    def get_svg_bounding_box(self):
        '''
        Return a Rect describing the bounding box of coords in the SVG file. 
        [TODO: is this already a function in the SVG lib?]
        '''
        svg_bounding_box = Rect.far_extents()
        for elem in self.svg_root.iter():
            elem_extents = self._get_elem_extents(elem)
            svg_bounding_box = svg_bounding_box.expand_to(elem_extents)

        print(f'SVG extents: {svg_bounding_box}')
        return svg_bounding_box

    def get_transform(self):
        '''
        Map the SVG bounding box onto the plot area.
        '''
        # Shrink either x_size or y_size to match aspect ratio of SVG        
        svg_ratio = self.svg_bounding_box.ratio
        plot_ratio = 1.0 * self.plot_size_mm.y / self.plot_size_mm.x

        if svg_ratio > plot_ratio:
            # svg is taller than plot - shrink the x
            self.plot_size_mm.x = self.plot_size_mm.y / svg_ratio
        else:
            # svg is wider than plot - shrink the y
            self.plot_size_mm.y = self.plot_size_mm.x * svg_ratio

        if self.plot_from_origin:
            # output extents are (0, 0 -> x_size, y_size) + offset, if plot_from_origin
            self.plot_extents = Rect(self.offset_mm, self.offset_mm + self.plot_size_mm)
        else:
            # output extents are (bed_centre +/- size / 2) + offset, if plot_from_centre
            self.plot_extents = Rect((self.plot_bed_mm.size - self.plot_size_mm), (self.plot_bed_mm.size + self.plot_size_mm)) / 2.0 + self.offset_mm
        # output extents are clipped to bed_size
        self.plot_extents = self.plot_extents.clip(self.plot_bed_mm)

        print(f'Plot extents: {self.plot_extents}')

        # Transform SVG bounding box to plot extents

        # flip the SVG y values, since the coordinate systems are different
        temp = self.svg_bounding_box.corner0.y
        self.svg_bounding_box.corner0.y = self.svg_bounding_box.corner1.y
        self.svg_bounding_box.corner1.y = temp

        scale = self.plot_extents.size / self.svg_bounding_box.size
        offset = self.plot_extents.corner0 - scale * self.svg_bounding_box.corner0

        print(f'scale: {scale}; offset: {offset}')

        return scale, offset

    def convert(self):
        ''' The main method that converts svg files into gcode files.'''
        # Iterate through svg elements
        for elem in self.svg_root.iter():
            self.svg_elem_to_gcode(elem)
        self.gcode_file.close()

    def debug_log(self, message):
        ''' Simple debugging function. If you don't understand
            something then chuck this frickin everywhere. '''
        if self.settings.DEBUG:
            print(message)


if __name__ == '__main__':
    args = parser.parse_args()
    _settings = importlib.import_module(args.settings)
    kwargs = vars(args)
    kwargs['settings'] = _settings
    outdir, input_filename = os.path.split(kwargs['svg_path'])
    gcode_path = os.path.join(outdir, input_filename.split('.svg')[0] + '.gcode')
    print('Output File: ' + gcode_path)
    kwargs['gcode_path'] = gcode_path

    gcode_converter = SVG2GCodeConverter(**kwargs)
    gcode_converter.convert()