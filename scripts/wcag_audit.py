#!/usr/bin/env python3
import re
import sys
from pathlib import Path
from collections import defaultdict, Counter
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]

HTML_GLOB = "**/*.html"

IMG_AMBIGUOUS_ALTS = {"", None}
AMBIGUOUS_LINK_TEXTS = re.compile(r"\b(click here|ici|read more|en savoir plus|more|learn more)\b", re.I)

Issue = dict  # {severity, rule, message, context}


def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return p.read_text(errors="ignore")


def has_doctype(text: str) -> bool:
    return bool(re.search(r"<!DOCTYPE\s+html", text, re.I))


def norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def check_file(p: Path):
    rel = p.relative_to(ROOT)
    text = read_text(p)
    soup = BeautifulSoup(text, "lxml")

    issues: list[Issue] = []

    # Doctype
    if not has_doctype(text):
        issues.append({
            "severity": "warn",
            "rule": "H67",
            "message": "Missing `<!DOCTYPE html>`; helps consistent semantics across UAs.",
            "context": str(rel),
        })

    # <html lang>
    html_el = soup.find("html")
    lang = (html_el.get("lang") if html_el else None)
    has_html_tag_in_source = bool(re.search(r"<html\b", text, re.I))
    if has_html_tag_in_source and html_el is not None and not lang:
        issues.append({
            "severity": "error",
            "rule": "H57",
            "message": "Missing language attribute on <html> (e.g., lang=\"fr\").",
            "context": str(rel),
        })

    # <head><title>
    title_el = soup.find("title")
    title_text = norm_space(title_el.get_text() if title_el else "")
    if not title_text:
        issues.append({
            "severity": "error",
            "rule": "G88/F25",
            "message": "Missing or empty <title> element.",
            "context": str(rel),
        })

    # meta charset
    meta_charset = soup.find("meta", attrs={"charset": True}) or soup.find("meta", attrs={"http-equiv": re.compile("content-type", re.I)})
    if not meta_charset:
        issues.append({
            "severity": "warn",
            "rule": "BEST-PRACTICE",
            "message": "Missing `<meta charset>`; improves parsing reliability.",
            "context": str(rel),
        })

    # meta viewport (best practice for reflow / zoom)
    viewport = soup.find("meta", attrs={"name": re.compile("viewport", re.I)})
    if not viewport:
        issues.append({
            "severity": "warn",
            "rule": "1.4.10/1.4.4",
            "message": "Missing responsive viewport meta; may affect zoom/reflow on mobile.",
            "context": str(rel),
        })

    # Headings
    headings = [(int(h.name[1]), norm_space(h.get_text())) for h in soup.find_all(re.compile("^h[1-6]$", re.I))]
    h1_count = sum(1 for lvl, _ in headings if lvl == 1)
    if h1_count == 0:
        issues.append({
            "severity": "warn",
            "rule": "G141",
            "message": "No <h1> heading found; consider providing a clear page heading.",
            "context": str(rel),
        })
    elif h1_count > 1:
        issues.append({
            "severity": "warn",
            "rule": "H42",
            "message": f"Multiple <h1> headings ({h1_count}); ensure logical outline.",
            "context": str(rel),
        })
    # Heading level jumps
    prev = None
    for lvl, txt in headings:
        if prev is not None and lvl - prev > 1:
            issues.append({
                "severity": "warn",
                "rule": "H42",
                "message": f"Heading level jumps from h{prev} to h{lvl}: '{txt[:80]}'",
                "context": str(rel),
            })
            break
        prev = lvl

    # Images
    for img in soup.find_all("img"):
        alt = img.get("alt")
        role = (img.get("role") or "").lower()
        aria_hidden = (img.get("aria-hidden") or "").lower() == "true"
        if alt is None:
            issues.append({
                "severity": "error",
                "rule": "H37",
                "message": "<img> missing alt text.",
                "context": f"{rel}:{img.get('src','')}",
            })
        elif norm_space(alt) == "":
            # Empty alt is valid for decorative images; no warning
            pass

    # Links
    def element_text_by_ids(ids: str) -> str:
        if not ids:
            return ""
        out = []
        for _id in ids.split():
            ref = soup.find(id=_id)
            if ref:
                out.append(norm_space(ref.get_text()))
        return norm_space(" ".join([t for t in out if t]))

    AMBIGUOUS_EXACT = re.compile(r"^(click here|ici|read more|en savoir plus|more|learn more)$", re.I)

    for a in soup.find_all("a"):
        href = a.get("href")
        # Accessible name computation (simplified)
        name = norm_space(a.get("aria-label")) if a.get("aria-label") else ""
        if not name and a.get("aria-labelledby"):
            name = element_text_by_ids(a.get("aria-labelledby"))
        if not name:
            name = norm_space(a.get_text())
        if not name:
            # use first non-empty img alt
            for img in a.find_all("img"):
                alt = norm_space(img.get("alt"))
                if alt:
                    name = alt
                    break

        if href and name == "":
            issues.append({
                "severity": "error",
                "rule": "G91",
                "message": "Link with empty or purely non-text content; ensure accessible name.",
                "context": f"{rel}:{href}",
            })
        elif name and AMBIGUOUS_EXACT.search(name):
            issues.append({
                "severity": "warn",
                "rule": "G91/G94",
                "message": f"Ambiguous link text '{name}'.",
                "context": f"{rel}:{href or ''}",
            })

    # Forms
    for inp in soup.find_all(["input", "select", "textarea"]):
        if inp.name == "input" and (inp.get("type") or "").lower() in {"hidden", "submit", "button", "image", "reset"}:
            continue
        # has visible label wrapper
        has_label_wrapper = any(parent.name == "label" for parent in inp.parents if getattr(parent, 'name', None))
        id_ = inp.get("id")
        has_for_label = bool(id_ and soup.find("label", attrs={"for": id_}))
        has_aria = bool(inp.get("aria-label") or inp.get("aria-labelledby"))
        has_title = bool(inp.get("title"))
        if not (has_label_wrapper or has_for_label or has_aria or has_title):
            issues.append({
                "severity": "error",
                "rule": "H44/H65",
                "message": f"Form control missing accessible name (<label>, aria-label/labelledby, or title).",
                "context": f"{rel}:{inp.name}",
            })

    # Tables
    for table in soup.find_all("table"):
        # Skip tables marked as presentation (layout tables)
        if table.get('role') == 'presentation':
            continue
        ths = table.find_all("th")
        if len(ths) == 0:
            issues.append({
                "severity": "warn",
                "rule": "H51/H43",
                "message": "Table without headers (<th>); verify it's for layout only or add headers.",
                "context": str(rel),
            })
        else:
            scopes = [th.get("scope") for th in ths]
            if not any(scopes):
                issues.append({
                    "severity": "warn",
                    "rule": "H63",
                    "message": "<th> elements missing scope/headers association.",
                    "context": str(rel),
                })

    return {
        "file": str(rel),
        "title": title_text,
        "issues": issues,
    }


