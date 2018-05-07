# pylint: disable=too-many-public-methods,too-many-lines
"""Test for certbot_apache.configurator AutoHSTS functionality"""
import re
import unittest
import mock
# six is used in mock.patch()
import six  # pylint: disable=unused-import

from certbot import errors
from certbot_apache import constants
from certbot_apache.tests import util


class AutoHSTSTest(util.ApacheTest):
    """Tests for AutoHSTS feature"""
    # pylint: disable=protected-access

    def setUp(self):  # pylint: disable=arguments-differ
        super(AutoHSTSTest, self).setUp()

        self.config = util.get_apache_configurator(
            self.config_path, self.vhost_path, self.config_dir, self.work_dir)
        self.config.parser.modules.add("headers_module")
        self.config.parser.modules.add("mod_headers.c")
        self.config.parser.modules.add("ssl_module")
        self.config.parser.modules.add("mod_ssl.c")

        self.vh_truth = util.get_vh_truth(
            self.temp_dir, "debian_apache_2_4/multiple_vhosts")

    def get_autohsts_value(self, vh_path):
        """ Get value from Strict-Transport-Security header """
        header_path = self.config.parser.find_dir("Header", None, vh_path)
        if header_path:
            pat = '(?:[ "]|^)(strict-transport-security)(?:[ "]|$)'
            for head in header_path:
                if re.search(pat, self.config.parser.aug.get(head).lower()):
                    return self.config.parser.aug.get(head.replace("arg[3]",
                                                                   "arg[4]"))

    @mock.patch("certbot_apache.configurator.ApacheConfigurator.enable_mod")
    def test_autohsts_enable_headers_mod(self, mock_enable):
        self.config.parser.modules.discard("headers_module")
        self.config.parser.modules.discard("mod_header.c")
        self.config.enhance("ocspvhost.com", "auto_hsts", None)
        self.assertTrue(mock_enable.called)

    def test_autohsts_deploy(self):
        self.config.enhance("ocspvhost.com", "auto_hsts", None)

    def test_autohsts_deploy_already_exists(self):
        self.config.enhance("ocspvhost.com", "auto_hsts", None)
        self.assertRaises(errors.PluginEnhancementAlreadyPresent,
                          self.config.enhance,
                          "ocspvhost.com", "auto_hsts", None)

    @mock.patch("certbot_apache.constants.AUTOHSTS_FREQ", 0)
    def test_autohsts_increase(self):
        maxage = "\"max-age={0}\""
        initial_val = maxage.format(constants.AUTOHSTS_STEPS[0])
        inc_val = maxage.format(constants.AUTOHSTS_STEPS[1])

        self.config.enhance("ocspvhost.com", "auto_hsts", None)
        # Verify initial value
        self.assertEquals(self.get_autohsts_value(self.vh_truth[7].path),
                          initial_val)
        # Increase
        self.config.generic_updates("ocspvhost.com")
        # Verify increased value
        self.assertEquals(self.get_autohsts_value(self.vh_truth[7].path),
                          inc_val)

    @mock.patch("certbot_apache.configurator.ApacheConfigurator._autohsts_increase")
    def test_autohsts_increase_noop(self, mock_increase):
        maxage = "\"max-age={0}\""
        initial_val = maxage.format(constants.AUTOHSTS_STEPS[0])
        self.config.enhance("ocspvhost.com", "auto_hsts", None)
        # Verify initial value
        self.assertEquals(self.get_autohsts_value(self.vh_truth[7].path),
                          initial_val)

        self.config.generic_updates("ocspvhost.com")
        # Freq not patched, so value shouldn't increase
        self.assertFalse(mock_increase.called)


    @mock.patch("certbot_apache.constants.AUTOHSTS_FREQ", 0)
    def test_autohsts_increase_no_header(self):
        self.config.enhance("ocspvhost.com", "auto_hsts", None)
        # Remove the header
        dir_locs = self.config.parser.find_dir("Header", None,
                                              self.vh_truth[7].path)
        dir_loc = "/".join(dir_locs[0].split("/")[:-1])
        self.config.parser.aug.remove(dir_loc)
        self.assertRaises(errors.PluginError,
                          self.config.generic_updates,
                          "ocspvhost.com")

    @mock.patch("certbot_apache.constants.AUTOHSTS_FREQ", 0)
    def test_autohsts_increase_and_make_permanent(self):
        maxage = "\"max-age={0}\""
        max_val = maxage.format(constants.AUTOHSTS_PERMANENT)
        mock_lineage = mock.MagicMock()
        mock_lineage.key_path = "/etc/apache2/ssl/key-certbot_15.pem"
        self.config.enhance("ocspvhost.com", "auto_hsts", None)
        for i in range(len(constants.AUTOHSTS_STEPS)-1):
            # Ensure that value is not made permanent prematurely
            self.config.renew_deploy(mock_lineage)
            self.assertNotEquals(self.get_autohsts_value(self.vh_truth[7].path),
                                 max_val)
            self.config.generic_updates("ocspvhost.com")
            # Value should match pre-permanent increment step
            cur_val = maxage.format(constants.AUTOHSTS_STEPS[i+1])
            self.assertEquals(self.get_autohsts_value(self.vh_truth[7].path),
                              cur_val)
        # Make permanent
        self.config.renew_deploy(mock_lineage)
        self.assertEquals(self.get_autohsts_value(self.vh_truth[7].path),
                          max_val)

    def test_autohsts_update_noop(self):
        with mock.patch("time.time") as mock_time:
            # Time mock is used to make sure that the execution does not
            # continue when no autohsts entries exist in pluginstorage
            self.config._autohsts_update()
            self.assertFalse(mock_time.called)

    def test_autohsts_make_permanent_noop(self):
        self.config.storage.put = mock.MagicMock()
        self.config._autohsts_make_permanent(mock.MagicMock())
        # Make sure that the execution does not continue when no entries in store
        self.assertFalse(self.config.storage.put.called)


if __name__ == "__main__":
    unittest.main()  # pragma: no cover