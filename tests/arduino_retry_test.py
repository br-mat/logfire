"""Build the real client with host stubs; no board or Arduino SDK required.

python tests/arduino_retry_test.py [--cxx g++] [--source path/to/source/tree]
For Zig: --cxx path/to/zig --compiler-arg c++
"""
import argparse
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx', default='g++')
    parser.add_argument('--compiler-arg', action='append', default=[])
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    tests = Path(__file__).resolve().parent
    library = args.source.resolve() / 'arduino' / 'LogFire'
    with tempfile.TemporaryDirectory(prefix='logfire-host-test-') as temporary:
        for platform in ('ESP32', 'ESP8266'):
            binary = Path(temporary) / (platform + '.exe')
            command = [args.cxx, *args.compiler_arg, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                       '-D' + platform, '-I' + str(tests / 'arduino_stubs'), '-I' + str(library),
                       str(tests / 'arduino_retry_test.cpp'), str(library / 'LogFire.cpp'),
                       '-o', str(binary)]
            print('Building host test for ' + platform, flush=True)
            subprocess.run(command, check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    main()
