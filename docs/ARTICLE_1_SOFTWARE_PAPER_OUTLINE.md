# Article 1 — BR-MANGUE Studio software paper

This outline is a working structure for the technical article about the
software. The CMMA ecological application belongs in the second article.

## Proposed contribution

BR-MANGUE Studio is a Python desktop implementation of the BR-MANGUE
cellular model that preserves the model rules while providing a reproducible
workflow for raster preparation, class mapping, simulation, monitoring and
annual outputs. Its technical contribution is the combination of a
provider-independent input pipeline, continuous and persistent-block engines,
resource diagnostics, and a Windows executable for researchers who do not
need to install Python.

## Sections and evidence

### 1. Introduction

- Explain the need for transparent, reproducible coastal cellular modelling.
- Identify the practical barriers in the previous Lua/TerraME workflow.
- State the objective: reimplement and package the model without changing its
  documented transition logic, while improving portability, observability and
  scalability.

### 2. Model and implementation background

- Describe the original BR-MANGUE formulation and cite the Bezerra work.
- Define the model states, annual transition step and migration/flooding
  processes at the level needed to reproduce the experiment.
- Distinguish model rules from the graphical interface and from optional
  integrations.
- Describe the Python architecture: input validation, class mapping, annual
  runner, continuous engine, persistent-block engine, output writer and GUI.

### 3. Software design

- Show a diagram from GeoTIFF inputs to validation, simulation and outputs.
- Explain CRS inspection and optional reprojection/alignment.
- Explain why the block engine exists and which state is preserved between
  blocks.
- Describe the Windows packaging and versioned release process.
- State the supported input assumptions and known limitations.

### 4. Reproducibility and provenance

- Give the exact repository commit, release version, operating system,
  Python/package versions and input hashes.
- Explain `metadata.json`, `trajectory.csv` and `resource_samples.csv`.
- State which outputs are required to reproduce a result and which are
  optional visual products.

### 5. Experiments

#### 5.1 Correctness and parity

- Run the same small and medium raster through the Python implementation and,
  where available, the reference implementation.
- Compare annual class counts, final cell states and transition totals.
- Report maximum absolute differences and differing-cell counts.

#### 5.2 CMMA benchmark

- Use the complete Costa de Manguezais de Macromaré da Amazônia (CMMA)
  land-cover raster and the aligned ANADEM Digital Terrain Model (MDT/DEM).
- Document the number of active cells, resolution, CRS, year range and class
  mapping.
- Compare continuous mode with persistent blocks using the same configuration.
- Test at least 10,000, 100,000 and 1,000,000 cells per block where the
  computer and storage allow.
- Use one warm-up and at least three timed repetitions per configuration.
- Report median, range, throughput, peak process RSS, system memory, disk
  usage, output size and annual-step timing.
- Repeat one short configuration with annual raster export enabled to separate
  model cost from output cost.

#### 5.3 Executable and usability evaluation

- Run the release executable on a second computer and record installation,
  startup, completion and output-integrity checks.
- Invite a small group of domain researchers to perform the same task:
  load inputs, map classes, configure a short run, inspect the outputs and
  export results.
- Use a short task-completion form and a System Usability Scale (SUS)
  questionnaire, with consent and ethics guidance when collecting identifiable
  responses.
- Report this as formative usability evidence, not as ecological validation.

### 6. Results

Recommended tables and figures:

1. Architecture diagram and output-folder example.
2. Parity table with annual and cell-wise differences.
3. Runtime and throughput by engine and block size.
4. Peak-RSS, available-memory and output-size comparison.
5. Annual-step timing/resource trace for a representative run.
6. Executable verification table and anonymized usability summary.

### 7. Discussion and limitations

- Explain the speed/memory trade-off between continuous and block engines.
- State that block processing is designed for domains that cannot fit safely
  in RAM, even when continuous mode is faster for a given machine.
- Separate implementation parity from ecological calibration and validation.
- Discuss dependence on storage speed, CPU load, raster geometry, export
  settings and operating-system memory management.
- Identify future work: parallel block scheduling, richer calibration and
  additional platform builds.

### 8. Availability and citation

- Link the public repository, versioned Windows release, user manual and
  Zenodo DOI.
- Include the license, `CITATION.cff`, release checksum and exact benchmark
  configuration.

## Claims that require evidence before submission

- Do not claim that the two engines are equivalent until a cell-wise comparison
  has been recorded for the final CMMA configuration.
- Do not claim ecological validation from a performance benchmark or usability
  test.
- Do not publish a capacity number such as “millions of cells” without naming
  the computer, active-cell count, number of annual steps, output settings and
  repetition summary.
- Do not call the executable cross-platform; the current public package is a
  Windows 64-bit build.

