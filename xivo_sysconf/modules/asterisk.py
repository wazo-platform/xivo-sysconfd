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

from flask.helpers import make_response
from ..sysconfd_server import app, VERSION

logger = logging.getLogger('xivo_sysconf.modules.delete_voicemail')

class Asterisk(object):
    def __init__(self, base_vmail_path='/var/spool/asterisk/voicemail'):
        self._base_vmail_path = base_vmail_path

    def delete_voicemail(self, context, mailbox):
        """Delete spool dir associated with voicemail

            options:
                mailbox    : voicemail name
                context : voicemail context (opt. default is 'default')
        """
        vmpath = os.path.join(self._base_vmail_path, context, mailbox)
        if os.path.exists(vmpath):
            shutil.rmtree(vmpath)

        return True

asterisk = Asterisk()

@app.route('/delete_voicemail/<context>/<mailbox>', methods=['DELETE'])
def delete_voicemail(context, mailbox):
    res = json.dumps(asterisk.delete_voicemail(context, mailbox))
    return make_response(res, 200, None, 'application/json')
