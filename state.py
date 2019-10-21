'''
This script gets the US state outlines and makes a tabular
list of their centers.
'''
import sys
import os
import os.path
import urllib
import shapefile
import zipfile
import logging
import ogr # gdal/ogr
from default_parser import DefaultArgumentParser
import luconfig
from memoize import memoized


logger=logging.getLogger('state')

# Getting real centers for the states is a little complicated because
# the polygonal coordinates are on the surface of the earth. Here
# are two versions from the web because we don't need it to be 
# terribly accurate.
# from 'http://www.maptechnavigation.com/support/forums/messages.cfm?'
#      'threadid=1101&CFID=2901702&CFTOKEN=69902104'
_state_centers1='''
STATE NAME FIPS LON LAT
DC District of Columbia 11 -77.01692 38.89078
AK Alaska 02 -149.05656 63.08239
AL Alabama 01 -86.68338 32.60661
AR Arkansas 05 -92.12893 34.75712
AS American Samoa 60 -170.70473 -14.31125
AZ Arizona 04 -111.93248 34.17163
CA California 06 -119.25700 37.26842
CO Colorado 08 -105.54781 38.99604
CT Connecticut 09 -72.75720 41.52281
DE Delaware 10 -75.41699 39.14561
FL Florida 12 -81.68751 28.06163
GA Georgia 13 -83.22671 32.67985
GU Guam 66 144.78514 13.44272
HI Hawaii 15 -155.43683 19.59269
IA Iowa 19 -93.39193 41.93699
ID Idaho 16 -114.14093 45.49204
IL Illinois 17 -89.51148 39.74655
IN Indiana 18 -86.44417 39.77044
KS Kansas 20 -98.32368 38.49518
KY Kentucky 21 -85.76394 37.81914
LA Louisiana 22 -91.42602 30.97712
MA Massachusetts 25 -71.71267 42.06141
MD Maryland 24 -76.74451 38.82523
ME Maine 23 -69.02289 45.26101
MI Michigan 26 -84.62436 43.74509
MN Minnesota 27 -93.35500 46.43515
MO Missouri 29 -92.43575 38.29989
MP Marianas 69 145.75757 15.19046
MS Mississippi 28 -89.86849 32.59474
MT Montana 30 -110.05062 46.67912
NC North Carolina 37 -79.88784 35.21638
ND North Dakota 38 -100.30356 47.46736
NE Nebraska 31 -99.68333 41.49784
NH New Hampshire 33 -71.63407 43.99997
NJ New Jersey 34 -74.37751 40.13828
NM New Mexico 35 -106.02717 34.17184
NV Nevada 32 -117.01664 38.50227
NY New York 36 -75.81028 42.75633
OH Ohio 39 -82.67375 40.19406
OK Oklahoma 40 -98.71880 35.31003
OR Oregon 41 -120.51327 44.13156
PA Pennsylvania 42 -77.61161 40.99494
PR Puerto Rico 72 -66.58765 18.19958
RI Rhode Island 44 -71.50537 41.57887
SC South Carolina 45 -80.94851 33.62318
SD South Dakota 46 -100.25584 44.21638
TN Tennessee 47 -85.97945 35.83453
TX Texas 48 -100.07718 31.16937
UT Utah 49 -111.54490 39.49720
VA Virginia 51 -79.46565 37.99920
VI Virgin Islands 78 -64.73421 17.72882
VT Vermont 50 -72.47119 43.86954
WA Washington 53 -120.84015 47.27291
WI Wisconsin 55 -89.84694 44.78330
WV West Virginia 54 -80.18361 38.92065
WY Wyoming 56 -107.55226 42.99929
UM Midway 74 -177.37427 28.19667
'''

    

# From http://www.maxmind.com/app/state_latlon
_state_centers2='''
"state","latitude","longitude"
AK,61.3850,-152.2683
AL,32.7990,-86.8073
AR,34.9513,-92.3809
AS,14.2417,-170.7197
AZ,33.7712,-111.3877
CA,36.1700,-119.7462
CO,39.0646,-105.3272
CT,41.5834,-72.7622
DC,38.8964,-77.0262
DE,39.3498,-75.5148
FL,27.8333,-81.7170
GA,32.9866,-83.6487
HI,21.1098,-157.5311
IA,42.0046,-93.2140
ID,44.2394,-114.5103
IL,40.3363,-89.0022
IN,39.8647,-86.2604
KS,38.5111,-96.8005
KY,37.6690,-84.6514
LA,31.1801,-91.8749
MA,42.2373,-71.5314
MD,39.0724,-76.7902
ME,44.6074,-69.3977
MI,43.3504,-84.5603
MN,45.7326,-93.9196
MO,38.4623,-92.3020
MP,14.8058,145.5505
MS,32.7673,-89.6812
MT,46.9048,-110.3261
NC,35.6411,-79.8431
ND,47.5362,-99.7930
NE,41.1289,-98.2883
NH,43.4108,-71.5653
NJ,40.3140,-74.5089
NM,34.8375,-106.2371
NV,38.4199,-117.1219
NY,42.1497,-74.9384
OH,40.3736,-82.7755
OK,35.5376,-96.9247
OR,44.5672,-122.1269
PA,40.5773,-77.2640
PR,18.2766,-66.3350
RI,41.6772,-71.5101
SC,33.8191,-80.9066
SD,44.2853,-99.4632
TN,35.7449,-86.7489
TX,31.1060,-97.6475
UT,40.1135,-111.8535
VA,37.7680,-78.2057
VI,18.0001,-64.8199
VT,44.0407,-72.7093
WA,47.3917,-121.5708
WI,44.2563,-89.6385
WV,38.4680,-80.9696
WY,42.7475,-107.2085
'''

