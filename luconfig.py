import ConfigParser
import logging
import os

logger=logging.getLogger('luconfig')

def get(name):
    config=ConfigParser.ConfigParser()
    suggested_files=['project.cfg', 'project_local.cfg']
    parsed_files=config.read(suggested_files)
    if len(parsed_files) is not len(suggested_files):
        unused=list(set(suggested_files)-set(parsed_files))
        logger.info('Using directory locations from %s, not %s.' %
                    (', '.join(parsed_files), ', '.join(unused)))
    return config.get('General',name)
