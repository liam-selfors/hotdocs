# Library

One module file, `test_probe.py`, never a package.

```
probe(test_source: str, criterion_bundle, module_name: str | list[str], *,
      timeout: float = 60.0, interpreter: str | None = None) -> ProbeReport
GATE_VERSION: str  # "test-probe@1.3.0"
```

`interpreter` is the Python that runs the component's tests, the
`interpreter` the `python` adapter's `provision` reports
(`specs/architecture/asset-kinds.md`); `None` means `sys.executable`.

`criterion_bundle` is a `CriterionBundle` or a mapping with its keys
(`spec-bundle-assembler`'s `interface/data/CriterionBundle.md`); only
`dependency_interfaces` is read, a dict from component id to that
component's `interface/` text, and a missing key means `{}`.
`module_name` is the importable name of the component's module, such as
`slugify`, or a list of such names, such as a capability scenario's
realizing modules `["slugify", "url_tools"]`; a string is read as a
one-name list, and every name below means each name of that list.

## How a probe runs

The checks run in this order, each giving only these kinds:

1. syntax (`R-PROBE-001`): `syntax_error`; on one, nothing else runs;
2. pyflakes (`R-PROBE-002`): `undefined_name` only; every other pyflakes
   message, such as an unused import, gives no finding of any kind;
3. imports (`R-PROBE-003`): `unknown_import`;
4. fake arity (`R-PROBE-004`): `fake_signature_mismatch`;
5. the stub run (`R-PROBE-005`): `collection_error`, `test_bug`,
   `probe_timeout`, `vacuous`.

The stub run happens only when checks 1 to 4 found no `error`; otherwise
`tests_run` and `tests_reached` are `0`. An import resolves when its
first dotted part is a name of `module_name` (the stub answers every name), a
standard-library module, or anything `importlib.util.find_spec` finds,
such as `pytest`: in the probing process when `interpreter` is `None`,
else in one subprocess of `interpreter`, the current environment kept,
that checks every remaining part. A `testcase` **reached** the code
under test exactly when its `failure` message contains
`HotdocsProbeStubReached`; it gives no finding. A failure of any other
type that is not a `test_bug` gives no finding either. A timed-out run
gives exactly one finding, `probe_timeout`: its report is not read. A file
pytest cannot collect appears in `report.xml` as a `testcase` with an
`error` whose `message` is `collection failure`; it is no test, and gives
exactly one finding, `collection_error`, with `tests_run` `0`. The
one temporary directory is made by `tempfile.mkdtemp()` with no
arguments.

## The stub run

The stub run executes, in a fresh temporary directory holding only the
test file (named `test_probe_target.py`), one stub module per name
of `module_name` (`<name>.py`, each with the source below) and the
asset plugin `hotdocs_probe_assets.py` (`R-PROBE-007`):

```
<interpreter> -m pytest -q -p no:cacheprovider --noconftest
    -p hotdocs_probe_assets --junitxml=<tmp>/report.xml test_probe_target.py
```

with `PYTHONPATH` set to that directory alone and the current directory
set to it. Each `testcase` element of `report.xml` is one test; a
`failure` or `error` child carries a `message` attribute, which for a
failure begins with the exception's type name, possibly module-qualified
(`NameError: ...`, `slugify.HotdocsProbeStubReached: ...`).

The stub module's source is exactly:

```python
class HotdocsProbeStubReached(BaseException):
    pass


class _Stub:
    def __init__(self, name):
        self._name = name

    def __call__(self, *args, **kwargs):
        raise HotdocsProbeStubReached(self._name)

    def __getattr__(self, name):
        return _Stub(self._name + "." + name)


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    return _Stub(name)
```

The asset plugin's source is exactly:

```python
import pytest


class HotdocsProbeStubReached(BaseException):
    pass


def _reached(*args, **kwargs):
    raise HotdocsProbeStubReached("asset_runner")


@pytest.fixture
def asset_runner():
    def runner(path):
        return _reached

    return runner
```

Test fixtures: a test passes `test_source` as a string literal and a
plain dict as `criterion_bundle`, such as
`{"dependency_interfaces": {"comp-bar": "bar_get(key: str) -> str"}}`.

Implements: `specs/architecture/asset-kinds.md`
