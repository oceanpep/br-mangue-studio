# BR-MANGUE Studio — technical model documentation

**Documented version:** 1.4.5 · **Language:** English · **Scope:** rules
implemented by the BR-MANGUE Studio raster engine.

[Leia esta documentação em português](MODEL_DOCUMENTATION_PT.md).

This document describes software behavior, not a single research protocol. Sea-level forcing, tidal influence height, land-cover mapping, accretion, and maturation parameters must be selected and justified for each application. The rules below were checked against version 1.4.5 source code. The previous technical supplement described version 1.4.4; this document updates it to version 1.4.5, including the flooded migrated-mangrove state.

<a id="contents"></a>
## Contents

1. [Purpose and scope](#1-purpose-and-scope)
2. [Spatial structure and variables](#2-spatial-structure-and-variables)
3. [Accepted input data](#3-accepted-input-data)
   - [Trajectory CSV](#trajectory-csv)
4. [Classes, profiles, and states](#4-classes-profiles-and-states)
5. [Forcing and parameters](#5-forcing-and-parameters)
6. [Transition rules](#6-transition-rules)
   - [Flooding and local redistribution](#61-flooding-and-local-redistribution)
   - [Migration eligibility](#62-migration-eligibility)
   - [Migrated-mangrove maturity](#63-migrated-mangrove-maturity)
   - [Soil-suitability layer](#64-soil-suitability-layer)
   - [Vertical accretion](#65-vertical-accretion)
   - [Comparison with the antecedent model](#comparison-with-the-antecedent-model)
   - [Rule and equation provenance](#rule-and-equation-provenance)
7. [Annual update order](#7-annual-update-order)
8. [Execution engines](#8-execution-engines)
9. [Outputs and metrics](#9-outputs-and-metrics)
10. [Interpretation and limitations](#10-interpretation-and-limitations)
11. [Reproducibility and citation](#11-reproducibility-and-citation)
12. [References](#12-references)

<a id="1-purpose-and-scope"></a>
## 1. Purpose and scope

BR-MANGUE Studio is a research application for running and inspecting spatial scenarios of mangrove change under sea-level rise. Its engine represents a landscape as a grid of cells and applies local flooding, migration, and accretion rules in annual steps. It is based on cellular automata: each cell has a state and attributes, and its update depends on local conditions and neighboring cells (Wolfram, 1983; O’Sullivan, 2001).

The Studio continues the conceptual line of the model by Bezerra et al. (2014), developed for Maranhão Island, Brazil. The current software is a new computational implementation. Its behaviors, parameters, and equations should be read from this documentation and from the state catalog saved for each run. Equations stated here as current rules describe code version 1.4.5; they are not literal transcriptions of the equations in Bezerra et al.

The software supports explicit scenario construction, inspection of transitions, and comparison of results under documented inputs and parameters. It does not provide a validated forecast for every coastline.

<a id="2-spatial-structure-and-variables"></a>
## 2. Spatial structure and variables

The model domain is the set of valid pixels remaining after input NoData values, excluded classes and, when supplied, a study-area mask are combined. Each valid cell $i$ stores:

- $c_i^t$: land-cover state at annual step $t$;
- $z_i^t$: relative elevation in metres;
- $u_i^t$: soil/suitability class, when enabled;
- $a_i^t$: internal age of migrated mangrove, when applicable.

Step $t=0$ is the initial map in the calendar year supplied by the user. Each subsequent step represents one year. A Moore neighborhood contains up to eight contiguous cells, including diagonals. Cells outside the raster or outside the valid domain are omitted; opposite grid edges are not connected.

~~~mermaid
flowchart LR
    A[Categorical land cover] --> D[Valid grid and state catalog]
    B[Aligned elevation] --> D
    C[Optional mask and soil] --> D
    D --> E[Initial state]
    E --> F[Annual step: flooding, migration, accretion]
    F --> G[Maps, tables, trajectories, metadata]
    G -->|next year| F
~~~

<a id="3-accepted-input-data"></a>
## 3. Accepted input data

The desktop application and raster command-line workflow use GeoTIFF files. BR-MANGUE Studio does not require a particular data provider. The source legend, units, resolution, horizontal reference system, and vertical datum must be known and documented.

| Input | Required? | Type and purpose |
| --- | --- | --- |
| Land cover | Yes | Categorical GeoTIFF with integer class codes. Multiband files are allowed; the user selects a band. The class year is user-supplied metadata. |
| Elevation | Yes | Continuous GeoTIFF; band 1 is read and used as elevation in metres. |
| Study-area mask | No | Aligned GeoTIFF; nonzero pixels are included, while zero and NoData pixels are excluded. |
| Soil/suitability | No | Aligned integer categorical GeoTIFF. It participates only when enabled. |
| Sea-level trajectory | No | UTF-8 CSV with columns `year` and `sea_level_mm`; an alternative to the constant rate. |

Land cover, elevation, and optional rasters must have the same rows and columns, CRS, spatial transform, and pixel alignment. The application does not silently resample these files during loading. NoData, NaN, and infinite values do not form active cells. Source code zero is also excluded; other source codes must be mapped or explicitly excluded.

Elevation raster values are read as metres and are not automatically converted
from feet, centimetres, or another unit.

A pixel is valid only when its land-cover value is non-NoData and nonzero, its elevation is non-NoData and finite, it is included by the mask, and its source class has not been excluded. Use a coordinate system appropriate for the spatial resolution. Tidal influence height and elevation must use compatible vertical datums; the Studio does not convert vertical datums.

<a id="trajectory-csv"></a>
### Trajectory CSV

Each CSV represents one time series, location or regional summary, scenario, and percentile. Its values are cumulative sea-level changes in millimetres relative to one common reference period; they are not annual rates.

~~~csv
year,sea_level_mm
2020,0
2030,40
2040,90
~~~

Years must be whole numbers, unique and increasing; levels must be finite. The series must cover the simulation start and end years. The engine interpolates missing years linearly, does not extrapolate, and subtracts the interpolated level at the initial year so that applied change starts at zero. Comma and semicolon delimiters are accepted; decimal commas are supported with a semicolon delimiter. See [Sea-level forcing](SEA_LEVEL_TRAJECTORIES.md) for preparation details.

<a id="4-classes-profiles-and-states"></a>
## 4. Classes, profiles, and states

Source raster numbers have no universal meaning in the engine. During class mapping, each source code is assigned a behavior profile. Several source codes may share one profile, while the project catalog and reports retain the link to the original class.

| Behavior profile | Role in the rules |
| --- | --- |
| **Mangrove** | Initial state that can propagate migration and receives accretion; it can become flooded. |
| **Suitable for migration** | Aggregated category of source classes allowed to receive mangrove, subject to the other rules. It can be flooded before conversion. |
| **Water** | Source for local flood propagation; it is not a migration destination and does not have its own flooded state. |
| **Anthropized area** | Cannot receive migration; it may change to its derived flooded state. |
| **Blocked area** | Cannot receive migration; it may change to its derived flooded state. |
| **Fixed class** | Retains its state and is not converted by flooding or migration rules. |

The legacy **Bare soil** profile is interpreted as **Blocked area**. In the reference mapping based on MapBiomas Collection 11, apicum (class code 32) is one of the classes that can be assigned to **Suitable for migration**. This is a configurable classification choice, not an automatic ecological rule; the legend and hypothesis of each application must be checked.

The MapBiomas reference mapping bundled with the software starts with these
source-code groups:

| Initial profile | Source codes |
| --- | --- |
| Mangrove | 5 |
| Suitable for migration | 6, 11, 12, 23, 32, 49, 50 |
| Water | 33 |
| Anthropized area | 14, 15, 18, 19, 20, 21, 24, 25, 30, 35, 36, 39, 40, 41, 46, 47, 48, 62 |

These associations are starting values for class mapping, not a claim that
all source classes are ecologically equivalent. In standard mode, observed
codes outside these lists default to **Anthropized area** until the user
remaps or excludes them. In custom mode, every observed code must be assigned
to a class or excluded. The bundled MapBiomas Collection 11 legend helps
identify original class names; also consult the [official MapBiomas Brazil
30 m Collection 11 legend documentation](https://brasil.mapbiomas.org/iniciativas-e-produtos/cobertura-e-uso-da-terra/cobertura-30m/cobertura/).

The project state catalog creates derived states as needed, such as **Migrated mangrove**, **Flooded mangrove**, and **Flooded migrated mangrove**. Derived numeric codes are allocated for each project. Read `model_state_catalog` in `metadata.json` or the raster metadata instead of assuming that numeric codes are fixed across projects.

In version 1.4.5, migrated mangrove reached by the flooding rule becomes **Flooded migrated mangrove**. It no longer counts as active mangrove and can no longer propagate migration. Source classes and the final state remain identifiable in transition tables and in the migration-by-source-class summary.

<a id="5-forcing-and-parameters"></a>
## 5. Forcing and parameters

| Parameter | Meaning and units | Initial Studio setting |
| --- | --- | --- |
| Initial/final year | Calendar years of the input map and last state. | 2025–2035. |
| Tidal influence height $T$ | Threshold in metres, using the same vertical datum as elevation. | 6.0 m; must be justified for each study. |
| Sea-level forcing | Constant rate in mm/year or CSV of cumulative levels in mm. | Constant 0.5 mm/year; annual trajectory is also available. |
| Surface accretion | Constant rate in mm/year. An empty field uses the empirical relation in Section 6.5. | Empty. |
| Maturation delay $M$ | Complete years before migrated mangrove can propagate. | 3 years. |
| Migration without suitability layer | Allows the soil filter to be skipped when no soil layer is enabled; neighborhood and elevation conditions remain. | Enabled initially when the layer is off. |
| Engine and block size | Execution strategy and cells per block for the persistent engine. | Blocks; initial size 10,000 cells. |

These initial values are application settings, not universally recommended parameters. Record the values actually used in each study.

### Sea-level forcing calculation

In the desktop interface, the constant rate is entered in mm/year and
converted to metres per annual step. For constant rate $r$ in m/year,
cumulative change and step increment are

$$H_t=tr, \qquad \delta H_t=r \quad (t\geq1),$$

with $H_0=0$. In CSV mode, let $L(y)$ be the interpolated cumulative level in
mm for calendar year $y$, and let $y_0$ be the initial year. The engine uses

$$H_t=\frac{L(y_0+t)-L(y_0)}{1000}, \qquad
\delta H_t=\frac{L(y_0+t)-L(y_0+t-1)}{1000}.$$

Both values are therefore in metres. $H_t$ feeds threshold $Z_t$, whereas
$\delta H_t$ is used for local flood redistribution and the accretion
regression. The desktop interface accepts the rate in mm/year. For legacy
unit compatibility, the command-line parameter `--sea-level-rise-rate` uses
metres per annual step.

<a id="6-transition-rules"></a>
## 6. Transition rules

<a id="61-flooding-and-local-redistribution"></a>
### 6.1 Flooding and local redistribution

Let $H_t$ be cumulative sea-level change since the simulation start and $\delta H_t$ its annual increment, both converted to metres. The tidal influence height used for migration is

$$Z_t = T + H_t.$$

Flooding propagates from cells whose state at the start of the year is water or flooded and whose elevation at the start of the step is nonnegative. For a source cell $i$, the set of valid lower-elevation neighbors is

$$\mathcal{L}_i^t = \{j \in \mathcal{N}_i : z_j^t < z_i^t\}.$$

The annual increment is divided equally between the source and those neighbors:

$$q_i^t = \frac{\delta H_t}{1 + |\mathcal{L}_i^t|}.$$

The engine adds $q_i^t$ to the current elevation of the source and each lower neighbor. A neighbor that was not already water or flooded changes to the flooded state corresponding to its base class, when that state is defined in the catalog. Lower-elevation comparisons and source states are read from the start-of-year snapshot. Newly flooded cells can contribute as sources only in the next year. Multiple sources can contribute to one cell in the same year.

Tidal height $T$ and threshold $Z_t$ define migration eligibility; flood
propagation follows the local rule above, starting from water or flooded
states.

This is a local rule implemented in BR-MANGUE Studio, conceptually continuing the antecedent model of Bezerra et al. (2014). It is not a hydrodynamic solution or a literal reproduction of that paper's equation. The engine does not calculate salinity, current velocity, detailed hydraulic connectivity, or a water mass balance.

<a id="62-migration-eligibility"></a>
### 6.2 Migration eligibility

Original mangrove and mature migrated mangrove may act as sources. A cell can receive migration only when all of the following conditions are met:

1. it is in the source cell's Moore neighborhood;
2. its profile is **Suitable for migration**;
3. its current elevation is $z_j \leq Z_t$;
4. it passes the soil filter when that layer is enabled.

In compact notation, let $\mathcal{C}_{\mathrm{suitable}}$ be the set of
classes with the **Suitable for migration** profile and let $Q_j^t$ be the
soil condition. For a source $i$, neighbor $j$ is eligible when

$$E_{ij}^{t,\mathrm{visit}} = \mathbf{1}[j \in \mathcal{N}_i]
\mathbf{1}[c_j^{t,\mathrm{visit}} \in \mathcal{C}_{\mathrm{suitable}}]
\mathbf{1}[z_j^{t,\mathrm{visit}} \leq Z_t]\mathbf{1}[Q_j^{t,\mathrm{visit}}].$$

The factor $\mathbf{1}[Q_j^t]$ is 1 when the soil filter is skipped or when
the destination has an accepted soil profile. Conversion occurs only when
$E_{ij}^t=1$ and cell $i$ meets the source rule described in the next section.

When accepted, the cell receives the **Migrated mangrove** state, starts at age zero, and ceases to be a suitable land-cover class. The rule traverses cells sequentially: flooding reads start-of-year states and elevations, whereas soil and migration read current values when each cell is visited. The maturation delay prevents a newly converted cell from immediately opening a new front.

<a id="63-migrated-mangrove-maturity"></a>
### 6.3 Migrated-mangrove maturity

Parameter $M$ is the configured number of complete years. Original mangrove can be a source immediately; migrated mangrove becomes a source only when its age reaches $M$. A newly converted cell receives age 0. With the default $M=3$, it must complete three annual steps before propagating. If it is flooded before then, it becomes **Flooded migrated mangrove**, its age is cleared, and it ceases to be a source.

The age counter is a configurable operational rule, not an automatic estimate of reproductive age for any species or location. Research on early reproduction in *Rhizophora mangle* provides context for biological variation, but does not calibrate the default value for all forests (Dangremond & Feller, 2016).

The source test can be summarized as

$$P_i^{t,\mathrm{visit}} = \mathbf{1}[c_i^{t,\mathrm{visit}}=\mathrm{mangrove}]
\lor\left(\mathbf{1}[c_i^{t,\mathrm{visit}}=\mathrm{migrated\ mangrove}]
\mathbf{1}[a_i^{t,\mathrm{visit}}\geq M]\right).$$

When converted to migrated mangrove, a cell's age starts at zero. It advances
in later steps while the state remains active. The superscript `visit` denotes
current values at the point when the cell is examined in the annual traversal,
not a simultaneous state computed for the whole grid.

<a id="64-soil-suitability-layer"></a>
### 6.4 Soil-suitability layer

The layer is optional. When enabled, it must be aligned with the other rasters and use integer codes recognized by the rule: 0 (channel), 3 (mangrove soil), and 9 (migrated-mangrove soil). These are internal soil-layer profiles, not land-cover codes.

Mangrove soil and channel profiles can pass the migrated-soil profile to neighboring suitable cells at or below $Z_t$; cells already assigned mangrove soil are not overwritten. A mature migrated cell with profile 9 can also propagate that profile. For land-cover conversion, when the layer is enabled, the destination must have soil profile 3 or 9. If the layer is disabled and **Allow migration without suitability layer** is checked, the soil filter is skipped. Class profile, neighborhood, and elevation conditions still apply.

<a id="65-vertical-accretion"></a>
### 6.5 Vertical accretion

The user may supply a constant rate $A$ in mm/year. If the field is empty, the engine uses the empirical regression attributed to Alongi (2008, Fig. 7):

$$A_t = 1.693 + 0.939x_t,$$

where $x_t = 1000\,\delta H_t$ is the annual sea-level increment in mm/year, and $A_t$ is also in mm/year. The value is converted to metres and applied to elevation at each step. Accretion is applied to states with mangrove behavior: original mangrove, migrated mangrove, and their flooded states. A supplied fixed rate replaces the regression for the entire run. This empirical equation is not a sediment mass-conservation law or a site-specific calibration; studies may substitute a documented rate.

In general, the applied rate is $A_t=A_{\mathrm{user}}$ when a constant rate
is supplied; otherwise, the regression above is used. The elevation adjustment
is $\Delta z_{i,\mathrm{accretion}}^t=A_t/1000$ metres per annual step.

<a id="comparison-with-the-antecedent-model"></a>
### Comparison with the antecedent model

Bezerra et al. (2014) describe the antecedent formulation for sea-level rise, flooding, and mangrove migration on Maranhão Island. The current version retains the cellular approach and local spatial propagation, but its forcing, increment distribution, behavior mapping, configurable maturation, accretion treatment, raster processing, and flooded states are those implemented in version 1.4.5. Cite the 2014 article as the conceptual and historical antecedent; use this documentation and the software release to describe what the Studio executes.

<a id="rule-and-equation-provenance"></a>
### Rule and equation provenance

| Component | Provenance and attribution |
| --- | --- |
| Cellular automaton and Moore neighborhood | Established modelling concepts; the raster grid and eight-cell neighborhood are implementation choices (Wolfram, 1983; O’Sullivan, 2001). |
| Antecedent mangrove model | Bezerra et al. (2014) is the conceptual and historical reference for the Maranhão Island application; it is not the literal specification of engine 1.4.5. |
| Constant or CSV forcing | Unit conversion, linear interpolation, and rebasing to the initial year are software input rules. The file and its source define the climate scenario. |
| Local flood redistribution | Operational equation implemented in BR-MANGUE Studio; it should not be attributed as a literal equation from Bezerra et al. (2014). |
| Accretion | Empirical relation from Alongi (2008, Fig. 7), used when no constant rate is supplied; a study-specific value overrides it. |
| Maturation and eligibility | Configurable software parameters and conditions. Mangrove reproductive literature provides biological context, but does not calibrate the three-year default for every location (Dangremond & Feller, 2016). |
| Extent, gains, and losses | Operational definitions of states and metrics in the code; flooded states are counted separately from active extent. |

<a id="7-annual-update-order"></a>
## 7. Annual update order

At each step, the engine preserves the start-of-year states, elevations, and migration ages, and calculates the forcing ($H_t$, $\delta H_t$, $Z_t$, and accretion). It then traverses valid cells in stored order. For each cell, it advances age if it was already migrated mangrove, applies the flooding contribution indicated by the snapshot, updates soil profiles, checks migration, and applies accretion. Cover changes from flooding and migration, and elevation adjustments, are available to subsequent current-value rules according to this visit order. At the end, the engine counts states and metrics, writes enabled outputs, and uses the resulting state as the next year's starting state.

The workflow is deterministic for the same inputs, configuration, software version, and cell order. Update order is part of the specification; it is not a simultaneous order-independent update.

<a id="8-execution-engines"></a>
## 8. Execution engines

- **Continuous:** keeps grid vectors in memory and updates each annual step.
- **Persistent blocks:** traverses cells in blocks and stores states and neighborhoods in disk-mapped files, alternating state files each year. Block size affects resource use, not the neighborhood or ecological parameters.
- **DissModel adapter:** a compatibility path that runs the rules through the continuous or block engine when the optional component is available.

Continuous and persistent-block engines use the same cell order and transition rules. Blocks reduce the need to keep complete state vectors in RAM, but require temporary disk space and may be slower depending on the hardware and block size.

<a id="9-outputs-and-metrics"></a>
## 9. Outputs and metrics

Depending on run options, the results folder may contain:

| File/output | Contents |
| --- | --- |
| `initial_state_<year>.tif` | Initial-year model states and classes. |
| `states/state_<year>.tif` | Annual model-state raster. |
| `final_state_<year>.tif` | Final state of the run. |
| `trajectory.csv` | State counts, minimum/maximum elevation, sea-level changes, and annual metrics. |
| `sea_level_forcing.csv` | Annual forcing, including cumulative change and increment. |
| `input_metadata.json` | Grid, CRS, resolution, mask, legend, and input mapping. |
| `metadata.json` | Version, parameters, engine, state catalog, timings, metrics, and run provenance. |
| `resource_samples.csv` | Resource-use samples, when collection is available. |
| `transition_by_land_cover_code.csv` | Transitions linked to original source codes and names. |
| `migration_by_source_class.csv` | Migration summary by original class, distinguishing active and flooded mangrove. |

Transition and migration reports are exported by the desktop workflow; files may vary with execution mode and selected options. GeoTIFFs store project state codes, which must be interpreted through the catalog in `metadata.json`.

The `mangrove_extent` metric counts unflooded original mangrove and active migrated mangrove. Flooded mangrove and flooded migrated mangrove are counted separately and excluded from active extent. Annual gain counts cells entering active extent; annual loss counts cells leaving it. Thus, a flooded mangrove cell contributes to active loss while its flooded area remains recorded as a separate state.

The nominal number of cell-year updates is $U=N\times T$, where $N$ is the number of valid cells and $T$ is the number of computed annual steps. It counts spatial units updated per step; it is not the number of years per run.

<a id="10-interpretation-and-limitations"></a>
## 10. Interpretation and limitations

BR-MANGUE Studio spatializes an explicit set of rules. It does not solve hydrodynamic equations or directly represent salinity, daily tides, waves, propagule transport, species differences, population dynamics, mortality from other causes, or a sediment mass balance. A sea-level rate or trajectory does not correct the raster's vertical datum. Suitable, blocked, and flooded areas depend on each application's class mapping and assumptions.

Interpret results as scenarios conditional on the inputs and documented rules. A scientific application should report raster sources and processing, vertical reference, classes and source codes, sea-level forcing, parameters, soil options, software version, and independent calibration or validation procedures. Computational performance and execution checks do not replace independent ecological evaluation.

<a id="11-reproducibility-and-citation"></a>
## 11. Reproducibility and citation

To reproduce a run, archive original and prepared rasters, legends, mask, class configuration, sea-level data, parameters, project file, output metadata, and exact software version. Projects with CSV trajectories store the samples and source hash; each run records the annual forcing used.

The DOI for release 1.4.5 is [10.5281/zenodo.24018559](https://doi.org/10.5281/zenodo.24018559). The [GitHub repository](https://github.com/oceanpep/br-mangue-studio) hosts source code and releases.

<a id="12-references"></a>
## 12. References

- Alongi, D. M. (2008). Mangrove forests: Resilience, protection from tsunamis, and responses to global climate change. *Estuarine, Coastal and Shelf Science*, 76(1), 1–13. [https://doi.org/10.1016/j.ecss.2007.08.024](https://doi.org/10.1016/j.ecss.2007.08.024).
- Bezerra, D. da S., Amaral, S., Kampel, M., & Andrade, P. R. (2014). Simulating sea-level rise impacts on mangrove ecosystem adjacent to anthropic areas: The case of Maranhão Island, Brazilian Northeast. *Pan-American Journal of Aquatic Sciences*, 9(3), 188–198. [Article PDF](https://panamjas.org/pdf_artigos/PANAMJAS_9(3)_188-198.pdf).
- Dangremond, E. M., & Feller, I. C. (2016). Precocious reproduction increases at the leading edge of a mangrove range expansion. *Ecology and Evolution*, 6(14), 5087–5092. [https://doi.org/10.1002/ece3.2270](https://doi.org/10.1002/ece3.2270).
- O’Sullivan, D. (2001). Exploring spatial process dynamics using irregular cellular automaton models. *Geographical Analysis*, 33(1), 1–18. [https://doi.org/10.1111/j.1538-4632.2001.tb00433.x](https://doi.org/10.1111/j.1538-4632.2001.tb00433.x).
- Sousa, F. M., Bezerra, D. da S., Costa, S. S., & Santos, R. L. (2026). *BR-MANGUE Studio* (version 1.4.5) [software]. Zenodo. [https://doi.org/10.5281/zenodo.24018559](https://doi.org/10.5281/zenodo.24018559).
- Wolfram, S. (1983). Statistical mechanics of cellular automata. *Reviews of Modern Physics*, 55(3), 601–644. [https://doi.org/10.1103/RevModPhys.55.601](https://doi.org/10.1103/RevModPhys.55.601).
- MapBiomas Brasil. (2026). *Brazil land cover and land use, 30 m — Collection 11: class codes and legend description*. [Official page](https://brasil.mapbiomas.org/iniciativas-e-produtos/cobertura-e-uso-da-terra/cobertura-30m/cobertura/).
