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
date: 22 September 2026
bibliography: paper.bib
---

# Summary

BR-MANGUE Studio is a desktop research application for exploring how mangrove
landscapes may respond to scenarios of coastal sea-level rise. It represents a
landscape as a raster grid, assigns a state to each valid cell, and applies
local transition rules year by year. Researchers can load a categorical
land-cover GeoTIFF and an aligned elevation raster, map source codes to model
roles, configure a scenario, and inspect annual maps, trajectories, transition
tables, resource diagnostics, and animations. A Windows executable provides a
ready-to-run interface, while the Python package exposes the model and raster
runner for reproducible computational workflows.

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
executor, and a graphical Windows distribution. It is intended for coastal
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
datasets. Its research impact is being evaluated through parity tests against
the reference workflow, complete-domain benchmarks using the Costa de
Manguezais de Macromaré da Amazônia (CMMA), and independent researcher
usability tests. The repository includes automated tests, a complete user
manual, benchmark protocols, a versioned Windows distribution, and run-level
metadata. These materials provide a concrete basis for reuse and review; final
claims about engine equivalence and ecological validity will be reported only
after the documented experiments are complete.

# AI usage disclosure

Generative AI was used as an editorial and engineering assistant during the
development of BR-MANGUE Studio and the preparation of this documentation. It
helped with code review, test scaffolding, wording, and manual structure. The
software authors selected the model rules, reviewed and edited generated text
and code, ran the automated tests, inspected outputs, and remain responsible
for all scientific, technical, authorship, and licensing decisions. No result
or performance claim is treated as validated solely because it was suggested
by an AI tool.

# Acknowledgements

The project was developed from the BR-MANGUE model formulation and the
coastal-mangrove modelling work of Bezerra and collaborators. The authors
acknowledge the GEOTAM laboratory and the Universidade Federal do Maranhão
for the research context in which the Studio is being developed.

# References
