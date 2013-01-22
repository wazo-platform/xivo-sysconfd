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

import os
import subprocess
import logging
import re
import apt

from xivo_dao.alchemy import dbconnection
from xivo import http_json_server
from xivo.http_json_server import HttpReqError
from xivo.http_json_server import CMD_RW
from xivo import OrderedConf
from xivo import urisup
from xivo.moresynchro import RWLock
from xivo.AsteriskConfigParser import AsteriskConfigParser

log = logging.getLogger('xivo_sysconf.modules.wizard')


WIZARDLOCK = RWLock()

Wdc = {'templates_path':                        os.path.join(os.path.sep, 'usr', 'share', 'xivo-config', 'templates'),
       'custom_templates_path':                 os.path.join(os.path.sep, 'etc', 'pf-xivo', 'custom-templates'),
       'lock_timeout':                          60,
       'agid_config_filename':                  "xivo-agid.conf",
       'agid_tpl_directory':                    os.path.join('xivo-agid', 'etc', 'pf-xivo'),
       'agid_config_path':                      None,
       'asterisk_modules_config_filename':      "modules.conf",
       'asterisk_extconfig_config_filename':    "extconfig.conf",
       'asterisk_res_pgsql_config_filename':    "res_pgsql.conf",
       'asterisk_config_path':                  os.path.join(os.path.sep, 'etc', 'asterisk'),
       'asterisk_tpl_directory':                'asterisk',
       'webinterface_xivo_config_filename':     "xivo.ini",
       'webinterface_ipbx_config_filename':     "ipbx.ini",
       'webinterface_cti_config_filename':      "cti.ini",
       'webinterface_tpl_directory':            "web-interface",
       'webinterface_config_path':              None}


WIZARD_ASTERISK_EXTCONFIG_RE = re.compile(r'^([^,]*)(?:,(".*"|[^,]*)(?:,(.*))?)?$').match

WIZARD_IPBX_ENGINES = {'asterisk':
                                {'extconfig':   {'queue_log': 'queue_log'},
                                'database':
                                    {'postgresql':
                                        {'params':  {'charset':    'utf8'},
                                         'res':     {'dbname':  'dbname',
                                                     'dbuser':  'dbuser',
                                                     'dbpass':  'dbpass',
                                                     'dbhost':  'dbhost',
                                                     'dbport':  'dbport',
                                                     'charset': 'dbcharset',
                                                     'encoding': 'dbcharset'},
                                         'modules': ('res_config_pgsql.so',)}}}}

def _find_template_file(tplfilename, customtplfilename, newfilename):
    """
    Find configuration file
    Return configuration filename and file stat
    """
    if os.access(customtplfilename, (os.F_OK | os.R_OK)):
        filename = customtplfilename
        filestat = os.stat(customtplfilename)
    else:
        filename = tplfilename
        if os.access(tplfilename, (os.F_OK | os.R_OK)):
            filestat = os.stat(tplfilename)
        else:
            filestat = None

    return filename, filestat


def _write_config_file(filename, config, filestat=None):
    """
    Write configuration file
    """
    tmpfilename = "%s.tmp" % filename
    tmp = file(tmpfilename, 'w')
    tmp.write("; XIVO: FILE AUTOMATICALLY GENERATED BY THE XIVO CONFIGURATION SUBSYSTEM\n")
    config.write(tmp)
    tmp.close()

    if filestat:
        os.chmod(tmpfilename, filestat[0])
        os.chown(tmpfilename, filestat[4], filestat[5])

    os.rename(tmpfilename, filename)


def merge_config_file(tplfilename, customtplfilename, newfilename, cfgdict, ipbxengine=None):
    """
    Generate a configuration file from a template
    """
    filename, filestat = _find_template_file(tplfilename, customtplfilename, newfilename)

    xdict = dict(cfgdict)

    if ipbxengine == 'asterisk':
        cfg = AsteriskConfigParser(filename=filename)
        newcfg = AsteriskConfigParser()
        putfunc = newcfg.append

        for directive in cfg.directives():
            newcfg.add_directive(directive[0], directive[1])
    else:
        cfg = OrderedConf.OrderedRawConf(filename=filename)
        newcfg = OrderedConf.OrderedRawConf(allow_multiple=False)
        putfunc = newcfg.set

    for sec in cfg:
        secname = sec.get_name()
        newcfg.add_section(secname)
        for opt in sec:
            optname = opt.get_name()
            if xdict.has_key(secname) \
               and xdict[secname].has_key(optname):
                value = xdict[secname][optname]
                del xdict[secname][optname]
                if not xdict[secname]:
                    del xdict[secname]
            else:
                value = opt.get_value()

            putfunc(secname, optname, value)

    for sec, options in xdict.iteritems():
        if not newcfg.has_section(sec):
            newcfg.add_section(sec)
        for optname, optvalue in options.iteritems():
            putfunc(sec, optname, optvalue)

    _write_config_file(newfilename, newcfg, filestat)


