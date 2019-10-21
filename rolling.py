'''
This version of reading the cereal rust data uses generating functions.

This version turns each record into a dictionary. Each stage of
processing adds entries to the dictionary with processed data, so
it keeps the original data. If there is an error, that is added
as well.

Keys for the csv data at: http://www.ars.usda.gov/Main/docs.htm?docid=11025
'''
import sys
import os
import itertools
import csv
import datetime
import difflib
import shapefile
import traceback
import collections
import logging
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import county
import county as county_shp
import state
import state_fips as statefips
import luconfig
from default_parser import DefaultArgumentParser


logger=logging.getLogger('rolling')


rust_fields=['year','collection','isolate','date','state','county',
             'host_code','crop_stage','cultivar','severity','prevalence',
             'source','ecoarea']

def to_fields(lines):
    line_idx=0
    for line in lines:
        fields=dict()
        for i in range(len(rust_fields)):
            fields[rust_fields[i]]=line[i]
        fields['line']=line_idx
        yield fields
        line_idx+=1


def fix_date(fields):
    '''
    This takes the given day and year and produces a Python datetime
    as a date_adj field. On error, it adds an error field.
    '''
    for f in fields:
        try:
            year=int(f['year'].strip())
            d=f['date'].strip()
            if '/' in d:
                split=d.split('/')
                month=int(split[0])
                day=int(split[1])
            elif len(d) is 4:
                month=int(d[0:2])
                day=int(d[2:4])
            else:
                raise Exception('Date in unknown format %s' % d)
            f['date_adj']=datetime.date(year,month,day)
            f['year']=year
        except Exception, e:
            f['error']=('Date error for year %s date %s: %s' %
                        (f['year'], f['date'], str(e)))
        yield f



def normalize_county(fields):
    '''
    Turn state and county into uppercase names without periods.
    '''
    for f in fields:
        if f.has_key('error'): # Skip errors.
            yield f
            next
        county=f['county'].strip()
        state=f['state'].strip()
        if not state.isalpha() or not len(state) is 2:
            f['error']='The state is not normal %s' % state
            yield f
            next
        else:
            f['state_adj']=state.upper()
            f['county_adj']=county.upper().replace('.','')
            yield f


def fix_stage(fields):
    for f in fields:
        if f.has_key('error'):
            yield f
            next
        else:
            try:
                f['crop_stage']=int(f['crop_stage'])
                f['severity']=f['severity'].strip().upper()
                f['prevalence']=f['prevalence'].strip().upper()
            except Exception, e:
                pass
            yield f


_state_to_fips=statefips.state_fips()

def generate_county_matches():
    counties=county.county_basics()
    fips_to_state=state.fips_to_state()

    name_to_id=dict()
    possibles=list()
    for id,c in counties.iteritems():
        for tag in ['NAME10','NAMELSAD10']:
            full_name='%s,%s' % (c[tag].upper(),
                                 fips_to_state[int(c['STATEFP10'])].upper())
            name_to_id[full_name]=id
            possibles.append(full_name)
    return name_to_id, possibles



def guess_county_id(fields):
    name_to_id, possibles=generate_county_matches()

    for f in fields:
        if f.has_key('error'):
            yield f
            next
        else:
            maybe_name='%s,%s' % (f['county_adj'],f['state_adj'])
            if name_to_id.has_key(maybe_name):
                f['fips']=name_to_id[maybe_name]
            else:
                possibles=difflib.get_close_matches(maybe_name,possibles)
                logger.warning('Did not find county %s by name %s' %
                               (maybe_name, str(possibles)))
                f['error']='name not found'
            yield f



def fips_state(fields):
    state_to_fips=state.state_to_fips()

    for f in fields:
        if f.has_key('error'): # Skip errors.
            yield f
            next
        else:
            try:
                f['state_fips']=state_to_fips[f['state_adj']]
            except KeyError, e:
                f['error']='Could not find fips state for "%s"' % f['state_adj']
            yield f



def first_passage(fields):
    '''
    Find the first observation in every county.
    '''
    seen=set()
    for f in fields:
        if f.has_key('error'):
            # Don't yield from this one. Good values only.
            next
        else:
            key=(f['year'],f['fips'])
            if key not in seen:
                seen.add(key)
                yield f
            else:
                next

