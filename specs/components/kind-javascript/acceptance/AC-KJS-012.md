# AC-KJS-012

Covers: R-KJS-007
Kind: generated-test

The calibration pair. Write `tmp_path / "c.js"` holding exactly these
lines, each ending in `\n`:

```
export function grade(score) {
  if (score >= 90) return "A";
  if (score >= 75) return "B";
  return "C";
}

export function both(a, b) {
  return a === b && a > 0;
}

export function total(xs) {
  let s = 0;
  for (const x of xs) s = s + x;
  return s;
}
```

A suite is a list of `(entry, args, expected)`. Strong:
`("grade",[95],"A")`, `("grade",[80],"B")`, `("grade",[50],"C")`,
`("both",[2,2],True)`, `("both",[2,3],False)`, `("both",[-1,-1],False)`,
`("total",[[1,2,3]],6)`. Weak: `("grade",[95],"A")`, `("grade",[80],"B")`,
`("both",[2,2],True)`, `("total",[[]],0)`.

```gherkin
Given those fixtures
When strength_sites is called on c.js
Then the descriptions are exactly ["2: >= -> <", "3: >= -> <",
  "8: === -> !==", "8: && -> ||", "8: > -> <=", "13: + -> -"]
And each suite passes on c.js unmutated (asset_runner's run returns
  every expected value)
And, for each site in turn, on a fresh copy of c.js with apply_site
  applied, a site is killed when some call raises AssetError or
  returns a value != expected
Then the strong suite kills 6 of 6 (100%, at or above the 80% bar)
  and the weak suite kills exactly 4 of 6 (66.7%, below it): the
  survivors are "8: && -> ||" and "13: + -> -"
```
