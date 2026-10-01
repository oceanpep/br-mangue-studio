# JOSS readiness audit

This checklist records the repository state against the current JOSS author
and review guidance. It is a preparation document, not a claim that the
project is ready to submit immediately.

## Implemented repository practices

- OSI-approved MIT license in the root `LICENSE` file;
- browsable source code, public issue tracker, and public contribution path;
- Python packaging through `pyproject.toml`;
- standalone Windows and Linux x86_64 executables and source installation
  instructions;
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

1. GitHub records the public repository as created on 16 September 2026.
   JOSS requires more than six months of active public development, so the
   earliest date based on repository age is after 16 March 2027; continue
   visible, iterative development and community activity through that period.
2. Extend the recorded one-step CMMA benchmark with repeated runs, block sizes,
   annual-output cost, and a controlled long-horizon comparison. The archived
   Windows metadata record about 8 h 03 min across two runs, but their class
   mappings differ and they do not establish engine parity.
3. Complete an independent second-computer verification, including a Linux
   distribution other than Ubuntu 26.04.1, and retain
   its reproducibility record.
4. Invite external researchers to use the executable and document feedback or
   issues without overstating a usability test as ecological validation.
5. Create a tagged release and archive it in Zenodo so `paper.md` can cite a
   stable DOI and exact source snapshot.
6. Replace provisional statements in the draft paper with verified results and
   final author/affiliation details. Complete the AI disclosure with the
   versions of every tool/model used in earlier code and manuscript work.

JOSS requires a full paper of approximately 750–1750 words, with Summary,
Statement of need, State of the field, Software design, Research impact
statement, AI usage disclosure, acknowledgements, and references. The paper
should remain a concise software article; detailed instructions belong in the
manual, not in the paper.

Current references: [JOSS paper format](https://joss.readthedocs.io/en/latest/paper.html)
and [JOSS submission requirements](https://joss.readthedocs.io/en/latest/submitting.html).