def has_severity_and_prevalence(fields):
    '''
    Want the records with the most covariates.
    '''
    # removed "VB" for variable from allowable severity levels.
    levels=['TR','LT','MD','HV']

    for record in fields:
        if record.has_key('error'):
            next
        else:
            cs=record['severity']
            pr=record['prevalence']
            stage=record['crop_stage']
            has_cs=cs in levels
            has_pr=pr in levels
            has_stage=type(stage) is int and stage is not 99

            if has_cs and has_pr and has_stage:
                record['severity_level']=levels.index(cs)
                record['prevalence_level']=levels.index(pr)
                yield record
            else:
                next

def remove_west(fields):
    '''
    The western US is throwing things off because their weather is quite
    different. They tend to be much later.
    '''
    remove_twoletter=['WA','OR','ID','CA','NV','UT','AZ']

    for f in fields:
        if f['state_adj'] not in remove_twoletter:
            yield f



def basic_chain():
    obs_file=luconfig.get('cereal_rust')

    lines=csv.reader(open(obs_file,'rU'))
    fields=to_fields(lines)
    fields=fix_date(fields)
    fields=fix_stage(fields)
    fields=normalize_county(fields)
    fields=guess_county_id(fields)
    fields=fips_state(fields)
    return fields

def get_first_passage():
    fields=basic_chain()
    return first_passage(fields)


def get_all_cov():
    fields=basic_chain()
    fields=has_severity_and_prevalence(fields)
    return fields


def get_first_passage_all_cov():
    fields=get_all_cov()
    fields=remove_west(fields)
    return first_passage(fields)


def same_county_multiple_stages():
    # key = (year,county), value=(date, stage, severity, prevalence)
    results=collections.defaultdict(list)
    fields=get_all_cov()
    for f in fields:
        key=(f['year'], f['fips'])
        results[key].append(tuple([f[x] for x in ['date_adj','crop_stage',
                                                  'severity','prevalence']]))
    counts=collections.defaultdict(int)
    for k, v in results.iteritems():
        counts[len(v)]+=1

    for cnt in sorted(counts):
        print cnt, counts[cnt]



def first_passage_to_R(filename):
    '''
    When saving the cleanest data, there are 680 first passage
    and 3901 when not just taking first passage.
    It's 670 when you throw out the states to the West.
    '''
    counties=county_shp.county_basics()
    fp=get_first_passage_all_cov()
    
    f=open(filename,'w')
    f.write('lat long year day geoid stage severity prevalence%s' % os.linesep)
    for rec in get_first_passage_all_cov():
        county=counties[rec['fips']]
        lat=county['INTPTLAT10']
        lon=county['INTPTLON10']
        day=(rec['date_adj']-datetime.date(rec['year'],1,1)).days
        f.write('%s %s %d %d %d %d %d %d%s' % (lat,lon,rec['year'],day,
                                         rec['fips'],rec['crop_stage'],
                                         rec['severity_level'],
                                         rec['prevalence_level'],os.linesep))

    f.close()



def characterize_first_passage():
    '''
    The results:
    For severity and prevalence, it should be:
    TR=<1%, LT=1-20%, MD=20-80%, HV=>80% VB=variable, NA=not available

    crop_stage: ',10,11,12,13,14,15,16,17,18,19,20,21,22,23,23\n,24,25,26,
                 27,28,29,3,30,30\n,31,5,8,99,HV,LT'
    prevalence: ',HV,LT,MD,MDNA,NA,RT,TR,TR\nHV,VB'
    severity: ',27,29,HA,HV,LT,MD,NA,TR,VB'

    prevalence: TR 343, LT 179, MD 129, HV 152, VB 7
    severity:   TR 384, LT 189, MD 95, HV 16, VB 143
    '''
    levels=['TR','LT','MD','HV','VB']

    categories=['prevalence', 'severity', 'crop_stage']
    coverage=collections.defaultdict(set)
    hist=dict()
    for initc in categories[0:2]:
        hist[initc]=dict(zip(levels,[0]*len(levels)))
    hist['crop_stage']=dict(zip(range(0,33),[0]*33))

    for record in get_first_passage():
        for c in categories:
            level=record[c]
            coverage[c].add(level)
            if hist[c].has_key(level):
                hist[c][level]+=1
    return coverage, hist


def plot_crop_stage():
    cs=list()
    poss=range(33)
    stage_cnt=0
    for record in get_first_passage():
        if record['crop_stage'] in poss:
            cs.append(record['crop_stage'])
            stage_cnt+=1

    logger.info('number with a crop stage %d' % stage_cnt)
    print('number with a crop stage %d' % stage_cnt) # 818
    fig=plt.figure()
    ax=fig.add_subplot(111)
    ax.hist(cs,33)
    ax.set_title('Crop Stages at First Incidence')
    ax.set_xlabel('Romig Scale of Wheat Growth')
    plt.show()



