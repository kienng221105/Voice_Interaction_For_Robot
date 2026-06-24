# Data Quality Assessment Report

## 1. Overview
This report evaluates the annotation quality and structural integrity of the `dataset_final.jsonl` and `dataset_150_bonus_v2.jsonl` files. Identifying and resolving these anomalies is crucial before model training.

## 2. Detected Issues

### 2.1. Duplicates
- **Issue:** Identical raw texts appearing multiple times in the dataset, which could skew the train/test splits if leaked.
- **Count:** 1 duplicate pair.
- **Example:** `"à thôi đổi sang coca lun"` appears at index 506 and 1041.

### 2.2. Missing Labels
- **Issue:** Samples lacking an `intent` and `entities` annotation.
- **Count:** 800 samples.
- **Note:** These correspond to the `"type": "unlabeled"` data partition. They represent a significant portion of the dataset (approx. 69.5%).

### 2.3. Invalid Entities
- **Issue:** Product entities that do not conform to the predefined base catalog (`coca`, `pepsi`, `sting`, `aquafina`, `7up`).
- **Count:** 36 samples.
- **Examples:** `"pepsi, 7up"`, `"sting, 7up"`, `"7up, aquafina"`.
- **Note:** The current annotation scheme concatenates multiple products into a single string. This violates standard entity extraction formats where multiple products should be represented as a list or multiple span entities.

### 2.4. Invalid Quantities
- **Issue:** Quantities that are negative, zero, non-integer, or implausibly high.
- **Count:** 0 samples.
- **Note:** All annotated quantities were valid integers greater than or equal to 1.

## 3. Recommended Corrective Actions

1. **Deduplication:** Remove exact text duplicates from the dataset or ensure they are strictly allocated to the same data split to prevent data leakage during evaluation.
2. **Entity Schema Revision:** The presence of comma-separated products (e.g., `"pepsi, 7up"`) indicates that users frequently request multiple items. The labeling schema must be updated to support arrays of entities (e.g., `[{"product": "pepsi", "quantity": 1}, {"product": "7up", "quantity": 1}]`) instead of flat key-value pairs.
3. **Pseudo-Labeling:** Initiate the Teacher-Student pipeline to annotate the 800 missing labels, drastically expanding the effective training set size.
4. **ASR Normalization:** Implement a pre-processing step or ensure the model is exposed to ASR aliases mapped correctly to their catalog ground truth (e.g., mapping `"xtinh"` to `"sting"`).
