import os
import random
import numpy as np
import torch
import nltk
import string
from tqdm import tqdm
from parrot import Parrot
import pickle
from kmeans_pytorch import kmeans
import pandas as pd
from transformers import (TrainingArguments, Trainer, AutoModelForSequenceClassification,
                          pipeline, set_seed, AutoTokenizer)
from datasets import Dataset, DatasetDict, load_metric
from nltk import tokenize
import time
import warnings
warnings.filterwarnings("ignore")

os.environ['CUDA_VISIBLE_DEVICES'] = '2'

nltk.download('punkt')

SD = int(str(time.time()).replace('.', '')) % 10000
np.random.seed(SD)  # Numpy
torch.manual_seed(SD)  # PyTorch
set_seed(SD)  # Hugging Face

TARGET_NETWORK = 'gpt2-xl'  # 'gpt2'
CLASSIFIER_MODEL = 'facebook/muppet-roberta-large'
MAX_LENGTH = 20
DEVICE = 'cuda:0'
target_lm = pipeline('text-generation',
                     model=TARGET_NETWORK,
                     do_sample=True,
                     max_length=MAX_LENGTH,
                     device=DEVICE,
                     torch_dtype=torch.float16,
                     pad_token_id=50256,
                     )
target_lm.tokenizer.pad_token = target_lm.tokenizer.eos_token
sm = torch.nn.Softmax(dim=1)


def remove_leading_whitespace(a_string):
    start = 0
    for i, c in enumerate(a_string):
        if c == ' ' or c == '\t':
            start += 1
        else:
            break
    a_string = a_string[start:]
    return a_string


def custom_sent_tokenize(a_string):
    sents = []
    sent_tokens = tokenize.sent_tokenize(a_string)
    for i, s in enumerate(sent_tokens):
        if i == 0 or s[0] in string.ascii_uppercase:
            sents.append(s)
        else:
            sents[-1] += s
    return sents


def sample(num_beams=1,
           top_p=1.0,
           top_k=50,
           max_length=MAX_LENGTH,
           early_stopping=True,
           num_return_sequences=1,
           seed='', banned_ids=None):

    utterances = target_lm(seed,
                           max_length=max_length,
                           num_beams=num_beams,
                           early_stopping=early_stopping,
                           no_repeat_ngram_size=2,
                           temperature=1.5,
                           top_p=top_p,
                           top_k=top_k,
                           num_return_sequences=num_return_sequences,
                           bad_words_ids=banned_ids,
                           pad_token_id=50256,
                           )
    utterances = [u['generated_text'].replace('\n', ' ').replace(u'\xa0', u' ') for u in utterances]
    out = []
    for u in utterances:
        sents = custom_sent_tokenize(u)
        if len(sents) > 0:
            out.append(sents[0])
    out = [o for o in out if 4 <= len(o.split(' '))]
    return out


def get_gpt2_embedding(sentences, bs=32):

    with torch.no_grad():
        embeddings = []
        for i in range(0, len(sentences), bs):
            prompt_ids = target_lm.tokenizer(sentences[i: i+bs], return_tensors='pt', truncation=True,
                                             padding='max_length', max_length=MAX_LENGTH).input_ids.to(DEVICE)
            hidden_states = target_lm.model(prompt_ids, labels=prompt_ids, output_hidden_states=True).hidden_states
            embeddings.append(hidden_states[-1][:, -1, :])
        embeddings = torch.cat(embeddings)
    return embeddings


def sample_from_clusters(cluster_labels, embedded_sentences, sentences, samples_per_cluster):
    uniqvals, indices = np.unique(cluster_labels, return_inverse=True)
    sampled_indices = []
    for val in uniqvals:
        val_indices = np.where(cluster_labels == val)[0]
        sampled_indices.extend(np.random.choice(val_indices, min(len(val_indices), samples_per_cluster), replace=False))
    return list(np.array(sentences)[sampled_indices]), embedded_sentences[sampled_indices]


def cluster_sample_and_save(sentences, num_clusters, samples_per_cluster, savename):
    sentences = list(set(sentences))
    with open(f'./data/{savename}_explore_sentences.pkl', 'wb') as f:
        pickle.dump(sentences, f)

    encoded_sentences = get_gpt2_embedding(sentences)

    with open(f'./data/{savename}_explore_encodings.pkl', 'wb') as f:
        pickle.dump(encoded_sentences, f)

    encoded_sentences = torch.nan_to_num(encoded_sentences)
    km_labels, _ = kmeans(X=encoded_sentences, num_clusters=num_clusters, distance='cosine', device=torch.device('cpu'))
    km_labels = km_labels.numpy()

    diverse_sentences, diverse_encoded_sentences = sample_from_clusters(km_labels, encoded_sentences,
                                                                        sentences, samples_per_cluster)

    with open(f'./data/{savename}_explore_diverse_sentences.pkl', 'wb') as f:
        pickle.dump(diverse_sentences, f)
    df = pd.DataFrame({'examples': diverse_sentences})
    df.to_csv(f'./data/{savename}_explore_diverse_sentences.csv', escapechar='$')


