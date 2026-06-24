# Vending Machine SLU Dataset Benchmark

This repository contains the prepared datasets and evaluation scripts for the Vietnamese Vending Machine Spoken Language Understanding (SLU) benchmark. The objective is to map noisy speech-to-text queries (STT) into structural intents and entities.

## 1. Dataset Splits

The dataset has been meticulously partitioned to evaluate different aspects of model robustness:

- `train.jsonl` (225 samples): The core gold-standard training data.
- `val.jsonl` (50 samples): Data reserved for hyperparameter tuning and early stopping.
- `unlabeled.jsonl` (800 samples): Large pool of raw, unannotated queries intended for semi-supervised learning.
- `normal_test.jsonl` (25 samples): Clean queries without ASR noise or complex intent logic. Evaluates baseline performance.
- `asr_noise_test.jsonl` (25 samples): Queries containing common ASR misspellings (e.g., "xtinh", "aqua fina"). Evaluates robustness to speech transcription errors.
- `hard_test.jsonl` (25 samples): Queries with multiple products, complex constraints, or cancellation intents. Evaluates the model's structural comprehension.

*Note: All multi-product entities have been migrated from a single string format (`"product": "coca, pepsi"`) to a list format (`"products": ["coca", "pepsi"]`).*

## 2. Evaluation Scripts

To benchmark models, use the provided Python scripts. Both scripts load predictions and ground truth to generate standard Classification Reports and Confusion Matrices.

- `evaluate_intent.py`: Computes accuracy and F1 scores for intent classification.
  `python evaluate_intent.py <true_jsonl> <pred_jsonl>`
  
- `evaluate_entity.py`: Computes precision, recall, and F1 scores for product extraction.
  `python evaluate_entity.py <true_jsonl> <pred_jsonl>`

## 3. Teacher-Student Distillation Workflow

To leverage the 800 unlabeled queries, we propose a Knowledge Distillation pipeline:

### Step 1: Teacher Pseudo-Labeling
1. Provide a powerful Teacher LLM (e.g., GPT-4 or Gemini) with the instructions in `teacher_prompt.txt`.
2. Run `teacher_label.py` to iterate over `unlabeled.jsonl` and generate `pseudo_labeled.jsonl`.
3. Filter out low-confidence predictions from the pseudo-labeled dataset.

### Step 2: Student Distillation
1. Combine `train.jsonl` with the high-confidence samples from `pseudo_labeled.jsonl`.
2. Train a lightweight Student model (e.g., JointBERT, fastText, or a small bi-encoder) on this augmented dataset.
3. The Student model will inherit the structural understanding and ASR-robustness of the Teacher while maintaining a low inference latency suitable for edge deployment on vending machines.

### Step 3: Benchmarking
Evaluate the distilled Student model against the three test splits (`normal`, `asr_noise`, `hard`) to quantify the impact of the pseudo-labeled distillation strategy.
