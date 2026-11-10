# AC-COMPILE-016

Covers: R-COMPILE-007
Kind: generated-test

```gherkin
Given a widget component whose interface/library.md declares
  make(value) -> Result, and interface/data/Thing.md has the heading
  # `Thing` and a json example {"name": "x", "size": 1}
And criteria whose Given steps bind, one each: a n is 3, a f is 2.5,
  a e is 1e3, a t is true, a b is false, a z is null,
  a s is "say \"hi\"", a l is [1, [2, 3], {"k": null}]
When each is followed by When make is invoked with [<that name>] and
  Then value equals <the same literal>, and compile runs
Then each compiles, and the emitted call passes exactly 3, 2.5, 1000.0,
  True, False, None, "say \"hi\"" and [1, [2, 3], {"k": None}]

Given the step Given a Thing with name: "a", size: 2
Then it compiles to a Thing built with name and size

Given the step Given a Thing with colour: "red"
Then it fails to compile, the message naming colour
```
