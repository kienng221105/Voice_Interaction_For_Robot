import json
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns

def load_predictions(true_file, pred_file):
    with open(true_file, "r", encoding="utf-8") as f1, open(pred_file, "r", encoding="utf-8") as f2:
        y_true = [json.loads(line)["intent"] for line in f1 if line.strip()]
        y_pred = [json.loads(line)["intent"] for line in f2 if line.strip()]
    return y_true, y_pred

def evaluate(y_true, y_pred, output_prefix="intent"):
    labels = sorted(list(set(y_true + y_pred)))
    
    # Classification Report
    report = classification_report(y_true, y_pred, labels=labels, zero_division=0)
    print("Classification Report:")
    print(report)
    with open(f"{output_prefix}_classification_report.txt", "w") as f:
        f.write(report)
        
    # Confusion Matrix
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    plt.figure(figsize=(10, 8))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=labels, yticklabels=labels)
    plt.ylabel('Actual')
    plt.xlabel('Predicted')
    plt.title('Intent Confusion Matrix')
    plt.tight_layout()
    plt.savefig(f"{output_prefix}_confusion_matrix.png")
    print(f"Saved {output_prefix}_confusion_matrix.png")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python evaluate_intent.py <true_jsonl> <pred_jsonl>")
        # Example dummy data if no files provided
        print("Running with dummy data template...")
        y_true = ["buy_product", "cancel", "payment", "buy_product"]
        y_pred = ["buy_product", "change_product", "payment", "buy_product"]
        evaluate(y_true, y_pred, "intent_template")
    else:
        y_true, y_pred = load_predictions(sys.argv[1], sys.argv[2])
        evaluate(y_true, y_pred, "intent")
