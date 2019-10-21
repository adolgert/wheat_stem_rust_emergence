import math
import datetime
import csv
import numpy as np
import matplotlib.patches as mpatches
import matplotlib.collections
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.colors import colorConverter
import logging
import ols
import county
import state
import aylor_corn
import luconfig
from default_parser import DefaultArgumentParser
import nass_emergence


logger=logging.getLogger('plot_obs')


def northward():
    f=luconfig.get('cereal_rust')
    # This gets an array of [date,[lat,long]]
    vals=county.observations_by_location(f)
    default_year=datetime.date.today().year
    dates=list()
    lats=list()
    for r in vals:
        d=r[0]
        dates.append(datetime.date(default_year,d.month,d.day))
        lats.append(r[1][0])

    days=np.zeros(len(dates))
    for idx,ad in enumerate(dates):
        days[idx]=(ad-datetime.date(ad.year,1,1)).days
    lats=np.array(lats)
    model=ols.ols(days,lats,'day',['lat'])
    print model.summary()
    # model.b[0] is intercept, model.b[1] is slope
    # model.se is standard error on these.
    def fit(l):
        res=[0]*len(l)
        for lidx,ll in enumerate(l):
            d=int(model.b[0]+ll*model.b[1])
            res[lidx]=(datetime.date(year=ad.year,month=1,day=1)+
                       datetime.timedelta(days=d))
        return res

    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.plot(lats,dates, 'bo', ms=2, alpha=0.3)
    ax.plot(lats,fit(lats),'-', color='orange')
    ax.set_title('Rate of Northward Progress')
    ax.set_ylabel('Date of observation')
    ax.set_xlabel('Latitude of observation')
    fig.autofmt_xdate()

    plt.show()
    return model


def by_year():
    f=luconfig.get('cereal_rust')
    # This gets an array of [date,[lat,long]]
    vals=county.observations_by_location(f)
    default_year=datetime.date.today().year
    dates=list()
    years=list()
    last_year=None
    all_dates=list()
    dates=None
    all_lats=list()
    lats=None
    for r in vals:
        d=r[0]
        if d.year!=last_year:
            if lats:
                all_lats.append(lats)
                all_dates.append(dates)
            lats=list()
            dates=list()
            years.append(d.year)
            last_year=d.year
        dates.append(datetime.date(d.year,d.month,d.day))
        lats.append(r[1][0])
    all_lats.append(lats)
    all_dates.append(dates)

    colors=('b', 'g', 'r', 'c', 'm', 'y', 'k')*5

    fig = plt.figure(figsize=(5,5))
    color_idx=0
    logger.debug('len years %d, len lats %d, len dates %d' % \
                     (len(years),len(all_lats),len(all_dates)))
    for (year,lats,dates) in zip(years,all_lats,all_dates):
        logger.debug('color_idx %d'%color_idx)
        early=datetime.date(year,3,1)
        late =datetime.date(year,9,1)
        ax = plt.subplot(4,4,color_idx+1)
        plt.plot(dates,lats, 'o',color=colors[color_idx])
        ax.set_title(str(year))
        ax.axis([early,late,25,50])
        color_idx+=1

    fig.autofmt_xdate()

    plt.show()



def show_sos(year):
    '''
    SOS is the start of growing season. It's roughly 10% of total
    greening level. We read it from CSV written by R.
    '''
    year=int(year)

    lat_longs=county.get_lat_long_by_county()

    green_start=dict()
    for line in csv.reader(open("sos%d.csv" % year)):
        idx, geoid, day_of_year = line
        if idx:
            green_start[int(geoid)]=int(math.floor(float(day_of_year)))
    
    first_passage=county.get_first_passage()
    this_passage=first_passage[year]

    build_data=list()
    for day in sorted(this_passage):
        counties=this_passage[day]
        for geoid in counties:
            lat=lat_longs[geoid][0]
            sos=green_start[geoid]
            build_data.append([geoid,day,sos,lat])

    logger.debug('build_data len %d %s %s' % (len(build_data),
                                           str(type(build_data)),
                                           str(type(build_data[0]))))
    logger.debug('build_data %s' % str(build_data))
    data=np.array(build_data)
    geoid=np.array(data[:,0].astype(np.uint))
    day=np.array(data[:,1].astype(np.int))
    sos=np.array(data[:,2].astype(np.int))
    lat=np.array(data[:,3])
    
    intercept, slope=aylor_corn.fit_corn().b
    corn_of_lat=intercept+lat*slope

    fig = plt.figure()
    ax = fig.add_subplot(111)
    #ax.plot(lat,day-(sos-365), 'o')
    ax.plot(lat,day, 'x', lat,corn_of_lat, '.', lat,sos, '+',
            lat,day-sos,'o')
    leg=ax.legend(('obs day', 'corn planting', 'SOS','obs adj SOS'),'upper left')
    ax.set_title('Adjusted for SOS')
    ax.set_xlabel('Latitude of observation')
    ax.set_ylabel('Day of observation')
    #fig.autofmt_xdate()
    leg.get_frame().set_facecolor('0.80')

    plt.show()



