# Manual do usuário — BR-MANGUE Studio 1.0.0

Este manual apresenta um fluxo completo para preparar os dados, configurar,
executar e interpretar uma simulação no BR-MANGUE Studio. A aplicação foi
desenvolvida para tornar o modelo espacial de manguezais acessível a
pesquisadores que trabalham com dados raster, sem exigir programação para uma
execução comum.

## 1. Antes de começar

### Requisitos

- Windows 10 ou Windows 11, 64 bits;
- raster de uso e cobertura da terra em GeoTIFF categórico;
- Modelo Digital de Terreno (MDT/DEM) em GeoTIFF, alinhado ao raster de uso e
  cobertura;
- espaço livre em disco para os resultados anuais;
- memória suficiente para a grade escolhida. Para áreas extensas, prefira o
  motor em blocos.

O executável distribuído já contém o ambiente necessário para rodar o Studio.
Os rasters, projetos e resultados permanecem fora do executável e devem ser
armazenados em uma pasta com permissão de leitura e gravação.

### Organização recomendada

Crie uma pasta para cada experimento. Mantenha nela o projeto, uma pasta
`inputs/` com os rasters originais e uma pasta `results/` para as execuções.
Não substitua os rasters originais pelos arquivos reprojetados: o Studio cria
cópias alinhadas em `prepared_inputs/`.

## 2. Criar ou abrir um projeto

1. Abra o **BR-MANGUE Studio**.
2. Em **Project**, escolha **New project** e indique a pasta do experimento.
3. Para continuar um trabalho anterior, use **Open project** e selecione o
   arquivo JSON salvo pelo Studio.
4. Salve o projeto depois de preencher os dados. O arquivo JSON registra os
   caminhos, as classes e os parâmetros usados.

## 3. Carregar os rasters

Na aba **Project data**, informe:

- **Land-cover / categorical raster**: raster inteiro no qual cada código
  representa uma classe de cobertura;
- **Elevation raster**: MDT/DEM com os valores de elevação;
- **Study-area mask**: máscara opcional para limitar o domínio;
- **Mangrove suitability raster**: camada opcional que indica onde a
  migração para mangue é permitida.

O raster de uso e cobertura e o MDT devem representar a mesma grade: número de
linhas e colunas, resolução, extensão e alinhamento. O Studio verifica essa
compatibilidade antes de iniciar o modelo.

### Inspecionar classes

Clique em **Inspect land-cover classes**. A tabela mostra cada código, o
número de células e o papel que será usado pelo modelo. Associe os códigos de
acordo com a legenda do seu produto:

| Papel no modelo | Interpretação |
| --- | --- |
| Mangrove | manguezal existente no estado inicial |
| Natural vegetation | vegetação natural que pode receber migração quando a regra permitir |
| Water | água ou corpos d'água |
| Anthropized / blocked | área ocupada, infraestrutura, praia, solo exposto ou qualquer área que não deve receber migração |
| Exclude | código fora da área válida, como NoData ou máscara indesejada |

Não associe uma classe apenas pelo número do código. Confirme a legenda do
produto de origem e, quando possível, verifique a distribuição no mapa inicial.
Uma mesma classe temática pode aparecer com códigos diferentes em produtos
distintos.

## 4. Sistema de coordenadas e reprojeção

O Studio exibe o CRS detectado, o datum informado nos metadados e os campos
para conferir ou alterar a referência espacial.

1. Consulte o CRS detectado em **Detected CRS**.
2. Em **Target CRS for reprojection**, digite o nome ou o código desejado.
   A lista sugere os resultados encontrados. O primeiro item recomendado para
   o projeto é o EPSG:10857, a projeção cônica equivalente de Albers para o
   Brasil, baseada no SIRGAS 2000.
3. Se necessário, informe a resolução em unidades do CRS de destino.
4. Clique em **Reproject and align input rasters**.
5. Revise as classes e use **Validate and load inputs**.

A reprojeção horizontal não converte automaticamente o datum vertical. O
campo **Declared vertical datum** é um registro documental; uma conversão de
alturas exige uma referência vertical ou superfície geoidal apropriada.

## 5. Configurar a simulação

Na aba **Simulation**, informe:

- **Initial calendar year**: ano associado ao estado inicial;
- **Final calendar year**: último ano a ser calculado;
- **Tidal influence height (m)**: altura de influência da maré, em metros e na
  mesma referência vertical do MDT;
- **Sea-level rise (mm/year)**: elevação média do nível do mar, em milímetros
  por ano. O Studio converte o valor para metros por passo internamente;
- **Constant surface accretion (mm/year, optional)**: acreção superficial
  constante, em milímetros por ano, quando houver justificativa para usá-la;
