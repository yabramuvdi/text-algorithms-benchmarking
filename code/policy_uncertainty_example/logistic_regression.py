"""
Implents a supervised learning approach to predict a label from 
text data using a Bag-of-Words representation of the text.
"""

#%%

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import f1_score, accuracy_score
from sklearn.svm import l1_min_c
from joblib import dump, load
import matplotlib.pyplot as plt
import yaml

# import custom module
import sys
sys.path.insert(1, '../utils/')
from utils import clean_sequence

# main paths
dict_path = "../../dictionaries/"
data_path = "../../data/"
output_path = "../../output/"
models_path = "../../models/"
#%%

# read main parameters from file
with open("params.yaml") as stream:
    params = yaml.safe_load(stream)

# paths and params
seed = params["seed"]
num_cv = params["num_cv"]

#%%

#=============================
# 0. Read data
#=============================

# # read text data
# df_text = pd.read_csv(data_path + "epu_modern_text.csv", index_col=0)

# # read train and test labels
# df_train = pd.read_csv(data_path + "epu_train.csv")
# df_test = pd.read_csv(data_path + "epu_test.csv")


# # join data
# df_test = pd.merge(df_test, df_text, how="left", 
#                    left_on="unique_id_current",
#                    right_on="article")

# df_train = pd.merge(df_train, df_text, how="left", 
#                    left_on="unique_id_current",
#                    right_on="article")

df_train = pd.read_parquet(data_path + "epu_train.parquet")
df_test = pd.read_parquet(data_path + "epu_test.parquet")

# %%

#=============================
# 1. Tokenization
#=============================

pattern = r'''
          (?x)                # set flag to allow verbose regexps (to separate logical sections of pattern and add comments)
          \w+(?:-\w+)*        # preserve expressions with internal hyphens as single tokens
          |\b\w+\b            # single letter words
          '''

# create a CountVectorizer object straight from the raw text
count_vectorizer = CountVectorizer(encoding='utf-8',
                                   token_pattern=pattern,
                                   lowercase=True,
                                   strip_accents="ascii",
                                   stop_words="english", 
                                   ngram_range=(1, 1),       
                                   analyzer='word',          
                                   max_features=params["max_dtm_features"],
                                   )
                                   
# transform our sequences into a document-term matrix
dt_matrix_train = count_vectorizer.fit_transform(df_train["text"])
dt_matrix_train = dt_matrix_train.toarray()
print(f"Document-term matrix created with shape: {dt_matrix_train.shape}")

#%%

# explore vocab
vocab = count_vectorizer.vocabulary_
n_terms = len(vocab)
print(f"Number of vocabulary terms: {n_terms}")

# save vectorizer
dump(count_vectorizer, models_path + 'epu_lr_vectorizer.joblib') 

#%%

# # transform document-term matrix into binary form
# dt_matrix_train_b = np.where(dt_matrix_train > 0, 1, dt_matrix_train)
# dt_matrix_train_b.shape

#%%

#=============================
# 2. Prepare K-Fold splits and parameter Grid
#=============================

# C --> Inverse of regularization strength; must be a positive float. 
# Like in support vector machines, smaller values specify stronger regularization. 

cs = np.linspace(-2, 2, 25)
cs = np.array([10**c for c in cs])

# plot lambdas
print(f"Min lambda: {np.min(cs)}, Max lambda: {np.max(cs)}")
plt.figure(figsize=(12,8))
plt.scatter(cs, cs)
plt.show()

# create grid with parameters
grid = {"penalty": ["l1"],
        "tol": [0.0001], 
        "C": 1/cs, 
        "fit_intercept": [True],  
        "random_state": [92],
        "solver": ["liblinear"], 
        "max_iter": [200]
        }

#%%

lr_cv = GridSearchCV(estimator=LogisticRegression(), 
                     param_grid=grid, 
                     cv=num_cv,
                     scoring="accuracy",
                     verbose=0,
                     n_jobs=-1)

#=============================
# 3. Fit the model
#=============================

lr_cv.fit(dt_matrix_train, df_train["label"].values)

print("\n=========================\n\n")
print("Tuned hpyerparameters : \n", lr_cv.best_params_)
print("Best F1 :", lr_cv.best_score_)
df_cv = pd.DataFrame(lr_cv.cv_results_)
df_cv.to_csv(models_path + "lr_cv_results_final.csv", index=False)

# plot results
plt.figure(figsize=(12,8))
plt.plot(df_cv["param_C"].values, df_cv["mean_test_score"].values)
plt.ylabel("F1 score")
plt.xlabel("Inverse regularization param (log)")
plt.xscale('log')
plt.show()

plt.figure(figsize=(12,8))
plt.plot(1/df_cv["param_C"].values, df_cv["mean_test_score"].values)
plt.ylabel("F1 score")
plt.xlabel("Regularization param (log)")
plt.xscale('log')
plt.show()

#%%

#=============================
# 4. Out of sample predictions
#=============================

# extract optimal model fitted on whole training data
lr_opt = lr_cv.best_estimator_

# save optimal model
dump(lr_opt, models_path + 'epu_lr_model.joblib') 

# %%

#=============================
# Tokenization
#=============================

# transform our sequences into a document-term matrix
# use the same vectorizer from the train data
dt_matrix_test = count_vectorizer.transform(df_test["text"])
dt_matrix_test = dt_matrix_test.toarray()
print(f"Document-term matrix created with shape: {dt_matrix_test.shape}")

# # transform document-term matrix into binary form
# dt_matrix_test_b = np.where(dt_matrix_test > 0, 1, dt_matrix_test)
# dt_matrix_test_b.shape

# %%

#=============================
# Predict and save results
#=============================

y_hat_test = lr_opt.predict(dt_matrix_test)
df_test["prediction"] = y_hat_test
print("Accuracy score in test data: ", accuracy_score(df_test["label"], df_test["prediction"]))

#%%

# save results
df_test = df_test[["article_id", "vintage","prediction"]]
df_test.to_csv(output_path + "epu_tagged_lr.csv", index=False)

# %%