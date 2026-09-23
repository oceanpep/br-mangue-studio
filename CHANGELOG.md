# Changelog

All notable changes to BR-MANGUE Studio are recorded here.

## [Unreleased]

- Added a configurable maturation delay for migrated mangrove cells. The
  default is three complete annual steps before a migrated cell can propagate;
  continuous and persistent-block engines preserve the same age state.
- Added `migration_maturity_years` to project files, command-line execution,
  run metadata, and the user manual.

## [1.0.0] — 2026-09-21

This release consolidates the Python desktop application for the BR-MANGUE
cellular model and prepares a reproducible release workflow.

- Added continuous and persistent-block raster execution in the desktop
  workflow.
- Added annual trajectory, state-raster, transition, figure, and animation
  outputs.
- Added run metadata with input provenance and detailed timing, memory, CPU,
  I/O, disk, throughput, and output-size measurements.
- Added per-year performance fields and a periodic `resource_samples.csv`
  trace.
- Added CRS inspection and optional reprojection/alignment of input rasters.
- Added automated tests, GitHub Actions, contribution guidance, issue
  templates, citation metadata, and a reproducibility/benchmarking protocol.
- Added the Portuguese user manual for the Windows executable.

The scientific equivalence of the continuous and block engines must be checked
for each released build and documented with the benchmark protocol.
