import json
import pandas as pd
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, f1_score
import matplotlib.pyplot as plt
import seaborn as sns
import argparse

def extract_entities_from_sample(sample):
    """
    Extracts a set of (product, quantity) tuples from a sample.
    Handles both the old schema and the new 'items' array schema.
    """
    entities = set()
    ent_dict = sample.get("entities", {})
    
    if "items" in ent_dict:
        # New schema
        for item in ent_dict["items"]:
            prod = item.get("product")
            qty = item.get("quantity")
            if prod:
                entities.add((str(prod).strip(), str(qty) if qty is not None else "1"))
    elif "products" in ent_dict:
        # Intermediate schema
        for prod in ent_dict["products"]:
            qty = ent_dict.get("quantity")
            entities.add((str(prod).strip(), str(qty) if qty is not None else "1"))
    elif "product" in ent_dict:
        # Old schema
        prod = ent_dict["product"]
        qty = ent_dict.get("quantity")
        if prod:
            # Handle comma separated old schema
            for p in str(prod).split(","):
                entities.add((p.strip(), str(qty) if qty is not None else "1"))
                
    return entities

def main(pred_file, gt_file):
    with open(gt_file, "r", encoding="utf-8") as f:
        gt_data = [json.loads(line) for line in f if line.strip()]
        
    with open(pred_file, "r", encoding="utf-8") as f:
        pred_data = [json.loads(line) for line in f if line.strip()]
        
    if len(gt_data) != len(pred_data):
        print(f"Warning: Number of predictions ({len(pred_data)}) does not match ground truth ({len(gt_data)}). Truncating to minimum.")
        min_len = min(len(gt_data), len(pred_data))
        gt_data = gt_data[:min_len]
        pred_data = pred_data[:min_len]

    # --- Intent Metrics ---
    y_true_intent = [s.get("intent", "unknown") for s in gt_data]
    y_pred_intent = [s.get("intent", "unknown") for s in pred_data]
    
    intent_acc = accuracy_score(y_true_intent, y_pred_intent)
    intent_macro_f1 = f1_score(y_true_intent, y_pred_intent, average="macro")
    
    labels = sorted(list(set(y_true_intent + y_pred_intent)))
    report_dict = classification_report(y_true_intent, y_pred_intent, labels=labels, zero_division=0, output_dict=True)
    report_df = pd.DataFrame(report_dict).transpose()
    report_df.to_csv("classification_report.csv")
    
    cm = confusion_matrix(y_true_intent, y_pred_intent, labels=labels)
    plt.figure(figsize=(10, 8))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=labels, yticklabels=labels)
    plt.ylabel('Actual Intent')
    plt.xlabel('Predicted Intent')
    plt.title('Intent Classification Confusion Matrix')
    plt.tight_layout()
    plt.savefig("confusion_matrix.png")
    
    # --- Entity Metrics ---
    tp = 0
    fp = 0
    fn = 0
    
    exact_matches = 0
    
    for gt_sample, pred_sample in zip(gt_data, pred_data):
        gt_ents = extract_entities_from_sample(gt_sample)
        pred_ents = extract_entities_from_sample(pred_sample)
        
        tp += len(gt_ents.intersection(pred_ents))
        fp += len(pred_ents - gt_ents)
        fn += len(gt_ents - pred_ents)
        
        intent_match = gt_sample.get("intent") == pred_sample.get("intent")
        entity_match = gt_ents == pred_ents
        
        if intent_match and entity_match:
            exact_matches += 1
            
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    end_to_end_acc = exact_matches / len(gt_data) if len(gt_data) > 0 else 0.0
    
    entity_metrics = {
        "intent_accuracy": intent_acc,
        "intent_macro_f1": intent_macro_f1,
        "entity_precision": precision,
        "entity_recall": recall,
        "entity_f1": f1,
        "end_to_end_accuracy": end_to_end_acc
    }
    
    with open("entity_metrics.json", "w", encoding="utf-8") as f:
        json.dump(entity_metrics, f, indent=4)
        
    print("Benchmarking Complete.")
    print(f"Intent Accuracy: {intent_acc:.4f}")
    print(f"Intent Macro F1: {intent_macro_f1:.4f}")
    print(f"Entity F1:       {f1:.4f}")
    print(f"End-to-End Acc:  {end_to_end_acc:.4f}")
    print("Artifacts saved: classification_report.csv, confusion_matrix.png, entity_metrics.json")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SLU Benchmark Script")
    parser.add_argument("predictions", help="Path to predictions.jsonl")
    parser.add_argument("ground_truth", help="Path to ground_truth.jsonl")
    args = parser.parse_args()
    main(args.predictions, args.ground_truth)
