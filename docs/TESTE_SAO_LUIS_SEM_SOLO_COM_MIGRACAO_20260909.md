# Teste sem solo com migração por uso e cobertura

Após o primeiro ensaio da Ilha de São Luís, foi acrescentada uma opção para
grades sem mapa de solos. Quando essa opção está ativa, a classe de solo deixa
de ser necessária para a elegibilidade da migração: somente células vizinhas
de vegetação terrestre ou solo exposto, com elevação dentro da zona de
influência da maré, podem receber `MANGUE_MIGRADO`. Água, áreas antropizadas,
restrições e células inundadas continuam inelegíveis.

O comportamento literal do Lua, que exige `SOLO_MANGUE` ou
`SOLO_MANGUE_MIGRADO`, continua disponível com `--no-migration-without-soil`.
Assim, a mudança não quebra a auditoria de paridade e o usuário escolhe o
nível de informação disponível.

## Execução

Foi repetido o teste com MapBiomas Coleção 11, banda 41 (2025), ANADEM 30 m,
máscara da Ilha do Maranhão e sem camada de solo:

```powershell
python -m brmangue_lua.raster_cli `
  --mapbiomas "C:\BR_MANGUE_PY\estudos_caso\ilha_maranhao\dados\processados\mapbiomas_c11_1985_2025.tif" `
  --elevation "C:\BR_MANGUE_PY\estudos_caso\ilha_maranhao\dados\processados\elevacao_anadem_30m.tif" `
  --mask "C:\BR_MANGUE_PY\estudos_caso\ilha_maranhao\dados\processados\mascara_area_interesse.tif" `
  --mapbiomas-band 41 --mapbiomas-year 2025 `
  --initial-year 2025 --final-year 2035 `
  --engine blocks --block-size 10000 `
  --output outputs\ilha_sao_luis_mapbiomas2025_anadem_nosolo_migracao_2035
```

## Resultado

| Ano | Mangue vivo | Mangue migrado | Mangue inundado | Vegetação terrestre |
|---:|---:|---:|---:|---:|
| 2025 (base) | 172.502 | 0 | 0 | 77.747 |
| 2026 | 165.422 | 13.966 | 7.080 | 60.593 |
| 2030 | 129.364 | 15.655 | 43.138 | 48.898 |
| 2035 | 84.907 | 16.629 | 87.595 | 39.053 |

O resultado mostra que a ausência do solo não impede a migração, mas a
transição permanece restrita às classes naturais candidatas. A migração é
registrada separadamente da classe de mangue vivo, preservando a codificação
original do modelo Lua.

Os produtos completos estão em
`outputs/ilha_sao_luis_mapbiomas2025_anadem_nosolo_migracao_2035`, incluindo
trajetória, metadados, estados anuais e workspace persistente. A execução
continua sendo uma demonstração computacional sem validade preditiva, pois os
parâmetros do exemplo Lua ainda não foram calibrados para São Luís.

