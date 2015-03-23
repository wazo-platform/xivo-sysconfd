# -*- coding: utf-8 -*-

# Copyright (C) 2011-2013 Avencall
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

import os.path
import shutil

from xivo import http_json_server
from xivo.http_json_server import HttpReqError
from xivo.http_json_server import CMD_R


class Asterisk(object):

    def __init__(self, base_vmail_path='/var/spool/asterisk/voicemail'):
        self._base_vmail_path = base_vmail_path
        self.remove_directory = _remove_directory
        self.is_valid_path_component = _is_valid_path_component

    def delete_voicemail(self, args, options):
        """Delete spool dir associated with voicemail

            options:
                name    : voicemail name
                context : voicemail context (opt. default is 'default')
        """
        if 'name' not in options:
            raise HttpReqError(400, "missing 'name' arg", json=True)
        context = options.get('context', 'default')
        name = options['name']

        if not self.is_valid_path_component(context):
            raise HttpReqError(400, 'invalid context')
        if not self.is_valid_path_component(name):
            raise HttpReqError(400, 'invalid name')

        vmpath = os.path.join(self._base_vmail_path, context, name)
        self.remove_directory(vmpath)

        return True


def _remove_directory( path):
    if os.path.exists(path):
        shutil.rmtree(path)


def _is_valid_path_component(path_component):
    return bool(path_component
                and path_component != os.curdir
                and path_component != os.pardir
                and os.sep not in path_component)


asterisk = Asterisk()
http_json_server.register(asterisk.delete_voicemail, CMD_R,
                          name='delete_voicemail')