def asterisk_modules_config(tplfilename, customtplfilename, newfilename, modules):
    """
    Generate Asterisk modules.conf from a template
    """
    filename, filestat = _find_template_file(tplfilename, customtplfilename, newfilename)
    customfile = customtplfilename == filename

    cfg = AsteriskConfigParser(filename=filename)
    newcfg = AsteriskConfigParser()

    for directive in cfg.directives():
        newcfg.add_directive(directive[0], directive[1])

    mods = list(modules)
    appendmods = True

    if customfile and cfg.has_option('modules', 'noload'):
        for optname, optvalue in cfg.items('modules'):
            if optname == 'noload' and optvalue in mods:
                mods.remove(optvalue)

    for sec in cfg:
        secname = sec.get_name()
        newcfg.add_section(secname)
        for opt in sec:
            optname = opt.get_name()
            optvalue = opt.get_value()
            if secname != 'modules':
                newcfg.append(secname, optname, optvalue)
                continue
            if optname in ('preload', 'load', 'noload'):
                if appendmods:
                    appendmods = False
                    for module in mods:
                        newcfg.append(secname, 'preload', module)
                if optvalue in mods:
                    continue
            newcfg.append(secname, optname, optvalue)

    if appendmods:
        appendmods = False
        if not newcfg.has_section('modules'):
            newcfg.add_section('modules')
        for module in mods:
            newcfg.append('modules', 'preload', module)

    _write_config_file(newfilename, newcfg, filestat)


def asterisk_extconfig(tplfilename, customtplfilename, newfilename, extconfig, dbtype, dbname):
    """
    Generate Asterisk extconfig.conf from a template
    """
    filename, filestat = _find_template_file(tplfilename, customtplfilename, newfilename)
    customfile = customtplfilename == filename

    cfg = AsteriskConfigParser(filename=filename)
    newcfg = AsteriskConfigParser()

    for directive in cfg.directives():
        newcfg.add_directive(directive[0], directive[1])

    extcfg = dict(extconfig)

    if customfile and cfg.has_section('settings'):
        for optname in extcfg.keys():
            if not cfg.has_option('settings', optname):
                del extcfg[optname]

    for sec in cfg:
        secname = sec.get_name()
        newcfg.add_section(secname)
        for opt in sec:
            optname = opt.get_name()
            optvalue = opt.get_value()
            if secname != 'settings' or not extcfg.has_key(optname):
                newcfg.append(secname, optname, optvalue)
                continue
            values = WIZARD_ASTERISK_EXTCONFIG_RE(optvalue)
            line = []
            if not values.group(1) or not customfile:
                line.append(dbtype)
            else:
                line.append(values.group(1))
            if not values.group(2) or not customfile:
                line.append('"%s"' % dbname)
            else:
                line.append(values.group(2))
            if values.group(3) is None:
                line.append(extcfg[optname])
            else:
                line.append(values.group(3))
            newcfg.append(secname, optname, ','.join(line))
            del extcfg[optname]

    for optname, table in extcfg.iteritems():
        newcfg.append('settings', optname, '%s,"%s",%s' % (dbtype, dbname, table))

    _write_config_file(newfilename, newcfg, filestat)


