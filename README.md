# Vietnamese Voice-Enabled Vending Machine Assistant

This repository contains the full end-to-end knowledge distillation pipeline for a Vietnamese voice assistant deployed on vending machines and kiosks.

## Goal
To train a lightweight CPU-deployable student LLM (`Qwen2.5-1.5B-Instruct`) capable of **Joint Intent Recognition and Entity Extraction (Slot Filling)** from spoken Vietnamese, handling complex colloquial speech, ASR noise, and multi-step reasoning.

## Task Output Format
The model takes raw Vietnamese speech (converted to text) and directly outputs a structured JSON response:
```json
{
  "intent": "buy_product",
  "items": [
    {
      "product": "coca",
      "quantity": 2
    }
  ]
}
```

## Pipeline Architecture
The pipeline is contained entirely within the `train_student.ipynb` Colab notebook and is divided into 8 automated phases:

1. **Dataset Preparation:** Parses raw text logs and ASR aliases into standardized intent and entity JSON structures.
2. **Teacher Labeling:** Uses `Qwen2.5-7B-Instruct` as a teacher to pseudo-label unlabeled data using zero-shot prompting.
3. **Training Data Generation:** Merges gold-annotated data and pseudo-labeled data into `train_distill.jsonl`.
4. **Student Fine-Tuning (QLoRA):** Fine-tunes the `Qwen2.5-1.5B-Instruct` student model using PEFT and 4-bit quantization on a single T4 GPU.
5. **Inference Constraints:** Enforces strict JSON decoding for deployment.
6. **Evaluation:** Measures Intent Accuracy, Macro F1, and strict End-to-End accuracy (exact match for intent, product, and quantities).
7. **Error Analysis:** Generates discrepancy logs for failing hard reasoning test cases (e.g. negation, payment after modification).
8. **CPU Benchmarking:** Simulates edge deployment by measuring latency and memory footprint on standard CPU infrastructure.

## How to Run

1. Open `train_student.ipynb` in Google Colab (Select T4 GPU runtime).
2. The very first cell will automatically:
   - Mount Google Drive
   - Clone this repository
   - Install all required pinned dependencies
3. Click "Run All". The notebook will execute the full pipeline from data prep through CPU benchmarking.
