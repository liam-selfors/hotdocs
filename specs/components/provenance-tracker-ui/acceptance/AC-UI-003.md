# AC-UI-003

Covers: R-UI-003
Kind: generated-test

```gherkin
Given a page rendered for a snapshot containing a failing component
  with a non-empty retry_feedback
When index.html is inspected
Then it contains no <form element, no href attribute other than ones
  beginning with "#", and exactly two script elements: the
  id="tracker-snapshot" JSON data block and one <script type="module">
  element whose text is static/app.js's text followed by
  "\ninit(document);\n", as R-UI-001 writes it
```