def asterisk_pgsql_config(authority, database, params, options):
    """
    Return PostgreSQL options for Asterisk
    """

    dbparams = WIZARD_IPBX_ENGINES['asterisk']['database']['postgresql']['params']

    rs = {}

    xdict = dict(options)
    if isinstance(authority, (tuple, list)):
        if authority[0]:
            rs[xdict['dbuser']] = authority[0]
        if authority[1]:
            rs[xdict['dbpass']] = authority[1]
        if authority[2]:
            rs[xdict['dbhost']] = authority[2]
        if authority[3]:
            rs[xdict['dbport']] = authority[3]

    if database:
        rs[xdict['dbname']] = database

    del(xdict['dbuser'],
        xdict['dbpass'],
        xdict['dbhost'],
        xdict['dbport'],
        xdict['dbname'])

    rs = dict(rs, **dbparams)

    if params:
        for k, v in params.iteritems():
            if xdict.has_key(k):
                rs[xdict[k]] = v
            else:
                rs[k] = v

    return rs


def asterisk_configuration(dburi, dbinfo, dbparams):
    """
    Entry point for Asterisk configuration
    """

    merge_config_file(Wdc['asterisk_res_pgsql_tpl_file'],
                  Wdc['asterisk_res_pgsql_custom_tpl_file'],
                  Wdc['asterisk_res_pgsql_file'],
                  {'general':
                        asterisk_pgsql_config(dburi[1],
                                              'asterisk',
                                              dbparams,
                                              dbinfo['res'])},
                  ipbxengine='asterisk')

    if 'modules' in dbinfo:
        asterisk_modules_config(Wdc['asterisk_modules_tpl_file'],
                                Wdc['asterisk_modules_custom_tpl_file'],
                                Wdc['asterisk_modules_file'],
                                dbinfo['modules'])

    if 'extconfig' in WIZARD_IPBX_ENGINES['asterisk']:
        asterisk_extconfig(Wdc['asterisk_extconfig_tpl_file'],
                           Wdc['asterisk_extconfig_custom_tpl_file'],
                           Wdc['asterisk_extconfig_file'],
                           WIZARD_IPBX_ENGINES['asterisk']['extconfig'],
                           'pgsql',
                           'asterisk')


def set_db_backends(args, options):
    """
    POST /set_db_backends
    """

    if 'xivo' not in args:
        raise HttpReqError(415, "missing option 'xivo'")
    elif 'ipbx' not in args:
        raise HttpReqError(415, "missing option 'ipbx'")
    elif 'ipbxengine' not in args:
        raise HttpReqError(415, "missing option 'ipbxengine'")
    elif args['ipbxengine'] not in WIZARD_IPBX_ENGINES:
        raise HttpReqError(415, "invalid ipbxengine: %r" % args['ipbxengine'])

    if not WIZARDLOCK.acquire_read(Wdc['lock_timeout']):
        raise HttpReqError(503, "unable to take WIZARDLOCK for reading after %s seconds" % Wdc['lock_timeout'])

    ipbxdbinfo = WIZARD_IPBX_ENGINES[args['ipbxengine']]['database']
    ipbxdburi = list(urisup.uri_help_split(args['ipbx']))

    if ipbxdburi[0] is None or ipbxdburi[0].lower() not in ipbxdbinfo:
        raise HttpReqError(415, "invalid option 'ipbx'")
    else:
        ipbxdburi[0] = ipbxdburi[0].lower()

    if ipbxdbinfo[ipbxdburi[0]]['params']:
        ipbxdbparams = ipbxdbinfo[ipbxdburi[0]]['params']
    else:
        ipbxdbparams = {}

    if ipbxdburi[3]:
        ipbxdbparams.update(dict(ipbxdburi[3]))

    if ipbxdbparams:
        ipbxdburi[3] = zip(ipbxdbparams.keys(), ipbxdbparams.values())
    else:
        ipbxdburi[3] = None

    args['ipbx'] = urisup.uri_help_unsplit(ipbxdburi)

    try:
        _new_db_connection_pool = dbconnection.DBConnectionPool(dbconnection.DBConnection)
        dbconnection.register_db_connection_pool(_new_db_connection_pool)

        dbconnection.add_connection_as(args['xivo'], 'xivo')
        connection = dbconnection.get_connection('xivo')
        if not connection:
            raise HttpReqError(415, "unable to connect to 'xivo' database")
        connection.close()

        dbconnection.add_connection_as(args['ipbx'], 'asterisk')
        connection = dbconnection.get_connection('asterisk')
        if not connection:
            raise HttpReqError(415, "unable to connect to 'ipbx' database")
        connection.close()

        merge_config_file(Wdc['agid_config_tpl_file'],
                          Wdc['agid_config_custom_tpl_file'],
                          Wdc['agid_config_file'],
                          {'db':
                                {'db_uri':  args['ipbx']}})

        merge_config_file(Wdc['webinterface_xivo_tpl_file'],
                          Wdc['webinterface_xivo_custom_tpl_file'],
                          Wdc['webinterface_xivo_file'],
                          {'general':
                                {'datastorage': '"%s"' % args['xivo']}})

        merge_config_file(Wdc['webinterface_cti_tpl_file'],
                          Wdc['webinterface_cti_custom_tpl_file'],
                          Wdc['webinterface_cti_file'],
                          {'general':
                                {'datastorage': '"%s"' % args['xivo']},
                           'queuelogger':
                                {'datastorage': '"%s"' % args['ipbx']},
                          })

        merge_config_file("%s.%s" % (Wdc['webinterface_ipbx_tpl_file'], args['ipbxengine']),
                          "%s.%s" % (Wdc['webinterface_ipbx_custom_tpl_file'], args['ipbxengine']),
                          Wdc['webinterface_ipbx_file'],
                          {'general':
                                {'datastorage': '"%s"' % args['ipbx']}})

        if args['ipbxengine'] == 'asterisk':
            asterisk_configuration(ipbxdburi, ipbxdbinfo[ipbxdburi[0]], ipbxdbparams)
    finally:
        WIZARDLOCK.release()


