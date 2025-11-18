# WCAG 2.x Accessibility Compliance

## Summary

This site has been audited and remediated for WCAG 2.x compliance using automated static analysis tools.

**Current Status:** ✅ **0 errors, 4 warnings** (263 HTML pages scanned)

The 4 remaining warnings are for Font Awesome webfont stub files missing `<h1>` headings, which is acceptable for these binary placeholder files.

## Automated Fixes Applied

### Safe Fixes
- ✅ Added `<!DOCTYPE html>` where missing
- ✅ Added `<meta charset="utf-8">` where missing
- ✅ Added `<meta name="viewport" content="width=device-width, initial-scale=1">` for responsive design
- ✅ Added `lang="en"` attribute to `<html>` tags where missing

### Content Fixes
- ✅ **Links:** Added `aria-label` to icon-only and ambiguous links using:
  - Inner image `alt` text
  - Link `title` attribute
  - Nearest heading context
  - Page title as fallback
- ✅ **Images:** 
  - Added `alt` text from `title` or `figcaption` where missing
  - Marked decorative images with `alt=""` and `role="presentation"`
- ✅ **Headings:**
  - Ensured each page has exactly one `<h1>`
  - Fixed heading level jumps (e.g., h2 → h5 becomes h2 → h3)
- ✅ **Tables:**
  - Marked layout tables with `role="presentation"`
  - Added `<th>` elements with proper `scope` attributes to data tables
- ✅ **Titles:**
  - Auto-filled missing `<title>` tags from headings or filenames
  - Normalized all titles to consistent format with site suffix

## Tools Created

### `scripts/wcag_audit.py`
Static WCAG compliance checker that scans all HTML files and generates a detailed report (`accessibility-report.md`).

**Usage:**
```bash
/Users/qad/Documents/GitHub/marinelepen/.venv/bin/python scripts/wcag_audit.py
```

**Checks:**
- DOCTYPE presence
- HTML lang attribute
- Page titles
- Meta charset and viewport
- Heading structure and hierarchy
- Image alt text
- Link accessible names
- Form control labels
- Table headers and scope
- ARIA attributes

### `scripts/wcag_autofix.py`
Automated remediation tool with three modes:

**Safe mode** (non-destructive metadata fixes):
```bash
/Users/qad/Documents/GitHub/marinelepen/.venv/bin/python scripts/wcag_autofix.py
```

**Content-sensitive mode** (adds aria-labels, fixes headings/tables):
```bash
/Users/qad/Documents/GitHub/marinelepen/.venv/bin/python scripts/wcag_autofix.py --content-sensitive
```

**All fixes mode** (runs both safe and content-sensitive):
```bash
/Users/qad/Documents/GitHub/marinelepen/.venv/bin/python scripts/wcag_autofix.py --all
```

## Manual Review Still Required

⚠️ **Note:** Automated tools cannot check everything. Manual testing is still required for:

- **Color Contrast:** Ensure text meets WCAG AA/AAA contrast ratios (4.5:1 for normal text, 3:1 for large text)
- **Keyboard Navigation:** Verify all interactive elements are keyboard accessible
- **Focus Indicators:** Ensure visible focus indicators on all focusable elements
- **Dynamic Content:** Test AJAX updates, modals, and live regions with screen readers
- **ARIA Semantics:** Validate complex ARIA patterns (tabs, accordions, etc.)
- **Screen Reader Testing:** Test with NVDA, JAWS, VoiceOver
- **Form Validation:** Ensure error messages are accessible
- **Multimedia:** Add captions/transcripts for audio/video content

## Remaining Considerations

### Duplicate Page Titles
Many pages share the same title (e.g., "News | Decoding Marine Le Pen's Rhetoric"). While not a WCAG violation, unique titles improve:
- User orientation (browser tabs, history)
- SEO
- Screen reader navigation

Consider making titles more specific by incorporating article dates or unique identifiers.

### Font Awesome Stubs
Four webfont HTML files have missing `<h1>` headings. These are essentially binary placeholders and can be safely ignored.

## References

- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [HTML Techniques for WCAG](https://www.w3.org/WAI/WCAG21/Techniques/#html)
- [ARIA Authoring Practices](https://www.w3.org/WAI/ARIA/apg/)

---

**Last Updated:** November 18, 2025  
**Audit Coverage:** 263 HTML pages  
**Status:** WCAG 2.x compliant (automated checks passed)
