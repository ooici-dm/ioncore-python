#!/usr/bin/env python

"""
@file ion/integration/app_integration_service.py
@author David Everett
@brief Core service frontend for Application Integration Services 
"""

import sys
import traceback

import ion.util.ionlog
log = ion.util.ionlog.getLogger(__name__)
from twisted.internet import defer

from ion.core.object import object_utils
from ion.core.process.process import ProcessFactory
from ion.core.process.service_process import ServiceProcess, ServiceClient
from ion.services.coi.resource_registry_beta.resource_client import ResourceClient, ResourceInstance
from ion.core.messaging.message_client import MessageClient

from ion.integration.ais.loadDummyDataset import LoadDummyDataset

# import GPB type identifiers for AIS
from ion.integration.ais.ais_object_identifiers import AIS_REQUEST_MSG_TYPE, AIS_RESPONSE_MSG_TYPE
from ion.integration.ais.ais_object_identifiers import UPDATE_USER_EMAIL_TYPE, UPDATE_USER_DISPATCH_QUEUE_TYPE
from ion.integration.ais.ais_object_identifiers import FIND_DATA_RESOURCES_REQ_MSG_TYPE

# import working classes for AIS
from ion.integration.ais.findDataResources.findDataResources import FindDataResources
from ion.integration.ais.getDataResourceDetail.getDataResourceDetail import GetDataResourceDetail
from ion.integration.ais.createDownloadURL.createDownloadURL import CreateDownloadURL
from ion.integration.ais.RegisterUser.RegisterUser import RegisterUser

addresslink_type = object_utils.create_type_identifier(object_id=20003, version=1)
person_type = object_utils.create_type_identifier(object_id=20001, version=1)


class AppIntegrationService(ServiceProcess):
    """
    Service to provide clients access to backend data
    """
    # Declaration of service
    declare = ServiceProcess.service_declare(name='app_integration',
                                             version='0.1.0',
                                             dependencies=[])

    def __init__(self, *args, **kwargs):

        ServiceProcess.__init__(self, *args, **kwargs)

        # Test for loadDummyData argument
        self.loadDummyData = self.spawn_args.get('loadDummyData', False)
        
        self.rc = ResourceClient(proc = self)
        self.mc = MessageClient(proc = self)
    
        log.debug('AppIntegrationService.__init__(): loadDummyData == %s' % str(self.loadDummyData))

    def slc_init(self):
        pass

    @defer.inlineCallbacks
    def op_findDataResources(self, content, headers, msg):
        """
        @brief Find data resources associated with given userID
        @param GPB containing OOID user ID, spatial, and temporal bounds.
        @retval GPB with list of resource IDs.
        """
        log.debug('op_findDataResources service method.')

        log.debug('op_findDataResources calling LoadDummyDataset!!!.')
        loader = LoadDummyDataset()
        self.dsID = yield loader.loadDummyDataset(self.rc)
        log.debug('op_findDataResources LoadDummyDataset!!! returned %s' % str(self.dsID))

        try:

            # Instantiate the worker class
            worker = FindDataResources(self)

            # if test case, do this:
            worker.setTestDatasetID(self.dsID)
            
            returnValue = yield worker.findDataResources(content)
            #log.debug('worker returned: ' + returnValue)
            yield self.reply_ok(msg, returnValue)
        except KeyError:
            estr = 'Missing information in message!'
            log.exception(estr)
            yield self.reply_err(msg, estr)

        return

    @defer.inlineCallbacks
    def op_getDataResourceDetail(self, content, headers, msg):
        """
        @brief Get detailed metadata for a given resource ID.
        @param GPB containing resource ID.
        @retval GPB containing detailed metadata.
        """
        log.info('op_getDataResourceDetail: '+str(content))
        try:
            
            worker = GetDataResourceDetail(self)
            
            yield self.reply_ok(msg, {'value' : 'value'})
        except KeyError:
            estr = 'Missing information in message!'
            log.exception(estr)
            yield self.reply_err(msg, estr)

        return

    @defer.inlineCallbacks
    def op_createDownloadURL(self, content, headers, msg):
        """
        @brief Create download URL for given resource ID.
        @param GPB containing resource ID.
        @retval GPB containing download URL.
        """
        log.info('op_createDownloadURL: '+str(content))
        try:
            worker = CreateDownloadURL(self)
            yield self.reply_ok(msg, {'value' : 'http://a.download.url.edu'})   
        except KeyError:
            estr = 'Missing information in message!'
            log.exception(estr)
            yield self.reply_err(msg, estr)
            return
        
        return

    @defer.inlineCallbacks
    def op_registerUser(self, content, headers, msg):
        log.debug('op_registerUser: \n'+str(content))
        worker = RegisterUser(self)
        log.debug('op_registerUser: calling worker')
        response = yield worker.registerUser(content);
        yield self.reply_ok(msg, response)
        
    @defer.inlineCallbacks
    def op_updateUserEmail(self, content, headers, msg):
        log.debug('op_updateUserEmail: \n'+str(content))
        worker = RegisterUser(self)
        log.debug('op_updateUserEmail: calling worker')
        response = yield worker.updateUserEmail(content);
        yield self.reply_ok(msg, response)
        
    @defer.inlineCallbacks
    def op_updateUserDispatcherQueue(self, content, headers, msg):
        log.debug('op_updateUserDispatcherQueue: \n'+str(content))
        worker = RegisterUser(self)
        log.debug('op_updateUserDispatcherQueue: calling worker')
        response = yield worker.updateUserDispatcherQueue(content);
        yield self.reply_ok(msg, response)
                         

