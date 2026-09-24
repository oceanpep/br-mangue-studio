"""Build the illustrated Portuguese BR-MANGUE Studio user manual."""

from __future__ import annotations

from pathlib import Path
import os

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    Flowable,
)


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "tmp" / "pdfs" / "brmangue_manual_assets"
OUT = ROOT / "output" / "pdf" / "Manual_Usuario_BR_MANGUE_Studio_1.0.0.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)

W, H = A4
DARK = colors.HexColor("#073f32")
GREEN = colors.HexColor("#0b6249")
GREEN_LIGHT = colors.HexColor("#e4f0e8")
TERRA = colors.HexColor("#b24325")
MUSTARD = colors.HexColor("#d4942f")
BLUE = colors.HexColor("#146f86")
INK = colors.HexColor("#17334a")
MUTED = colors.HexColor("#5e7480")
PALE = colors.HexColor("#f5f8f5")
LINE = colors.HexColor("#d8e4df")
WHITE = colors.white

FONT = r"C:\Windows\Fonts\segoeui.ttf"
FONT_BOLD = r"C:\Windows\Fonts\segoeuib.ttf"
FONT_ITALIC = r"C:\Windows\Fonts\segoeuii.ttf"
if all(Path(p).exists() for p in (FONT, FONT_BOLD, FONT_ITALIC)):
    pdfmetrics.registerFont(TTFont("SegoeUI", FONT))
    pdfmetrics.registerFont(TTFont("SegoeUI-Bold", FONT_BOLD))
    pdfmetrics.registerFont(TTFont("SegoeUI-Italic", FONT_ITALIC))
    BASE_FONT, BOLD_FONT, ITALIC_FONT = "SegoeUI", "SegoeUI-Bold", "SegoeUI-Italic"
else:
    BASE_FONT, BOLD_FONT, ITALIC_FONT = "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"


