# Changelog

All notable changes to BR-MANGUE Studio are recorded here.

## [Unreleased]

- Replaced the fixed legacy land-cover state constants with a per-project
  state catalog. Configured class codes, behavior profiles, colors, and
  flooded states now drive the continuous and persistent-block engines,
  output rasters, maps, trajectory summaries, and transition reports.
- Added one generic derived state named `Migrated mangrove`; flooded states
  retain the source class name, and every code is documented in run metadata
  and GeoTIFF tags.
- Renamed state-raster outputs to English (`initial_state_*.tif`,
  `states/state_*.tif`, and `final_state_*.tif`) and updated the batch workflow
  and documentation.
- Updated the Model rules view to show the current project class assignments
  and behavior profiles directly. Removed the raw engine source pane from this
  user-facing view so internal state identifiers are not presented as project
  class rules.

## [1.1.0] — 2026-10-06

- Added a Portuguese (Brazil) interface alongside English, which remains the
  default language for new installations.
- Added an in-app language selector and saved the preference between sessions.
- Localized the desktop workflow, status messages, simulation charts, and
  annual figure labels without changing project-file values or data columns.

## [1.0.1] — 2026-10-06

- Frozen desktop builds now prefer their bundled, version-matched GDAL/PROJ
  databases over coordinate-library paths inherited from the host computer.
- Added a configurable maturation delay for migrated mangrove cells. The
  default is three complete annual steps before a migrated cell can propagate;
  continuous and persistent-block engines preserve the same age state.
- Added `migration_maturity_years` to project files, command-line execution,
  run metadata, and the user manual.

## [1.2.0] — 2026-10-12

- Added optional project-defined classes to the class-mapping tab. Users can
  name and colour additional states and select an existing behavior profile
  for mangrove, natural vegetation, bare soil, anthropized land, or water.
  Continuous and persistent-block engines apply the same migration, flooding,
  and flow rules. Project files and metadata retain the selected profile, and
  transition reports identify custom source classes after a derived transition.
- Added a fully user-defined mapping mode. It hides the standard model classes,
  starts every source code unassigned, and requires each code to be mapped to a
  named class and behavior profile or explicitly excluded. The selected mode is
  saved with the project; older projects continue to use standard mapping.

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
