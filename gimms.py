import os
import sys
from datetime import date
import logging
import datetime
import fileinput
import glob
import itertools
from collections import defaultdict
import numpy as np
import cPickle
import gdal
import osr
from gdalconst import GA_ReadOnly, GDT_Float32
import default_parser
import luconfig

logger=logging.getLogger('gimms')

# The spatial reference info inside the GIMMS files is incomplete.
GIMMS_PROJ4 = ("+proj=aea +lat_1=20 +lat_2=60 +lat_0=45 " +
    "+lon_0=-103 +x_0=0 +y_0=0 +ellps=NAD27 +units=m +no_defs ")

def date_to_gimms_filename(when):
    if when.day<16: day_key='a'
    else: day_key='b'

    month=when.strftime('%b')[0:3].lower()
    filekey='NA%s%s15%s.n[0-9][0-9]-VIg' % (when.strftime('%y'), month, day_key)
    # vsigzip is a magic prepend that unzips gzipped files.
    gimms_dir=luconfig.get('gimms')
    name = '%s/%s/%s.tif.gz' % (gimms_dir, filekey, filekey)
    files=glob.glob(name)
    logger.debug('glob found %s' % str(files))
    if not files:
        logger.error('Cannot find file %s' % name)
    name = '/vsigzip/%s' % files[0]
    logger.debug('reading file %s' % name)
    return name
    

class pixel_to_xy(object):
    '''
    Use a GDAL transform from dataset.GetGeoTransform()
    to convert pixels into lat and long coordinates.
    '''
    def __init__(self, gdal_dataset):
        self.g_transform=gdal_dataset.GetGeoTransform()
        srs=osr.SpatialReference()
        srs.ImportFromProj4(GIMMS_PROJ4)
        lat_long_srs=srs.CloneGeogCS()
        self.c_transform=osr.CoordinateTransformation(srs, lat_long_srs)

    def __call__(self, p, l):
        t=self.g_transform
        xy=(t[0]+p*t[1]+l*t[2], t[3]+p*t[4]+l*t[5])
        return self.c_transform.TransformPoint( xy[0], xy[1] )


def gimms_to_xy():
    '''
    Return an functor which turns pixel/line into long-lat.
    '''
    ds=gdal.Open(date_to_gimms_filename(datetime.date(2000, 1, 1)),
                 gdal.GA_ReadOnly)
    return pixel_to_xy(ds)


def get_greens(when, x, y):
    '''
    Get NDVI values at the specified locations on the given date.
    The date is a datetime.
    The where_array is a list of (pixel,line) coordinates in the gimms file.
    where array is shape (n,2).
    '''
    minx=min(x)
    xsize=1+max(x)-minx
    miny=min(y)
    ysize=1+max(y)-miny
    logger.debug('size x %d y %d' % (xsize,ysize))

    ds=gdal.Open(date_to_gimms_filename(when), GA_ReadOnly)
    band=ds.GetRasterBand(1)

    arr = ds.ReadAsArray(int(minx), int(miny), int(xsize), int(ysize))

    # Switch x and y because ReadAsArray returnes an array such that
    # you access numpy with arr[y,x]. Yes.
    return arr[y-miny,x-minx]



def year_trace(year, x, y):
    '''
    Pull the NDVI values for the whole year at specified pixel coords.
    '''
    year=int(year)
    assert(isinstance(x,np.ndarray))
    assert(isinstance(y,np.ndarray))
    assert(x.size==y.size)

    data=np.zeros((12*2,len(x)), dtype=np.int16)
    days=np.zeros(12*2, dtype=np.int)

    for i, (mon,day) in enumerate(itertools.product(range(1,13),[1,16])):
        when=datetime.date(year,mon,day)
        data[i,:]=get_greens(when,x,y)
        days[i]=(when-datetime.date(year,1,1)).days

    return days, data.transpose()


def pixel_with_max_wheat(weighted_counties):
    '''
    The county data coming in is the (pixel, line, weight). Which pixel and
    line is the largest?
    '''
    c_arr=np.zeros(len(weighted_counties),dtype=np.int)
    x_arr=np.zeros(len(weighted_counties),dtype=np.int)
    y_arr=np.zeros(len(weighted_counties),dtype=np.int)

    for i, county in enumerate(weighted_counties):
        x,y,weight=weighted_counties[county]
        max_idx=np.argsort(weight)[-1]
        c_arr[i]=county
        x_arr[i]=x[max_idx]
        y_arr[i]=y[max_idx]

    return c_arr, x_arr, y_arr


