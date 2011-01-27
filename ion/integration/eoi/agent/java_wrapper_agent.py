#!/usr/bin/env python

"""
@file:   ion/integration/eoi/agent/java_wrapper_agent.py
@author: Chris Mueller
@author: Tim LaRocque
@brief:  EOI JavaWrapperAgent and JavaWrapperAgentClient class definitions
"""

import ion.util.ionlog
import ion.util.procutils as pu

from twisted.internet import defer, reactor
from ion.core.process.process import Process, ProcessFactory
from ion.core.process.service_process import ServiceProcess, ServiceClient
from ion.util.state_object import BasicStates
from ion.util.os_process import OSProcess

log = ion.util.ionlog.getLogger(__name__)


class JavaWrapperAgent(ServiceProcess):
    """
    Class designed to facilitate (Java) Dataset Agent's tight interaction with ION in
    lieu of an incomplete Java CC.  Wrapping Java Agents in Python processes in this way
    provides the following functionality:
    Agent registration, process lifecycle, and reactivity to other core ION services
    """
    
    
    declare = ServiceProcess.service_declare(name='java_wrapper_agent',
                                             version='0.1.0',
                                             dependencies=[]) # no dependencies

        
    def __init__(self, *args, **kwargs):
        '''
        Initialize the JavaWrapperAgent instance, init instance fields, etc.
        '''
        # Step 1: Delegate initialization to parent "ServiceProcess"
        log.info('')
        log.info('Initializing class instance...')
        ServiceProcess.__init__(self, *args, **kwargs)
        
        # Step 2: Create class attributes
        self.__agent_phandle = None
        self.__agent_binding = None
        self.__agent_updt_op = None
        self.__agent_term_op = None
        self.__agent_spawn_args = None
        self.__binding_key_deferred = None
        
        # Step 3: Setup the dataset context dictionary (to simulate acquiring context from the dataset registry)
        # @todo: remove 'callbck', it is no longer used
        self.__dataset_context_dict = {"sos_station_st":{"source_type":"SOS",
                                              "callback":"data_message_callback",
                                              "base_url":"http://sdf.ndbc.noaa.gov/sos/server.php?",
                                              "start_time":"2008-08-01T00:00:00Z",
                                              "end_time":"2008-08-02T00:00:00Z",
                                              "property":"sea_water_temperature",
                                              "stationId":"41012"},
                                        "sos_station_sal":{"source_type":"SOS",
                                              "callback":"data_message_callback",
                                              "base_url":"http://sdf.ndbc.noaa.gov/sos/server.php?",
                                              "start_time":"2008-08-01T00:00:00Z",
                                              "end_time":"2008-08-02T00:00:00Z",
                                              "property":"salinity",
                                              "stationId":"41012"},
                                        "sos_glider_st":{"source_type":"SOS",
                                              "callback":"data_message_callback",
                                              "base_url":"http://sdf.ndbc.noaa.gov/sos/server.php?",
                                              "start_time":"2010-07-26T00:00:00Z",
                                              "end_time":"2010-07-27T00:00:00Z",
                                              "property":"sea_water_temperature",
                                              "stationId":"48900"},
                                        "sos_glider_sal":{"source_type":"SOS",
                                              "callback":"data_message_callback",
                                              "base_url":"http://sdf.ndbc.noaa.gov/sos/server.php?",
                                              "start_time":"2010-07-26T00:00:00Z",
                                              "end_time":"2010-07-27T00:00:00Z",
                                              "property":"salinity",
                                              "stationId":"48900"},
                                        "usgs_multi_test":{"source_type":"USGS",
                                              "callback":"data_message_callback",
                                              "base_url":"http://waterservices.usgs.gov/nwis/iv?",
                                              "start_time":"2010-10-10T00:00:00Z",
                                              "end_time":"2010-10-12T00:00:00Z",
                                              "property":["00010", "00060"],
                                              "stationId":["01362500","01463500","01646500"]},
                                        "usgs_station_temp":{"source_type":"USGS",
                                              "callback":"data_message_callback",
                                              "base_url":"http://waterservices.usgs.gov/nwis/iv?",
                                              "start_time":"2010-10-10T00:00:00Z",
                                              "end_time":"2010-10-12T00:00:00Z",
                                              "property":"00010",
                                              "stationId":"01463500"},
                                        "usgs_station_sflow":{"source_type":"USGS",
                                              "callback":"data_message_callback",
                                              "base_url":"http://waterservices.usgs.gov/nwis/iv?",
                                              "start_time":"2010-10-10T00:00:00Z",
                                              "end_time":"2010-10-12T00:00:00Z",
                                              "property":"00060",
                                              "stationId":"01463500"},
                                        "aoml_xbt_all":{"source_type":"AOML",
                                              "callback":"data_message_callback",
                                              "base_url":"http://www.aoml.noaa.gov/cgi-bin/trinanes/datosxbt.cgi?",
                                              "start_time":"2010-09-10T00:00:00Z",
                                              "end_time":"2010-09-12T00:00:00Z",
                                              "type":"xbt",
                                              "left":"-82.0",
                                              "right":"-60.0",
                                              "bottom":"31.0",
                                              "top":"47.0"},
                                        "aoml_ctd_all":{"source_type":"AOML",
                                              "callback":"data_message_callback",
                                              "base_url":"http://www.aoml.noaa.gov/cgi-bin/trinanes/datosxbt.cgi?",
                                              "start_time":"2010-09-10T00:00:00Z",
                                              "end_time":"2010-09-12T00:00:00Z",
                                              "type":"ctd",
                                              "left":"-82.0",
                                              "right":"-60.0",
                                              "bottom":"31.0",
                                              "top":"47.0"}}
        
        # Step 4: Attach a receiver for incoming callbacks during initialization
