#!/usr/bin/env python

"""
@file ion/core/test/test_baseprocess.py
@author Michael Meisinger
@brief test case for process base class
"""

import os
import sha

from twisted.trial import unittest
from twisted.internet import defer

import ion.util.ionlog
log = ion.util.ionlog.getLogger(__name__)

from ion.core import ioninit
from ion.core.base_process import BaseProcess, ProcessDesc, ProcessFactory
from ion.core.cc.container import Container
from ion.core.messaging.receiver import Receiver, WorkerReceiver
from ion.core.id import Id
from ion.test.iontest import IonTestCase, ReceiverProcess
import ion.util.procutils as pu

class BaseProcessTest(IonTestCase):
    """
    Tests the process base class, the root class of all message based interaction.
    """

    @defer.inlineCallbacks
    def setUp(self):
        yield self._start_container()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self._stop_container()

    @defer.inlineCallbacks
    def test_process_basics(self):
        p1 = BaseProcess()
        self.assertTrue(p1.id)
        self.assertIsInstance(p1.id, Id)
        self.assertTrue(p1.receiver)
        self.assertFalse(p1.receiver.consumer)
        self.assertEquals(p1.receiver.consumer, None)
        self.assertEquals(p1._get_state(), "INIT")

        self.assertEquals(p1.spawn_args, {})
        self.assertTrue(p1.proc_init_time)
        self.assertTrue(p1.proc_name)
        self.assertTrue(p1.sys_name)
        self.assertTrue(p1.proc_group)
        self.assertTrue(p1.backend_id)
        self.assertTrue(p1.backend_receiver)
        self.assertEquals(len(p1.receivers), 2)
        self.assertEquals(p1.conversations, {})
        self.assertEquals(p1.child_procs, [])

        pid1 = yield p1.spawn()
        self.assertEquals(pid1, p1.id)
        self.assertEquals(p1._get_state(), "ACTIVE")

        procid = Id('local','container')
        args = {'proc-id':procid.full}
        p2 = BaseProcess(spawnargs=args)
        self.assertEquals(p2.id, procid)
        yield p2.initialize()
        self.assertEquals(p2._get_state(), "READY")
        yield p2.activate()
        self.assertEquals(p2._get_state(), "ACTIVE")

        args = {'arg1':'value1','arg2':{}}
        p3 = BaseProcess(None, args)
        self.assertEquals(p3.spawn_args, args)

    @defer.inlineCallbacks
    def test_process(self):
        # Also test the ReceiverProcess helper class
        print "p1"
        p1 = ReceiverProcess(spawnargs={'proc-name':'p1'})
        pid1 = yield p1.spawn()

        print "others"
        processes = [
            {'name':'echo','module':'ion.core.test.test_baseprocess','class':'EchoProcess'},
        ]
        sup = yield self._spawn_processes(processes, sup=p1)
        assert sup == p1

        pid2 = p1.get_child_id('echo')
        proc2 = self._get_procinstance(pid2)

        yield p1.send(pid2, 'echo','content123')
        log.info('Sent echo message')

        msg = yield p1.await_message()
        log.info('Received echo message')

        self.assertEquals(msg.payload['op'], 'result')
        self.assertEquals(msg.payload['content']['value'], 'content123')

        yield sup.terminate()
        self.assertEquals(sup._get_state(), "TERMINATED")
        self.assertEquals(proc2._get_state(), "TERMINATED")

    @defer.inlineCallbacks
    def test_child_processes(self):
        p1 = BaseProcess()
        pid1 = yield p1.spawn()

        child = ProcessDesc(name='echo', module='ion.core.test.test_baseprocess')
        pid2 = yield p1.spawn_child(child)

        (cont,hdrs,msg) = yield p1.rpc_send(pid2,'echo','content123')
        self.assertEquals(cont['value'], 'content123')

        yield p1.terminate()
        self.assertEquals(p1._get_state(), "TERMINATED")

    @defer.inlineCallbacks
    def test_spawn_child(self):
        child1 = ProcessDesc(name='echo', module='ion.core.test.test_baseprocess')
        self.assertEquals(child1._get_state(),'INIT')

        pid1 = yield self.test_sup.spawn_child(child1)
        self.assertEquals(child1._get_state(),'ACTIVE')
        proc = self._get_procinstance(pid1)
        self.assertEquals(str(proc.__class__),"<class 'ion.core.test.test_baseprocess.EchoProcess'>")
        self.assertEquals(pid1, proc.id)
        log.info('Process 1 spawned and initd correctly')

        (cont,hdrs,msg) = yield self.test_sup.rpc_send(pid1,'echo','content123')
        self.assertEquals(cont['value'], 'content123')
        log.info('Process 1 responsive correctly')

        # The following tests the process attaching a second receiver
        msgName = pu.create_guid()
        extraRec = WorkerReceiver(label=proc.proc_name, name=msgName, handler=proc.receive)
        extraid = yield extraRec.attach()
        log.info('Created new receiver %s' % (msgName))

        (cont,hdrs,msg) = yield self.test_sup.rpc_send(msgName,'echo','content456')
        self.assertEquals(cont['value'], 'content456')
        log.info('Process 1 responsive correctly on second receiver')


    @defer.inlineCallbacks
    def test_message_before_activate(self):
        p1 = ReceiverProcess(spawnargs={'proc-name':'p1'})
        pid1 = yield p1.spawn()
        proc1 = self._get_procinstance(pid1)

        child2 = ProcessDesc(name='echo', module='ion.core.test.test_baseprocess')
        pid2 = yield self.test_sup.spawn_child(child2, activate=False)
        self.assertEquals(child2._get_state(), 'READY')
        proc2 = self._get_procinstance(pid2)
        self.assertEquals(proc2._get_state(), 'READY')

        # The following tests that a message to a not yet activated process
        # is queued and not lost, but not delivered
        yield proc1.send(pid2,'echo','content123')
        self.assertEquals(proc1.inbox_count, 0)
        yield pu.asleep(1)
        self.assertEquals(proc1.inbox_count, 0)

        yield child2.activate()
        yield pu.asleep(1)
        self.assertEquals(child2._get_state(), 'ACTIVE')
        self.assertEquals(proc1.inbox_count, 1)

        (cont,hdrs,msg) = yield self.test_sup.rpc_send(pid2,'echo','content123')
        self.assertEquals(cont['value'], 'content123')
        log.info('Process 1 responsive correctly after init')

    @defer.inlineCallbacks
    def test_error_in_op(self):
        child1 = ProcessDesc(name='echo', module='ion.core.test.test_baseprocess')
        pid1 = yield self.test_sup.spawn_child(child1)

        (cont,hdrs,msg) = yield self.test_sup.rpc_send(pid1,'echofail2','content123')
        self.assertEquals(hdrs['status'], 'ERROR')
        log.info('Process 1 responded to error correctly')

    @defer.inlineCallbacks
    def test_send_byte_string(self):
        """
        @brief Test that any arbitrary byte string can be sent through the
        ion CC stack. Use a 20 byte sha1 digest as test string.
        """
        p1 = ReceiverProcess()
        pid1 = yield p1.spawn()

        processes = [
            {'name':'echo','module':'ion.core.test.test_baseprocess','class':'EchoProcess'},
        ]
        sup = yield self._spawn_processes(processes, sup=p1)

        pid2 = p1.get_child_id('echo')

        byte_string = sha.sha('test').digest()

        yield p1.send(pid2, 'echo', byte_string)
        log.info('Sent byte-string')

        msg = yield p1.await_message()
        log.info('Received byte-string')
        self.assertEquals(msg.payload['content']['value'], byte_string)

        yield sup.shutdown()

    @defer.inlineCallbacks
    def test_shutdown(self):
        processes = [
            {'name':'echo1','module':'ion.core.test.test_baseprocess','class':'EchoProcess'},
            {'name':'echo2','module':'ion.core.test.test_baseprocess','class':'EchoProcess'},
            {'name':'echo3','module':'ion.core.test.test_baseprocess','class':'EchoProcess'},
        ]
        sup = yield self._spawn_processes(processes)

        yield self._shutdown_processes()


class EchoProcess(BaseProcess):

    @defer.inlineCallbacks
    def plc_noinit(self):
        log.info("In init: "+self.proc_state)
        yield pu.asleep(1)
        log.info("Leaving init: "+self.proc_state)

    @defer.inlineCallbacks
    def op_echo(self, content, headers, msg):
        log.info("Message received: "+str(content))
        yield self.reply_ok(msg, content)

    @defer.inlineCallbacks
    def op_echofail1(self, content, headers, msg):
        log.info("Message received: "+str(content))
        ex = RuntimeError("I'm supposed to fail")
        yield self.reply_err(msg, ex)

    @defer.inlineCallbacks
    def op_echofail2(self, content, headers, msg):
        log.info("Message received: "+str(content))
        raise RuntimeError("I'm supposed to fail")
        yield self.reply_ok(msg, content)

# Spawn of the process using the module name
factory = ProcessFactory(EchoProcess)
