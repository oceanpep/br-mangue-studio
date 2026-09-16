# Comparação com o protocolo publicado por Bezerra et al. (2014)

**Data do ensaio:** 14 de setembro de 2026  
**Objetivo:** reproduzir, no núcleo que alimenta o BR-MANGUE Studio, o protocolo temporal e os parâmetros descritos no artigo de Bezerra et al. (2014), sem utilizar a camada de solo, e separar claramente a verificação de implementação da reprodução numérica do estudo publicado.

## 1. O que foi publicado

O artigo de Bezerra, Amaral, Kampel e Andrade (2014), publicado no *Pan-American Journal of Aquatic Sciences*, propôs um autômato celular espacialmente explícito para explorar a resposta de manguezais da Ilha do Maranhão à elevação do nível do mar. A área de estudo corresponde à Ilha do Maranhão, formada pelos municípios de São Luís, São José de Ribamar, Paço do Lumiar e Raposa.

O banco de dados publicado foi organizado no TerraView 4.2.0 com resolução de 1 ha (células de 100 m × 100 m) e 94.704 células. O estado inicial representava o ano de 2011 e continha as classes mangue, estuário, área antrópica, vegetação terrestre e praia. Cada célula recebia, além da classe de cobertura, a classe de solo predominante, a menor altitude derivada do DEM SRTM e a condição de influência da maré. A altura média de maré adotada para a ilha foi de 6 m, valor confrontado com dados da Marinha do Brasil.

O experimento publicado não foi uma projeção anual contínua até 2100. Foram executados dez incrementos de elevação, de 0,1 m a 1,0 m, com cada passo representando 0,1 m. O artigo não atribui aos incrementos uma sequência de anos-calendário além da condição inicial de 2011; por isso, o ensaio atual registra passos 1–10, sem inventar datas. O artigo relatou aumento aproximado de 1.173 ha (6,75%) até 0,3 m e redução expressiva a partir de 0,4 m; no cenário de 1,0 m, a área simulada foi de aproximadamente 17.028 ha, 2,06% abaixo da condição inicial de 17.387 ha.

## 2. Regras relevantes para a comparação

As regras descritas no artigo foram transcritas para o núcleo Python sem alteração de significado:

1. O mangue ocorre dentro da área sob influência da maré (ATI).
2. A ATI inicial é definida pela altura de maré e é atualizada pelo incremento do nível do mar.
3. A água se propaga de células aquáticas para vizinhas de Moore, com até oito vizinhos.
4. Uma célula de vegetação terrestre pode ser convertida em mangue quando está na ATI e não encontra barreira antrópica ou natural.
5. Áreas antrópicas funcionam como barreiras; no modelo publicado, praia, altimetria acima da ATI e solo diferente do solo de mangue também funcionam como barreiras naturais.
6. O mangue é inundado quando a altura da coluna d’água alcança ou supera a altimetria da célula adjacente; a célula passa ao estado aquático inundado.
7. Áreas antrópicas, praia e vegetação terrestre também podem ser inundadas quando a mesma condição altimétrica é satisfeita.

O artigo ressalta que o incremento de área representa potencial de migração. A formulação não calcula hidrodinâmica horária, aporte sedimentar, erosão, subsidência, transporte de propágulos ou acreção suficiente para acompanhar o nível do mar. Esses limites são importantes para não interpretar o ensaio como previsão ecológica.

## 3. Diferença entre o banco publicado e o arquivo disponível

O arquivo histórico que acompanha a versão de referência disponível para auditoria é:

`tmp/brmangue_0_001_audit_20260909/brmangue-versao_0_001/data/anil/elevacao_pol.shp`

Ele possui 50.496 células de 30 m, no sistema SIRGAS 2000 / Polyconic, e os campos `Col`, `Lin`, `ClaseSolos`, `Alt2` e `Usos`. A distribuição da cobertura no arquivo é 25.432 células de mangue, 4.567 de vegetação terrestre, 3.364 de mar, 15.943 de área antropizada e 1.190 de solo descoberto. Esse arquivo não é a grade publicada no artigo: tem outra resolução, outro número de células, outra área total por célula e outra organização das classes.

Consequentemente, não é metodologicamente correto comparar diretamente as áreas em hectares do artigo com as áreas produzidas por este arquivo. O ensaio abaixo verifica a implementação e reproduz o protocolo de dez incrementos; a reprodução numérica da Figura 4 de Bezerra et al. exigiria a grade de 94.704 células e os dados de 2011 usados na publicação.

