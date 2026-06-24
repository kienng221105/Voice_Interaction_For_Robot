# Dataset Card: Vietnamese Vending Machine SLU

## Dataset Overview
The Vietnamese Vending Machine Spoken Language Understanding (SLU) dataset is designed for training edge-deployed virtual assistants in automated retail environments. It provides structural annotations (Intents and Entities) mapped from text queries that often contain complex phrasing and phonetical Speech-to-Text (ASR) noise. 

**Total Size:** 1,150 samples (350 Gold Labeled, 800 Unlabeled)  
**Language:** Vietnamese (vi)  
**Domain:** Retail, Vending Machine Transactions  

## Label Space

### Intents
The dataset classifies queries into 9 distinct intents:
1. `buy_product`: Core intent for purchasing.
2. `payment`: Queries regarding checkout methods (e.g., Momo, cash, bank transfer).
3. `change_product`: Modifying an existing cart.
4. `cancel`: Aborting a transaction.
5. `add_product`: Appending items to a cart.
6. `show_menu`: Asking what items are available.
7. `greeting`: Standard greetings.
8. `help`: Asking for instructions.
9. `unknown`: Out-of-domain or incomprehensible queries.

### Entities (Products Catalog)
Product entities are strictly resolved to a base catalog of 5 items:
- `coca`
- `pepsi`
- `sting`
- `aquafina`
- `7up`

## Data Characteristics

### ASR Aliases
Because the primary input modality is voice, the raw text heavily features Vietnamese ASR misspellings and phonetical approximations. Systems trained on this data must learn mappings such as:
- **aquafina** -> "aqua fina", "a qua phi na"
- **sting** -> "xtinh", "x ting", "xA tin"
- **pepsi** -> "pAct si", "pep xi", "bAcp si"

### Hard Test Cases
A dedicated partition of the dataset ("hard test") evaluates advanced semantic understanding. These samples include:
- **Multi-Product Transactions:** Single queries specifying multiple distinct products and quantities (e.g., "cho mình 2 sting và 1 coca").
- **Intent Negation & Cancellation:** Complex phrasing where the user changes their mind mid-sentence or explicitly cancels an action.

## Dataset Splits

To facilitate rigorous model benchmarking and semi-supervised distillation workflows, the dataset is partitioned as follows:

| Split | Count | Description |
|-------|-------|-------------|
| **Train** | 225 | High-quality gold labeled samples for core training. |
| **Validation**| 50 | High-quality gold samples for hyperparameter tuning. |
| **Unlabeled** | 800 | Raw text samples intended for Teacher-Student pseudo-labeling. |
| **Normal Test**| 25 | Clean, straightforward queries evaluating baseline intent/entity logic. |
| **ASR Test** | 25 | Queries heavily saturated with ASR distortions to evaluate robustness. |
| **Hard Test** | 25 | Multi-entity and complex intent queries to evaluate structural extraction. |

## Application and Benchmarking
This dataset is published with a benchmark suite evaluating Intent Accuracy, Macro F1, Entity F1, and End-to-End exact match accuracy, promoting the development of highly optimized, low-latency SLU models for physical hardware deployment.
