#!/usr/bin/env python3
"""Copy generated HTML reports to docs/ folder for GitHub Pages deployment."""
import sys
import shutil
from pathlib import Path

# Add src directory to path to import constants
src_dir = Path(__file__).parent / 'src'
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from constants import REPORTS_DIR

def copy_reports_to_docs():
    """
    Copy all HTML reports from src/data/reports/ to docs/ for GitHub Pages.
    """
    reports_dir = Path(REPORTS_DIR)
    docs_dir = Path('docs')
    
    if not reports_dir.exists():
        print(f"Error: Reports directory not found: {reports_dir}")
        print("Please generate reports first using option 5 in main.py")
        return False
    
    # Create docs directory if it doesn't exist
    docs_dir.mkdir(exist_ok=True)
    
    # Remove existing files in docs (except README.md)
    for item in docs_dir.iterdir():
        if item.name != 'README.md' and item.is_file():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)
    
    # Copy all files and directories from reports to docs
    if reports_dir.exists():
        for item in reports_dir.iterdir():
            dest = docs_dir / item.name
            if item.is_file():
                shutil.copy2(item, dest)
                print(f"Copied: {item.name}")
            elif item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
                print(f"Copied directory: {item.name}/")
    
    print(f"\n✅ Successfully copied reports to {docs_dir}/")
    print(f"📁 Reports are ready for GitHub Pages deployment!")
    return True

if __name__ == '__main__':
    copy_reports_to_docs()

