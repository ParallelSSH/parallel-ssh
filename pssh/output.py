class HostOutput(dict):
    __slots__ = ('host', 'cmd', 'channel', 'stdout', 'stderr', 'stdin', 'exit_code', 'exception')

    def __init__(self, host, cmd, channel, stdout, stderr, stdin, exit_code=None, exception=None):
        dict.__init__(self, (('host', host), ('cmd', cmd), ('channel', channel),
                             ('stdout', stdout), ('stderr', stderr),
                             ('stdin', stdin), ('exit_code', exit_code),
                             ('exception', exception)))
        self.host = host
        self.cmd = cmd
        self.channel = channel
        self.stdout = stdout
        self.stderr = stderr
        self.stdin = stdin
        self.exception = exception
        self.exit_code = exit_code

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
        dict.__setitem__(self, name, value)

    def update(self, update_dict):
        dict.update(self, update_dict)
        for key in update_dict:
            object.__setattr__(self, key, update_dict[key])

    def __repr__(self):
        return "host=%s, cmd=%s, channel=%s, stdout=%s, stderr=%s, stdin=%s, \
exception=%s" % (self.host, self.cmd, self.channel, self.stdout, self.stdin,
                 self.stderr, self.exception,)
