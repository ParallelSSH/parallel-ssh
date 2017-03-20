from pssh import utils
import unittest
import os
from logging import NullHandler
try:
    from cStringIO import StringIO as BytesIO
except ImportError:
    from io import BytesIO
from uuid import uuid4

PKEY_FILENAME = os.path.sep.join([os.path.dirname(__file__), 'test_client_private_key'])
DSA_KEY_FILENAME = os.path.sep.join([os.path.dirname(__file__), 'test_client_private_key_dsa'])
ECDSA_KEY_FILENAME = os.path.sep.join([os.path.dirname(__file__), 'test_client_private_key_ecdsa'])

class ParallelSSHUtilsTest(unittest.TestCase):

    def test_enabling_host_logger(self):
        self.assertTrue(len([h for h in utils.host_logger.handlers
                             if isinstance(h, NullHandler)]) == 1)
        utils.enable_host_logger()
        # And again to test only one non-null handler is attached
        utils.enable_host_logger()
        self.assertTrue(len([h for h in utils.host_logger.handlers
                             if not isinstance(h, NullHandler)]) == 1)

    def test_enabling_pssh_logger(self):
        self.assertTrue(len([h for h in utils.logger.handlers
                             if isinstance(h, NullHandler)]) == 1)
        utils.enable_logger(utils.logger)
        self.assertTrue(len([h for h in utils.host_logger.handlers
                             if not isinstance(h, NullHandler)]) == 1)

    def test_loading_key_files(self):
        for key_filename in [PKEY_FILENAME, DSA_KEY_FILENAME, ECDSA_KEY_FILENAME]:
            pkey = utils.load_private_key(key_filename)
            self.assertTrue(pkey, msg="Error loading key from file %s" % (key_filename,))
            pkey = utils.load_private_key(open(key_filename))
            self.assertTrue(pkey, msg="Error loading key from open file object for file %s" % (key_filename,))
        fake_key = BytesIO(b"blah blah fakey fakey key")
        self.assertFalse(utils.load_private_key(fake_key))

    def test_openssh_config_missing(self):
        self.assertFalse(utils.read_openssh_config('test', config_file=str(uuid4())))
