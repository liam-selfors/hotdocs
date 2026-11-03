---
id: P-SLUGS
title: Titles Become URL Slugs
status: draft
owners: [web-team]
---

# Titles Become URL Slugs

## Purpose

A page title can be turned into a URL-safe slug.

### CS-SLUGS-001
Covers: P-SLUGS
Kind: generated-test

```gherkin
Given the title "Hello, World!"
When it is slugified
Then the result is "hello-world"
```
