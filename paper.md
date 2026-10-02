---
title: "BR-MANGUE Studio: desktop software for raster-based cellular simulation of mangrove responses to sea-level rise"
tags:
  - cellular automata
  - coastal ecosystems
  - geospatial rasters
  - mangrove modelling
  - research software
  - sea-level rise
authors:
  - name: Felipe Martins Sousa
    affiliation: "1"
  - name: Denilson da Silva Bezerra
    affiliation: "1"
  - name: Sergio Souza Costa
    affiliation: "1"
  - name: Ricardo Luvizotto Santos
    affiliation: "1"
affiliations:
  - name: Programa de Pós-Graduação em Ciência e Tecnologia Ambiental, Universidade Federal do Maranhão, Brazil
    index: 1
date: 2 October 2026
bibliography: paper.bib
---

# Summary

BR-MANGUE Studio is an open-source desktop application for exploring how mangrove ecosystems may respond to rising sea levels. It implements a raster-based adaptation of the published BR-MANGUE cellular model, with configurable extensions for scenario testing, and saves annual maps, tables, and run records. Researchers can map their own land-cover categories to model states, set parameters, and compare runs. Windows and Linux x86_64 builds bundle the Python runtime and project libraries; users supply the input maps and need a compatible operating-system environment. A Python package also supports scripted workflows. The software helps researchers inspect scenarios; it does not by itself calibrate or validate ecological predictions [@brmangue2026].

# Statement of need

Coastal wetlands are shaped by changes in water level, elevation, land cover, and barriers to inland migration. Spatially explicit models make these local relationships visible by representing a landscape as cells whose states change over time [@wolfram1983]. The published BR-MANGUE formulation uses cellular automata to explore flooding and potential mangrove migration under sea-level rise [@bezerra2014]. Related spatial cellular-automata studies have applied similar ideas to other mangrove coastlines [@tomaz2021].

Researchers reusing BR-MANGUE need to prepare aligned raster inputs, map source land-cover categories to model states, configure a scenario, and preserve enough information to interpret each run. BR-MANGUE Studio brings these tasks into one workflow. It validates categorical land-cover and elevation rasters, records class mappings and parameters, runs the model, and exports annual maps and tabular summaries. It is intended for coastal researchers, geographers, environmental modellers, and students who need to inspect and compare scenarios without implementing the transition rules themselves. Inputs are not tied to a particular data provider: users can supply compatible land-cover maps and a digital elevation model (DEM) for their study area.

# State of the field

Geospatial libraries such as GDAL support raster conversion and analysis, while platforms such as Google Earth Engine provide cloud-based geospatial workflows [@gdal2026; @gorelick2017]. TerraME is a flexible, multi-paradigm environment for spatial simulation and was used in the earlier BR-MANGUE workflow [@carneiro2013]. The Studio moves this specific model workflow from its earlier Lua/TerraME setting into a focused Python package and desktop application, integrating raster checks, class mapping, annual outputs, and persistent-block execution. This focused design reduces setup for BR-MANGUE while leaving broader modelling tasks to TerraME and GIS tools. The Sea Level Affecting Marshes Model (SLAMM) is a closer coastal comparator: it models habitat transitions under sea-level rise using elevation ranges, tidal parameters, and accretion assumptions [@clough2010]. Published spatial cellular-automata applications have also explored mangrove response to sea-level rise [@bezerra2014; @tomaz2021; @osullivan2001].

BR-MANGUE Studio complements these approaches rather than replacing them. Its contribution is a portable, inspectable implementation of a specific mangrove cellular-model workflow, with explicit source-class mapping, annual outputs, run provenance, and continuous or persistent-block execution. Users who need this formulation can run and inspect it directly instead of rebuilding the workflow from general GIS operations or adapting a different coastal model. The software does not claim to provide a new ecological theory, a general cellular-automata framework, or ecological validation.

# Software design

