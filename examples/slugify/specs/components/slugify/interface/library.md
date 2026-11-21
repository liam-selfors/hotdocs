# Library

One module file, `slugify.py`.

```
slugify(title: str, max_length: int = 80) -> str
```

Errors: `slugify` raises `ValueError` for an invalid argument, as the
requirements state; it never returns an empty string.
