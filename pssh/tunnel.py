from .clients.native.tunnel import Tunnel  # noqa: F401

from warnings import warn
__msg = "pssh.tunnel is deprecated and has been moved to " \
        "pssh.clients.native.tunnel"
warn(__msg)
