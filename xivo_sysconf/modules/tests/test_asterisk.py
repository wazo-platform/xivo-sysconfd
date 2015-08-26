# -*- coding: utf-8 -*-

# Copyright (C) 2013-2015 Avencall
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
import shutil
import tempfile
import unittest
from mock import Mock, call, patch
from xivo.http_json_server import HttpReqError
from xivo_sysconf.modules.asterisk import Asterisk, _remove_directory, _is_valid_path_component, _move_directory


class TestAsterisk(unittest.TestCase):

    def setUp(self):
        self.base_voicemail_path = '/tmp/foo/bar'
        self.remove_directory = Mock()
        self.move_directory = Mock()
        self.is_valid_path_component = Mock()
        self.asterisk = Asterisk(self.base_voicemail_path)
        self.asterisk.remove_directory = self.remove_directory
        self.asterisk.move_directory = self.move_directory
        self.asterisk.is_valid_path_component = self.is_valid_path_component

    def test_delete_voicemail(self):
        self.is_valid_path_component.return_value = True
        mailbox = '1000'
        context = 'foo'
        options = {'context': context, 'mailbox': mailbox}

        self.asterisk.delete_voicemail(None, options)

        self.assertEqual([call(context), call(mailbox)],
                         self.is_valid_path_component.call_args_list)

        expected_path = os.path.join(self.base_voicemail_path, context, mailbox)
        self.remove_directory.assert_called_once_with(expected_path)

    def test_delete_voicemail_invalid_path_component_raise_error(self):
        self.asterisk.is_valid_path_component.return_value = False
        options = {'context': '', 'mailbox': ''}

        self.assertRaises(HttpReqError, self.asterisk.delete_voicemail, None, options)

    def test_move_voicemail(self):
        self.is_valid_path_component.return_value = True
        old_mailbox = '1000'
        old_context = 'foo'
        new_mailbox = '1001'
        new_context = 'bar'
        options = {'old_context': old_context, 'old_mailbox': old_mailbox,
                   'new_context': new_context, 'new_mailbox': new_mailbox}

        self.asterisk.move_voicemail(None, options)

        expected_calls = [call(old_context),
                          call(old_mailbox),
                          call(new_context),
                          call(new_mailbox)]
        self.assertEqual(expected_calls, self.is_valid_path_component.call_args_list)

        expected_old_path = os.path.join(self.base_voicemail_path, old_context, old_mailbox)
        expected_new_path = os.path.join(self.base_voicemail_path, new_context, new_mailbox)
        self.move_directory.assert_called_once_with(expected_old_path, expected_new_path)

    def test_move_voicemail_invalid_path_component_raise_error(self):
        self.asterisk.is_valid_path_component.return_value = False
        options = {'old_context': '', 'old_mailbox': '',
                   'new_context': '', 'new_mailbox': ''}

        self.assertRaises(HttpReqError, self.asterisk.delete_voicemail, None, options)


class TestRemoveDirectory(unittest.TestCase):

    def setUp(self):
        self.path = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.path, ignore_errors=True)

    def test_remove(self):
        _remove_directory(self.path)

        self.assertFalse(os.path.exists(self.path))


@patch('subprocess.check_call')
class TestMoveDirectory(unittest.TestCase):

    def test_move(self, check_call):
        old_path = "/var/spool/asterisk/default/1000"
        new_path = "/var/spool/asterisk/newctx/2000"
        _move_directory(old_path, new_path)

        expected_calls = [call(["rm", "-rf", new_path]),
                          call(["install", "-d", "-m", "750",
                                "-o", "asterisk", "-g", "asterisk",
                                "/var/spool/asterisk/newctx"]),
                          call(["mv", old_path, new_path])]

        self.assertEqual(check_call.call_args_list, expected_calls)


class TestPathComponentValidator(unittest.TestCase):

    def test_valid_path_component(self):
        path_components = [
            'foo',
            'foo.bar',
            '1234',
        ]

        for pc in path_components:
            self.assertTrue(_is_valid_path_component(pc), pc)

    def test_invalid_path_component(self):
        path_components = [
            '.',
            '..',
            'foo/bar',
            '',
        ]

        for pc in path_components:
            self.assertFalse(_is_valid_path_component(pc), pc)
