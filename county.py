import sys
import os
import itertools
import csv
import datetime
import json
import difflib
import shapefile
import state_fips as statefips
import logging
from memoize import memoized
import luconfig
from default_parser import DefaultArgumentParser


logger=logging.getLogger('county')


def hamming_distance(str0,str1):
    diffs=0
    for ch0,ch1 in zip(str0,str1):
        if ch0!=ch1:
            diffs+=1
    return diffs


def shift_comp(str0,str1):
    spaceless=[str0.replace(' ',''),str1.replace(' ','')]
        



def find_county_in_state(county_name, state, possibles,all_matches):
    for (code,names) in possibles:
        if county_name==names[0] or county_name==names[1]:
            return code
    logger.warn('Did not find',county_name, state, difflib.get_close_matches(county_name,all_matches))
    return 0


def find_counties(names,shapefile_records):
    state_to_code=statefips.state_fips()
    counties_in_state=counties_by_state(shapefile_records)
    all_matches=dict()
    for state,records in counties_in_state.items():
        all_names=[x[1] for x in records]
        flattened=itertools.chain.from_iterable(all_names)
        together=list()
        for f in flattened:
                together.append(f)
        all_matches[state]=together
        logger.debug('state %d %d' % (state,len(together)))

    codes=list()
    for (state,county) in names:
        state_fips=None
        possibles=None
        code=0
        try:
            state_fips=state_to_code[state]
        except KeyError, e:
            logger.warn('Could not find state', state,'for county',county)
        if state_fips:
            try:
                possibles=counties_in_state[state_fips]
            except KeyError, e:
                logger.warn('Missing state_fips',state,'fips',state_fips)
        if possibles:
            code=find_county_in_state(county,state,possibles,
                                      all_matches[state_fips])
        codes.append(code)

    assert(len(names)==len(codes))
    return codes


def ccounty(county):
    return county.replace('.','').strip().upper()


def counties_by_state(shapefile_records):
    by_state=dict()
    for r in shapefile_records:
        state_code=int(r[0])
        county_code=int(r[3])
        county_names=[ccounty(r[4]),ccounty(r[5])]
        if not by_state.has_key(state_code):
            by_state[state_code]=list()
        by_state[state_code].append([county_code,county_names])
    return by_state


@memoized
def county_basics():
    '''
    Fields are:
    ['DeletionFlag', 'STATEFP10', 'COUNTYFP10', 'COUNTYNS10', 'GEOID10',
    'NAME10', 'NAMELSAD10', 'LSAD10', 'CLASSFP10', 'MTFCC10', 'CSAFP10',
    'CBSAFP10', 'METDIVFP10', 'FUNCSTAT10', 'ALAND10', 'AWATER10',
    'INTPTLAT10', 'INTPTLON10'] and 'bounds'
    '''
    counties=dict()
    reader=shapefile.Reader(luconfig.get('county'))
    fields=[x[0] for x in reader.fields]
    fields.remove('DeletionFlag')

    for idx in range(reader.numRecords):
        record=dict(zip(fields,reader.record(idx)))
        record['bounds']=reader.shape(idx).bbox
        counties[int(record['GEOID10'])]=record
    return counties


def county_coords(filename):
    out=open(filename,'w')

    cols=['GEOID10', 'INTPTLAT10', 'INTPTLON10']
    out.write('%s%s' % (' '.join(cols),os.linesep))
    basics=county_basics()
    for id, c in basics.iteritems():
        dat=[c[x] for x in cols]
        out.write('%s %s %s%s' % tuple(dat+[os.linesep]))
    out.close()


def observation_counties(datafile,shape_records):
    logger.debug('reading datafile %s' % datafile)
    incidence=csv.reader(open(datafile,'rU'))
    observation_locations=list()
    for spot in incidence:
        if spot[0].isdigit():
            (state,county)=(ccounty(spot[4]),ccounty(spot[5]))
            observation_locations.append([state,county])

    codes=find_counties(observation_locations,shape_records)
    return codes



def get_date(obs_year,obs_date):
    if obs_date.isdigit():
        d=None
        d=datetime.date(obs_year,int(obs_date[:-2]),
        int(obs_date[-2:]))
        return d
    else:
        spl=obs_date.split('/')
        return datetime.date(obs_year,int(spl[0]),int(spl[1]))



def lat_long_by_county(shape_record):
    lat_long=dict()
    for r in shape_record:
        lat_long[int(r[3])]=(float(r[-2]),float(r[-1]))
    return lat_long


def get_lat_long_by_county():
    sh=shapefile.Reader(luconfig.get('county'))
    shape_records=sh.records()
    lat_longs=lat_long_by_county(shape_records)
    return lat_longs


def observations_by_location(obs_file):
    sh=shapefile.Reader(luconfig.get('county'))
    shape_records=sh.records()
    logger.debug('There are %d records in shapefile.' % len(shape_records))
    county_code=observation_counties(obs_file,shape_records)
    lat_longs=lat_long_by_county(shape_records)
    idx=0

    obs_by_location=list()
    for line in csv.reader(open(obs_file,'rU')):
        if line[0].isdigit():
            if county_code[idx] is not 0:
                try:
                    obs_year=int(line[0].strip())
                    obs_date=get_date(obs_year,line[3].strip())
                except ValueError, e:
                    logger.warn("%s %s" % (line,str(e)))
                try:
                    loc=lat_longs[county_code[idx]]
                except KeyError, e:
                    logger.warn("%s %s" % (line,e))
                obs_by_location.append([obs_date,loc,county_code[idx]])
            idx+=1
    return obs_by_location



