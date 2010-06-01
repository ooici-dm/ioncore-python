# Python Capability Container start script.
# Starts empty container with system name set.

import logging
from twisted.internet import defer

from ion.core import ioninit
from ion.core import bootstrap

CONF = ioninit.config('ion.core.bootstrap')

# Static definition of service names
agent_procs = ioninit.get_config('ccagent_cfg', CONF)

svc_procs = ioninit.get_config('services_cfg', CONF)


@defer.inlineCallbacks
def main():
    """
    Initializes container
    """
    logging.info("ION CONTAINER initializing...")

    processes = []
    processes.extend(agent_procs)
    processes.extend(svc_procs)
    yield bootstrap.bootstrap(None, processes)

main()
