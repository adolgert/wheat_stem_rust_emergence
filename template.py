__DESC='''
This is a demo of how to make every script you write have
logging and a quiet and verbose mode. Try calling it with

  python template.py; or
  python template.py --help; or
  python template.py --multiples; or
  python template.py --multiples -q # for quiet so INFO doesn't print.; or
  python template.py --multiples -v # for verbose so DEBUG does print.

If you use a local logger object, created as shown below, then another
python application or library that calls this one will be able to 
modify the error level and reporting style of logging messages from this
module.
'''
import logging
from default_parser import DefaultArgumentParser

logger=logging.getLogger(__file__)


def by_year():
    logger.debug('Entered by_year()')
    logger.info('Chose not to specify year.')
    logger.warn('This won\'t really do anything.')
    print 'Successfully completed!'
    raise Exception('nothing to succeed')
    logger.debug('Left by_year()')


def suite():
    '''
    Not every file needs to have a test suite, but this is how
    it might look, or you might use unittest.TestCase classes.
    '''
    import unittest
    suite=unittest.TestSuite()
    loader=unittest.TestLoader()
    suite.addTest(unittest.FunctionTestCase(by_year))
    return suite


if __name__ == '__main__':
    parser=DefaultArgumentParser(description=__DESC, suite=suite)
    parser.add_function('together','print all observations together')
    parser.add_function('multiples','print years separately in small multiples')

    parser.add_argument('--year',metavar='year',type=int,
                        help='The year of interest')

    args=parser.parse_args()

    try:
        if args.multiples:
            by_year()
    except:
        logger.exception('Could not complete --multiples.')

    if not parser.any_function():
        parser.print_help()
