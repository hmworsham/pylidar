"""
Handles conversion between ASCII and SPDV4 formats
"""

# This file is part of PyLidar
# Copyright (C) 2015 John Armston, Pete Bunting, Neil Flood, Sam Gillingham
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import print_function, division

import numpy
from pylidar import lidarprocessor
from pylidar.lidarformats import generic
from pylidar.lidarformats import spdv4
from rios import cuiprogress
from osgeo import osr

from . import translatecommon

def transFunc(data, otherArgs):
    """
    Called from lidarprocessor. Does the actual conversion to SPD V4
    """
    pulses = data.input1.getPulses()
    points = data.input1.getPointsByPulse()
    
    # set scaling 
    if data.info.isFirstBlock():
        translatecommon.setOutputScaling(otherArgs.scaling, data.output1)
        translatecommon.setOutputNull(otherArgs.nullVals, data.output1)

    # check the range
    translatecommon.checkRange(otherArgs.expectRange, points, pulses)
        
    data.output1.setPoints(points)
    data.output1.setPulses(pulses)

def translate(info, infile, outfile, expectRange, scaling, colTypes, pulseCols,
        classificationTranslation=None, nullVals=None):
    """
    Main function which does the work.

    * Info is a fileinfo object for the input file.
    * infile and outfile are paths to the input and output files respectively.
    * expectRange is a list of tuples with (type, varname, min, max).
    * scaling is a list of tuples with (type, varname, gain, offset).
    * colTypes is a list of name and data type tuples for every column
    * pulseCols is a list of strings defining the pulse columns
    * classificationTranslation is a list of tuples specifying how to translate
        between the codes within the files and the 
        lidarprocessor.CLASSIFICATION_* ones. First element of tuple is file 
        number, second the lidarprocessor code.
    * nullVals is a list of tuples with (type, varname, value)
    """
    scalingsDict = translatecommon.overRideDefaultScalings(scaling)

    # set up the variables
    dataFiles = lidarprocessor.DataFiles()
    dataFiles.input1 = lidarprocessor.LidarFile(infile, lidarprocessor.READ)

    # convert from strings to numpy dtypes
    numpyColTypes = []
    for name, typeString in colTypes:
        numpydtype = translatecommon.STRING_TO_DTYPE[typeString.upper()]
        numpyColTypes.append((name, numpydtype))

    dataFiles.input1.setLiDARDriverOption('COL_TYPES', numpyColTypes)
    if pulseCols is not None:
        dataFiles.input1.setLiDARDriverOption('PULSE_COLS', pulseCols)

    if classificationTranslation is not None:
        dataFiles.input1.setLiDARDriverOption('CLASSIFICATION_CODES', 
                classificationTranslation)

    controls = lidarprocessor.Controls()
    progress = cuiprogress.GDALProgressBar()
    controls.setProgress(progress)
    controls.setSpatialProcessing(False)

    otherArgs = lidarprocessor.OtherArgs()
    otherArgs.scaling = scalingsDict
    otherArgs.expectRange = expectRange
    otherArgs.nullVals = nullVals
    
    dataFiles.output1 = lidarprocessor.LidarFile(outfile, lidarprocessor.CREATE)
    dataFiles.output1.setLiDARDriver('SPDV4')
    dataFiles.output1.setLiDARDriverOption('SCALING_BUT_NO_DATA_WARNING', False)

    lidarprocessor.doProcessing(transFunc, dataFiles, controls=controls, 
                    otherArgs=otherArgs)

