# Synthetic grid capacity benchmarks

These scripts and records document five-year performance and capacity checks
on synthetic rasters. The inputs use arbitrary coordinates and have no
geographic or ecological interpretation. They are intended to measure the
software workflow, not ecological response.

## Latest capacity series

The largest completed continuous run in the October 2026 series used
160,000,000 valid cells and completed five annual steps, processing
800,000,000 cell updates at 364,334 updates per second. Peak process RSS
during the measured simulation was 9.07 GiB; an external monitor recorded
12.65 GiB including input loading. The 180, 200, and 240 million cell runs
were stopped by a system-memory safety guard before completion. They are not
completed simulations and do not establish a software limit.

The cumulative record is [capacity_limit_20261013.json](capacity_limit_20261013.json).
It includes the hardware and software environment, input hashes, configurations,
run outcomes, and references to raw reports and resource samples in
[`capacity_runs/`](capacity_runs/). The 160 million cell simulation metadata
and trajectory are also preserved there.

## Reproducing or extending the runs

Install the project and its dependencies from the repository root:

```sh
python -m pip install -e .
```

Run the smaller continuous and block-engine comparison:

```sh
python docs/benchmarks/capacity_tests/benchmark.py
```

Run one larger grid with resource safeguards (height and width are in cells):

```sh
python docs/benchmarks/capacity_tests/benchmark_next_capacity.py 10000 16000 continuous
```

The second script stops a run if system-available memory drops below 1.5 GiB
or free swap drops below 1 GiB. A guard stop is a safety outcome, not a model
failure. Each new run writes its report and samples under
`execucoes_limite_salto/`; generated rasters and run folders are ignored by
Git. Preserve the original records and add a dated entry to the cumulative
JSON when extending this series. The measured rate is specific to hardware,
software version, input grid, output settings, and system load.
