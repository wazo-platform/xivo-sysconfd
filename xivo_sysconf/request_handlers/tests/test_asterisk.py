# -*- coding: utf-8 -*-
# Copyright 2015-2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from mock import ANY, Mock, patch, sentinel

from xivo_bus import Publisher
from xivo_sysconf.request_handlers.asterisk import (
    AsteriskCommandFactory,
    AsteriskCommandExecutor,
)


class TestAsteriskCommandFactory(unittest.TestCase):

    def setUp(self):
        self.executor = Mock()
        self.factory = AsteriskCommandFactory(self.executor)

    def test_new_command(self):
        value = 'dialplan reload'

        command = self.factory.new_command(value)

        self.assertEqual(command.value, value)
        self.assertIs(command.executor, self.executor)
        self.assertEqual(command.data, value)

    def test_new_command_with_arg(self):
        value = 'sccp reset SEP001122334455'

        command = self.factory.new_command(value)

        self.assertEqual(command.data, value)

    def test_new_command_unauthorized(self):
        value = 'foobar'

        self.assertRaises(ValueError, self.factory.new_command, value)


class TestAsteriskCommandExecutor(unittest.TestCase):

    def setUp(self):
        self.bus_publisher = Mock(Publisher)
        self.executor = AsteriskCommandExecutor(self.bus_publisher)

    @patch('subprocess.call')
    def test_execute(self, mock_call):
        mock_call.return_value = 0

        self.executor.execute(sentinel.data)

        expected_args = ['asterisk', '-rx', sentinel.data]
        mock_call.assert_called_once_with(expected_args, stdout=ANY, close_fds=True)
