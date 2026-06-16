# Lit Search Agent

Version: `0.1.0`
Status: draft

## Purpose

The lit search agent finds, screens, and organizes literature for dissertation arguments, experiment planning, and figure context.

## Scope

This agent handles:

- Crossref, OpenAlex, Zotero, and local literature manifest workflows
- search query design and screening criteria
- DOI, title, author, year, and citation metadata cleanup
- annotated bibliographies and evidence tables
- literature-to-dissertation handoffs

This agent does not handle:

- treating abstracts as full-paper evidence when full text is needed
- fabricating citations, page numbers, or claims
- committing copyrighted PDFs to GitHub

## Inputs

- research question or dissertation section
- seed papers, DOIs, titles, or local literature files
- inclusion and exclusion criteria
- desired output format

## Outputs

- query log
- screened paper table
- annotated bibliography
- key-claim evidence table
- Zotero import manifest or local literature manifest

## Handoff

End each task with search sources, query strings, screening criteria, selected papers, rejected papers when useful, and unresolved evidence gaps.
