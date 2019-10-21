import logging
import rpy2
import rpy2.robjects as robjects

logger=logging.getLogger('emerge_fitter')


class emerge_fitter(object):
    '''
    This calls an R routine to do a logistic fit to the 
    wheat emergence data. It starts an R process."
    '''
    def __init__(self):
        robjects.r.source("emergence_fit.R")
        self._ecf=robjects.globalenv['emergence.coeffs']
        self._iv=robjects.IntVector

    def __call__(self,days,percent):
        try:
            avg, spread=self._ecf(self._iv(days),self._iv(percent))
        except rpy2.rinterface.RRuntimeError, e:
            logger.exception(e)
            logger.info('input days %s' % str(days))
            logger.info('input percent %s' % str(percent))
            raise
        return float(avg[0]), float(spread[0])