class AppIntegrationServiceClient(ServiceClient):
    """
    This is a service client for AppIntegrationServices.
    """
    def __init__(self, proc=None, **kwargs):
        if not 'targetname' in kwargs:
            kwargs['targetname'] = "app_integration"
        ServiceClient.__init__(self, proc, **kwargs)
        
    @defer.inlineCallbacks
    def findDataResources(self, msg):
        yield self._check_init()
        log.debug("AppIntegrationServiceClient: findDataResources(): sending msg to AppIntegrationService.")
        (content, headers, payload) = yield self.rpc_send('findDataResources', msg)
        log.info('Service reply: ' + str(content))
        defer.returnValue(content)
        
    @defer.inlineCallbacks
    def getDataResourceDetail(self, msg):
        yield self._check_init()
        (content, headers, payload) = yield self.rpc_send('getDataResourceDetail', msg)
        log.info('Service reply: ' + str(content))
        defer.returnValue(content)
        
    @defer.inlineCallbacks
    def createDownloadURL(self, msg):
        yield self._check_init()
        (content, headers, payload) = yield self.rpc_send('createDownloadURL', msg)
        log.info('Service reply: ' + str(content))
        defer.returnValue(content)
 
    @defer.inlineCallbacks
    def registerUser(self, message):
        yield self._check_init()
        log.debug("AIS_client.registerUser: sending following message to registerUser:\n%s" % str(message))
        (content, headers, payload) = yield self.rpc_send('registerUser', message)
        log.debug('AIS_client.registerUser: IR Service reply:\n' + str(content))
        defer.returnValue(content)
        
    @defer.inlineCallbacks
    def updateUserEmail(self, message):
        yield self._check_init()
        log.debug("AIS_client.updateUserEmail: sending following message to registerUser:\n%s" % str(message))
        (content, headers, payload) = yield self.rpc_send('updateUserEmail', message)
        log.debug('AIS_client.registerUser: IR Service reply:\n' + str(content))
        defer.returnValue(content)
        
    @defer.inlineCallbacks
    def updateUserDispatcherQueue(self, message):
        yield self._check_init()
        log.debug("AIS_client.updateUserDispatcherQueue: sending following message to registerUser:\n%s" % str(message))
        (content, headers, payload) = yield self.rpc_send('updateUserDispatcherQueue', message)
        log.debug('AIS_client.registerUser: IR Service reply:\n' + str(content))
        defer.returnValue(content)
        

# Spawn of the process using the module name
factory = ProcessFactory(AppIntegrationService)
