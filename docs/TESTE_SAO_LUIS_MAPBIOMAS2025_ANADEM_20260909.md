# Teste raster da Ilha de São Luís — 2025–2035

## Escopo

Foi executado um ensaio computacional da tradução Python do modelo Lua/TerraME
usando a banda de 2025 da série MapBiomas Coleção 11, o raster ANADEM de 30 m
e a máscara da área de interesse da Ilha do Maranhão (São Luís, Paço do Lumiar,
Raposa e São José de Ribamar). O FES2022b não participa deste ensaio.

O resultado é uma demonstração de funcionamento e desempenho. Os parâmetros
de maré e elevação do nível do mar continuam sendo os valores literais do
exemplo Lua (`tide_height=6.0` e `sea_level_rise_rate=0.5`), portanto o ensaio
não possui validade preditiva ou calibração científica.

## Entradas e preparação

| Item | Produto utilizado |
|---|---|
| Uso e cobertura | `mapbiomas_c11_1985_2025.tif`, banda 41 (2025) |
| Elevação | `elevacao_anadem_30m.tif` |
| Domínio | `mascara_area_interesse.tif` |
| Solo | Não fornecido; desativado (`-999`), com fallback de migração por uso/cobertura |
| Células | 1.083.556 pixels válidos de 30 m |
| Mangue inicial | 172.502 células |

O leitor verificou forma, resolução, transformação e CRS comuns aos três
rasters. O código 5 do MapBiomas foi convertido para mangue, o código 33 para
água, classes naturais candidatas para vegetação terrestre e classes manejadas
ou restritas para área antropizada. O mapeamento completo e as contagens dos
códigos de origem estão em `input_metadata.json` da execução.

## Execução reproduzível

Na pasta `brmangue_python_lua`, o teste foi executado com:

```powershell
python -m brmangue_lua.raster_cli `
  --mapbiomas "C:\BR_MANGUE_PY\estudos_caso\ilha_maranhao\dados\processados\mapbiomas_c11_1985_2025.tif" `
  --elevation "C:\BR_MANGUE_PY\estudos_caso\ilha_maranhao\dados\processados\elevacao_anadem_30m.tif" `
  --mask "C:\BR_MANGUE_PY\estudos_caso\ilha_maranhao\dados\processados\mascara_area_interesse.tif" `
  --mapbiomas-band 41 --mapbiomas-year 2025 `
  --initial-year 2025 --final-year 2035 `
  --engine blocks --block-size 10000 `
  --output outputs\ilha_sao_luis_mapbiomas2025_anadem_nosolo_2035_v2
```

O modo em blocos usa dois estados alternados em `numpy.memmap`, sem carregar
uma lista de objetos por célula. Foram gravados o estado inicial, um GeoTIFF
para cada ano de 2026 a 2035 em `states/`, o estado final, a trajetória CSV,
os metadados e o workspace de auditoria.

## Resultado observado

| Ano | Mangue vivo | Mangue inundado | Mangue migrado | Perda anual |
|---:|---:|---:|---:|---:|
| 2025 (base) | 172.502 | 0 | 0 | — |
| 2026 | 165.422 | 7.080 | 0 | 7.080 |
| 2030 | 128.616 | 43.886 | 0 | 9.730 |
| 2035 | 83.108 | 89.394 | 0 | 8.179 |

O modo contínuo e o modo em blocos foram comparados para o primeiro passo:
os dois produziram o mesmo raster final, célula a célula. O ensaio completo em
blocos levou aproximadamente 38 s e registrou pico de cerca de 268 MiB de RAM
no processo Python.

## Interpretação e limite científico

O declínio rápido do mangue é consequência direta das regras e dos parâmetros
herdados do exemplo Lua: a elevação da água é aplicada a cada passo e uma
célula de mangue que satisfaz a regra de inundação passa à classe
`MANGUE_INUNDADO`. A camada de solo foi desativada, mas o fallback de
uso/cobertura permite que vegetação terrestre e solo exposto elegíveis recebam
`MANGUE_MIGRADO`; por isso, um novo ensaio sem solo pode registrar migração.
A magnitude da inundação não deve ser
interpretada como previsão para São Luís antes de harmonizar datum vertical,
maré, taxa regional de nível do mar e parâmetros ecológicos.

## Solo opcional

Quando um pesquisador possuir um GeoTIFF de solo alinhado à grade, basta usar
`--soil caminho\solo.tif`. A opção `--disable-soil` força a desativação. Sem
solo, o fallback por uso/cobertura substitui apenas o teste de elegibilidade
para migração; água, áreas antropizadas e restrições continuam bloqueadas. A
opção `--no-migration-without-soil` desliga também esse fallback. A inundação e
a elevação continuam ativas em todos os casos.
