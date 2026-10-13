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
    "Project data": "Dados do projeto",
    "Class mapping": "Mapeamento de classes",
    "Simulation": "Simulação",
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
    "Choose how each numeric class from the categorical raster is interpreted. Excluded codes become NoData.": "Defina como cada classe numérica do raster será interpretada. Os códigos excluídos serão tratados como NoData.",
    "Inspect the land-cover raster to list its classes.": "Inspecione o raster de cobertura da terra para listar suas classes.",
    "Initial calendar year": "Ano inicial",
    "Final calendar year": "Ano final",
    "Tidal influence height (m)": "Altura de influência da maré (m)",
    "Sea-level rise (mm/year)": "Elevação do nível do mar (mm/ano)",
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
    "Rule module": "Módulo de regras",
    "Refresh source": "Atualizar código",
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
    "Cellular rules": "Regras celulares",
    "Raster input validation": "Validação dos rasters de entrada",
    "Raster runner": "Execução de rasters",
    "Source file not bundled: {filename}": "Arquivo de código não incluído: {filename}",
    "Unable to read {path}: {error}": "Não foi possível ler {path}: {error}",
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
