# Auditoria de paridade Lua/Python

## Escopo

Foi executada a versão Lua/TerraME original e a tradução Python usando a mesma grade `data/anil/elevacao_pol.shp`, com 50.496 células, os mesmos parâmetros e 100 iterações.

## Resultado

| Verificação | Resultado |
|---|---|
| Número de passos | 100 em ambas as execuções |
| Número de células | 50.496 em ambas as execuções |
| Contagem de mangue | Idêntica em todos os passos |
| Contagem de vegetação | Idêntica em todos os passos |
| Contagem de mar | Idêntica em todos os passos |
| Contagem de área antropizada | Idêntica em todos os passos |
| Contagem de solo exposto | Idêntica em todos os passos |
| Mangue migrado | Idêntico em todos os passos |
| Mangue inundado | Idêntico em todos os passos |
| Menor elevação | Idêntica em todos os passos |
| Maior elevação | Diferença máxima de aproximadamente 1,1×10⁻⁷, causada por arredondamento |

## Observação sobre o campo de solo

O shapefile histórico possui o campo `ClaseSolos`, enquanto o script Lua seleciona `ClasseSolos`. No modo `--strict-lua-schema`, a tradução reproduz literalmente a consequência observada no TerraME: o campo de solo não ativa as regras de migração e acreção. No modo padrão, o Python aceita o alias para permitir um ensaio separado da regra pretendida pelo modelo.

## Conclusão

O núcleo de atualização celular foi traduzido com paridade operacional. A próxima implementação pode melhorar o armazenamento, a visualização e o desempenho sem alterar as regras do autômato. Qualquer correção ecológica ou física deverá ser desenvolvida em uma etapa posterior e comparada separadamente com esta linha de base.
