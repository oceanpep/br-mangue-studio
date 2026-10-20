# Full-CMMA five-year forcing checks — 20 October 2026

BR-MANGUE Studio 1.4.0 completed two five-year continuous-engine runs on the
complete prepared CMMA domain: **77,061,011 valid cells**, 30 m, EPSG:10857.
Each run updated **385,305,055 cells** from the 2025 input state to 2030 and
exported five annual GeoTIFFs (2026–2030). This is a software-operation and
forcing-equivalence test, not a calibrated ecological projection.

## Configuration and result

The first run imported the prepared IPCC AR6 medium-confidence SSP2-4.5 p50
regional curve ([source archive](https://doi.org/10.5281/zenodo.6382554));
the second used its equivalent constant rate for this interval,
4.7 mm/year. Both have zero change at 2025 and 23.5 mm cumulative change at
2030. The complete curve changes rate in later decades.

Both runs used fixed surface accretion of 2.4 mm/year, a three-year maturation
delay, no suitability layer, migration enabled without that layer, and the
same default class mapping. The tidal-influence height of 6 m is an operational
test value and does not constitute a regional vertical-datum calibration.
The input manifest and exact class mapping are preserved in the JSON record.

All five annual state-raster pairs were identical cell by cell. The annual
state/transition metrics matched, and the forcing values matched within
1e-9 mm. All annual rasters retained the initial valid domain, CRS, transform,
dimensions and NoData=0; both final rasters matched their 2030 annual state.

## Descriptive measurements

| Configuration | Load (s) | Simulation (s) | Cell updates/s | Simulation RSS peak (GiB) | Whole-process sampled RSS peak (GiB) |
| --- | ---: | ---: | ---: | ---: | ---: |
| SSP2-4.5 CSV | 37.6 | 965.7 | 399,007 | 6.00 | 9.69 |
| Constant 4.7 mm/year | 41.0 | 965.0 | 399,278 | 5.79 | 9.41 |

There is one run per configuration. Loading was measured separately; simulation
time includes annual state writes. The external supervisor sampled process RSS
every two seconds, including input loading; the runner sampled the simulation
phase every second. The host was in ordinary use and swap was enabled.
The reported simulation peak includes all periodic samples and was checked
against the complete trace. These measurements describe these executions and
do not establish a performance
difference between forcing modes. An earlier attempt stopped before its fifth
year with execution-session exit 143 and is excluded from successful timings.
Another completed pair exposed a flooding-boundary discrepancy from floating-
point cancellation. A 17 × 17 real-data regression fixture reproduced it. Both
forcing modes now use a common 1e-12 m precision, recorded in metadata. The two
full-domain runs reported here were repeated after that correction; all failed
or interrupted attempts remain separately identified in the research workspace.

The host has an Intel Core i3-1215U (six physical cores/eight logical CPUs) and
20,116,140,032 bytes of usable RAM. Maximum CPU frequency of 4.4 GHz and
DDR4-3200 memory were supplied by the user; they were not measured during the
run. The source runner used Python 3.12.14 on Ubuntu Linux; exact platform,
inputs, source revision, parameters, timings and counters are in the
[JSON record](CMMA_TRAJECTORIES_20261020.json).

## Additional checks

- 88 local automated tests passed, including calendar interpolation, rebasing,
  analytical nonlinear increments, engine equivalence, project portability,
  CSV errors, and English/Brazilian Portuguese desktop controls.
- Linux and Windows CI builds passed packaged constant/trajectory checks with
  both engines. The Linux binary also passed those checks on this computer.
- All three regional SSP curves completed five-year continuous runs on the
  preserved real CMMA tile (11,471 valid cells). Their increases through 2030
  were 24.0, 23.5 and 25.0 mm for SSP1-2.6, SSP2-4.5 and SSP5-8.5 respectively.
- A separate 75-year real-tile test previously matched all 75 annual state
  pairs between continuous and persistent-block execution.

## Reproduce

Use the three aligned prepared files in the input manifest and the preserved
SSP2-4.5 CSV. The source CLI retains metres per annual step for constant rates:

```bash
python -m brmangue_lua.raster_cli \
  --land-cover mapbiomas_c11_30m_cmma_2025_epsg10857.tif \
  --elevation anadem_mde_cmma_30m_epsg10857.tif \
  --mask mascara_cmma_epsg10857_30m.tif --disable-soil \
  --initial-year 2025 --final-year 2030 --engine continuous \
  --tide-height 6 --accretion-rate-mm 2.4 --migration-maturity-years 3 \
  --sea-level-trajectory cmma_ssp245_p50_2020_2100.csv --output run_curve
```

Repeat with `--sea-level-rise-rate 0.0047` instead of
`--sea-level-trajectory ...`, and a separate output directory. The GUI equivalent
is **4.7 mm/year**. Compare every annual raster and all non-timing trajectory
columns. Full input data and output rasters stay in the research workspace;
the repository preserves their hashes and the compact verification record.
