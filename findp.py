'''
In order to load this script from within qgis, do this:
import sys
sys.path.append('.')
import findp

It could also be run from the command line if you install
gdal and PyQt4.

These examples started from the pygis-cookbook.
http://qgis.org/pyqgis-cookbook/loadlayer.html
'''
#from qgis.core import QFileInfo
import os
import sys
import re
import glob
import os.path
import subprocess
import traceback
import collections
import numpy as np
try:
    import qgis.core as qcore
    import qgis.utils
except ImportError,e:
    print 'Could not load qgis. That may be OK.'
import struct
import gdal
from gdalconst import *
import logging
import logging.handlers
from argparse import ArgumentParser
try:
    import PyQt4.QtGui
    import PyQt4.QtCore
except ImportError,e:
    print 'Could not load Qt. Do you really need it?'


logger=logging.getLogger('findp')


# wheat, oat, barley, rye
# This can be read from a file, but it's more convenient here.
# This is wheat, barley, oats, rye
#wheatish=np.array([21,22,23,24,26,27,28,225,226,230,233,234,235,236,
#                   237,238,240,254])
# This is Wheat|Wht
wheatish=np.array([22, 23, 24, 26, 225, 230, 234, 236, 238])


class UnbufferedStream:
     def __init__(self, stream):
         self.stream = stream
     def write(self, data):
         self.stream.write(data)
         self.stream.flush()
     def __getattr__(self, attr):
         return getattr(self.stream, attr)


def log(level='debug'):
    level=level.upper()
    userlevel=logging.DEBUG
    logging.basicConfig(filename='script.log',level=userlevel)

    logger.debug('I\'m debugging!')
    logger.info('It\'s info.')


nlcd=luconfig.get('cdls')


def read_vecs():
    vsource=luconfig.get('county_region')
    vl=qcore.QgsVectorLayer(vsource,'combined','ogr')
    return (vl,)



def read_crop():
    '''
    This is the cropland data layer.
    hasPyramids=True
    single band. This means it has a gray band called "Band 1".
    Does not use a provider for setting/retrieving values.
    paletted color
    print rl.width(), rl.height() : 153811 96523 
    The extent is in Albers Equal Area.
    print rl.extent().toString()
    -2356095.0000000000000000,276915.0000000000000000 :
    2258235.0000000000000000,3172605.0000000000000000

    for i in range(11): print pl[i].level, pl[i].xDim, pl[i].yDim, ' --- '
    2 76906 48262 --- 4 38453 24131 --- 8 19227 12066 --- 16 9614 6033 ---
    32 4807 3017 --- 64 2404 1509 --- 128 1202 755 --- 256 601 378 ---
    512 301 189 --- 1024 151 95 --- 2048 76 48
    '''
    source=luconfig.get('cdls')
    # Example uses the QFileInfo class. I can't find it in these modules.
    # The class seems no longer to be exported, and all it did was manipulate
    # paths, so replace it with functionality in os.path.
    #file_info=qcore.QFileInfo(source)
    #base_name = file_info.baseName()
    rlayer=qcore.QgsRasterLayer(source,os.path.basename(source))
    if not rlayer.isValid():
        print('Layer failed to load: %s' % source)
    return rlayer


class crop_transform(object):
    def __init__(self,geo_transform):
        '''
        Call as crop_transform(dataset.GetGeoTransform()).
        From docs on GDalDataset::GetGeoTransform()
        '''
        self.v_=geo_transform

    def xy(self,x,y):
        '''
        Returns the upper-left corner of the pixel for
        a North-up image. For x=0, y=0, it is the upper-left
        pixel of the whole image.
        '''
        v=self.v_
        return (v[0]+x*v[1]+y*v[2], v[3]+x*v[4]+y*v[5])

    def mid(self,x,y):
        ul=self.xy(x,y)
        lr=self.xy(x+1,y+1)
        return (0.5*(ul[0]+lr[0]),0.5*(ul[1]+lr[1]))



def crop_data(filename):
    '''
    http://www.gdal.org/gdal_tutorial.html
    '''
    ds=gdal.Open(filename,GA_ReadOnly)
    band=ds.GetRasterBand(1)
    
    print 'xsize:',band.XSize, 'ysize:',band.YSize

    for yidx in range(band.YSize):
        scanline=band.ReadRaster(0,yidx,band.XSize,1,band.YSize,1,GDT_Byte)
        print len(scanline)
        tb=struct.unpack('B'*band.YSize,scanline)
        if not all([x is 0 for x in tb]):
            print "Found something nonzero", yidx
            return ds


