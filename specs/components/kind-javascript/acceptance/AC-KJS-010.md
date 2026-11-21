# AC-KJS-010

Covers: R-KJS-007
Kind: generated-test

```gherkin
Given tmp_path / "a.js" holding exactly these five lines, each ending
  in "\n" (shown here as Python string literals):
  "const t = 'it\\'s < 1' + \"a \\\" > b\"; // c == d"
  "/* p && q */ const u = `x ${1 < 2}`;"
  "export const f = (a, b) => a === b || -a <= b;"
  "export function g(x) { return -x + x[0] - 1 >= true; }"
  "let n = 1 + 2; n++; n += 2; n = n >> 1 >>> 0 << 2;"
When strength_sites(that path) is called
Then the list of each site's "description" is exactly
  ["3: === -> !==", "3: || -> &&", "3: <= -> >", "4: + -> -",
   "4: - -> +", "4: >= -> <", "4: true -> false", "5: + -> -"]
And every site has exactly the keys description, offset, token, swap
  with text[offset:offset + len(token)] == token
```

No site comes from line 1's strings or comment (the `+` there follows a
string), line 2's comment or template, `=>`, the unary `-` after `||`
and `return`, or line 5's `++`, `+=`, `>>`, `>>>` and `<<`.