#        self.callbacks_id = Id(self.id.local+"cb", self.id.container)
#        self.callbacks_receiver = ProcessReceiver(
#                                    label=self.proc_name,
#                                    name=self.callbacks_id.full,
#                                    group=self.proc_group,
#                                    process=self,
#                                    handler=self.receive)


    @defer.inlineCallbacks
    def slc_init(self):
        '''
        Initialization upon Service spawning.  This life-cycle process, in-turn, spawns the
        a Dataset Agent for which it is providing governance
        '''
        log.debug(" -[]- Entered slc_init()")
        # Step 1: Delegate initialization to parent class
        yield defer.maybeDeferred(ServiceProcess.slc_init, self)
        
        # Step 2: Spawn the associated dataset agent (if not already done)
        res = yield defer.maybeDeferred(self._spawn_dataset_agent)
    
    @defer.inlineCallbacks
    def slc_activate(self):
        '''
        Service activation during spawning.  Returns a deferred which does not
        resolve until the external Dataset Agent remotely invokes op_binding_key_callback()
        @return: defer.Deferred()
        '''
        log.debug(" -[]- Entered slc_activate()")
        # Step 1: Delegate initialization to parent class
        yield defer.maybeDeferred(ServiceProcess.slc_activate, self)
        
        # Step 2: Suspend execution until receipt of the Dataset Agent's binding key
        def _recieve_binding_key(self):
            d = self.__binding_key_deferred
            if d is None:
                d = defer.Deferred()
                self.__binding_key_deferred = d
            return d
        
        d = defer.Deferred()
        
        reactor.callLater(0, lambda: _recieve_binding_key(self))