## 4. Configuração do ensaio BR-MANGUE Studio

Para atender ao teste solicitado, a camada de solo foi desativada. No BR-MANGUE Studio, o modo sem camada de aptidão mantém ativada a regra de compatibilidade que usa vegetação terrestre e solo exposto como candidatos à migração, sem inventar uma classe de solo. A resolução de 30 m corresponde a 0,09 ha por célula. Também foi executado um controle estrito, sem solo e sem fallback de migração, para separar o efeito dessa opção de compatibilidade.

Foram usados:

| Parâmetro | Valor | Correspondência ao artigo |
|---|---:|---|
| Passos anuais | 10 | dez incrementos publicados |
| Incremento por passo | 0,1 m | cenários de 0,1 a 1,0 m |
| Altura de maré | 6,0 m | valor médio adotado no artigo |
| Camada de solo | desativada | teste solicitado, sem solo |
| Migração sem solo | habilitada no Studio | compatibilidade por uso/cobertura |
| Vizinhança | Moore, até 8 células | regra publicada |
| Resolução do arquivo disponível | 30 m | diferente dos 100 m do artigo |
| Área por célula usada no relatório | 0,09 ha | 30 m × 30 m |

Comandos executados no núcleo do Studio:

```powershell
python -m brmangue_lua.cli --input "C:\BR_MANGUE_PY\tmp\brmangue_0_001_audit_20260909\brmangue-versao_0_001\data\anil\elevacao_pol.shp" --final-time 10 --tide-height 6 --sea-level-rise-rate 0.1 --engine continuous --strict-lua-schema --allow-migration-without-soil --output "outputs\bezerra2014_protocol_no_soil\continuous_fallback"

python -m brmangue_lua.cli --input "C:\BR_MANGUE_PY\tmp\brmangue_0_001_audit_20260909\brmangue-versao_0_001\data\anil\elevacao_pol.shp" --final-time 10 --tide-height 6 --sea-level-rise-rate 0.1 --engine blocks --block-size 10000 --strict-lua-schema --allow-migration-without-soil --output "outputs\bezerra2014_protocol_no_soil\blocks_fallback"

# Controle sem solo e sem a regra de compatibilidade
python -m brmangue_lua.cli --input "C:\BR_MANGUE_PY\tmp\brmangue_0_001_audit_20260909\brmangue-versao_0_001\data\anil\elevacao_pol.shp" --final-time 10 --tide-height 6 --sea-level-rise-rate 0.1 --engine continuous --strict-lua-schema --output "outputs\bezerra2014_protocol_no_soil\continuous"
```

## 5. Resultado do protocolo sem solo

Os dois motores produziram a mesma trajetória. A tabela apresenta a contagem de células; a conversão para hectares é feita multiplicando por 0,09.

| Passo | Mangue vivo (cél.) | Mangue migrado (cél.) | Mangue total (ha) | Mangue inundado (cél.) | Vegetação terrestre (cél.) |
|---:|---:|---:|---:|---:|---:|
| 1 | 25.377 | 742 | 2.350,71 | 55 | 3.659 |
| 2 | 25.168 | 742 | 2.331,90 | 264 | 3.031 |
| 3 | 24.989 | 742 | 2.315,79 | 443 | 2.636 |
| 4 | 24.832 | 742 | 2.301,66 | 600 | 2.382 |
| 5 | 24.691 | 742 | 2.288,97 | 741 | 2.214 |
| 6 | 24.568 | 742 | 2.277,90 | 864 | 2.073 |
| 7 | 24.454 | 742 | 2.267,64 | 978 | 1.976 |
| 8 | 24.346 | 742 | 2.257,92 | 1.086 | 1.914 |
| 9 | 24.256 | 742 | 2.249,82 | 1.176 | 1.857 |
| 10 | 24.183 | 848 | 2.252,79 | 1.249 | 1.702 |

