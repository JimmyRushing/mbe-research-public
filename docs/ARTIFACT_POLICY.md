# Artifact Policy

Use the private repo for source-of-truth research provenance. Use a separate public repo for curated, sanitized, public-facing documentation, demos, and scripts.

GitHub repositories are public/private at the repository level, not folder level. Do not rely on "hiding" sensitive folders inside an otherwise public repo. The clean pattern is:

```text
private repo -> allowlist export/sanitize script -> public repo
```

## Public Repo Artifacts

These can be published after review:

- cleaned analysis notes
- reproducible scripts with no private paths, credentials, or raw-data assumptions
- generated figures without private metadata
- small curated CSV examples
- literature summaries written in our own words
- non-sensitive characterization heuristics
- public-facing agent cards or sanitized prompts
- reproducible plotting and analysis workflows
- selected public PDFs when rights and collaborator expectations are clear
- hosted static HTML demos and screenshots

## Private Repo Artifacts

These can live in the private source repo, but should not be copied directly into a public repo:

- facility notes with operational details
- collaborator emails, messages, or private correspondence
- raw unpublished datasets
- sample logs tied to private or unpublished projects
- internal meeting slides
- private growth databases
- raw instrument exports that contain sensitive metadata
- rough notebooks with private paths, comments, or half-finished analysis
- local connector files and personal automation notes
- bulky generated exports, audio, or rendered draft bundles

## Never Commit Publicly

Do not commit these to a public repository:

- passwords, access instructions, API keys, or tokens
- safety-critical facility procedures or staff-only shortcuts
- personal documents, certifications, IDs, or tax/admin files
- purchase orders, billing information, or receipts
- collaborator correspondence
- copyrighted PDFs unless clearly allowed
- Office lock files, `.DS_Store`, `Thumbs.db`, cache folders, or temp files
- downloaded runtimes, model weights, or vendor tool bundles
- raw SQLite database snapshots
- raw control-point exports or growth-note PDFs
- files with private home-directory paths when avoidable

If any credential or password-like value ever lands in a public repo, deleting the file is not enough. Rotate the credential and rewrite public history if the repository must remain public.

## Good Private Git Artifacts

Track files that explain or reproduce work:

- Markdown notes, plans, and reports
- scripts
- sidecar metadata
- schemas and import instructions
- small curated CSV summaries
- final or near-final figure assets when they are dissertation-critical
- manifests or checksums for raw data stored elsewhere

## Avoid Normal Git

Do not add new files of these types unless there is a specific reason:

- credentials, passwords, tokens, or screenshots/images containing login information
- raw PDFs and books
- Office binaries
- raw instrument dumps
- generated exports and zip bundles
- SQLite/database snapshots
- audio/video outputs
- downloaded runtimes and model files

The private source repository may contain historical or bulky research artifacts for provenance, but public work must be exported through an allowlist.

## Before Adding A Large File

Ask:

- Is this source, evidence, or just storage?
- Can it be regenerated from tracked scripts and documented inputs?
- Does Zotero or a storage folder handle it better?
- Would a manifest, checksum, or short summary be enough?
- Is this public-safe, private-only, or never-commit material?

If the file must be versioned, decide between Git LFS, a release artifact, or a separate private storage location before adding it.

## Public Export Gate

Before pushing a public repo:

- export only allowlisted paths
- run secret scanning such as `gitleaks` or `trufflehog`
- search for local paths such as local drive-root paths, personal home directories, and personal usernames
- search for sensitive words such as `password`, `token`, `secret`, `credential`, `facility`, `SOP`, `private`, and `unpublished`
- verify that no raw exports, raw databases, copyrighted PDFs, or private facility notes are present
- open the GitHub Pages site in a normal browser and click every public-facing link
