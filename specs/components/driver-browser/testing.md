# Testing driver-browser

Provisioning downloads Playwright and Chromium, so every test shares
one environment, built once per machine: a session-scoped fixture calls
`provision(Path.home() / ".cache" / "hotdocs-test")` and skips nothing
when it fails, failing instead with its `reason`. Each test then calls
`open_session(Path.home() / ".cache" / "hotdocs-test", tmp_path)`, and
`close()` in a `finally`.

Pages are written under `tmp_path` by the test itself, each a complete
HTML document with any script inline. A loopback server is
`http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)` started in
a thread, serving a directory under `tmp_path`, and shut down in a
`finally`. No test reaches any host but loopback.
