#!/usr/bin/env python3
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup
import re

ROOT = Path(__file__).resolve().parents[1]
HTML_GLOB = "**/*.html"

HEAD_OPEN_RE = re.compile(r"<head(\s[^>]*)?>", re.IGNORECASE)
HAS_DOCTYPE_RE = re.compile(r"<!DOCTYPE\s+html", re.IGNORECASE)
HAS_META_CHARSET_RE = re.compile(r"<meta[^>]+charset=", re.IGNORECASE)
HAS_HTTP_EQUIV_CT_RE = re.compile(r"<meta[^>]+http-equiv=\"?content-type\"?", re.IGNORECASE)
HAS_VIEWPORT_RE = re.compile(r"<meta[^>]+name=\"?viewport\"?", re.IGNORECASE)
HTML_OPEN_RE = re.compile(r"<html(\s[^>]*)?>", re.IGNORECASE)
HAS_LANG_RE = re.compile(r"<html[^>]*\blang=", re.IGNORECASE)

FONT_AWESOME_MISSING_LANG = {
    "sites/all/themes/open_framework/packages/font-awesome-3.2.1/font/fontawesome-webfontd41d.html",
    "sites/all/themes/open_framework/packages/font-awesome-3.2.1/font/fontawesome-webfontf77b-2.html",
    "sites/all/themes/open_framework/packages/font-awesome-3.2.1/font/fontawesome-webfontf77b-3.html",
    "sites/all/themes/open_framework/packages/font-awesome-3.2.1/font/fontawesome-webfontf77b.html",
}


def ensure_doctype(text: str) -> str:
    if HAS_DOCTYPE_RE.search(text):
        return text
    return "<!DOCTYPE html>\n" + text


def insert_after_head_open(text: str, snippet: str) -> str:
    m = HEAD_OPEN_RE.search(text)
    if not m:
        return text  # don't attempt if no <head>
    insert_pos = m.end()
    return text[:insert_pos] + "\n" + snippet + text[insert_pos:]


def ensure_meta_charset(text: str) -> str:
    if HAS_META_CHARSET_RE.search(text) or HAS_HTTP_EQUIV_CT_RE.search(text):
        return text
    return insert_after_head_open(text, '  <meta charset="utf-8">')


def ensure_viewport(text: str) -> str:
    if HAS_VIEWPORT_RE.search(text):
        return text
    return insert_after_head_open(text, '  <meta name="viewport" content="width=device-width, initial-scale=1">')


def ensure_lang(text: str, rel_path: str) -> str:
    if HAS_LANG_RE.search(text):
        return text
    # Only set for known missing files (safe fix)
    if rel_path in FONT_AWESOME_MISSING_LANG:
        # Add lang="en" on <html>
        def _add_lang(m):
            tag = m.group(0)
            if tag.endswith('>'):
                return tag[:-1] + ' lang="en">'
            return tag + ' lang="en">'
        return HTML_OPEN_RE.sub(_add_lang, text, count=1)
    return text


def process_file(p: Path) -> bool:
    rel = str(p.relative_to(ROOT)).replace("\\", "/")
    orig = p.read_text(encoding="utf-8", errors="ignore")
    text = orig

    text = ensure_doctype(text)
    text = ensure_meta_charset(text)
    text = ensure_viewport(text)
    text = ensure_lang(text, rel)

    if text != orig:
        p.write_text(text, encoding="utf-8")
        return True
    return False


