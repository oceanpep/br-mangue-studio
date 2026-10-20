# Sea-level forcing

Version 1.4.0 offers two choices in **Simulation**:

- **Constant rate** (default) preserves earlier projects. The desktop field
  accepts mm/year.
- **Year-based trajectory (CSV)** reads cumulative levels for calendar years.
  It disables the constant-rate field. **Preview curve** displays the rise
  relative to the initial raster year.

## Input and calculations

### Create a CSV in a spreadsheet

1. In **Simulation**, select **Save CSV example**, or download
   [the example](../examples/sea_level_SYNTHETIC_example.csv). Its values are
   synthetic and must be replaced before research use.
2. Open the file in Excel or LibreOffice Calc. The first line beginning with
   `#` is a comment; it may be removed. Keep the header `year,sea_level_mm`.
3. Obtain regional cumulative projections from the
   [NASA/IPCC AR6 tool](https://sealevel.nasa.gov/data_tools/17), the
   [original IPCC archive](https://doi.org/10.5281/zenodo.6382554), or the
   [Earth Engine catalog](https://developers.google.com/earth-engine/datasets/catalog/IPCC_AR6_SLP).
   The source download is not necessarily in the application's CSV format.
4. Select one scenario and percentile, and one location or documented spatial
   summary. Copy its calendar years to `year` and cumulative **total** levels
   to `sea_level_mm`. All levels must use the same reference period.
   Convert metres × 1000 or centimetres × 10 to millimetres. Do not copy
   annual rates into this column.
5. Include samples covering the initial and final simulation years. For a
   2025–2100 run, the decadal 2020–2100 samples cover the interval: 2025 is
   interpolated between 2020 and 2030. Annual rows are also accepted.
6. Save as **CSV UTF-8**, without a title above the header, formulas, units
   inside numeric cells, or thousands separators. A comma separator requires
   decimal points; a semicolon separator also accepts decimal commas.
7. Select **Year-based trajectory (CSV)**, choose the file, and check
   **Preview curve** before running. Keep source, region, scenario, percentile,
   reference period and unit-conversion notes beside the CSV. The model
   embeds imported samples in the saved project.

**Format and data sources** provides these instructions offline inside the
application. The source links require an internet connection. Projections
remain future scenarios when rebased to a recent year. A measured trend is
entered separately through **Constant rate**.

Provide one trajectory per CSV with these exact column names:

```csv
year,sea_level_mm
2020,100
2030,140
2040,220
```

**These values are synthetic examples, not IPCC projections.** Values are
cumulative levels in mm relative to one common reference period, rather than
mm/year rates. Years must be unique integers in increasing order and levels
must be finite. At least two samples must cover the complete simulation period.
Extrapolation is rejected. Comma-delimited CSVs and semicolon-delimited CSVs
with decimal commas are accepted. Extra columns are ignored; each file should
contain only one scenario, region and percentile.

Linear interpolation supplies intermediate years. The engine subtracts the
initial-year value. In the example, a 2025 start interpolates 120 mm; the
additional rise is 4 mm/year through 2030 and 8 mm/year afterwards, reaching
100 mm after 2025 in 2040. The initial 120 mm is not added to the raster.

For input level `P(year)` in mm and initial year `y0`:

```text
cumulative_change_m(t) = (P(y0 + t) - P(y0)) / 1000
annual_increment_m(t) = (P(y0 + t) - P(y0 + t - 1)) / 1000
tidal_influence_height_m(t) = tide_height + cumulative_change_m(t)
```

Both forcing modes use a common numerical precision of `1e-12 m` for cumulative
change and annual increments before applying cell rules. This removes binary
round-off differences at exact flooding boundaries for equivalent linear curves
and constant rates. The resolution is recorded in forcing metadata.

The annual increment supplies the existing local water redistribution rule.
The optional Alongi accretion regression uses that year's increment in mm/year.
An explicit fixed accretion value remains constant. Continuous and persistent
blocks share the forcing calculation, performed once per step outside cell
loops. No monotone acceleration is imposed. Existing flooded states retain
their rules; a declining curve does not add ecological recovery transitions.
Rebasing changes does not establish the absolute vertical reference of the DEM
or the initial tidal-influence threshold.

The [IPCC AR6 Earth Engine product](https://developers.google.com/earth-engine/datasets/catalog/IPCC_AR6_SLP)
provides cumulative projections at decadal intervals. Export `year` and the
chosen `total_values_quantile_*` for a documented region/scenario/percentile.
Retain the 2020 sample when starting in 2025. The
[original archive](https://doi.org/10.5281/zenodo.6382554) is also available.
The application accepts trajectories from any suitable source. An observed
contemporary trend requires observational data with a stated period; rebasing
an IPCC projection does not turn it into an observation.

## Reproducibility and command line

Project format 0.4.0 embeds source samples, units, interpolation, filename and
CSV SHA-256. Embedded samples have priority on reopening, so moving/deleting
the CSV cannot change a saved project. Reselect a CSV to import a revised
source. Older projects default to constant forcing.

Raster runs export `sea_level_forcing.csv`, including zero change in the initial
year and subsequent annual changes/increments. `trajectory.csv` adds
`sea_level_change_mm` and `sea_level_increment_mm`. `metadata.json` records the
mode, reference year and complete source samples; its legacy scalar-rate field
is null in trajectory mode.

The raster CLI accepts `--sea-level-trajectory curve.csv`, `--initial-year` and
`--final-year`. Trajectory input is mutually exclusive with
`--sea-level-rise-rate`; the older CLI rate retains **metres per annual step**,
while GUI rates use mm/year. Python users pass a `SeaLevelTrajectory` to
`ModelParameters` and set `sea_level_reference_year` to the initial raster year.

## Configuração em português

Baixe o exemplo no site ou clique em **Salvar exemplo CSV** na aba **Simulação**.
Abra no Excel ou LibreOffice Calc e substitua os valores sintéticos pelos
níveis acumulados de uma fonte documentada. Mantenha os cabeçalhos `year` e
`sea_level_mm`; use um arquivo por local ou síntese regional, cenário e
percentil. Converta metros em milímetros multiplicando por 1000, ou centímetros
por 10. Salve como CSV UTF-8 e confira a curva antes de executar.
**Formato e fontes de dados** explica o procedimento no próprio programa.

Na aba **Simulação**, escolha **Taxa constante** ou **Trajetória por ano (CSV)**.
Selecione um arquivo com as colunas `year` e `sea_level_mm`, contendo níveis
acumulados em mm. **Visualizar curva** mostra a elevação desde o ano inicial.
Para 2025–2100, o CSV pode conter os valores decenais de 2020 a 2100. Use um
arquivo por cenário e percentil. O programa interpola os anos intermediários
e desconta o nível do ano inicial. A acreção constante e o atraso de maturação
mantêm os valores escolhidos. O projeto incorpora as amostras e cada execução
registra a curva anual usada em `sea_level_forcing.csv`.
