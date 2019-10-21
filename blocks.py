'''
This script demonstrates reading a raster dataset with GDAL
using blocked / rasterline strategies.

Drew Dolgert
adolgert@cornell.edu
Cornell University
23 April 2012
'''
import os
import sys
import numpy as np
import struct
import gdal
from gdalconst import GA_ReadOnly, GDT_Byte
import logging
from argparse import ArgumentParser


logger = logging.getLogger('blocks')


def read_by_line_y(band):
    '''
    This example is from the tutorial at
    http://www.gdal.org/gdal_tutorial.html

    Args: band is a RasterBand from GDAL. It stores single bytes.
    Yields: (row index, Numpy array of raster lines)
    '''
    for yidx in range(band.YSize):
        scanline=band.ReadRaster(0,yidx,band.XSize,1,band.XSize,1,GDT_Byte)
        arr=np.array(struct.unpack('B'*band.XSize,scanline),dtype=np.uint8)
        yield ((0,yidx),arr)



def read_by_line_x(band):
    '''
    This example is from the tutorial at
    http://www.gdal.org/gdal_tutorial.html

    Args: band is a RasterBand from GDAL. It stores single bytes.
    Yields: (row index, Numpy array of raster lines)
    '''
    for xidx in range(band.XSize):
        scanline=band.ReadRaster(xidx,0,1,band.YSize,1,band.YSize,GDT_Byte)
        arr=np.array(struct.unpack('B'*band.YSize,scanline),dtype=np.uint8)
        yield ((xidx,0),arr)



def read_by_multiline(band,line_cnt):
    '''
    This example is from the tutorial at
    http://www.gdal.org/gdal_tutorial.html

    Args: band is a RasterBand from GDAL. It stores single bytes.
    Yields: (row index, Numpy array of raster lines)
    '''
    logger.debug('Reading %d lines at a time' % line_cnt)

    for yidx in range(0, band.YSize, line_cnt):
        read_cnt=min(line_cnt, band.YSize-yidx)
        scanline=band.ReadRaster(0, yidx, band.XSize, read_cnt,
                                 band.XSize, read_cnt, GDT_Byte)
        arr=np.array(struct.unpack('B'*band.XSize*read_cnt, scanline),
                     dtype=np.uint8).reshape((band.XSize, read_cnt))
        yield ((0,yidx),arr)



def read_by_block(band):
    '''
    Read whatever blocksize the file uses.

    Args: band is a gdal.RasterBand of byte values.
    Yields: ((x,y) of corner, numpy array of values)
    '''
    block=band.GetBlockSize()
    logger.info('block size %d %d' % (block[0],block[1]))

    # Note that y and x are switched b/c that's how ReadAsArray works.
    main_buf=np.zeros((block[1],block[0]),dtype=np.uint8)

    for yidx in range(0, band.YSize, block[1]):
        for xidx in range(0, band.XSize, block[0]):
            ysize=min(block[1], band.YSize-yidx)
            xsize=min(block[0], band.XSize-xidx)
            if xsize is block[0] and ysize is block[1]:
                xform_buf=main_buf
            else:
                xform_buf=np.zeros((ysize,xsize),dtype=np.uint8)

            band.ReadAsArray(xidx, yidx, xsize, ysize,
                             xsize, ysize, xform_buf)
            yield ((xidx,yidx),xform_buf)



class DefaultArgumentParser(ArgumentParser):
    '''This adds some default behaviors to the argument parsing.'''

    def __init__(self,*args,**kwargs):
        ArgumentParser.__init__(self,*args,**kwargs)
        self.add_argument('--verbose','-v',dest='verbose',action='store_true',
                          default=False,help='print debug messages')
        self.add_argument('--quiet','-q',dest='quiet',action='store_true',
                          default=False,help='print only exceptions')


    def add_function(self,name,msg):
        '''A shorthand for created a boolean flag.'''
        self.add_argument('--%s'%name,dest=name,action='store_true',
                        default=False,help=msg)


    def parse_args(self):
        args=ArgumentParser.parse_args(self)
        log_level=logging.INFO
        if args.verbose:
            log_level=logging.DEBUG
        elif args.quiet:
            log_level=logging.ERROR
        logging.basicConfig(level=log_level)
        return args



if __name__ == '__main__':
    parser=DefaultArgumentParser(description='tests speed of reading rasters')
    parser.add_function('liney','Read file one line at a time, stepping y.')
    parser.add_function('linex','Read file one line at a time, stepping x.')
    parser.add_function('multiline','Read file one line at a time, stepping '
                        'y by count')
    parser.add_function('block','Read file one block at a time.')

    parser.add_argument('--count',dest='count',type=int,default=32,
                        help='Read n scanlines at a time.')

    parser.add_argument('filenames', metavar='filenames', type=str,
                        nargs='+', help='The file to read.')

    args=parser.parse_args()

    if not args.filenames:
        print 'Is there a file you would like to read? I don\'t see it.'
        parser.print_help()
        sys.exit(1)

    ds=gdal.Open(args.filenames[0], GA_ReadOnly)
    band=ds.GetRasterBand(1)
    logger.info('xsize: %d ysize: %d' % (band.XSize, band.YSize))

    reader=None
    if args.linex:
        reader=read_by_line_x

    if args.liney:
        reader=read_by_line_y

    if args.multiline:
        reader = lambda x: read_by_multiline(x,args.count)

    if args.block:
        reader=read_by_block

    if reader:
        byte_cnt=0
        for (x,y), line in reader(band):
            byte_cnt+=line.size
        logger.info('Read %d bytes' % byte_cnt)
    else:
        print 'Give one option of line, multiline, block.%s' % os.linesep
        parser.print_help()


