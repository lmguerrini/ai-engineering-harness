# Evidence index — capability <id>

Content-addressed: each file under `evidence/` is named
`sha256-<hash>-<short-name>`, written once, then referenced — never edited
after being referenced (write-then-reference ordering).

| sha256 (short) | File | What it is evidence for | Produced by | Date |
|---|---|---|---|---|

## Reading this index

An entry with no row here is not evidence yet, whatever is on disk — the index
*is* the claim that this file was reviewed and is being relied on. A file in
`evidence/` that never gets a row is either dead weight (delete it) or an
oversight (add the row).