def attribs(vlayer,limit=None):
    '''
    This pulls attributes. We could getIntersection with the square
    from the other dataset and then get the area.
    '''
    provider = vlayer.dataProvider()

    feat = qcore.QgsFeature()
    allAttrs = provider.attributeIndexes()

    # start data retrieval: fetch geometry and all attributes for each feature
    provider.select(allAttrs)

    if not limit:
        limit=1
    read_idx=0
    # retrieve every feature with its geometry and attributes
    while read_idx<limit and provider.nextFeature(feat):

        # fetch geometry
        geom = feat.geometry()
        print "Feature ID %d: " % feat.id() ,

        # show some information about the feature
        # example calls geom.vectorType(). Now changed just to type().
        if geom.type() == qcore.QGis.Point:
            x = geom.asPoint()
            print "Point: " + str(x)
        elif geom.type() == qcore.QGis.Line:
            x = geom.asPolyline()
            print "Line: %d points" % len(x)
        elif geom.type() == qcore.QGis.Polygon:
            x = geom.asPolygon()
            # x is a list of lists of points.
            numPts = 0
            for ring in x:
                numPts += len(ring)
                print "Polygon: %d rings with %d points" % (len(x), numPts)
        else:
            print "Unknown"

        # fetch map of attributes
        attrs = feat.attributeMap()

        # attrs is a dictionary: key = field index, value = QgsFeatureAttribute
        # show all attributes and their values
        for (k,attr) in attrs.iteritems():
            print "%d: %s" % (k, attr.toString())

        if limit:
            read_idx+=1


def create_copy(ds,subset,filename=None,
                inset=None):
    '''
    ds is a gdal dataset for cropland datalayer
    '''
    if not filename: filename=luconfig.get('just_wheat')
    xsize=(ds.RasterXSize-1)/subset + 1
    ysize=(ds.RasterYSize-1)/subset + 1
    if inset:
        (xsize,ysize)=inset
    driver=ds.GetDriver()
    #driver=gdal.GetDriverByName('HFA')
    logger.debug('About to GDALCreate a file called %s' % filename)
    try:
        print dir(driver)
        dst_ds=driver.Create(filename,xsize,ysize,1,gdal.GDT_Byte)
    except Exception,e:
        logger.exception(e)
        print 'problem creating dataset',e.message()
        sys.exit(1)
    logger.debug('GDALCreate returned a %s' % str(dst_ds))

    # Copy the transform, but change the pixel width.
    trans=list(ds.GetGeoTransform())
    trans[1]*=subset
    trans[5]*=subset
    dst_ds.SetGeoTransform(trans)
    dst_ds.SetProjection(ds.GetProjection())
    return dst_ds,xsize,ysize



