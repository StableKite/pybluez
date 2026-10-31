# Experimental CPython 3.15t dependency wheels

Ordinary pip from the fork default branch selects exact, SHA256-checked original
wheels on Windows x64 or Linux x86_64/glibc 2.39+. No consumer build flags,
compiler SDK configuration or GIL overrides are required for these profiles.
Windows links only Windows system Winsock/Bluetooth DLLs. Linux is built from
the retained BlueZ source and repaired using standard auditwheel policy, including
its actual libbluetooth dependency. Wheels are never obtained by retagging an
older Python ABI.

The source/metadata guard compares the complete source tree to its recorded
commit, apart from explicitly hashed delivery files. Changed source, another
ABI/platform, explicit configuration settings or compiler overrides retain the
original setuptools source build and its normal development-library prerequisites.
Source guard text hashes normalize Git CRLF/LF checkout conversion only.

The Windows backend has a substantive free-threading ownership/synchronization
port. The existing Linux native implementation is preserved. See
README.free-threading.md for exact concurrency contracts and hardware limits.
The five native wheel CI targets use CPython 3.15t and actual applicable software
tests. A separate two-OS job exercises ordinary default-branch Git installation,
strict checking of installed Python sources, all native software tests and
pip check. CI results must be inspected before claiming CI acceptance.

These are engineering dependency artifacts, not a StableKite product release.
