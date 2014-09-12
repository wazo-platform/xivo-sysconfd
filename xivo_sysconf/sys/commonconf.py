# -*- coding: utf-8 -*-

# Copyright (C) 2010-2013 Avencall
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>


import logging
import subprocess
import traceback
from jinja2 import Template

logger = logging.getLogger('xivo_sysconf.modules.commonconf')

XivoCommonTpl = Template("""
### AUTOMATICALLY GENERATED BY sysconfd. DO NOT EDIT ###

{%- for key, value in conf.items() recursive %}
XIVO_{{ key }}="{{ value }}"
{%- endfor %}

""")

class CommonConf(object):

    def __init__(self, cfg):
        self.file = cfg.commonconf.commonconf_file
        self.cmd = cfg.commonconf.commonconf_cmd
        self.monit = cfg.commonconf.commonconf_monit
        self.monit_checks_dir = cfg.monit.monit_checks_dir
        self.monit_conf_dir = cfg.monit.monit_conf_dir

    def enable_disable_dhcpd(self, args):
        if 'dhcp_active' in args:
            if args['dhcp_active']:
                cmd = ['ln',
                      '-s',
                      '%s/isc-dhcp-server' % self.monit_checks_dir,
                      '%s/isc-dhcp-server' % self.monit_conf_dir]
            else:
                cmd = ['rm', '-f', '%s/isc-dhcp-server' % self.monit_conf_dir]
            try:
                p = subprocess.Popen(cmd,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT,
                                     close_fds=True)
                ret = p.wait()
                output = p.stdout.read()
            except OSError:
                traceback.print_exc()
                raise HttpReqError(500, "can't apply ha changes")

    def generate(self, args):
        self.enable_disable_dhcpd(args)
        conf_dict = {}
        for k, v in args.items():
             conf_dict[k.upper()] = v
        with open(self.file, 'w') as f:
            f.write(XivoCommonTpl.render(conf=conf_dict))

    def apply(self):
        output = ''
        try:
            p = subprocess.Popen([self.cmd],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,
                                 close_fds=True)
            ret = p.wait()
            output += p.stdout.read()
            logger.debug("commonconf apply: %d" % ret)

            if ret != 0:
                raise (output)
        except OSError:
            traceback.print_exc()
            raise ("can't apply commonconf changes")

        try:
            p = subprocess.Popen([self.monit],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,
                                 close_fds=True)
            ret = p.wait()
            output += '\n' + p.stdout.read()
            logger.debug("monit apply: %d" % ret)

            if ret != 0:
                raise (output)
        except OSError:
            traceback.print_exc()
            raise ("can't apply monit changes")

        return output
