# Atraso de maturação da migração

## Por que o atraso existe

Uma célula que acabou de ser convertida para `MANGUE_MIGRADO` representa uma
área recém-estabelecida. Ela não deve ser tratada como uma fonte reprodutiva
completa no passo anual imediatamente seguinte. O núcleo mantém, portanto,
um contador interno de idade para cada célula migrada.

O contador começa em zero no ano da conversão. A cada passo anual completo ele
é incrementado. Quando atinge `migration_maturity_years`, a célula pode
propagar para vizinhas elegíveis. A célula continua sendo registrada como
`MANGUE_MIGRADO`; a idade não é gravada no GeoTIFF de uso/cobertura.

## Valor padrão e sensibilidade

O padrão do Studio é `migration_maturity_years = 3`. Esse valor é uma
aproximação operacional, não uma constante universal para todas as espécies e
regiões. Recomenda-se testar pelo menos 2, 3 e 5 anos e reportar a análise de
sensibilidade.

O valor `0` é reservado para controle metodológico sem atraso biológico. Mesmo
nesse caso, uma célula recém-convertida não encadeia uma segunda conversão no
mesmo passo anual; ela só fica disponível a partir do passo seguinte.

## Base ecológica

Estudos com *Rhizophora mangle* documentam reprodução precoce em parte das
populações, inclusive em indivíduos de 1–2 anos na borda de expansão, mas a
idade de primeira reprodução varia com latitude e contexto ambiental. Uma
referência florestal reúne estimativas de início de floração por volta de
3–6 anos. Para *Rhizophora apiculata*, o ciclo entre estruturas reprodutivas e
propágulos pode se aproximar de três anos. Por isso, o parâmetro é exposto ao
usuário em vez de ser tratado como uma idade fixa do manguezal.

## Referências principais

- Dangremond, E. M.; Feller, I. C. (2016). *Precocious reproduction increases
  at the leading edge of a mangrove range expansion*. Ecology and Evolution.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC4979729/
- USDA Forest Service. *Rhizophora mangle L.* species account. A síntese indica
  floração possivelmente entre 3–5 anos e até cerca de 6 anos, dependendo das
  condições. https://research.fs.usda.gov/treesearch/download/45149.pdf
- Tomlinson, P. B. (1977). *Seasonal growth of mangrove trees in Southern
  Thailand. I. The phenology of Rhizophora apiculata*. Marine Biology.
  https://doi.org/10.1007/BF00395163

Essas fontes justificam a faixa de sensibilidade, mas não substituem a
calibração com dados de recrutamento e estabelecimento da área de estudo.
