# JOSS readiness audit

**Updated:** 2 October 2026

This checklist tracks the manuscript and repository against the current JOSS
author and review guidance. It records preparation status; it is not a claim
that the software is ready for immediate submission.

## Prepared in the current draft

- The manuscript has JOSS YAML metadata and the required sections.
- The four supplied article authors appear in the stated order and share the
  supplied graduate-program affiliation at the Universidade Federal do
  Maranhão.
- The acknowledgements include the supplied CAPES Finance Code 001 wording.
- The AI-use disclosure now identifies Consensus for article discovery and
  ChatGPT/Codex models in the Sol, Luna, and Astra families for software
  development and Python model structuring.
- The main text is within JOSS's 750–1,750-word range.
- The summary describes the software for non-specialists and keeps its use
  independent of a specific land-cover provider or DEM source.
- The state-of-the-field section compares general geospatial tooling, SLAMM,
  TerraME, and published spatial cellular-automata work on mangroves.
- The manuscript distinguishes the published BR-MANGUE formulation from the
  Studio's configurable migration-maturity delay and optional land-cover
  fallback, which are software extensions rather than results of the original
  publication.
- The design section explains the continuous/block trade-off and reports that
  the pilot did not show a speed or peak-memory advantage for block mode.
- The research-impact section separates the controlled Linux comparison from
  historical, non-controlled Windows timing records and from ecological
  validation.
- Key references now include the original BR-MANGUE formulation, its 2022
  MPI/CUDA parallelization study, related mangrove cellular-automata work,
  ecological model assessment, TerraME, SLAMM documentation, NumPy, Rasterio,
  and GDAL.
- A GitHub Actions workflow is configured to compile the JOSS draft and retain
  its PDF as a workflow artifact when manuscript files change.

## Items to resolve before a JOSS submission

1. **Public development history and open collaboration.** The local history
   begins on 16 September 2026 and currently has 52 commits through 1 October,
   all by one contributor and concentrated in about two weeks. The conservative
   earliest submission date is 17 March 2027, and JOSS requires more than
   elapsed time: continue iterative development in public across that period.
   Three public issues (#1–#3) track Linux compatibility, reproducible
   benchmark inputs, and controlled engine-parity measurements. The public
   draft manuscript is PR #4. Continue substantive public discussion and
   contributions over time. The historical Windows 1.0.0 release and tag are
   published; the Linux build remains a separate research preview.
2. **Research significance.** The software is used in an ongoing graduate
   research project, but no external adoption or peer-reviewed publication is
   documented. JOSS asks for demonstrated research use and significance beyond
   a one-off analysis. Preserve evidence of the dissertation use and seek
   independent feedback, use, integration, or a research output before
   submission; the editor makes the final scope decision.
3. **Funding and acknowledgements.** The supplied CAPES Finance Code 001
   statement is included. Confirm that the funding applies to this work, state
   whether the sponsor influenced it, and confirm permission to thank the
   named lab and institution.
4. **Author review and AI-assisted work.** The manuscript records Consensus
   for article discovery and ChatGPT/Codex GPT-6 models in the Sol, Luna, and
   Astra families for software development and Python model structuring;
   Codex also assisted with documentation and this manuscript. JOSS asks for
   exact tool/model versions and where they were used. The Consensus version
   and exact model identifiers and dates are not yet recorded. Confirm them,
   then have all authors verify the disclosure, review AI-assisted text,
   sources, code, and claims, and confirm scientific and architectural
   decisions.
5. **Author metadata and consent.** Names, order, and the supplied official
   affiliation are recorded. Confirm authorship agreement and final metadata
   with all four authors before submission. `CITATION.cff` still lists only
   Felipe Martins Sousa and Denilson da Silva Bezerra; confirm software
   authorship and align its metadata if needed.
6. **Reproducible benchmark inputs.** The paper intentionally uses generic
   terms for land cover and elevation, but a reviewer must be able to identify
   or obtain the exact benchmark inputs. Record stable source/version details,
   hashes, and redistribution permissions; provide a small sample or a
   reproducible acquisition procedure where possible.
7. **Controlled Windows comparison.** The downloaded Windows archives report
   about 8 h 03 min across the two separate runs (about 3 h 52 min continuous
   and 4 h 11 min in blocks), despite an earlier recollection of about 4 h
   total. The archives use different class mappings and omit a parameter in
   the block metadata, so they cannot establish engine parity. The paper
   reports the archive-based values as historical descriptions.
8. **Independent platform verification.** No external use of the
   Studio is documented yet. A second-computer or second-distribution Linux
   run would strengthen the platform claim. Keep separate from the independent
   community-use evidence needed for research significance.
9. **Benchmark replication.** The current Linux comparison has one recorded
   run per engine and one block size. Repeat relevant tests and report the
   environment, variability, I/O, and storage costs; avoid a speed advantage
   claim unless replicated measurements support it.
10. **Scientific evaluation.** The current tests establish software behavior
   and engine agreement, not ecological validity. Define independent data,
   calibration and evaluation periods, a persistence baseline, and spatial
   metrics if the article is to make ecological-performance claims.
11. **PDF compilation.** The first hosted JOSS draft build completed
   successfully in GitHub Actions on PR #4. Review the generated PDF artifact
   for final typesetting before submission; this environment has no local
   Pandoc or Docker executable.
12. **Conflicts and final article metadata.** Ask all authors to disclose any
   potential conflicts of interest and add the required statement. Confirm the
   final article date and affiliation format before submission.

## Deferred until after JOSS review

JOSS describes the tagged software release and deposit with an archive such
as Zenodo after successful review. At that stage, create the tagged snapshot,
obtain its DOI, and replace the GitHub-only software citation with the exact
archive and version. No Zenodo record has been created.

## Current repository practices

The repository has an OSI-approved MIT license, browsable source, tests and
continuous integration, installation instructions, a manual, citation
metadata, release procedures, issue templates, contribution guidance, and
benchmark records.

JOSS paper guidance requires a concise Markdown paper with YAML metadata,
a summary, statement of need, state of the field, software design, research
impact, AI usage disclosure, acknowledgements, and references. It also asks
for key references to related software, financial-support acknowledgements,
and a software-archive link. See the [JOSS paper format](https://joss.readthedocs.io/en/latest/paper.html)
and [JOSS review criteria](https://joss.readthedocs.io/en/latest/review_criteria.html).
