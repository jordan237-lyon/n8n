#!/usr/bin/env python3
"""Build a simple one-page DOCX template for cover letters."""

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs/templates/CV-template-original.docx"
TARGET = ROOT / "outputs/templates/LM-template.docx"


def paragraph(text, *, bold=False, size=None, align=None):
    p = ET.Element(W + "p")

    if align or bold or size:
        p_pr = ET.SubElement(p, W + "pPr")
        if align:
            jc = ET.SubElement(p_pr, W + "jc")
            jc.set(W + "val", align)

    run = ET.SubElement(p, W + "r")
    if bold or size:
        r_pr = ET.SubElement(run, W + "rPr")
        if bold:
            ET.SubElement(r_pr, W + "b")
        if size:
            sz = ET.SubElement(r_pr, W + "sz")
            sz.set(W + "val", str(size))
            sz_cs = ET.SubElement(r_pr, W + "szCs")
            sz_cs.set(W + "val", str(size))

    text_node = ET.SubElement(run, W + "t")
    text_node.text = text
    if text != text.strip():
        text_node.set(XML_SPACE, "preserve")

    return p


with TemporaryDirectory(prefix="lm-template-") as temporary:
    temporary_path = Path(temporary)

    with ZipFile(SOURCE) as archive:
        archive.extractall(temporary_path)

    document_path = temporary_path / "word/document.xml"
    for _, namespace in ET.iterparse(document_path, events=("start-ns",)):
        prefix, uri = namespace
        if prefix != "xml":
            ET.register_namespace(prefix, uri)

    tree = ET.parse(document_path)
    root = tree.getroot()
    body = root.find(W + "body")

    if body is None:
        raise RuntimeError("Le document source ne contient pas de corps.")

    sect_pr = body.find(W + "sectPr")
    new_body = ET.Element(W + "body")
    new_body.append(paragraph("Lettre de motivation", bold=True, size=32, align="center"))
    new_body.append(paragraph("{{cover_letter}}"))

    if sect_pr is not None:
        new_body.append(deepcopy(sect_pr))

    root.remove(body)
    root.append(new_body)

    tree.write(document_path, encoding="UTF-8", xml_declaration=True)

    with ZipFile(TARGET, "w", ZIP_DEFLATED) as output:
        for file_path in temporary_path.rglob("*"):
            if file_path.is_file():
                output.write(file_path, file_path.relative_to(temporary_path))

print(TARGET)
