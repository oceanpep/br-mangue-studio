# Manguezais da CMMA por município — 2025

Tabela suplementar S1: áreas de manguezais por município no recorte operacional da Costa de Manguezais de Macromaré da Amazônia (CMMA), com referência em 2025. Aprovada pelo autor em 22/10/2026.

## Conteúdo

- `municipios_manguezais_cmma_2025.xlsx`: resumo estadual e regional, método, fontes e tabela de 65 municípios.
- `municipios_manguezais_cmma_2025.csv`: tabela municipal para análise e versionamento.
- `totais_estaduais_e_recorte_cmma_2025.csv`: totais de PA, MA, parcela sem correspondência municipal e total do recorte.
- `metodo_e_totais.json`: contagens, método, parâmetros, fontes e hashes dos arquivos de entrada.
- `limite_cmma.geojson`: recorte operacional da pesquisa, em coordenadas geográficas longitude/latitude (GeoJSON).
- `SHA256SUMS`: hashes dos arquivos distribuídos.

## Dados e método

Cobertura de mangue: classe 5 do raster MapBiomas Brasil, coleção 11, ano 2025, preparado para o recorte da CMMA. Limites: arquivos originais da Malha Municipal Digital 2025 do IBGE para PA e MA. Os limites em SIRGAS 2000 (EPSG:4674) foram transformados para a grade SIRGAS 2000 / Brazil Albers (EPSG:10857), sem simplificação geométrica no cálculo.

Cada pixel mede 30 × 30 m (900 m² = 0,09 ha = 0,0009 km²). A área resulta da contagem de pixels de mangue, atribuídos ao polígono municipal que contém seu centro (`all_touched=False`). Um município entra na lista quando possui pelo menos um desses centros dentro do recorte. O uso do pixel inteiro por seu centro mantém uma partição aditiva da grade. As áreas representam estimativas do produto cartográfico e não levantamentos cadastrais de campo.

A área por município abrange somente a parcela dentro do recorte, e não necessariamente toda a cobertura de mangue municipal. Não se contam pixels de outras classes do MapBiomas. Os cálculos usam contagens inteiras, sem arredondamento intermediário.

## Reconciliação das áreas

| Unidade | Municípios | Mangue no recorte (km²) | Mangue no domínio simulável (km²) |
|---|---:|---:|---:|
| Pará | 26 | 2.241,0297 | 2.229,1992 |
| Maranhão | 39 | 4.509,4455 | 4.504,6215 |
| Sem correspondência municipal | — | 32,4225 | 25,0443 |
| **Total do recorte** | **65** | **6.782,8977** | **6.758,8650** |

A parcela sem correspondência soma 36.025 pixels, equivalentes a 0,478% da cobertura mapeada. Seus centros estão dentro do recorte de estudo, mas fora dos polígonos municipais oficiais. A comparação de uma classificação raster com a malha administrativa pode produzir diferenças nas margens e em superfícies aquáticas; o cálculo não estabelece, por si só, a causa de cada ocorrência. Não houve atribuição ao município mais próximo nem dupla contagem em sobreposições municipais.

Os totais estaduais acima compreendem os pixels com correspondência municipal. A parcela sem correspondência é mantida separada, sem estimar a qual município ou estado ela pertence. O total de 6.782,8977 km² inclui ambas as parcelas.

A máscara com dados válidos empregada nas simulações retém 6.758,8650 km² e exclui 24,0327 km² do mangue mapeado. O subconjunto foi conferido contra a classe de mangue do estado inicial do modelo. Essa diferença de domínio é distinta da ausência de correspondência municipal.

## Dicionário de dados da tabela municipal

| Campo | Definição |
|---|---|
| codigo_ibge | Identificador municipal IBGE de sete caracteres |
| municipio / uf | Nome oficial e sigla da unidade federativa |
| ano | Ano de referência da cobertura: 2025 |
| pixels_mangue_recorte | Contagem de centros de pixels da classe 5 no município e no recorte |
| mangue_recorte_km2 / mangue_recorte_ha | Área dessa cobertura em km² / ha |
| pixels_mangue_simulavel | Pixels da contagem anterior também incluídos na máscara de dados válidos |
| mangue_simulavel_km2 | Área usada no estado inicial da simulação |
| mangue_fora_dominio_km2 | Área municipal mapeada que não participa das simulações |
| fracao_mangue_total_recorte | Fração do total de 6.782,8977 km² localizada no município. O denominador inclui a parcela sem correspondência. |

Os CSVs usam UTF-8, vírgula como separador de campos e ponto decimal. A planilha conserva identificadores como texto e números como valores numéricos. As fórmulas recalculam áreas, participações e totais a partir das contagens. A notação regional de separadores depende do programa que abre o arquivo.

## Fontes

- IBGE, Malha Municipal Digital 2025, Pará: https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2025/UFs/PA/PA_Municipios_2025.zip
- IBGE, Malha Municipal Digital 2025, Maranhão: https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2025/UFs/MA/MA_Municipios_2025.zip
- MapBiomas Brasil, códigos de legenda: https://brasil.mapbiomas.org/codigos-de-legenda/

Os arquivos de entrada e seus hashes estão identificados em `metodo_e_totais.json`. O recorte e os rasters de entrada são os preparados para a pesquisa. Este suplemento não redistribui os arquivos raster brutos.

## Citação dos dados

Sousa, Felipe Martins; Bezerra, Denilson da Silva; Costa, Sergio Souza; Santos, Ricardo Luvizotto. Manguezais da CMMA por município — 2025. Tabela suplementar S1, 2026. Repositório BR-MANGUE Studio.

https://github.com/oceanpep/br-mangue-studio/tree/main/datasets/cmma_municipalities_2025

## Autores do estudo

Felipe Martins Sousa; Denilson da Silva Bezerra; Sergio Souza Costa; Ricardo Luvizotto Santos. Universidade Federal do Maranhão, Programa de Pós-Graduação em Ciência e Tecnologia Ambiental.
