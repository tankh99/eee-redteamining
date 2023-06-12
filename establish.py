from transformers import RobertaTokenizer, RobertaForSequenceClassification
from lm_utils import *

TRAIN_EPOCHS = 1
TRAIN_BATCH_SIZE = 32
LEARNING_RATE = 1e-4
ENSEMBLE_SIZE = 5

if __name__ == '__main__':

    print(f'Running establish step...')

    toxicity_tokenizer = RobertaTokenizer.from_pretrained(
        'SkolkovoInstitute/roberta_toxicity_classifier')
    toxicity_classifier = RobertaForSequenceClassification.from_pretrained(
        'SkolkovoInstitute/roberta_toxicity_classifier').to(DEVICE)

    with open(f'./data/toxicity_explore_diverse_sentences.pkl', 'rb') as f:
        sentences = pickle.load(f)

    random.shuffle(sentences)
    good_sentences, bad_sentences = [], []
    for i in tqdm(range(len(sentences))):
        sample_sentence = sentences[i]
        badness_label = (sm(toxicity_classifier(toxicity_tokenizer.encode(sample_sentence, return_tensors='pt').to(DEVICE))[0])[0][0] < 0.9).item()
        if badness_label:
            bad_sentences.append(sample_sentence)
        else:
            good_sentences.append(sample_sentence)
    print(f'num good sentences: {len(good_sentences)}, num bad sentences: {len(bad_sentences)}')

    dset_path = f'data/paraphrasing_dset.pkl'
    for i in range(ENSEMBLE_SIZE):
        failed = True
        while failed:
            model, failed = train_text_classifier_paraphrasing([good_sentences, bad_sentences],
                                                       dset_path=dset_path,
                                                       train_epochs=1)
            print(f'Model {i} training failure: {failed}. If failed, retraining; else moving to next model...')
        model.save_pretrained(f'./models/{CLASSIFIER_MODEL}_classifier_{i}')

    print('Done :)')
