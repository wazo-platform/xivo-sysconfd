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

__author__  = "Guillaume Bour <gbour@proformatique.com>"

import os.path, logging

from xivo import http_json_server
from xivo.http_json_server import CMD_R

logger = logging.getLogger('xivo_sysconf.modules.services')

def timezone(args, options):
    """Return system timezone. * is Debian specific (and probably ubuntu too) *
    GET /timezone

    >>> return: 'Europe/Paris'
    """
    tz = None
    if os.path.exists('/etc/timezone'):
        with open('/etc/timezone') as f:
            tz = f.readline()[:-1]

    return tz


http_json_server.register(timezone, CMD_R, name='timezone')

