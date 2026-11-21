# AC-KPY-011

Covers: R-KPY-007
Kind: generated-test

The calibration pair. Write `tmp_path / "grade" / "grade.py"` holding
exactly these lines, each ending in `\n`:

```
def grade(score):
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    return "C"


def both(a, b):
    return a == b and a > 0


def total(xs):
    s = 0
    for x in xs:
        s = s + x
    return s
```

A suite is a list of `(entry, args, expected)`. Strong:
`("grade",[95],"A")`, `("grade",[80],"B")`, `("grade",[50],"C")`,
`("both",[2,2],True)`, `("both",[2,3],False)`, `("both",[-1,-1],False)`,
`("total",[[1,2,3]],6)`. Weak: `("grade",[95],"A")`, `("grade",[80],"B")`,
`("both",[2,2],True)`, `("total",[[]],0)`.

```gherkin
Given those fixtures
When strength_sites is called on tmp_path / "grade"
Then the descriptions are exactly ["grade.py:2: score >= 90 -> score < 90",
  "grade.py:4: score >= 75 -> score < 75",
  "grade.py:10: a == b and a > 0 -> a == b or a > 0",
  "grade.py:10: a == b -> a != b", "grade.py:10: a > 0 -> a <= 0",
  "grade.py:16: s + x -> s - x"]
And each suite passes unmutated (asset_runner's run returns every
  expected value)
And, for each site in turn, on a fresh copy at
  tmp_path / "m<i>" / "grade" (the directory keeps its name) with
  apply_site applied, a site is killed when some call raises AssetError
  or returns a value != expected
Then the strong suite kills 6 of 6 (100%, at or above the 80% bar)
  and the weak suite kills exactly 4 of 6 (66.7%, below it): the
  survivors are "grade.py:10: a == b and a > 0 -> a == b or a > 0" and
  "grade.py:16: s + x -> s - x"
```
