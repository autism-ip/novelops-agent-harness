"""Raw Python function entry coverage, named definitions and lambdas included."""
from functools import cache
import inspect
import json
from pathlib import Path
import sys
import threading
from types import CodeType

ROOT = (Path.cwd() / 'app').resolve()
functions = {}
called = set()
previous = None
previous_threads = None


@cache
def identity(code):
    # Source position distinguishes multiple lambdas on the same line.
    position = next((value for value in code.co_positions()
                     if value[2] is not None and value[3] is not None and value[3] > value[2]), None)
    return (str(Path(code.co_filename).resolve()), code.co_qualname, code.co_firstlineno, position)


def catalog(code):
    if code.co_flags & inspect.CO_NEWLOCALS and (not code.co_name.startswith('<') or code.co_name == '<lambda>'):
        functions[identity(code)] = {'file': str(Path(code.co_filename).relative_to(ROOT)),
                                   'name': code.co_qualname, 'line': code.co_firstlineno,
                                   'source_position': next((value for value in code.co_positions()
                                       if value[2] is not None and value[3] is not None and value[3] > value[2]), None)}
    for value in code.co_consts:
        if isinstance(value, CodeType):
            catalog(value)


def record(frame, event, arg):
    if event == 'call' and frame.f_code.co_filename.startswith(str(ROOT) + '/'):
        called.add(identity(frame.f_code))


def pytest_sessionstart(session):
    global previous, previous_threads
    for path in sorted(ROOT.rglob('*.py')):
        catalog(compile(path.read_text(), str(path), 'exec', dont_inherit=True))
    previous = sys.getprofile()
    previous_threads = threading.getprofile()
    sys.setprofile(record)
    threading.setprofile(record)


def pytest_sessionfinish(session, exitstatus):
    sys.setprofile(previous)
    threading.setprofile(previous_threads)
    missing = [value for key, value in functions.items() if key not in called]
    output = {'metric': 'raw Python function entry coverage: all named definitions and lambdas',
              'total': len(functions), 'entered': len(functions) - len(missing),
              'percent': 100 * (len(functions) - len(missing)) / len(functions),
              'lambdas_total': sum(value['name'].endswith('<lambda>') for value in functions.values()),
              'lambdas_entered': sum(value['name'].endswith('<lambda>') for key, value in functions.items() if key in called),
              'unmatched_calls': sorted(str(key) for key in called if key not in functions),
              'pytest_exitstatus': exitstatus, 'missing': missing,
              'definition_scope': 'every app Python source including unimported modules and Protocol declarations; module/class bodies and compiler-generated comprehensions are not source functions'}
    Path('coverage-functions.json').write_text(json.dumps(output, indent=2))
