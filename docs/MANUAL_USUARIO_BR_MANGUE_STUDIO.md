# Manual do usuário — BR-MANGUE Studio 1.0.0

## Como usar este manual

Este manual foi escrito para quem nunca trabalhou com um autômato celular ou
com dados raster. Leia as seções 1 a 5 na primeira utilização. Depois, use as
seções de resultados e solução de problemas como consulta rápida.

O BR-MANGUE Studio é uma ferramenta de pesquisa. Ele ajuda a explorar cenários
de elevação do nível do mar e não substitui medições de campo, calibração
local, análise de incerteza ou avaliação de um especialista. Um mapa produzido
pelo programa é uma simulação condicionada aos dados e às regras escolhidas,
não uma previsão garantida do futuro.

---

## 1. O que é o BR-MANGUE Studio?

O Studio transforma dois mapas digitais — um mapa de uso e cobertura da terra
e um mapa de elevação — em uma grade de células. Em seguida, atualiza essa
grade ano a ano para representar, sob um cenário escolhido, processos como:

- inundação de áreas baixas à medida que o nível do mar sobe;
- mudança do estado de células de mangue inundadas;
- possibilidade de migração do mangue para células vizinhas adequadas;
- alteração da superfície conforme a regra de acreção utilizada;
- bloqueio da migração por áreas antropizadas, infraestrutura e outras
  classes que o usuário marcar como impedimento.

O Studio possui uma interface gráfica para Windows. O usuário não precisa
programar para fazer uma simulação comum: seleciona os arquivos, confere as
classes, informa os parâmetros, executa e examina mapas, gráficos, tabelas e
animações.

### O que o Studio não faz

O modelo não escolhe automaticamente o melhor cenário, não corrige um MDT
incorreto, não descobre sozinho o significado dos códigos do seu mapa e não
converte automaticamente um datum vertical. Essas decisões precisam ser
documentadas pelo pesquisador.

---

## 2. Entendendo o autômato celular

### 2.1 A ideia em linguagem simples

Imagine uma folha quadriculada. Cada quadrado representa uma pequena parte do
território e guarda informações sobre aquele lugar: por exemplo, “mangue”,
“água”, “vegetação natural” ou “área bloqueada”. Essa folha é a **grade** do
modelo.

Em um autômato celular, cada célula tem:

1. um **estado**, que descreve o que existe nela;
2. atributos, como a elevação e, quando disponível, a classe de aptidão do
   solo;
3. células vizinhas que podem influenciar sua mudança;
4. regras que dizem como ela poderá mudar no próximo passo.

O modelo aplica as mesmas regras a todas as células, uma vez por ano. Assim,
um mapa inicial de 2024 pode gerar mapas de 2025, 2026, 2027 e assim por
diante. O resultado não é criado por uma única fórmula para toda a paisagem:
ele emerge da interação de muitas decisões locais.

### 2.2 Por que usar um autômato celular?

Uma área costeira não muda como um bloco uniforme. Um canal pode inundar uma
célula baixa, enquanto uma célula um pouco mais alta permanece seca. Um trecho
de vegetação pode estar ao lado de mangue e ser candidato à colonização,
enquanto uma estrada próxima funciona como barreira.

O autômato celular é útil porque:

- mantém a posição de cada célula;
- representa diferenças locais de elevação e cobertura;
- torna explícitas as regras de vizinhança;
- permite acompanhar cada ano da trajetória;
- é reproduzível: os mesmos dados, classes e parâmetros produzem o mesmo
  resultado;
- permite testar cenários sem afirmar que um deles acontecerá necessariamente.

### 2.3 O que é uma célula?

Se a resolução do raster é de 30 m, cada célula representa um quadrado de
30 m por 30 m, ou 900 m² (0,09 ha), desde que o CRS esteja em uma unidade
métrica. Uma área com 1.000.000 de células de 30 m representa 900 km² de
superfície rasterizada, antes de considerar células excluídas ou NoData.

**Importante:** o programa processa células, não hectares. A conversão para
área depende da resolução e deve ser conferida no sistema de coordenadas.

### 2.4 A vizinhança de Moore

O Studio usa a vizinhança de Moore: a célula central pode observar até oito
células ao redor dela.

