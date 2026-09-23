# API de referência — BR-MANGUE Studio

Esta página resume a interface Python destinada a scripts e notebooks. Para
uma execução sem programação, use o executável e o [manual do usuário](MANUAL_USUARIO_BR_MANGUE_STUDIO.md).

## Preparar a grade

```python
from brmangue_lua.raster_inputs import load_raster_inputs

inputs = load_raster_inputs(
    land_cover_path="inputs/land_cover.tif",
    terrain_path="inputs/elevation.tif",
    land_cover_band=1,
    mapping={...},
    soil_enabled=False,
)
```

`load_raster_inputs` valida forma, CRS e alinhamento, remove pixels inválidos,
constrói uma grade compacta de células válidas e materializa a vizinhança de
Moore. `mask_path`, `soil_path`, `land_cover_year` e
`exclude_source_codes` são opcionais. O retorno é um `RasterInputSet` com:

- `grid`: estado compacto (`BrMangueGrid`);
- `n_cells`: número de células válidas;
- `metadata`: CRS, resolução, códigos e estatísticas;
- `write_state_raster(...)`: grava um vetor de estados na grade original.

## Configurar o modelo

```python
from brmangue_lua.engine import ModelParameters

parameters = ModelParameters(
    start=1,
    final_time=10,
    tide_height=6.0,
    sea_level_rise_rate=0.0005,  # m per model step; 0.5 mm/year
    allow_migration_without_soil=True,
    migration_maturity_years=3,
)
```

Os parâmetros principais são `start`, `final_time`, `tide_height`,
`sea_level_rise_rate`, `accretion_rate_mm` e
`allow_migration_without_soil`. `migration_maturity_years` define quantos anos
completos uma célula recém-migrada precisa permanecer estabelecida antes de
servir como fonte de propagação. O padrão é `3`; `0` é útil para testes de
sensibilidade sem atraso biológico. A interface gráfica recebe a elevação do
nível do mar em mm/ano e faz a conversão para metros.

## Rodar uma grade em memória

```python
trajectory = inputs.grid.run(parameters)
```

`BrMangueGrid` também oferece:

- `step(time, parameters)`: aplica uma atualização;
- `class_counts()`: conta os estados atuais;
- `run(parameters)`: executa todos os passos mantendo os arrays em memória;
- `run_blocks(parameters, block_size=10000)`: percorre a grade por blocos em
  uma grade já materializada.

## Rodar uma simulação raster completa

```python
from brmangue_lua.raster_runner import run_raster_simulation

trajectory = run_raster_simulation(
    inputs,
    "outputs/example_run",
    parameters,
    initial_year=2024,
    engine="blocks",       # "continuous" or "blocks"
    block_size=100000,
    save_annual_states=True,
)
```

`run_raster_simulation` cria os GeoTIFFs anuais, a trajetória, as transições,
os metadados e os diagnósticos de desempenho. `step_callback`, quando usado,
recebe eventos anuais para monitoramento.

## Motor persistente em blocos

`PersistentBlockRunner` é a implementação usada pelo modo raster `blocks`. Ele
mantém dois estados alternados e a tabela de vizinhos em arquivos persistentes
no workspace da execução. Use-o diretamente apenas quando for necessário
controlar um fluxo avançado; para uso normal, prefira `run_raster_simulation`.

## Linha de comando

```powershell
python -m brmangue_lua.raster_cli `
  --land-cover "inputs/land_cover.tif" `
  --elevation "inputs/elevation.tif" `
  --initial-year 2024 --final-year 2050 `
  --engine blocks --block-size 100000 `
  --output "outputs/example_run"
```

Use `python -m brmangue_lua.raster_cli --help` para ver todas as opções.

## Códigos do modelo

Os códigos públicos do núcleo estão em `brmangue_lua.engine`: `MANGUE`,
`VEGETACAO_TERRESTRE`, `MAR`, `AREA_ANTROPIZADA`, estados inundados e
`MANGUE_MIGRADO`. A interface gráfica apresenta nomes legíveis para esses
códigos.

Alterações nas regras ou nos códigos devem incluir testes, uma nota no
`CHANGELOG.md` e uma comparação de estados com uma entrada fixa.
