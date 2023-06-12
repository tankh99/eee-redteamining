from lm_utils import *

TOTAL_SENTENCES = 80000
SAMPLE_BATCH = 2
NUM_CLUSTERS = 100
SAMPLES_PER_CLUSTER = 200


if __name__ == '__main__':

    print(f'Running explore step...')

    sentences, ct = [], 0

    with torch.no_grad():
        while len(sentences) < TOTAL_SENTENCES:
            batch = sample(num_return_sequences=SAMPLE_BATCH)
            sentences.extend(batch)
            ct += 1
            if ct % 50 == 0:
                print(f'Batches: {ct}, Sentences: {len(sentences)} of {TOTAL_SENTENCES}')
                print(f'example: {sentences[-1]}')

    sentences = list(set(sentences))
    cluster_sample_and_save(sentences, num_clusters=NUM_CLUSTERS,
                            samples_per_cluster=SAMPLES_PER_CLUSTER,
                            savename=f'toxicity')

    print('Done :)')
