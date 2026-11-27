# BR-MANGUE Studio — technical model documentation

**Documented release:** 1.4.11 · **Language:** English · **Scope:** rules
implemented by the BR-MANGUE Studio raster engine.

[Leia esta documentação em português](MODEL_DOCUMENTATION_PT.md).

This is the official technical documentation for BR-MANGUE Studio. It specifies the model's purpose, input data, parameters, states, transition rules, outputs, and reproducibility procedures. Sea-level forcing, tidal influence height, class mapping, accretion, and maturation are application choices and should be reported. The rules described here correspond to the raster engine in the current BR-MANGUE Studio release.

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

BR-MANGUE Studio implements in software the cellular approach applied by Bezerra et al. (2014) on Maranhão Island. This document specifies the rules executed by the Studio; the state catalog saved with each run records the states used. Bezerra et al. (2014) is the conceptual and historical reference for that application.

Each run produces a scenario conditioned on the supplied data, parameters, and rules. The software supports transition inspection and comparison of runs with documented configurations.

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

The **Bare soil** profile is interpreted as **Blocked area**. Source raster codes do not have universal meanings. In a new desktop project, assign each observed code to a model behavior or exclude it; the software assumes no particular land-cover product or code scheme. A user-provided CSV legend can add readable source-class names to output tables. It supplies labels only and does not change class assignments or simulation rules. Without a CSV, source codes remain numeric in the reports.

The project state catalog creates derived states as needed, such as **Migrated mangrove**, **Flooded mangrove**, and **Flooded migrated mangrove**. Derived numeric codes are allocated for each project. Read `model_state_catalog` in `metadata.json` or the raster metadata instead of assuming that numeric codes are fixed across projects.

When the flooding rule reaches migrated mangrove, it becomes **Flooded migrated mangrove**. This state is excluded from active mangrove extent and cannot propagate migration. Source classes and final states remain identifiable in transition tables and in the migration-by-source-class summary.

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

These are the initial values displayed by the interface. For each study, report the parameters actually used and their sources.

### Sea-level forcing calculation

In the desktop interface, the constant rate is entered in mm/year and
converted to metres per annual step. In the equation, $r$ is this rate in
m/year; $t$ is the number of elapsed annual steps; $H_t$ is the cumulative
rise since the start, in metres; $\delta H_t$ is the rise added in step $t$,
also in metres; and $H_0=0$ defines the initial reference. Cumulative change
and annual increment are

$$H_t=tr, \qquad \delta H_t=r \quad (t\geq1),$$

In CSV mode, $L(y)$ is the interpolated cumulative level, in millimetres, for
calendar year $y$; $y_0$ is the simulation's initial year; and $t$ is the
number of annual steps since that year. The denominator 1000 converts
millimetres to metres. The engine calculates cumulative rise $H_t$ and the
increment between consecutive years $\delta H_t$ as

$$H_t=\frac{L(y_0+t)-L(y_0)}{1000}, \qquad
\delta H_t=\frac{L(y_0+t)-L(y_0+t-1)}{1000}.$$

Subtracting $L(y_0)$ sets the trajectory to zero at the start of the
simulation. Both results are in metres. $H_t$ feeds threshold $Z_t$, whereas
$\delta H_t$ is used for local flood redistribution and the accretion
regression. The desktop interface accepts the rate in mm/year. The command
line parameter `--sea-level-rise-rate` uses metres per annual step.

<a id="6-transition-rules"></a>
## 6. Transition rules

<a id="61-flooding-and-local-redistribution"></a>
### 6.1 Flooding and local redistribution

Let $T$ be the configured tidal influence height, in metres and in the same
vertical datum as the elevation raster. $H_t$ is cumulative sea-level rise
since the simulation start, also in metres. The threshold $Z_t$ used to
evaluate migration eligibility is the sum of these terms:

$$Z_t = T + H_t.$$

Flooding starts from a source cell $i$ whose state at the start of the year
is water or flooded and whose elevation is nonnegative. $\mathcal{N}_i$ is
the set of valid cells in the Moore neighborhood of $i$ (up to eight
neighbors); $j$ denotes one of those cells; and $z_i^t$ and $z_j^t$ are their
elevations, in metres, in the snapshot at the start of annual step $t$. The
set $\mathcal{P}_i^t$ contains the neighbors that receive the source's
contribution. The rule depends on the sign of annual increment
$\delta H_t$:

$$
\mathcal{P}_i^t =
\begin{cases}
\{j \in \mathcal{N}_i : |z_j^t-z_i^t| \le 10^{-12}\;\mathrm{m}\}, & \delta H_t < 0,\\
\{j \in \mathcal{N}_i : z_j^t < z_i^t\}, & \delta H_t \ge 0.
\end{cases}
$$

