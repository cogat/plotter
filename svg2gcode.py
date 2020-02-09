#!/usr/bin/env python3
"""
Take an SVG file and output a gcode equivalent.
"""

import os
import sys
import xml.etree.ElementTree as ET
import importlib
from lib import shapes

SVG_TAGS = set(['rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'path'])

import argparse
parser = argparse.ArgumentParser(description='Take an svg input and convert to gcode commands, '
    'using the parameters set in settings.py. By default the input will be maximised in size and '
    'centered in the work area.'
)
parser.add_argument('svg_path')
parser.add_argument('--settings', default='settings', help="use the settings for a particular machine")

parser.add_argument('--position-at-origin', action='store_true', help="position the lower left corner of the output at the corner of the work area")
parser.add_argument('--x-offset', type=float, default=0.0, help="move the output right by x mm")
parser.add_argument('--y-offset', type=float, default=0.0, help="move the output up by y mm")

parser.add_argument('--x-size', type=float, help="set the x size of the output in mm (cannot be bigger than the work area)")
parser.add_argument('--y-size', type=float, help="set the y size of the output in mm (cannot be bigger than the work area)")

parser.add_argument('--output-bounding-box', action='store_true', help="output a -bb.gcode file which traces the bounding box for the output")


class GCodeFile():
    """
    Wrapper round a file that writes GCode
    """
    def __init__(self, filename, settings):
        '''Open the file and write the preamble'''
        self.settings = settings
        self.file = open(filename, 'w')
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
        position_at_origin,
        x_offset,
        y_offset,
        x_size,
        y_size,
        output_bounding_box,
    ):

        # Check File Validity
        if not os.path.isfile(svg_path):
            raise ValueError('File \''+svg_path+'\' not found.')

        if not svg_path.endswith('.svg'):
            raise ValueError('File \''+svg_path+'\' is not an SVG file.')

        self.settings = settings
        self.svg_path = svg_path
        self.gcode_path = gcode_path
        self.position_at_origin = position_at_origin
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.x_size = max(x_size or self.settings.work_area_mm[0], self.settings.work_area_mm[0])
        self.y_size = max(y_size or self.settings.work_area_mm[1], self.settings.work_area_mm[1])
        self.output_bounding_box = output_bounding_box

        self.scale = None
        self.offset = None

    def path_to_gcode(self, path, mtx):
        '''Convert a single svg path to a gcode shape'''

        result = ''
        new_shape = True
        points = shapes.point_generator(path, mtx, settings.smoothness)
        x_curr, y_curr = None, None

        for x, y in points:  # pylint: disable=invalid-name
            x_curr = self.scale * x + self.offset[0]
            y_curr = self.scale * y + self.offset[1]

            if 0 <= x_curr <= self.settings.work_area_mm[0] and \
                0 <= y_curr <= self.settings.work_area_mm[1]:
                result += f'G00 X{x_curr} Y{y_curr}\n'
                if new_shape:
                    # move to position, put the pen down
                    result += f'{self.settings.TOOL_ON_CMD}\n'
                    new_shape = False
            else:
                print(
                    f'\t--POINT OUT OF RANGE: ({x_curr}, {y_curr})'
                )
        return result

    def svg_elem_to_gcode(self, elem):
        '''Transform an SVG element into gcode'''
        self.debug_log(f'--Found Elem: {elem}')
        tag_suffix = elem.tag.split('}')[-1]

        # Checks element is valid SVG_TAGS shape
        if tag_suffix in SVG_TAGS:

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
                if settings.shape_preamble:
                    self.gcode_file.writeln(settings.shape_preamble)
                self.gcode_file.writeln(self.path_to_gcode(d_path, mtx))
                if settings.shape_postamble:
                    self.gcode_file.writeln(settings.shape_postamble)
            else:
                self.debug_log('\tNO PATH INSTRUCTIONS FOUND!!')
        else:
            self.debug_log('  --No Name: '+tag_suffix)

    def _get_scale_offset(self, root):
        '''Inspect the root SVG element and return the scale factor for the drawing'''
        # Get the Height and Width from the parent svg tag
        work_width = float(root.get('width', '0').rstrip('px'))
        work_height = float(root.get('height', '0').rstrip('px'))
        if not (work_width and work_height):
            viewbox = root.get('viewBox')
            if viewbox:
                _, _, work_width, work_height = viewbox.split()

        work_width = float(work_width)
        work_height = float(work_height)

        if not (work_width and work_height):
            raise ValueError('Unable to get width or height for the svg')

        scale_x = self.x_size / work_width
        scale_y = self.y_size / work_height
        scale = min(scale_x, scale_y)

        print(f'svg dimensions: {work_width:.2f} x {work_height:.2f}')
        print(f'output dimensions: {self.x_size:.2f} x {self.y_size:.2f} mm (scale {scale:.2f})')

        if self.position_at_origin:
            offset = (0, 0)
        else:
            offset = (
                (-work_width * scale + self.settings.work_area_mm[0]) / 2,
                (-work_height * scale + self.settings.work_area_mm[1]) / 2
            )
        offset = (offset[0] + self.x_offset, offset[1] + self.y_offset)

        print(f'offset: {offset[0]:.2f} x {offset[1]:.2f}mm')

        return scale, offset

    def convert(self):
        ''' The main method that converts svg files into gcode files.
            Still incomplete. See tests/start.svg'''

        # Get the svg Input File
        input_file = open(self.svg_path, 'r')
        root = ET.parse(input_file).getroot()
        input_file.close()

        self.scale, self.offset = self._get_scale_offset(root)
        self.gcode_file = GCodeFile(self.gcode_path, self.settings)

        # Iterate through svg elements
        for elem in root.iter():
            self.svg_elem_to_gcode(elem)

        # Write the Result
        self.gcode_file.close()

    def debug_log(self, message):
        ''' Simple debugging function. If you don't understand
            something then chuck this frickin everywhere. '''
        if self.settings.DEBUG:
            print(message)


if __name__ == '__main__':
    args = parser.parse_args()
    settings = importlib.import_module(args.settings)
    kwargs = vars(args)
    kwargs['settings'] = settings

    outdir, input_filename = os.path.split(kwargs['svg_path'])
    gcode_path = os.path.join(outdir, input_filename.split('.svg')[0] + '.gcode')
    print('Output File: ' + gcode_path)
    kwargs['gcode_path'] = gcode_path

    gcode_converter = SVG2GCodeConverter(**kwargs)
    gcode_converter.convert()