# Changelog

All notable changes to BR-MANGUE Studio are recorded here.

## [Unreleased]

## [1.3.0] — 2026-10-17

- Apply sediment accretion to every state configured with mangrove behavior,
  including migrated mangrove, without requiring the optional soil-suitability
  raster. The default accretion rate uses the annual sea-level-rise rate; users
  can still enter a fixed annual accretion rate or select the legacy soil-gated
  rule for reproducing earlier runs.
- Replace the fixed legacy land-cover state constants with a per-project state
  catalog. Configured class codes, behavior profiles, colors, and flooded
  states now drive continuous and persistent-block engines, output rasters,
  maps, trajectories, and transition reports.
- Use one derived state named `Migrated mangrove`; flooded states retain their
  source class name, and all state codes are recorded in run metadata and
  GeoTIFF tags.
- Rename state-raster outputs to English and show configured class assignments
  and behavior profiles in Model rules.

## [1.2.0] — 2026-10-12

- Add optional project-defined classes with custom names, colors, and existing
  model behavior profiles.
- Add fully user-defined class mapping. This mode starts with no standard
  categories selected and requires every raster code to be assigned or
  explicitly excluded.

## [1.1.0] — 2026-10-06

- Add a Brazilian Portuguese interface alongside English, the default language
  for new installations.
- Add an in-app language selector and save the preference between sessions.
- Localize desktop workflows, status messages, charts, and annual figure labels
  without changing project-file values or data columns.

## [1.0.1] — 2026-10-06

- Make frozen desktop builds prefer their bundled GDAL/PROJ databases over
  coordinate-library paths inherited from the host computer.
- Add a configurable maturation delay for migrated mangrove cells. The default
  is three complete annual steps; both engines preserve the age state.
- Add `migration_maturity_years` to project files, command-line execution, run
  metadata, and the user manual.

## [1.0.0] — 2026-09-21

This release consolidates the Python desktop application for the BR-MANGUE
cellular model and prepares a reproducible release workflow.

- Add continuous and persistent-block raster execution in the desktop workflow.
- Add annual trajectory, state-raster, transition, figure, and animation
  outputs.
- Record input provenance and detailed timing, memory, CPU, I/O, disk,
  throughput, and output-size measurements.
- Add CRS inspection and optional reprojection/alignment of input rasters.
- Add automated tests, contribution guidance, issue templates, citation
  metadata, and a reproducibility/benchmarking protocol.
- Add the Portuguese user manual for the Windows executable.

The scientific equivalence of the continuous and block engines should be
checked for each released build and documented with the benchmark protocol.