def cereal_codes(metadata_file=None):
    '''
    Retrieve tables from the metadata of the CDLS.

    >>>[state,[state_accuracy,cover]]=cereal_codes()
    >>>print cover.fields
    [u'Cover Type ', u'Attribute Code ', u'*Correct Pixels ',
    u"Producer's Accuracy ", u'Omission Error ', u'Kappa ',
    u"User's Accuracy ", u'Commission Error ', u"Cond'l Kappa "]
    >>>print cover.records[0]
    [u'Corn', u'1', u'8459170', u'98.26%', u'1.74%', u'0.960', u'98.37%',
    u'1.63%', u'0.962']
    '''
    import xml.dom.minidom
    try:
        dom=xml.dom.minidom.parse(open(metadata_file))
    except Exception:
        logger.exception('Could not open the metadata file.')

    cdls_dir=os.path.split(luconfig.get('cdls'))[0]
    if not metadata_file: metadata_file=os.path.join(cdls_dir,
                                                'cdlmeta_30m_r_ia_2011.xml')
    us_state=None
    places=dom.getElementsByTagName('placekey')
    for i in range(len(places)):
        guess_state=places[i].firstChild.nodeValue.strip()
        if len(guess_state)==2:
            us_state=guess_state
    #logger.debug('state is %s' % state)

    table_node=dom.getElementsByTagName('attraccr')
    if len(table_node) is 0:
        logger.error('Could not find the metadata tag with codes.')
        return
    elif len(table_node) > 1:
        logger.error('There is more than one element in metadata called '
                     'attraccr. Which one is the right one to use?')

    # The first child of this node contains the text of the table.
    table_text=table_node[0].firstChild.nodeValue

    # The table looks like this
    #Cover   Attribute
    #Type         Code
    #----         ----
    #Corn            1
    #Pop. or Orn     13
    # We use the --- to find the titles, then use the column count
    # to pull out values.
    has_entries=re.compile('[0-9,\.\%]+\w+[0-9,\.\%]+')
    separator_regexp=re.compile('^[\-\s]*$') # all - and space

    (INTABLE,NOT)=range(2)
    state=NOT
    Table=collections.namedtuple('Table',['fields','records'])
    tables=list()
    cur_table=None
    lines=list()
    for idx,line in enumerate(table_text.split(os.linesep)):
        if line.startswith('>'):
            line=line[1:]
        line=line.strip()
        #logger.debug('next line %s' % line)
        if state is NOT and len(line)>0 and separator_regexp.search(line):
            if cur_table:
                tables.append(cur_table)
            cur_table=list()
            # Find titles as those words above the ---- lines.
            sep_cols=[x.span() for x in re.finditer('\-+',line)]
            titles=['']*len(sep_cols)
            prev_line=lines.pop()
            while len(prev_line)>0:
                #logger.debug('prev_line is %s' % prev_line)
                for word_match in reversed([x for x in re.finditer('\S+',prev_line)]):
                    w_span=word_match.span()
                    for sep_idx,sep_span in enumerate(sep_cols):
                        if w_span[1]>=sep_span[0] and w_span[0]<=sep_span[1]:
                            titles[sep_idx]='%s %s' % (word_match.group(0),titles[sep_idx])
                prev_line=lines.pop()
            state=INTABLE
        elif state is INTABLE:
            if len(line)>0 and has_entries.search(line):
                # The number of columns is known from the titles.
                # The first column may have long names with spaces.
                cols=line.split()
                ncol0=1+len(cols)-len(titles)
                #logger.debug('col0 is %d cols are %s' % (ncol0,str(cols)))
                joined=[' '.join(cols[0:ncol0])]
                joined.extend(cols[ncol0:])
                entry=dict()
                #logger.debug('cols are %s' % (str(joined),))
                for title,val in zip(titles,joined):
                    entry[title]=val
                cur_table.append(joined)
            else:
                state=NOT
                tables.append(Table(titles,cur_table))
                cur_table=None

        lines.append(line)

    if cur_table:
        tables.append(cur_table)

    return (us_state,tables)


def are_cereal_codes_same(metafiles):
    '''
    Look through metadata to see whether the cereal codes
    are the same in every file.

    are_cereal_codes_same(glob.glob('2011_30m_cdls/cdlmeta*.xml'))
    '''
    all_types=set()
    all_codes=set()

    state_codes=dict()
    read_idx=0
    for f in metafiles:
        [state,tables]=cereal_codes(f)
        logger.debug('state is %s' % state)
        read_idx+=1
        cover=dict()
        for r in tables[1].records:
            cover[int(r[1])]=r[0]
            all_types.add(r[0])
            all_codes.add(int(r[1]))
        state_codes[state]=cover

    logger.debug('number of codes %d types %d for %d states' % 
                     (len(all_codes),len(all_types),read_idx))
    all_covers=dict()
    # Loop through 1-255
    for cover_idx in all_codes:
        # For each, make a map (name -> list of states using that name)
        cover_vals=collections.defaultdict(list)
        for state,cover in state_codes.items():
            if cover.has_key(cover_idx):
                all_covers[cover_idx]=cover[cover_idx]
                cover_vals[cover[cover_idx]].append(state)
        if len(cover_vals)>1:
            print('More than one name for this code %d' % cover_idx)
            # Show me which states use which names
            for k,v in cover_vals.items():
                print('%s: %s' % (k,str(v)))

    return all_covers



