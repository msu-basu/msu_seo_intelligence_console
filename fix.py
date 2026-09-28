import os
import re

path = "src/data/loaders.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Completely replace the detect_and_load_all function
import_block = "import pandas as pd\nfrom pathlib import Path\nfrom typing import Dict, Union\n"

old_func_start = "def detect_and_load_all"

# Let's just do a manual find and replace on the exact loop block
content = re.sub(
    r'    for file in file_list:.*?if df\.empty:',
    """    for file in file_list:
        if file.suffix.lower() == ".parquet":
            df = pd.read_parquet(file)
        elif file.suffix.lower() in [".xlsx", ".xls"]:
            df = load_excel_file(file)
        else:
            df = pd.read_parquet(file)
            
        if df.empty:""",
    content, flags=re.DOTALL
)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Loaders fixed.")