```text
┌─────────┬─────────┬─────────┐
│ noroeste│  norte  │ nordeste│
├─────────┼─────────┼─────────┤
│  oeste  │ CÉLULA  │  leste  │
├─────────┼─────────┼─────────┤
│ sudoeste│   sul   │ sudeste │
└─────────┴─────────┴─────────┘
```

Uma célula na borda pode ter menos de oito vizinhos. Células NoData ou
excluídas não participam da grade válida. A vizinhança é espacial: ela não
significa que duas classes temáticas são parecidas, mas que ocupam posições
contíguas na grade.

### 2.5 Um passo anual

Em cada ano, o modelo utiliza o estado anterior como referência e percorre a
grade. De forma resumida:

1. calcula o aumento acumulado do nível do mar;
2. identifica células de água ou já inundadas;
3. distribui a influência para vizinhos mais baixos e aplica transições de
   inundação;
4. procura células de mangue junto a vegetação natural ou solo exposto que
   satisfaçam as regras de migração;
5. aplica a acreção prevista pela configuração;
6. registra contagens, tempos e resultados do ano.

As mudanças são exibidas ano a ano. O modelo não salta intencionalmente de
cinco em cinco anos.

---

## 3. Estados e papéis das classes

### 3.1 Papéis exibidos na aba Class mapping

O mapa de origem contém números. O número `5`, por exemplo, só tem significado
quando sabemos qual produto o produziu. Na aba **Class mapping**, o usuário
atribui cada código a um papel do modelo:

| Papel no Studio | O que significa | Pode receber migração? |
|---|---|---:|
| **Mangrove** | Mangue existente no estado inicial | É a origem da migração |
| **Natural vegetation** | Vegetação natural que pode acomodar mangue | Sim, se as demais regras permitirem |
| **Water** | Água, canais, rios, estuários ou mar | Não como destino de migração |
| **Anthropized / blocked** | Área construída, infraestrutura, praia, solo descoberto sem permissão ou qualquer barreira | Não |
| **Exclude** | NoData, borda inválida ou classe fora do domínio do estudo | Não participa |

O enquadramento depende da legenda do produto. Não atribua um papel apenas
porque o código parece familiar. Confirme a legenda, consulte os metadados e
observe o mapa inicial.

### 3.2 Estados internos

O Studio também registra estados derivados durante a simulação:

| Estado | Interpretação |
|---|---|
| Mangrove | Mangue presente no início ou preservado |
| Natural vegetation | Vegetação natural ainda não convertida |
| Water | Água |
| Anthropized / blocked | Área antropizada ou bloqueada |
| Bare soil | Solo descoberto, quando mantido como estado separado |
| Flooded bare soil | Solo descoberto inundado |
| Flooded anthropized / blocked | Área bloqueada inundada |
| Migrated mangrove | Célula convertida para mangue por migração |
| Flooded mangrove | Mangue atingido pela inundação |
| Flooded natural vegetation | Vegetação natural inundada |

Na visualização, alguns estados inundados mantêm a cor da classe de origem
para não confundir o mapa. O vermelho é reservado ao mangue inundado. Os
códigos detalhados continuam disponíveis nos GeoTIFFs e nas tabelas.

### 3.3 Água, praia e solo descoberto

Água deve ser mapeada para **Water**. Praia, areia e solo descoberto não são
automaticamente água: se a hipótese do estudo é que essas áreas não podem
receber mangue, associe-as a **Anthropized / blocked**. Se o produto e a
calibração justificarem que uma classe de solo descoberto pode acomodar
mangue, ela pode ser usada como candidata, mas essa escolha precisa ser
registrada no método do estudo.

---

## 4. Preparando os dados

### 4.1 Arquivos necessários

Para uma simulação raster comum, prepare:

1. **Uso e cobertura da terra:** GeoTIFF categórico; cada pixel contém um
   código inteiro de classe.
2. **Elevação:** GeoTIFF contínuo; geralmente um MDT/DEM (Modelo Digital de
   Terreno/Modelo Digital de Elevação), com valores de altura.

Opcionalmente, prepare:

3. **Máscara da área de estudo:** pixels diferentes de zero permanecem no
   domínio; pixels zero ou NoData são excluídos.
4. **Camada de aptidão de mangue:** GeoTIFF inteiro alinhado, quando o estudo
   possui informação de solo/aptidão para restringir a migração.

O Studio não exige um provedor específico. Os rasters podem vir de produtos
distintos, desde que sejam alinhados e que as classes estejam documentadas.

