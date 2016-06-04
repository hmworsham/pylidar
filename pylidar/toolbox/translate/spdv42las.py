"""
Handles conversion between SPDV4 and LAS formats
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
from pylidar.lidarformats import las
from rios import cuiprogress

def setOutputScaling(points, indata, outdata):
    """
    Sets the output scaling for las. Tries to copy scaling accross.
    """
    for colName in points.dtype.fields:
        try:
            gain, offset = indata.getScaling(colName, 
                    lidarprocessor.ARRAY_TYPE_POINTS)
        except generic.LiDARArrayColumnError:
            # no scaling
            continue
        indtype = indata.getNativeDataType(colName, 
                    lidarprocessor.ARRAY_TYPE_POINTS)
        ininfo = numpy.iinfo(indtype)
        try:
            outdtype = outdata.getNativeDataType(colName, 
                    lidarprocessor.ARRAY_TYPE_POINTS)
        except generic.LiDARArrayColumnError:
            outdtype = points[colName].dtype
            
        if numpy.issubdtype(outdtype, numpy.floating):
            continue
            
        outinfo = numpy.iinfo(outdtype)
        maxVal = offset + ((ininfo.max - ininfo.min) * gain)
        # adjust gain
        # assume min always 0. Not currect in the las case since
        # X, Y and Z are I32 which seems a bit weird so keep it all positive
        gain = (maxVal - offset) / outinfo.max
        
        if colName == "Y" and gain < 0:
            # we need to do another fiddle since las is strict
            # in its min and max for Y
            # not sure if this should be in the driver...
            gain = abs(gain)
            offest = maxVal
            
        outdata.setScaling(colName, lidarprocessor.ARRAY_TYPE_POINTS, 
                        gain, offset)
        
def transFunc(data):
    """
    Called from pylidar. Does the actual conversion to las
    """
    pulses = data.input1.getPulses()
    points = data.input1.getPointsByPulse()
    waveformInfo = data.input1.getWaveformInfo()
    revc = data.input1.getReceived()
    
    # DO we need this??
    #if points is not None:
    #    data.output1.translateFieldNames(data.input1, points, 
    #        lidarprocessor.ARRAY_TYPE_POINTS)
    #if pulses is not None:
    #    data.output1.translateFieldNames(data.input1, pulses, 
    #        lidarprocessor.ARRAY_TYPE_PULSES)
            
    # set scaling
    if data.info.isFirstBlock():
        setOutputScaling(points, data.input1, data.output1)

    data.output1.setPoints(points)
    data.output1.setPulses(pulses)
    data.output1.setWaveformInfo(waveformInfo)
    data.output1.setReceived(revc)

def translate(info, infile, outfile, spatial):
    """
    Does the translation between SPD V4 and .las format files.

    * Info is a fileinfo object for the input file.
    * infile and outfile are paths to the input and output files respectively.
    * spatial is True or False - dictates whether we are processing spatially or not.
        If True then spatial index will be created on the output file on the fly.

    Currently does not take any command line scaling options so LAS scaling
    will be the same as the SPDV4 input file scaling. Not sure if this is
    a problem or not...    
    """
    # first we need to determine if the file is spatial or not
    if spatial and not info.has_Spatial_Index:
        msg = "Spatial processing requested but file does not have spatial index"
        raise generic.LiDARInvalidSetting(msg)

    # get the waveform info
    print('Getting waveform description')
    try:
        wavePacketDescr = las.getWavePacketDescriptions(infile)
    except generic.LiDARInvalidData:
        wavePacketDescr = None
        
    # set up the variables
    dataFiles = lidarprocessor.DataFiles()
        
    dataFiles.input1 = lidarprocessor.LidarFile(infile, lidarprocessor.READ)

    controls = lidarprocessor.Controls()
    progress = cuiprogress.GDALProgressBar()
    controls.setProgress(progress)
    controls.setSpatialProcessing(spatial)
    
    dataFiles.output1 = lidarprocessor.LidarFile(outfile, lidarprocessor.CREATE)
    dataFiles.output1.setLiDARDriver('LAS')
    if wavePacketDescr is not None:
        dataFiles.output1.setLiDARDriverOption('WAVEFORM_DESCR', 
                    wavePacketDescr)

    lidarprocessor.doProcessing(transFunc, dataFiles, controls=controls)