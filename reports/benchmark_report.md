# Intent Classification Benchmark Report

## 1. Objective
Compare traditional NLP models (TF-IDF + Logistic Regression) against Pre-trained Language Models (PhoBERT) and Distilled LLMs on Vietnamese Vending Machine intent classification.

## 2. Dataset Configuration
- **Total Gold Samples**: 350
- **Split**: 80% Train, 10% Validation, 10% Test
- **Splitting Strategy**: Stratified by intent to handle class imbalances, ensuring rare classes like `greeting` or `help` are distributed evenly across splits.

## 3. Baseline Models

### A. TF-IDF + Logistic Regression
A lightweight, traditional NLP approach utilizing n-gram lexical features.
- **Accuracy:** [TO BE FILLED]
- **Macro F1:** [TO BE FILLED]
- **Precision:** [TO BE FILLED]
- **Recall:** [TO BE FILLED]

### B. PhoBERT-base
A transformer-based model pre-trained natively on Vietnamese text, fine-tuned for sequence classification.
- **Accuracy:** [TO BE FILLED]
- **Macro F1:** [TO BE FILLED]
- **Precision:** [TO BE FILLED]
- **Recall:** [TO BE FILLED]

## 4. Distilled LLM (Future Target)
- **Model:** Knowledge Distilled Student Model from Large Language Model (e.g. Gemini/GPT-4).
- **Accuracy:** [TO BE FILLED]
- **Macro F1:** [TO BE FILLED]

## 5. Confusion Matrix Analysis
*(Insert observations from `tf_idf_logistic_regression_cm.png` and `phobert_cm.png` here)*
- **Observations:** [TO BE FILLED] (e.g., Which intents are frequently confused? Does PhoBERT resolve ASR noise better than TF-IDF?)

## 6. Conclusion
[TO BE FILLED]
