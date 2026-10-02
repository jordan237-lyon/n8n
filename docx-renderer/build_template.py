#!/usr/bin/env python3
"""Build the two-page DOCX template from the preserved original."""

from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs/templates/CV-template-original.docx"
TARGET = ROOT / "outputs/templates/CV-template.docx"


def paragraph_text(paragraph):
    return "".join(node.text or "" for node in paragraph.iter(W + "t"))


def replace_text(paragraph, replacement):
    texts = list(paragraph.iter(W + "t"))
    if not texts:
        raise RuntimeError(f"Paragraphe sans texte: {replacement}")
    texts[0].text = replacement
    texts[0].set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    for node in texts[1:]:
        node.text = ""


def replace_text_node(paragraph, original, replacement):
    matches = [node for node in paragraph.iter(W + "t") if node.text == original]
    if len(matches) != 1:
        raise RuntimeError(f"Texte introuvable ou ambigu: {original}")
    matches[0].text = replacement


with TemporaryDirectory(prefix="cv-template-") as temporary:
    temporary_path = Path(temporary)
    with ZipFile(SOURCE) as archive:
        archive.extractall(temporary_path)

    document_path = temporary_path / "word/document.xml"
    # Docxtemplater recognizes WordprocessingML tags by their original prefixes.
    # Preserve every namespace prefix instead of letting ElementTree emit ns0/ns1.
    for _, namespace in ET.iterparse(document_path, events=("start-ns",)):
        prefix, uri = namespace
        if prefix != "xml":
            ET.register_namespace(prefix, uri)
    tree = ET.parse(document_path)
    root = tree.getroot()
    parents = {child: parent for parent in root.iter() for child in parent}
    paragraphs = list(root.iter(W + "p"))

    # The imported source contains a full-page raster layer before the actual
    # document. It has no text but LibreOffice allocates a dedicated page for
    # it, so discard that conversion artifact.
    for paragraph in paragraphs:
        if not paragraph_text(paragraph).strip() and list(paragraph.iter(W + "drawing")):
            parents[paragraph].remove(paragraph)
    paragraphs = list(root.iter(W + "p"))

    # The source was saved as US Letter although the validated CV is A4. The
    # shorter page makes LibreOffice spill the same content onto extra pages.
    for page_size in root.iter(W + "pgSz"):
        page_size.set(W + "w", "11906")
        page_size.set(W + "h", "16838")
        page_size.set(W + "orient", "portrait")
    for page_margins in root.iter(W + "pgMar"):
        page_margins.set(W + "top", "360")
        page_margins.set(W + "right", "500")
        page_margins.set(W + "bottom", "360")
        page_margins.set(W + "left", "500")
        page_margins.set(W + "header", "0")
        page_margins.set(W + "footer", "0")
    for section in root.iter(W + "sectPr"):
        for footer_reference in list(section.findall(W + "footerReference")):
            section.remove(footer_reference)

    profile_prefix = "Data Engineer orienté delivery, intervenant"
    exp1_prefixes = [
        "Analyse de l’existant, recueil des besoins",
        "Conception de l’architecture cible",
        "Développement de pipelines ETL/ELT",
        "Mise en place de contrôles de qualité",
        "Structuration des données dans PostgreSQL",
        "Intégration de composants RAG",
    ]
    exp1_remove = [
        "Automatisation des déploiements",
        "Participation aux activités Build & Run",
        "Rédaction de la documentation technique",
    ]
    exp2_prefixes = [
        "Recueil des besoins opérationnels",
        "Conception d’un pipeline analytique",
        "Développement de traitements Python et SQL",
        "Modélisation relationnelle dans PostgreSQL",
        "Mise en place de règles de data quality",
        "Création de tableaux de bord Power BI",
    ]
    exp2_remove = [
        "Développement d’API de collecte",
        "Assistance à la recette",
    ]

    matches = {prefix: [] for prefix in [profile_prefix, *exp1_prefixes, *exp1_remove, *exp2_prefixes, *exp2_remove]}
    for paragraph in paragraphs:
        text = paragraph_text(paragraph).strip().lstrip("–—- ")
        for prefix in matches:
            if text.startswith(prefix):
                matches[prefix].append(paragraph)

    missing = [prefix for prefix, found in matches.items() if len(found) != 1]
    if missing:
        raise RuntimeError(f"Paragraphes introuvables ou ambigus: {missing}")

    experience_headers = {
        "Devoteam — CDD": "Devoteam",
        "Sept. 2024 – Déc. 2025": "Oct. 2023 – Sept. 2025",
        "Data Engineer — Projet IA & Transformation Digitale": "IA / Data Engineer — Projet IA & Transformation Digitale",
        "Green4All — Conception et industrialisation d’une plateforme Data & IA Green IT.": "Green4All — Outil de recommandation Green IT et Sustainability IT.",
        "LMT Group — Freelance": "LMT Group",
        "Oct. 2023 – Juil. 2024": "Sept. 2020 – Août 2023",
        "Data Engineer / Analytics Engineer": "Data Engineer / ML Engineer",
        "Plateforme analytique de supervision des incidents et d’aide à la décision pour un Call Center.": "Plateforme Data/ML de supervision et de prédiction des incidents d’un Call Center.",
    }
    for original, replacement in experience_headers.items():
        paragraph = next(
            paragraph
            for paragraph in paragraphs
            if original in paragraph_text(paragraph)
        )
        replace_text_node(paragraph, original, replacement)

    replace_text(matches[profile_prefix][0], "{{PROFIL}}")
    for index, prefix in enumerate(exp1_prefixes, 1):
        replace_text(matches[prefix][0], f"{{{{EXP1_POINT{index}}}}}")
    for index, prefix in enumerate(exp2_prefixes, 1):
        replace_text(matches[prefix][0], f"{{{{EXP2_POINT{index}}}}}")
    for prefix in [*exp1_remove, *exp2_remove]:
        paragraph = matches[prefix][0]
        parents[paragraph].remove(paragraph)

    exp1_result = next(
        paragraph
        for paragraph in root.iter(W + "p")
        if paragraph_text(paragraph).strip().startswith("Résultat : réduction d’environ 60 %")
    )
    parents[exp1_result].remove(exp1_result)

    # Keep both experiences in the same section. Leaving the original section
    # boundary here forces Word/LibreOffice to add blank space and expands the
    # generated CV beyond its required two pages.
    lmt_paragraph = next(
        paragraph
        for paragraph in root.iter(W + "p")
        if paragraph_text(paragraph).strip().startswith("LMT Group")
    )
    lmt_parent = parents[lmt_paragraph]
    lmt_position = list(lmt_parent).index(lmt_paragraph)
    section_boundary = list(lmt_parent)[lmt_position - 1]
    if section_boundary.tag == W + "p" and list(section_boundary.iter(W + "sectPr")):
        lmt_parent.remove(section_boundary)

    exp1_environment = next(
        paragraph for paragraph in root.iter(W + "p")
        if paragraph_text(paragraph).strip().startswith("Environnement : Python, SQL, Airflow")
    )
    exp2_environment = next(
        paragraph for paragraph in root.iter(W + "p")
        if "Environnement : Python, SQL, PostgreSQL" in paragraph_text(paragraph)
    )
    replace_text(exp1_environment, "Environnement : {{ENV1}}")
    replace_text(exp2_environment, "Environnement : {{ENV2}}")

    # Replace the complete skills block with one dynamic, compact paragraph.
    paragraphs = list(root.iter(W + "p"))
    skill_start = next(i for i, p in enumerate(paragraphs) if paragraph_text(p).strip().startswith("Data Engineering : ETL/ELT"))
    projects_heading = next(i for i, p in enumerate(paragraphs) if paragraph_text(p).strip() == "PROJETS DATA")
    replace_text(paragraphs[skill_start], "{{COMPETENCES}}")
    for paragraph in paragraphs[skill_start + 1 : projects_heading]:
        parent = parents.get(paragraph)
        if parent is not None and paragraph in list(parent):
            parent.remove(paragraph)

    tree.write(document_path, encoding="UTF-8", xml_declaration=True)

    styles_path = temporary_path / "word/styles.xml"
    styles_tree = ET.parse(styles_path)
    styles_root = styles_tree.getroot()
    for size_tag in (W + "sz", W + "szCs"):
        for font_size in styles_root.iter(size_tag):
            value = font_size.get(W + "val")
            if value and value.isdigit():
                font_size.set(W + "val", str(max(16, round(int(value) * 0.9))))
    styles_tree.write(styles_path, encoding="UTF-8", xml_declaration=True)

    with ZipFile(TARGET, "w", ZIP_DEFLATED) as output:
        for file_path in temporary_path.rglob("*"):
            if file_path.is_file():
                output.write(file_path, file_path.relative_to(temporary_path))

print(TARGET)
