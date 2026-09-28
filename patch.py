import os
import re
from pathlib import Path

def patch_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    # 1. Change data paths
    content = content.replace('"data/input"', '"data/processed"')
    content = content.replace("'data/input'", "'data/processed'")
    content = content.replace('DATA_DIR/"', 'DATA_DIR/"') # no change needed if defined via DATA_DIR

    # 2. Change filenames from .csv to .parquet
    content = re.sub(r'(\w+\.)csv', r'\1parquet', content)
    
    # 3. Change pd.read_csv to pd.read_parquet
    # We must remove the CSV specific kwargs like encoding, on_bad_lines, skiprows, engine
    # Parquet doesn't use these.
    
    # Very basic replacement first
    content = content.replace("pd.read_csv(", "pd.read_parquet(")
    
    # Strip out CSV args if they exist on the exact same line (simple heuristic for this project)
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if "read_parquet" in line:
            # Remove encoding
            line = re.sub(r',\s*encoding=["\'][^"\']+["\']', '', line)
            # Remove low_memory
            line = re.sub(r',\s*low_memory=(True|False)', '', line)
            # Remove engine
            line = re.sub(r',\s*engine=["\'][^"\']+["\']', '', line)
            # Remove skiprows
            line = re.sub(r',\s*skiprows=\d+', '', line)
            # Remove on_bad_lines
            line = re.sub(r',\s*on_bad_lines=["\'][^"\']+["\']', '', line)
            # Remove header
            line = re.sub(r',\s*header=\d+', '', line)
            
            lines[i] = line
            
    content = '\n'.join(lines)

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Patched: {filepath}")

# Find all py files
for root, _, files in os.walk('pages'):
    for f in files:
        if f.endswith('.py'):
            patch_file(os.path.join(root, f))

# Also patch src/data/loaders.py
# (Actually, let's just patch the pages for now, as they are the ones we just updated to be standalone)
patch_file('src/data/loaders.py')

print("All files patched for Parquet!")