def plot_severity_v_prevalence():
    levels=['TR','LT','MD','HV','VB']

    mat=np.zeros((5,5),dtype=np.int)
    record_cnt=0
    cs_cnt=0
    pr_cnt=0
    for record in get_first_passage():
        cs=record['severity']
        pr=record['prevalence']
        has_cs=cs in levels
        has_pr=pr in levels
        if has_cs: cs_cnt+=1
        if has_pr: pr_cnt+=1
        if cs in levels and pr in levels:
            mat[levels.index(cs),levels.index(pr)]+=1
            record_cnt+=1

    print(mat)
    print record_cnt
    logging.debug('%d records have both prevalence and severity' % record_cnt)
    logging.debug('%d have prevalence, %d have severity' % (pr_cnt,cs_cnt))
    print '%d have prevalence, %d have severity' % (pr_cnt,cs_cnt)
    fig=plt.figure()
    ax=fig.add_subplot(111)
    ax.imshow(mat, cmap=cm.gray, interpolation='nearest')
    ax.set_title('Correlation of Prevalence and Severity')
    ax.set_xlabel('Prevalence')
    ax.set_ylabel('Severity')
    ind=np.arange(len(levels))
    ax.set_xticks(ind)
    ax.set_xticklabels( tuple(levels) )
    ax.set_yticks(ind)
    ax.set_yticklabels( tuple(levels) )

    plt.show()



def plot_severity_v_crop_stage(tag='severity'):
    '''
    Tag can also be 'prevalence'.
    '''
    levels=['TR','LT','MD','HV','VB']

    mat=np.zeros((5,33),dtype=np.int)
    record_cnt=0
    cs_cnt=0
    pr_cnt=0
    for record in get_first_passage():
        cs=record['crop_stage']
        pr=record[tag]
        has_cs=cs in range(33)
        has_pr=pr in levels
        if has_cs: cs_cnt+=1
        if has_pr: pr_cnt+=1
        if has_cs and has_pr:
            mat[levels.index(pr),cs]+=1
            record_cnt+=1

    fig=plt.figure()
    ax=fig.add_subplot(111)
    ax.imshow(mat, cmap=cm.gray, interpolation='nearest')
    ax.set_title('Correlation of Crop Stage and %s' % tag.title())
    ax.set_xlabel('Crop Stage on Romig Scale')
    ax.set_ylabel(tag.title())
    ind=np.arange(len(levels))
    #ax.set_xticks(ind)
    #ax.set_xticklabels( tuple(levels) )
    ax.set_yticks(ind)
    ax.set_yticklabels( tuple(levels) )

    plt.show()



def plot_severity(tag='severity'):
    '''
    Could also plot prevalence with this, using tag='prevalence'.
    '''
    cov,hist=characterize_first_passage()
    levels=['TR','LT','MD','HV','VB']
    level_names=['trace', 'light', 'medium', 'heavy', 'variable']
    ind=np.arange(len(levels))
    vals=np.zeros(len(levels),dtype=np.int)

    for idx,l in enumerate(levels):
        vals[idx]=hist[tag][l]

    fig=plt.figure()
    ax=fig.add_subplot(111)
    width=0.7
    rects=ax.bar(ind, vals, width, color='r')
    ax.set_title('Crop %s at First Observation' % tag.title())
    ax.set_xlabel('%s Level' % tag.title())
    ax.set_xticks(ind+width/2)
    ax.set_xticklabels( tuple(level_names) )
    plt.show()
    

if __name__ == '__main__':
    parser=DefaultArgumentParser(description="read observation data")
    parser.add_function('fields','show fields in the county dataset')
    parser.add_function('plotstage','plot the crop stage histogram')
    parser.add_function('firstr','write first passage to R with extra '
                        ' covariates')
    parser.add_argument('--out',metavar='out',type=str,
                        help='file to write')

    args=parser.parse_args()

    if args.fields:
        obs_file=luconfig.get('cereal_rust')

        lines=csv.reader(open(obs_file,'rU'))
        fields=to_fields(lines)
        fields=fix_date(fields)
        fields=fix_stage(fields)
        fields=normalize_county(fields)
        fields=guess_county_id(fields)
        fields=fips_state(fields)
        for f in fields:
            if f.has_key('error'):
                 print f['error']

    if args.plotstage:
        plot_crop_stage()

    if args.firstr:
        first_passage_to_R(args.out)

    if not parser.any_function():
        parser.print_help()
