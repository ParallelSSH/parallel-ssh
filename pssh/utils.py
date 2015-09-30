"""Package containing static utility functions for parallel-ssh module"""

import logging

host_logger = logging.getLogger('pssh.host_logger')
logger = logging.getLogger('pssh')

def enable_host_logger():
    """Enables host logger for logging stdout from remote servers as it
    becomes available
    """
    if logging.StreamHandler in [type(h) for h in host_logger.handlers]:
        logger.warning("Host logger already has a StreamHandler attached")
        return
    handler = logging.StreamHandler()
    host_log_format = logging.Formatter('%(message)s')
    handler.setFormatter(host_log_format)
    host_logger.addHandler(handler)
    host_logger.setLevel(logging.INFO)