#        defer.returnValue(d)
    
    def slc_deactivate(self):
        '''
        '''
        log.debug(" -[]- Entered java_wrapper_agent.slc_deactivate()")
        log.debug(" ********* Current state is %s" % self._get_state())
    
    @defer.inlineCallbacks
    def slc_terminate(self):
        '''
        Termination life cycle process.  This affect also terminates the Java Dataset Agent which
        this class is intended to wrap.
        '''
        log.debug(" -[]- Entered java_wrapper_agent.slc_terminate()")
        log.debug(" ********* Current state is %s" % self._get_state())
        # Step 1: Terminate the underlying dataset agent
        returncode, outlines, errlines = yield self._terminate_dataset_agent()
        msg1 = "Agent process terminated.  RETURN CODE == %s" % str(returncode)
        msg2 = "Agent process terminated with the following log:\r"
        if outlines is not None:
            msg2 += '\r'.join(outlines) + '\r'
        if errlines is not None:
            msg2 += '\r'.join(errlines)
        log.info(msg1)
        log.debug(msg2)
        
        # Step 2: Finish termination by delegating to parent
        yield defer.maybeDeferred(ServiceProcess.slc_terminate, self)
        defer.returnValue(returncode)


    def on_deactivate(self, *args, **kwargs):
        """
        """
        log.debug(" -[]- Entered java_wrapper_agent.on_deactivate()")
        log.debug(" ********* Current state is %s" % self._get_state())
        
    def _spawn_dataset_agent(self):
        '''
        Instantiates the Java Dataset Agent providing appropriate binding information so the underlying agent can establish messaging channels
        '''
        log.debug(" -[]- Entered _spawn_dataset_agent()")
        if self._get_state() is not BasicStates.S_READY:
            err_msg = "External dataset agent cannot be spawned unless %s's service state is %s" % (__name__, str(BasicStates.S_READY))
            log.warn(err_msg)
            raise RuntimeError(err_msg)
        
        # Step 1: Acquire the dataset spawn arguments
        (binary, args) = self.agent_spawn_args
        log.info("Spawning delegate process with command: \n\n\t'%s %s'\n" % (binary, " ".join(args)))
        
        # Step 2: Start the Dataset Agent (java) passing necessary spawn arguments
        try:
            def _cb_deactivate_on_callback(result):
                self.deactivate()
                return result
            proc = OSProcess(binary, args)
            proc.spawn()
            proc.deferred_exited.addBoth(_cb_deactivate_on_callback)
            # @todo Add a callback which forces this service to terminate if the underlying dataset agent exits (when the deferred returns)
        except ValueError, ex:
            raise RuntimeError("JavaWrapperAgent._spawn_agent(): Received invalid spawn arguments form JavaWrapperAgent.agent_spawn_args" + str(ex))
        except OSError, ex:
            raise RuntimeError("JavaWrapperAgent._spawn_agent(): Failed to spawn the external Dataset Agent.  Error: %s" % (str(ex)))

        # Step 3: Maintain a reference to the OSProcess object for later communication
        self.__agent_phandle = proc
        return True
        
    @defer.inlineCallbacks
    def _terminate_dataset_agent(self):
        '''
        Terminates the underlying dataset by sending it a 'terminate' message and waiting for the OSProcess object's exit callback.  
        '''
        log.debug("Entered _terminate_dataset_agent()")
        returncode = -1
        outlines = None
        errlines = None
        if self.is_agent_active():
            # Step 1: Send a terminate message to the java dataset agent
            log.info("@@@--->>> Sending termination request to underlying Dataset Agent")
            yield self.send(self.agent_binding, self.agent_term_op, None)
            
            # Step 2: Suspend execution until the agent process exits
            result = yield self.__agent_phandle.deferred_exited
            
            returncode = result["exitcode"]
            outlines = result["outlines"]
            errlines = result["errlines"]
            self.__agent_binding = None
            self.__agent_phandle = None
        else:
            errlines = "Dataset Agent has not been spawned, and therefore will not be terminated"
            log.warning(errlines)
        
        result = (returncode, outlines, errlines)
        defer.returnValue(result)


    @defer.inlineCallbacks
    def op_pretty_print(self, content, headers, msg):
        pretty = "Java_Wrapper_Agent Status:" + \
                 "\n--------------------------" + \
                 "\nService State:  " + str(self._get_state()) + \
                 "\nIs Initialized:  " + str(self.is_agent_initialized()) + \
                 "\nIs Activating:  " + str(self.is_agent_activating()) + \
                 "\nIs Active:  " + str(self.is_agent_active()) +\
                 "\nIs Terminated:  " + str(self.is_agent_terminated());
        res = yield self.reply_ok(msg, {'value':pretty}, {})
        defer.returnValue(res)
        
        
    @defer.inlineCallbacks
    def op_do_shutdown(self, content, headers, msg):
        res = yield defer.maybeDeferred(self.shutdown)
        res = yield self.reply_ok(msg, {'value':res}, {})
        defer.returnValue(res)

    
    @defer.inlineCallbacks
    def op_do_deactivate(self, content, headers, msg):
        res = yield defer.maybeDeferred(self.deactivate)
        res = yield self.reply_ok(msg, {'value':res}, {})
        defer.returnValue(res)
    
