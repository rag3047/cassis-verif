from lxml import etree as ET
from lxml.etree import _Element as Element, _ElementTree as ElementTree

def inject_css_links(html: str, css_links: list[str]) -> str:
    tree: ElementTree = ET.HTML(html)
    head: Element = tree.find('head')

    if head is None:
        raise ValueError('No head tag found in the HTML')

    for link in css_links:
        head.append(ET.Element('link', attrib={'rel': 'stylesheet', 'href': link, 'type': 'text/css'}))

    return ET.tostring(tree, pretty_print=True, method='html', encoding="utf-8")