'''
Figure out Aylor's corn planting plot.
'''
import os
import sys
import numpy as np
import logging
import datetime
import fileinput
import cPickle
import glob
import shapefile
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.colors import colorConverter


import state
import corn_planting
import default_parser
import luconfig
import county
import gimms



# possible plants to track for phenology
'''
Panicum virgatum,switchgrass
Pascopyrum smithii,western wheatgrass
Pennisetum ciliare,buffelgrass
Pseudoroegneria spicata,bluebunch wheatgrass
Sisyrinchium bellum,western blue-eyed grass
'''

logger=logging.getLogger('aylor_corn')


def corn_graph():
    fips_dates=corn_planting.typical_corn()
    state_centers=state.state_center_data()
    
    rows=list()
    for fips in fips_dates.keys():
        rows.append([fips,fips_dates[fips]['plant_active_begin'],
                    state_centers[fips]['lon'],state_centers[fips]['lat']])

    return rows



def get_green():
    '''
    Combine first passage of cereal rust by county with
    the greening of that county to get the greening at the
    time of cereal rust first passage.
    '''    
    obs=county.observations_by_location(luconfig.get('cereal_rust'))
    first_passage = county.first_passage_by_year(obs)

    WHEAT=np.array([int(x) for x in luconfig.get('wheat_codes').split(',')],
                   dtype=np.uint8)
    gimms_dir=os.path.join(luconfig.get('gimms'),'counties')
    logger.info('Reading gimms in %s' % gimms_dir)
    #county_codes=gimms.build(fileinput.input(glob.glob(
    #            os.path.join(gimms_dir,'*.txt'))), WHEAT)

    county_codes=cPickle.load(open(os.path.join(gimms_dir,'grid.pickle')))

    county_filename=luconfig.get('county')
    sh=shapefile.Reader(county_filename)
    shape_records=sh.records()
    lat_longs=county.lat_long_by_county(shape_records)

    results=dict()
    for yr in sorted(first_passage):
        results[yr]=list()
        for day in sorted(first_passage[yr]):
            geoids=first_passage[yr][day]
            obs_date=datetime.date(yr,1,1)+datetime.timedelta(day)
            for geoid in geoids:
                if geoid in county_codes:
                    x,y,weights=county_codes[geoid]
                    ndvi=gimms.get_greens(obs_date, x, y)
                    pos=np.where(ndvi>0)
                    ndvi_eff=np.dot(ndvi[pos],weights[pos])
                    longlat=lat_longs[geoid]
                    results[yr].append([yr,day,longlat[0],longlat[1],
                                        geoid,ndvi_eff])
                else:
                    logger.error('Can\'t find %d' % geoid)

    return results



def green_of_important_pixels(year):
    '''
    This finds the greening for a whole year for the pixel
    with the most wheat in each county that has an observation.
    '''
    gimms_dir=os.path.join(luconfig.get('gimms'),'counties')
    county_codes=cPickle.load(open(os.path.join(gimms_dir,'grid.pickle')))
    logger.debug('read county codes')

    (counties, pixel, line)=gimms.pixel_with_max_wheat(county_codes)
    logger.debug('read pixels with max wheat')
    days, data = gimms.year_trace(year, pixel, line)

    pl_to_xy=gimms.gimms_to_xy()
    lon_arr=np.zeros(len(pixel),dtype=np.float)
    lat_arr=np.zeros(len(pixel),dtype=np.float)
    for i in range(len(pixel)):
        lon, lat, z = pl_to_xy(pixel[i], line[i])
        lon_arr[i]=lon
        lat_arr[i]=lat

    logger.debug('traced data through the year')
    return (counties, lon_arr, lat_arr, data, days)



def write_pixels_for_R(year):
    gm=green_of_important_pixels(year-1)
    gn=green_of_important_pixels(year)
    gp=green_of_important_pixels(year+1)

    res=np.hstack((gm[3],gn[3],gp[3]))
    import csv
    spam = csv.writer(open('pix_for_R_%d.csv' % year,'wb'),
                      quoting=csv.QUOTE_MINIMAL)
    for idx in range(len(gn[0])):
        spam.writerow([gn[0][idx], gn[1][idx], gn[2][idx]] + list(res[idx,:]))
        
    return (gn[0], res)



