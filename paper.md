---
title: "BR-MANGUE Studio: a raster-based cellular model for mangrove response to sea-level rise"
tags:
  - cellular automata
  - mangrove modelling
  - sea-level rise
  - geospatial raster
  - environmental modelling
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
  - name: Universidade Federal do Maranhão, Programa de Pós-Graduação em Ciência e Tecnologia Ambiental, Brazil
    index: 1
date: 12 October 2026
bibliography: paper.bib
---

# Summary

BR-MANGUE Studio is desktop and Python software for building, running, and inspecting spatial cellular-automaton simulations of mangrove response to coastal sea-level rise [@brmangue2026]. It reads categorical land-cover and elevation rasters, lets users map source codes to model classes, and applies annual transition rules across a raster grid. Users can inspect annual maps, trajectories, class transitions, and run metadata. The software provides a graphical interface for Windows and Linux, a command-line raster runner, and a Python package. Packaged applications include the Python runtime and required project libraries; users supply their own input data. English and Brazilian Portuguese are available in the interface.

# Statement of need

Mangrove response to sea-level rise depends on spatially explicit interactions among land cover, elevation, inundation, neighbourhood conditions, and barriers to migration. The original BR-MANGUE model used cellular automata to represent these interactions and explore mangrove response on Maranhão Island [@bezerra2014]. Researchers who reuse this approach need to prepare raster inputs, configure model classes and parameters, run simulations, and trace how outputs were produced. A research workflow that exposes these choices is useful for testing assumptions and comparing scenarios.

BR-MANGUE Studio addresses this need with raster validation, configurable class mapping, annual simulation, two execution engines, and standard geospatial and tabular outputs. It is intended for coastal researchers, geographers, environmental modellers, students, and research groups that need an inspectable workflow for spatial scenarios. The software accepts provider-independent, aligned raster inputs rather than requiring a particular land-cover or elevation product.

# State of the field

The BR-MANGUE formulation has previously been implemented as a cellular model and later parallelized with MPI and CUDA for high-performance computing [@bezerra2014; @carreirofilho2022]. BR-MANGUE Studio continues this research line in a Python-based desktop and raster workflow; it does not claim a new transition theory or replace the earlier parallel implementation. It adds input validation, configurable class mapping, annual output and run provenance, alongside continuous and persistent-block execution.

General cellular-modelling environments such as TerraME provide flexible tools for implementing spatial and multi-paradigm models [@carneiro2013], while GDAL supports interoperable raster and vector data access [@gdal2026]. These tools are broader in scope. BR-MANGUE Studio packages the BR-MANGUE states and workflow in a focused application that can be used without implementing the model infrastructure from scratch. The contribution is the integrated, reusable implementation and its reproducible raster workflow, built on established geospatial libraries and cellular-automaton concepts [@wolfram1983].

# Software design

The software separates raster preparation, model state and transition rules, simulation execution, and output generation. During preparation, aligned rasters are validated and valid cells are represented in a compact grid with neighbourhood indices. The model updates cell states annually from their current attributes, neighbourhood, and scenario parameters. Outputs include GeoTIFF states, trajectory and transition tables, run parameters, input hashes, timing, and available resource measurements.

The class-mapping interface lets users define additional model classes by name and colour, assign raster source codes, and select a behavior profile. Profiles reuse the implemented rules for a fixed class, mangrove source, natural vegetation, bare soil, anthropized land, or water; they do not add new transition equations. The continuous and persistent-block engines apply the selected migration, flooding, and flow behavior consistently. When a custom class changes to a derived state, run metadata retains its name and profile, and the transition report links its source raster code to the final model state. Projects created before profiles were introduced retain their previous fixed-state behavior.

The repository includes automated unit and raster-workflow tests, user documentation, and continuous integration across supported Python versions.

The continuous engine keeps the model state in memory and avoids persistent state-file access. The persistent-block engine stores state and neighbourhood arrays in disk-backed memory maps and updates a configurable slice of cells at a time. It reduces resident state during simulation and can lower memory pressure, at the cost of storage space and additional I/O. Both engines load and prepare the input grid before simulation; the block engine therefore still requires sufficient memory during preparation and is not an out-of-core raster reader. Their outputs can be compared cell by cell to check computational equivalence. Optional reprojection creates aligned copies and leaves source rasters unchanged.

# Research impact statement

The software has been used by its developers to exercise both engines on geospatial input and to measure computational capacity. In a 75-step raster workflow with 2,337,998 valid cells, the continuous and block engines produced identical annual states and trajectory metrics. The input extent was the valid rectangular overlap of the rasters without a study-area mask; this is a software verification run, not an ecological assessment.

A separate five-step synthetic capacity run used 160,000,000 valid cells (10,000 × 16,000) and disabled annual state export. On Ubuntu 26.04.1 LTS, an Intel Core i3-1215U with 8 logical CPUs and 20.1 GB of DDR4-3200 memory, the continuous engine processed 800,000,000 cell updates in 2,195.8 s, or 364,334 cell updates per second. Peak RSS during the measured simulation was 9.07 GiB; an external monitor recorded 12.65 GiB including input loading. The CPU's advertised maximum frequency is 4.4 GHz; its frequency during the run was not measured. The synthetic rasters have arbitrary spatial coordinates and no geographic or ecological interpretation. Attempts at 180, 200, and 240 million cells were stopped by a system-memory safety guard before completion. These were not completed simulations or software failures. Each size was run once, so the result is a measured capacity example for this computer, not a universal limit or comparative performance claim. The repository contains the benchmark configuration, run metadata, resource samples, and trajectory under `docs/benchmarks/capacity_tests/`.

# AI usage disclosure

Consensus and Connected Papers were used to discover relevant literature. ChatGPT and Codex, using the model families Sol, Luna, and Astra, assisted with Python development, model structuring, code and test review, benchmark-record analysis, and drafting and editing project documentation and this paper. The project records identify the model families but do not retain build-specific version identifiers. The authors made the core scientific and design decisions and are responsible for reviewing and validating AI-assisted code, text, references, and results before submission.

# Acknowledgements

This study was financed in part by the Coordenação de Aperfeiçoamento de Pessoal de Nível Superior - Brasil (CAPES) - Finance Code 001. The authors acknowledge the GEOTAM laboratory and the Universidade Federal do Maranhão for the research context in which the software was developed.

# References
