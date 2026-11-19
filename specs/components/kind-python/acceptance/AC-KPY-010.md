# AC-KPY-010

Covers: R-KPY-008
Kind: generated-test

```gherkin
Given the code directory d of AC-KPY-009's fixture, written exactly as
  that criterion shows it, and sites = strength_sites(d)
When apply_site(d, sites[11]) is called
Then (d / "calc.py").read_text() is exactly
  '"""Calculator: a < b and True are prose here."""\n\ndef check(a, b, xs):\n    flags = [a == b, a != b, a < b, a >= b, a > b, a <= b]\n    flags += [a is None, a is not None, a in xs, a not in xs]\n    return (flags, 0 < a < 10)\n\ndef combine(a, b):\n\n    def inner(x):\n        return x * 2 / 4\n    return ((a and b) and inner(a + b - 1) // 3 % 2, True, False)'
  (a Python string literal, with no newline at the end)
And pkg/__init__.py is unchanged

Given a fresh copy of the fixture and its sites
When apply_site(d, sites[20]) is called
Then (d / "pkg" / "__init__.py").read_text() is exactly
  "def sign(n):\n    return -1 if n >= 0 else 1"
  and calc.py is unchanged
And apply_site(d, dict(sites[0], index=99)) and
  apply_site(d, dict(sites[0], description="calc.py:5: x -> y")) each
  raise ValueError and leave calc.py unchanged
```
