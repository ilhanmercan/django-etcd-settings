import os
import re

from django.http import HttpRequest
from django.test import TestCase
from django.test.utils import override_settings
from etcd_settings.loader import get_overwrites
from etcd_settings.manager import EtcdConfigManager
from etcd_settings.proxy import EtcdSettingsProxy
from mock import MagicMock

ETCD_PREFIX = '/config/etcd_settings'
ETCD_ENV = 'test'
ETCD_HOST = 'etcd'
ETCD_PORT = 2379
ETCD_DETAILS = dict(host=ETCD_HOST, port=ETCD_PORT, prefix=ETCD_PREFIX)


@override_settings(
    DJES_ETCD_DETAILS=ETCD_DETAILS,
    DJES_ENV=ETCD_ENV,
    DJES_REQUEST_GETTER='etcd_settings.utils.threaded',
    E=0
)
class TestEtcdSettingsProxy(TestCase):

    def setUp(self):
        mgr = EtcdConfigManager(
            prefix=ETCD_PREFIX, host=ETCD_HOST, port=ETCD_PORT)
        self.env_config = {
            "A": 1, "B": "c", "D": {"e": "f"}, "E": 1,
            "C": {'c2': 1}
        }
        mgr.set_env_defaults('test', self.env_config)
        mgr.set_config_sets({
            'foo': {'A': 11},
            'bar': {'C': {'c3': 2}}})
        self.proxy = EtcdSettingsProxy()
        with open('manage.py', 'w') as f:
            f.write("testing artifact")

    def tearDown(self):
        try:
            os.remove('manage.py')
        except:
            pass

    def test_proxy_reads_initial_blob(self):
        self.assertEquals(1, self.proxy.A)
        self.assertEquals("c", self.proxy.B)

    def test_proxy_raises_attribute_errors_on_not_found(self):
        with self.assertRaises(AttributeError):
            self.proxy.KEY_THAT_IS_NOT_THERE

    def test_proxy_reads_django_settings(self):
        self.assertEquals('test', self.proxy.DJES_ENV)

    def test_proxy_gives_prio_to_env_over_django_settings(self):
        self.assertEquals(1, self.proxy.E)

    def test_proxy_can_be_viewed_as_dict(self):
        d = self.proxy.as_dict()
        for k, v in self.env_config.items():
            self.assertEqual(v, d[k])

    def test_proxy_uses_dynamic_settings(self):
        r = HttpRequest()
        r.META = {'HTTP_X_DYNAMIC_SETTING': 'foo'}
        self.proxy._req_getter = MagicMock(return_value=r)
        self.assertEqual(11, self.proxy.A)

    def test_proxy_dynamic_settings_handle_dict_overwrites(self):
        r = HttpRequest()
        r.META = {'HTTP_X_DYNAMIC_SETTING': 'bar'}
        self.proxy._req_getter = MagicMock(return_value=r)
        c = self.proxy.C
        self.assertEqual(1, c.get('c2'))
        self.assertEqual(2, c.get('c3'))

    def test_proxy_locates_uwsgi_file(self):
        self.proxy._locate_wsgi_file(None)
        self.assertEqual(None, self.proxy._wsgi_file)
        self.proxy._locate_wsgi_file(__file__)
        self.assertEqual(__file__, self.proxy._wsgi_file)
        self.proxy._locate_wsgi_file('etcd_settings/proxy.py')
        self.assertIsNotNone(
            re.match("^/(.*)/etcd_settings/proxy.py", self.proxy._wsgi_file))
        os.remove('manage.py')
        with self.assertRaises(IOError):
            self.proxy._locate_wsgi_file('file_that_cannot_exist.py')

    def test_loader_gets_overwrites(self):
        self.assertEqual(
            self.env_config,
            get_overwrites(ETCD_ENV, None, ETCD_DETAILS)
        )