def cdls_code_key(filename='generic_cdl_attributes.tif.vat.dbf'):
    '''
    The cdls has a byte at each value. The key for those bytes is 
    sort of hard to get to because the online CropScape only shows
    you colors and the per-state xml metadata files only show a
    subset of the values used. It seems they show the crops but not things
    like Pasture or Barren. I can see these fields in the .img file
    if I use the strings command, but I can't seem to get them with
    gdal.

    One way to get them is to download the file 
    http://www.nass.usda.gov/research/Cropland/docs/generic_cdl_attributes.tif.vat.dbf.zip
    which contains generic_cdl_attributes.tif.vat.dbf. It's an XBase file,
    so reading it in Python seems to work if I install dbfpy.
    '''
    import dbfpy.dbf
    db=dbfpy.dbf.Dbf(filename)
    tabular=list()
    for rec in db:
        tabular.append((rec['VALUE'],rec['CLASS_NAME']))
    return tabular



def wheat_codes(pattern='Wheat|Wht',guesses=wheatish,
                code_db=None):
    '''
    Which codes can be cereal crops? Compare with the given guesses.
    '''
    if not code_db:
        cdls_dir=os.path.split(luconfig.get('cdls'))[0]
        code_db=os.path.join(cdls_dir,'generic_cdl_attributes.tif.vat.dbf')
    guesses=set(guesses)

    search=re.compile(pattern)

    found=dict()
    codes=cdls_code_key(code_db)
    for (value,name) in codes:
        if name and search.search(name):
            found[value]=name
    
    wheats=set(found.keys())

    logger.info('codes not in guesses: %s' % str(wheats-guesses))
    logger.info('codes not in wheats: %s' % str(guesses-wheats))

    return found



def wheat_codes_gdalinfo(pattern='Wheat|Wht',filename='2011_30m_cdls.img'):
    '''
    Found a better way to get wheat codes if you have gdalinfo installed.
    '''
    all_info=subprocess.check_output(['gdalinfo',filename])
    xml_info=all_info[all_info.find('<GDALRaster'):]
    dom=xml.dom.minidom.parseString(xml_info)
    rows=dom.getElementsByTagName('Row')
    search=re.compile(pattern)

    codes=dict() # numeric code -> name
    for r in rows:
        try:
            code=int(r.attributes['index'].value)
            # Each row has four columns, labeled <F/>
            name=r.getElementsByTagName('F')[4].firstChild.data.strip()
            if search.search(name):
                codes[code]=name
        except Exception,e:
            logger.debug('Could not translate code: %s'%e.message)
            
    return codes



def condense_crop(filename,subset=16):
    '''
    Take the nlcd and pull out just the density of wheat.
    Make a smaller image with a grayscale byte value.
    '''
    ds=gdal.Open(filename,GA_ReadOnly)
    logger.debug('opened %s' % filename)
    ds2,x,y=create_copy(ds,subset)
    logger.debug('created copy %s dim %d %d' % (str(ds2),x,y))

    raster = np.zeros( (y,x), dtype=np.uint8 )

    band=ds.GetRasterBand(1)
    
    logger.info('xsize: %d ysize: %d' % (band.XSize,band.YSize))
    bins=np.arange(256)
    inhist=np.zeros(len(bins)-1)


    maxwheat=0
    # Don't worry about not being divisible by 32 on last pixels.
    # Mostly water.
    for yidx in range(0,band.YSize-(band.YSize%subset),subset):
        #logger.debug('reading band %d scanline len %d' % (yidx,len(scanline)))

        dat=np.zeros((subset,band.XSize),dtype=np.uint8)
        for lineidx in range(subset):
            scanline=band.ReadRaster(0,yidx+lineidx,band.XSize,1,
                                 band.XSize,1,GDT_Byte)
            ar=np.array(struct.unpack('B'*band.XSize,scanline),
                        dtype=np.uint8)
            dat[lineidx,:]=ar
            inhist+=np.histogram(ar,bins)[0]

        for xidx in range(0,band.XSize-(band.XSize%subset),subset):
            subarray=dat[0:subset,xidx:(xidx+subset)]
            flat=subarray.flatten()
            if flat is None or len(flat)<subset*subset:
                logger.debug('xidx: %d yidx: %d len(sub): %d' % (xidx,yidx,
                                                                 len(flat)))
            counts=np.bincount(flat) # np version 1.6 has a minlength option
            val=np.sum(np.append(counts,np.zeros(255-len(counts)))[wheatish])
            if val>maxwheat:
                maxwheat=val
                logger.debug('max wheat value %d' % maxwheat)
            raster[yidx/subset,xidx/subset]=val
                         

        if yidx%(10*subset) is 0:
            logger.debug('at y %d out of %d' % (yidx,band.YSize))
            #logger.debug('hist %s' % str(inhist))

    ds2.GetRasterBand(1).WriteArray( raster )
    # Recommended way to close the file.
    ds2=None




