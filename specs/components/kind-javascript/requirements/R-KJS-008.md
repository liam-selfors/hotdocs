# R-KJS-008

**R-KJS-008** — `apply_site(asset_file, site)` MUST read the file as
UTF-8 bytes decoded, check that `text[offset:offset + len(token)]`
equals `site["token"]` (else raise `ValueError` and leave the file
unchanged), and write back, UTF-8 with no newline translation,
`text[:offset] + swap + text[offset + len(token):]`: exactly one token
replaced, every other character, newlines included, unchanged.
