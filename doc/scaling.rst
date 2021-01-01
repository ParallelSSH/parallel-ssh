********
Scaling
********

Some guide lines on scaling ``parallel-ssh`` and pool size numbers.

In general, long lived commands with little or no output *gathering* will scale better. Pool sizes in the multiple thousands have been used successfully with little CPU overhead in the single thread running them in these use cases.

Conversely, many short lived commands with output gathering will not scale as well. In this use case, smaller pool sizes in the hundreds are likely to perform better with regards to CPU overhead in the event loop.

Multiple Python native threads, each of which can get its own event loop, may be used to scale this use case further as number of CPU cores allows. Note that ``parallel-ssh`` imports *must* be done within the target function of the newly started thread for it to receive its own event loop. ``gevent.get_hub()`` may be used to confirm that the worker thread event loop differs from the main thread.

Gathering is highlighted here as output generation does not affect scaling. Only when output is gathered either over multiple still running commands, or while more commands are being triggered, is overhead increased.

Technical Details
******************

To understand why this is, consider that in co-operative multi tasking, which is being used in this project via the ``gevent`` library, a co-routine (greenlet) needs to ``yield`` the event loop to allow others to execute - *co-operation*. When one co-routine is constantly grabbing the event loop in order to gather output, or when co-routines are constantly trying to start new short-lived commands, it causes contention with other co-routines that also want to use the event loop.

This manifests itself as increased CPU usage in the process running the event loop and reduced performance with regards to scaling improvements from increasing pool size.

On the other end of the spectrum, long lived remote commands that generate *no* output only need the event loop at the start, when they are establishing connections, and at the end, when they are finished and need to gather exit codes, which results in practically zero CPU overhead at any time other than start or end of command execution.

Output *generation* is done remotely and has no effect on the event loop until output is gathered - output buffers are iterated on. Only at that point does the event loop need to be held.