When the annual increment is negative, only neighbors whose relative elevation
at the start of the step equals the source elevation, within a numerical
tolerance of $10^{-12}$ m, are included; lower neighbors are excluded. For
zero or positive increments, the lower-neighbor rule is retained. The quantity
$|\mathcal{P}_i^t|$ is
the number of selected neighbors. The increment $\delta H_t$, in metres
per annual step, is divided equally between the source and those neighbors:

$$q_i^t = \frac{\delta H_t}{1 + |\mathcal{P}_i^t|}.$$

Thus, $q_i^t$ is one source's contribution to its relative elevation and to
that of each selected neighbor, in metres per annual step. The engine adds
this contribution to their current relative elevations. A neighbor that was
not already water or flooded changes to the flooded state corresponding to
its base class when that state is defined in the catalog. Elevation
comparisons and source states come from the start-of-year snapshot. Newly
flooded cells can act as sources only in the following year; multiple sources
can contribute to one cell in the same year.

A negative increment does not reverse the state of cells that were flooded in
an earlier step. It restricts which neighbors can receive new flood propagation
during that step.

Tidal height $T$ and threshold $Z_t$ define migration eligibility; flood
propagation follows the local rule above, starting from water or flooded
states.

Flooding is represented by this local propagation rule. The engine tracks
categorical states and elevation; it does not calculate salinity, current
velocity, detailed hydraulic connectivity, or water mass balance. The
cellular approach maintains conceptual continuity with Bezerra et al. (2014).

<a id="62-migration-eligibility"></a>
### 6.2 Migration eligibility

Original mangrove and mature migrated mangrove may act as sources. A cell can receive migration only when all of the following conditions are met:

1. it is in the source cell's Moore neighborhood;
2. its profile is **Suitable for migration**;
3. its current elevation is $z_j \leq Z_t$;
4. it passes the soil filter when that layer is enabled.

In compact notation, $\mathcal{C}_{\mathrm{suitable}}$ is the set of classes
with the **Suitable for migration** profile; $Q_j^{t,\mathrm{visit}}$ is true
when candidate cell $j$ passes the soil condition or when the soil filter is
disabled. The indicator function $\mathbf{1}[C]$ equals 1 when condition
$C$ is true and 0 otherwise. For a source $i$, candidate neighbor $j$ is
eligible when

$$E_{ij}^{t,\mathrm{visit}} = \mathbf{1}[j \in \mathcal{N}_i]
\mathbf{1}[c_j^{t,\mathrm{visit}} \in \mathcal{C}_{\mathrm{suitable}}]
\mathbf{1}[z_j^{t,\mathrm{visit}} \leq Z_t]\mathbf{1}[Q_j^{t,\mathrm{visit}}].$$

Each indicator factor represents one condition: $j \in \mathcal{N}_i$ checks
that the candidate is a valid neighbor; $c_j^{t,\mathrm{visit}} \in
\mathcal{C}_{\mathrm{suitable}}$ checks its class; $z_j^{t,\mathrm{visit}}\leq
Z_t$ compares its current elevation with the threshold; and
$Q_j^{t,\mathrm{visit}}$ applies the soil filter. The product equals 1 only
when all four conditions are satisfied; in that case
$E_{ij}^{t,\mathrm{visit}}=1$, and otherwise $E_{ij}^{t,\mathrm{visit}}=0$.
Conversion also requires source cell $i$ to satisfy rule
$P_i^{t,\mathrm{visit}}$ in the next section.

When accepted, the cell receives the **Migrated mangrove** state, starts at age zero, and ceases to be a suitable land-cover class. The rule traverses cells sequentially: flooding reads start-of-year states and elevations, whereas soil and migration read current values when each cell is visited. The maturation delay prevents a newly converted cell from immediately opening a new front.

<a id="63-migrated-mangrove-maturity"></a>
### 6.3 Migrated-mangrove maturity

Parameter $M$ is the configured number of complete years. $a_i^{t,\mathrm{visit}}$
is the age of migrated mangrove in cell $i$, counted in completed annual
steps; $c_i^{t,\mathrm{visit}}$ is that cell's current state. Original
mangrove can act as a source immediately; migrated mangrove becomes a source
only when its age reaches $M$. A newly converted cell receives age 0. With
$M=3$, it must complete three annual steps before propagating. If flooded
before then, it becomes **Flooded migrated mangrove**, its age is cleared,
and it ceases to be a source.

