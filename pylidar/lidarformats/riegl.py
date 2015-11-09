
"""
Driver for riegl rxp files. Note that the requires access to Riegl's 
'rivlib' and 'riwavelib' closed source libraries that can be obtained from Riegl.

To build Riegl support the $RIVLIB_ROOT and $RIWAVELIB_ROOT environment variables
must be set before running setup.py.

These variables must point into the directories that rivlib and riwavelib
created when they were unzipped.

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

import os
import copy
import numpy

from . import generic
from . import _riegl
from . import gridindexutils

class RieglFile(generic.LiDARFile):
    """
    Driver for reading Riegl rxp files. Uses rivlib
    via the _riegl module.
    """
    def __init__(self, fname, mode, controls, userClass):
        generic.LiDARFile.__init__(self, fname, mode, controls, userClass)

        # The riegl supplied functions only return an error when 
        # we actually start reading but PyLidar needs to know straight
        # away. Workaround is to read the start of the file and see
        # if it contains 'Riegl'. Normally at byte position 9 but we check
        # any of the first 32 bytes.
        fh = open(fname, 'rb')
        data = fh.read(32)
        fh.close()
        
        if data.find(b'Riegl') == -1:
            msg = 'not a riegl file'
            raise generic.LiDARFileException(msg)
        
        # test if there is a .wfm file with the same base name
        root, ext = os.path.splitext(fname)
        waveName = root + '.wfm'
        if not os.path.exists(waveName):
            waveName = None
            msg = '.wfm file not found. Use rxp2wfm to extract first.'
            controls.messageHandler(msg, generic.MESSAGE_WARNING)
        
        self.range = None
        self.lastRange = None
        self.lastPoints = None
        self.lastPulses = None
        self.scanFile = _riegl.ScanFile(fname, waveName)
                          
    @staticmethod        
    def getDriverName():
        return 'riegl'
        
    def close(self):
        self.range = None
        self.lastRange = None
        self.lastPoints = None
        self.lastPulses = None
        self.scanFile = None
        
    def readPointsByPulse(self, colNames=None):
        """
        Read a 3d structured masked array containing the points
        for each pulse.
        """
        pulses = self.readPulsesForRange()
        points = self.readPointsForRange()
        nReturns = pulses['POINTCOUNT']
        startIdxs = pulses['POINTSTARTIDX']

        point_idx, point_idx_mask = gridindexutils.convertSPDIdxToReadIdxAndMaskInfo(        
                startIdxs, nReturns)
                
        pointsByPulse = points[point_idx]
        
        if colNames is None:
            # workaround - seems a structured array returned from
            # C doesn't work with masked arrays. The dtype looks different.
            # TODO: check this with a later numpy
            colNames = pointsByPulse.dtype.names
            
        pointsByPulse = self.subsetColumns(pointsByPulse, colNames)
        points = numpy.ma.array(pointsByPulse, mask=point_idx_mask)
        
        return points
        
    def readWaveformInfo(self):
        """
        2d structured masked array containing information
        about the waveforms.
        """
        self.scanFile.readWaveforms(self.range.startPulse, 
                                    self.range.endPulse)
        raise NotImplementedError()
        
    def readTransmitted(self):
        """
        Read the transmitted waveform for all pulses
        returns a 3d masked array. 
        """
        raise NotImplementedError()
        
    def readReceived(self):
        """
        Read the received waveform for all pulses
        returns a 2d masked array
        """
        raise NotImplementedError()

    def hasSpatialIndex(self):
        """
        Riegl files aren't spatially indexed
        """
        return False
        
    def setPulseRange(self, pulseRange):
        """
        Sets the PulseRange object to use for non spatial
        reads/writes.
        """
        self.range = copy.copy(pulseRange)
        # return True if we can still read data
        # we just assume we can until we find out
        # after a read that we can't
        return not self.scanFile.finished
    
    def readPointsForRange(self, colNames=None):
        """
        Reads the points for the current range. Returns a 1d array.
        
        Returns an empty array if range is outside of the current file.

        colNames can be a list of column names to return. By default
        all columns are returned.
        """
        if self.lastRange is None or self.range != self.lastRange:
            pulses, points = self.scanFile.readData(self.range.startPulse, 
                            self.range.endPulse)
            self.lastRange = self.range        
            self.lastPoints = points
            self.lastPulses = pulses
                            
        return self.subsetColumns(self.lastPoints, colNames)
        
    def readPulsesForRange(self, colNames=None):
        """
        Reads the pulses for the current range. Returns a 1d array.

        Returns an empty array if range is outside of the current file.

        colNames can be a list of column names to return. By default
        all columns are returned.
        """
        if self.lastRange is None or self.range != self.lastRange:
            pulses, points = self.scanFile.readData(self.range.startPulse, 
                            self.range.endPulse)
            self.lastRange = self.range        
            self.lastPoints = points
            self.lastPulses = pulses
                            
        return self.subsetColumns(self.lastPulses, colNames)
        
    def getTotalNumberPulses(self):
        """
        No idea how to find out how many pulses so unsupported
        """
        raise generic.LiDARFunctionUnsupported()

    def writeData(self, pulses=None, points=None, transmitted=None, 
                received=None, waveformInfo=None):
        """
        This driver does not support writing so ignore if reading,
        throw and error otherwise.
        """
        if self.mode == generic.READ:
            # the processor always calls this so if a reading driver just ignore
            return
        
        msg = 'riegl driver does not support update/creating'
        raise generic.LiDARWritingNotSupported(msg)
        
    def getHeader(self):
        """
        Riegl doesn't seem to have a header as such
        """
        return {}
        
    def getHeaderValue(self, name):
        """
        Just extract the one value and return it
        """
        return self.getHeader()[name]
    
        