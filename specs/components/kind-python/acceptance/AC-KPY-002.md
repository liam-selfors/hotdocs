# AC-KPY-002

Covers: R-KPY-002
Kind: generated-test

```gherkin
Given the code directory d = tmp_path / "lay" holding, written with
  write_text (or write_bytes where bytes are shown):
  "a.py": "def ok():\n    return 1\n"
  "b.py": "def f(:\n    pass\n"
  "b/c.py": "x = 1\nif x\n    y = 2\n"
  "n.py": b"x = 1\x00\n"
  "u.py": b"x = '\xff'\n"
  "__pycache__/bad.py": "def (\n"
  "notes.txt": "def (\n"
When layout_errors(d) is called
Then the result is exactly
  ["b.py:1: SyntaxError: invalid syntax",
   "b/c.py:2: SyntaxError: expected ':'",
   "n.py:0: SyntaxError: source code string cannot contain null bytes",
   "u.py:1: SyntaxError: Non-UTF-8 code starting with '\\xff' on line 1, but no encoding declared; see https://peps.python.org/pep-0263/ for details"]
  (the last shown as a Python string literal: one backslash before xff)
And after deleting b.py, b/c.py, n.py and u.py, layout_errors(d) is []
```
