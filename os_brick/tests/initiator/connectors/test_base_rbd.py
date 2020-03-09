# Copyright 2020 Cloudbase Solutions Srl
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from unittest import mock

import ddt
from oslo_concurrency import processutils

from os_brick import exception
from os_brick.i18n import _
from os_brick.tests import base
from os_brick.initiator.connectors import base_rbd

# Both Linux and Windows tests are using those mocks.
class RBDConnectorTestMixin(object):
    def setUp(self):
        super(RBDConnectorTestMixin, self).setUp()

        self.user = 'fake_user'
        self.pool = 'fake_pool'
        self.volume = 'fake_volume'
        self.clustername = 'fake_ceph'
        self.hosts = ['192.168.10.2']
        self.ports = ['6789']
        self.keyring = "[client.cinder]\n  key = test\n"
        self.image_name = '%s/%s' % (self.pool, self.volume)

        self.connection_properties = {
            'auth_username': self.user,
            'name': self.image_name,
            'cluster_name': self.clustername,
            'hosts': self.hosts,
            'ports': self.ports,
            'keyring': self.keyring,
        }

@ddt.ddt
class TestRBDConnectorMixin(RBDConnectorTestMixin, base.TestCase):
    def setUp(self):
        super(TestRBDConnectorMixin, self).setUp()

        self._execute = mock.Mock(return_value=['fake_stdout', 'fake_stderr'])

        self._conn = base_rbd.RBDConnectorMixin()
        self._conn._execute = self._execute

    @ddt.data((['192.168.1.1', '192.168.1.2'],
               ['192.168.1.1', '192.168.1.2']),
              (['3ffe:1900:4545:3:200:f8ff:fe21:67cf',
                'fe80:0:0:0:200:f8ff:fe21:67cf'],
               ['[3ffe:1900:4545:3:200:f8ff:fe21:67cf]',
                '[fe80:0:0:0:200:f8ff:fe21:67cf]']),
              (['foobar', 'fizzbuzz'], ['foobar', 'fizzbuzz']),
              (['192.168.1.1',
                '3ffe:1900:4545:3:200:f8ff:fe21:67cf',
                'hello, world!'],
               ['192.168.1.1',
                '[3ffe:1900:4545:3:200:f8ff:fe21:67cf]',
                'hello, world!']))
    @ddt.unpack
    def test_sanitize_mon_host(self, hosts_in, hosts_out):
        self.assertEqual(hosts_out, self._conn._sanitize_mon_hosts(hosts_in))

    def test_get_rbd_args(self):
        res = self._conn._get_rbd_args(self.connection_properties, None)
        expected = ['--id', self.user,
                    '--mon_host', self.hosts[0] + ':' + self.ports[0]]
        self.assertEqual(expected, res)

    def test_get_rbd_args_with_conf(self):
        res = self._conn._get_rbd_args(self.connection_properties,
                                       mock.sentinel.conf_path)
        expected = ['--id', self.user,
                    '--mon_host', self.hosts[0] + ':' + self.ports[0],
                    '--conf', mock.sentinel.conf_path]
        self.assertEqual(expected, res)

    def test_get_version(self):
        stdout = ('ceph version 16.0.0-7114-gbe992dd8f5 '
                  '(be992dd8f5b577102f6a56026bdeb1c7f80c70eb) '
                  'pacific (dev)')
        self._execute.return_value = [stdout, 'fake_stderr']
        self.assertEqual('16.0.0-7114-gbe992dd8f5',
                         self._conn._get_rbd_version(
                            execute=self._execute, as_tuple=False))
        self.assertEqual((16, 0, 0),
                         self._conn._get_rbd_version(
                            execute=self._execute, as_tuple=True))

        stdout = ('ceph version 15.2.5 '
                  '(2c93eff00150f0cc5f106a559557a58d3d7b6f1f) '
                  'octopus (stable) ')
        self._execute.return_value = [stdout, 'fake_stderr']
        self.assertEqual('15.2.5',
                         self._conn._get_rbd_version(
                            execute=self._execute, as_tuple=False))
        self.assertEqual((15, 2, 5),
                         self._conn._get_rbd_version(
                            execute=self._execute, as_tuple=True))

    @ddt.data(False, True)
    @mock.patch.object(base_rbd.RBDConnectorMixin, '_get_rbd_version')
    def test_get_connector_properties(self, version_retrieved,
                                      mock_get_rbd_version):

        if version_retrieved:
            mock_get_rbd_version.return_value = mock.sentinel.rbd_version
            exp_rbd_version = mock.sentinel.rbd_version
        else:
            mock_get_rbd_version.side_effect = Exception
            exp_rbd_version = None

        exp_props = dict(rbd_version=exp_rbd_version)
        props = self._conn.get_connector_properties()
        self.assertEqual(exp_props, props)
