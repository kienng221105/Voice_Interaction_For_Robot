# Voice-enabled Vending Machine Assistant: Intent Recognition via LLM Distillation

This repository contains the pipeline for distilling a large Large Language Model (Qwen2.5-7B-Instruct) into a lightweight, edge-deployable model (Qwen2.5-0.5B-Instruct) for **Intent Recognition** in the Vending Machine domain.

## 1. Dataset Overview

*   **Gold Samples:** 200 manually labeled samples from real usage.
*   **Bonus Hard Test:** 150 hard samples featuring complex phrasing, ASR noise (e.g., "xtinh" -> "sting"), multi-intents, and cancellation scenarios.
*   **Unlabeled Samples:** 800 raw text samples derived from voice input without intent labels.
*   **Ontology:** `greeting`, `show_menu`, `buy_product`, `add_product`, `change_product`, `payment`, `cancel`, `help`, `unknown`.

## 2. Pipeline Execution

The pipeline is organized into distinct phases designed to run seamlessly on a Google Colab instance with a T4 GPU (and CPU for edge benchmarking).

### Phase 1: Dataset Preparation

Run the following command to format all datasets into a standard schema `{"text": "...", "label": "..."}`:
```bash
python prepare_dataset.py
```
This extracts and partitions the datasets into `train_gold`, `normal_test`, `hard_test`, and `unlabeled` inside the `data/qwen_distill/` folder.

### Phase 2 & 3: Teacher Pseudo-Labeling

To generate labels for the 800 unlabeled samples, run:
```bash
python teacher_label.py
```
This script loads the **Teacher Model (Qwen2.5-7B-Instruct)** in 4-bit quantization and automatically assigns pseudo-labels. It merges the gold training set with the pseudo-labels to generate `train_distill.jsonl` (the final dataset for the student).

### Phase 4: Student Fine-Tuning (Distillation)

Train the **Student Model (Qwen2.5-0.5B-Instruct)** via QLoRA:
```bash
python train_student.py
```
This script leverages PEFT (LoRA) and BitsAndBytes for efficient fine-tuning on a single T4 GPU. The resulting adapter weights are saved to `./student_qwen_adapter`.

### Phase 5 & 6: Evaluation & Benchmarking

Evaluate and compare the models on both the `normal_test` and `hard_test` sets to calculate Accuracy, Macro F1, and Per-Intent F1:

Evaluate Teacher:
```bash
python evaluate.py --model_type teacher
```

Evaluate Student:
```bash
python evaluate.py --model_type student
```

### Phase 7: CPU Edge Inference Benchmark

To validate the real-world deployment viability of the Student model on kiosk hardware (CPU only), run the benchmark script:
```bash
python benchmark_cpu.py
```
This tool measures:
1.  **Load time**
2.  **Memory Usage (RSS/RAM)**
3.  **Inference Latency (seconds/query)**

*Note: The script safely tests the 0.5B model by default. Loading the 7B model in pure float32 requires ~28GB RAM and may cause Out-Of-Memory (OOM) errors on standard hardware.*