def content_sensitive_fix(p: Path) -> bool:
    # Broader content-sensitive fixes: links, images, headings, tables
    rel = str(p.relative_to(ROOT))
    html = p.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "lxml")

    changed = False

    # Helpers
    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").strip())

    def page_title() -> str:
        t = soup.title.get_text() if soup.title else ""
        t = norm(t)
        if " | " in t:
            t = t.split(" | ", 1)[0]
        return t

    def nearest_heading_text(node) -> str:
        # Walk previous elements to find last h1-h4 text
        for el in node.find_all_previous(["h1", "h2", "h3", "h4"]):
            txt = norm(el.get_text())
            if txt:
                return txt
        return page_title()

    ambiguous = re.compile(r"\b(click here|ici|read more|en savoir plus|more|learn more|ecouter ici)\b", re.I)

    # 1) Links: add aria-label for icon-only or ambiguous text
    for a in soup.find_all("a"):
        txt = norm(a.get_text())
        if not a.has_attr('aria-label') and not a.has_attr('aria-labelledby'):
            if txt == "":
                # icon-only link: prefer inner img alt
                label = None
                for img in a.find_all('img'):
                    alt = norm(img.get('alt'))
                    if alt:
                        label = alt
                        break
                if not label and a.has_attr('title'):
                    label = norm(a['title'])
                if not label:
                    label = nearest_heading_text(a)
                if label:
                    a['aria-label'] = label
                    changed = True
            elif ambiguous.search(txt):
                ctx = nearest_heading_text(a)
                label = f"{txt}: {ctx}" if ctx else txt
                a['aria-label'] = label
                changed = True

    # 2) Images: ensure alt; avoid duplicating link text
    for img in soup.find_all('img'):
        alt = img.get('alt')
        if alt is None:
            parent_link = img.find_parent('a')
            # If link has an accessible name, make image decorative
            if parent_link and (parent_link.get('aria-label') or norm(parent_link.get_text())):
                img['alt'] = ''
                img['role'] = 'presentation'
                changed = True
            elif img.get('title'):
                img['alt'] = norm(img.get('title'))
                changed = True
            else:
                # Try figure>figcaption
                fig = img.find_parent('figure')
                caption = norm(fig.figcaption.get_text()) if fig and fig.find('figcaption') else ''
                if caption:
                    img['alt'] = caption[:120]
                    changed = True
                else:
                    img['alt'] = ''
                    img['role'] = 'presentation'
                    changed = True
        elif norm(alt) == "":
            # If image is inside named link, keep decorative
            parent_link = img.find_parent('a')
            if parent_link and (parent_link.get('aria-label') or norm(parent_link.get_text())):
                if img.get('role') != 'presentation':
                    img['role'] = 'presentation'
                    changed = True

    # 3) Headings: provide single h1 and smooth level jumps
    headings = soup.find_all(re.compile(r'^h[1-6]$', re.I))
    # Promote first heading to h1 if missing
    if headings and not soup.find('h1'):
        first = headings[0]
        if first.name != 'h1':
            first.name = 'h1'
            changed = True
    # Fix level jumps
    prev_level = None
    for h in soup.find_all(re.compile(r'^h[1-6]$', re.I)):
        lvl = int(h.name[1])
        if prev_level is not None and (lvl - prev_level) > 1:
            new_lvl = prev_level + 1
            if new_lvl < 1:
                new_lvl = 1
            h.name = f'h{new_lvl}'
            changed = True
            prev_level = new_lvl
        else:
            prev_level = lvl

    # 4) Tables: detect layout vs data tables. Mark layout tables with role='presentation'.
    # Data tables get proper headers with scope.
    for t in soup.find_all('table'):
        if t.get('role') == 'presentation':
            continue
        rows = t.find_all('tr')
        has_any_th = bool(t.find('th'))
        if not rows:
            continue

        # Heuristic: if table has no th and most/all rows have single cell, likely layout
        # Also check for malformed tables (rows with no td/th cells - invalid HTML)
        def is_layout_table():
            if has_any_th:
                return False
            if len(rows) < 2:
                return False
            cells_per_row = [len(r.find_all(['td','th'])) for r in rows]
            empty_rows = sum(1 for c in cells_per_row if c == 0)
            single_cell_rows = sum(1 for c in cells_per_row if c == 1)
            # If most rows have no cells (malformed) or single cell, it's layout
            return (empty_rows + single_cell_rows) >= len(rows) * 0.8

        if is_layout_table():
            t['role'] = 'presentation'
            changed = True
        elif not has_any_th:
            # Data table without headers: promote first row to th(col), first column to th(row)
            for r_idx, tr in enumerate(rows):
                cells = tr.find_all(['td', 'th'])
                if not cells:
                    continue
                if r_idx == 0:
                    for c in cells:
                        if c.name != 'th':
                            c.name = 'th'
                            changed = True
                        if not c.get('scope'):
                            c['scope'] = 'col'
                            changed = True
                else:
                    first = cells[0]
                    if first.name != 'th':
                        first.name = 'th'
                        changed = True
                    if not first.get('scope'):
                        first['scope'] = 'row'
                        changed = True
        else:
            # Add scope to existing th
            for r_idx, tr in enumerate(rows):
                cells = tr.find_all(['th', 'td'])
                for c_idx, cell in enumerate(cells):
                    if cell.name == 'th' and not cell.get('scope'):
                        if r_idx == 0:
                            cell['scope'] = 'col'
                            changed = True
                        elif c_idx == 0:
                            cell['scope'] = 'row'
                            changed = True

    # 5) <title>: ensure non-empty and unique title
    # Build title from first heading or filename, with site suffix for consistency
    def first_heading_text():
        for tag in ['h1', 'h2', 'h3', 'h4']:
            el = soup.find(tag)
            if el:
                return norm(el.get_text())
        return ''

    def fallback_from_filename():
        name = Path(rel).name.rsplit('.', 1)[0]
        name = name.replace('-', ' ').replace('_', ' ').replace('%', ' ').strip()
        return name.title() if name else 'Page'

    SITE_SUFFIX = " | Decoding Marine Le Pen's Rhetoric"

    head = soup.find('head')
    title_el = soup.find('title')
    title_text = norm(title_el.get_text()) if title_el else ''

    # Normalize existing titles to ensure uniqueness and consistency
    new_title = None
    if not title_text:
        base = first_heading_text() or fallback_from_filename()
        new_title = base + SITE_SUFFIX
    elif title_text and not title_text.endswith(SITE_SUFFIX.strip()):
        # Ensure consistent suffix
        base = title_text.split('|')[0].strip() if '|' in title_text else title_text
        if not base:
            base = first_heading_text() or fallback_from_filename()
        new_title = base + SITE_SUFFIX

    if new_title:
        if not head:
            head = soup.new_tag('head')
            if soup.html:
                soup.html.insert(0, head)
            else:
                soup.insert(0, head)
            changed = True
        if not title_el:
            title_el = soup.new_tag('title')
            head.append(title_el)
            changed = True
        title_el.string = new_title
        changed = True

    if changed:
        p.write_text(str(soup), encoding="utf-8")
    return changed


def main():
    mode = "safe"
    if len(sys.argv) > 1:
        if sys.argv[1] == "--content-sensitive":
            mode = "content"
        elif sys.argv[1] == "--all":
            mode = "all"

    html_files = [p for p in ROOT.glob(HTML_GLOB) if p.is_file()]
    changed = 0
    for p in html_files:
        try:
            if mode == "safe":
                if process_file(p):
                    changed += 1
            elif mode == "content":
                if content_sensitive_fix(p):
                    changed += 1
            elif mode == "all":
                did = False
                if process_file(p):
                    did = True
                if content_sensitive_fix(p):
                    did = True
                if did:
                    changed += 1
        except Exception as e:
            print(f"Skip {p}: {e}")
    print(f"Mode: {mode}. Updated {changed} files out of {len(html_files)}.")


if __name__ == "__main__":
    main()
