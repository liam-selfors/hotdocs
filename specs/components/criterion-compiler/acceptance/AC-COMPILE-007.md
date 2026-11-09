# AC-COMPILE-007

Covers: R-COMPILE-007
Kind: generated-test

```gherkin
Given a compiled-kind criterion whose step is
  Given a payload is "os.system('touch <marker>')", with <marker> a path
  under tmp_path, followed by a When step invoking a declared function
  with payload and a Then step
When compile runs
Then it reports compiled, <marker> does not exist, and every occurrence
  of the payload text in the emitted source lies inside a Python string
  literal (the Given binding, and the When call's argument, where
  R-COMPILE-007 substitutes the literal for the name payload)

Given the emitted file is imported as a module (without running its test
  function)
Then <marker> still does not exist
```
