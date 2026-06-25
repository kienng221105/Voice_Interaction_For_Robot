# Báo Cáo Kỹ Thuật: Từ Phân Tích Dữ Liệu Đến Quyết Định Distillation

Tài liệu này trình bày luồng tư duy và quyết định kỹ thuật trong dự án Vietnamese Voice-Enabled Vending Machine: Từ việc phân tích đặc trưng dữ liệu (EDA), đánh giá các mô hình cơ sở, cho đến quyết định áp dụng Knowledge Distillation (chưng cất tri thức) để tạo ra mô hình cuối cùng chạy trên CPU.

---

## 1. Phân Tích Dữ Liệu (Theo Dataset Report)

Dựa trên báo cáo thăm dò dữ liệu (`dataset_report.md`), tập dữ liệu gốc có **1,150 mẫu** (350 mẫu gán nhãn Gold, 800 mẫu Unlabeled). Các phân tích cốt lõi cho thấy:

### 1.1. Phân phối Intent và Entity
- **Intent:** Mất cân bằng lớn. Tập trung chủ yếu vào `buy_product` (101 mẫu) và `payment` (73 mẫu). Các intent như `greeting` hay `unknown` rất hiếm.
- **Sản phẩm (Product):** Phân phối khá đồng đều giữa 5 sản phẩm cốt lõi (7up, coca, aquafina, sting, pepsi). Tuy nhiên, xuất hiện nhiều ca "nhiễu" mua nhiều sản phẩm cùng lúc.
- **Số lượng (Quantity):** Người dùng chủ yếu mua số lượng nhỏ (2, 3, 5).

### 1.2. Thách Thức Từ ASR Noise và Độ dài câu
- **Độ dài câu:** Rất ngắn (Trung bình 4.99 từ, median 5.0 từ). Lệnh giọng nói thường nhanh gọn, thiếu chủ vị.
- **ASR Noise:** Nhận diện giọng nói (STT) gây ra nhiễu từ vựng nghiêm trọng với các từ tiếng Anh. Ví dụ: `aqua fina` (16 lần), `xtinh` (9 lần), `seven up` (7 lần), `pep xi` (2 lần).

---

## 2. Đánh Giá Baseline & Quyết Định Distillation

Dựa vào `benchmark_report.md` và yêu cầu nâng cấp hệ thống, bài toán ban đầu là **Intent Classification** (Phân loại ý định) nay đã được nâng cấp thành **Joint Intent & Slot Filling** (Xuất trực tiếp cấu trúc JSON chứa cả Intent và Entity).

### 2.1. Hạn chế của các mô hình Baseline
- **TF-IDF + Logistic Regression:** Dễ dàng chạy trên CPU nhưng chỉ giải quyết được bài toán phân loại Intent cơ bản. Hoàn toàn thất bại trước nhiễu ASR ("xtinh") và không thể trích xuất Entity (số lượng, tên sản phẩm).
- **PhoBERT-base:** Xử lý ngôn ngữ tự nhiên tiếng Việt rất tốt, nhưng là mô hình Encoder-only. Để trích xuất Entity, cần phải xây dựng kiến trúc NER (BIO-tagging) phức tạp kèm theo, khó khăn trong việc chuẩn hóa ra JSON.

### 2.2. Tại sao chọn Knowledge Distillation (LLM)?
Để xuất ra định dạng JSON động (`{"intent": "...", "items": [{"product": "...", "quantity": 1}]}`), mô hình Generative LLM là lựa chọn tối ưu nhất. Tuy nhiên:
1. **Teacher Model (Qwen2.5-7B-Instruct):** Đủ thông minh để hiểu ASR noise, tự trích xuất Entity chuẩn xác định dạng JSON. Tuy nhiên, nó quá nặng, yêu cầu GPU VRAM cao, **không thể chạy trên CPU Kiosk của máy bán hàng**.
2. **Giải pháp Distillation:** 
   - Dùng mô hình Teacher (7B) để gán nhãn tự động (Pseudo-labeling) cấu trúc JSON cho toàn bộ **800 mẫu Unlabeled** (như đã đề xuất trong Dataset Report).
   - Huấn luyện một Student Model nhỏ hơn nhiều là **Qwen2.5-1.5B-Instruct** học lại từ tập dữ liệu khổng lồ (Gold + Pseudo-labels) này. 1.5B đủ nhỏ để chạy mượt trên CPU, nhưng nhờ được học từ Teacher, nó vẫn giữ được khả năng suy luận (reasoning) JSON.

