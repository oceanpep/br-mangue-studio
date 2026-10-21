"""Interface translations and persisted language preference for BR-MANGUE Studio."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

LANGUAGES = ("English", "Português (Brasil)")
LANGUAGE_CODES = {"English": "en", "Português (Brasil)": "pt-BR"}
CODE_TO_LANGUAGE = {code: name for name, code in LANGUAGE_CODES.items()}

_PT_BR = {
    "Flooded area: {name}": "Área inundada: {name}",
    "Flooded Natural vegetation": "Vegetação natural inundada",
    "Flooded Bare soil": "Solo descoberto inundado",
    "Flooded Anthropized / blocked": "Área antropizada / bloqueada inundada",
    "Easting (km)": "Coordenada leste (km)",
    "Northing (km)": "Coordenada norte (km)",
    "Longitude": "Longitude",
    "Latitude": "Latitude",
    "Forest Formation": "Formação florestal",
    "Savanna Formation": "Formação savânica",
    "Floodable Forest": "Floresta alagável",
    "Forest Plantation": "Silvicultura",
    "Wetland": "Campo alagado e área pantanosa",
    "Grassland Formation": "Formação campestre",
    "Pasture": "Pastagem",
    "Mosaic of Uses": "Mosaico de usos",
    "Beach, Dune and Sand Spot": "Praia, duna e areal",
    "Urban Area": "Área urbanizada",
    "Other non Vegetated Areas": "Outras áreas não vegetadas",
    "Mining": "Mineração",
    "Aquaculture": "Aquicultura",
    "Hypersaline Tidal Flat": "Apicum",
    "River, Lake and Ocean": "Rio, lago e oceano",
    "Palm Oil": "Dendê",
    "Soybean": "Soja",
    "Other Temporary Crops": "Outras lavouras temporárias",
    "Herbaceous Sandbank Vegetation": "Restinga herbácea ou arbustiva",
    "Language": "Idioma",
    "Select": "Selecione",
    "BR-MANGUE Studio": "BR-MANGUE Studio",
    "Version {version}": "Versão {version}",
    "Version": "Versão",
    "by": "por",
    "Spatial cellular model for coastal change": "Modelo espacial de autômatos celulares para mudanças costeiras",
    "Loading workspace…": "Carregando o ambiente de trabalho…",
    "Desktop interface for the BR-MANGUE cellular model.": "Interface desktop do modelo de autômatos celulares BR-MANGUE.",
    "The model accepts aligned user-provided rasters; inputs are read-only and products are saved in the project results folder.": "O modelo aceita rasters alinhados fornecidos pelo usuário. Os dados de entrada não são alterados e os resultados são salvos na pasta do projeto.",
    "New project": "Novo projeto",
    "Open project": "Abrir projeto",
    "Save project": "Salvar projeto",
    "Save project as...": "Salvar projeto como...",
    "Exit": "Sair",
    "Project": "Projeto",
    "Load / inspect inputs": "Carregar / inspecionar dados",
    "Refresh land-cover classes": "Atualizar classes de cobertura da terra",
    "Data": "Dados",
    "About": "Sobre",
    "Help": "Ajuda",
    "Create Linux shortcuts": "Criar atalhos no Linux",
    "Application shortcuts": "Atalhos do aplicativo",
    "The application shortcut is ready. Open BR-MANGUE Studio from your applications menu.": "O atalho do aplicativo está pronto. Abra o BR-MANGUE Studio pelo menu de aplicativos.",
    "Create shortcuts from the packaged Linux executable.": "Crie os atalhos pelo executável Linux do programa.",
    "The application executable is missing or is not executable.": "O executável do programa não foi encontrado ou está sem permissão de execução.",
    "The bundled application icon is missing.": "O ícone incluído no programa não foi encontrado.",
    "Project data": "Dados do projeto",
    "Class mapping": "Mapeamento de classes",
    "Simulation": "Simulação",
    "Save CSV example": "Salvar exemplo CSV",
    "Format and data sources": "Formato e fontes de dados",
    "IPCC AR6 archive": "Arquivo IPCC AR6",
    "Synthetic example saved. Replace its values with documented projections before research use.": "Exemplo sintético salvo. Substitua os valores por projeções documentadas antes de usá-lo na pesquisa.",
    "Create a spreadsheet with two columns named year and sea_level_mm. Enter calendar years and cumulative sea levels in millimetres, all relative to the same baseline. Save as CSV (UTF-8). Commas or semicolons are accepted as separators; use decimal commas only with semicolons.\n\nUse at least two different years in increasing order. The file must cover the entire simulation: for 2025–2100, decadal samples from 2020 to 2100 are sufficient. The model interpolates intermediate years and subtracts the initial-year level automatically.\n\nData sources: obtain regional projections from the NASA/IPCC AR6 tool, the IPCC AR6 archive, or the Earth Engine catalog. Select one location or documented regional summary, one scenario, and one percentile per file. Copy the years and cumulative total sea-level values into the two required columns. Source downloads may need reformatting. Convert metres to millimetres by multiplying by 1000, or centimetres by 10.\n\nUse projected cumulative levels, not annual rates. Record the source, location, scenario, percentile, units, and reference period alongside the CSV. An observed annual trend can be entered directly in Constant rate.\n\nSave CSV example creates a synthetic file for learning the format. Replace all example values before using it in research. Each run exports the actual annual forcing in sea_level_forcing.csv.": "Crie uma planilha com duas colunas chamadas year e sea_level_mm. Preencha os anos e os níveis acumulados em milímetros, todos relativos ao mesmo período de referência. Salve como CSV (UTF-8). O separador pode ser vírgula ou ponto e vírgula; use vírgula decimal apenas com separador ponto e vírgula.\n\nUse pelo menos dois anos diferentes, em ordem crescente. O arquivo deve cobrir toda a simulação: para 2025–2100, bastam valores decenais de 2020 a 2100. O modelo interpola os anos intermediários e desconta automaticamente o nível do ano inicial.\n\nFontes: obtenha projeções regionais na ferramenta NASA/IPCC AR6, no arquivo IPCC AR6 ou no catálogo do Earth Engine. Escolha um local ou uma síntese regional documentada, um cenário e um percentil por arquivo. Copie os anos e os níveis totais acumulados para as duas colunas exigidas. Os arquivos da fonte podem precisar de adaptação. Converta metros em milímetros multiplicando por 1000, ou centímetros por 10.\n\nUse níveis acumulados projetados, e não taxas anuais. Registre a fonte, o local, o cenário, o percentil, as unidades e o período de referência junto ao CSV. Uma tendência anual observada pode ser informada diretamente em Taxa constante.\n\nSalvar exemplo CSV cria um arquivo sintético para conhecer o formato. Substitua todos os valores de exemplo antes de usá-lo na pesquisa. Cada execução exporta a curva anual utilizada em sea_level_forcing.csv.",

    "Browse...": "Procurar...",
    "Input rasters (read-only)": "Rasters de entrada (somente leitura)",
    "Choose any aligned categorical raster for land cover and any aligned elevation raster. The model does not require a specific provider.": "Selecione um raster categórico de cobertura da terra e um raster de elevação alinhados. O modelo não exige uma fonte de dados específica.",
    "Land-cover / categorical raster (GeoTIFF)": "Raster de cobertura da terra / categórico (GeoTIFF)",
    "Elevation raster (GeoTIFF)": "Raster de elevação (GeoTIFF)",
    "Study-area mask": "Máscara da área de estudo",
    "Mangrove suitability raster": "Raster de adequabilidade para manguezais",
    "Study-area mask (optional)": "Máscara da área de estudo (opcional)",
    "Mangrove suitability raster (optional)": "Raster de adequabilidade para manguezais (opcional)",
    " (optional)": " (opcional)",
    "Raster band (1-based)": "Banda do raster (começa em 1)",
    "Reference year (optional)": "Ano de referência (opcional)",
    "For a multiband raster, select the band that represents the desired reference date. Leave the year blank when the raster has no date metadata.": "Em um raster multibanda, selecione a banda correspondente à data de referência. Deixe o ano vazio quando o raster não tiver essa informação.",
    "Inspect land-cover classes": "Inspecionar classes de cobertura da terra",
    "Validate and load inputs": "Validar e carregar dados",
    "Coordinate reference": "Sistema de referência de coordenadas",
    "Detected CRS": "SRC detectado",
    "Datum metadata": "Metadados do datum",
    "Input CRS check (optional)": "Verificar SRC de entrada (opcional)",
    "Reprojection target (search by name or EPSG code)": "SRC de destino (pesquise pelo nome ou código EPSG)",
    "Type a name such as SIRGAS 2000 or an EPSG code. The default is 10857, using the supplied Albers Brasil definition.": "Digite um nome, como SIRGAS 2000, ou um código EPSG. O padrão é 10857, com a definição Albers Brasil incluída.",
    "Target resolution (map units/pixel, optional)": "Resolução de destino (unidades do mapa/pixel, opcional)",
    "Reproject and align input rasters": "Reprojetar e alinhar rasters de entrada",
    "Declared vertical datum (metadata only)": "Datum vertical declarado (somente metadados)",
    "Reprojection creates new aligned GeoTIFF copies in the project prepared_inputs folder; original rasters remain unchanged. Vertical datum conversion is not inferred automatically.": "A reprojeção cria cópias alinhadas em GeoTIFF na pasta prepared_inputs do projeto; os rasters originais não são alterados. A conversão do datum vertical não é inferida automaticamente.",
    "Source class → model role": "Classe de origem → categoria do modelo",
    "Source class → model class": "Classe de origem → classe do modelo",
    "Model class": "Classe do modelo",
    "Mapping mode": "Modo de mapeamento",
    "Use standard model classes": "Usar classes padrão do modelo",
    "Define my own classes": "Definir minhas próprias classes",
    "Custom mode starts with no assignments. Add classes below, then assign each raster code to a custom class or choose Exclude.": "O modo personalizado começa sem atribuições. Adicione classes abaixo e associe cada código do raster a uma classe criada ou escolha Excluir.",
    "Unassigned": "Não atribuído",
    "Assign each source code to a custom class or choose Exclude before loading inputs. Unassigned codes: {codes}.": "Antes de carregar os dados, associe cada código de origem a uma classe personalizada ou escolha Excluir. Códigos não atribuídos: {codes}.",
    "Add at least one custom model class before loading inputs in custom mode.": "Adicione pelo menos uma classe personalizada antes de carregar os dados no modo personalizado.",
    "The raster contains source codes that were not inspected. Inspect the raster again and assign or exclude them: {codes}.": "O raster contém códigos de origem que não foram inspecionados. Inspecione novamente o raster e associe ou exclua estes códigos: {codes}.",
    "Choose how each numeric class from the categorical raster is interpreted. Excluded codes become NoData.": "Defina como cada classe numérica do raster será interpretada. Os códigos excluídos serão tratados como NoData.",
    "Optional custom classes": "Classes personalizadas (opcional)",
    "Class name": "Nome da classe",
    "Behavior profile": "Perfil de comportamento",
    "Fixed class": "Classe fixa",
    "Mangrove source": "Fonte de mangue",
    "Bare soil": "Solo descoberto",
    "Anthropized area": "Área antropizada",
    "Water body": "Corpo d'água",
    "Select the existing model rules that this class will follow. Its name and color identify it in the outputs.": "Selecione as regras existentes do modelo para esta classe. O nome e a cor identificam a classe nos resultados.",
    "Assign these classes to source codes below. Their selected behavior profile applies existing model rules; fixed classes keep their state.": "Atribua estas classes aos códigos de origem abaixo. O perfil selecionado aplica regras existentes do modelo; classes fixas mantêm seu estado.",
    "Custom class": "Classe personalizada",
    "Choose class color": "Escolher cor da classe",
    "State": "Estado",
    "Color": "Cor",
    "Add": "Adicionar",
    "Remove": "Remover",
    "Enter a name for the custom class.": "Informe um nome para a classe personalizada.",
    "Custom class names must be unique.": "Os nomes das classes personalizadas devem ser únicos.",
    "Reassign its source classes before removing this custom class.": "Reatribua os códigos de origem antes de remover esta classe personalizada.",
    "The model supports custom class codes through {limit}.": "O modelo aceita códigos de classe personalizados até {limit}.",
    "Inspect the land-cover raster to list its classes.": "Inspecione o raster de cobertura da terra para listar suas classes.",
    "Initial calendar year": "Ano inicial",
    "Final calendar year": "Ano final",
    "Tidal influence height (m)": "Altura de influência da maré (m)",
    "Sea-level rise (mm/year)": "Elevação do nível do mar (mm/ano)",
    "Sea-level forcing": "Variação do nível do mar",
    "Constant rate": "Taxa constante",
    "Year-based trajectory (CSV)": "Trajetória por ano (CSV)",
    "Choose trajectory CSV": "Selecionar trajetória CSV",
    "Preview curve": "Visualizar curva",
    "Sea-level trajectory": "Trajetória do nível do mar",
    "Sea-level change since initial year (mm)": "Elevação desde o ano inicial (mm)",
    "CSV columns: year, sea_level_mm. Use cumulative levels relative to a common baseline.": "Colunas do CSV: year, sea_level_mm. Informe níveis acumulados em relação a uma referência comum.",
    "{first}–{last}: {rise:.1f} mm rise; annual increments {minimum:.2f}–{maximum:.2f} mm/year.": "{first}–{last}: elevação de {rise:.1f} mm; acréscimos anuais de {minimum:.2f}–{maximum:.2f} mm/ano.",
    "Choose a trajectory CSV before running the simulation.": "Selecione um CSV de trajetória antes de executar a simulação.",
    "The trajectory CSV is empty.": "O CSV da trajetória está vazio.",
    "The trajectory CSV requires columns year and sea_level_mm.": "O CSV da trajetória precisa conter as colunas year e sea_level_mm.",
    "A trajectory requires at least two year/sea_level_mm pairs.": "A trajetória precisa conter pelo menos dois pares de ano e nível em mm.",
    "Trajectory years must be whole calendar years.": "Os anos da trajetória precisam ser anos inteiros do calendário.",
    "Trajectory years must be unique and strictly increasing.": "Os anos da trajetória precisam ser únicos e estar em ordem crescente.",
    "Trajectory sea levels must be finite numbers in millimetres.": "Os níveis da trajetória precisam ser números finitos em milímetros.",
    "Trajectory years and sea levels must be numeric.": "Os anos e níveis da trajetória precisam ser numéricos.",
    "Trajectories require millimetres and linear interpolation.": "As trajetórias precisam usar milímetros e interpolação linear.",
    "Final calendar year must be greater than or equal to initial year.": "O ano final precisa ser maior ou igual ao ano inicial.",
    "Constant surface accretion (mm/year, optional)": "Acreção constante da superfície (mm/ano, opcional)",
    "Migration maturation delay (years)": "Atraso para maturação da migração (anos)",
    "Block size (cells)": "Tamanho do bloco (células)",
    "Processing engine": "Mecanismo de processamento",
    "Persistent blocks": "Blocos persistentes",
    "Continuous": "Contínuo",
    "DissModel": "DissModel",
    "Enable optional mangrove suitability layer": "Ativar camada opcional de adequabilidade para manguezais",
    "Allow migration without suitability layer": "Permitir migração sem camada de adequabilidade",
    "A migrated cell becomes a new propagation source only after the maturation delay. Use 0 for a sensitivity test without a biological delay.": "Uma célula migrada só se torna fonte de propagação após o período de maturação. Use 0 para testar o modelo sem esse atraso.",
    "Visualization": "Visualização",
    "Console": "Console",
    "Results": "Resultados",
    "Trajectory": "Trajetória",
    "Animation": "Animação",
    "Model rules": "Regras do modelo",
    "Initial state": "Estado inicial",
    "Elevation / relative surface": "Elevação / superfície relativa",
    "Current state": "Estado atual",
    "Scenario trajectory": "Trajetória do cenário",
    "Cell state": "Estado da célula",
    "Mangrove trajectory": "Trajetória do manguezal",
    "Net annual change": "Variação anual líquida",
    "Model states:": "Estados do modelo:",
    "Model states": "Estados do modelo",
    "Run simulation": "Executar simulação",
    "Open results folder": "Abrir pasta de resultados",
    "Reset layout": "Redefinir layout",
    "Execution messages and annual summaries appear here while the simulation runs.": "As mensagens de execução e os resumos anuais aparecem aqui durante a simulação.",
    "Project outputs": "Arquivos do projeto",
    "Each run stores annual state rasters, four independent figure series, a complete simulation table, transition summaries and metadata in its own timestamped folder.": "Cada execução salva rasters anuais dos estados, quatro séries de figuras, uma tabela completa da simulação, resumos das transições e metadados em uma pasta própria.",
    "Open simulation table": "Abrir tabela da simulação",
    "Run a simulation to generate the annual preview.": "Execute uma simulação para gerar a prévia anual.",
    "Play": "Reproduzir",
    "Pause": "Pausar",
    "Previous": "Anterior",
    "Next": "Próximo",
    "Open state GIF": "Abrir GIF dos estados",
    "Export state GIF...": "Exportar GIF dos estados...",
    "Open animations": "Abrir animações",
    "Open annual figures": "Abrir figuras anuais",
    "This view lists the raster classes and rule profiles assigned in the current project.": "Esta tela lista as classes do raster e os perfis de regras atribuídos no projeto atual.",
    "Custom class mapping": "Mapeamento de classes personalizadas",
    "Standard class mapping": "Mapeamento de classes padrão",
    "Raster code": "Código do raster",
    "Assigned model class": "Classe atribuída no modelo",
    "Transition profile": "Perfil de transição",
    "Built-in rule set": "Regras padrão do modelo",
    "No rule assigned": "Nenhuma regra atribuída",
    "Excluded from simulation": "Excluída da simulação",
    "Inspect a categorical raster to see its class assignments here.": "Inspecione um raster categórico para ver aqui as atribuições das classes.",
    "No raster codes have been inspected yet. The custom classes below are defined and ready for assignment.": "Nenhum código do raster foi inspecionado. As classes personalizadas abaixo estão definidas e prontas para atribuição.",
    "Custom mode starts with no assignments. Assign every raster code to a custom class or choose Exclude before loading inputs.": "O modo personalizado começa sem atribuições. Associe cada código do raster a uma classe personalizada ou escolha Excluir antes de carregar os dados.",
    "Each raster code follows the behavior profile shown for its assigned custom class.": "Cada código do raster segue o perfil de comportamento da classe personalizada atribuída.",
    "Each raster code follows its assigned standard model class.": "Cada código do raster segue a classe padrão do modelo que lhe foi atribuída.",
    "Live run monitor": "Monitor da execução",
    "Net change by class": "Variação líquida por classe",
    "Loss ↓     0     ↑ Gain": "Perda ↓     0     ↑ Ganho",
    "Each bar shows the net change from the initial state. Gains rise above zero and losses fall below zero.": "Cada barra mostra a variação líquida em relação ao estado inicial. Ganhos ficam acima de zero e perdas, abaixo.",
    "Code": "Código",
    "Pixels": "Pixels",
    "Model role": "Categoria do modelo",
    "Exclude": "Excluir",
    "Mangrove": "Manguezal",
    "Natural vegetation": "Vegetação natural",
    "Water": "Água",
    "Anthropized / blocked": "Área antropizada / bloqueada",
    "Migrated mangrove": "Manguezal migrado",
    "Flooded mangrove": "Manguezal inundado",
    "Migrated": "Migrado",
    "Flooded": "Inundado",
    "Vegetation": "Vegetação",
    "Developed": "Área urbanizada",
    "Land-cover inspection": "Inspeção da cobertura da terra",
    "Select a valid categorical land-cover GeoTIFF first.": "Selecione primeiro um GeoTIFF categórico válido de cobertura da terra.",
    "Inputs prepared": "Dados preparados",
    "Aligned copies were created in:\n{folder}\n\nOriginal rasters were not modified. Review the class mapping and click Validate and load inputs.": "Cópias alinhadas foram criadas em:\n{folder}\n\nOs rasters originais não foram alterados. Confira o mapeamento de classes e clique em Validar e carregar dados.",
    "Reprojection": "Reprojeção",
    "Input validation": "Validação dos dados",
    "A simulation is already running.": "Já existe uma simulação em execução.",
    "No figure available for this component.": "Não há figura disponível para este componente.",
    "No simulation has been run in this project.": "Nenhuma simulação foi executada neste projeto.",
    "No annual figures generated yet.": "Ainda não foram geradas figuras anuais.",
    "No annual figures were generated.": "Nenhuma figura anual foi gerada.",
    "Year —": "Ano —",
    "Simulation running…": "Simulação em andamento…",
    "Run a simulation first to generate the GIF.": "Execute uma simulação para gerar o GIF.",
    "Run a simulation first to generate the animations.": "Execute uma simulação para gerar as animações.",
    "Run a simulation first to generate annual figures.": "Execute uma simulação para gerar as figuras anuais.",
    "Simulation table": "Tabela da simulação",
    "Animations": "Animações",
    "Annual figures": "Figuras anuais",
    "Results": "Resultados",
    "Run a simulation first to generate the simulation table.": "Execute uma simulação para gerar a tabela da simulação.",
    "Unable to open {path}:\n{error}": "Não foi possível abrir {path}:\n{error}",
    "Choose a new BR-MANGUE project folder": "Selecione uma pasta para o novo projeto BR-MANGUE",
    "Save BR-MANGUE project": "Salvar projeto BR-MANGUE",
    "Open BR-MANGUE project": "Abrir projeto BR-MANGUE",
    "Choose a folder for prepared input rasters": "Selecione uma pasta para os rasters de entrada preparados",
    "Choose project folder for results": "Selecione a pasta do projeto para os resultados",
    "Export simulation GIF": "Exportar GIF da simulação",
    "Select {label}": "Selecione {label}",
    "GeoTIFF": "GeoTIFF",
    "Animated GIF": "GIF animado",
    "All files": "Todos os arquivos",
    "BR-MANGUE project": "Projeto BR-MANGUE",
    "JSON": "JSON",
    "Project JSON": "Projeto JSON",
    "No project or simulation output exists yet.": "Ainda não há projeto ou resultados de simulação.",
    "Aligned copies were created in:": "Cópias alinhadas foram criadas em:",
    "Original rasters were not modified. Review the class mapping and click Validate and load inputs.": "Os rasters originais não foram alterados. Confira o mapeamento de classes e clique em Validar e carregar dados.",
    "Select valid land-cover and elevation rasters first.": "Selecione primeiro rasters válidos de cobertura da terra e elevação.",
    "Target resolution must be positive.": "A resolução de destino deve ser positiva.",
    "The target CRS produced an empty raster grid.": "O SRC de destino gerou uma grade raster vazia.",
    "No figure available for this component.": "Não há figura disponível para este componente.",
    "Not loaded": "Não carregado",
    "See CRS WKT / source metadata": "Consulte o WKT do SRC / metadados da fonte",
    "No project open": "Nenhum projeto aberto",
    "Ready": "Pronto",
    "Inputs validated": "Dados validados",
    "Prepared aligned rasters; validate and load inputs": "Rasters alinhados e preparados; valide e carregue os dados",
    "Running…": "Executando…",
    "Failed": "Falhou",
    "Simulation started.": "Simulação iniciada.",
    "Simulation finished.": "Simulação concluída.",
    "Simulation complete. Generating annual figures and GIF in the background…": "Simulação concluída. Gerando figuras anuais e GIF em segundo plano…",
    "Generating annual figures and GIF…": "Gerando figuras anuais e GIF…",
    "not started": "simulação não iniciada",
    "Four independent animations and figures saved  |  {count} annual frames": "Quatro séries de figuras e animações salvas  |  {count} quadros anuais",
    "Peak process RAM:": "Pico de RAM do processo:",
    "Throughput:": "Vazão:",
    "Output size:": "Tamanho dos arquivos:",
    "Model time:": "Tempo do modelo:",
    "Total run time:": "Tempo total:",
    "Elapsed:": "Tempo decorrido:",
    "Calendar year:": "Ano calendário:",
    "Mangrove:": "Manguezal:",
    "Migrated mangrove:": "Manguezal migrado:",
    "Active mangrove extent:": "Extensão atual de manguezal:",
    "Flooded mangrove:": "Manguezal inundado:",
    "Flooded natural vegetation:": "Vegetação natural inundada:",
    "Flooded anthropized / blocked:": "Área antropizada / bloqueada inundada:",
    "Gross annual gain:": "Ganho bruto anual:",
    "Gross annual loss:": "Perda bruta anual:",
    "Net annual change:": "Variação anual líquida:",
    "Elevation range:": "Intervalo de elevação:",
    "cells": "células",
    "CPU ": "CPU ",
    "RAM ": "RAM ",
    " (process ": " (processo ",
    " | Disk ": " | Disco ",
    " | Disco ": " | Disk ",
    " free": " livres",
    " livres": " free",
    " (processo ": " (process ",
    "Current state — {year}": "Estado atual — {year}",
    "Mangrove cells": "Células de manguezal",
    "Net annual gain": "Ganho anual líquido",
    "Net annual loss": "Perda anual líquida",
    "Calendar year": "Ano calendário",
    "Cells": "Células",
    "Net annual change (cells)": "Variação anual líquida (células)",
    "Load input rasters to begin": "Carregue os rasters de entrada para começar",
    "Run a simulation to build the trajectory": "Execute uma simulação para gerar a trajetória",
    "range: ": "intervalo: ",
    "Year {year}": "Ano {year}",
    "Cell state": "Estado da célula",
    "Elevation / relative surface": "Elevação / superfície relativa",
    "Raster columns": "Colunas do raster",
    "Raster rows": "Linhas do raster",
    "Relative elevation": "Elevação relativa",
    "Mangrove trajectory": "Trajetória do manguezal",
    "Net annual change": "Variação anual líquida",
    "Select a target CRS or enter an EPSG code.": "Selecione um SRC de destino ou digite um código EPSG.",
    "The study-area mask must share shape, CRS and transform with the land-cover raster.": "A máscara da área de estudo deve ter as mesmas dimensões, SRC e transformação do raster de cobertura da terra.",
    "Target resolution must be positive.": "A resolução de destino deve ser positiva.",
    "The target CRS produced an empty raster grid.": "O SRC de destino gerou uma grade raster vazia.",
    "The land-cover and elevation paths must be valid.": "Os caminhos dos rasters de cobertura da terra e elevação devem ser válidos.",
    "Final calendar year must be greater than initial year.": "O ano final deve ser posterior ao ano inicial.",
    "Migration maturation delay must be zero or greater.": "O atraso de maturação da migração deve ser zero ou maior.",
    "Block size must be positive.": "O tamanho do bloco deve ser maior que zero.",
}

_RUNTIME_PATTERNS = (
    (re.compile(r"^Trajectory covers (.+)–(.+); year (.+) is outside this range\.$"), re.compile(r"^A trajetória cobre (.+)–(.+); o ano (.+) está fora desse intervalo\.$"), "Trajectory covers {value}–{value2}; year {value3} is outside this range.", "A trajetória cobre {value}–{value2}; o ano {value3} está fora desse intervalo."),
    (re.compile(r"^Invalid year or sea_level_mm at CSV row (.+)\.$"), re.compile(r"^Ano ou sea_level_mm inválido na linha (.+) do CSV\.$"), "Invalid year or sea_level_mm at CSV row {value}.", "Ano ou sea_level_mm inválido na linha {value} do CSV."),
    (re.compile(r"^Cells processed: (.+)$"), re.compile(r"^Células processadas: (.+)$"), "Cells processed: {value}", "Células processadas: {value}"),
    (re.compile(r"^Speed: (.+)$"), re.compile(r"^Velocidade: (.+)$"), "Speed: {value}", "Velocidade: {value}"),
    (re.compile(r"^Loaded (.+) cells$"), re.compile(r"^Carregadas (.+) células$"), "Loaded {value} cells", "Carregadas {value} células"),
    (re.compile(r"^Found (.+) source classes in study area$"), re.compile(r"^Encontradas (.+) classes de origem na área de estudo$"), "Found {value} source classes in study area", "Encontradas {value} classes de origem na área de estudo"),
    (re.compile(r"^Found (.+) source classes in raster$"), re.compile(r"^Encontradas (.+) classes de origem no raster$"), "Found {value} source classes in raster", "Encontradas {value} classes de origem no raster"),
    (re.compile(r"^New project: (.+)$"), re.compile(r"^Novo projeto: (.+)$"), "New project: {value}", "Novo projeto: {value}"),
    (re.compile(r"^Project: (.+)$"), re.compile(r"^Projeto: (.+)$"), "Project: {value}", "Projeto: {value}"),
    (re.compile(r"^Finished — (.+)$"), re.compile(r"^Concluído — (.+)$"), "Finished — {value}", "Concluído — {value}"),
    (re.compile(r"^Year (.+)$"), re.compile(r"^Ano (.+)$"), "Year {value}", "Ano {value}"),
    (re.compile(r"^Four independent animations and figures saved  \|  (.+) annual frames$"), re.compile(r"^Quatro séries de figuras e animações salvas  \|  (.+) quadros anuais$"), "Four independent animations and figures saved  |  {value} annual frames", "Quatro séries de figuras e animações salvas  |  {value} quadros anuais"),
    (re.compile(r"^Initial state — (.+)$"), re.compile(r"^Estado inicial — (.+)$"), "Initial state — {value}", "Estado inicial — {value}"),
    (re.compile(r"^Current state — (.+)$"), re.compile(r"^Estado atual — (.+)$"), "Current state — {value}", "Estado atual — {value}"),
    (re.compile(r"^Select (.+)$"), re.compile(r"^Selecione (.+)$"), "Select {value}", "Selecione {value}"),
    (re.compile(r"^Unable to reproject the inputs: (.*)$"), re.compile(r"^Não foi possível reprojetar os dados: (.*)$"), "Unable to reproject the inputs: {value}", "Não foi possível reprojetar os dados: {value}"),
    (re.compile(r"^Unable to display annual figures: (.*)$"), re.compile(r"^Não foi possível exibir as figuras anuais: (.*)$"), "Unable to display annual figures: {value}", "Não foi possível exibir as figuras anuais: {value}"),
    (re.compile(r"^Unable to open (.+):$"), re.compile(r"^Não foi possível abrir (.+):$"), "Unable to open {value}:", "Não foi possível abrir {value}:"),
    (re.compile(r"^Band must be between (.+) and (.+)\.$"), re.compile(r"^A banda deve estar entre (.+) e (.+)\.$"), "Band must be between {value} and {value2}.", "A banda deve estar entre {value} e {value2}."),
    (re.compile(r"^Band (.+) is not available in (.+)\.$"), re.compile(r"^A banda (.+) não está disponível em (.+)\.$"), "Band {value} is not available in {value2}.", "A banda {value} não está disponível em {value2}."),
    (re.compile(r"^The (.+) raster has no CRS metadata: (.+)$"), re.compile(r"^O raster de (.+) não contém metadados de SRC: (.+)$"), "The {value} raster has no CRS metadata: {value2}", "O raster de {value} não contém metadados de SRC: {value2}"),
    (re.compile(r"^Expected CRS (.+) does not match input CRS (.+); reproject inputs before loading\.$"), re.compile(r"^O SRC esperado (.+) não corresponde ao SRC de entrada (.+); reprojete os dados antes de carregá-los\.$"), "Expected CRS {value} does not match input CRS {value2}; reproject inputs before loading.", "O SRC esperado {value} não corresponde ao SRC de entrada {value2}; reprojete os dados antes de carregá-los."),
    (re.compile(r"^The desktop utility '(.+)' is not installed\.$"), re.compile(r"^O utilitário '(.+)' não está instalado\.$"), "The desktop utility '{value}' is not installed.", "O utilitário '{value}' não está instalado."),
    (re.compile(r"^Simulation failed after (.+)\.$"), re.compile(r"^A simulação falhou após (.+)\.$"), "Simulation failed after {value}.", "A simulação falhou após {value}."),
)


def _config_file() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "BR-MANGUE Studio" / "settings.json"
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "brmangue-studio" / "settings.json"


def load_language() -> str:
    """Return the saved UI language, defaulting to English."""
    try:
        value = json.loads(_config_file().read_text(encoding="utf-8")).get("language")
    except (OSError, ValueError, AttributeError):
        value = None
    return value if value in CODE_TO_LANGUAGE else "en"


def save_language(code: str) -> None:
    """Persist the UI language without changing project or simulation files."""
    if code not in CODE_TO_LANGUAGE:
        return
    path = _config_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"language": code}, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        # An unwritable preferences folder should not prevent the application
        # from running; the language remains active for the current session.
        pass


def _normalize(text: str) -> str:
    """Convert known Portuguese UI strings back to their English source text."""
    reverse = {translated: original for original, translated in _PT_BR.items()}
    if text in reverse:
        return reverse[text]
    for portuguese, english in sorted(reverse.items(), key=lambda item: len(item[0]), reverse=True):
        if (english.endswith(":") or english.endswith(" ")) and text.startswith(portuguese):
            return english + text[len(portuguese):]
    if text.startswith("CPU "):
        text = text.replace(" | Disco ", " | Disk ").replace(" livres", " free").replace(" (processo ", " (process ")
    text = text.replace(" células (", " cells (")
    for english_pattern, portuguese_pattern, english_template, _portuguese_template in _RUNTIME_PATTERNS:
        match = portuguese_pattern.match(text)
        if match:
            values = {f"value{index + 1 if index else ''}": value for index, value in enumerate(match.groups())}
            try:
                return english_template.format(**values)
            except KeyError:
                return text
    return text


def translate(text: str, language: str = "en") -> str:
    """Translate a UI string while leaving unknown/data strings unchanged."""
    source = _normalize(text)
    if language == "pt-BR":
        return _PT_BR.get(source, source)
    return source


def translate_runtime(text: str, language: str = "en") -> str:
    """Translate status and monitor text, including values inserted at runtime."""
    source = "\n".join(_normalize(line) for line in text.split("\n"))
    if language != "pt-BR":
        return source
    output: list[str] = []
    for line in source.split("\n"):
        exact = _PT_BR.get(line)
        if exact is not None:
            output.append(exact)
            continue
        matched = False
        for english_pattern, _portuguese_pattern, _english_template, portuguese_template in _RUNTIME_PATTERNS:
            match = english_pattern.match(line)
            if match:
                values = {f"value{index + 1 if index else ''}": value for index, value in enumerate(match.groups())}
                if _english_template in ("Initial state — {value}", "Current state — {value}"):
                    values["value"] = translate(values["value"], language)
                output.append(portuguese_template.format(**values))
                matched = True
                break
        if matched:
            continue
        replaced = line
        prefix_entries = sorted(
            ((source, localized) for source, localized in _PT_BR.items() if source.endswith(":") or source.endswith(" ")),
            key=lambda item: len(item[0]),
            reverse=True,
        )
        for original, localized in prefix_entries:
            if original and replaced.startswith(original):
                replaced = localized + replaced[len(original):]
                break
        if replaced.startswith("CPU "):
            replaced = replaced.replace(" | Disk ", " | Disco ").replace(" free", " livres").replace(" (process ", " (processo ")
        replaced = replaced.replace(" cells (", " células (")
        if replaced.endswith(" cells"):
            replaced = replaced[:-6] + " células"
        output.append(replaced)
    return "\n".join(output)
