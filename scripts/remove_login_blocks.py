#!/usr/bin/env python3
"""
Remove SUNetID and WebAuth login blocks from HTML files.
"""

from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent.parent

def remove_login_blocks(html_path):
    """Remove SUNetID and WebAuth login blocks from an HTML file."""
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    soup = BeautifulSoup(content, 'html.parser')
    modified = False
    
    # Find and remove SUNetID Login block
    sunetid_block = soup.find('div', id='block-stanford-saml-block-stanford-saml-block-login-block')
    if sunetid_block:
        sunetid_block.decompose()
        modified = True
    
    # Find and remove WebAuth Login block
    webauth_block = soup.find('div', id='block-webauth-webauth-login-block')
    if webauth_block:
        webauth_block.decompose()
        modified = True
    
    if modified:
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(str(soup))
        return True
    return False

def main():
    html_files = sorted(ROOT.glob('*.html'))
    updated_count = 0
    
    for html_file in html_files:
        if remove_login_blocks(html_file):
            updated_count += 1
            print(f"Updated: {html_file.name}")
    
    print(f"\nRemoved login blocks from {updated_count} files out of {len(html_files)} total.")

if __name__ == '__main__':
    main()
