# R-DRV-003

**R-DRV-003** — A driven page MUST be isolated exactly as
  `specs/architecture/test-driver-browser.md`'s "Isolation" states:
  every request other than a `file://` URL inside the opened file's
  directory, a `data:` or `blob:` URL, or an `http://` URL on a loopback
  host is aborted and listed by `blocked_requests()`; each session has a
  fresh profile with the fixed locale, time zone, scale, motion and
  colour scheme; and a call over 30 seconds ends the session with
  `timed out after 30 seconds`.
