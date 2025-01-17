"""
Finetunes a small language model (i.e. BERT and friends) 
to predict a label using text data.
"""

#%%

import pandas as pd
import numpy as np
from transformers import AutoTokenizer, AutoModelForSequenceClassification, TrainingArguments, Trainer
from datasets import Dataset
import evaluate
import yaml

# main paths
dict_path = "../../dictionaries/"
data_path = "../../data/"
output_path = "../../output/"
models_path = "../../models/"

# read main parameters from file
with open("params.yaml") as stream:
    params = yaml.safe_load(stream)

# name of selected language model from HuggingFace model hub
model_name = params["slm_name"]

#%%

# read text data
df_text = pd.read_csv(data_path + "epu_modern_text.csv", index_col=0)

# read train and test labels
df_train = pd.read_csv(data_path + "epu_train.csv")
df_train["label"] = df_train["label"].astype(int) 
df_test = pd.read_csv(data_path + "epu_test.csv")
df_test["label"] = df_test["label"].astype(int) 

# join data
df_test = pd.merge(df_test, df_text, how="left", 
                   left_on="unique_id_current",
                   right_on="article")

df_train = pd.merge(df_train, df_text, how="left", 
                   left_on="unique_id_current",
                   right_on="article")

# transform data into Dataset class
finetune_dataset = Dataset.from_pandas(df_train)
test_dataset = Dataset.from_pandas(df_test)

#%%

num_categories = 2

# load a tokenizer using the name of the model we want to use
tokenizer = AutoTokenizer.from_pretrained(model_name)

# tokenize the datasets
def tokenize_function(examples):
    return tokenizer(examples["text"],
                     max_length=min(512, len(df_train["text"].max())), 
                     padding="max_length", 
                     truncation=True)

tokenized_ft = finetune_dataset.map(tokenize_function, batched=True)    # batched=True is key for training
tokenized_test = test_dataset.map(tokenize_function, batched=True)

#%%

# load the model
model_ft = AutoModelForSequenceClassification.from_pretrained(model_name,
                                                              num_labels=num_categories,
                                                              output_hidden_states=False)

#%%

# define the main arguments for training
training_args = TrainingArguments(output_dir=models_path,
                                  learning_rate=float(params["slm_learning_rate"]),                
                                  num_train_epochs=params["slm_epochs"],                 
                                  per_device_train_batch_size=8,
                                  per_device_eval_batch_size=8,
                                  eval_strategy="no",
                                  save_strategy="no")

#%%

# define the set of metrics to be computed through the training process
metric1 = evaluate.load("precision")
metric2 = evaluate.load("recall")
metric3 = evaluate.load("f1")
metric4 = evaluate.load("accuracy")

def compute_metrics(eval_pred):

    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)

    precision = metric1.compute(predictions=predictions, references=labels, average="macro")["precision"]
    recall = metric2.compute(predictions=predictions, references=labels, average="macro")["recall"]
    f1 = metric3.compute(predictions=predictions, references=labels, average="macro")["f1"]
    accuracy = metric4.compute(predictions=predictions, references=labels)["accuracy"]

    return {"precision": precision, "recall": recall,
            "f1": f1, "accuracy": accuracy}

# by default the Trainer will use MSEloss from (torch.nn) for regression and
# CrossEntropy loss for classification
trainer = Trainer(
    model=model_ft,
    args=training_args,
    train_dataset=tokenized_ft,
    eval_dataset=tokenized_test,
    compute_metrics=compute_metrics
)

#%%

# train!
trainer.train()

# save final version of the model
trainer.save_model(models_path)

# %%

# evaluate final model on the test dataset
results = trainer.predict(tokenized_test)
predictions = np.argmax(results.predictions, axis=-1)
final_metrics = results[2]
print(final_metrics)

# %%

# save a dataframe with the predictions
df_test["ft_bert"] = predictions
df_test = df_test[["article", "ft_bert"]] 
df_test.columns = ["article", "prediction"]

#%%

if "/" in model_name:
    clean_name = model_name.split("/")[1]
else:
    clean_name = model_name


df_test.to_csv(output_path + f"epu_tagged_{clean_name}.csv", index=False)
# %%