def main():
    html_files = sorted((p for p in ROOT.glob(HTML_GLOB) if p.is_file()), key=lambda p: str(p))
    results = []
    title_to_files = defaultdict(list)
    for p in html_files:
        res = check_file(p)
        results.append(res)
        title_to_files[res["title"]].append(res["file"])

    # Site-level: duplicate titles
    dup_titles = {t: fs for t, fs in title_to_files.items() if t and len(fs) > 1}

    # Aggregate counts
    severity_counts = Counter()
    rule_counts = Counter()
    total_issues = 0
    for r in results:
        for i in r["issues"]:
            severity_counts[i["severity"]] += 1
            key = f"{i['severity']}:{i['rule']}"
            rule_counts[key] += 1
            total_issues += 1

    report = []
    report.append("# Accessibility Audit (WCAG 2.x static checks)")
    report.append("")
    report.append(f"Scanned {len(results)} HTML pages. Found {total_issues} issues: "
                  f"{severity_counts.get('error',0)} errors, {severity_counts.get('warn',0)} warnings.")
    report.append("")
    report.append("Note: Automated static analysis; manual review is still required for color contrast, keyboard navigation, focus order, dynamic content, and ARIA semantics.")
    report.append("")

    if dup_titles:
        report.append("## Site-wide Findings")
        report.append("")
        report.append("- Duplicate page titles detected (unique titles help orientation):")
        for t, fs in sorted(dup_titles.items(), key=lambda x: x[0].lower()):
            report.append(f"  - '{t}': {len(fs)} pages")
        report.append("")

    report.append("## Top Issue Types")
    for (key, count) in rule_counts.most_common(10):
        sev, rule = key.split(":", 1)
        report.append(f"- {sev.upper()} {rule}: {count}")
    report.append("")

    report.append("## Per-Page Details")
    for r in results:
        report.append(f"### {r['file']}")
        title_line = r["title"] or "(no title)"
        report.append(f"- Title: {title_line}")
        if not r["issues"]:
            report.append("- No issues found.")
        else:
            for i in r["issues"]:
                report.append(f"- {i['severity'].upper()} {i['rule']}: {i['message']} ({i['context']})")
        report.append("")

    out_path = ROOT / "accessibility-report.md"
    out_path.write_text("\n".join(report), encoding="utf-8")
    print(f"Wrote report to {out_path}")


if __name__ == "__main__":
    sys.exit(main())
