# BR-MANGUE Studio — interface desktop

## O que é

O BR-MANGUE Studio é uma interface gráfica opcional para o núcleo
`brmangue_lua`. Ele não substitui as regras científicas nem altera os dados de
entrada. O usuário cria um projeto, informa os GeoTIFFs, confere o alinhamento,
associa os códigos do uso e cobertura às classes do autômato e executa a
simulação.

Nesta versão, a interface já oferece:

- novo, abrir, salvar e salvar como projeto JSON;
- seleção de um raster categórico de uso/cobertura, um raster de elevação,
  máscara e camada opcional de aptidão de mangue;
- inspeção das classes numéricas e contagens do raster categórico;
- associação interativa de cada código às classes Mangrove, Natural
  vegetation, Water, Anthropized / blocked ou Exclude;
- confirmação do CRS dos rasters, declaração do datum vertical e registro dos
  metadados;
- reprojeção horizontal opcional para um CRS escolhido pelo usuário, com
  geração de cópias alinhadas do uso/cobertura, elevação, máscara e solo;
- quatro painéis visuais independentes para estado inicial, elevação, estado
  corrente e trajetória; os divisores podem ser arrastados para redimensionar
  cada linha e o botão **Reset layout** restaura a distribuição equilibrada;
- parâmetros de anos, maré, elevação relativa, acreção constante opcional,
  tamanho de bloco e executor contínuo, em blocos ou DissModel;
- mapa inicial, mapa corrente, trajetória e barras divergentes de mudança líquida
  por classe, com zero central, perdas à esquerda e ganhos à direita;
- trajetória com linha de células, barras separadas de ganhos e perdas e
  animação GIF com uma figura PNG para cada ano;
- aba opcional para consulta do código das regras celulares e do leitor raster;
- CPU, RAM do sistema e do processo, espaço livre em disco, células
  processadas, velocidade e tempo registrados;
- CSV de trajetória, GeoTIFF anual, metadados, figuras anuais em `figures/`,
  `simulation.gif` e `transition_by_land_cover_code.csv` na pasta da execução.

## Instalação e execução no ambiente Conda

Na pasta `brmangue_python_lua`, com o ambiente que contém o modelo:

```powershell
python -m pip install -e .
python -m brmangue_studio
```

Ou, depois da instalação editável:

```powershell
brmangue-studio
```

O Tkinter é parte do Python no Windows e não é instalado pelo pip. Matplotlib,
rasterio, NumPy, pandas e psutil são dependências do projeto.

Os nomes dos campos são deliberadamente genéricos: qualquer GeoTIFF categórico
pode ser usado como uso/cobertura e qualquer GeoTIFF contínuo alinhado pode ser
usado como elevação. O modelo não identifica nem exige um provedor específico.

## Tela de abertura

Ao iniciar o Studio, uma tela compacta apresenta o logotipo, a versão atual
(`0.2.0 beta`) e o estado de carregamento. Ela fecha automaticamente quando o
workspace principal está pronto. O logotipo é empacotado junto com a versão
executável e não depende de um caminho fixo no computador do usuário.

## Fluxo recomendado

1. Em **Project > New project**, escolha uma pasta de trabalho.
2. Selecione o raster categórico de uso/cobertura e informe a banda/ano, se
   ele for multibanda. O ano é apenas um metadado opcional.
3. Selecione o raster de elevação. Opcionalmente selecione uma máscara e um
   GeoTIFF de aptidão de mangue.
4. Clique em **Inspect land-cover classes** e escolha o papel de cada código.
   Códigos marcados como **Exclude** ficam fora do domínio válido; não são
   transformados em uma classe ecológica.
5. Se os rasters estiverem em CRS, resolução ou grades diferentes, informe o
   **Target CRS for reprojection** (por exemplo, `EPSG:31983`) e, se desejado,
   a resolução em unidades do mapa por pixel. Clique em **Reproject and align
   input rasters**. O Studio cria cópias em `prepared_inputs/` e preserva os
   arquivos originais. Em seguida, revise as classes e clique em **Validate and
   load inputs**.
6. Ajuste os parâmetros e clique em **Run simulation**. A execução ocorre em
  uma thread separada, permitindo acompanhar o mapa, o DEM, o gráfico e as
  contagens por classe. O painel visual é atualizado a cada ano do calendário;
  a execução longa não reduz a frequência dos rasters anuais. Isso vale também para a distribuição estendida com
  DissModel.
7. Os resultados ficam em `results/run_AAAAMMDDTHHMMSS` dentro da pasta do
   projeto. O projeto JSON registra todos os caminhos, associações e opções;
   quando os rasters estão no mesmo volume, os caminhos são gravados relativos
   à pasta do projeto para facilitar a transferência para outro computador.

## Unidades e cautelas

`Tidal influence height` é informado em metros na mesma referência vertical do
DEM. Na interface, `Sea-level rise` é informado em milímetros por ano e
convertido internamente para metros por passo do modelo Lua-parity. Isso torna
explícita a unidade solicitada pelo usuário sem alterar a API histórica do
núcleo. A taxa ainda não é uma taxa regional calibrada. A acreção constante,
quando informada, é em milímetros por ano. Deixe o campo vazio para preservar a
fórmula legada do Lua.

O campo `Target CRS for reprojection` atua sobre o sistema horizontal e o
datum associado ao CRS. A resolução opcional é expressa nas unidades do CRS
de destino. O campo `Declared vertical datum` continua sendo apenas
documental: o Studio não estima nem converte datum vertical ou geóide
automaticamente. Essa conversão precisa ser realizada com uma superfície
geoidal ou referência vertical fornecida pelo usuário antes da simulação.

Quando o solo é ativado, a camada deve ser um GeoTIFF inteiro alinhado à grade.
Quando não há solo, **Allow migration without soil** permite a migração para
vegetação terrestre ou solo exposto; desmarcar a opção reproduz a exigência
literal das classes de solo do Lua.

O formulário de entrada possui uma barra de rolagem vertical. Ela permite
acessar os campos de referência espacial e reprojeção mesmo quando a janela
está reduzida ou o monitor tem pouca altura.

## Gerar um executável Windows

Para pesquisadores e usuários finais, use preferencialmente o executável
compacto `BRMANGUE_Studio.exe`. Ele já contém o motor contínuo, o motor em
blocos, a interface visual, a geração de figuras anuais e o GIF. O DissModel é
uma integração opcional para testes de compatibilidade e não é necessário para
executar o modelo.

O repositório inclui `packaging/BRMANGUE_Studio.spec`. Depois de instalar o
PyInstaller no ambiente (`python -m pip install pyinstaller`), gere o
executável `dist/BRMANGUE_Studio.exe` com:

```powershell
pyinstaller packaging/BRMANGUE_Studio.spec --clean
```

A distribuição deve ser gerada no mesmo tipo de Windows em que será usada.
Rasters, projetos e resultados continuam sendo arquivos externos e não são
embutidos no executável. O executável compacto não embute o pacote opcional
DissModel para evitar dependências gráficas desnecessárias; a opção DissModel
funciona na instalação Python. Para gerar uma versão executável que também
leve o DissModel, use `packaging/BRMANGUE_Studio_DissModel.spec` em um ambiente
onde o pacote esteja instalado; o resultado será
`dist/BRMANGUE_Studio_DissModel.exe`.