#    def dec_requires_active(self, func, *args, **kwargs):
#        
#        def _check_active(self, func, *args, **kwargs):
#            status = self._get_state()
#            if state is not BasicStates.S_READY:
#                raise RuntimeError("")
#            else:
#                func(args, kwargs)
#        
#        return _check_active(func, args, kwargs)
#    
#    @dec_requires_active
    @defer.inlineCallbacks
    def op_update_request(self, content, headers, msg):
        '''
        Responds to the Scheduler Service's request for update by having the wrapped Dataset Agent
        perform an update and push the compliant data into the Resource Registry.
        This process involves:
            1) Requesting the datasources current state (known as "context") from the Resource Registry
            2) The update procedure is invoked via an RPC call to the underlying Dataset Agent using
               the acquired "context"
            3) The Dataset Agent performs the update assimilating data into CDM/CF compliant form,
               pushes that data to the Resource Registry, and returns the new DatasetID. 
        '''
        log.info("<<<---@@@ Recieved operation 'update_request'.  Delegating to underlying dataset agent...")
        
        # @todo: this check should be pulled into a decorator so that all ops may process in the same manner.
        # @todo: This method could pass itself as a callback to a deferred where the head in that deferred's
        #        callback chain relies on the activation of the dataset agent
#        status = self._get_state()
#        
#        if state is not BasicStates.S_READY:
#            
#            S_INIT = "INIT"
#    S_READY = "READY"
#    S_ACTIVE = "ACTIVE"
#    S_TERMINATED = "TERMINATED"
#    S_ERROR = "ERROR"
#    
#    
#        if (self.is_agent_terminated()):
#            errmsg = "Dataset agent has been terminated.  Requests cannot be made!"
##            raise RuntimeError(errmsg)
#            log.warning(errmsg)
#            yield self.reply_uncaught_err(msg, errmsg)
#            defer.returnValue(None)
#        elif (self.is_agent_activating()):
#            errmsg = "Dataset agent is not yet active.  Cannot fulfill update request for: " + str(content)
#            log.warning(errmsg)
#            yield self.reply_uncaught_err(msg, errmsg)
#            defer.returnValue(None)
        
        # Step 1: Grab the context for the given dataset ID
        try:
            context = self._get_dataset_context(str(content))
        except KeyError, ex:
            yield self.reply_err(msg, "Could not grab the current context for the dataset with id: " + str(content))
        
        # Step 2: Perform the dataset update as a RPC
        # @todo: this should ultimately be an RPC send which replies when the update is complete, just before data is pushed back
        log.info("@@@--->>> Sending update request to Dataset Agent with context...")
        log.info("..." + str(context))
        (content, headers, msg1) = yield self.rpc_send(self.agent_binding, self.agent_update_op, context, timeout=30)
        
        # @todo: change reply based on response of the RPC send
        # yield self.reply_ok(msg, {"value":"Successfully dispatched update request"}, {})
        res = yield self.reply_ok(msg, {"value":"OOI DatasetID:" + str(content)}, {})
        defer.returnValue(res)
    
    def op_binding_key_callback(self, content, headers, msg):
        '''
        Caches the given binding_key for future communication between the JavaWrapperAgent and its underlying
        Java Dataset Agent.  This method is invoked remotely from the Dataset Agent during its initialization.
        '''
        log.info("<<<---@@@ Incoming callback with binding key message")
        log.debug("...Content:\t" + str(content))
