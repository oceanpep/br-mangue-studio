# Pacote de teste para pesquisadores — Ilha de São Luís

Este pacote contém uma pequena área de demonstração para testar o BR-MANGUE
Studio sem precisar procurar ou baixar dados adicionais.

## Conteúdo

- `BR-MANGUE.exe`: executável Windows da versão 1.0.0;
- `mapbiomas_2025_ilha_sao_luis.tif`: uso e cobertura da terra do MapBiomas,
  banda de 2025, em GeoTIFF categórico;
- `anadem_30m_ilha_sao_luis.tif`: modelo digital de terreno ANADEM, resolução
  de 30 m;
- `mascara_area_interesse.tif`: máscara da área de demonstração;
- `brmangue_project.json`: projeto já configurado para abrir no Studio;
- `Manual_Usuario_BR_MANGUE_Studio_1.0.0.pdf`: manual de uso.

## Como iniciar

1. Extraia todos os arquivos para uma pasta com permissão de escrita.
2. Abra `BR-MANGUE.exe`.
3. No menu **Project**, abra `brmangue_project.json`.
4. Confira o mapeamento das classes na aba **Class mapping**.
5. Na aba **Simulation**, revise os parâmetros e clique em **Run simulation**.
6. Consulte **Results**, **Trajectory**, **Animation** e **Console**.

O projeto usa 2025 como estado inicial e está configurado para uma simulação
demonstrativa até 2100. Os resultados são para avaliação de usabilidade e
interpretação do modelo; não representam uma previsão calibrada para a Ilha de
São Luís.

## O que gostaríamos de receber

Ao testar, observe principalmente: facilidade de preparar os dados, clareza
do mapeamento de classes, compreensão dos parâmetros, mensagens de validação,
tempo de execução, leitura dos gráficos e utilidade dos arquivos gerados.
Registre qualquer erro, dúvida ou sugestão e responda ao convite com os passos
que realizou e, se possível, uma captura de tela.

## Verificação dos dados

Os três rasters estão alinhados na mesma grade, resolução e sistema de
referência. O uso e cobertura é categórico; o ANADEM é numérico; a máscara
delimita o domínio da demonstração. O arquivo `brmangue_project.json` aponta
para os nomes desses arquivos e pode ser editado para testar outros cenários.
