"""Check actual installed sources and their native module, without suppressions."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path


def main() -> None:
    repo = Path(sys.argv[1]).resolve(strict=True)
    assert sys.version_info[:2] == (3, 15)
    assert sysconfig.get_config_var('Py_GIL_DISABLED') == 1
    assert sys.flags.gil is None and not sys._is_gil_enabled()
    assert 'PYTHON_GIL' not in os.environ and 'gil' not in sys._xoptions
    import bluetooth

    package = Path(bluetooth.__file__).resolve().parent
    assert package != repo / 'bluetooth', 'installation must not be shadowed by checkout'
    assert bluetooth.__version__ == importlib.metadata.version('PyBluez')
    files = ['btcommon.py', 'msbt.py', '_msbt.pyi', 'py.typed', '__init__.py']
    hashes: dict[str, str] = {}
    for name in files:
        actual = (package / name).read_bytes().replace(b'\r\n', b'\n')
        assert actual == (repo / 'bluetooth' / name).read_bytes().replace(b'\r\n', b'\n'), name
        hashes[name] = hashlib.sha256(actual).hexdigest()

    with tempfile.TemporaryDirectory(prefix='pybluez-installed-typing-') as temporary:
        root = Path(temporary)
        copied = root / 'bluetooth'
        copied.mkdir()
        for name in files:
            shutil.copyfile(package / name, copied / name)
        shutil.copyfile(repo / '_binary_wheel_backend.py', root / '_binary_wheel_backend.py')
        configurations: list[tuple[str, list[str]]] = [('All', ['_binary_wheel_backend.py', 'bluetooth/btcommon.py'])]
        if sys.platform == 'win32':
            from bluetooth import _msbt

            native = Path(_msbt.__file__).resolve(strict=True)
            assert native.suffix == '.pyd' and native.parent == package
            shutil.copyfile(native, copied / native.name)
            configurations.append(('Windows', ['bluetooth/msbt.py', 'bluetooth/btcommon.py', 'bluetooth/_msbt.pyi']))
        else:
            from bluetooth import _bluetooth

            native = Path(_bluetooth.__file__).resolve(strict=True)
            assert native.suffix == '.so' and native.parent == package
        for platform, include in configurations:
            config = root / ('pyright-' + platform + '.json')
            config.write_text(json.dumps({'include': include, 'typeCheckingMode': 'strict',
                                          'pythonVersion': '3.15', 'pythonPlatform': platform}), 'utf8')
            subprocess.run([sys.executable, '-m', 'pyright', '--project', str(config),
                            '--pythonpath', sys.executable, '--outputjson'], check=True)
    assert not sys._is_gil_enabled()
    print(json.dumps({'installed_package': str(package), 'native': str(native),
                      'native_sha256': hashlib.sha256(native.read_bytes()).hexdigest(),
                      'installed_source_hashes': hashes, 'natural_gil_off': True}))


if __name__ == '__main__':
    main()