def plot_year_green(geoid, vals, days, lat, which=0):
    '''
    plot results from green_of_important_pixels. vals is a 2d array.
    Show greening, with county and state in title, and
    a vertical bar where corn predicts greening.
    '''

    assert(len(days)==vals.shape[1])

    const, mlat=fit_corn().b
    import county as county_data
    cb=county_data.county_basics()
    import state as state_data
    sb=state_data.state_basics()

    fig = plt.figure(figsize=(5,5))
    fig.text(0.5, 0.95,
             'Greening Trends at Pixel with Most Wheat in County',
             ha='center', fontsize=16)
    for idx in range(which,which+16):
        ax = fig.add_subplot(4,4,idx+1-which)
        ax.plot(days, vals[idx,:], 'o')
        plt.axvline(x=(mlat*lat[idx]+const))
        county_info=cb[geoid[idx]]
        name=county_info['NAME10']
        state=sb[int(county_info['STATEFP10'])]['STUSPS10']
        ax.set_title('%s, %s' % (name,state))
        #ax.set_xlabel('Date of observation')
        #ax.set_ylabel('Greenness')
        ax.axis([1,365,0,9000])
        #fig.autofmt_xdate()

    plt.show()



def print_corn():
    print '\t'.join(['fips','day','lon','lat'])
    for r in corn_graph():
        print '\t'.join([str(x) for x in r])


def fit_to_corn(corn_rows):
    import ols
    y=np.array(list([x[1] for x in corn_rows]))
    x=np.array(list([x[3] for x in corn_rows]))
    model=ols.ols(y,x,'date',['lat'])
    return model


def fit_corn():
    rows=corn_graph()
    return fit_to_corn(rows)


def test_important():
    logger.debug(green_of_important_pixels(2000)[3].shape)

def test_plot_green():
    geoid, pixel, line, data, days=green_of_important_pixels(2000)
    plot_year_green(geoid, data, days, 0)
     

if __name__ == '__main__':
    parser = default_parser.DefaultArgumentParser(
        description='calculate values for aylor corn hypothesis')
    parser.add_function('test','run tests')
    parser.add_function('fitcorn','fit the corn graph')
    parser.add_function('getgreen','get first passage greening')
    parser.add_function('allgreen','get a whole year of greening at'
                        ' places that have lots of wheat in each county')
    parser.add_function('plotgreen','plot greening at'
                        ' places that have lots of wheat in each county')
    parser.add_function('writer','write pixels in csv for R')
    parser.add_argument('--year',dest='year',type=int,
                        help='what year to get all the greening')
    parser.add_argument('--offset',dest='offset',type=int,
                        help='start index of counties to plot for plotgreen')
    #parser.add_argument('filenames',metavar='filenames',type=str,
    #                    nargs='*', desc='command line args')
    args=parser.parse_args()
    
    if args.test:
        test_important()
        test_plot_green()
        sys.exit(0)


    if args.fitcorn:
        model=fit_corn()
        print model.summary()

    if args.getgreen:
        observations_by_year=get_green()
        for yr in observations_by_year:
            for obs in observations_by_year[yr]:
                print '\t'.join([str(x) for x in obs])

    
    if args.allgreen:
        geoid, lon, lat, data, days=green_of_important_pixels(args.year)
        f=open('testgreen_%d.txt' % args.year,'w')
        cPickle.dump(geoid,f)
        cPickle.dump(data,f)
        

    if args.plotgreen:
        geoid, lon, lat, data, days=green_of_important_pixels(args.year)
        # This step sorts by latitude so we can use the offset
        # to pick out traces of similar latitude.
        order=np.argsort(lat)[args.offset:args.offset+16]
        plot_year_green(geoid[order], data[order,:], days, lat[order], 0)


    if args.writer:
        if not args.year:
            logger.error('This needs a year')
        write_pixels_for_R(args.year)