def t():
    print 'blah'


def state_center_data(data_idx=1):
    if data_idx is 1:
        fips_to_center=dict()
        for line in _state_centers1.split(os.linesep):
            sp=line.strip().split()
            try:
                two=sp[0]
                lon=float(sp[-2])
                lat=float(sp[-1])
                fips=int(sp[-3])
                name=sp[1:-3]
                fips_to_center[fips] = {'twoletter' : two,
                    'lon' : lon, 'lat' : lat, 'name' : name, 'fips' : fips}
            except:
                pass
                
        return fips_to_center
        
    else:
        fstate_to_center=dict()
        for line in _state_centers2.split(os.linesep):
            sp=line.strip().split(',')
            try:
                two=sp[0]
                lon=float(sp[1])
                lat=float(sp[2])
                fstate_to_center[two]={'twoletter' : two, 'lon':lon,'lat':lat}
            except:
                pass
                
        return fstate_to_center


state_url='http://www2.census.gov/geo/tiger/TIGER2007FE/fe_2007_us_state.zip'


def retrieve_states(url):
    local_name=os.path.split(url)[-1]
    if not os.path.exists(local_name):
        try:
            urllib.urlretrieve(url,local_name)
        except Exception,e:
            logger.exception('Could not retrieve %s.' % 
                    (url,))
    
    dir_name=''.join(local_name.split('.')[0:-1])
    if not os.path.exists(dir_name):
        try:
            os.mkdir(dir_name)
        except Exception,e:
            logger.exception('Could not make directory into which'
                            ' to put the shapefile')

    shapefile_name='%s/%s.shp' % (dir_name,dir_name)
    if not os.path.exists(shapefile_name):
        z=zipfile.ZipFile(local_name)
        z.extractall(dir_name)
        
    return shapefile_name

    

@memoized
def state_basics():
    '''
    The shapefile has simple information, plus geometry. This returns
    the simple field information and the bounding box in lat-long.

    Returns: A dictionary from integer geoids of US states and territories
             to a dictionary containing fields from the TIGER shapefile,
             listed below, and a "bounds" field with bounds in lat-long.
    
    STATEFP10 - 2010 Census state Federal Information Processing Standards
                 (FIPS) code
    STATENS10 - 2010 Census state ANSI code
    GEOID10 - State identifier; state FIPS code
    STUSPS10 - 2010 Census United States Postal Service state abbreviation
    NAME10 - 2010 Census state name
    LSAD10 - 2010 Census legal/statistical area description code for state
               blank
    MTFCC10 - MAF/TIGER feature class code (G4000 always)
    FUNCSTAT10 - (A) Active government providing primary general-purpose
                     functions
                 (N) Nonfunctioning legal entity
    ALAND10 - 2010 Census land area (square meters)
    AWATER10 - 2010 Census water area (square meters)
    INTPTLAT10 - 2010 Census latitude of the internal point
    INTPTLON10 - 2010 Census longitude of the internal point
    bounds - Tuple of (long-West, long-East, lat-South, lat-North)
    '''
    driver = ogr.GetDriverByName('ESRI Shapefile')
    logger.debug(luconfig.get('state'))
    inds=driver.Open(luconfig.get('state'))
    layer=inds.GetLayer()
    fields=layer.GetLayerDefn()
    field_names=dict()
    for fidx in range(fields.GetFieldCount()):
        afield=fields.GetFieldDefn(fidx).GetName()
        field_names[fidx]=afield
    logger.debug(", ".join(field_names.values()))

    state_records=dict()
    feature=layer.GetNextFeature()
    while feature:
        record=dict()
        for i,field_name in field_names.iteritems():
            record[field_name]=feature.GetField(i)

        geom=feature.GetGeometryRef()
        record['bounds']=geom.GetEnvelope()
        state_records[int(record['GEOID10'])]=record

        feature=layer.GetNextFeature()

    return state_records
    

@memoized
def fips_to_state():
    states=state_basics()
    fts=dict()
    for id, s in states.iteritems():
        fts[id]=s['STUSPS10']
    return fts


@memoized
def state_to_fips():
    states=state_basics()
    fts=dict()
    for id, s in states.iteritems():
        fts[s['STUSPS10']]=id
    return fts


if __name__ == '__main__':
    parser = DefaultArgumentParser(description='read data about U.S. states')
    parser.add_function('get', 'retrieve dataset')
    parser.add_function('centers', 'find state centers')
    parser.add_function('basics', 'get shapefile state properties')
    parser.add_function('test','Whether to run unit tests on this file.')
    parser.add_argument('--file',metavar='file',type=str,
                        nargs="*",help='A file to read')

    args = parser.parse_args()

    if args.file and len(args.file)>0:
        state_shapefile=args.file[0]
    else:
        state_shapefile=None
        
    if args.get:
        state_shapefile=retrieve_states(state_url)
        
    if args.centers:
        if not state_shapefile:
            logging.error('In order to compute state centers, specify a '
                            'state shapefile on the command line.')
        print os.linesep.join(state_centers(state_shapefile))
    
    if not parser.any_function():
        parser.print_help()
