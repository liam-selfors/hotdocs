# AC-KPY-009

Covers: R-KPY-007
Kind: generated-test

The parity criterion (`D344`). The code directory `d = tmp_path / "calc"`
holds three files, each shown as Python string literals concatenated:

`calc.py`:
`'"""Calculator: a < b and True are prose here."""\n' "\n" "\n"`
`"def check(a, b, xs):\n"`
`"    flags = [a == b, a != b, a < b, a >= b, a > b, a <= b]\n"`
`"    flags += [a is None, a is not None, a in xs, a not in xs]\n"`
`"    return flags, 0 < a < 10\n" "\n" "\n"`
`"def combine(a, b):\n" "    def inner(x):\n" "        return x * 2 / 4\n"`
`"    return (a and b) or inner(a + b - 1) // 3 % 2, True, False\n"`

`pkg/__init__.py`: `"def sign(n):\n    return -1 if n < 0 else 1\n"`

`__pycache__/junk.py`: `"x = 1 == 2\n"`

```gherkin
Given that code directory d
When strength_sites(d) is called
Then the list of "description" values is exactly
  ["calc.py:5: a == b -> a != b", "calc.py:5: a != b -> a == b",
   "calc.py:5: a < b -> a >= b", "calc.py:5: a >= b -> a < b",
   "calc.py:5: a > b -> a <= b", "calc.py:5: a <= b -> a > b",
   "calc.py:6: a is None -> a is not None",
   "calc.py:6: a is not None -> a is None",
   "calc.py:6: a in xs -> a not in xs",
   "calc.py:6: a not in xs -> a in xs",
   "calc.py:12: x * 2 / 4 -> x * 2 * 4",
   "calc.py:13: a and b or inner(a + b - 1) // 3 % 2 -> (a and b) and inner(a + b - 1) // 3 % 2",
   "calc.py:13: True -> False", "calc.py:13: False -> True",
   "calc.py:12: x * 2 -> x / 2", "calc.py:13: a and b -> a or b",
   "calc.py:13: inner(a + b - 1) // 3 % 2 -> inner(a + b - 1) // 3 // 2",
   "calc.py:13: inner(a + b - 1) // 3 -> inner(a + b - 1) % 3",
   "calc.py:13: a + b - 1 -> a + b + 1", "calc.py:13: a + b -> a - b",
   "pkg/__init__.py:2: n < 0 -> n >= 0"]
And the "file" values are "calc.py" for the first 20 and
  "pkg/__init__.py" for the last, and the "index" values are 0 to 19
  then 0
And every site has exactly the keys description, file, index
```

No site comes from the docstring, the chained `0 < a < 10`, the numeric
constants, `+=`, the unary `-1`, or `__pycache__`.
