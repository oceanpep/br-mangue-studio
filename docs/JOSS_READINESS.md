# JOSS readiness review

This review follows the current [JOSS paper format](https://joss.readthedocs.io/en/latest/paper.html),
[submission requirements](https://joss.readthedocs.io/en/latest/submitting.html), and
[review criteria](https://joss.readthedocs.io/en/latest/review_criteria.html).
The submission manuscript is the English [`paper.md`](../paper.md) in the
software repository.

## Manuscript review completed

- The JOSS manuscript is within the required 750–1,750-word range and includes
  Summary, Statement of need, State of the field, Software design, Research
  impact statement, AI usage disclosure, Acknowledgements, and References.
- The author metadata now lists the four authors and the UFMA graduate program
  supplied for OE2. The date is the current draft date and must be replaced by
  the actual submission date when submitted.
- The field discussion cites the original BR-MANGUE article, its 2022
  MPI/CUDA implementation, TerraME, cellular-automata foundations, GDAL, and
  the software release. The GDAL record now uses the project's recommended
  citation. The 2022 BR-MANGUE reference was checked against the SBC
  proceedings record and the supplied PDF.
- The research-impact section distinguishes computational verification from
  ecological validation. It reports the 75-step, 2.34-million-cell engine
  comparison and the synthetic 160-million-cell run, with its single-run and
  hardware-specific limits. Larger guard-stopped runs are not presented as
  completed simulations or model failures.
- The description of the persistent-block engine now states that input rasters
  are loaded and prepared before the block workspace is created; block
  execution reduces resident state during the simulation but does not remove
  preparation memory requirements.
- A reproducibility package for synthetic capacity runs is now in
  [`docs/benchmarks/capacity_tests/`](benchmarks/capacity_tests/README.md),
  including scripts, cumulative results, raw run records, resource samples,
  and trajectory data.
- The acknowledgements include the CAPES Finance Code 001 statement supplied
  by the authors.
- Static checks found all six in-text citation keys in `paper.bib` and every
  raw record referenced by the cumulative capacity JSON in the repository.
  The JOSS/Inara rendering pipeline was not run because neither Pandoc nor
  Docker is available in the current environment; use the official JOSS
  action or renderer to produce the submission PDF before submission.

## Items to close before next year's submission

1. **Public development history:** the public repository was created on
   16 September 2026. JOSS requires more than six months of active public
   development before submission, so maintain visible development and
   recheck eligibility after 16 March 2027.
2. **Software archive:** create the requested Zenodo archive for the exact
   release to be reviewed, then add its DOI and update the software citation.
   Do not invent a DOI before the archive exists.
3. **AI disclosure:** project records identify Consensus and Connected Papers
   for literature discovery and ChatGPT/Codex model families Sol, Luna, and
   Astra for Python development, model structuring, review, and drafting. The
   build-specific model identifiers were not recorded. Add them if they can be
   recovered; all authors must also verify and endorse the disclosure that
   they reviewed and validated AI-assisted text, references, code, and results.
4. **Authorship metadata:** confirm that the four OE2 authors are also the
   correct software authors for JOSS. The current release's `CITATION.cff`
   lists Felipe Martins Sousa and Denilson da Silva Bezerra; reconcile the
   software citation metadata if the author team confirms the additional
   software authors.
5. **Final version check:** before submission, update the date, version and
   repository snapshot in `paper.md` and `paper.bib`; recheck the public
   repository, release, links, references, and current JOSS instructions.

The Portuguese file `manuscrito_OE2_v0.4_PT.md` in the dissertation materials
is a longer working manuscript, not the JOSS-formatted submission file. It is
approximately 3,800 words and should not be submitted to JOSS in its current
form. The concise English repository `paper.md` is the JOSS draft reviewed
here. The article is now formatted and substantially complete, with the
submission-year and author-verification items above still outstanding.
