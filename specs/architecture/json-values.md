---
id: arch-json-values
title: Converting Values to JSON
status: draft
owners: [pipeline-team]
depends_on: []
---

# Converting Values to JSON

## Purpose

One conversion, shared by every component that writes another
component's result as JSON (a manifest, an attempt record, a
`--format=json` print), so that no value a test, a model or a scanner
can produce makes the write fail (`D318`).

## Rules

`to_json(value)` returns a value `json.dumps` accepts, by the first of
these rules that applies, applied recursively:

1. `None`, a `bool`, an `int` or a `str` is itself; a `float` is itself
   when finite, else its `repr` (`"nan"`, `"inf"`, `"-inf"`).
2. A `dict` (any `collections.abc.Mapping`) is an object: each key that
   is a `str` is kept, any other key becomes `str(key)`, and each value
   is converted.
3. A `list` or `tuple` is an array of its converted items, in order.
4. A `set` or `frozenset` is an array of its converted items, sorted by
   `json.dumps(item, sort_keys=True)` of each converted item.
5. `bytes` or a `bytearray` is `value.decode("utf-8", errors="replace")`.
6. A `pathlib.PurePath` is `str(value)`.
7. An `enum.Enum` member is its converted `.value`.
8. An object with a callable `to_dict` is its converted `to_dict()`.
9. A dataclass instance is an object of each field's name and converted
   value, in field order (`dataclasses.fields`), never
   `dataclasses.asdict`, which fails on a value it cannot copy.
10. An object with a `__dict__` is an object of its `vars()` entries
    whose name does not start with `_` and whose value is not callable.
11. Anything else, a slotted object for example, is `repr(value)`.

Converting never raises. A test checks it by passing a value holding,
for example, `{"b", "a"}`, `b"x"`, `pathlib.Path("p")` and an instance
of `class S: __slots__ = ("x",)` and reading back `["a", "b"]`, `"x"`,
`"p"` and a string beginning `<`.