### 4.2 Alinhamento obrigatório

O uso/cobertura e o MDT devem ter:

- o mesmo número de linhas e colunas;
- a mesma resolução;
- a mesma extensão espacial;
- o mesmo CRS;
- o mesmo transform/alinhamento de pixel.

Se qualquer item for diferente, o Studio interrompe o carregamento para evitar
uma comparação espacial incorreta.

### 4.3 NoData e NaN

`NoData` é o valor que representa uma célula sem informação. `NaN` (“not a
number”) é outra forma de valor ausente, comum em arquivos científicos
exportados por alguns programas. Nenhum dos dois deve ser interpretado como
uma classe ecológica.

Se aparecer `cannot convert float nan to integer`:

1. não associe `NaN` a nenhuma classe;
2. use uma versão do Studio atualizada;
3. confirme que o raster categórico não contém NaN não mascarado;
4. defina um NoData coerente e exporte o raster categórico como inteiro;
5. inspecione novamente as classes.

O Studio atual filtra valores não finitos durante a inspeção e o carregamento,
mas a limpeza prévia do dado continua sendo a prática mais segura.

### 4.4 CRS, datum e reprojeção

O CRS informa como as posições estão localizadas. Um CRS projetado em metros é
normalmente mais adequado para uma grade de 30 m do que coordenadas
geográficas em graus.

Na aba **Project data**:

1. leia o **Detected CRS**;
2. confirme se uso/cobertura e elevação estão no mesmo CRS;
3. só use **Target CRS for reprojection** quando os arquivos precisarem ser
   alinhados ou quando o método exigir outro sistema;
4. informe a **Target resolution** nas unidades do CRS de destino. Para uma
   grade métrica de 30 m, escreva `30`;
5. clique em **Reproject and align input rasters**;
6. use as cópias criadas em `prepared_inputs/` e preserve os originais.

O primeiro preset do Studio é **10857 — Albers Brasil (SIRGAS 2000)**. Ele é
uma definição WKT fornecida para o projeto; não digite `EPSG:10857`, pois essa
identificação pode não estar registrada como código EPSG no PROJ instalado.

A reprojeção horizontal não converte automaticamente o datum vertical. O
campo **Declared vertical datum** registra informação, mas não calcula uma
superfície geoidal.

### 4.5 Exemplo: dados da CMMA

Para o teste da Costa de Manguezais de Macromaré da Amazônia (CMMA), use os
arquivos separados organizados para o projeto:

- `CMMA_2024_landcover_30m.tif`;
- `CMMA_2024_ANADEM_DEM_30m.tif`.

Eles já estão preparados na mesma grade. Nesse caso, não é necessário
reprojetar antes de testar. Se a reprojeção for necessária por uma exigência
metodológica, informe 30 m e verifique o espaço livre em disco: uma grade com
centenas de milhões de pixels gera arquivos grandes.

---

## 5. Instalação e primeiro projeto

### 5.1 Executável Windows

O download público é um executável para Windows 10 ou Windows 11, 64 bits.
Ele já inclui o Python e as bibliotecas necessárias. Os dados e resultados
continuam em arquivos externos.

1. Baixe o executável no site do BR-MANGUE Studio.
2. Salve-o em uma pasta com permissão de leitura e gravação.
3. Abra `BRMANGUE_Studio.exe`.
4. Se o Windows exibir um aviso de segurança para um programa novo, confirme
   a origem do arquivo e o checksum antes de abrir.

### 5.2 Instalação a partir do código-fonte

Para desenvolvimento ou uso do núcleo Python:

```powershell
python -m pip install -e .
python -m brmangue_studio
```

Python 3.10 ou mais recente é necessário. O executável é recomendado para
usuários que não precisam modificar o código.

### 5.3 Criando um projeto

1. Abra **Project > New project**.
2. Escolha uma pasta para o experimento.
3. Mantenha uma subpasta `inputs/` para os dados originais.
4. Deixe o Studio criar `prepared_inputs/` e `results/`.
5. Salve o projeto depois de preencher os campos.

Um projeto salvo registra caminhos, banda, ano, CRS esperado, papéis das
classes, parâmetros, motor e opções de saída. Isso não substitui o backup dos
rasters originais.

---

## 6. Conhecendo a interface

### 6.1 Tela de abertura