#        log.debug("...Headers\t" + str(headers))
#        log.debug("...Message\t" + str(msg))
        
        self.__agent_binding = str(content)
        if self.__binding_key_deferred is not None and 'result' not in dir(self.__binding_key_deferred):
            # @todo: This will error if callback is called more than once
            self.__binding_key_deferred.callback(self.__agent_binding)
        else:
            # @todo: this should be an error
            # If this callback is invoked manually before this service is spawned this would occur
            pass
        log.info("Accepted Dataset Agent binding key: '%s'" % (self.__agent_binding))
        return True
    
    def op_data_message_callback(self, content, headers, msg):
        """
        Currently UNUSED.  Intented purpose has expired.  This method may be removed in future release.
        """
        # @todo: pass this message up to the eoi ingest service
        #log.info("<<<---@@@ Receiving incoming data stream...")
        #log.info("...Headers\t" + str(headers))
        #(content, headers, msg) = yield self.rpc_send('ingest', content)
        #log.info("Returned OOI DatasetID: " + str(content))
        
        return True

        
    def _get_dataset_context(self, datasetID):
        '''
        Requests the current state of the given datasetID from the Resource Registry and returns that state as
        "context" for future update procedures.

        (For the purposes of elaboration this method simply returns a cached context from a dictionary which has
        been keyed to the given datasetID; communication with the Resource Registry does NOT occur)
        '''
        log.debug("Entered _get_dataset_context(datasetID=%s)" % (datasetID))
        if (datasetID in self.__dataset_context_dict):
            return self.__dataset_context_dict[datasetID]
        else:
            raise KeyError("Invalid datasetID: %s" % (datasetID))

    def is_agent_initialized(self):
        '''
        @return: True if this agent is initialized.  This agent is initialized when it has spawned its underlying
        Dataset Agent via slc_init()
        '''
        return self.agent_phandle != None
    
    def is_agent_active(self):
        '''
        @return: True if this agent is active.  This agent is active when it has spawned its underlying
        Dataset Agent via slc_init() and that agent has responded.  Essentially, a JavaWrapperAgent is active,
        when communication channels between it and the agent it is wrapping, have been established.
        '''
        return self.is_agent_initialized() and self.agent_binding != None
    
    def is_agent_terminated(self):
        return self.is_agent_initialized() and 'result' in dir(self.agent_phandle.deferred_exited)
    
    def is_agent_activating(self):
        '''
        Returns True if this agent is currently activating.  This agent is activating when it has been initialized
        but the underlying dataset agent has not yet responded.
        '''
        return self.is_agent_initialized() and not self.is_agent_active()

    @property
    def agent_phandle(self):
        '''
        @return: an the defered result of the last call to OSProcess.spawn() via self._spawn_dataset_agent() as a
                 reference to the underlying dataset agent, if self._spawn_dataset_agent has been successfully invoked,
                 otherwise None
        '''
        # Initialization done upon successfull call to self._spawn_agent()
        return self.__agent_phandle

    @property
    def agent_binding(self):
        '''
        @return: a string representing the reply-to binding key used to send messages to the underlying dataset agent
                 if the dataset agent has responded to spawning through callback self.on_binding_key_callback(),
                 otherwise None
        '''
        # Initialization done by Dataset agent through callback, self.on_binding_key_callback() 
        return self.__agent_binding

    @property
    def agent_spawn_args(self):
        '''
        @return: a list of arguments which can be passed to a spawning mechanism (such as OSProcess) to spawn this JavaWrapperAgent's
        underlying Dataset Agent.
        '''
        # Lazy-initialize the spawn arguments
        if (self.__agent_spawn_args == None):
            self._init_agent_spawn_args()
        return self.__agent_spawn_args

    @property
    def agent_update_op(self):
        '''
        @return: the name of the RPC operation used by the Java Dataset Agent for performing a dataset update.
        '''
        # Lazy-initialize the update operation name
        if (self.__agent_updt_op == None):
            self._init_agent_update_op()
        return self.__agent_updt_op

    @property
    def agent_term_op(self):
        '''
        @return: the name of the RPC operation used by the Java Dataset Agent for performing self-termination.
        '''
        # Lazy-initialize the terminate operation name
        if (self.__agent_term_op == None):
            self._init_agent_term_op()
        return self.__agent_term_op

    def _init_agent_spawn_args(self):
        '''
        Lazy-initializes self.__agent_spawn_args
        '''
        # @todo: Generate jar_pathname dynamically
        # jar_pathname = "/Users/tlarocque/Development/Java/Workspace_eclipse/EOI_dev/build/TryAgent.jar"   # STAR #
        jar_pathname = "res/apps/eoi_ds_agent/DatasetAgent.jar"   # STAR #
        hostname = self.container.exchange_manager.message_space.connection.hostname
        exchange = self.container.exchange_manager.exchange_space.name
        wrapper = self.get_scoped_name("system", str(self.declare['name']))      # validate that 'system' is the correct scope
        callback = "binding_key_callback"

        # Do not return anything.  Store spawn arguments in __agent_spawn_args
        binary = "java"
        args = ["-jar", jar_pathname, hostname, exchange, wrapper, callback]
        log.debug("Acquired dataset agent spawn arguments:  %s %s" % (binary, " ".join(args)))
        self.__agent_spawn_args = (binary, args)
    
    def _init_agent_update_op(self):
        '''
        Lazy-initializes self.__agent_updt_op
        '''
        # @todo: Acquiring the shutdown op may need to be dynamic in the future
        updt_op= "op_update"
        log.debug("Acquired Dataset Agent update op: %s" % (updt_op))
        self.__agent_updt_op = updt_op

    def _init_agent_term_op(self):
        '''
        Lazy-initializes self.__agent_term_op
        '''
        # @todo: Acquiring the shutdown op may need to be dynamic in the future
        term_op= "op_shutdown"
        log.debug("Acquired Dataset Agent terminate op: %s" % (term_op))
        self.__agent_term_op = term_op
        

