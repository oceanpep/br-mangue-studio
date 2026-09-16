# Comparação dos modos de processamento

## Ensaio

- Grade: `data/anil/elevacao_pol.shp` da versão Lua anexada.
- Células: 50.496.
- Passos: 100.
- Parâmetros: valores literais do Lua.
- Modo estrito de esquema: ativado.
- Tamanho do bloco: 5.000 células.

## Resultado do executor em memória

| Modo | Tempo observado | Trajetória |
|---|---:|---|
| Contínuo | 11,54 s | referência |
| Blocos | 11,26 s | idêntica à referência |

As duas trajetórias possuem 100 linhas e são exatamente iguais em todas as colunas. Os estados finais de `Usos`, `ClasseSolos` e `Alt2` também são idênticos.

## Interpretação

O modo em blocos persistente também foi executado no mesmo ensaio:

| Modo | Tempo observado | Armazenamento |
|---|---:|---|
| Blocos persistentes | 45,17 s | dois estados `numpy.memmap` |

Na execução posterior com diagnóstico de memória, o modo persistente apresentou aproximadamente 130,2 MiB de memória residente antes do processamento e 130,3 MiB no pico. A trajetória continuou exatamente igual à do modo contínuo.

A trajetória persistente foi exatamente igual à trajetória contínua, incluindo os estados finais de `Usos`, `ClasseSolos` e `Alt2`. O tempo maior neste recorte pequeno é esperado, pois há custo de leitura, cópia e gravação em disco. A vantagem do modo persistente aparece quando a grade deixa de caber confortavelmente na memória.

O modo `blocks-memory` permanece disponível apenas para comparação do particionamento em memória. O modo recomendado para grades grandes é `blocks`, que usa o workspace persistente.

O motor persistente preserva a ordem de atualização do autômato e a fotografia `past` por meio de dois estados alternados. Cada célula acessa no máximo oito índices de vizinhança, sem criar objetos espaciais individuais durante a simulação.

A próxima otimização será um leitor rasterizado nativo, que evitará a criação inicial do GeoDataFrame e permitirá construir o workspace diretamente de bandas georreferenciadas. A borda de uma célula da vizinhança de Moore continuará sendo preservada pelo índice compacto de vizinhos.
