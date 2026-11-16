# AC-VERIFY-004

Covers: R-VERIFY-004
Kind: generated-test

```gherkin
Given a component whose gen/<component>/ public interface does not match
  its interface/ contract
When verify runs
Then interface_drift is true and the overall verdict is fail
```
