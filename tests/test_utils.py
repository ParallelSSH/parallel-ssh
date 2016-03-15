from pssh import utils
import unittest


class ParallelSSHUtilsTest(unittest.TestCase):

    def test_enabling_host_logger(self):
        utils.enable_host_logger()
        # And again to test only one handler is attached
        utils.enable_host_logger()
        self.assertTrue(len(utils.host_logger.handlers)==1)

    def test_enabling_pssh_logger(self):
        utils.enable_logger(utils.logger)
        self.assertTrue(len(utils.logger.handlers)==1)