def train_text_classifier_paraphrasing(data, dset_path='', lr=4e-5, train_epochs=1, bs=32, classifier_model=CLASSIFIER_MODEL):

    n_classes = len(data)

    # if dataset already saved
    if dset_path and os.path.isfile(dset_path):
        with open(dset_path, 'rb') as f:
            dset = pickle.load(f)
            worddict_train_1d = dset['train']
            worddict_val_1d = dset['val']
    # if not, make it and save it
    else:
        for d in data:
            random.shuffle(d)

        sentences, splits, train_sentences, val_sentences = [], [], [], []
        for d in data:
            sentences.append(np.array(d))
            splits.append(np.array_split(sentences[-1], 8))
            train_sentences.append([item for sublist in splits[-1][:-1] for item in sublist])
            val_sentences.append([item for item in splits[-1][-1]])

        print('Running augmentation...')
        parrot = Parrot(model_tag="prithivida/parrot_paraphraser_on_T5", use_gpu=True)
        train_max = max([len(ts) for ts in train_sentences])
        val_max = max([len(vs) for vs in val_sentences])
        train_augmentations = [[] for _ in train_sentences]
        val_augmentations = [[] for _ in val_sentences]
        for i, ts in enumerate(train_sentences):
            while len(train_augmentations[i]) + len(ts) < train_max * 0.99:
                for s in tqdm(ts):
                    augmentations = parrot.augment(input_phrase=s, do_diverse=True)
                    if augmentations is not None:
                        train_augmentations[i].extend([aug[0] for aug in augmentations])
        for i in range(len(train_sentences)):
            diff = train_max - len(train_sentences[i])
            if len(train_augmentations[i]) >= diff:
                train_sentences[i].extend(random.sample(train_augmentations[i], diff))
        for i, vs in enumerate(val_sentences):
            while len(val_augmentations[i]) + len(vs) < val_max * 0.99:
                for s in tqdm(vs):
                    augmentations = parrot.augment(input_phrase=s, do_diverse=True)
                    if augmentations is not None:
                        val_augmentations[i].extend([aug[0] for aug in augmentations])
        for i in range(len(val_sentences)):
            diff = val_max - len(val_sentences[i])
            if len(val_augmentations[i]) >= diff:
                val_sentences[i].extend(random.sample(val_augmentations[i], diff))

        worddict_train_1d, worddict_val_1d = dict(), dict()
        for i, ts in enumerate(train_sentences):
            for sent in ts:
                worddict_train_1d[sent] = i
        for i, vs in enumerate(val_sentences):
            for sent in vs:
                worddict_val_1d[sent] = i

        if dset_path:
            with open(dset_path, 'wb') as f:
                pickle.dump({'train': worddict_train_1d, 'val': worddict_val_1d}, f)

        del parrot

    dset = DatasetDict({
        "train": Dataset.from_pandas(
            pd.DataFrame(
                {"question": list(worddict_train_1d.keys()), "label": list(worddict_train_1d.values())})).shuffle(
            seed=0).select((range(len(worddict_train_1d)))),
        "validation": Dataset.from_pandas(pd.DataFrame(
            {"question": list(worddict_val_1d.keys()), "label": list(worddict_val_1d.values())})).shuffle(
            seed=0).select((range(len(worddict_val_1d)))),
    })

    sd = int(str(time.time()).replace('.', '')) % 10000
    np.random.seed(sd)  # Numpy
    torch.manual_seed(sd)  # PyTorch
    set_seed(sd)  # Hugging Face

    model = AutoModelForSequenceClassification.from_pretrained(classifier_model, num_labels=n_classes,
                                                               ignore_mismatched_sizes=True).to(DEVICE)
    classifier_tokenizer = AutoTokenizer.from_pretrained(classifier_model)

    training_args = TrainingArguments(
        output_dir='./models/tmp',
        evaluation_strategy="epoch",
        learning_rate=lr,
        num_train_epochs=train_epochs,
        auto_find_batch_size=True,
        per_device_train_batch_size=bs,
        per_device_eval_batch_size=bs,
        report_to='none',
        seed=sd)
    param_count = sum(p.numel() for p in model.parameters())
    print(f'Model [{classifier_model}] size: {param_count // 1000000}M parameters')

    def tokenize_function(inputs):
        # might need to change max_length if this causes an error
        return classifier_tokenizer(inputs["question"], padding="max_length", truncation=True, max_length=MAX_LENGTH)
    tokenized_datasets = dset.map(tokenize_function, batched=True)

    acc_metric = load_metric("accuracy")  # use f1 in favor of "accuracy" for imbalanced tasks
    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        predictions = np.argmax(logits, axis=-1)
        print(np.sum(np.logical_and(labels==0, logits[:, 0] > logits[:, 1])))
        print(len(labels[labels==0]))
        metrics = {**acc_metric.compute(predictions=predictions, references=labels)}
        for i in range(len(data)):
            metrics.update(**{f'label_{i}_acc': np.sum(np.logical_and(labels==i, predictions==i)) / len(labels[labels==i])})
        return metrics

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_datasets['train'],
        eval_dataset=tokenized_datasets['validation'],
        compute_metrics=compute_metrics,
    )
    trainer.train()
    metrics = trainer.evaluate(tokenized_datasets['validation'])
    failed = any([metrics[f'eval_label_{i}_acc'] < 0.2 for i in range(n_classes)])
    return model, failed
