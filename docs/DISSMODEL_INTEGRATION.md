# Integração com DissModel

O DissModel foi integrado como camada de coordenação da simulação. Ele fornece o relógio de execução (`Environment`), o componente do modelo (`Model`) e o registro de séries (`track_plot`). A regra do autômato permanece no núcleo Python traduzido do Lua.

## Modos

O adaptador `BRMangueLuaDissModel` pode chamar:

- `BrMangueGrid`, para execução contínua;
- `PersistentBlockRunner`, para execução persistente em blocos.

O segundo modo é selecionado pela linha de comando:

```powershell
python -m brmangue_lua.cli `
  --input "C:\caminho\elevacao_pol.shp" `
  --final-time 100 `
  --engine dissmodel `
  --dissmodel-runner blocks `
  --block-size 5000 `
  --output outputs\dissmodel_blocks
```

## Séries registradas

O DissModel registra:

- Mangrove;
- Flooded mangrove;
- Migrated mangrove;
- Annual gain;
- Annual loss.

O gráfico ao vivo é opcional. Para abri-lo em uma sessão gráfica, acrescente `--show-chart`. A execução sem essa opção continua adequada para terminal, Spyder, VS Code e testes automatizados.

O DissModel não fornece nem exige FES2022b nesta versão. Ele apenas coordena a execução e a visualização das mesmas regras originais do autômato celular.
