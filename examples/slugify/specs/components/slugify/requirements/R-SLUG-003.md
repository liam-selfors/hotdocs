# R-SLUG-003

**R-SLUG-003** — `slugify` MUST raise `ValueError` with a message
  containing `empty` when the slug the rules above produce would be the
  empty string, such as for `""`, `"   "` or `"!!!"`.
