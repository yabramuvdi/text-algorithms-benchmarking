""" Loads and prepares the Economic Policy Uncertainty Data
"""

#%%

import pandas as pd
import numpy as np
import yaml
import os
import shutil

# main paths
data_path = "../../data/"
articles_path = "../../../EPU/All Audit Hard Copies/All Audit Hard Copies/Modern/"
output_path = "../../labeled_articles/"

# read main parameters from file
with open("params.yaml") as stream:
    params = yaml.safe_load(stream)

seed = params["seed"]
test_size = params["test_size"]

# %%

#===============
# Master data with labels
#===============

# load complete master data
df_master = pd.read_stata(data_path + "EPU_AUDIT_MASTER_FILE.dta")
df_master = df_master.loc[df_master["vintage"] == "Current"]
# key column is EPU and ID is a comination of article number and year
df_master = df_master[["article_number", "year", "month", "EPU"]]

#%%

# get unique label as a majority vote
df_master = df_master.groupby(["article_number", "year", "month"], as_index=False).mean()

def classify_epu(score):
    if score > 0.5:
        return 1
    elif score < 0.5:
        return 0
    else:
        return np.nan
    
df_master["label"] = df_master["EPU"].apply(classify_epu)
df_master.dropna(inplace=True)
#%%

# load master data for modern articles (provided by Baker)
df_master_modern = pd.read_stata(data_path + "modern_unique_ids.dta")
df_master_modern.drop_duplicates(inplace=True)

# %%

df_complete = pd.merge(df_master, df_master_modern, on=["article_number", "year", "month"])
df_complete.to_csv(data_path + "epu_modern_labels.csv", index=False)
# %%

#===============
# Save only articles with labels
#===============

all_success = []
for article in df_complete["unique_id_current"].values:
    try:
        print(article)
        source_file = os.path.join(articles_path, article + ".html")
        destination_file = os.path.join(output_path, article + ".html")
        # Copy the file
        shutil.copy2(source_file, destination_file)
        print(f'Copied {source_file} to {destination_file}')
        all_success.append(True)
    except Exception as e:
        print(f'An error occurred: {e} with file {article}')
        all_success.append(False)
        
# %%
