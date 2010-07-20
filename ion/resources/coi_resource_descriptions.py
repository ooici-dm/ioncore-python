#!/usr/bin/env python

import inspect
import logging
logging = logging.getLogger(__name__)
from ion.data.dataobject import DataObject, Resource, TypedAttribute, LCState, LCStates, ResourceReference, InformationResource, StatefulResource

"""
Container object are used as self describing sendable objects
"""
class SetResourceLCStateContainer(DataObject):
    """
    @ Brief a message object used to set state and 
    """
    # Beware of using a class object as a typed attribute!
    lcstate = TypedAttribute(LCState, default=None)
    reference = TypedAttribute(ResourceReference)


class ResourceListContainer(DataObject):
    """
    @ Brief a message object used to pass a list of resource description objects
    """
    resources = TypedAttribute(list, default=None)


class FindResourceContainer(DataObject):
    """
    @ Brief a message object used to find resource description in a registry
    @ note string_comparison_method can be 'regex' or '=='
    """
    description = TypedAttribute(Resource, default=None)
    regex = TypedAttribute(bool, default=True)
    ignore_defaults = TypedAttribute(bool, default=True)
    attnames = TypedAttribute(list)
    
    
"""
Resource Description object are used in the OOICI Registries
"""

"""
Define properties of resource types
"""
ResourceTypes = ['generic',
                'unassigned',
                'information',
                'service',
                'stateful'
                ]

class ResourceType(object):
    """
    @Brief Class to control the possible states based on the LCStateNames list
    """

    def __init__(self, type='unassigned'):
        assert type in ResourceTypes
        self._type = type

    def __repr__(self):
        return self._type

    def __eq__(self, other):
        assert isinstance(other, ResourceType)
        return str(self) == str(other)

OOIResourceTypes = dict([('ResourceType', ResourceType)] + [(name, ResourceType(name)) for name in ResourceTypes])

class TypesContainer(dict):
    """
    Class used to set the the possible types
    """

    def __init__(self, d):
        dict.__init__(self, d)
        for k, v in d.items():
            setattr(self, k, v)

OOIResourceTypes = TypesContainer(OOIResourceTypes)

# Classes that do not inherit from DataObject must be explicitly added to the data
# Object Dictionary to be decoded!
DataObject._types.update(OOIResourceTypes)

class AttributeDescription(DataObject):
    name = TypedAttribute(str)
    type = TypedAttribute(str)
    #default = TypedAttribute(str) Ignore defaults for now - can't get at it!


class ResourceDescription(InformationResource):
    """
    Resource Descriptions are stored in the resource registry.
    They describe resources, resource types and resource attributes
    """
    type = TypedAttribute(ResourceType)
    atts = TypedAttribute(list)
    inherits_from = TypedAttribute(ResourceReference)
    description = TypedAttribute(str)

    
    def describe_resource(self,resource):
        """
        @Brief Extract metadata from a resource object to store in the resource
        registry
        @Param resource is an instance of a class which inherits from Resource
        """
        assert isinstance(resource, Resource)
        
        self.name = resource.__class__.__name__
        
        if isinstance(resource, InformationResource):
            self.type = OOIResourceTypes.information
        elif isinstance(resource, StatefulResource):
            self.type = OOIResourceTypes.stateful
        else:
            self.type = OOIResourceTypes.unassigned
        
        self.description = inspect.getdoc(resource)
            
        for att in resource.attributes:
            attdesc = AttributeDescription()
            attdesc.name = att
            attdesc.type = str(type(getattr(resource, att)))
            self.atts.append(attdesc)    
            
    
class ResourceInstance(InformationResource):
    """
    Resource Instances are stored in the resource registry.
    They describe instances of a resource type
    """
    instance_description = TypedAttribute(ResourceReference)
    instance_owner = TypedAttribute(ResourceReference)
    instance = TypedAttribute(ResourceReference)
    
class IdentityResource(InformationResource):
    """
    Identity Resources are stored in the identity registry
    Identity Resources describe the identity of human in the OOICI...
    """
    # These are the fields that we get from the Trust Provider
    ooi_id = TypedAttribute(str)
    common_name = TypedAttribute(str)
    country = TypedAttribute(str)
    trust_provider = TypedAttribute(str) # this is the trust provider /O (Organization field)
    domain_component = TypedAttribute(str)
    certificate = TypedAttribute(str)
    rsa_private_key = TypedAttribute(str)
    expiration_date = TypedAttribute(str)
    # These are the fields we prompt the user for during registration
    first_name = TypedAttribute(str)
    last_name = TypedAttribute(str)
    phone = TypedAttribute(str)
    fax = TypedAttribute(str)
    email = TypedAttribute(str)
    organization = TypedAttribute(str)
    department = TypedAttribute(str)
    title = TypedAttribute(str)


class ServiceMethodInterface(DataObject):
    description = TypedAttribute(str)
    arguments = TypedAttribute(str)

class ServiceDescription(InformationResource):
    """
    Resource Descriptions are stored in the resource registry.
    They describe resources, resource types and resource attributes
    """
    interface = TypedAttribute(list)
    module = TypedAttribute(str)
    version = TypedAttribute(str)
    #spawnargs = TypedAttribute(dict,{})
    description = TypedAttribute(str)

    
    def describe_service(self,svc):
        
        assert issubclass(svc, BaseService)
        
        self.name = svc.declare['name']
        self.version = svc.declare['version']
        
        self.class_name = svc.__name__
        self.module = svc.__module__
                
        self.description = inspect.getdoc(svc)      
            
        for attr in inspect.classify_class_attrs(svc):
            if attr.kind == 'method':
            
                opdesc = ServiceMethodInterface()
                opdesc.name = attr.name
                opdesc.description = inspect.getdoc(attr.object)
                #Can't seem to get the arguments in any meaningful way...
                #opdesc.arguments = inspect.getargspec(attr.object)
                
                self.interface.append(attdesc)    
            
    
class ServiceInstance(InformationResource):
    """
    Resource Instances are stored in the resource registry.
    They describe instances of a resource type
    """
    description = TypedAttribute(ResourceReference)
    #owner = TypedAttribute(ResourceReference)
    spawnargs = TypedAttribute(str)
    type = TypedAttribute(str)
    exchange_name = TypedAttribute(str)
    
    def describe_instance(self,svc_inst):
        """
        """
        self.name=svc_inst.svc_name
        self.description = inspect.getdoc(svc_inst)
        self.exchange_name = svc_inst.svc_reciever