A tela inicial mostra a identidade do projeto, a versão 1.0.0 e a associação
ao laboratório. Ela permanece aberta por alguns segundos para que o usuário
consiga ler as informações.

### 6.2 Menu superior

- **Project:** criar, abrir, salvar e salvar como um projeto;
- **Data:** selecionar ou revisar os arquivos de entrada;
- **Help:** consultar o manual e informações da versão.

### 6.3 Aba Project data

É onde os arquivos e a referência espacial são conferidos. Use **Browse**
para escolher cada arquivo. Depois de selecionar o uso/cobertura, clique em
**Inspect land-cover classes**. Quando todos os arquivos estiverem prontos,
clique em **Validate and load inputs**.

### 6.4 Aba Class mapping

Cada linha mostra um código do raster, o número de pixels e uma lista de
papéis. Selecione o papel de acordo com a legenda do seu produto. Revise a
lista antes de carregar: um código que deveria ser água associado a
**Anthropized / blocked** altera completamente o cenário.

### 6.5 Aba Simulation

É onde o cenário temporal e o motor são configurados. Os campos são
explicados na seção 7.

### 6.6 Abas de resultados

- **Visualization:** quatro painéis independentes para os mapas e a trajetória;
- **Console:** mensagens de validação e execução;
- **Results:** tabelas e arquivos produzidos;
- **Trajectory:** gráfico de contagens e mudanças anuais;
- **Animation:** mapas e gráficos anuais individualizados, com controles de
  reprodução e salvamento;
- **Model rules:** consulta das regras e da implementação para auditoria.

Os divisores dos painéis podem ser arrastados. Redimensione um painel sem
alterar os dados da simulação.

---

## 7. Configurando uma simulação

### 7.1 Initial calendar year

É o ano associado ao mapa de entrada. Se o raster representa 2024, informe
`2024`. Esse mapa é o estado inicial, não uma atualização calculada pelo
modelo.

### 7.2 Final calendar year

É o último ano do cenário. `2024` até `2100` gera o estado inicial e 76 mapas
anuais de calendário, correspondentes a 76 anos informados pelo intervalo.
O primeiro passo calculado ocorre no ano seguinte ao estado inicial.

O valor final precisa ser maior que o inicial para executar uma simulação.

### 7.3 Tidal influence height (m)

Altura de influência da maré, em metros e na mesma referência vertical do
MDT. O valor não é a altura de uma onda isolada. É um parâmetro do modelo que
define a zona de elevação onde a migração pode ser considerada.

### 7.4 Sea-level rise (mm/year)

Taxa de elevação do nível do mar em milímetros por ano. O Studio converte o
valor para metros internamente. Portanto:

- `0.5` significa 0,5 mm por ano;
- `13` significa 13 mm por ano;
- `5` significa 5 mm por ano.

Use uma taxa justificável para a área e o período estudados. O programa não
decide se a taxa é regionalmente adequada.

### 7.5 Constant surface accretion (mm/year, optional)

Representa um ganho superficial constante, em milímetros por ano, quando essa
hipótese for adotada. Deixe vazio para manter a formulação padrão do modelo.
Não confunda acreção com elevação do nível do mar: uma é mudança da superfície
sedimentar; a outra é mudança relativa da água.

### 7.6 Block size (cells)

É o número de células processadas por grupo no motor em blocos. Exemplos:

- `10,000`: valor conservador para testes;
- `100,000`: compromisso entre processamento e memória;
- `1,000,000`: útil em máquinas com memória e disco suficientes.

Um bloco maior nem sempre é mais rápido. A velocidade depende do processador,
do armazenamento, do número de células válidas, da vizinhança e da exportação
de arquivos anuais.

### 7.7 Processing engine

#### Continuous

Mantém o estado ativo na memória e normalmente é o mais rápido quando a grade
é pequena ou média e cabe confortavelmente na RAM. Acrescentar anos aumenta o
tempo de cálculo, mas não multiplica automaticamente a memória pelo número de
anos, porque o estado é atualizado e reutilizado.

#### Blocks

Cria um workspace persistente com estados alternados e vizinhanças em arquivos
de apoio. O domínio é percorrido por blocos, e o estado é preservado entre os
blocos e entre os anos. Esse modo é indicado para grades muito grandes, como
domínios costeiros com milhões de células, mesmo que uma execução contínua
seja mais rápida em uma máquina específica.

