# Test Probe — Non-Functional Constraints

- **No model calls and no network access.** The stub run's test may try
  the network; nothing in this component does.
- **Never imports the code under test.** The real module is never on the
  stub run's import path.
- **Leaves nothing behind.** Every file it writes is under a temporary
  directory it removes before returning.
- **Bounded.** The stub run is killed after `timeout` seconds.
