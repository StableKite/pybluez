"""Linux-only software tests; no Bluetooth device or SDP server is contacted."""
import concurrent.futures
import fcntl
import os
import socket
import sys
import sysconfig
import threading
import unittest

from bluetooth import _bluetooth as bt


@unittest.skipUnless(sysconfig.get_config_var('Py_GIL_DISABLED'), 'free-threaded CPython required')
class FreeThreadingTest(unittest.TestCase):
    def setUp(self):
        self.assertFalse(sys._is_gil_enabled())
        self.assertNotIn('gil', sys._xoptions)
        self.assertNotIn('PYTHON_GIL', os.environ)

    def tearDown(self):
        bt.setdefaulttimeout(None)
        self.assertFalse(sys._is_gil_enabled())

    def test_binary_filter_mutation_and_immutable_copy(self):
        mutable = bt.hci_filter_new()
        self.assertIsInstance(mutable, bytearray)
        self.assertFalse(bt.hci_filter_test_event(mutable, 4))
        self.assertIs(bt.hci_filter_set_event(mutable, 4), mutable)
        self.assertTrue(bt.hci_filter_test_event(mutable, 4))
        immutable = bytes(mutable)
        original_hash = hash(immutable)
        changed = bt.hci_filter_clear_event(immutable, 4)
        self.assertIsInstance(changed, bytes)
        self.assertFalse(bt.hci_filter_test_event(changed, 4))
        self.assertTrue(bt.hci_filter_test_event(immutable, 4))
        self.assertEqual(hash(immutable), original_hash)
        self.assertEqual(bytes(mutable), immutable)

    def test_concurrent_filter_updates(self):
        shared = bt.hci_filter_new()
        barrier = threading.Barrier(8)
        def worker(index):
            barrier.wait()
            for _ in range(500):
                bt.hci_filter_set_event(shared, index + 1)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(worker, range(8)))
        for index in range(8): self.assertTrue(bt.hci_filter_test_event(shared, index + 1))

    def test_filter_rejects_bad_input_without_native_access(self):
        for value in [b'', bytearray(1), b'\0' * 100]:
            with self.assertRaises(ValueError): bt.hci_filter_set_event(value, 1)
        with self.assertRaises(TypeError): bt.hci_filter_set_event('text', 1)
        with self.assertRaises(TypeError): bt.hci_event_name()
        with self.assertRaises(TypeError): bt.hci_event_name('bad')
        with self.assertRaises(bt.error): bt.hci_event_name(100000)

    def test_socketpair_roundtrip_and_binary_options(self):
        left, right = socket.socketpair()
        wrapped = bt.fromfd(left.fileno(), socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            wrapped.settimeout(0.5)
            payload = bytes(range(256))
            right.sendall(payload)
            self.assertEqual(wrapped.recv(256), payload)
            wrapped.sendall(payload)
            self.assertEqual(right.recv(256), payload)
            wrapped.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            self.assertEqual(wrapped.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE), 1)
            option = bytearray((0).to_bytes(4, sys.byteorder))
            wrapped.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, option)
            self.assertEqual(wrapped.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE), 0)
        finally:
            wrapped.close()
            left.close()
            right.close()

    def test_poll_accepts_descriptor_above_fd_setsize(self):
        # fromfd duplicates into the lowest free slot. Reserve our own low
        # descriptors first so the wrapped descriptor itself is above 1023.
        reserved = [os.open(os.devnull, os.O_RDONLY) for _ in range(1100)]
        left, right = socket.socketpair()
        wrapped = bt.fromfd(left.fileno(), socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self.assertGreaterEqual(wrapped.fileno(), 1100)
            wrapped.settimeout(0.5)
            right.sendall(b'poll')
            self.assertEqual(wrapped.recv(4), b'poll')
        finally:
            wrapped.close()
            left.close()
            right.close()
            for fd in reserved: os.close(fd)

    def test_concurrent_close_never_closes_reused_descriptor(self):
        for _ in range(30):
            left, right = socket.socketpair()
            wrapped = bt.fromfd(left.fileno(), socket.AF_UNIX, socket.SOCK_STREAM)
            barrier = threading.Barrier(4)
            def close_and_open(index):
                barrier.wait()
                wrapped.close()
                return os.open(os.devnull, os.O_RDONLY)
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                sentinels = list(pool.map(close_and_open, range(4)))
            try:
                self.assertEqual(wrapped.fileno(), -1)
                for fd in sentinels: os.fstat(fd)
            finally:
                for fd in sentinels: os.close(fd)
                left.close()
                right.close()

    def test_default_timeout_concurrent_snapshots(self):
        def worker(index):
            for _ in range(1000):
                bt.setdefaulttimeout(None if index % 2 else 0.125)
                self.assertIn(bt.getdefaulttimeout(), [None, 0.125])
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(worker, range(4)))

    def test_closed_sdp_session_operations_are_safe(self):
        session = bt.SDPSession()
        def worker(index):
            for _ in range(200):
                session.close()
                self.assertIn('unconnected', repr(session))
                with self.assertRaises(bt.error): session.fileno()
                with self.assertRaises(bt.error): session.search('1101')
                with self.assertRaises(bt.error): session.browse()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(worker, range(4)))
        # Parsing fails before the C library is allowed to connect anywhere.
        with self.assertRaises(TypeError): session.connect(target=object())
        with self.assertRaises(ValueError): session.connect(target='invalid-address')


if __name__ == '__main__':
    unittest.main()