def safe_init(options):
    """Load parameters, etc"""
    global Wdc

    cfg = options.configuration

    Wdc['xivo_config_path'] = cfg.get('general', 'xivo_config_path')

    if cfg.has_section('wizard'):
        for x in Wdc.iterkeys():
            if cfg.has_option('wizard', x):
                Wdc[x] = cfg.get('wizard', x)

    Wdc['lock_timeout'] = float(Wdc['lock_timeout'])

    if Wdc['agid_config_path'] is None:
        Wdc['agid_config_path'] = Wdc['xivo_config_path']

    if Wdc['webinterface_config_path'] is None:
        Wdc['webinterface_config_path'] = os.path.join(Wdc['xivo_config_path'], "web-interface")

    for x in ('agid',):
        Wdc["%s_config_file" % x] = os.path.join(Wdc["%s_config_path" % x],
                                                 Wdc["%s_config_filename" % x])

        Wdc["%s_config_tpl_file" % x] = os.path.join(Wdc['templates_path'],
                                                     Wdc["%s_tpl_directory" % x],
                                                     Wdc["%s_config_filename" % x])

        Wdc["%s_config_custom_tpl_file" % x] = os.path.join(Wdc['custom_templates_path'],
                                                            Wdc["%s_tpl_directory" % x],
                                                            Wdc["%s_config_filename" % x])

    for x in ('modules', 'extconfig', 'res_pgsql'):
        Wdc["asterisk_%s_file" % x] = os.path.join(Wdc['asterisk_config_path'],
                                                   Wdc["asterisk_%s_config_filename" % x])

        Wdc["asterisk_%s_tpl_file" % x] = os.path.join(Wdc['templates_path'],
                                                       Wdc['asterisk_tpl_directory'],
                                                       Wdc["asterisk_%s_config_filename" % x])

        Wdc["asterisk_%s_custom_tpl_file" % x] = os.path.join(Wdc['custom_templates_path'],
                                                              Wdc['asterisk_tpl_directory'],
                                                              Wdc["asterisk_%s_config_filename" % x])

    for x in ('xivo', 'ipbx', 'cti'):
        Wdc["webinterface_%s_file" % x] = os.path.join(Wdc['webinterface_config_path'],
                                                       Wdc["webinterface_%s_config_filename" % x])

        Wdc["webinterface_%s_tpl_file" % x] = os.path.join(Wdc['templates_path'],
                                                           Wdc['webinterface_tpl_directory'],
                                                           Wdc["webinterface_%s_config_filename" % x])

        Wdc["webinterface_%s_custom_tpl_file" % x] = os.path.join(Wdc['custom_templates_path'],
                                                                  Wdc['webinterface_tpl_directory'],
                                                                  Wdc["webinterface_%s_config_filename" % x])


http_json_server.register(set_db_backends, CMD_RW, safe_init=safe_init)