#### DissModel

É uma integração opcional para compatibilidade. Ela não é necessária para o
executável compacto nem para o funcionamento do motor principal. Use-a apenas
se a instalação correspondente estiver disponível e se o experimento exigir
essa comparação.

### 7.8 Camada de aptidão de mangue

Marque **Enable optional mangrove suitability layer** somente quando tiver um
GeoTIFF alinhado e souber interpretar seus códigos.

Se não houver essa camada, marque **Allow migration without suitability
layer** para permitir que as classes escolhidas como vegetação natural ou solo
exposto funcionem como candidatas, conforme a regra configurada. Sem a camada,
as regras de inundação continuam ativas; não fornecer solo não desliga o
modelo inteiro.

Desmarcar essa opção torna a migração dependente da informação de aptidão
disponível. Registre qual escolha foi usada no relatório do experimento.

---

## 8. Executando e acompanhando

1. Salve o projeto.
2. Clique em **Run simulation**.
3. Observe o **Live run monitor**.
4. Não feche o programa enquanto o monitor indicar que a execução está ativa.

O monitor apresenta o ano corrente, o número de células, a velocidade, o uso
da CPU, a RAM do processo, a memória do sistema e o espaço livre em disco.
Ao final, mostra o tempo do modelo, o tempo total, o pico de RAM e a pasta de
resultados.

O mapa é atualizado a cada ano simulado. A geração de figuras e GIF pode
continuar depois do último passo do modelo; aguarde a mensagem de conclusão
antes de abrir ou mover a pasta.

---

## 9. Entendendo os resultados

### 9.1 Mapa de estado

Mostra a classe de cada célula no ano selecionado. Use-o para verificar se:

- o mangue inicial está onde deveria;
- a água não foi confundida com áreas terrestres;
- as áreas bloqueadas permanecem barreiras;
- as células migradas e inundadas aparecem em locais coerentes.

### 9.2 Mapa de elevação

Mostra a superfície usada pelo cálculo. Cores claras ou escuras são uma escala
visual, não classes ecológicas. Confira a unidade e a referência vertical do
MDT antes de interpretar o mapa.

### 9.3 Trajetória de mangue

O gráfico acompanha, ano a ano, as contagens de mangue, mangue migrado e
mangue inundado. Uma queda no mangue existente pode ocorrer junto com um
aumento do mangue inundado; isso não significa automaticamente que a regra
falhou.

### 9.4 Mudança anual por classe

O gráfico divergente usa uma linha central zero:

- barras acima de zero representam acréscimo líquido;
- barras abaixo de zero representam perda líquida;
- a cor identifica a classe.

Perda líquida não é o mesmo que área totalmente desaparecida: uma classe pode
perder células para outra e também receber células de outra origem no mesmo
ano.

### 9.5 Tabelas de transição

`transition_by_land_cover_code.csv` registra a relação entre códigos de origem
e estados de destino. Ele é útil para descobrir, por exemplo, quais classes
foram convertidas em mangue migrado ou quais células passaram a inundadas.

---

## 10. Arquivos gerados

Cada execução cria uma pasta como `results/run_20260922T120000/`.

| Arquivo/pasta | Conteúdo |
|---|---|
| `metadata.json` | Parâmetros, motor, contagens, caminhos, CRS, hashes e diagnóstico de desempenho |
| `input_metadata.json` | Metadados dos rasters e do mapeamento de classes |
| `trajectory.csv` | Contagens e indicadores para cada ano |
| `resource_samples.csv` | Amostras de RAM, CPU, disco e processo |
| `initial_usos_*.tif` | Estado inicial em raster |
| `states/` | GeoTIFF do estado de cada ano, quando habilitado |
| `figures/` | Figuras individuais de estado, elevação, trajetória e mudança |
| `simulation.gif` | Animação combinada, quando gerada |
| `animations/` | Componentes animados individualmente, quando gerados |
| `simulation_data.xlsx` | Planilha com dados da trajetória e tabelas auxiliares |
| `transition_by_land_cover_code.csv` | Transições por código de origem e estado de destino |
| `workspace/` | Arquivos persistentes do motor em blocos |

O arquivo mais importante para auditoria é `metadata.json`. Para compartilhar
uma execução, envie também `trajectory.csv`, o mapeamento e os hashes dos
rasters de entrada.