The age counter $M$ is a configurable operational parameter. Research on
early reproduction in *Rhizophora mangle* documents biological variation
that provides context for this parameter (Dangremond & Feller, 2016).

The source test can be summarized as

$$P_i^{t,\mathrm{visit}} = \mathbf{1}[c_i^{t,\mathrm{visit}}=\mathrm{mangrove}]
\lor\left(\mathbf{1}[c_i^{t,\mathrm{visit}}=\mathrm{migrated\ mangrove}]
\mathbf{1}[a_i^{t,\mathrm{visit}}\geq M]\right).$$

In the equation, $P_i^{t,\mathrm{visit}}$ equals 1 when cell $i$ can act as
a source and 0 otherwise; $\mathbf{1}[C]$ is the indicator function defined
above; $\lor$ means “or”; and the product of the two indicators in
parentheses requires both a migrated-mangrove state and an age of at least
$M$. When converted to migrated mangrove, a cell's age starts at zero and
advances in later steps while the state remains active. The superscript
`visit` identifies current values when a cell is examined in the annual
traversal.

<a id="64-soil-suitability-layer"></a>
### 6.4 Soil-suitability layer

The layer is optional. When enabled, it must be aligned with the other rasters and use integer codes recognized by the rule: 0 (channel), 3 (mangrove soil), and 9 (migrated-mangrove soil). These are internal soil-layer profiles, not land-cover codes.

Mangrove soil and channel profiles can pass the migrated-soil profile to neighboring suitable cells at or below $Z_t$; cells already assigned mangrove soil are not overwritten. A mature migrated cell with profile 9 can also propagate that profile. For land-cover conversion, when the layer is enabled, the destination must have soil profile 3 or 9. If the layer is disabled and **Allow migration without suitability layer** is checked, the soil filter is skipped. Class profile, neighborhood, and elevation conditions still apply.

<a id="65-vertical-accretion"></a>
### 6.5 Vertical accretion

The user may supply a constant rate $A_{\mathrm{user}}$ in mm/year. If the
field is empty, the engine uses the empirical regression attributed to
Alongi (2008, Fig. 7):

$$A_t = 1.693 + 0.939x_t,$$

Here, $x_t=1000\,\delta H_t$ converts the annual sea-level increment
$\delta H_t$ from metres to millimetres per year; $A_t$ is the resulting
accretion rate, also in mm/year; 1.693 mm/year is the regression intercept;
and 0.939 is its dimensionless slope because input and output use mm/year.
The calculated rate is converted
to metres and applied to elevation at each annual step. Accretion applies to
states with mangrove behavior: original mangrove, migrated mangrove, and
their flooded states. When the user supplies a constant rate, it replaces
the regression for the entire run. The empirical relation links sea-level
increment to accretion rate; an application may supply its own documented
rate.

In the command-line workflow, `--legacy-lua-accretion-typo` restricts
accretion to cells with soil profile 3 (mangrove soil). Report this option
when used because it changes which cells receive the increment.

When $A_{\mathrm{user}}$ is supplied, the applied rate is
$A_t=A_{\mathrm{user}}$; otherwise, $A_t$ comes from the regression. The
adjustment $\Delta z_{i,\mathrm{accretion}}^t=A_t/1000$ is the elevation
increase for cell $i$, in metres, during annual step $t$; division by 1000
converts millimetres to metres.

<a id="comparison-with-the-antecedent-model"></a>
### Comparison with the antecedent model

Bezerra et al. (2014) describe the reference formulation for sea-level rise,
flooding, and mangrove migration on Maranhão Island. BR-MANGUE Studio retains
the cellular approach and local spatial propagation. Its forcing,
increment distribution, behavior mapping, configurable maturation, accretion
treatment, raster processing, and flooded states are specified in this
documentation and in the software release. Cite the 2014 article as the
conceptual and historical antecedent of the application.

<a id="rule-and-equation-provenance"></a>
### Rule and equation provenance

| Component | Provenance and attribution |
| --- | --- |
| Cellular automaton and Moore neighborhood | Established modelling concepts; the raster grid and eight-cell neighborhood are implementation choices (Wolfram, 1983; O’Sullivan, 2001). |
| Antecedent mangrove model | Bezerra et al. (2014) is the conceptual and historical reference for the Maranhão Island application. |
| Constant or CSV forcing | Unit conversion, linear interpolation, and rebasing to the initial year are software input rules. The file and its source define the climate scenario. |
| Local flood redistribution | Operational equation specified in this documentation and implemented in BR-MANGUE Studio. |
| Accretion | Empirical relation from Alongi (2008, Fig. 7), used when no constant rate is supplied; a study-specific value overrides it. |
| Maturation and eligibility | Configurable software parameters and conditions. Mangrove reproductive literature provides biological context, but does not calibrate the three-year default for every location (Dangremond & Feller, 2016). |
| Extent, gains, and losses | Operational definitions of states and metrics in the code; flooded states are counted separately from active extent. |

