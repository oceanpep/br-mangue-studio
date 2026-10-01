# Registro de verificação Linux — piloto com dados da Ilha do Maranhão

**Data:** 1º de outubro de 2026
**Código do modelo:** commit `e30b1e3268b78096ae51243bfd7fc8f93f3c8229`
**Sistema:** Ubuntu 26.04.1 LTS x86_64, kernel 7.0.0-34-generic
**Computador:** Intel Core i3-1215U, 8 CPUs lógicas, 18 GiB de RAM física
**Ambiente raster:** Python 3.12.14, Rasterio 1.5.2 / GDAL 3.12.2,
pyproj 3.8.0 / PROJ 9.8.1, NumPy 2.5.3 e pandas 3.0.6.

Este registro documenta testes de software com os rasters locais disponíveis.
Não representa uma simulação limitada pelo polígono da Ilha do Maranhão nem
uma avaliação ecológica: não havia máscara insular nos arquivos e o modelo
processou a interseção retangular válida dos rasters.

## Dados e cenário

- MapBiomas Coleção 11, banda 41 (referência 2025), raster original
  EPSG:5880, 30 m, SHA-256 `03290e77425751c8efe86b10e35609ec075b581d02d03cb48168701ce82839eb`.
- ANADEM, 30 m, alinhado ao MapBiomas, SHA-256
  `3d053dda13c1e4740aae9e42b081ae947ea896844af6064555e15822762f11d1`.
- Células válidas: 2.337.998. Solo e máscara: desativados/ausentes.
- Parâmetros usados: influência de maré de 6,0 m; elevação do nível do mar
  de 0,5 mm/ano; maturação de migração de 3 anos; migração sem solo habilitada;
  acreção constante desativada e fórmula legada mantida.
- As entradas, a versão do aplicativo e os resultados devem ser associados
  aos metadados de cada execução antes de qualquer interpretação científica.

## Comparação contínuo × blocos, 2025–2035

Cada motor executou dez passos anuais (23.379.980 atualizações). Os dois
usaram o mesmo conjunto de entradas e parâmetros e exportaram estados anuais.

| Medida | Contínuo | Blocos, 10.000 células |
|---|---:|---:|
| Tempo total, incluindo preparação e saídas | 51,04 s | 127,84 s |
| Pico de memória do processo (RSS) | 545.320.960 bytes (520 MiB) | 567.173.120 bytes (541 MiB) |
| Tamanho da pasta ao fim da execução | 1.557.335 bytes | 141.839.377 bytes |
| Estados anuais comparados | 10 | 10 |
| Diferenças entre células por ano | 0 | 0 |

Os GeoTIFFs anuais, o estado inicial e as métricas comparáveis das trajetórias
coincidiram. O tamanho maior da execução em blocos inclui o workspace persistente.

## Reprojeção

Foram criadas cópias alinhadas em EPSG:31983, com resolução de 30 m e grade de
2.142 × 2.122 células. O MapBiomas categórico foi reamostrado por vizinho mais
próximo; a elevação contínua do ANADEM, por interpolação bilinear. As classes
categóricas continuaram inteiras e válidas, os NoData foram preservados, e os
hashes das fontes não mudaram. Uma etapa anual com essas cópias produziu saídas
iguais entre motores, sem células diferentes.

## Inicialização do aplicativo e testes de entrada

O executável Linux `BRMANGUE_Studio_Linux_x86_64` é ELF x86_64. A soma SHA-256
foi conferida, a janela **BR-MANGUE Studio** abriu no ambiente gráfico e não
foram detectadas bibliotecas dinâmicas ausentes neste Ubuntu. O ensaio de
simulação foi executado pelo leitor raster do pacote do projeto em linha de
comando; não foi executado dentro da interface gráfica. O executável testado e
o arquivo público de download têm o mesmo SHA-256:
`369a4f8a296eb61bcf5a53d6ec63042b3d6a7111f298731f40ffec4fa47a2ab9`.

O leitor rejeitou um raster de elevação com grade deslocada e rejeitou o
pedido pela banda 42, inexistente no MapBiomas fornecido. A suíte automatizada
concluiu com **17 aprovados, 1 pulado e nenhuma falha**. O teste pulado é o
adaptador legado opcional de DissModel, que não é necessário nos dois motores
atuais das distribuições desktop.

## Comparação de horizonte longo, 2025–2100

Os dois motores usaram a mesma entrada de 2025, parâmetros, mapeamento, ausência
de máscara e ausência de solo. Cada um completou 75 transições, de 2025 a 2100,
com 175.349.850 atualizações. Foram gravados 75 GeoTIFFs anuais para 2026–2100,
além do estado inicial de 2025.

| Medida | Contínuo | Blocos, 10.000 células |
|---|---:|---:|
| Tempo total registrado | 567,50 s (9 min 27 s) | 1.417,14 s (23 min 37 s) |
| Taxa registrada | 309.008 atualizações/s | 123.982 atualizações/s |
| Pico de memória do processo (RSS) | 545.349.632 bytes (520 MiB) | 567.394.304 bytes (541 MiB) |
| Tamanho de saída, inclui workspace em blocos | 10.116.819 bytes | 150.409.818 bytes |

O estado inicial de 2025 e os 75 rasters anuais foram comparados célula a
célula: **zero diferenças** em todos os anos. As contagens das classes e as
métricas de ganhos, perdas e saldo de mangue nas trajetórias também coincidiram
em todos os anos. A comparação reproduzível, incluindo hashes das entradas e
versões do ambiente, está em `comparacao_motores_2025_2100.json`.

O teste demonstra equivalência computacional dos dois motores para essa
configuração e essa extensão raster. Sem máscara, as 2.337.998 células válidas
abrangem a interseção retangular dos rasters e ultrapassam o limite exato da
Ilha do Maranhão. Sem solo e sem dados observacionais independentes, isso não
é uma projeção insular calibrada nem validação ecológica.

## Dependências dos executáveis

Os executáveis desktop são empacotados com o runtime Python e as bibliotecas
Python necessárias, então o usuário não precisa instalar Python, Rasterio,
NumPy, pyproj ou bibliotecas do projeto via pip. Os rasters de entrada seguem
como arquivos externos. No Linux, é necessário ambiente gráfico compatível,
`xdg-open` para abrir arquivos e pastas e bibliotecas de sistema compatíveis
com o executável x86_64. A inicialização foi verificada somente no Ubuntu
26.04.1 neste computador.

## Artefatos locais

Os metadados, trajetórias, amostras de recursos, rasters e logs completos estão
em `BRMANGUE_Linux_Testes_Ilha_Maranhao_20261001/` na pasta pessoal do ambiente
de desenvolvimento. Esses resultados não são incluídos no repositório porque
contêm GeoTIFFs anuais derivados dos dados de entrada e são volumosos. O resumo
acima conserva as configurações e medições necessárias para interpretar o
ensaio.
