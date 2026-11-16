# R-SLUG-004

**R-SLUG-004** — `slugify` MUST return at most `max_length` characters: a
  longer slug is cut to its first `max_length` characters, then any
  trailing hyphen is removed. A `max_length` below `1` MUST raise
  `ValueError` with a message containing `max_length`.