def wheat_from_cdl(filename,outfile,inset=None):
    '''
    Pull wheat values out of crop dataland layer, but just pixel
    for pixel, not subsetting.
    '''
    ds=gdal.Open(filename,GA_ReadOnly)
    logger.debug('opened %s' % filename)
    ds2,x,y=create_copy(ds,1,outfile,inset)
    logger.debug('created copy %s dim %d %d' % (str(ds2),x,y))

    raster = np.zeros( (y,x), dtype=np.uint8 )
    logger.debug('allocated large raster')

    band=ds.GetRasterBand(1)
    
    logger.info('incoming xsize: %d ysize: %d' % (band.XSize,band.YSize))
    logger.info('outgoing xsize: %d ysize: %d' % (x,y))

    maxwheat=0
    for yidx in range(0,y):
        #logger.debug('reading band %d scanline len %d' % (yidx,len(scanline)))

        scanline=band.ReadRaster(0,yidx,band.XSize,1,
                                 band.XSize,1,GDT_Byte)
        ar=np.array(struct.unpack('B'*band.XSize,scanline),
                    dtype=np.uint8)[0:x]

        # Where the data value is one of the wheat values, put a 1, else a 0.
        ar2=np.where(np.in1d(ar,wheatish),ar,0)
        nonzero=len(ar2.nonzero()[0])
        if nonzero>maxwheat: maxwheat=nonzero
        raster[yidx,:]=ar2

        if yidx%50 is 0:
            logger.debug('at y %d out of %d nonzero %d' % (yidx,y,
                                                           maxwheat))
            maxwheat=0

    ds2.SetGeoTransform(ds.GetGeoTransform())
    ds2.SetProjection(ds.GetProjection())
    ds2.GetRasterBand(1).WriteArray( raster )
    # Recommended way to close the file.
    ds2=None





def wheat_from_cdl_blocked(filename,outfile,inset=None):
    '''
    Pull wheat values out of crop dataland layer, but just pixel
    for pixel, not subsetting.
    Work in blocks, specified as block=[x block, y block].
    '''
    ds=gdal.Open(filename,GA_ReadOnly)
    logger.debug('opened %s' % filename)
    ds2,x,y=create_copy(ds,1,outfile,inset)
    logger.debug('created copy %s dim %d %d' % (str(ds2),x,y))

    band=ds.GetRasterBand(1)
    block=band.GetBlockSize()
    logger.info('block size %d %d' % (block[0],block[1]))

    write_band=ds2.GetRasterBand(1)
    write_band.SetColorInterpretation(band.GetColorInterpretation())
    write_band.SetColorTable(band.GetColorTable())
    #write_band.SetDefaultHistogram(band.GetDefaultHistogram())
    write_band.SetDefaultRAT(band.GetDefaultRAT())
    write_band.SetNoDataValue(band.GetNoDataValue())
    #write_band.SetRasterCategoryNames(band.GetRasterCategoryNames())
    write_band.SetRasterColorInterpretation(band.GetRasterColorInterpretation())
    write_band.SetRasterColorTable(band.GetRasterColorTable())
    #write_band=ds2.AddBand(gdal.GDT_Byte,['BLOCKSIZE=512','COMPRESSED=YES'])
    
    logger.info('incoming xsize: %d ysize: %d' % (band.XSize,band.YSize))
    logger.info('outgoing xsize: %d ysize: %d' % (x,y))

    maxwheat=0
    block_idx=0
    # Note that y and x are switched b/c that's how ReadAsArray works.
    main_buf=np.zeros((block[1],block[0]),dtype=np.uint8)

    for xidx in range(0,x,block[0]):
        for yidx in range(0,y,block[1]):
            ysize=min(block[1],y-yidx)
            xsize=min(block[0],x-xidx)
            if xsize is block[0] and ysize is block[1]:
                xform_buf=main_buf
            else:
                xform_buf=np.zeros((ysize,xsize),dtype=np.uint8)

            band.ReadAsArray(xidx,yidx,xsize,ysize,
                                 xsize,ysize,xform_buf)
            # Where the data value is a wheat value, put a 1, else a 0.
            xform_buf=np.where(
                np.in1d(xform_buf,wheatish).reshape((ysize,xsize)),xform_buf,0)
            # It is here that the buffer size determines how many entries
            # are written. There is no option to write a subarray.
            write_band.WriteArray(xform_buf,xidx,yidx)

            nonzero=len(xform_buf.nonzero()[0])
            if nonzero>maxwheat: maxwheat=nonzero

            if block_idx%1000 is 0:
                logger.debug('at (%d,%d) nonzero %d' % (xidx,yidx,
                                                           maxwheat))
                maxwheat=0
            block_idx+=1

    ds2.SetGeoTransform(ds.GetGeoTransform())
    ds2.SetProjection(ds.GetProjection())
    # Recommended way to close the file.
    ds2=None





