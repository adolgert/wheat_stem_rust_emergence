import math
import logging
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

import luconfig
from default_parser import DefaultArgumentParser

logger=logging.getLogger('prob_curve')


def logistic(t,t0,s=5):
    return 1/(1+np.exp(-(t-t0)/s))


def gen_sim(day_cnt, sim_cnt):
    res=np.zeros((sim_cnt,day_cnt),np.int)
    base_prob=lambda d: 0.04*logistic(d,100,7)
    #base_prob=lambda d: 0.05
    
    sim_days=np.arange(day_cnt,dtype=np.float)
    prob=base_prob(sim_days)
    for sim_idx in range(sim_cnt):
        population=963
        for d in sim_days:
            infected=int(np.random.binomial(population,prob[d]))
            res[sim_idx,d]=infected
            population -= infected
            if population<=0: break;
    return(res, sim_days)


def bounds(res, sim_days):
    sim_cnt=res.shape[0]
    day_cnt=res.shape[1]

    most=np.zeros(day_cnt,np.int)
    low_high=np.zeros((2,day_cnt),np.int)
    for ds in sim_days:
        one=res[:,ds]
        omin=np.min(one)
        omax=np.max(one)
        if omin!=omax:
            hist=np.histogram(one, bins=np.arange(np.min(one),np.max(one)+2))
            most[ds]=hist[1][hist[0].argmax()]
            sum_one=np.sum(one)
            low=None
            high=None
            for sim_idx in range(len(hist[0])):
                if not low and hist[0][sim_idx]>0.05*sum_one:
                    low=hist[1][sim_idx]
                if not high and hist[0][sim_idx]>0.95*sum_one:
                    high=hist[1][sim_idx]
            if low:
                low_high[0,ds]=low
            else:
                low_high[0,ds]=hist[1][0]
            if high:
                low_high[1,ds]=high
            else:
                low_high[1,ds]=hist[1][-1]
        else:
            most[ds]=one[0]
            low_high[0,ds]=one[0]
            low_high[0,ds]=one[0]

    return most, low_high


def bounded_curve():
    sim_cnt=100000
    day_cnt=250
    (res, sim_days)=gen_sim(day_cnt, sim_cnt)
    most, low_high = bounds(res,sim_days)

    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.plot(sim_days, most, 'r.-', sim_days, low_high[0,:], 'g-',
            sim_days, low_high[1,:], 'g-',
            sim_days, 50*logistic(sim_days,100,7),'b-')
    ax.set_title('Distribution of Sightings')
    ax.set_xlabel('Days')
    ax.set_ylabel('Infection Count')

    plt.show()


def curve():
    sim_cnt=1000
    day_cnt=250
    (res, sim_days)=gen_sim(day_cnt, sim_cnt)
    days=np.arange(0,day_cnt,dtype=np.float)
    to_plot=np.average(res,0)
    std_dev=np.std(res,0)
    logger.debug('days %d to_plot %s' % (len(days), str(to_plot.shape)))

    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.plot(days,to_plot, '.-', days,to_plot+std_dev, 'g-',
            days, to_plot-std_dev, 'g-',
            days, 50*logistic(days,100,7),'b-')
    ax.set_title('Distribution of Sightings')
    ax.set_xlabel('Days')
    ax.set_ylabel('Infection Count')

    plt.show()



if __name__ == '__main__':
    parser=DefaultArgumentParser(description="county data")
    parser.add_function('curve','plot probability curve')

    args=parser.parse_args()

    if args.curve:
        curve()

    if not parser.any_function():
        parser.print_help()
