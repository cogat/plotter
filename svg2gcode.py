#!/usr/bin/env python

# External Imports
import os
import sys
import math
import xml.etree.ElementTree as ET

# Local Imports
from lib import shapes
import settings

DEBUGGING = True
SVG = set(['rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'path'])


def generate_gcode(filename):
    ''' The main method that converts svg files into gcode files.
        Still incomplete. See tests/start.svg'''

    # Check File Validity
    if not os.path.isfile(filename):
        raise ValueError("File \""+filename+"\" not found.")

    if not filename.endswith('.svg'):
        raise ValueError("File \""+filename+"\" is not an SVG file.")

    # Define the Output
    # ASSUMING LINUX / OSX FOLDER NAMING STYLE
    log = ""
    log += debug_log("Input File: "+filename)

    dir_string, file = os.path.split(filename)

    # Make Output File
    outdir = dir_string + "/gcode_output/"
    if not os.path.exists(outdir):
        os.makedirs(outdir)
    outfile = outdir + file.split(".svg")[0] + '.gcode'
    log += debug_log("Output File: "+outfile)

    # Make Debug File
    debugdir = dir_string + "/log/"
    if not os.path.exists(debugdir):
        os.makedirs(debugdir)
    debug_file = debugdir + file.split(".svg")[0] + '.log'
    log += debug_log("Log File: "+debug_file+"\n")

    # Get the SVG Input File
    file = open(filename, 'r')
    tree = ET.parse(file)
    root = tree.getroot()
    file.close()
    
    # Get the Height and Width from the parent svg tag
    width = root.get('width')
    height = root.get('height')
    if width == None or height == None:
        viewbox = root.get('viewBox')
        if viewbox:
            _, _, width, height = viewbox.split()                

    if width == None or height == None:
        # raise ValueError("Unable to get width or height for the svg")
        print("Unable to get width and height for the svg")
        sys.exit(1)
    
    # Scale the file appropriately
    # (Will never distort image - always scales evenly)
    # ASSUMES: Y AXIS IS LONG AXIS
    #          X AXIS IS SHORT AXIS
    # i.e. laser cutter is in "portrait"
    scale_x = settings.bed_max_x / float(width)
    scale_y = settings.bed_max_y / float(height)
    scale = min(scale_x, scale_y)
    if scale > 1:
        scale = 1

    log += debug_log("wdth: "+str(width))
    log += debug_log("hght: "+str(height))
    log += debug_log("scale: "+str(scale))
    log += debug_log("x%: "+str(scale_x))
    log += debug_log("y%: "+str(scale_y))

    # CREATE OUTPUT VARIABLE
    gcode = ""

    # Write Initial G-Codes
    gcode += settings.preamble + "\n"
    gcode += "G1 F" + str(settings.feed_rate) + "\n"
    
    # Iterate through svg elements
    for elem in root.iter():
        log += debug_log("--Found Elem: "+str(elem))
        new_shape = True
        try:
            tag_suffix = elem.tag.split("}")[-1]
        except:
            print("Error reading tag value:", tag_suffix)
            continue
        
        # Checks element is valid SVG shape
        if tag_suffix in SVG:

            log += debug_log("  --Name: "+str(tag_suffix))

            # Get corresponding class object from 'shapes.py'
            shape_class = getattr(shapes, tag_suffix)
            shape_obj = shape_class(elem)

            log += debug_log("\tClass : "+str(shape_class))
            log += debug_log("\tObject: "+str(shape_obj))
            log += debug_log("\tAttrs : "+str(list(elem.items())))
            log += debug_log("\tTransform: "+str(elem.get('transform')))


            ############ HERE'S THE MEAT!!! #############
            # Gets the Object path info in one of 2 ways:
            # 1. Reads the <tag>'s 'd' attribute.
            # 2. Reads the SVG and generates the path itself.
            d = shape_obj.d_path()
            log += debug_log("\td: "+str(d))

            # The *Transformation Matrix* #
            # Specifies something about how curves are approximated
            # Non-essential - a default is used if the method below
            #   returns None.
            m = shape_obj.transformation_matrix()
            log += debug_log("\tm: "+str(m))

            if d:
                log += debug_log("\td is GOOD!")

                gcode += settings.shape_preamble + "\n"
                points = shapes.point_generator(d, m, settings.smoothness)

                log += debug_log("\tPoints: "+str(points))

                x_prev, y_prev, x_curr, y_curr = None, None, None, None
                
                for x,y in points:

                    if x_curr is None:
                        x_curr = scale*x
                        y_curr = scale*y

                    x_prev = x_curr
                    y_prev = y_curr

                    x_curr = scale*x
                    y_curr = scale*y
                    z = math.sqrt((math.pow(x_prev-x_curr, 2) + math.pow(y_prev-y_curr, 2)))

                    # Set the extrusion value (Ennn) per 10mm/1cm of lateral travel
                    b = z * 1.0

                    # Increase material extruded cumulatively
                    if not 'e' in locals():
                        e = b
                    else:
                        e = e + b

                    print("X:", x_curr, "Y:", y_curr, "New_Extr:", e)
                    log += debug_log("\t  pt: "+str((x,y)))

                    if x_curr >= 0 and x_curr <= settings.bed_max_x and y_curr >= 0 and y_curr <= settings.bed_max_y:
                        if new_shape:
                            # move to position
                            gcode += ("G00 X%0.3f Y%0.3f\n" % (x_curr, y_curr))
                            gcode += settings.PEN_DOWN_CMD + "\n"
                            new_shape = False
                        else:
                            gcode += (f"G01 X%0.3f Y%0.3f\n" % (x_curr, y_curr))
                        log += debug_log("\t    --Point printed")
                    else:
                        log += debug_log("\t    --POINT NOT PRINTED ("+str(bed_max_x)+","+str(bed_max_y)+")")
                gcode += settings.shape_postamble + "\n"
            else:
              log += debug_log("\tNO PATH INSTRUCTIONS FOUND!!")
        else:
          log += debug_log("  --No Name: "+tag_suffix)

    gcode += settings.postamble + "\n"

    # Write the Result
    ofile = open(outfile, 'w+')
    ofile.write(gcode)
    ofile.close()

    # Write Debugging
    if DEBUGGING:
        dfile = open(debug_file, 'w+')
        dfile.write(log)
        dfile.close()


def debug_log(message):
    ''' Simple debugging function. If you don't understand 
        something then chuck this frickin everywhere. '''
    if (DEBUGGING):
        print(message)
    return message+'\n'


if __name__ == "__main__":
    generate_gcode(os.path.abspath(sys.argv[1]))
    