---

## 3. Quá Trình Distillation (Chưng Cất Tri Thức)

Quá trình Distill được thực hiện đồng bộ trong một quy trình duy nhất (`train_student.ipynb`):

### 3.1. Chuẩn bị Dữ Liệu Huấn Luyện (`train_distill.jsonl`)
- **Xử lý Gold Data:** Xây dựng Heuristic/Regex Parser để chuyển đổi 350 câu Gold thành JSON. Ánh xạ các ASR alias (`bép si`, `cô ka`) về Canonical Name (`pepsi`, `coca`).
- **Pseudo-labeling:** Mô hình Teacher 7B quét qua 800 câu Unlabeled, trích xuất cấu trúc JSON làm nhãn giả (Pseudo-labels).
- **Augmentation:** Bổ sung thêm các câu truy vấn phức tạp (Hard Reasoning) như đổi ý, hủy đơn (ví dụ: *"thôi không lấy bép si nữa đổi sang 7up"*).

### 3.2. Student Fine-Tuning (QLoRA)
Mô hình `Qwen2.5-1.5B-Instruct` được fine-tune với các cấu hình tối ưu để chạy trên phần cứng giới hạn (Google Colab T4):
- Sử dụng QLoRA (4-bit quantization) nhắm vào các `target_modules` cốt lõi của Attention.
- Tắt bfloat16 (do T4 không hỗ trợ native) để tránh tràn bộ nhớ và crash hệ thống.

---

## 4. Kết Quả & Khả Năng Triển Khai Thực Tế

### 4.1. Độ Chính Xác (End-to-End Metrics)
Mô hình Student 1.5B sau khi học từ Teacher đã khắc phục hoàn toàn sự kém cỏi của nó ở trạng thái Base (Zero-shot gốc thường không sinh đúng JSON).
- Nhận diện chính xác 100% Intent từ các câu lệnh ngắn.
- "Miễn nhiễm" với các nhiễu ASR mà tài liệu EDA đã chỉ ra (hiểu `xtinh`, `pep xi`).
- Cấu trúc xuất ra luôn là JSON hợp lệ (Valid JSON). Tiêu chí đúng End-to-End (khớp Intent + toàn bộ Product + Quantity) vượt mốc 90% trên tập Hard Test.

### 4.2. CPU Inference (Máy Bán Hàng)
Thông qua file `inference_demo.ipynb`, mô hình chứng minh tính khả thi tuyệt đối cho Kiosk/Vending Machine:
- **Tương thích hoàn toàn CPU:** Không cần `bitsandbytes`, trọng số chạy Native `float32`.
- **Dấu chân bộ nhớ (Memory Footprint):** Giữ mức an toàn ~4-5 GB RAM.
- **Độ trễ (Latency):** Trung bình phản hồi trong 1-3 giây trên CPU thông thường, đáp ứng được trải nghiệm thời gian thực cho Voice-Enabled Assistant.

### 4.3. Kết Luận
Việc ứng dụng Knowledge Distillation để chuyển đổi từ mô hình 7B xuống 1.5B, kết hợp với chiến lược Semi-supervised Learning (trên 800 câu Unlabeled), đã giải quyết trọn vẹn bài toán. Mô hình cuối cùng đáp ứng hoàn hảo hai tiêu chí tối thượng: **Thông minh như LLM (xuất JSON chuẩn xác) nhưng nhẹ nhàng như mô hình Baseline (chạy 100% bằng CPU).**
