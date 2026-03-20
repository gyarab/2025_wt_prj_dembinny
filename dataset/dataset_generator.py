import pandas as pd
import random
import unicodedata

def remove_diacritics(input_str):
    """Converts 'Šimon' to 'Simon' for emails."""
    nfkd_form = unicodedata.normalize('NFKD', str(input_str))
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def get_name_pool(file_path):
    """Extracts unique names from the 'JMÉNO' column of your dataset."""
    try:
        # These Czech files are usually encoded in cp1250 (Windows) or utf-8
        try:
            df = pd.read_csv(file_path, encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, encoding='cp1250', sep=None, engine='python')
        
        # We only care about the names, not the frequency years
        oup = map(lambda a: a.split(),df['JMÉNO'].dropna().unique().tolist())
        return list(filter(lambda a: len(a) == 2, oup))
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []

def make_files(names_path, num_files=5, rows_per_file=30):
    pool = get_name_pool(names_path)

    for i in range(1, num_files + 1):
        data = []
        for row_num in range(1, rows_per_file + 1):
            ent = random.choice(pool)
            f_name = ent[0]
            l_name = ent[1]
            
            # Clean email logic for students
            clean_f = remove_diacritics(f_name.lower().replace(" ", "-"))
            clean_l = remove_diacritics(l_name.lower().replace(" ", "-"))
            email = f"{clean_f}.{clean_l}.s@skola.cz"
            
            data.append([row_num, l_name, f_name, email])
        
        filename = f"test_set_{i}.csv"
        df_out = pd.DataFrame(data, columns=["number", "last_name", "first_name", "email"])
        df_out.to_csv(filename, index=False, encoding='utf-8')
        print(f"Generated {filename}")

# Run it
# make_files('jmena.csv', 'prijmeni.csv')
# --- CONFIGURATION ---
# 1. Download the surname file (prijmeni.csv) from the same source
# 2. Update these filenames to match yours
make_files(names_path='jmena.csv', num_files=10)