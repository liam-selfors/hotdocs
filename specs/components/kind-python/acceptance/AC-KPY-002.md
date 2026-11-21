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
Then the result is exactly four items, in this order: "b.py:1: SyntaxError: invalid syntax",
  "b/c.py:2: SyntaxError: expected ':'", one starting
  "n.py:0: SyntaxError: " and one starting "u.py:1: SyntaxError: "
  (those two messages differ between Python versions; on 3.11 the null
  byte raises ValueError, which counts the same)
And after deleting b.py, b/c.py, n.py and u.py, layout_errors(d) is []
```