class JavaWrapperAgentClient(ServiceClient):
    """
    Test client for direct (RPC) interaction with the JavaWrapperAgent ServiceProcess
    """
    
    def __init__(self, *args, **kwargs):
        kwargs['targetname'] = 'java_wrapper_agent'
        ServiceClient.__init__(self, *args, **kwargs)
    
    @defer.inlineCallbacks
    def rpc_pretty_print(self):
        '''
        Retrieve the state of the JavaWrapperAgent Service
        '''
        yield self._check_init()
        (content, headers, msg) = yield self.rpc_send('pretty_print', None)
        
        log.info("<<<---@@@ Incoming rpc reply...")
        log.info("... Content\t" + str(content))
        log.info("... Headers\t" + str(headers))
        log.info("... Message\t" + str(msg))
        
        result = ""
        if 'value' in content:
            result = content['value']
            print "found value"
        else:
            result = str(content)
            print "couldnt get value"
        defer.returnValue(result)
        
    @defer.inlineCallbacks
    def rpc_do_shutdown(self):
        '''
        Retrieve the state of the JavaWrapperAgent Service
        '''
        yield self._check_init()
        (content, headers, msg) = yield self.rpc_send('do_shutdown', None)
        defer.returnValue(str(content))

    @defer.inlineCallbacks
    def rpc_do_deactivate(self):
        '''
        Retrieve the state of the JavaWrapperAgent Service
        '''
        yield self._check_init()
        (content, headers, msg) = yield self.rpc_send('do_deactivate', None)
        defer.returnValue(str(content))
    
    @defer.inlineCallbacks
    def rpc_request_update(self, datasetId):
        '''
        Simulates an update request to the JavaWrapperAgent as if from the Scheduler Service
        '''
        # Ensure a Process instance exists to send messages FROM...
        #   ...if not, this will spawn a new default instance.
        yield self._check_init()
        
        # Invoke [op_]update_request() on the target service 'dispatcher_svc' via RPC
        log.info("@@@--->>> Sending 'update_request' RPC message to java_wrapper_agent service")
        (content, headers, msg) = yield self.rpc_send('update_request', datasetId)
        
        defer.returnValue(str(content))
        
        
    
# Spawn of the process using the module name
factory = ProcessFactory(JavaWrapperAgent)



'''


#---------------------#
# Copy/paste startup:
#---------------------#
#  :spawn an agent
from ion.agents.eoiagents.java_wrapper_agent import JavaWrapperAgent as jwa
agent = jwa()
agent.spawn()

#  :Setup the client - placeholder for generating update requests
from ion.agents.eoiagents.java_wrapper_agent import JavaWrapperAgentClient as jwac
aclient = jwac()
#  :Send update request for the dataset 'sos_station_st'
aclient.rpc_request_update('sos_station_st')


'''












