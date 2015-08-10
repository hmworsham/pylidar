"""
Common utility functions for dealing with grid spatial indices
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

import numpy
from numba import jit

@jit
def updateBoolArray(boolArray, mask):
    """
    Used by readPointsForExtentByBins and writeData to update the mask of 
    elements that are to be written. Often elements need to be dropped
    since they are outside the window etc.
    """
    nBool = boolArray.shape[0]
    maskIdx = 0
    for n in range(nBool):
        if boolArray[n]:
            boolArray[n] = mask[maskIdx]
            maskIdx += 1

@jit
def flattenMaskedStructuredArray(inArray, inArrayMask, outArray):
    """
    using compressed() on a masked structured array does not
    work. Here is a workaround.
    
    inArray and inArrayMask should be 2d. outArray is 1d.
    """
    nX = inArray.shape[1]
    nY = inArray.shape[0]
    outIdx = 0
    for x in range(nX):
        for y in range(nY):
            if not inArrayMask[y, x]:
                outArray[outIdx] = inArray[y, x]
                outIdx += 1

@jit
def flatten3dMaskedArray(flatArray, in3d, mask3d, idx3d):
    """
    Used by writeData to flatten out masked 3d data into a 1d
    using the indexes and masked saved from when the array was created.
    """
    (maxPts, nRows, nCols) = in3d.shape
    for n in range(maxPts):
        for row in range(nRows):
            for col in range(nCols):
                if not mask3d[n, row, col]:
                    idx = idx3d[n, row, col]
                    val = in3d[n, row, col]
                    flatArray[idx] = val

@jit
def flatten2dMaskedArray(flatArray, in2d, mask2d, idx2d):
    """
    Used by writeData to flatten out masked 2d data into a 1d
    using the indexes and masked saved from when the array was created.
    """
    (maxPts, nRows) = in2d.shape
    for n in range(maxPts):
        for row in range(nRows):
            if not mask2d[n, row]:
                idx = idx2d[n, row]
                val = in2d[n, row]
                flatArray[idx] = val

    
@jit
def BuildSpatialIndexInternal(binNum, sortedBinNumNdx, si_start, si_count):
    """
    Internal function used by CreateSpatialIndex.
    
    Fills in the spatial index from the sorted bins created by CreateSpatialIndex.
    
    binNum is row * nCols + col where row and col are arrays of the row and col 
        of each element being spatially indexed.
    sortedBinNumNdx is argsorted binNum    
    si_start and si_count are output spatial indices
    """
    nCols = si_start.shape[1]
    nRows = si_start.shape[0]
    nThings = binNum.shape[0]
    for i in range(nThings):
        # get the bin of the sorted location of this element
        bn = binNum[sortedBinNumNdx[i]]
        # extract the row and column
        row = bn // nCols
        col = bn % nCols
        # range check in case outside of the bouds of index 
        # being created - not needed anymore as caller does this
        #if row >= 0 and col >= 0 and row < nRows and col < nCols:    
        if si_count[row, col] == 0:
            # first element of a new bin - save the start 
            # rest of elements in this bin should be next
            # since it is sorted
            si_start[row, col] = i
        # update count of elements
        si_count[row, col] += 1
    
@jit
def convertIdxBool2D(start_idx_array, count_array, outBool, outRow, outCol, 
                        outIdx, counts, outMask):
    """
    Internal function called by convertSPDIdxToReadIdxAndMaskInfo
    
    Convert SPD's default regular spatial index of pulse offsets and pulse 
    counts per bin into a boolean array (for passing to h5py for reading data), 
    an array of indexes and a mask for creating a 3d masked array of the data 
    extracted.
    
    Note: indexes returned are relative to the subset, not the file.

    start_idx_array 2d - array of start indexes
       input - from the SPD spatial index
    count_array 2d - array of counts
       input - from the SPD spatial index
    outBool 1d - same shape as the dataset size, but bool inited to False
       for passing to h5py for reading data
    outIdx 3d - (max(count_array), nRows, nCols) int32 inited to 0
       for constructing a masked array - relative to subset size
    outMask 3d - bool same shape as outIdx inited to True
       for constructing a masked array. Result will be False were valid data
    outRow same shape as outBool but uint32 created with numpy.empty()
       used internally only
    outCol same shape as outBool but uint32 empty()
       used internally only
    counts (nRows, nCols) int32 inited to 0
       used internally only
    """
    
    nRows = start_idx_array.shape[0]
    nCols = start_idx_array.shape[1]
    
    for col in range(nCols):
        for row in range(nRows):
            # go through each bin in the spatial index
        
            cnt = count_array[row, col]
            startidx = start_idx_array[row, col]
            for i in range(cnt):
                # work out the location in the file we need
                # to read this element from
                # seems a strange bug in numba/llvm where the
                # result of this add gets promoted to a double
                # so cast it back
                idx = int(startidx + i)
                outBool[idx] = True # tell h5py we want this one
                outRow[idx] = row   # store the row/col for this element
                outCol[idx] = col   # relative to this subset
                
    # go through again setting up the indexes and mask
    counter = 0
    n = outBool.shape[0]
    for j in range(n):
        if outBool[j]:
            # ok will be data extracted here
            # get the row and col of where it came from
            row = outRow[j]
            col = outCol[j]
            # get the current number of elements from this bin
            c = counts[row, col]
            # save the current element number at the right level
            # in the outIdx (using the current number of elements in this bin)
            outIdx[c, row, col] = counter
            # tell the masked array there is valid data here
            outMask[c, row, col] = False
            # update the current number of elements in this bin
            counts[row, col] += 1
            # update the current element number
            counter += 1

@jit
def convertIdxBool1D(start_idx_array, count_array, outBool, outRow, outIdx, 
                        counts, outMask):
    """
    Internal function called by convertSPDIdxToReadIdxAndMaskInfo
    
    Convert SPD's indexing of points from pulses, or waveforms from pulses
    into a single boolean array (for passing to h5py for reading data), 
    an array of indexes and a mask for creating a 3d masked array of the data 
    extracted.
    
    Note: indexes returned are relative to the subset, not the file.
    
    start_idx_array 1d - array of start indexes
       input - from the SPD index
    count_array 1d - array of counts
       input - from the SPD index
    outBool 1d - same shape as the dataset size, but bool inited to False
       for passing to h5py for reading data
    outIdx 2d - (max(count_array), nRows) int32 inited to 0
       for constructing a masked array - relative to subset size
    outMask 2d - bool same shape as outIdx inited to True
       for constructing a masked array. Result will be False were valid data
    outRow same shape as outBool but uint32 created with numpy.empty()
       used internally only
    counts (nRows, nCols) int32 inited to 0
       used internally only

    """
    
    nRows = start_idx_array.shape[0]
    if nRows == 0:
        return
    
    for row in range(nRows):
        # go through each bin in the index
        
        cnt = count_array[row]
        startidx = start_idx_array[row]
        for i in range(cnt):
            # work out the location in the file we need
            # to read this element from
            # seems a strange bug in numba/llvm where the
            # result of this add gets promoted to a double
            # so cast it back
            idx = int(startidx + i)
            outBool[idx] = True # tell h5py we want this one
            outRow[idx] = row # store the row for this element
                
    # go through again setting up the indexes and mask
    n = outBool.shape[0]
    counter = 0
    for j in range(n):
        if outBool[j]:
            # ok will be data extracted here
            # get the row of where it came from
            row = outRow[j]
            # get the current number of elements from this bin
            c = counts[row]
            # save the current element number at the right level
            # in the outIdx (using the current number of elements in this bin)
            outIdx[c, row] = counter
            # tell the masked array there is valid data here
            outMask[c, row] = False
            # update the current number of elements in this bin
            counts[row] += 1
            # update the current element number
            counter += 1
    
def CreateSpatialIndex(coordOne, coordTwo, binSize, coordOneMax, 
                coordTwoMin, nRows, nCols, indexDtype, countDtype):
    """
    Create a SPD grid spatial index given arrays of the coordinates of 
    the elements.
        
    This can then be used for writing a SPD V3/4 spatial index to file,
    or to re-bin data to a new grid.
        
    Any elements outside of the new spatial index are ignored and the
    arrays returned will not refer to them.

    Parameters:
        coordOne is the coordinate corresponding to bin row. 
        coordTwo corresponds to bin col.
            Note that coordOne will always be reversed, in keeping with widespread
            conventions that a Y coordinate increases going north, but a grid row number
            increases going south. This same assumption will be applied even when
            the coordinates are not cartesian (e.g. angles). 
        binSize is the size (in world coords) of each bin. The V3/4 index definition
            requires that bins are square. 
        coordOneMax and coordTwoMin define the top left of the 
            spatial index to be built. This is the world coordinate of the
            top-left corner of the top-left bin
        nRows, nCols - size of the spatial index
        indexDtype is the numpy dtype for the index (si_start, below)
        countDtype is the numpy dtype for the count (si_count, below)
            
    Returns:
        mask - a 1d array of bools of the valid elements. This must be applied
            before sortedBins.
        sortedBins - a 1d array of indices that is used to 
            re-sort the data into the correct order for using 
            the created spatial index. Since the spatial index puts
            all elements in the same bin together this is a very important
            step!
        si_start - a 2d array of start indexes into the sorted data (see
            above)
        si_count - the count of elements in each bin.
    """
    # work out the row and column of each element to be put into the
    # spatial index
    row = numpy.floor((coordOneMax - coordOne) / binSize)
    col = numpy.floor((coordTwo - coordTwoMin) / binSize)
        
    # work out the elements that aren't within the new spatial 
    # index and remove them
    validMask = (row >= 0) & (col >= 0) & (row < nRows) & (col < nCols)
    row = row[validMask].astype(numpy.uint32)
    col = col[validMask].astype(numpy.uint32)
    coordOne = coordOne[validMask]
    coordTwo = coordTwo[validMask]
        
    # convert this to a 'binNum' which is a combination of row and col
    # and can be sorted to make a complete ordering of the 2-d grid of bins
    binNum = row * nCols + col
    # get an array of indices of the sorted version of the bins
    sortedBinNumNdx = numpy.argsort(binNum)
    
    # output spatial index arrays
    si_start = numpy.zeros((nRows, nCols), dtype=indexDtype)
    si_count = numpy.zeros((nRows, nCols), dtype=countDtype)
        
    # call our helper function to put the elements into the spatial index
    BuildSpatialIndexInternal(binNum, sortedBinNumNdx, si_start, si_count)
        
    # return array to get back to sorted version of the elements
    # and the new spatial index
    return validMask, sortedBinNumNdx, si_start, si_count

def convertSPDIdxToReadIdxAndMaskInfo(start_idx_array, count_array, outSize):
    """
    Convert either a 2d SPD spatial index or 1d index (pulse to points, 
    pulse to waveform etc) information for reading with h5py and creating
    a masked array with the indices into the read subset.
        
    Parameters:
    start_idx_array is the 2 or 1d input array of file start indices from SPD
    count_array is the 2 or 1d input array of element counts from SPD
    outSize is the size of the h5py dataset to be read. 
        
    Returns:
    A 1d bool array to pass to h5py for reading the info out of the dataset.
        This will be outSize elements long
    A 3 or 2d (depending on if a 2 or 1 array was input) array containing
        indices into the new subset of the data. This array is arranged so
        that the first axis contains the indices for each bin (or pulse)
        and the other axis is the row (and col axis for 3d output)
        This array can be used to rearrange the data ready from h5py into
        a ragged array of the correct shape constaining the data from 
        each bin.
    A 3 or 2d (depending on if a 2 or 1 array was input) bool array that
        can be used as a mask in a masked array of the ragged array (above)
        of the actual data.
    """
    # create the bool array for h5py
    outBool = numpy.zeros((outSize,), dtype=numpy.bool)
    # work out the size of the first dimension of the index
    if count_array.size > 0:
        maxCount = count_array.max()
    else:
        maxCount = 0
        
    if count_array.ndim == 2:
        # 2d input - 3d output index and mask
        nRows, nCols = count_array.shape
        outIdx = numpy.zeros((maxCount, nRows, nCols), dtype=numpy.uint32)
        outMask = numpy.ones((maxCount, nRows, nCols), numpy.bool)
        # for internal use by convertIdxBool2D
        outRow = numpy.empty((outSize,), dtype=numpy.uint32)
        outCol = numpy.empty((outSize,), dtype=numpy.uint32)
        counts = numpy.zeros((nRows, nCols), dtype=numpy.uint32)
        
        convertIdxBool2D(start_idx_array, count_array, outBool, outRow, 
                        outCol, outIdx, counts, outMask)
                            
    elif count_array.ndim == 1:
        # 1d input - 2d output index and mask
        nRows = count_array.shape[0]
        outIdx = numpy.zeros((maxCount, nRows), dtype=numpy.uint32)
        outMask = numpy.ones((maxCount, nRows), numpy.bool)
        # for internal use by convertIdxBool1D
        outRow = numpy.empty((outSize,), dtype=numpy.uint32)
        counts = numpy.zeros((nRows,), dtype=numpy.uint32)
            
        convertIdxBool1D(start_idx_array, count_array, outBool, outRow,
                            outIdx, counts, outMask)
    else:
        msg = 'only 1 or 2d indexing supported'
        raise ValueError(msg)
        
    # return the arrays
    return outBool, outIdx, outMask

def getSlicesForExtent(siPixGrid, siShape, overlap, xMin, xMax, yMin, yMax):
    """
    xMin, xMax, yMin, yMax is the extent snapped to the pixGrid.
    """
    imageSlice = None
    siSlice = None
    
    # work out where on the whole of file spatial index to read from
    xoff = int((xMin - siPixGrid.xMin) / siPixGrid.xRes)
    yoff = int((siPixGrid.yMax - yMax) / siPixGrid.yRes)
    xright = int(numpy.ceil((xMax - siPixGrid.xMin) / siPixGrid.xRes))
    xbottom = int(numpy.ceil((siPixGrid.yMax - yMin) / siPixGrid.yRes))
    xsize = xright - xoff
    ysize = xbottom - yoff
        
    # adjust for overlap
    xoff_margin = xoff - overlap
    yoff_margin = yoff - overlap
    xSize_margin = xsize + overlap * 2
    ySize_margin = ysize + overlap * 2
        
    # Code below adapted from rios.imagereader.readBlockWithMargin
    # Not sure if it can be streamlined for this case

    # The bounds of the whole image in the file        
    imgLeftBound = 0
    imgTopBound = 0
    imgRightBound = siShape[1]
    imgBottomBound = siShape[0]
        
    # The region we will, in principle, read from the file. Note that xSize_margin 
    # and ySize_margin are already calculated above
        
    # Restrict this to what is available in the file
    xoff_margin_file = max(xoff_margin, imgLeftBound)
    xoff_margin_file = min(xoff_margin_file, imgRightBound)
    xright_margin_file = xoff_margin + xSize_margin
    xright_margin_file = min(xright_margin_file, imgRightBound)
    xSize_margin_file = xright_margin_file - xoff_margin_file

    yoff_margin_file = max(yoff_margin, imgTopBound)
    yoff_margin_file = min(yoff_margin_file, imgBottomBound)
    ySize_margin_file = min(ySize_margin, imgBottomBound - yoff_margin_file)
    ybottom_margin_file = yoff_margin + ySize_margin
    ybottom_margin_file = min(ybottom_margin_file, imgBottomBound)
    ySize_margin_file = ybottom_margin_file - yoff_margin_file
        
    # How many pixels on each edge of the block we end up NOT reading from 
    # the file, and thus have to leave as null in the array
    notRead_left = xoff_margin_file - xoff_margin
    notRead_right = xSize_margin - (notRead_left + xSize_margin_file)
    notRead_top = yoff_margin_file - yoff_margin
    notRead_bottom = ySize_margin - (notRead_top + ySize_margin_file)
        
    # The upper bounds on the slices specified to receive the data
    slice_right = xSize_margin - notRead_right
    slice_bottom = ySize_margin - notRead_bottom
        
    if xSize_margin_file > 0 and ySize_margin_file > 0:
        # Now read in the part of the array which we can actually read from the file.
        # Read each layer separately, to honour the layerselection
            
        # The part of the final array we are filling
        imageSlice = (slice(notRead_top, slice_bottom), slice(notRead_left, slice_right))
        # the input from the spatial index
        siSlice = (slice(yoff_margin_file, yoff_margin_file+ySize_margin_file), 
                    slice(xoff_margin_file, xoff_margin_file+xSize_margin_file))

    return imageSlice, siSlice