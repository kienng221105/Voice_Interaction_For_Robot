import json
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import collections

# Load data
files = ["dataset_final.jsonl", "dataset_150_bonus_v2.jsonl"]
data = []
for f in files:
    with open(f, "r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                data.append(json.loads(line))

intents = []
products = []
quantities = []
text_lengths = []
asr_matches = []

asr_mapping = {
    "cA' ca": "coca",
    "cA' ka": "coca",
    "coca cA' la": "coca",
    "pAct si": "pepsi",
    "pep xi": "pepsi",
    "bAcp si": "pepsi",
    "xtinh": "sting",
    "x ting": "sting",
    "xA tin": "sting",
    "aqua fina": "aquafina",
    "a qua phi na": "aquafina",
    "seven up": "7up",
    "sA ven Ap": "7up",
    "se vn _p": "7up",
    "by Ap": "7up"
}

catalog = ["coca", "pepsi", "sting", "aquafina", "7up"]

duplicates = collections.defaultdict(list)
missing_labels = []
invalid_entities = []
invalid_quantities = []

for i, row in enumerate(data):
    text = row.get("text", "")
    intent = row.get("intent")
    entities = row.get("entities", {})
    
    # Distributions
    intents.append(intent if intent else "missing")
    
    prod = entities.get("product")
    if prod:
        products.append(prod)
    
    qty = entities.get("quantity")
    if qty is not None:
        quantities.append(qty)
        
    text_lengths.append(len(text.split()))
    
    for alias in asr_mapping:
        if alias in text:
            asr_matches.append(alias)
            
    # Detect issues
    duplicates[text].append(i)
    
    if not intent:
        missing_labels.append(i)
        
    if prod and prod not in catalog:
        invalid_entities.append((i, prod))
        
    if qty is not None:
        try:
            qty_int = int(qty)
            if qty_int < 1:
                invalid_quantities.append((i, qty))
        except:
            invalid_quantities.append((i, qty))

# Visualizations
plt.figure(figsize=(10, 6))
sns.countplot(y=intents, order=[k for k, v in collections.Counter(intents).most_common()])
plt.title("Intent Distribution")
plt.tight_layout()
plt.savefig("intent_distribution.png")

plt.figure(figsize=(10, 6))
sns.countplot(y=products, order=[k for k, v in collections.Counter(products).most_common()])
plt.title("Product Distribution")
plt.tight_layout()
plt.savefig("product_distribution.png")

plt.figure(figsize=(10, 6))
sns.countplot(x=quantities, order=sorted(list(set(quantities))))
plt.title("Quantity Distribution")
plt.tight_layout()
plt.savefig("quantity_distribution.png")

plt.figure(figsize=(10, 6))
sns.histplot(text_lengths, bins=range(1, max(text_lengths)+2), discrete=True)
plt.title("Text Length Histogram (Words)")
plt.tight_layout()
plt.savefig("text_length_histogram.png")

# Gather Stats
stats = {
    "total_samples": len(data),
    "intent_counts": dict(collections.Counter(intents)),
    "product_counts": dict(collections.Counter(products)),
    "quantity_counts": dict(collections.Counter(quantities)),
    "text_length": {
        "min": min(text_lengths),
        "max": max(text_lengths),
        "mean": float(np.mean(text_lengths)),
        "median": float(np.median(text_lengths))
    },
    "asr_alias_counts": dict(collections.Counter(asr_matches)),
    "issue_counts": {
        "duplicates": sum(len(idxs) - 1 for text, idxs in duplicates.items() if len(idxs) > 1),
        "missing_labels": len(missing_labels),
        "invalid_entities": len(invalid_entities),
        "invalid_quantities": len(invalid_quantities)
    },
    "duplicates_example": {k: v for k, v in list(duplicates.items())[:5] if len(v) > 1},
    "missing_labels_example": missing_labels[:5],
    "invalid_entities_example": invalid_entities[:5],
    "invalid_quantities_example": invalid_quantities[:5]
}

with open("eda_results.json", "w", encoding="utf-8") as f:
    json.dump(stats, f, indent=4, ensure_ascii=False)