def compare_all_and_wheat(filename1,filename2,inset=None):
    '''
    Pull wheat values out of crop dataland layer, but just pixel
    for pixel, not subsetting.
    '''
    ds1=gdal.Open(filename1,GA_ReadOnly)
    logger.debug('opened %s' % filename1)
    ds2=gdal.Open(filename2,GA_ReadOnly)
    logger.debug('opened %s' % filename2)

    band1=ds1.GetRasterBand(1)
    band2=ds2.GetRasterBand(1)
    
    logger.info('incoming xsize: %d ysize: %d' % (band1.XSize,band1.YSize))

    for yidx in range(0,band1.YSize):
        #logger.debug('reading band %d scanline len %d' % (yidx,len(scanline)))

        scanline=band1.ReadRaster(0,yidx,band1.XSize,1,
                                 band1.XSize,1,GDT_Byte)
        ar1=np.array(struct.unpack('B'*band1.XSize,scanline),
                    dtype=np.uint8)[0:band1.XSize]

        scanline=band2.ReadRaster(0,yidx,band1.XSize,1,
                                 band1.XSize,1,GDT_Byte)
        ar2=np.array(struct.unpack('B'*band1.XSize,scanline),
                    dtype=np.uint8)[0:band1.XSize]

        for idx in range(band1.XSize):
            if ar1[idx] in wheatish:
                if ar1[idx]!=ar2[idx]:
                    print('unequal at %d,%d' % (idx,yidx))
                    logger.warning('unequal at %d,%d' % (idx,yidx))
            else:
                if ar2[idx]!=0:
                    logger.warning('should be zero at %d,%d' % (idx,yidx))
                    print('should be zero at %d,%d' % (idx,yidx))
        print 'one line', yidx

    ds1=None
    ds2=None





def blocked_read(filename):
    '''
    Pull wheat values out of crop dataland layer, but just pixel
    for pixel, not subsetting.
    Work in blocks, specified as block=[x block, y block].
    '''
    ds=gdal.Open(filename,GA_ReadOnly)
    logger.debug('opened %s' % filename)

    band=ds.GetRasterBand(1)
    block=band.GetBlockSize()
    logger.info('block size %d %d' % (block[0],block[1]))

    logger.info('incoming xsize: %d ysize: %d' % (band.XSize,band.YSize))
    x=band.XSize
    y=band.YSize

    # Note that y and x are switched b/c that's how ReadAsArray works.
    main_buf=np.zeros((block[1],block[0]),dtype=np.uint8)

    for xidx in range(0,x,block[0]):
        for yidx in range(0,y,block[1]):
            ysize=min(block[1],y-yidx)
            xsize=min(block[0],x-xidx)
            if xsize is block[0] and ysize is block[1]:
                xform_buf=main_buf
            else:
                xform_buf=np.zeros((ysize,xsize),dtype=np.uint8)

            band.ReadAsArray(xidx,yidx,xsize,ysize,
                                 xsize,ysize,xform_buf)

    ds=None




