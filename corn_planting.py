import sys
import os
import re
import csv
import logging
import collections
import datetime
import numpy as np
import state_fips
import emerge_fitter
import state as state_dat
import luconfig
from memoize import memoized
from default_parser import DefaultArgumentParser

logger=logging.getLogger("corn_planting")


def typical_corn():
    '''
    Returns a dictionary with state fips as keys and these harvest dates
    as values, where each date is represented by days since January.
    '''
    filename=luconfig.get('typical_corn')
    name_to_fips=state_fips.name_to_fips()
    
    state_match=re.compile('^([\w ]+) \.')
    date_match=re.compile('(\w\w\w)\s+([\d]+)')
    day1=datetime.datetime.strptime('Jan 1','%b %d')
    
    state_dates=dict()
    date_cols=['plant_begin','plant_active_begin','plant_active_end',
        'plant_end','harvest_begin','harvest_active_begin',
        'harvest_active_end','harvest_end']

    for line in open(filename,'r'):
        if not '.:' in line: continue
        state=state_match.search(line).group(1)
        dates=[' '.join(x) for x in date_match.findall(line)]
        dates=[(datetime.datetime.strptime(x,'%b %d')-day1).days+1 for x in dates]
        fips=name_to_fips[state.upper()]
        state_dates[fips] = dict(zip(date_cols,dates))
        
    return state_dates



@memoized
def planted_yearly_records():
    reader=csv.reader(open(luconfig.get('corn_planted'), "rU"))
    headers=reader.next()
    logger.debug('corn planed header: %s' % ', '.join(headers))
    program_idx=headers.index('Progam') # Yes, it is misspelled.
    year_idx=headers.index('Year')
    fips_idx=headers.index('State Fips')
    percent_idx=headers.index('Value')
    week_idx=headers.index('Period')

    week_pat=re.compile('\#([0-9]+)')

    vals=list()
    for line in reader:
        if line[program_idx]=="SURVEY":
            fips=int(line[fips_idx])
            if fips is not 99:
                record=dict()
                record['year']=int(line[year_idx])
                record['day']=int(week_pat.search(line[week_idx]).group(1))*7
                record['fips']=fips
                record['percent']=int(line[percent_idx])
                vals.append(record)

    return vals



def planted_year(year):
    '''
    Given all of the records from the csv, return one year's data
    formatted so that there is a numpy array of the days of observations
    and a dictionary of arrays of observations for each state.
    '''
    recs=planted_yearly_records()
    state_dat=collections.defaultdict(list)
    state_days=collections.defaultdict(list)
    for r in recs:
        if r['year']==year:
            state_days[r['fips']].append(r['day'])
            state_dat[r['fips']].append(r['percent'])
    
    state_arr=dict()
    for state, vals in state_dat.iteritems():
        state_arr[state]=(np.array(vals), np.array(state_days[state]))

    return state_arr



def yearly_fit(year):
    '''
    This writes in a format suitable for R.
    '''
    state_info=state_dat.state_basics()
    by_state=planted_year(year)
    fitter=emerge_fitter.emerge_fitter()

    print 'year, fips, lat, long, minx, maxx, miny, maxy, mid, spread'
    for state, (percent, days) in by_state.iteritems():
        if len(days)>2:
          mid, spread = fitter(days, percent)
          lat=state_info[state]['INTPTLAT10']
          lon=state_info[state]['INTPTLON10']
          b=state_info[state]['bounds']
          print '%d, %d, %s, %s, %g, %g, %g, %g, %g, %g' % (year, state, lat,
                                                           lon, b[0],
                                                           b[1], b[2], b[3],
                                                           mid, spread)
        else:
            print 'why is this so short?', state, percent



def test():
    c=typical_corn()
    assert(c)


if __name__ == '__main__':
    parser=DefaultArgumentParser(description='corn planting data')
    parser.add_function('fityear','fit one year to logistic functions')
    parser.add_function('test','run tests')
    parser.add_argument('--year',metavar='year',type=int,
                        help='the year to fit')
    args=parser.parse_args()

    if args.test: test()

    if args.fityear:
        yearly_fit(args.year)

    if not parser.any_function():
        parser.print_help()
