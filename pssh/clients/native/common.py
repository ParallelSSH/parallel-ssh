# This file is part of parallel-ssh.
#
# Copyright (C) 2014-2018 Panos Kittenis.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, version 2.1.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

import os

from ...exceptions import PKeyFileError


def _validate_pkey_path(pkey, host=None):
    if pkey is None:
        return
    pkey = os.path.normpath(os.path.expanduser(pkey))
    if not os.path.exists(pkey):
        msg = "File %s does not exist. " \
              "Please use either absolute or relative to user directory " \
              "paths like '~/.ssh/my_key' for pkey parameter"
        ex = PKeyFileError(msg, pkey)
        ex.host = host
        raise ex
    return pkey