Antes do primeiro passo, a grade disponível tinha 25.432 células de mangue (2.288,88 ha). Com a compatibilidade do Studio, o primeiro passo registrou 2.350,71 ha de mangue total (vivo + migrado) e o décimo, 2.252,79 ha. Em relação à condição inicial do arquivo, o décimo passo representa redução líquida de 1,58%; em relação ao primeiro passo já atualizado, a redução é de 4,17%. O mangue vivo isolado caiu 4,71% entre os passos 1 e 10. A migração somou 742 células no primeiro passo e 848 no décimo, enquanto 1.249 células estavam no estado de mangue inundado ao final. Esses valores são o resultado do arquivo de 30 m sem solo, e não podem ser comparados em hectares diretamente com a grade de 1 ha do artigo.

No controle estrito sem solo e sem fallback, a área de mangue vivo passou de 2.283,93 para 2.156,22 ha entre os passos 1 e 10, redução de 5,59%; em relação às 2.288,88 ha da condição inicial, a redução no décimo passo é de 5,80%, e não houve migração. A diferença entre os dois ensaios quantifica o efeito da opção de compatibilidade do Studio.

Para deixar explícito o limite da comparação, os pontos de referência ficam assim:

| Elevação acumulada | Bezerra et al. (2014) | Studio, sem solo e com compatibilidade |
|---:|---:|---:|
| 0,0 m (inicial) | 17.387 ha | 2.288,88 ha |
| 0,3 m (passo 3) | aproximadamente 18.560 ha (+6,75%) | 2.315,79 ha (+1,18% em relação ao inicial) |
| 1,0 m (passo 10) | aproximadamente 17.028 ha (-2,06% em relação ao inicial) | 2.252,79 ha (-1,58% em relação ao inicial) |

As porcentagens não devem ser interpretadas como desempenho relativo entre os modelos: os denominadores, a resolução, as classes e a presença da camada de solo são diferentes. A tabela serve para mostrar por que a comparação numérica direta não é válida com o arquivo atualmente disponível.

## 6. Verificação dos motores

Os arquivos `continuous_fallback/trajectory.csv` e `blocks_fallback/trajectory.csv` possuem 10 linhas e as mesmas 10 colunas; a comparação célula a célula resultou em diferença máxima igual a zero. O processamento em blocos, portanto, não alterou as regras nem os resultados; ele apenas mudou a forma de percorrer e armazenar a grade. A equivalência operacional entre os motores é uma verificação de implementação, não uma validação ecológica.

## 7. Arquivos de saída

- [Trajetória contínua sem solo, com compatibilidade do Studio](../outputs/bezerra2014_protocol_no_soil/continuous_fallback/trajectory.csv)
- [Trajetória em blocos sem solo, com compatibilidade do Studio](../outputs/bezerra2014_protocol_no_soil/blocks_fallback/trajectory.csv)
- [Controle contínuo sem solo e sem compatibilidade](../outputs/bezerra2014_protocol_no_soil/continuous/trajectory.csv)
- [Teste de paridade Lua–Python com 100 passos](../outputs/bezerra_reference/)

## 8. Interpretação e limite da comparação

O resultado demonstra que o BR-MANGUE Studio consegue executar dez atualizações com os parâmetros centrais do experimento de 2014 e que os motores contínuo e em blocos são determinísticos. Com a opção de compatibilidade sem solo, o sistema registra simultaneamente inundação e migração potencial; no controle estrito, a migração é desativada e a perda é maior. Essa separação é necessária para que o leitor saiba qual regra foi usada em cada curva.

Não é possível afirmar, a partir desse ensaio, que o Studio reproduziu a curva de 17.387 ha, o máximo de 6,75% em 0,3 m ou o valor de 17.028 ha em 1,0 m. Esses números pertencem à grade e aos dados publicados por Bezerra et al. (2014), que não estão presentes no arquivo histórico auditado. A comparação cientificamente válida nesta etapa é: (i) mesma área de estudo conceitual; (ii) mesmas regras e altura de maré; (iii) mesmo protocolo de dez incrementos; (iv) execução sem solo, conforme solicitado; e (v) explicitação das diferenças de resolução e entrada.

**Referência do artigo:** Bezerra, D. S.; Amaral, S.; Kampel, M.; Andrade, P. R. *Simulating sea-level rise impacts on mangrove ecosystem adjacent to anthropic areas: the case of Maranhão Island, Brazilian Northeast*. Pan-American Journal of Aquatic Sciences, 9(3), 188–198, 2014. [Texto completo](https://panamjas.org/pdf_artigos/PANAMJAS_9%283%29_188-198.pdf).
