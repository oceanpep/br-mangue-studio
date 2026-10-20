# Numerical boundary regression fixture

`floating_point_tidal_boundary.npz` contains a 17 × 17 local neighborhood of
categorical cover, elevation and a domain mask. Its spatial origin is omitted;
the test writes an arbitrary 30 m grid and checks local transitions only.
It reproduces the five-step constant/CSV disagreement observed in the full-CMMA
software checks: subtraction of interpolated levels changed an annual increment
by floating-point round-off, sufficient to cross an exact flooding boundary.
The original 4.7 mm/year inputs differ in the third annual increment, and
the disagreement becomes visible in the fifth annual state.

Data attribution (CC BY 4.0 for the third-party datasets):

- Project MapBiomas, Brazil annual land-cover and land-use maps, Collection 11,
  30 m, 2025: https://brasil.mapbiomas.org/ . Categorical values were extracted
  from the aligned CMMA test input.
- Agência Nacional de Águas e Saneamento Básico (2025), *ANADEM: A Digital Terrain
  Model for South America*, distributed by OpenTopography,
  https://doi.org/10.5069/G9736P4G . The prepared test DEM was aligned to the
  EPSG:10857 land-cover grid before the neighborhood was extracted.
- License: https://creativecommons.org/licenses/by/4.0/ . The fixture contains
  extracted, aligned values; it does not imply endorsement by either provider.
  The binary fixture's data license is separate from the repository's MIT code
  license. The all-valid local mask identifies the regression-test domain.
