"""Yield direct Apple Health children while releasing processed XML nodes."""

from collections.abc import Iterator
from pathlib import Path
from xml.etree import ElementTree as ET


def export_elements(path: Path) -> Iterator[ET.Element]:
    with path.open("rb") as source:
        events = ET.iterparse(source, events=("start", "end"))
        root = None
        depth = 0
        for event, element in events:
            if event == "start":
                if root is None:
                    if element.tag != "HealthData":
                        raise ValueError("Expected an Apple Health HealthData document.")
                    root = element
                depth += 1
            else:
                depth -= 1
                if depth == 1:
                    yield element
                    root.remove(element)
