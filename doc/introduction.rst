*****************
Design And Goals
*****************

``parallel-ssh``'s design goals and motivation are to provide a *library* for running *asynchronous* SSH commands in parallel with little to no load induced on the system by doing so with the intended usage being completely programmatic and non-interactive.

To meet these goals, API driven solutions are preferred first and foremost. This frees up the developer to drive the library via any method desired, be that environment variables, CI driven tasks, command line tools, existing OpenSSH or new configuration files, from within an application et al.


Design Principles
-------------------

Taking a cue from `PEP 20 <https://www.python.org/dev/peps/pep-0020/>`_, heavy emphasis is in the following areas.

* Readability
* Explicit is better than implicit
* Simple is better than complex
* Beautiful is better than ugly

Contributions are asked to keep these in mind.
