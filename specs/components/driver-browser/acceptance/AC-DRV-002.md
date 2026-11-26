# AC-DRV-002

Covers: R-DRV-002
Kind: generated-test

```gherkin
Given a page with a button named "Add", a list whose items are
  "alpha" and "beta", an input labelled "Filter", and an inline script
  that appends a list item "gamma" when Add is clicked and hides every
  item not containing the filter's text on input
When the page is opened, Add is clicked, and "al" is filled into the
  Filter input
Then find(css="li").count() is 3, find(css="li").texts() is ["alpha",
  "beta", "gamma"], find(text="alpha").visible() is True,
  find(text="beta").visible() is False, and console_errors() is []

Given the same page
When find(role="button", name="Remove").click() is called
Then BrowserError is raised with message
  "no element matches role=button name=\"Remove\""

When find() is called with both css and role
Then BrowserError is raised with message
  "find takes exactly one selector"
```