### Tempo e memória

O Studio registra separadamente preparação, cálculo, pós-processamento e tempo
total. O pico de RSS é a memória observada pelo processo. A memória disponível
do computador pode mudar por causa de outros programas e do cache do sistema.
Uma amostragem de um segundo pode não capturar um pico muito breve.

---

## 11. Comparando contínuo e blocos

Para comparar os motores corretamente:

1. use os mesmos rasters e a mesma versão do Studio;
2. use o mesmo mapeamento de classes;
3. mantenha iguais anos, maré, elevação do nível do mar, acreção e solo;
4. mantenha a exportação anual igual;
5. faça uma execução curta de aquecimento;
6. repita cada configuração pelo menos três vezes;
7. compare os estados anuais célula a célula, e não apenas o tempo.

O resultado esperado para configurações equivalentes é:

- mesma trajetória anual;
- mesmas contagens por classe;
- zero células diferentes no raster final;
- mesmas transições agregadas.

Se os estados divergirem, trate isso como uma diferença científica ou de
implementação. Não apresente uma execução mais rápida como equivalente sem
fazer a comparação espacial.

---

## 12. Tutorial completo: uma primeira simulação

### Exemplo didático

Suponha que você tenha um uso/cobertura de 2024, um MDT de 2024 e queira
simular até 2050.

1. Crie `Experimento_2024_2050/inputs/`.
2. Copie os dois GeoTIFFs para essa pasta, sem renomear os originais.
3. Abra o Studio e crie o projeto nessa pasta.
4. Selecione o uso/cobertura e clique em **Inspect land-cover classes**.
5. Consulte a legenda do produto e atribua os papéis.
6. Selecione o MDT e clique em **Validate and load inputs**.
7. Na aba **Simulation**, informe inicial `2024` e final `2050`.
8. Informe a altura de influência da maré na unidade do MDT.
9. Informe a taxa de elevação em mm/ano, com a justificativa do cenário.
10. Deixe a acreção vazia no primeiro teste, salvo se ela fizer parte do
    desenho experimental.
11. Para uma área pequena, escolha `continuous`; para uma área grande,
    escolha `blocks` e comece com `10000` células.
12. Faça primeiro um teste de 2024 a 2025.
13. Confira o mapa e `trajectory.csv`.
14. Só depois execute todo o período.
15. Guarde a pasta de resultados junto com uma cópia do projeto JSON.

### O que escrever no caderno de pesquisa

Registre a data, a versão do Studio, o computador, os arquivos de entrada,
CRS, resolução, código de cada classe, anos, parâmetros, motor, tamanho do
bloco e se a aptidão foi usada. Sem essas informações, uma simulação pode ser
visualizada, mas não é plenamente reproduzível.

---

## 13. Solução de problemas

### “The land-cover and elevation paths must be valid”

Confira se os caminhos ainda existem e se o arquivo não está em uma pasta
sincronizada que está apenas online. Copie os dados para uma pasta local com
permissão de leitura.

### “The elevation has different dimensions/CRS/alignment”

Os dois rasters não estão na mesma grade. Reprojete e alinhe uma cópia ou
prepare os dados em um SIG, sempre preservando os originais.

### “cannot convert float nan to integer”

O uso/cobertura contém NaN não mascarado. Atualize o Studio, use arquivos
limpos, defina NoData e exporte a camada categórica como inteiro. Não transforme
NaN em uma classe ecológica.

### A reprojeção para Albers falha

Use o preset **10857 — Albers Brasil (SIRGAS 2000)**, não `EPSG:10857`, e
informe a resolução `30` quando a grade original for de 30 m. Para a CMMA,
primeiro confirme se a reprojeção é realmente necessária. Grandes grades
exigem espaço em disco e podem levar tempo, mesmo com a reprojeção em blocos.

### O mapa aparece cinza ou vazio

Cinza geralmente representa NoData, uma célula excluída ou uma área sem classe
válida. Revise a máscara, o NoData e o mapeamento. Use **Initial state** para
separar um problema de entrada de um problema de simulação.

### A migração é zero

Verifique se há mangue inicial, vegetação natural ou solo exposto candidato,
elevação dentro da zona de influência, vizinhança contígua e permissão para
migrar sem a camada de aptidão. Uma área inteira classificada como bloqueada
não oferece destino para migração.

### O motor contínuo consome muita RAM

