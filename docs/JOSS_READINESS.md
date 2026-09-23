# JOSS readiness audit

This checklist records the repository state against the current JOSS author
and review guidance. It is a preparation document, not a claim that the
project is ready to submit immediately.

## Implemented repository practices

- OSI-approved MIT license in the root `LICENSE` file;
- browsable source code, public issue tracker, and public contribution path;
- Python packaging through `pyproject.toml`;
- Windows executable and source installation instructions;
- Portuguese user manual and English project documentation;
- JOSS-format draft in `paper.md` with `paper.bib`;
- `CITATION.cff` and a Zenodo release checklist;
- automated tests in `tests/` and GitHub Actions in `.github/workflows/`;
- bug report and feature request templates;
- contribution, support, and code-of-conduct documents;
- changelog and versioned release/checksum workflow;
- reproducibility and benchmark protocols;
- explicit AI-usage disclosure in the draft paper.

## Evidence still required before submission

1. Maintain a public development history for at least six months from the
   public repository record, with releases and visible iterative development.
2. Add the final CMMA benchmark, including hardware, repeated runs, peak RAM,
   throughput, output cost, and cell-wise equivalence checks.
3. Complete at least one independent second-computer verification and retain
   its reproducibility record.
4. Invite external researchers to use the executable and document feedback or
   issues without overstating a usability test as ecological validation.
5. Create a tagged release and archive it in Zenodo so `paper.md` can cite a
   stable DOI and exact source snapshot.
6. Replace provisional statements in the draft paper with verified results and
   final author/affiliation details.

JOSS requires a full paper of approximately 750–1750 words, with Summary,
Statement of need, State of the field, Software design, Research impact
statement, AI usage disclosure, acknowledgements, and references. The paper
should remain a concise software article; detailed instructions belong in the
manual, not in the paper.
