from pathlib import Path
import pandas as pd
from processing import get_witel_preview

path = Path(r'c:\Users\ASUS\Downloads\dapros-web-fastapi-final\dapros-web\uploads\preview_00a97cedfa524dbab4ba650bec105e30.xlsx')
print('File exists:', path.exists())
if path.exists():
    xls = pd.ExcelFile(path)
    print('Sheet names:', xls.sheet_names)
    try:
        res = get_witel_preview(path)
        print('Result total:', res['total'])
        print('Result witels count:', len(res['witels']))
        if len(res['witels']) > 0:
            print('First witel:', res['witels'][0])
    except Exception as e:
        print('Error running get_witel_preview:', str(e))
