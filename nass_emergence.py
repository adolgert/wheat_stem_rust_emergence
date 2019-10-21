'''
NASS provides some statistics on crops. This file retrieves those.
'''
import csv
import logging
import re
import datetime
import numpy as np
import scipy.stats as ss
import scipy as sp
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.colors import colorConverter

import luconfig
import state
import emerge_fitter
from default_parser import DefaultArgumentParser
from memoize import memoized

logger=logging.getLogger('nass_emergence')


def get_spring():
    '''
    This NASS data shows wheat emergence for ID, MN, MO, SD, WA
    and a national number. We pull these numbers by week with
    the lat-long of the states for ease of use.
    '''
    reader=csv.reader(open(luconfig.get('spring_wheat'), "rU"))
    headers=reader.next()
    year_idx=headers.index('Year')
    fips_idx=headers.index('State Fips')
    percent_idx=headers.index('Value')
    week_idx=headers.index('Period')

    week_pat=re.compile('\#([0-9]+)')
    vals=list()
    for line in reader:
        if line and line[0] == 'SURVEY':
            fips=int(line[fips_idx])
            if fips is not 99:
                record=dict()
                record['year']=int(line[year_idx])
                record['day']=int(week_pat.search(line[week_idx]).group(1))*7
                record['fips']=fips
                record['percent']=int(line[percent_idx])
                vals.append(record)

    return vals



@memoized
def get_spring_year_state():
    spring=get_spring()
    by_year=dict()
    for obs in spring:
        if obs['year'] not in by_year:
            by_year[obs['year']]=dict()
        if obs['fips'] not in by_year[obs['year']]:
            by_year[obs['year']][obs['fips']]=[list(),list()]
        state_obs=by_year[obs['year']][obs['fips']]
        state_obs[0].append(obs['percent'])
        state_obs[1].append(obs['day'])

    for yr in by_year:
        for st in by_year[yr]:
            x=np.array(by_year[yr][st][0])
            y=np.array(by_year[yr][st][1])
            by_year[yr][st][0]=x
            by_year[yr][st][1]=y
    return by_year



def match_rates(year):
    '''
    Returns: dictionary from state fips to (midpoint, spread)
             of logistic match to wheat emergence curve.
    '''
    by_state=get_spring_year_state()[year]
    fitter=emerge_fitter.emerge_fitter()
    
    data=dict()
    for st, (pct,days) in by_state.iteritems():
        mid,spread=fitter(days,pct)
        data[st]=(mid,spread)
        print "fips", st
        print "   ", pct
        print "   ", mid, mid-2*spread, mid+2*spread
    return data


def plot_spring(year):
    by_state = get_spring_year_state()[year]
    state_info=state.state_basics()

    fig = plt.figure()
    ax = fig.add_subplot(111)
    names=list()
    for st in by_state:
        names.append(state_info[st]['STUSPS10'])
        print names[-1]
        print "   c(%s)" % ", ".join([str(x) for x in by_state[st][1]])
        print "   c(%s)" % ", ".join([str(x) for x in by_state[st][0]])
        ax.plot(by_state[st][1],by_state[st][0],'o-')
    
    leg=ax.legend(tuple(names),'upper left')
    leg.get_frame().set_facecolor('0.80')
    ax.set_title('Ground Truth Wheat Emergence %d' % year)
    ax.set_ylabel('Percent emergence')
    ax.set_xlabel('Day of year for observation')
    plt.show()




def test_spring():
    vals=get_spring()
    print len(vals)
    print vals[0]


if __name__ == '__main__':
    parser=DefaultArgumentParser(description='plots cereal rust')
    parser.add_function('test','see if it works')
    parser.add_function('fitlog','try a logistic fit to emergence')
    parser.add_function('pem','plot emergence for a year')
    parser.add_argument('--year',metavar='year',type=int,
                        help='the year of interest')

    args=parser.parse_args()

    if args.test:
        test_spring()

    if args.pem:
        plot_spring(args.year)

    if args.fitlog:
        match_rates(args.year)

    if not parser.any_function():
        parser.print_help()