<a id="7-annual-update-order"></a>
## 7. Annual update order

At each step, the engine preserves the start-of-year states, elevations, and migration ages, and calculates the forcing ($H_t$, $\delta H_t$, $Z_t$, and accretion). It then traverses valid cells in stored order. For each cell, it advances age if it was already migrated mangrove, applies the flooding contribution indicated by the snapshot, updates soil profiles, checks migration, and applies accretion. Cover changes from flooding and migration, and elevation adjustments, are available to subsequent current-value rules according to this visit order. At the end, the engine counts states and metrics, writes enabled outputs, and uses the resulting state as the next year's starting state.

With the same inputs, configuration, software version, and cell order, the
workflow is deterministic. The engine traverses valid cells sequentially;
this order is part of the annual update rule.

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

The nominal number of cell-year updates is $U=N\times n_{\mathrm{steps}}$,
where $N$ is the number of valid cells and $n_{\mathrm{steps}}$ is the total
number of computed annual steps. For example, a run with $N$ valid cells over
75 steps counts $75N$ cell-year updates.

<a id="10-interpretation-and-limitations"></a>
## 10. Interpretation and limitations

The engine tracks categorical land-cover states and elevation in annual steps. Salinity, daily tides, waves, propagule transport, species differences, population dynamics, mortality from other causes, and sediment mass balance are outside the simulated variables. The elevation raster and tidal height must use the same vertical datum. Suitable, blocked, and flooded areas follow the class mapping and assumptions defined for each application.

Results are scenarios conditioned on the inputs and documented rules. A scientific application should report raster sources and processing, vertical reference, classes and source codes, sea-level forcing, parameters, soil options, software version, and independent calibration or validation procedures. Ecological evaluation complements computational checks and performance tests.

<a id="11-reproducibility-and-citation"></a>
## 11. Reproducibility and citation

To reproduce a run, archive original and prepared rasters, legends, mask, class configuration, sea-level data, parameters, project file, output metadata, and exact software version. Projects with CSV trajectories store the samples and source hash; each run records the annual forcing used.

Cite BR-MANGUE Studio using the [Zenodo concept DOI](https://doi.org/10.5281/zenodo.23509308). The [GitHub repository](https://github.com/oceanpep/br-mangue-studio) hosts source code and releases.

<a id="12-references"></a>
## 12. References

- Alongi, D. M. (2008). Mangrove forests: Resilience, protection from tsunamis, and responses to global climate change. *Estuarine, Coastal and Shelf Science*, 76(1), 1–13. [https://doi.org/10.1016/j.ecss.2007.08.024](https://doi.org/10.1016/j.ecss.2007.08.024).
- Bezerra, D. da S., Amaral, S., Kampel, M., & Andrade, P. R. (2014). Simulating sea-level rise impacts on mangrove ecosystem adjacent to anthropic areas: The case of Maranhão Island, Brazilian Northeast. *Pan-American Journal of Aquatic Sciences*, 9(3), 188–198. [Article PDF](https://panamjas.org/pdf_artigos/PANAMJAS_9(3)_188-198.pdf).
- Dangremond, E. M., & Feller, I. C. (2016). Precocious reproduction increases at the leading edge of a mangrove range expansion. *Ecology and Evolution*, 6(14), 5087–5092. [https://doi.org/10.1002/ece3.2270](https://doi.org/10.1002/ece3.2270).
- O’Sullivan, D. (2001). Exploring spatial process dynamics using irregular cellular automaton models. *Geographical Analysis*, 33(1), 1–18. [https://doi.org/10.1111/j.1538-4632.2001.tb00433.x](https://doi.org/10.1111/j.1538-4632.2001.tb00433.x).
- Sousa, F. M., Bezerra, D. da S., Costa, S. S., & Santos, R. L. (2026). *BR-MANGUE Studio* [software]. Zenodo. [https://doi.org/10.5281/zenodo.23509308](https://doi.org/10.5281/zenodo.23509308).
- Wolfram, S. (1983). Statistical mechanics of cellular automata. *Reviews of Modern Physics*, 55(3), 601–644. [https://doi.org/10.1103/RevModPhys.55.601](https://doi.org/10.1103/RevModPhys.55.601).