'''
Tab-delimited list of county geoid, x, y, cover code, square meters
'''
file_sample='''
28104	784	663	112	11163.5
28107	784	662	111	36163.5
28107	784	662	121	25091.9
Other crap.
28107	784	662	122	22147.2
28107	784	662	141	48570.4
28107	784	662	142	4051.59
28107	784	662	152	37061.7
28107	784	662	181	12041.9
28107	784	662	190	7566.78
28107	784	662	195	2266.32
28107	784	663	121	7566.78
28107	784	663	195	2266.32
28108	784	662	121	2.32
'''

def read_code_stream(lines):
    '''Turn the raw file into an array of typed values'''
    for line in lines:
        splitted=line.split('\t')
        if len(splitted) is 5:
            (geoid, x, y, cover) = [int(x) for x in splitted[0:4]]
            area=float(splitted[4])
            yield (geoid, x, y, cover, area)


class weight_function(object):
    def __init__(self,wheatish):
        self._wheat=wheatish
        self._mask=np.zeros(shape=(255,),dtype=np.bool)
        self._mask[self._wheat]=True
    def __call__(self,areas):
        #return np.sum(areas[np.where(np.in1d(codes,self.wheat))])
        #print('weight %g' % np.sum(areas[self._mask]))
        return np.sum(areas[self._mask])



def apply_weights(code_stream,weights):
    cur_grid=None
    area_buf=np.zeros(255,dtype=np.float)

    for (geoid, x, y, cover, area) in code_stream:
        #print geoid, x, y, cover, area

        if cur_grid!=(geoid,x,y):
            if cur_grid:
                weight=weights(area_buf)
                #print 'apply_weights yielding', cur_grid, weight
                yield (cur_grid[0], cur_grid[1], cur_grid[2], weight)
                cur_grid=(geoid,x,y)
                area_buf.fill(0)
            cur_grid=(geoid,x,y)
            #print 'apply_weights sets new grid', cur_grid

        area_buf[cover]=area


    if cur_grid:
        weight=weights(area_buf)
        #print 'apply_weights yielding', weight
        yield (geoid, x, y, weight)



def county_array(weighted):
    '''
    Take the weight of each ndvi pixel in a county and assemble
    the nonzero ones into arrays.
    '''
    cur_geoid=None
    for (geoid, x, y, weight) in weighted:
        #print 'county_array gets', geoid, x, y, weight
        if (geoid!=cur_geoid):
            if cur_geoid and len(xl)>0:
                weights=np.array(wl)
                weights /= np.sum(weights)
                yield cur_geoid, np.array(xl), np.array(yl), weights
            cur_geoid=geoid
            xl=list()
            yl=list()
            wl=list()
        if weight>0:
            xl.append(x)
            yl.append(y)
            wl.append(weight)

    if cur_geoid and len(xl)>0:
        weights=np.array(wl)
        weights /= np.sum(weights)
        yield cur_geoid, np.array(xl), np.array(yl), weights


WHEAT=np.array(luconfig.get('wheat_codes').split(','))

def build(lines,wheat):
    typed=read_code_stream(lines)
    projected=apply_weights(typed,weight_function(wheat))
    by_county=county_array(projected)
    counties=dict()
    for (geoid, x, y, weights) in by_county:
        counties[geoid]=(x,y,weights)
    logger.info('build found %d counties' % len(counties))
    return counties



def test_build():
    print '===test_build'
    sample=file_sample.split(os.linesep)
    wheat=np.array([121,122,181])
    counties=build(sample,wheat)
    print counties
    assert(len(counties) is 2) # only those that are nonzero.


def test_get_green():
    print '===test_get_green'
    wheat=np.array([121,122,181])
    counties=build(file_sample.split(os.linesep),wheat)
    for county in counties:
        x,y,area = counties[county]
        ndvi = get_greens(date(2000,3,14),x,y)
        print county, np.dot(ndvi, area), ndvi, area



if __name__ == '__main__':
    parser = default_parser.DefaultArgumentParser(
        description='reading gimms for observations')
    parser.add_function('test','run tests')
    parser.add_function('weights','precalculate the weights')
    parser.add_argument('files',metavar='files', type=str, nargs='+',
                        help='files to search for county code data')
    args=parser.parse_args()
    
    if args.test:
        test_build()
        test_get_green()
        sys.exit(0)

    if args.weights:
        counties=build(fileinput.input(args.files), WHEAT)
        cPickle.dump(counties,open('/media/data0/counties/grid.pickle','w'))
        #for county in sorted(counties):
        #    x, y, weight = counties[county]
        #    print county, x, y, weight
