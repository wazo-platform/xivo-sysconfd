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

"""
    Abstract JSON sysconfd database management:
        - get key/values
        - set key/values
        - generate flat sh file from DB key/values
        
    Currently used by commonconf & ha modules
"""

__author__  = "Guillaume Bour <gbour@proformatique.com>"

import re
import traceback
from datetime import datetime

from xivo.http_json_server import HttpReqError


class JsonCore(object):
    def __init__(self):
        pass
        
    def safe_init(self, options):
        self.file       = None

    SECTIONS   = {}
    KEYSELECT  = ''

    ## type generators
    def _generators_dispatch(self, f, key, value):
        try:
            eval('self._gen_%s(f, key, value)' % type(value).__name__, {
                'self'  : self,
                'f'     : f,
                'key'   : key,
                'value' : value,
            })
        except:
            traceback.print_exc()
            self.log.error("no callback defined for *%s* value type" % \
                type(value).__name__)

    def _gen_bool(self, f, key, value):
        value = 'yes' if value else 'no'
        f.write("%s=\"%s\"\n" % (key, value))
        
    def _gen_str(self, f, key, value):
        value = re.sub(r'\r\n', r'\\r\\n', value)
        f.write("%s=\"%s\"\n" % (key, value))
        
    def _gen_int(self, f, key, value):
        f.write("%s=%d\n" % (key, value))

    def _gen_NoneType(self, f, key, value):
        f.write("#%s=\"\"\n" % key)
        
    def _gen_dict(self, f, key, value):
        key = key.replace('[', '_%s[') if '[' in key else ''.join(key, '_%s')

        for k, v in value.iteritems():
            self._generators_dispatch(f, key % k.upper(), v)
        f.write('\n')
        
    def _gen_list(self, f, key, value):
        if len(value) == 0:
            # empty list
            f.write("#%s[0]=\"\"\n" % key)
        else:
            for i in xrange(len(value)):
                self._generators_dispatch(f, "%s[%d]" % (key, i), value[i])
    ## /
    
    def generate(self, args, options):
        """
        GET /generate
        """
        
        with open(self.file, 'w') as f:
            def write_keyval(key):
                if args.has_key(key):
                    value = args[key]
                    self._generators_dispatch(f, key.upper().replace('.', '_'), value)
                else:
                    self.log.error("undefined key '%s' in sysconfd items database table" % key)

            def write_section(name):
                f.write("\n# %s\n" % name)
                for dbkey in self.SECTIONS[name]:
                    write_keyval(dbkey)

            f.write("### AUTOMATICALLY GENERATED BY sysconfd. DO NOT EDIT ###\n")
            f.write(datetime.now().strftime("# $%Y/%m/%d %H:%M:%S$\n\n"))
                
            f.write("### Configuration ###")
            for key in sorted(self.SECTIONS.keys()):
                write_section(key)

        return True
        
    def apply(self, args, options):
        raise HttpReqError(500, "not implemented")