def blocked_write(filename1,outfile,inset=None):
    '''
    Pull wheat values out of crop dataland layer, but just pixel
    for pixel, not subsetting.
    '''
    ds1=gdal.Open(filename1,GA_ReadOnly)
    logger.debug('opened %s' % filename1)
    ds2,x,y=create_copy(ds1,1,outfile,inset)
    logger.debug('created copy %s dim %d %d' % (str(ds2),x,y))
    ds1=None

    write_band=ds2.GetRasterBand(1)
    block=write_band.GetBlockSize()    
    logger.info('block size is %s' % str(block))
    logger.info('incoming xsize: %d ysize: %d' % \
                    (write_band.XSize,write_band.YSize))

    # Note that y and x are switched b/c that's how ReadAsArray works.
    main_buf=np.zeros((block[1],block[0]),dtype=np.uint8)

    for xidx in range(0,x,block[0]):
        for yidx in range(0,y,block[1]):
            ysize=min(block[1],y-yidx)
            xsize=min(block[0],x-xidx)
            if xsize is block[0] and ysize is block[1]:
                xform_buf=main_buf
            else:
                xform_buf=np.zeros((ysize,xsize),dtype=np.uint8)

            # It is here that the buffer size determines how many entries
            # are written. There is no option to write a subarray.
            write_band.WriteArray(xform_buf,xidx,yidx)

    # Recommended way to close the file.
    ds2=None





def pretty_print(resx=800*12,resy=600*12):
    reg=qgis.core.QgsMapLayerRegistry.instance()
    layers=reg.mapLayers()
    want=['just_wheat','Eco_Level','rust_points']
    show_layers=list()
    for l in layers.keys():
        for w in want:
            if l.startsWith(w):
                show_layers.append(l)

    img=PyQt4.QtGui.QImage(PyQt4.QtCore.QSize(resx,resy),PyQt4.QtGui.QImage.Format_ARGB32_Premultiplied)
    #color=PyQt4.QtGui.QColor(255,255,255)
    p=PyQt4.QtGui.QPainter()
    p.begin(img)
    p.setRenderHint(PyQt4.QtGui.QPainter.Antialiasing)
    render=qgis.core.QgsMapRenderer()
    render.setLayerSet(show_layers)
    
    r=qgis.core.QgsRectangle(render.fullExtent())
    r.scale(1.1)
    render.setExtent(r)
    render.setOutputSize(img.size(),img.logicalDpiX())
    render.render(p)
    p.end()
    img.save("render.png","png")



if __name__ == '__main__':
    parser=ArgumentParser(description='converts land use data')
    def add_function(name,msg):
        parser.add_argument('--%s'%name,dest=name,action='store_true',
                        default=False,help=msg)
    add_function('pick','Make a file with only wheat in it.')
    add_function('crop_check','Check NCDL metadata crop lists')
    add_function('wheat_codes','Check which codes are wheat')

    parser.add_argument('--inset',dest='inset',type=str,default=None,
                        help='x,y for a subset of the image. Try 20000,20000')

    parser.add_argument('--verbose','-v',dest='verbose',action='store_true',
                        default=False,help='print debug messages')
    parser.add_argument('--quiet','-q',dest='quiet',action='store_true',
                        default=False,help='print only exceptions')
    parser.add_argument('--cdls',dest='cdls',type=str,
                        help='the path to the 30m cdls file ending in .img')
    parser.add_argument('--outfile',dest='outfile',type=str,default='',
                        help='a path to an output file to create')


    args=parser.parse_args()
    log_level=logging.INFO
    if args.verbose:
        log_level=logging.DEBUG
    elif args.quiet:
        log_level=logging.ERROR
    logging.basicConfig(level=log_level)

    did_something=False
    try:
        if args.pick:
            did_something=True
            if not os.path.exists(args.cdls):
                print 'cdls', args.cdls
                logger.exception('Could not find the file %s. Set it with --cdls filename'
                                  % args.cdls)

            if not args.outfile:
                print 'out', args.outfile
                logger.exception('Please specify an output file with --outfile')
            inset=None
            if args.inset:
                inset=[int(x) for x in args.inset.split(',')]
                logger.info('using an inset of (%d,%d)' % tuple(inset))
            wheat_from_cdl_blocked(args.cdls,args.outfile,inset)

        if args.crop_check:
            did_something=True
            cdls_dir=os.path.split(luconfig.get('cdls'))
            metafiles=glob.glob(os.path.join(cdls_dir,'cdlmeta*.xml'))
            print 'mf', len(metafiles)
            cover=findp.are_cereal_codes_same(metafiles)
            for number,name in cover.items():
                print('%d: %s' % (number,name))

        if args.wheat_codes:
            did_something=True
            print(wheat_codes())

    except Exception,e:
        traceback.print_exc()

    if not did_something:
        parser.print_help()
