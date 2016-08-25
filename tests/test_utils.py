from pssh import utils
import unittest
import os
from cStringIO import StringIO
from uuid import uuid4

PKEY_FILENAME = os.path.sep.join([os.path.dirname(__file__), 'test_client_private_key'])
DSA_KEY_FILENAME = os.path.sep.join([os.path.dirname(__file__), 'test_client_private_key_dsa'])
ECDSA_KEY_FILENAME = os.path.sep.join([os.path.dirname(__file__), 'test_client_private_key_ecdsa'])

class ParallelSSHUtilsTest(unittest.TestCase):

    def test_enabling_host_logger(self):
        utils.enable_host_logger()
        # And again to test only one handler is attached
        utils.enable_host_logger()
        self.assertTrue(len(utils.host_logger.handlers)==1)

    def test_enabling_pssh_logger(self):
        utils.enable_logger(utils.logger)
        self.assertTrue(len(utils.logger.handlers)==1)
    
    def test_loading_key_files(self):
        for key_filename in [PKEY_FILENAME, DSA_KEY_FILENAME, ECDSA_KEY_FILENAME]:
            pkey = utils.load_private_key(key_filename)
            self.assertTrue(pkey, msg="Error loading key from file %s" % (key_filename,))
            pkey = utils.load_private_key(open(key_filename))
            self.assertTrue(pkey, msg="Error loading key from open file object for file %s" % (key_filename,))
        fake_key = StringIO("blah blah fakey fakey key")
        self.assertFalse(utils.load_private_key(fake_key))

    def test_openssh_config_missing(self):
        self.assertFalse(utils.read_openssh_config('test', config_file=str(uuid4())))
