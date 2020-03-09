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

import re

from oslo_concurrency import processutils as putils
from oslo_log import log as logging
from oslo_utils import netutils

from os_brick import exception
from os_brick.i18n import _

LOG = logging.getLogger(__name__)


class RBDConnectorMixin(object):
    """Mixin covering cross platform RBD connector functionality"""

    _rbd_version_re = re.compile('ceph version (\S+)')

    @staticmethod
    def _sanitize_mon_hosts(hosts):
        def _sanitize_host(host):
            if netutils.is_valid_ipv6(host):
                host = '[%s]' % host
            return host
        return list(map(_sanitize_host, hosts))

    @classmethod
    def _get_rbd_args(cls, connection_properties, conf=None):
        try:
            user = connection_properties.get('auth_username')
            monitor_ips = connection_properties.get('hosts')
            monitor_ports = connection_properties.get('ports')
        except KeyError:
            msg = _("Connect volume failed, malformed connection properties")
            raise exception.BrickException(msg=msg)

        args = []
        if user:
            args = ['--id', user]
        if monitor_ips and monitor_ports:
            monitors = ["%s:%s" % (ip, port) for ip, port in
                        zip(
                            cls._sanitize_mon_hosts(monitor_ips),
                            monitor_ports)]
            for monitor in monitors:
                args += ['--mon_host', monitor]

        if conf:
            args += ['--conf', conf]

        return args

    @classmethod
    def _get_rbd_version(cls, execute=None, as_tuple=True):
        execute = execute or putils.execute

        cmd = ['rbd', '--version']
        out, err = execute(*cmd)
        version = cls._rbd_version_re.findall(out)
        if not version:
            LOG.warning("Unsupported ceph version string: %s", out)
            return

        version = version[0]
        if as_tuple:
            version = tuple(map(int, version.split('-')[0].split('.')))

        return version

    @staticmethod
    def get_connector_properties(*args, **kwargs):
        try:
            rbd_version = RBDConnectorMixin._get_rbd_version(
                excute=kwargs.get('executor'), as_tuple=True)
        except Exception as ex:
            LOG.debug("Couldn't retrieve RBD version. Exception: %s" % ex)
            rbd_version = None
        return dict(rbd_version=rbd_version)
