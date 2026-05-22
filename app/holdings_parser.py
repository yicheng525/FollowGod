from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree


@dataclass(frozen=True)
class Holding:
    name_of_issuer: str
    title_of_class: str
    cusip: str
    value: int
    shares_or_principal: int
    share_type: str
    put_call: str | None


def parse_13f_information_table(xml_text: str) -> list[Holding]:
    root = ElementTree.fromstring(xml_text)
    holdings: list[Holding] = []
    for info_table in root.findall(".//{*}infoTable"):
        holding = Holding(
            name_of_issuer=_text(info_table, "nameOfIssuer"),
            title_of_class=_text(info_table, "titleOfClass"),
            cusip=_text(info_table, "cusip"),
            value=_int_text(info_table, "value"),
            shares_or_principal=_int_text(info_table, "sshPrnamt"),
            share_type=_text(info_table, "sshPrnamtType"),
            put_call=_text(info_table, "putCall") or None,
        )
        if holding.cusip:
            holdings.append(holding)
    return holdings


def _text(element: ElementTree.Element, tag: str) -> str:
    child = element.find(f".//{{*}}{tag}")
    if child is None or child.text is None:
        return ""
    return " ".join(child.text.split())


def _int_text(element: ElementTree.Element, tag: str) -> int:
    text = _text(element, tag)
    if not text:
        return 0
    return int(float(text.replace(",", "")))
