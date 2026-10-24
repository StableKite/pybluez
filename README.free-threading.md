# Free-threaded Linux CPython

The Linux extension declares GIL-free import support after porting socket
descriptor/timeout state to atomics, making close transfer descriptor ownership
once, snapshotting poll inputs, and serializing native SDP connection lifetime.
SDP locks are released before reattaching Python thread state or constructing
Python results. HCI filters are mutable bytearrays; immutable bytes inputs are
copied, never modified. Filter predicates return bool and setsockopt accepts
binary buffer values.

As with POSIX sockets, applications must coordinate close/reinitialization with
in-flight I/O and serialize advertisement setup/teardown on a socket. Discovery,
HCI and advertisement calls still require actual Bluetooth hardware/permissions.
No hardware operations are performed by the regression suite; it uses UNIX
socketpairs wrapped through fromfd, closed SDP sessions, and pure filter/opcode
helpers. This change does not claim hardware acceptance.
