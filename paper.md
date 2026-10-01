---
title: "BR-MANGUE Studio: an accessible and reproducible cellular model for exploring mangrove response to sea-level rise"
tags:
  - cellular automata
  - mangrove modelling
  - sea-level rise
  - coastal change
  - geospatial raster
  - environmental modelling
authors:
  - name: Felipe Martins Sousa
    affiliation: "1"
  - name: Denilson da Silva Bezerra
    affiliation: "2"
affiliations:
  - name: Universidade Federal do Maranhão, Brazil
    index: 1
  - name: Instituto Nacional de Pesquisas Espaciais, Brazil
    index: 2
date: 1 October 2026
bibliography: paper.bib
---

# Summary

BR-MANGUE Studio is a desktop research application for exploring how mangrove
landscapes may respond to scenarios of coastal sea-level rise [@brmangue2026].
It represents a landscape as a raster grid, assigns a state to each valid cell,
and applies local transition rules year by year. Researchers can load a categorical
land-cover GeoTIFF and an aligned elevation raster, map source codes to model
roles, configure a scenario, and inspect annual maps, trajectories, transition
tables, resource diagnostics, and animations. A standalone Windows application
and a Linux x86_64 research preview provide ready-to-run interfaces, while the
Python package exposes the model and raster runner for reproducible
computational workflows. Both desktop builds bundle the Python runtime and
project libraries; users still provide their own input rasters and a compatible
operating-system environment.

# Statement of need

Mangroves occupy complex coastal landscapes in which small differences in
elevation, adjacency, land cover, and human occupation affect the space
available for future migration. Spatially explicit cellular models are useful
for making these local assumptions visible and for testing alternative
scenarios. The original BR-MANGUE formulation demonstrated this approach for
Maranhão Island, Brazil, using a cellular automaton to explore sea-level-rise
impacts and mangrove migration near anthropic barriers [@bezerra2014].

Researchers who want to reuse that formulation face practical barriers: input
data must be converted to a particular grid schema, the original workflow is
not convenient for users unfamiliar with its development environment, and
large raster domains require an explicit memory strategy. BR-MANGUE Studio
addresses this gap by combining an input-validation workflow, explicit class
mapping, annual state outputs, a continuous executor, a persistent block
executor, and graphical Windows and Linux distributions. It is intended for coastal
scientists, geographers, environmental modellers, students, and research
groups that need to inspect assumptions rather than receive an opaque final
map. The application also exports ordinary GeoTIFF, CSV, and spreadsheet
products, so results can be checked in familiar tools and incorporated into
existing geographic-information workflows without requiring a new data
format.

# State of the field

General-purpose GIS software can reclassify rasters and perform map algebra,
but it does not by itself provide the BR-MANGUE state-transition semantics,
annual transition reports, or a direct comparison between in-memory and
persistent-block execution. The Studio builds on established cellular-automata
ideas [@wolfram1983] and interoperable geospatial raster tooling [@gdal2020].
General cellular-automata frameworks offer more flexibility, but require users
to implement the mangrove-specific states, neighbourhood rules, input schema,
and output audit trail. Large-scale geospatial platforms such as Earth Engine
address a different, cloud-oriented workflow [@gorelick2017]. BR-MANGUE Studio is
therefore a domain-specific, provider-independent implementation rather than
a replacement for GIS or a general cellular-automata framework. Building a
focused tool was appropriate because the research contribution is the
reproducible packaging of the documented BR-MANGUE rules and workflow, not a
new generic CA language.

# Software design

The implementation separates four concerns: (1) raster validation and
compaction into a valid-cell grid; (2) model states, attributes, and Moore
neighbourhood rules; (3) annual execution and persistent block storage; and
(4) user-interface visualisation and provenance outputs. This separation keeps
the scientific transition rules testable without requiring the desktop
interface and allows the same input metadata to be used in continuous and
block runs.

The continuous engine keeps active arrays in memory and avoids persistent
block I/O. The block engine alternates persistent state arrays and traverses a
configurable number of cells at a time. The second option can run domains that
are unsafe to materialise in RAM, at the cost of storage operations. Both
engines record the engine, input hashes, parameters, annual trajectories,
resource samples, and output manifest so that speed claims can be separated
from scientific equivalence. Optional CRS reprojection writes aligned copies
without modifying source rasters.

# Research impact statement

The project provides a reproducible implementation of a published mangrove
cellular-model formulation and makes it usable with modern aligned raster
datasets. Verification includes automated rule and raster tests, a long-horizon
continuous-versus-block comparison on 2,337,998 valid raster cells, and a
one-step CMMA comparison on 78,007,000 active cells. In the unmasked Ilha do
Maranhão raster extent, both Linux engines completed 75 steps from 2025 to
2100, processing 175,349,850 cell updates each. The initial state and all 75
annual output rasters (2026–2100), as well as state and transition metrics,
were identical cell by cell. Continuous mode took 567.5 s, and 10,000-cell
blocks took 1,417.1 s; peak process RSS was 545 and 567 MB, respectively. The
same inputs were also reprojected to EPSG:31983 and aligned; a one-step run on
the prepared copies matched between engines. An archived CMMA one-step
comparison reported identical final rasters and trajectories; it took 123.6 s
in continuous mode and 476.7 s in persistent blocks of 10,000 cells, without
annual raster export.

Separate Windows archives record 76 steps from 2024 to 2100 on 78,007,309
valid cells, with annual rasters for 2025–2100. They report 13,921 s for
continuous mode and 15,065 s for 1,000,000-cell blocks (about 8 h combined),
with peak process RSS of 5.02 and 5.81 GB, respectively. The two runs used
different source-class mappings: codes 3 and 4, and codes 23 and 32, were
assigned to different model classes; the block metadata also omits the
migration-maturity parameter. These runs therefore provide descriptive
timings, not a controlled engine-equivalence comparison. The archives do not
identify the Windows version, processor, or source revision. A Linux x86_64
executable started successfully on Ubuntu 26.04.1 LTS. The raster tests used
the project runner and an unmasked rectangular raster extent, so they provide
software verification and performance evidence, not independent ecological
validation. The repository includes automated tests, a user manual, benchmark
records, platform builds, and run-level metadata.

# AI usage disclosure

OpenAI Codex (GPT-6, accessed 1 October 2026) assisted with code and test
review, benchmark-record analysis, and revisions to project documentation and
this manuscript. Earlier project work also used generative AI for reference
discovery and draft structuring; the authors must confirm the tool and model
versions used for those earlier tasks before submission. The authors are
responsible for verifying AI-assisted text, references, code, and results and
for all scientific, technical, authorship, and licensing decisions.

# Acknowledgements

The project was developed from the BR-MANGUE model formulation and the
coastal-mangrove modelling work of Bezerra and collaborators. The authors
acknowledge the GEOTAM laboratory and the Universidade Federal do Maranhão
for the research context in which the Studio is being developed.

# References