def write_obs_points(obs):
    '''
    Write the county observations to a file as a shapefile.
    '''
    w=shapefile.Writer(shapefile.POINT)
    w.field('DATE')
    w.field('COUNTY_FIPS')
    for x in obs:
        # It's longlat, not latlong.
        w.point(x[1][1],x[1][0])
        w.record(x[0].isoformat())
        w.record(x[2])
    w.save('cereal_obs_points')



def first_passage(obs):
    '''
    For each year, list first record in each county, giving date and fips.
    '''
    seen_by_year=dict() # year -> set of what has been recorded already
    date_by_year=dict() # year -> dictionary of counties observed by day in year

    for (obs_date, obs_loc, obs_fips) in obs:
        if not seen_by_year.has_key(obs_date.year):
            seen_by_year[obs_date.year]=set()
            date_by_year[obs_date.year]=list()
                
        if obs_fips not in seen_by_year[obs_date.year]:
            day_idx=(obs_date-datetime.date(obs_date.year,1,1)).days
            if not date_by_year[obs_date.year].has_key(day_idx):
                date_by_year[obs_date.year][day_idx]=list()
            date_by_year[obs_date.year].append([obs_date,obs_fips])
            seen_by_year[obs_date.year].add(obs_fips)

    # This is returning a dictionary of years with lists of observations.
    return date_by_year




def first_passage_by_year(obs):
    '''
    For each year, list county_fips by the date of first occurrence.
    '''
    seen_by_year=dict() # year -> set of what has been recorded already
    date_by_year=dict() # year -> dictionary of counties observed by day in year

    for (obs_date, obs_loc, obs_fips) in obs:
        if not seen_by_year.has_key(obs_date.year):
            seen_by_year[obs_date.year]=set()
            date_by_year[obs_date.year]=dict()
                
        if obs_fips not in seen_by_year[obs_date.year]:
            day_idx=(obs_date-datetime.date(obs_date.year,1,1)).days
            if not date_by_year[obs_date.year].has_key(day_idx):
                date_by_year[obs_date.year][day_idx]=list()
            date_by_year[obs_date.year][day_idx].append(obs_fips)
            seen_by_year[obs_date.year].add(obs_fips)
    return date_by_year


def get_first_passage():
    obs_file=luconfig.get('cereal_rust')
    obs=observations_by_location(obs_file)

    # This writes the shapefile.
    #write_obs_points(obs)

    first_passage=first_passage_by_year(obs)
    return first_passage


def first_passage_to_R(filename):
    fp=get_first_passage()
    lat_longs=get_lat_long_by_county()
    
    f=open(filename,'w')
    f.write('lat long year day geoid%s' % os.linesep)
    for yr in fp:
        for day in fp[yr]:
            for geoid in fp[yr][day]:
                ll=lat_longs[geoid]
                f.write('%g %g %d %d %d%s' % (ll[0],ll[1],yr,day,geoid,os.linesep))
    f.close()


def show_first_passage(fp):
    '''Make a json list showing what days rust happens in what counties
    on what years.
    '''
    for yr in sorted(fp.keys()):
        for day in sorted(fp[yr].keys()):
            print ('%d: %s' % (day, str(fp[yr][day])))
            #print('%d: %s' % (day, ','.join(str(fp[yr][day]))))

    for yr in sorted(fp.keys()):
        day_min=min(fp[yr].keys())
        day_max=max(fp[yr].keys())
        print('%d: (%d, %d))' % (yr,day_min,day_max))


def counties_with_observations(fp):
    '''Print counties that have observations of rust.
    '''
    counties=set()
    for yr in fp:
        for day in fp[yr]:
            for x in fp[yr][day]:
                counties.add(x)

    counties=list(counties)
    counties.sort()
    #print os.linesep.join([str(x) for x in counties])
    print counties
    print 'total ',len(counties)



if __name__ == '__main__':
    parser=DefaultArgumentParser(description="county data")
    parser.add_function('fields','show fields in the county dataset')
    parser.add_function('showfirst','show first passage data')
    parser.add_function('showcounties','show counties with measurements')
    parser.add_function('firstr','write first passage data for R')
    parser.add_argument('--out',metavar='out',type=str,
                        help='create a file with this path')
    args=parser.parse_args()

    if args.fields:
        sh=shapefile.Reader(luconfig.get('county'))
        logger.info(sh.fields)
        state_code = 'STATEFP10'
        county_federal_processing_code = 'COUNTYFP10'
        county_ansi_code = 'COUNTYNS10'
        # County identifier; a concatenation of 2010 Census state FIPS
        #         code and county FIPS code
        county_id = 'GEOID10'
        county_name = 'NAME10'
        county_type = 'LSAD10' # city, borough, county, district, ... as a code.

    if args.showfirst:
        obs_file=luconfig.get('cereal_rust')
        obs=observations_by_location(obs_file)

        # This writes the shapefile.
        #write_obs_points(obs)

        first_passage=first_passage_by_year(obs)
        show_first_passage(first_passage)
        
    if args.showcounties:
        #json.dump(first_passage,open('first_passage.json','w'))
        print '---------'
        counties_with_observations(first_passage)

    if args.firstr:
        if not args.out:
            print 'give a filename to write with --out'
            sys.exit(1)
        first_passage_to_R(args.out)

    if not parser.any_function():
        parser.print_help()
        
