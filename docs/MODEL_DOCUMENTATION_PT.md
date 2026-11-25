# BR-MANGUE Studio — documentação técnica do modelo

**Versão documentada:** 1.4.9 · **Idioma:** português brasileiro ·
**Escopo:** regras implementadas no motor raster do BR-MANGUE Studio.

[Read this documentation in English](MODEL_DOCUMENTATION_EN.md).

Esta é a documentação técnica oficial do BR-MANGUE Studio. Ela especifica a finalidade do modelo, os dados de entrada, os parâmetros, os estados, as regras de transição, as saídas e os procedimentos de reprodução. Forçante do nível do mar, altura de influência da maré, mapeamento das classes, acreção e maturação são escolhas de cada aplicação e devem ser registrados. As regras descritas correspondem ao motor raster da versão atual do BR-MANGUE Studio.

<a id="sumario"></a>
## Sumário

1. [Finalidade e escopo](#1-finalidade-e-escopo)
2. [Estrutura espacial e variáveis](#2-estrutura-espacial-e-variaveis)
3. [Dados de entrada aceitos](#3-dados-de-entrada-aceitos)
   - [Trajetória CSV](#trajetoria-csv)
4. [Classes, perfis e estados](#4-classes-perfis-e-estados)
5. [Forçantes e parâmetros](#5-forcantes-e-parametros)
6. [Regras de transição](#6-regras-de-transicao)
   - [Inundação e redistribuição local](#61-inundacao-e-redistribuicao-local)
   - [Migração e elegibilidade](#62-migracao-e-elegibilidade)
   - [Maturação do mangue migrado](#63-maturacao-do-mangue-migrado)
   - [Camada de aptidão do solo](#64-camada-de-aptidao-do-solo)
   - [Acreção vertical](#65-acrecao-vertical)
   - [Comparação com o modelo antecedente](#comparacao-com-o-modelo-antecedente)
   - [Origem das regras e expressões](#origem-das-regras-e-expressoes)
7. [Ordem de atualização anual](#7-ordem-de-atualizacao-anual)
8. [Motores de execução](#8-motores-de-execucao)
9. [Saídas e métricas](#9-saidas-e-metricas)
10. [Interpretação e limites](#10-interpretacao-e-limites)
11. [Reprodutibilidade e citação](#11-reprodutibilidade-e-citacao)
12. [Referências](#12-referencias)

<a id="1-finalidade-e-escopo"></a>
## 1. Finalidade e escopo

O BR-MANGUE Studio é um aplicativo de pesquisa que executa e inspeciona cenários espaciais de mudanças nos manguezais sob elevação do nível do mar. O motor representa a paisagem como uma grade de células e aplica, em passos anuais, regras locais de inundação, migração e acreção. O modelo é baseado em autômatos celulares: cada célula tem um estado e atributos, e sua atualização depende de condições próprias e das células vizinhas (Wolfram, 1983; O’Sullivan, 2001).

O BR-MANGUE Studio desenvolve computacionalmente a abordagem celular aplicada por Bezerra et al. (2014) na Ilha do Maranhão. Esta documentação especifica as regras executadas pelo Studio; o catálogo gravado em cada execução registra os estados usados. Bezerra et al. (2014) é a referência conceitual e histórica da aplicação.

Cada execução produz um cenário condicionado aos dados, parâmetros e regras informados. O programa permite inspecionar as transições e comparar execuções com configurações documentadas.

<a id="2-estrutura-espacial-e-variaveis"></a>
## 2. Estrutura espacial e variáveis

O domínio é o conjunto de pixels válidos depois de combinar os rasters de entrada, os valores NoData, os códigos excluídos e, se fornecida, a máscara da área de estudo. Cada célula válida $i$ mantém:

- $c_i^t$: estado de cobertura no passo anual $t$;
- $z_i^t$: elevação relativa em metros;
- $u_i^t$: classe de solo/aptidão, quando ativada;
- $a_i^t$: idade interna do mangue migrado, quando aplicável.

O passo $t=0$ representa o mapa inicial no ano-calendário informado. Cada passo seguinte corresponde a um ano. A vizinhança de Moore contém até oito células contíguas, incluindo diagonais. Vizinhos fora do raster ou do domínio válido são omitidos; as bordas não se conectam entre si.

~~~mermaid
flowchart LR
    A[Uso e cobertura categórico] --> D[Grade válida e catálogo de estados]
    B[Elevação alinhada] --> D
    C[Mascara e solo opcionais] --> D
    D --> E[Estado inicial]
    E --> F[Passo anual: inundação, migração e acreção]
    F --> G[Mapas, tabelas, trajetórias e metadados]
    G -->|próximo ano| F
~~~

<a id="3-dados-de-entrada-aceitos"></a>
## 3. Dados de entrada aceitos

O fluxo raster do aplicativo e do executável de linha de comando usa arquivos GeoTIFF. O Studio não exige uma fonte específica: os dados podem vir de qualquer provedor, desde que legenda, unidades, resolução, referência horizontal e datum vertical sejam conhecidos e registrados.

| Entrada | Necessária? | Tipo e função |
| --- | --- | --- |
| Uso e cobertura da terra | Sim | GeoTIFF categórico com códigos inteiros. Arquivos multibanda são aceitos; seleciona-se uma banda. O ano é metadado informado pelo usuário. |
| Elevação | Sim | GeoTIFF contínuo, lido na banda 1; os valores são usados como elevação em metros. |
| Máscara da área de estudo | Não | GeoTIFF alinhado; valores diferentes de zero são incluídos, enquanto zero e NoData são excluídos. |
| Aptidão/solo | Não | GeoTIFF categórico inteiro e alinhado. Só participa quando a camada é ativada. |
| Trajetória do nível do mar | Não | CSV UTF-8 com colunas `year` e `sea_level_mm`; alternativa à taxa constante. |

Uso/cobertura, elevação e rasters opcionais precisam ter a mesma quantidade de linhas e colunas, CRS, transformação espacial e alinhamento dos pixels. O programa não reamostra silenciosamente esses arquivos durante o carregamento. Valores NoData, NaN ou infinitos não formam células ativas. Códigos de origem iguais a zero também ficam fora do domínio; os demais devem ser mapeados ou excluídos explicitamente.

Os valores do raster de elevação são lidos como metros e não são convertidos
automaticamente de pés, centímetros ou outra unidade.

Um pixel é válido quando a cobertura não é NoData nem zero, a elevação não é NoData e é finita, o pixel está incluído pela máscara e seu código não foi excluído. Recomenda-se usar uma projeção adequada à resolução espacial. A altura de maré e as elevações precisam compartilhar um datum vertical: o Studio não converte datum vertical.

<a id="trajetoria-csv"></a>
### Trajetória CSV

Cada arquivo representa uma única série, local ou resumo regional, cenário e percentil. Os níveis são acumulados em milímetros em relação à mesma referência temporal; não são taxas anuais.

~~~csv
year,sea_level_mm
2020,0
2030,40
2040,90
~~~

Os anos devem ser inteiros, únicos e crescentes; os níveis devem ser finitos. A série precisa cobrir os anos inicial e final da simulação. O motor interpola linearmente os anos ausentes, não extrapola e subtrai o nível interpolado do ano inicial para que a mudança aplicada comece em zero. São aceitos separadores por vírgula ou ponto e vírgula; com ponto e vírgula, valores decimais podem usar vírgula. Para o preparo detalhado, consulte [Forçante de nível do mar](SEA_LEVEL_TRAJECTORIES.md).

<a id="4-classes-perfis-e-estados"></a>
## 4. Classes, perfis e estados

Os números do raster de origem não têm significado universal no motor. No mapeamento, cada código recebe um perfil comportamental. Vários códigos originais podem compartilhar o mesmo perfil, mas o catálogo e os relatórios preservam a correspondência com a classe de origem.

| Perfil comportamental | Papel nas regras |
| --- | --- |
| **Mangue** | Estado inicial que pode propagar a migração e recebe acreção; pode tornar-se inundado. |
| **Apta para migração** | Categoria agregada das classes de origem autorizadas a receber mangue, condicionada às demais regras. Pode ser inundada antes da conversão. |
| **Água** | Fonte da propagação local da inundação; não é destino de migração nem recebe uma transição inundada própria. |
| **Área antropizada** | Não recebe migração; pode passar ao estado derivado inundado. |
| **Área bloqueada** | Não recebe migração; pode passar ao estado derivado inundado. |
| **Classe fixa** | Mantém seu estado e não é convertida pelas regras de inundação ou migração. |

O perfil **Solo exposto** é interpretado como **Área bloqueada**. Os códigos do raster de origem não têm significado universal. Em um novo projeto, associe cada código observado a um perfil do modelo ou exclua-o; o programa não pressupõe um produto de cobertura da terra nem um esquema específico de códigos. Uma legenda CSV fornecida pelo usuário pode acrescentar nomes legíveis às planilhas de resultados. Ela fornece apenas rótulos e não altera o mapeamento nem as regras da simulação. Sem CSV, os códigos de origem permanecem numéricos nos relatórios.

O catálogo de estados do projeto inclui estados derivados conforme os perfis usados, como **Mangue migrado**, **Mangue inundado** e **Mangue migrado inundado**. Códigos numéricos derivados são alocados conforme o catálogo de cada execução; leia `model_state_catalog` em `metadata.json` ou nos metadados do raster, em vez de presumir códigos fixos entre projetos.

Quando a regra de inundação alcança mangue migrado, ele passa a **Mangue migrado inundado**. Esse estado deixa de contar como mangue ativo e de propagar migração. As classes de origem e o estado final permanecem identificáveis nas tabelas de transição e no resumo por classe de origem.

<a id="5-forcantes-e-parametros"></a>
## 5. Forçantes e parâmetros

| Parâmetro | Significado e unidade | Configuração inicial do Studio |
| --- | --- | --- |
| Ano inicial/final | Anos-calendário do mapa inicial e do último estado. | 2025–2035. |
| Altura de influência da maré $T$ | Limiar em metros, no mesmo datum vertical da elevação. | 6,0 m; justificar para cada estudo. |
| Forçante do nível do mar | Taxa constante em mm/ano ou CSV de níveis acumulados em mm. | Taxa constante de 0,5 mm/ano; também aceita trajetória anual. |
| Acreção superficial | Taxa constante em mm/ano. Campo vazio usa a relação empírica da seção 6.5. | Vazio. |
| Atraso de maturação $M$ | Anos completos antes que o mangue migrado possa propagar. | 3 anos. |
| Migração sem camada de aptidão | Permite ignorar o filtro de solo quando não há camada ativada; vizinhança e elevação continuam obrigatórias. | Opção habilitada inicialmente quando a camada está desligada. |
| Motor e tamanho do bloco | Estratégia de execução e número de células por bloco no motor persistente. | Blocos; tamanho inicial de 10.000 células. |

Esses são os valores iniciais apresentados pela interface. Em cada estudo, registre os parâmetros efetivamente usados e suas fontes.

### Cálculo da forçante do nível do mar

Na interface, a taxa constante é informada em mm/ano e convertida para metros
por passo anual. Na equação, $r$ é essa taxa em m/ano; $t$ é o número de passos
anuais transcorridos; $H_t$ é a elevação acumulada desde o início, em metros;
$\delta H_t$ é a elevação acrescentada no passo $t$, também em metros; e
$H_0=0$ define a referência inicial. Assim, a mudança acumulada e o incremento
anual são

$$H_t=tr, \qquad \delta H_t=r \quad (t\geq1),$$

No modo CSV, $L(y)$ é o nível acumulado interpolado, em milímetros, no
ano-calendário $y$; $y_0$ é o ano inicial da simulação; e $t$ é o número de
passos anuais desde esse ano. O denominador 1000 converte milímetros em
metros. O motor calcula a elevação acumulada $H_t$ e o incremento entre dois
anos consecutivos $\delta H_t$ por

$$H_t=\frac{L(y_0+t)-L(y_0)}{1000}, \qquad
\delta H_t=\frac{L(y_0+t)-L(y_0+t-1)}{1000}.$$

Como $L(y_0)$ é subtraído, a série tem valor zero no início da simulação.
Ambos os resultados ficam em metros; $H_t$ alimenta o limiar $Z_t$, enquanto
$\delta H_t$ é usado na redistribuição local da inundação e na regressão de
acreção. A interface gráfica recebe a taxa em mm/ano. Para compatibilidade
com a convenção do parâmetro de linha de comando `--sea-level-rise-rate`,
esse parâmetro usa metros por passo anual.

<a id="6-regras-de-transicao"></a>
## 6. Regras de transição

<a id="61-inundacao-e-redistribuicao-local"></a>
### 6.1 Inundação e redistribuição local

Seja $T$ a altura de influência da maré definida na configuração, em metros e
no mesmo datum vertical do raster de elevação. $H_t$ é a elevação acumulada do
nível do mar desde o ano inicial, também em metros. O limiar $Z_t$ usado para
avaliar a elegibilidade à migração é a soma desses termos:

$$Z_t = T + H_t.$$

A inundação parte de uma célula-fonte $i$ cujo estado no início do ano é água
ou inundado e cuja elevação é não negativa. $\mathcal{N}_i$ é o conjunto de
células válidas na vizinhança de Moore de $i$ (até oito vizinhas); $j$ indica
uma dessas células; e $z_i^t$ e $z_j^t$ são as elevações, em metros, no
instantâneo do início do passo anual $t$. O conjunto $\mathcal{L}_i^t$
reúne apenas as vizinhas com elevação estritamente menor que a da fonte:

$$\mathcal{L}_i^t = \{j \in \mathcal{N}_i : z_j^t < z_i^t\}.$$

O número $|\mathcal{L}_i^t|$ é a quantidade dessas vizinhas. O incremento de
nível do mar $\delta H_t$, em metros por passo anual, é dividido igualmente
entre a fonte e as vizinhas reunidas no conjunto:

$$q_i^t = \frac{\delta H_t}{1 + |\mathcal{L}_i^t|}.$$

Assim, $q_i^t$ é a contribuição de uma fonte para a elevação da própria
célula-fonte e de cada vizinha mais baixa, em metros por passo anual. O motor
adiciona esse valor às elevações correntes dessas células. Uma vizinha que
ainda não era água ou inundada passa ao estado inundado correspondente à
classe-base, se esse estado estiver definido no catálogo. As comparações de
elevação e os estados-fontes vêm do instantâneo do início do ano. Novas
células inundadas passam a contribuir como fontes somente no ano seguinte;
várias fontes podem contribuir para a mesma célula no mesmo ano.

A altura de maré $T$ e o limiar $Z_t$ definem a elegibilidade para migração;
a propagação da inundação segue a regra local acima, a partir dos estados de
água ou inundados.

A inundação é representada por essa regra de propagação local. O motor acompanha
estados categóricos e elevação; não calcula salinidade, velocidade de corrente,
conectividade hidráulica detalhada nem balanço de massa da água. A abordagem
celular mantém continuidade conceitual com Bezerra et al. (2014).

<a id="62-migracao-e-elegibilidade"></a>
### 6.2 Migração e elegibilidade

Mangue original e mangue migrado maduro podem ser fontes. Para receber migração, uma célula precisa satisfazer simultaneamente:

1. estar na vizinhança de Moore de uma fonte;
2. ter perfil configurado como **Apta para migração**;
3. ter elevação corrente $z_j \leq Z_t$;
4. passar pelo filtro de solo, quando a camada estiver ativada.

Em notação compacta, $\mathcal{C}_{\mathrm{apta}}$ é o conjunto de classes
com perfil **Apta para migração**; $Q_j^{t,\mathrm{visita}}$ vale verdadeiro
quando a condição de solo da célula candidata $j$ é aceita ou quando o filtro
de solo está desligado. A função indicadora $\mathbf{1}[C]$ vale 1 quando a
condição $C$ é verdadeira e 0 quando é falsa. Para uma fonte $i$, a
elegibilidade da vizinha candidata $j$ é

$$E_{ij}^{t,\mathrm{visita}} = \mathbf{1}[j \in \mathcal{N}_i]
\mathbf{1}[c_j^{t,\mathrm{visita}} \in \mathcal{C}_{\mathrm{apta}}]
\mathbf{1}[z_j^{t,\mathrm{visita}} \leq Z_t]\mathbf{1}[Q_j^{t,\mathrm{visita}}].$$

Cada fator indicadora representa uma condição: $j \in \mathcal{N}_i$ verifica
se a candidata é vizinha válida; $c_j^{t,\mathrm{visita}} \in
\mathcal{C}_{\mathrm{apta}}$ verifica sua classe; $z_j^{t,\mathrm{visita}}\leq
Z_t$ compara a elevação corrente com o limiar; e $Q_j^{t,\mathrm{visita}}$
aplica o filtro de solo. O produto vale 1 somente quando as quatro condições
são satisfeitas; nesse caso, $E_{ij}^{t,\mathrm{visita}}=1$, e nos demais
$E_{ij}^{t,\mathrm{visita}}=0$. A conversão também exige que a célula-fonte
$i$ satisfaça a regra $P_i^{t,\mathrm{visita}}$ da seção seguinte.

Quando aceita, a célula recebe o estado **Mangue migrado**, inicia com idade zero e deixa de ser uma classe de cobertura apta. A regra percorre as células sequencialmente: a inundação consulta os estados e as elevações do começo do ano, enquanto solo e migração consultam valores correntes no instante em que cada célula é visitada. O atraso de maturação impede que uma célula recém-convertida abra imediatamente uma nova frente.

<a id="63-maturacao-do-mangue-migrado"></a>
### 6.3 Maturação do mangue migrado

O parâmetro $M$ é o número configurado de anos completos. $a_i^{t,\mathrm{visita}}$
é a idade do mangue migrado na célula $i$, contada em passos anuais completos;
$c_i^{t,\mathrm{visita}}$ é o estado corrente dessa célula. Mangue original
pode ser fonte imediatamente; mangue migrado só é fonte quando sua idade
alcança $M$. Uma célula recém-convertida recebe idade 0. Com $M=3$, precisa
completar três passos anuais antes de propagar. Se inundar antes disso, passa
a **Mangue migrado inundado**, sua idade é encerrada e ela deixa de ser fonte.

O contador $M$ é um parâmetro operacional configurável. Estudos sobre
reprodução precoce de *Rhizophora mangle* documentam variação biológica que
contextualiza esse parâmetro (Dangremond e Feller, 2016).

O teste de fonte pode ser resumido por

$$P_i^{t,\mathrm{visita}} = \mathbf{1}[c_i^{t,\mathrm{visita}}=\mathrm{mangue}]
\lor\left(\mathbf{1}[c_i^{t,\mathrm{visita}}=\mathrm{mangue\ migrado}]
\mathbf{1}[a_i^{t,\mathrm{visita}}\geq M]\right).$$

Na equação, $P_i^{t,\mathrm{visita}}$ vale 1 quando a célula $i$ pode atuar
como fonte e 0 nos demais casos; $\mathbf{1}[C]$ é a função indicadora já
definida; $\lor$ significa “ou”; e o produto das duas indicadoras entre
parênteses exige que o estado seja mangue migrado e que a idade seja pelo
menos $M$. Na conversão para mangue migrado, a idade começa em zero e avança
nos passos posteriores enquanto o estado permanecer ativo. O sobrescrito
`visita` identifica os valores correntes quando a célula é examinada na ordem
anual.

<a id="64-camada-de-aptidao-do-solo"></a>
### 6.4 Camada de aptidão do solo

A camada é opcional. Quando ativada, precisa estar alinhada aos demais rasters e usar códigos inteiros reconhecidos pela regra: 0 (canal), 3 (solo de mangue) e 9 (solo de mangue migrado). Esses códigos são perfis internos da camada de solo, não códigos de uso e cobertura.

O solo de mangue e o canal podem transferir o perfil de solo migrado às células vizinhas aptas com elevação até $Z_t$; células que já têm solo de mangue não são sobrescritas. Uma célula migrada madura com perfil 9 também pode propagar esse perfil. Para a conversão da cobertura, com a camada ativada, o destino precisa ter perfil de solo 3 ou 9. Se a camada estiver desligada e **Permitir migração sem camada de aptidão** estiver marcado, o filtro de solo é ignorado. O filtro de classe, vizinhança e elevação continua valendo.

<a id="65-acrecao-vertical"></a>
### 6.5 Acreção vertical

O usuário pode informar uma taxa constante $A_{\mathrm{usuário}}$ em mm/ano.
Se o campo ficar vazio, o motor usa a regressão empírica atribuída a Alongi
(2008, Fig. 7):

$$A_t = 1{,}693 + 0{,}939x_t,$$

Aqui, $x_t=1000\,\delta H_t$ converte o incremento anual do nível do mar
$\delta H_t$ de metros para milímetros por ano; $A_t$ é a taxa de acreção
resultante, também em mm/ano; 1,693 mm/ano é o intercepto da regressão; e
0,939 é seu coeficiente angular adimensional, pois entrada e saída estão em
mm/ano. A taxa calculada
é convertida para metros e aplicada à elevação em cada passo anual. Acreção
incide sobre estados com comportamento de mangue: mangue original, mangue
migrado e seus estados inundados. Quando o usuário informa uma taxa constante,
ela substitui a regressão durante toda a execução. A relação empírica associa
o incremento do nível do mar à taxa de acreção; uma aplicação pode informar
uma taxa própria documentada.

Na linha de comando, `--legacy-lua-accretion-typo` restringe a acreção às
células com perfil de solo 3 (solo de mangue). Registre essa opção quando
utilizada, pois ela altera quais células recebem o incremento.

Se $A_{\mathrm{usuário}}$ foi informado, a taxa aplicada é
$A_t=A_{\mathrm{usuário}}$; caso contrário, $A_t$ vem da regressão. O ajuste
$\Delta z_{i,\mathrm{acreção}}^t=A_t/1000$ é o aumento da elevação da célula
$i$ em metros no passo anual $t$; a divisão por 1000 converte mm em m.

<a id="comparacao-com-o-modelo-antecedente"></a>
### Comparação com o modelo antecedente

Bezerra et al. (2014) descrevem a formulação de referência para simular nível
do mar, inundação e migração na Ilha do Maranhão. O BR-MANGUE Studio mantém a
abordagem celular e a propagação espacial local. A forçante, a repartição do
incremento, o mapeamento comportamental, a maturação configurável, o
tratamento da acreção, o processamento raster e os estados inundados são
especificados nesta documentação e no release do software. Cite o artigo de
2014 como antecedente conceitual e histórico da aplicação.

<a id="origem-das-regras-e-expressoes"></a>
### Origem das regras e expressões

| Componente | Procedência e atribuição |
| --- | --- |
| Autômato celular e vizinhança de Moore | Conceito de modelagem estabelecido na literatura; a grade raster e a vizinhança de oito células são escolhas desta implementação (Wolfram, 1983; O’Sullivan, 2001). |
| Modelo antecedente de manguezal | Bezerra et al. (2014) é a referência conceitual e histórica para a aplicação na Ilha do Maranhão. |
| Forçante constante ou CSV | Conversão de unidades, interpolação linear e rebase ao ano inicial são regras de entrada implementadas no software. O arquivo e sua fonte definem o cenário climático. |
| Redistribuição local de inundação | Equação operacional especificada nesta documentação e implementada no BR-MANGUE Studio. |
| Acreção | Relação empírica de Alongi (2008, Fig. 7), usada como padrão quando não se informa taxa constante; uma taxa de estudo informada a substitui. |
| Maturação e elegibilidade | Parâmetros e condições configuráveis do software. A literatura sobre reprodução de mangues oferece contexto biológico, não calibra o padrão de três anos para todos os locais (Dangremond; Feller, 2016). |
| Extensão, ganhos e perdas | Definições operacionais dos estados e métricas implementadas no código; inundados são contados à parte da extensão ativa. |

<a id="7-ordem-de-atualizacao-anual"></a>
## 7. Ordem de atualização anual

Em cada passo, o motor preserva estados, elevações e idades do começo do ano e calcula a forçante ($H_t$, $\delta H_t$, $Z_t$ e acreção). Em seguida, percorre as células válidas na ordem armazenada. Para cada célula, avança a idade se ela já era mangue migrado, aplica a contribuição de inundação indicada pelo instantâneo, atualiza os perfis de solo, testa a migração e aplica acreção. As alterações de cobertura por inundação e migração, assim como os ajustes de elevação, ficam disponíveis às regras correntes subsequentes conforme a ordem de visita. Ao final, o motor conta estados e métricas, grava as saídas habilitadas e usa o novo estado como início do ano seguinte.

Com as mesmas entradas, configuração, versão e ordem das células, o fluxo é determinístico. O motor percorre sequencialmente as células válidas; essa ordem integra a regra de atualização anual.

<a id="8-motores-de-execucao"></a>
## 8. Motores de execução

- **Contínuo:** mantém os vetores da grade em memória e atualiza cada passo.
- **Blocos persistentes:** percorre as células em blocos e mantém estados e vizinhanças em arquivos mapeados em disco, alternando arquivos de estado por ano. O tamanho do bloco afeta o perfil de recursos, não a vizinhança nem os parâmetros ecológicos.
- **Adaptador DissModel:** caminho de compatibilidade que executa as regras pelo motor contínuo ou em blocos quando o componente opcional está disponível.

Os motores contínuo e em blocos usam a mesma ordem de células e as mesmas regras de transição. O modo em blocos reduz a necessidade de manter vetores completos de estado na RAM, mas exige espaço temporário em disco e pode ser mais lento dependendo do hardware e do tamanho do bloco.

<a id="9-saidas-e-metricas"></a>
## 9. Saídas e métricas

Conforme as opções da execução, a pasta de resultados pode conter:

| Arquivo/saída | Conteúdo |
| --- | --- |
| `initial_state_<ano>.tif` | Estado de cobertura e classes no ano inicial. |
| `states/state_<ano>.tif` | Raster anual do estado do modelo. |
| `final_state_<ano>.tif` | Estado final da execução. |
| `trajectory.csv` | Contagens por estado, elevação mínima/máxima, mudança do nível do mar e métricas anuais. |
| `sea_level_forcing.csv` | Forçante aplicada a cada ano, com mudança acumulada e incremento. |
| `input_metadata.json` | Grade, CRS, resolução, máscara, legenda e mapeamento dos dados. |
| `metadata.json` | Versão, parâmetros, motor, catálogo de estados, tempos, métricas e proveniência da execução. |
| `resource_samples.csv` | Amostras de uso de recursos, quando a coleta está disponível. |
| `transition_by_land_cover_code.csv` | Transições vinculadas aos códigos e nomes das classes de origem. |
| `migration_by_source_class.csv` | Resumo de migração por classe original, distinguindo mangue ativo e inundado. |

Os relatórios de transição e migração são exportados pelo fluxo da interface; os arquivos disponíveis podem variar conforme o modo e as opções escolhidas. Os GeoTIFFs guardam códigos de estado do projeto, que devem ser interpretados pelo catálogo em `metadata.json`.

A métrica `mangrove_extent` conta mangue original não inundado e mangue migrado ativo. Mangue inundado e mangue migrado inundado são contados separadamente e ficam fora da extensão ativa. Ganho anual conta células que entraram na extensão ativa; perda anual conta células que saíram dela. Assim, uma célula de mangue inundada contribui para a perda ativa, enquanto sua área inundada permanece registrada em outro estado.

O número nominal de atualizações célula-ano é $U=N\times n_{\mathrm{passos}}$, em que $N$ é o número de células válidas e $n_{\mathrm{passos}}$ é o total de passos anuais calculados. Por exemplo, uma execução com $N$ células válidas durante 75 passos contabiliza $75N$ atualizações célula-ano.

<a id="10-interpretacao-e-limites"></a>
## 10. Interpretação e limites

O motor acompanha estados categóricos da cobertura e elevação em passos anuais. Salinidade, marés diárias, ondas, transporte de propágulos, diferenças entre espécies, dinâmica demográfica, mortalidade por causas independentes e balanço de massa sedimentar ficam fora das variáveis simuladas. O raster de elevação e a altura de maré devem compartilhar o mesmo datum vertical. A classificação das áreas aptas, bloqueadas e inundadas segue o mapeamento e as hipóteses definidos para cada aplicação.

Os resultados são cenários condicionados às entradas e às regras documentadas. Uma aplicação científica deve declarar a origem e o processamento dos rasters, a referência vertical, as classes e seus códigos de origem, a forçante do nível do mar, os parâmetros, as opções de solo, a versão do software e os procedimentos independentes de calibração ou validação. A avaliação ecológica complementa a verificação computacional e os testes de desempenho.

<a id="11-reprodutibilidade-e-citacao"></a>
## 11. Reprodutibilidade e citação

Para reproduzir uma execução, arquive os rasters originais e preparados, as legendas, a máscara, a configuração de classes, os dados do nível do mar, os parâmetros, o arquivo de projeto, os metadados de saída e a versão exata do software. Projetos com trajetória CSV armazenam amostras e hash da fonte; cada execução registra a forçante anual usada.

O [DOI conceitual do BR-MANGUE Studio](https://doi.org/10.5281/zenodo.23509308) identifica o software e reúne suas versões arquivadas. O [repositório GitHub](https://github.com/oceanpep/br-mangue-studio) mantém o código-fonte e os executáveis.

<a id="12-referencias"></a>
## 12. Referências

- Alongi, D. M. (2008). Mangrove forests: Resilience, protection from tsunamis, and responses to global climate change. *Estuarine, Coastal and Shelf Science*, 76(1), 1–13. [https://doi.org/10.1016/j.ecss.2007.08.024](https://doi.org/10.1016/j.ecss.2007.08.024).
- Bezerra, D. da S., Amaral, S., Kampel, M., & Andrade, P. R. (2014). Simulating sea-level rise impacts on mangrove ecosystem adjacent to anthropic areas: The case of Maranhão Island, Brazilian Northeast. *Pan-American Journal of Aquatic Sciences*, 9(3), 188–198. [Artigo em PDF](https://panamjas.org/pdf_artigos/PANAMJAS_9(3)_188-198.pdf).
- Dangremond, E. M., & Feller, I. C. (2016). Precocious reproduction increases at the leading edge of a mangrove range expansion. *Ecology and Evolution*, 6(14), 5087–5092. [https://doi.org/10.1002/ece3.2270](https://doi.org/10.1002/ece3.2270).
- O’Sullivan, D. (2001). Exploring spatial process dynamics using irregular cellular automaton models. *Geographical Analysis*, 33(1), 1–18. [https://doi.org/10.1111/j.1538-4632.2001.tb00433.x](https://doi.org/10.1111/j.1538-4632.2001.tb00433.x).
- Sousa, F. M., Bezerra, D. da S., Costa, S. S., & Santos, R. L. (2026). *BR-MANGUE Studio* [software]. Zenodo. [https://doi.org/10.5281/zenodo.23509308](https://doi.org/10.5281/zenodo.23509308).
- Wolfram, S. (1983). Statistical mechanics of cellular automata. *Reviews of Modern Physics*, 55(3), 601–644. [https://doi.org/10.1103/RevModPhys.55.601](https://doi.org/10.1103/RevModPhys.55.601).
