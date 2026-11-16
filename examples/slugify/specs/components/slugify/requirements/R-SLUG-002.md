# R-SLUG-002

**R-SLUG-002** — Before the R-SLUG-001 rules apply, `slugify` MUST convert
  accented letters to their unaccented ASCII letters by Unicode NFKD
  normalization, dropping the combining marks, so `"Café Déjà Vu"` gives
  `"cafe-deja-vu"`. A character with no ASCII form, such as `"日"`, counts
  as a non-alphanumeric character.
