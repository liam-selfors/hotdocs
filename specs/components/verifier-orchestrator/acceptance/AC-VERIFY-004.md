# AC-VERIFY-004

Covers: R-VERIFY-004
Kind: compiled

```gherkin
Given a component whose gen/<component>/ public interface does not match
  interface.md
When verify runs
Then interface_drift is true and the overall verdict is fail
```