class PillHeading(Flowable):
    def __init__(self, title: str, color=TERRA, width=165 * mm, height=14 * mm):
        super().__init__()
        self.title = title
        self.color = color
        self.width = width
        self.height = height

    def wrap(self, availWidth, availHeight):
        self.width = min(self.width, availWidth)
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.setFillColor(self.color)
        c.roundRect(0, 0, self.width, self.height, self.height / 2, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont(BOLD_FONT, 19 if self.width > 430 else 16)
        c.drawString(12 * mm, 4.2 * mm, self.title)


def p(text: str, style):
    return Paragraph(text, style)


def image(path: Path, max_width=170 * mm, max_height=100 * mm, h_align="CENTER"):
    if not path.exists():
        return p(f"<i>Imagem não encontrada: {path.name}</i>", styles["Caption"])
    with PILImage.open(path) as im:
        iw, ih = im.size
    scale = min(max_width / iw, max_height / ih)
    obj = Image(str(path), width=iw * scale, height=ih * scale)
    obj.hAlign = h_align
    return obj


def caption(text: str):
    return p(text, styles["Caption"])


def info_box(title: str, text: str, color=GREEN_LIGHT):
    data = [[p(f"<b>{title}</b><br/>{text}", styles["Box"])] ]
    table = Table(data, colWidths=[170 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("BOX", (0, 0), (-1, -1), .7, GREEN),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    return table


def two_col(left, right, widths=(82 * mm, 82 * mm)):
    table = Table([[left, right]], colWidths=list(widths), hAlign="CENTER")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="BodyBR", fontName=BASE_FONT, fontSize=10.5, leading=15.2, textColor=INK, spaceAfter=7, alignment=TA_LEFT))
styles.add(ParagraphStyle(name="BodySmall", parent=styles["BodyBR"], fontSize=9.2, leading=13, textColor=MUTED))
styles.add(ParagraphStyle(name="Caption", fontName=BASE_FONT, fontSize=8.1, leading=10.5, textColor=MUTED, alignment=TA_CENTER, spaceBefore=4, spaceAfter=8))
styles.add(ParagraphStyle(name="Box", fontName=BASE_FONT, fontSize=9.2, leading=13, textColor=INK))
styles.add(ParagraphStyle(name="CoverTitle", fontName=BOLD_FONT, fontSize=27, leading=31, textColor=WHITE, alignment=TA_CENTER, spaceAfter=7))
styles.add(ParagraphStyle(name="CoverSub", fontName=BASE_FONT, fontSize=17, leading=22, textColor=WHITE, alignment=TA_CENTER))
styles.add(ParagraphStyle(name="CoverMeta", fontName=BASE_FONT, fontSize=10.5, leading=15, textColor=colors.HexColor("#d9eee4"), alignment=TA_CENTER))
styles.add(ParagraphStyle(name="TOC", fontName=BASE_FONT, fontSize=11, leading=17, textColor=INK, leftIndent=8, bulletIndent=0))
styles.add(ParagraphStyle(name="SmallWhite", fontName=BASE_FONT, fontSize=9.5, leading=13, textColor=WHITE, alignment=TA_CENTER))
styles.add(ParagraphStyle(name="TableHead", fontName=BOLD_FONT, fontSize=8.6, leading=11, textColor=WHITE))
styles.add(ParagraphStyle(name="TableBody", fontName=BASE_FONT, fontSize=8.4, leading=11, textColor=INK))


def cover_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(DARK)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#0b5b43"))
    path = canvas.beginPath()
    path.moveTo(-20, H * .78)
    path.curveTo(W * .25, H * .92, W * .58, H * .69, W + 20, H * .82)
    path.lineTo(W + 20, H * .68)
    path.curveTo(W * .58, H * .55, W * .25, H * .82, -20, H * .64)
    path.close()
    canvas.drawPath(path, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#0d503c"))
    path = canvas.beginPath()
    path.moveTo(-20, H * .25)
    path.curveTo(W * .25, H * .37, W * .62, H * .13, W + 20, H * .28)
    path.lineTo(W + 20, H * .10)
    path.curveTo(W * .61, H * .02, W * .25, H * .24, -20, H * .09)
    path.close()
    canvas.drawPath(path, fill=1, stroke=0)
    canvas.setFillColor(TERRA)
    canvas.rect(0, 0, W, 22, fill=1, stroke=0)
    canvas.restoreState()


def later_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(PALE)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)
    canvas.setFillColor(TERRA)
    canvas.rect(0, H - 25, W, 25, fill=1, stroke=0)
    canvas.setFillColor(DARK)
    canvas.roundRect(18 * mm, H - 22, 46 * mm, 17, 8, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont(BOLD_FONT, 8.5)
    canvas.drawString(22 * mm, H - 16.5, "BR-MANGUE Studio")
    # A very light cellular grid gives the pages a subtle model reference
    # without competing with screenshots, tables, and explanatory text.
    canvas.setStrokeColor(colors.HexColor("#e5eee9"))
    canvas.setLineWidth(0.25)
    for x in range(0, int(W), 18):
        canvas.line(x, 25, x, H - 25)
    for y in range(35, int(H - 25), 18):
        canvas.line(0, y, W, y)
    canvas.setFillColor(TERRA)
    path = canvas.beginPath()
    path.moveTo(0, 0)
    path.curveTo(W * .32, 15, W * .54, -4, W * .78, 10)
    path.curveTo(W * .88, 16, W * .94, 8, W, 13)
    path.lineTo(W, 0)
    path.close()
    canvas.drawPath(path, fill=1, stroke=0)
    canvas.setFillColor(MUTED)
    canvas.setFont(BASE_FONT, 8)
    canvas.drawString(18 * mm, 8, "Manual do usuário · Versão 1.0.0")
    canvas.setFillColor(WHITE)
    canvas.setFont(BOLD_FONT, 10)
    canvas.drawRightString(W - 18 * mm, 8, str(doc.page))
    canvas.restoreState()


def build_story():
    story = []
    # Cover
    story += [Spacer(1, 25 * mm), p("BR-MANGUE Studio", styles["CoverTitle"]), p("Manual do usuário", styles["CoverSub"]), Spacer(1, 8 * mm)]
    logo = ASSETS / "logo_cropped.png"
    if logo.exists():
        story.append(image(logo, max_width=145 * mm, max_height=52 * mm))
    story += [Spacer(1, 10 * mm), p("Uma ferramenta para explorar mudanças nos manguezais em diferentes cenários de elevação do nível do mar.", styles["CoverSub"]), Spacer(1, 10 * mm), p("Versão 1.0.0 · Windows 10/11 · 64 bits", styles["CoverMeta"]), p("Universidade Federal do Maranhão · GEOTAM", styles["CoverMeta"]), Spacer(1, 20 * mm), p("Um guia visual para preparar dados, executar cenários e interpretar resultados.", styles["CoverMeta"]), PageBreak()]

    # Presentation
    story += [PillHeading("Apresentação"), Spacer(1, 5 * mm)]
    story += [p("O BR-MANGUE Studio é um programa para explorar como os manguezais podem mudar quando o nível do mar sobe. Para fazer isso, ele divide a área de estudo em pequenos quadrados, chamados de células.", styles["BodyBR"]), p("Em cada célula, o programa observa a altura do terreno, o tipo de cobertura da terra e as células vizinhas. Depois aplica as mesmas regras ano a ano e registra o que aconteceu: a célula pode continuar como está, ser inundada ou receber mangue que avançou de uma área próxima.", styles["BodyBR"]), p("Esse modo de trabalhar é chamado de autômato celular. O nome parece técnico, mas a ideia é simples: muitas mudanças locais, reunidas, formam o mapa da paisagem. Este manual explica cada etapa com linguagem direta, desde a escolha dos arquivos até a leitura dos mapas, gráficos e tabelas.", styles["BodyBR"]), info_box("Como interpretar o resultado", "O Studio produz cenários, não uma previsão garantida. O resultado mostra o que as regras indicam para os dados e parâmetros escolhidos. Por isso, ele deve ser comparado com observações, literatura e avaliação de especialistas antes de ser usado em uma conclusão científica."), Spacer(1, 5 * mm), p("O BR-MANGUE começou a ser desenvolvido entre 2010 e 2014 em Lua com TerraME pelo Dr. Denilson da Silva Bezerra. O Studio leva essa proposta para um programa Windows com mapas, gráficos e tabelas, permitindo executar um cenário sem precisar programar.", styles["BodyBR"]), PageBreak()]

    # Contents and quick start
    story += [PillHeading("Como usar este manual", color=GREEN), Spacer(1, 5 * mm)]
    toc = [
        ("01", "O modelo em linguagem simples", "autômato celular, célula, vizinhança e regras"),
        ("02", "Prepare os dados", "GeoTIFF, DEM/MDT, NoData, máscara e CRS"),
        ("03", "Conheça a interface", "projeto, mapeamento, simulação e monitor"),
        ("04", "Configure um cenário", "anos, maré, nível do mar, blocos e motores"),
        ("05", "Execute e acompanhe", "validação, atualização anual e tempo de execução"),
        ("06", "Leia os resultados", "mapas, trajetórias, mudanças, transições e GIF"),
        ("07", "Exemplo real", "recorte da Ilha do Maranhão, 3.600 células e 50 passos"),
        ("08", "Problemas frequentes", "mensagens de erro e como corrigir"),
    ]
    data = [[p("<b>Seção</b>", styles["TableHead"]), p("<b>Conteúdo</b>", styles["TableHead"]), p("<b>Você vai aprender</b>", styles["TableHead"])] ]
    data += [[p(a, styles["TableBody"]), p(f"<b>{b}</b>", styles["TableBody"]), p(c, styles["TableBody"])] for a, b, c in toc]
    table = Table(data, colWidths=[20 * mm, 57 * mm, 93 * mm], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), DARK), ("GRID", (0, 0), (-1, -1), .35, LINE), ("BACKGROUND", (0, 1), (-1, -1), WHITE), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, colors.HexColor("#eff6f1")]), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story += [table, Spacer(1, 7 * mm), info_box("Fluxo resumido", "1. Prepare rasters alinhados → 2. Inspecione e mapeie classes → 3. Defina o cenário → 4. Valide e execute → 5. Interprete mapas, gráficos e tabelas.", color=colors.HexColor("#e7f1f7")), PageBreak()]

    # Chapter 1
    story += [PillHeading("01 · O modelo em linguagem simples"), Spacer(1, 4 * mm), p("Imagine um mapa dividido em pequenos quadrados. Cada quadrado é uma célula. Em vez de calcular a paisagem como uma fotografia única, o BR-MANGUE acompanha a mudança célula por célula e ano por ano.", styles["BodyBR"]), p("O estado da célula é a classe que ela representa: mangue, vegetação natural, água ou área antropizada/bloqueada. A elevação vem do DEM/MDT. A regra observa também as células vizinhas, porque a água e a possibilidade de migração dependem da posição e da continuidade espacial.", styles["BodyBR"]), image(ASSETS / "moore_neighborhood.png", max_width=155 * mm, max_height=82 * mm), caption("Figura 1. Vizinhança de Moore: a célula central pode consultar até oito vizinhas."), two_col([p("<b>O que entra</b>", styles["BodyBR"]), p("Uso e cobertura da terra, elevação, CRS, anos e parâmetros costeiros.", styles["BodySmall"])], [p("<b>O que sai</b>", styles["BodyBR"]), p("Estado anual de cada célula, mapas, trajetórias, mudanças, tabelas e animações.", styles["BodySmall"])]), PageBreak()]

    # Chapter 2 data
    story += [PillHeading("02 · Prepare os dados", color=GREEN), Spacer(1, 4 * mm), p("O programa trabalha com rasters GeoTIFF. O arquivo de uso e cobertura é categórico: cada pixel guarda um código inteiro de classe. O arquivo de elevação é numérico: cada pixel guarda a altura do terreno.", styles["BodyBR"])]
    data = [[p("Arquivo", styles["TableHead"]), p("Função", styles["TableHead"]), p("Requisito", styles["TableHead"])], [p("Uso/cobertura", styles["TableBody"]), p("Estado inicial da célula", styles["TableBody"]), p("Códigos inteiros, sem NaN; mesma grade do DEM", styles["TableBody"])], [p("DEM/MDT", styles["TableBody"]), p("Elevação relativa do terreno", styles["TableBody"]), p("Valores numéricos, mesma extensão, resolução e CRS", styles["TableBody"])], [p("Máscara de estudo", styles["TableBody"]), p("Limita o domínio", styles["TableBody"]), p("Opcional; pixels válidos diferentes de zero", styles["TableBody"])], [p("Aptidão de mangue", styles["TableBody"]), p("Apoia migração e regras de solo", styles["TableBody"]), p("Opcional; pode ser desativado com fallback", styles["TableBody"])]]
    t = Table(data, colWidths=[38 * mm, 57 * mm, 75 * mm], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), DARK), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, colors.HexColor("#eff6f1")]), ("GRID", (0, 0), (-1, -1), .35, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story += [t, Spacer(1, 5 * mm), info_box("Regra de alinhamento", "Os rasters precisam ter o mesmo número de linhas e colunas, a mesma resolução, a mesma extensão e o mesmo sistema de referência. Se algo estiver diferente, reprojete e alinhe antes de executar."), Spacer(1, 4 * mm), image(ASSETS / "ui_current_project_visualization.png", max_width=172 * mm, max_height=83 * mm), caption("Figura 2. Versão atual: dados do projeto, legenda dos estados e quatro painéis independentes de visualização."), PageBreak()]

    # CRS / class mapping
    story += [PillHeading("03 · CRS, classes e mapeamento"), Spacer(1, 4 * mm), p("Na seção Coordinate reference, o Studio informa o CRS detectado e permite indicar um CRS esperado. Para gerar cópias reprojetadas, pesquise pelo nome ou EPSG no campo de destino; a versão atual traz 10857 — Albers Brasil (SIRGAS 2000) como opção padrão. Informe a resolução desejada quando necessário. O programa cria cópias alinhadas na pasta preparada; os arquivos originais permanecem intactos.", styles["BodyBR"]), two_col(image(ASSETS / "ui_current_crs.png", max_width=72 * mm, max_height=76 * mm), [p("<b>Como conferir</b>", styles["BodyBR"]), p("1. Verifique o CRS detectado.<br/>2. Pesquise o datum ou EPSG de destino.<br/>3. Confirme unidade e resolução.<br/>4. Reprojete e valide novamente antes de mapear as classes.", styles["BodySmall"])]), caption("Figura 3. Tela atual de referência espacial, busca de CRS e reprojeção."), PageBreak()]

    story += [PillHeading("04 · Mapeie as classes", color=GREEN), Spacer(1, 4 * mm), p("Clique em Inspect land-cover classes para listar os códigos presentes no raster. Em seguida, atribua a cada código um papel do modelo. A escolha precisa representar o significado da classe no seu estudo, não apenas o número do código.", styles["BodyBR"]), image(ASSETS / "ui_current_class_mapping.png", max_width=90 * mm, max_height=90 * mm), caption("Figura 4. Tela atual de mapeamento dos códigos de origem para os papéis do modelo."), info_box("Água e solo descoberto", "Água deve ser mapeada como Water. Solo descoberto, praia ou área sem vegetação só deve ser colocado em Natural vegetation quando a regra de migração do seu cenário realmente permitir essa ocupação; caso contrário, use Anthropized / blocked para impedir a conversão."), p("Os papéis principais são: Mangrove; Natural vegetation; Water; Anthropized / blocked. Durante a simulação, o motor registra também Migrated mangrove e Flooded mangrove. Classes excluídas são tratadas como NoData e não participam da vizinhança.", styles["BodyBR"]), PageBreak()]

    # Simulation parameters
    story += [PillHeading("05 · Configure o cenário"), Spacer(1, 4 * mm), image(ASSETS / "ui_current_simulation.png", max_width=125 * mm, max_height=76 * mm), caption("Figura 5. Aba Simulation na versão atual, com os parâmetros do cenário e as opções de migração."), p("<b>Initial calendar year / Final calendar year.</b> O raster de entrada representa o estado inicial. O motor executa uma transição por passo; 2025 a 2075 com 50 passos gera estados anuais de 2026 a 2075 e mantém 2025 como estado inicial.", styles["BodyBR"]), p("<b>Tidal influence height (m).</b> Altura de influência usada pelas regras de migração. <b>Sea-level rise (mm/year).</b> É informado em milímetros por ano: 0.5 significa meio milímetro por ano; 13 significa 13 mm por ano. <b>Constant surface accretion.</b> Opcional, também em mm por passo.", styles["BodyBR"]), p("<b>Block size (cells).</b> É quantidade de células por bloco, não tamanho do pixel. Se a resolução do raster é 30 m, uma célula representa 30 m; um bloco de 10.000 contém 10.000 células. <b>Processing engine.</b> Continuous mantém a grade na RAM; blocks usa estado persistente em disco para domínios maiores.", styles["BodyBR"]), PageBreak()]

    # Engines and execution
    story += [PillHeading("06 · Execute e acompanhe", color=GREEN), Spacer(1, 4 * mm), p("Antes de executar, clique em Validate and load inputs. O programa verifica alinhamento, NoData, tipos de dados, CRS, códigos e número de células. Corrija os avisos antes de iniciar uma simulação longa.", styles["BodyBR"]), two_col([p("<b>Continuous</b>", styles["BodyBR"]), p("Mais rápido quando a grade cabe com folga na memória. Os arrays de estado são reutilizados a cada passo; aumentar o número de anos aumenta o tempo, mas não multiplica a RAM pelo número de passos.", styles["BodySmall"])], [p("<b>Blocks</b>", styles["BodyBR"]), p("Indicado para áreas muito grandes. O estado é particionado e persistido; o custo de leitura e escrita pode deixar o processamento mais lento, mas permite trabalhar com domínios que não cabem com segurança na RAM.", styles["BodySmall"])]), Spacer(1, 5 * mm), info_box("Durante a execução", "O Live run monitor mostra mensagens, o andamento anual, uso de memória e tempo. O mapa é atualizado a cada ano processado; a geração de figuras e GIF ocorre depois da simulação."), image(ASSETS / "ui_current_animation.png", max_width=170 * mm, max_height=100 * mm), caption("Figura 6. Aba Animation atual, com quatro painéis independentes e controles para percorrer os anos."), PageBreak()]

    # Outputs
    story += [PillHeading("07 · Resultados e arquivos"), Spacer(1, 4 * mm), p("Cada execução é salva em uma pasta própria. Os nomes tornam possível rastrear o que aconteceu sem depender apenas da imagem na tela.", styles["BodyBR"])]
    data = [[p("Arquivo/pasta", styles["TableHead"]), p("O que contém", styles["TableHead"])], [p("metadata.json", styles["TableBody"]), p("Parâmetros, engine, número de células, tempo, pico de RAM, I/O e informações do sistema.", styles["TableBody"])], [p("trajectory.csv", styles["TableBody"]), p("Uma linha por ano: classes, extensão ativa de mangue, ganhos brutos, perdas brutas, saldo anual, tempo por passo e células por segundo.", styles["TableBody"])], [p("states/usos_YYYY.tif", styles["TableBody"]), p("Raster de estado anual, com 0 fora do domínio válido.", styles["TableBody"])], [p("figures/", styles["TableBody"]), p("Mapas, trajetória, mudança anual e elevação em arquivos separados.", styles["TableBody"])], [p("animations/state.gif", styles["TableBody"]), p("Animação dos mapas anuais do estado celular.", styles["TableBody"])], [p("resource_samples.csv", styles["TableBody"]), p("Amostras de RAM, CPU e disco quando o monitoramento está disponível.", styles["TableBody"])]]
    t = Table(data, colWidths=[49 * mm, 121 * mm], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), DARK), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, colors.HexColor("#eff6f1")]), ("GRID", (0, 0), (-1, -1), .35, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story += [t, Spacer(1, 6 * mm), image(ASSETS / "ui_net_change.png", max_width=68 * mm, max_height=70 * mm), caption("Figura 7. Gráfico de mudança líquida por classe: perdas à esquerda de zero e ganhos à direita."), PageBreak()]

    # Real example maps and gif
    story += [PillHeading("08 · Exemplo real: Ilha do Maranhão", color=GREEN), Spacer(1, 4 * mm), p("Para mostrar o funcionamento de perto, foi executada uma simulação real usando um recorte de 60 × 60 células da Ilha do Maranhão. O uso e cobertura e o ANADEM foram recortados juntos, ambos com resolução de 30 m. A execução usou 3.600 células e 50 passos anuais, de 2025 a 2075.", styles["BodyBR"]), image(ASSETS / "real_initial_final_maps.png", max_width=172 * mm, max_height=91 * mm), caption("Figura 8. Estado inicial e estado final do recorte real. As cores representam estados do modelo, não uma classificação nova do território."), p("A primeira imagem mantém áreas de mangue e água em suas posições iniciais. Ao longo dos passos, as regras convertem parte do mangue em Flooded mangrove e registram células adjacentes como Migrated mangrove. O padrão depende diretamente da elevação, das classes vizinhas, da maré configurada e da taxa de elevação do nível do mar.", styles["BodyBR"]), PageBreak()]

    # Charts interpretation
    story += [PillHeading("09 · Interprete os gráficos"), Spacer(1, 4 * mm), image(ASSETS / "real_trajectory.png", max_width=172 * mm, max_height=78 * mm), caption("Figura 9. Trajetória real do recorte de 3.600 células."), p("No exemplo, a linha verde representa as células que ainda estão no estado Mangrove. A linha vermelha cresce à medida que células de mangue passam para Flooded mangrove. A linha roxa mostra Migrated mangrove. A leitura correta é comparativa: observe o ano, o parâmetro usado e o estado que a célula recebeu; não interprete a curva como uma previsão universal para toda a ilha.", styles["BodyBR"]), image(ASSETS / "real_annual_change.png", max_width=172 * mm, max_height=70 * mm), caption("Figura 10. Saldo anual da extensão ativa de mangue: Mangrove + Migrated mangrove. Barras verdes indicam aumento líquido; barras vermelhas indicam perda líquida."), p("O arquivo trajectory.csv também preserva annual_gain e annual_loss como ganhos e perdas brutos célula a célula. O gráfico usa annual_net_change = annual_gain − annual_loss, evitando contar como perda uma célula que apenas mudou de Mangrove para Migrated mangrove.", styles["BodyBR"]), p("O Studio calcula também a área: um pixel de 30 m × 30 m equivale a 0,0009 km². As colunas terminadas em _km2 mostram a mesma trajetória e o mesmo saldo em área; isso exige um CRS projetado em unidades métricas.", styles["BodyBR"]), PageBreak()]

    # Result explanation and visualization
    story += [PillHeading("10 · Leia o mapa e a animação", color=GREEN), Spacer(1, 4 * mm), p("O mapa de estado é categórico: cada cor representa um estado. O verde escuro é Mangrove; verde claro é Natural vegetation; azul é Water; laranja é Anthropized / blocked; roxo é Migrated mangrove; vermelho é Flooded mangrove. As cores não representam altitude nem intensidade.", styles["BodyBR"]), two_col(image(ASSETS / "real_gif_first_frame.png", max_width=77 * mm, max_height=75 * mm), image(ASSETS / "real_gif_last_frame.png", max_width=77 * mm, max_height=75 * mm)), caption("Figura 11. Primeiro e último quadro do GIF real gerado pelo Studio para o recorte da Ilha do Maranhão."), image(ASSETS / "real_dem_cutout.png", max_width=150 * mm, max_height=76 * mm), caption("Figura 12. O ANADEM fornece a superfície usada nas regras de transição."), info_box("Como evitar uma leitura errada", "Uma mudança de cor pode ser inundação, migração ou outra transição prevista. Sempre consulte trajectory.csv e transition_by_land_cover_code.csv para saber de qual classe a célula veio e para qual estado foi."), PageBreak()]

    # Interface screenshots
    story += [PillHeading("11 · Guia rápido das telas"), Spacer(1, 4 * mm), image(ASSETS / "ui_current_project_visualization.png", max_width=172 * mm, max_height=80 * mm), caption("Figura 13. Tela atual de projeto e visualização, com quatro quadros independentes."), p("Na aba Project data você escolhe os rasters e confere o sistema de coordenadas. A aba Visualization mostra o estado inicial, o relevo relativo, a trajetória e a mudança anual. Results organiza os arquivos produzidos; Animation permite percorrer os anos.", styles["BodyBR"]), image(ASSETS / "ui_current_simulation.png", max_width=94 * mm, max_height=72 * mm), caption("Figura 14. Tela atual de Simulation e opções do cenário."), PageBreak()]

    # Troubleshooting
    story += [PillHeading("12 · Problemas frequentes", color=GREEN), Spacer(1, 4 * mm)]
    problems = [
        ("cannot convert float NaN to integer", "O raster categórico contém NaN ou valores inválidos. Exporte novamente a classe como inteiro, defina NoData e remova pixels inválidos antes do mapeamento."),
        ("Rasters com dimensões ou CRS diferentes", "Use a seção de reprojeção para criar cópias alinhadas. Não altere os originais; confira resolução, extensão, linhas, colunas e CRS após o processo."),
        ("O mapa não muda ou a migração é pequena", "Verifique se há mangue, vegetação/solo elegível, elevação abaixo da zona de influência e, se não houver raster de aptidão, marque Allow migration without suitability layer."),
        ("O programa fica lento ou parece travar", "Aguarde a etapa de processamento e consulte o Live run monitor. Para uma grade que cabe com folga na RAM, Continuous costuma ser mais rápido; para áreas muito grandes, use Blocks e reduza exportações anuais se necessário."),
        ("A legenda ou um painel aparece cortado", "Redimensione o painel arrastando os divisores, use a aba de visualização individual e abra os arquivos separados na pasta figures/ para leitura em tela cheia."),
    ]
    data = [[p("Mensagem/situação", styles["TableHead"]), p("O que fazer", styles["TableHead"])] ]
    data += [[p(f"<b>{a}</b>", styles["TableBody"]), p(b, styles["TableBody"])] for a, b in problems]
    t = Table(data, colWidths=[63 * mm, 107 * mm], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), DARK), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, colors.HexColor("#eff6f1")]), ("GRID", (0, 0), (-1, -1), .35, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story += [t, PageBreak()]

    # Checklist and references
    story += [PillHeading("13 · Checklist de uma execução confiável"), Spacer(1, 4 * mm)]
    checklist = ["Os rasters têm a mesma extensão, resolução, dimensões e CRS.", "O raster categórico não contém NaN e seus códigos foram inspecionados.", "Água, mangue, vegetação e áreas bloqueadas foram mapeados conscientemente.", "Os anos, a taxa de elevação do nível do mar e a altura de influência foram registrados.", "O motor e o tamanho de bloco foram escolhidos de acordo com a RAM disponível.", "A execução terminou sem erro e o metadata.json foi salvo.", "trajectory.csv, mapas anuais e figuras foram revisados antes da interpretação.", "O resultado foi comparado com dados observados, literatura ou um cenário de referência quando possível."]
    for item in checklist:
        story.append(p(f"☐ {item}", styles["BodyBR"]))
    story += [Spacer(1, 5 * mm), info_box("Reprodutibilidade", "Guarde os rasters de entrada, o mapeamento de classes, os parâmetros, a versão do Studio e a pasta completa de resultados. Assim, outra pessoa consegue repetir o cenário e verificar as diferenças."), Spacer(1, 8 * mm), PillHeading("Referências e materiais", color=GREEN), Spacer(1, 4 * mm), p("Bezerra, D. S. et al. (2014). Artigo de referência do modelo BR-MANGUE e da aplicação na Ilha do Maranhão.", styles["BodyBR"]), p("BR-MANGUE Studio. Manual do usuário, versão 1.0.0. Universidade Federal do Maranhão / GEOTAM.", styles["BodyBR"]), p("Os exemplos numéricos e figuras deste manual foram gerados a partir dos resultados armazenados na pasta de execução do recorte real da Ilha do Maranhão. Eles servem para demonstrar o fluxo do software e não constituem uma previsão publicada para a área.", styles["BodyBR"]), Spacer(1, 12 * mm), p("Fim do manual · BR-MANGUE Studio", styles["BodySmall"])]
    return story


def main():
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm, topMargin=31 * mm, bottomMargin=20 * mm, title="Manual do usuário BR-MANGUE Studio", author="BR-MANGUE Studio")
    doc.build(build_story(), onFirstPage=cover_page, onLaterPages=later_page)
    print(OUT)


if __name__ == "__main__":
    main()
