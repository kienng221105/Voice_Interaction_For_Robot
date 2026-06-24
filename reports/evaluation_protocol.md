# Vending Machine SLU Evaluation Protocol

This protocol defines the rigorous evaluation criteria for benchmarking the performance of Spoken Language Understanding (SLU) models on the Vietnamese Vending Machine dataset.

## 1. Intent Metrics
Evaluating the model's ability to correctly classify the user's core intent.

- **Intent Accuracy:** The ratio of correctly predicted intents to the total number of queries. This provides a high-level view of classification performance.
- **Macro F1 Score:** The unweighted mean of the F1 scores calculated for each individual intent class. This metric is crucial because it treats all classes equally, penalizing models that perform poorly on minority intents (e.g., `greeting`, `help`) despite high overall accuracy on majority intents (e.g., `buy_product`).

## 2. Entity Metrics
Evaluating the model's ability to extract specific constraints, primarily the exact catalog products and their corresponding quantities.

- **Entity Precision:** The ratio of correctly extracted entities to the total number of entities predicted by the model. High precision means fewer false positives (hallucinations).
- **Entity Recall:** The ratio of correctly extracted entities to the total number of actual entities in the ground truth. High recall means fewer false negatives (missed extractions).
- **Entity F1 Score:** The harmonic mean of Entity Precision and Entity Recall, providing a balanced measure of the model's extraction capabilities.

*Note: For the vending machine domain, an entity prediction is considered strictly correct only if the exact product string (mapped to the internal catalog) and its quantity are identified correctly.*

## 3. System-Level Metrics
Evaluating the holistic performance of the pipeline.

- **End-to-End Accuracy:** Also known as Exact Match (EM) accuracy. A sample is considered correct if and only if **both** the predicted intent perfectly matches the ground truth intent, **and** the set of predicted entities perfectly matches the ground truth set of entities. This is the most stringent metric and best represents the actual user experience (e.g., dispensing the right product).