def wheat_patches(year):
    state_info=state.state_basics()
    rates=nass_emergence.match_rates(year)
    patches=list()
    for fips, (mid,spread) in rates.iteritems():
        width=state_info[fips]['bounds'][3]-state_info[fips]['bounds'][2]
        height=4.2*spread
        logger.debug('lat %g mid %g' % (float(state_info[fips]['INTPTLAT10']),mid))
        center=np.array([float(state_info[fips]['INTPTLAT10']),mid])
        r=mpatches.Rectangle(center, width=width, height=height,
                             facecolor='green')
        patches.append(r)
    patch_col=matplotlib.collections.PatchCollection(patches,color='green',
                                                     alpha=0.1)
    return patch_col



def several_together(year):
    '''
    SOS is the start of growing season. It's roughly 10% of total
    greening level. We read it from CSV written by R.
    '''
    year=int(year)

    lat_longs=county.get_lat_long_by_county()

    
    first_passage=county.get_first_passage()
    this_passage=first_passage[year]

    build_data=list()
    for day in sorted(this_passage):
        counties=this_passage[day]
        for geoid in counties:
            lat=lat_longs[geoid][0]
            build_data.append([geoid,day,lat])

    logger.debug('build_data len %d %s %s' % (len(build_data),
                                           str(type(build_data)),
                                           str(type(build_data[0]))))
    logger.debug('build_data %s' % str(build_data))
    data=np.array(build_data)
    geoid=np.array(data[:,0].astype(np.uint))
    day=np.array(data[:,1].astype(np.int))
    lat=np.array(data[:,2])

    # corn itself
    corn_rows=aylor_corn.corn_graph()
    corn_model=aylor_corn.fit_to_corn(corn_rows)

    corny=np.array(list([x[1] for x in corn_rows]))
    cornx=np.array(list([x[3] for x in corn_rows]))

    # corn fit
    fit_lat=np.arange(min(lat), max(lat),(max(lat)-min(lat))/50)
    intercept, slope=aylor_corn.fit_corn().b
    corn_of_lat=intercept+fit_lat*slope
    logger.debug('fit_lat %s' % str(fit_lat))
    logger.debug('corn of lat %s ' % str(corn_of_lat))

    fig = plt.figure()
    ax = fig.add_subplot(111)
    #ax.plot(lat,day-(sos-365), 'o')
    ax.plot(lat,day, 'ro', fit_lat,corn_of_lat, 'b-', cornx, corny, 'bx')
    leg=ax.legend(('obs day', 'corn fit', 'corn planting'),'upper left')
    ax.add_collection(wheat_patches(year))
    ax.set_title('Wheat Rust Compared with Emergence and Corn Planting %d' %
                 year)
    ax.set_xlabel('Latitude of observation')
    ax.set_ylabel('Day of observation')
    #fig.autofmt_xdate()
    leg.get_frame().set_facecolor('0.80')

    plt.show()



 
def plot_corn_obs():
    corn_rows=aylor_corn.corn_graph()
    corn_model=aylor_corn.fit_to_corn(corn_rows)

    corny=np.array(list([x[1] for x in corn_rows]))
    cornx=np.array(list([x[3] for x in corn_rows]))

    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.plot(cornx, corny, 'x')
    #leg=ax.legend(('obs day', 'corn planting', 'SOS','obs adj SOS'),'upper left')
    #leg.get_frame().set_facecolor('0.80')
    ax.set_title('Ground Truth')
    ax.set_xlabel('Latitude of observation')
    ax.set_ylabel('Day of observation')
    #fig.autofmt_xdate()

    plt.show()



if __name__ == '__main__':
    parser=DefaultArgumentParser(description='plots cereal rust')
    parser.add_function('together','print all observations together')
    parser.add_function('multiples','print years separately in small multiples')
    parser.add_function('several','corn, first_passage, wheat ground truth')
    parser.add_function('sos','Show the start of season graph.')
    parser.add_function('ground','show a ground truth graph of corn and emergence')

    parser.add_argument('--year',metavar='year',type=int,
                        help='The year of interest')

    args=parser.parse_args()

    if args.multiples:
        by_year()

    if args.together:
        northward()

    if args.several:
        several_together(args.year)

    if args.sos:
        if not args.year:
            logger.error('Need to know which year for sos, so use --year.')
        show_sos(args.year)

    if args.ground:
        plot_corn_obs()

    if not parser.any_function():
        parser.print_help()
