# Reproducibility and benchmarking protocol

This document defines the evidence package for the BR-MANGUE Studio software
article. It is intentionally separate from the ecological interpretation of a
case study: the software paper should establish that the implementation is
traceable, measurable, and usable on a documented computer.

## What every run records

Each raster run creates a directory under `results/run_*` containing the input
metadata, the annual trajectory, state rasters when enabled, and
`metadata.json`. The metadata distinguishes:

- preparation time: loading and, for block mode, creation of the persistent
  workspace;
- simulation time: annual model transitions and state writes;
- post-processing and total run time;
- total cell updates and cell-updates per second;
- process RSS before, after, and at the measured peak;
- system memory before and after the simulation;
- free disk space before and after the run, and the size of generated outputs;
- process CPU time and operating-system I/O counters when Windows exposes them;
- engine, block size, input counts, model parameters, and input hashes.

`trajectory.csv` includes `step_elapsed_seconds`, `step_rss_bytes`, and
`step_cells_per_second` for each simulated year. These fields make it possible
to plot scaling and identify a slow annual transition without relying on a
single final summary. When `psutil` is available, `resource_samples.csv`
contains periodic process-RAM, system-memory, CPU, and free-disk observations
throughout the run.

## CMMA benchmark matrix

For the complete Costa de Manguezais de Macromaré da Amazônia (CMMA), use the
same aligned land-cover raster and ANADEM Digital Terrain Model for every run.
Record the following factors explicitly:

| Factor | Recommended levels |
| --- | --- |
| Engine | continuous; persistent blocks |
| Block size | 10,000 cells for the baseline; 100,000 and 1,000,000 for sensitivity |
| Simulation horizon | one-year smoke test; 20-year throughput test; 75-year article run |
| Annual state export | disabled for pure engine timing; enabled for an output-cost run |
| Soil/suitability | disabled and documented when reproducing the current CMMA baseline |
| Repetitions | at least three after one warm-up run per configuration |

For every repetition, preserve the complete run directory, the computer
description, Python and package versions, input hashes, and the exact
configuration. Report median and range rather than the fastest run alone.

## Correctness checks

Performance is only interpretable after equivalence has been checked. For
continuous and block runs with identical inputs and parameters:

1. compare every annual class-count row;
2. compare the final state raster cell by cell;
3. compare transition totals by source and destination class;
4. record the maximum absolute difference and the number of differing cells;
5. retain the output manifest and hashes.

The expected result for equivalent engines is zero differing cells and equal
annual trajectories. A performance improvement that changes states must be
reported as a scientific discrepancy, not as an optimization.

The repository includes `scripts/compare_runs.py` to produce a JSON report
with trajectory differences and final-raster cell differences from two run
directories.

## Article figures and tables

The software article should include, at minimum:

- a system diagram showing input validation, class mapping, annual transition,
  output generation, and the two processing engines;
- a table describing the computer, operating system, Python version, raster
  dimensions, active-cell count, and parameter set;
- a runtime-throughput plot by engine and block size;
- a peak-RSS and output-size plot;
- an equivalence table with differing-cell counts and annual trajectory checks;
- a short limitations paragraph explaining that benchmark results depend on
  storage, CPU load, raster export settings, and input geometry.

The CMMA benchmark is a performance and reproducibility experiment. It is not
by itself an ecological validation of the model.