- **Block size (cells)**: quantidade de células processadas por bloco;
- **Processing engine**: `continuous`, `blocks` ou `DissModel` quando essa
  integração opcional estiver instalada.

O motor contínuo mantém a grade ativa na memória e geralmente é mais rápido
quando ela cabe confortavelmente na RAM. O motor em blocos divide o domínio e
preserva o estado entre os blocos; ele é a opção mais segura para grades com
milhões de células, mesmo que possa levar mais tempo por causa das operações
de leitura e gravação.

### Camada de aptidão e migração

Quando a camada de aptidão de mangue é carregada, ela restringe as células que
podem receber a migração conforme a regra configurada. Sem essa camada, a
opção **Allow migration without soil** permite que a migração use as classes
de vegetação natural e solo exposto selecionadas no mapeamento. Desmarcar a
opção reproduz a exigência literal de uma classe de solo/aptidão.

## 6. Executar e acompanhar

Clique em **Run simulation**. O painel **Live run monitor** mostra o andamento
da execução, o ano em processamento e, ao final:

- tempo do modelo;
- tempo total da execução;
- pico de RAM do processo;
- vazão aproximada em milhões de atualizações de células por segundo;
- tamanho dos arquivos gerados.

O mapa e os painéis visuais são atualizados ano a ano. Uma simulação longa
continua em segundo plano, mas não deve ser encerrada enquanto o monitor ainda
indicar processamento.

## 7. Ler os resultados

Cada execução cria uma pasta semelhante a
`results/run_20260921T120000/`, contendo, conforme as opções selecionadas:

- `metadata.json`: configuração, hashes de entrada, contagens iniciais e
  finais, tempos, memória, CPU, I/O, disco e resumo do processamento;
- `trajectory.csv`: contagens anuais, ganhos e perdas, tempo de cada passo,
  RSS e atualizações por segundo;
- `resource_samples.csv`: amostras aproximadamente a cada segundo de RAM do
  processo, memória do sistema, uso de CPU e espaço livre em disco;
- `states/`: GeoTIFFs anuais quando a exportação foi habilitada;
- `figures/`: mapas e gráficos anuais;
- `simulation.gif`: animação, quando gerada;
- `transition_by_land_cover_code.csv`: transições por código de origem e
  destino;
- `final_usos_*.tif`: estado final do raster.

Os contadores de RAM são medidas do processo e do sistema; não representam
apenas o tamanho do raster. O espaço livre em disco e o tamanho dos produtos
indicam o custo de armazenamento. A amostragem é periódica, portanto o pico
registrado pode ser ligeiramente inferior a um pico muito breve entre duas
amostras.

## 8. Comparar motores e garantir reprodutibilidade

Para comparar `continuous` e `blocks`, mantenha iguais os rasters, o
mapeamento, os parâmetros, a exportação e o número de anos. Faça pelo menos
uma execução curta para verificar os arquivos e, para um benchmark, três
repetições após uma execução de aquecimento.

Compare:

1. todas as linhas anuais de `trajectory.csv`;
2. o raster final célula a célula;
3. os totais de transição por classe;
4. o tempo, a vazão, o pico de RAM e o tamanho de saída.

O resultado esperado de uma comparação equivalente é zero células diferentes
e trajetórias anuais iguais. Se os estados diferirem, registre a diferença
como uma questão científica ou de implementação; não a apresente como ganho
de desempenho.

## 9. Solução de problemas

**O programa não carrega os rasters.** Verifique se os arquivos existem, se
estão em GeoTIFF válido e se o processo tem permissão de leitura.

**O mapa aparece vazio ou com cores inesperadas.** Revise os códigos em
**Class mapping**, o NoData e a máscara de estudo. As cores representam os
papéis do modelo, não necessariamente a legenda original do produto.

**A migração é zero.** Verifique se há células de vegetação natural/solo
permitidas, se a camada de aptidão não bloqueia o domínio e se a opção de
migração sem camada está coerente com o experimento.

**O motor contínuo consome muita memória.** Reduza o domínio para um teste,
desative a exportação anual durante o benchmark ou use `blocks` com um tamanho
de bloco adequado.

**O resultado demora ou o disco fica cheio.** Desative GeoTIFFs anuais quando
eles não forem necessários, confirme o espaço livre e acompanhe
`resource_samples.csv`.

## 10. Relato de uma execução

Ao compartilhar uma simulação, informe a versão do Studio, o sistema
operacional, o processador, a RAM disponível, o CRS, a resolução, o número de
células, os códigos mapeados, os parâmetros, o motor e o tamanho do bloco.
Inclua `metadata.json`, `trajectory.csv` e os hashes dos rasters sempre que
possível. Isso permite que outro pesquisador reproduza o teste sem depender de
uma captura de tela.