Faça um teste com menos células, use `blocks`, reduza a exportação anual e
feche outros programas. O tamanho do bloco controla a parte percorrida por
vez, mas o custo total também depende da vizinhança e do workspace.

### O processamento em blocos é mais lento

Isso é esperado em muitas máquinas: o motor em blocos troca velocidade por
capacidade, usando arquivos persistentes e operações de leitura/gravação. Sua
vantagem aparece quando o contínuo não cabe com segurança na RAM ou quando uma
execução longa precisa de um estado recuperável.

### O programa parece travado

Confira o **Live run monitor** e o uso do disco. A geração de figuras e GIF pode
ocorrer depois do cálculo. Não encerre o programa sem verificar se o processo
terminou. Em grades muito grandes, faça antes um teste de um ano.

### O mangue inundado aparece em vermelho

Isso é intencional: o vermelho diferencia o estado **Flooded mangrove**. As
demais classes inundadas podem usar a cor da classe de origem para manter uma
legenda legível. Consulte os códigos detalhados nos rasters e tabelas.

---

## 14. Reprodutibilidade e interpretação responsável

Uma simulação reproduzível precisa de três camadas de informação:

1. **dados:** arquivos, bandas, NoData, CRS, resolução, máscara e hashes;
2. **decisões:** mapeamento de classes, anos, maré, taxa de elevação,
   acreção, solo, motor e tamanho do bloco;
3. **evidência:** `metadata.json`, trajetória, transições, rasters anuais e
   diagnóstico de recursos.

Ao comparar cenários, altere um fator por vez sempre que possível. Uma
diferença entre dois mapas pode vir da taxa de elevação, do código de água,
da máscara, do CRS, da resolução, da aptidão ou do próprio motor. O mapa final
sozinho não revela qual decisão produziu a diferença.

O modelo representa regras espaciais simplificadas. Ele não inclui, por
exemplo, todas as variáveis de salinidade, sedimentos, ondas, espécies,
conectividade hidrodinâmica, erosão lateral ou intervenções futuras. Use os
resultados como cenários e hipóteses testáveis, não como certeza determinística.

---

## 15. Glossário

**Autômato celular:** modelo que atualiza células de uma grade por regras
locais e discretas.

**Célula:** unidade espacial da grade raster.

**CRS:** sistema de referência de coordenadas.

**DEM/MDT:** modelo digital de elevação/modelo digital de terreno.

**GeoTIFF:** formato de imagem raster que guarda dados geográficos e
metadados.

**Grade alinhada:** rasters com a mesma posição de origem, resolução,
dimensão, extensão e CRS.

**NoData:** valor que significa “sem dado” e não deve ser tratado como classe.

**NaN:** valor numérico ausente ou não finito.

**Migração:** conversão de uma célula elegível vizinha ao mangue para o estado
de mangue migrado.

**Inundação:** transição causada pela influência da água sobre células baixas
ou vizinhas de células de água/inundadas.

**Acreção:** aumento representado na superfície, informado ou calculado pela
regra configurada.

**RAM:** memória de trabalho do computador.

**RSS:** memória residente observada para o processo do Studio.

**Motor contínuo:** execução mantendo o estado ativo na RAM.

**Motor em blocos:** execução que percorre grupos de células e preserva estados
em um workspace persistente.

---

## 16. Checklist antes de publicar um resultado

- [ ] A versão do Studio foi registrada.
- [ ] Os rasters e suas bandas foram identificados.
- [ ] NoData e NaN foram verificados.
- [ ] CRS, resolução e alinhamento foram conferidos.
- [ ] Cada código foi associado a um papel com base na legenda.
- [ ] A água, a praia e as áreas bloqueadas foram distinguidas.
- [ ] O cenário de elevação do nível do mar foi justificado.
- [ ] A opção de solo/aptidão foi documentada.
- [ ] Motor e tamanho do bloco foram registrados.
- [ ] Foi feito um teste curto antes da execução completa.
- [ ] `metadata.json`, `trajectory.csv` e hashes foram preservados.
- [ ] A interpretação foi apresentada como cenário, não como previsão certa.

Para problemas ou sugestões, abra uma issue no repositório público do
BR-MANGUE Studio e inclua a versão, o sistema operacional, a mensagem de erro
e, quando possível, o `metadata.json` sem anexar dados restritos.