The implementation separates raster validation, model rules, execution and output writing, and the graphical interface. The same model code is used by the desktop application and the scripted raster runner. This separation allows the transition rules to be checked without requiring the interface and keeps input preparation distinct from model behaviour. Raster reprojection creates aligned copies rather than changing the user's source files; categorical data use nearest-neighbour resampling, while continuous elevation data use bilinear resampling. Raster I/O relies on Rasterio and GDAL, and model states are represented with NumPy arrays [@gillies2013; @gdal2026; @harris2020array].

The Studio implements a raster-based Python adaptation derived from the published BR-MANGUE cellular automaton [@bezerra2014]. It adds a configurable delay before newly migrated cells can propagate and an optional land-cover-based migration fallback when a suitability layer is unavailable. These are software extensions rather than rules evaluated in the original publication. The default three-year delay is an operational assumption exposed for sensitivity analysis, not a globally calibrated biological constant; reproductive timing varies among mangrove populations [@dangremond2016].

The continuous engine keeps active state arrays in memory and is generally faster when the grid fits comfortably in RAM. The persistent-block engine stores state arrays and neighbourhood indices in memory-mapped files, releases the materialized input grid before stepping, and updates a configurable number of cells at a time. It trades additional disk use and I/O for a processing path intended for larger grids. It is not faster in the reported pilot: on the 2.34-million-cell Linux test, block mode took about 2.5 times as long and used about 21 MiB more peak process memory. Both engines preserve the model's update order, so their outputs can be compared cell by cell.

# Research impact statement

The Studio is being used in an ongoing graduate research project; no peer-reviewed publication or external adoption of the software has yet been documented. Current evidence consists of software verification and performance measurements on aligned raster inputs.

In a matched-input Linux run over an unmasked raster extent, both engines completed 75 transitions from 2025 to 2100 across 2,337,998 valid cells, processing 175,349,850 cell updates each. The initial state and all 75 annual output rasters (2026–2100), as well as state and transition metrics, were identical cell by cell. Continuous mode took 567.5 s, and 10,000-cell blocks took 1,417.1 s; peak process RSS was 520 and 541 MiB, respectively. A one-step run on reprojected and aligned copies also matched between engines. An archived one-step comparison on 78,007,000 active cells reported matching final rasters and trajectories; it took 123.6 s in continuous mode and 476.7 s in persistent blocks of 10,000 cells, without annual raster export. These computational checks establish agreement between execution paths for the tested inputs, not ecological validity or predictive skill [@oreskes1994; @rykiel1996].

Historical Windows archives record 76 transitions from 2024 to 2100 on 78,007,309 cells, with annual rasters for 2025–2100. They report 13,921 s for continuous mode and 15,065 s for persistent blocks, about 8 h 03 min combined. These are descriptive historical timings, not a controlled comparison or a benchmark of the current source revision: the class mappings differ, the block-run metadata omits a migration-maturity parameter, and the archives do not identify the application version, Windows release, or processor. The Linux executable opened on one Ubuntu 26.04.1 LTS x86_64 computer; the long simulation was run through the package's raster runner rather than through the graphical interface. The Linux input lacked a study-area mask and soil data, so the test covered a rectangular raster extent and does not constitute an island-specific ecological projection or independent ecological validation.

# AI usage disclosure

Consensus was used to discover scholarly articles relevant to the research. ChatGPT and Codex, using GPT-6 models from the Sol, Luna, and Astra families, assisted with software development and structuring the model in Python. Codex also assisted with editing the software documentation and this manuscript. Benchmark descriptions were checked against archived run records, and bibliographic details against publisher or software-maintainer sources. The authors are responsible for checking the sources, code, analyses, and text, and for the final content of the manuscript and software. Before submission, all authors must confirm that they reviewed, edited, and validated AI-assisted outputs and made the core scientific and architectural decisions; exact model identifiers and dates of use should also be confirmed.

# Acknowledgements

The authors acknowledge the original BR-MANGUE formulation and the coastal-mangrove modelling work of Bezerra and collaborators. They thank the GEOTAM laboratory and the Universidade Federal do Maranhão for the research context in which the Studio is being developed. This study was financed in part by the Coordenação de Aperfeiçoamento de Pessoal de Nível Superior - Brasil (CAPES) - Finance Code 001.

# References
