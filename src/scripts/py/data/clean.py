import numpy as np
import pandas as pd

df = pd.read_csv('drugs.csv', usecols=['Generic Name', 'Brand Name'])

df_melted = df.melt(
    value_vars=['Generic Name', 'Brand Name'],
    var_name='Drug_Type',
    value_name='Drugs' 
)

df_clean = df_melted.drop_duplicates()
df_clean.to_csv('drug_cleaned.csv', index=False)
