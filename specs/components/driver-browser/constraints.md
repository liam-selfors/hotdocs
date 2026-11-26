# Browser Test Driver — Non-Functional Constraints

- **The test's own process never imports Playwright**; it runs in the
  driver's own process, from the environment's interpreter.
- **Network only for provisioning**: a driven page reaches only what
  `specs/architecture/test-driver-browser.md`'s Isolation allows.
