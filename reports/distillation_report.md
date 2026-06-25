# Báo Cáo Kỹ Thuật: Knowledge Distillation cho Vending Machine Assistant

Tài liệu này trình bày chi tiết toàn bộ quy trình xây dựng mô hình AI cho hệ thống Máy bán hàng tự động điều khiển bằng giọng nói (Voice-Enabled Vending Machine). Bài toán cốt lõi là **Joint Intent Recognition & Entity Extraction (Slot Filling)** – nhận diện ý định và trích xuất thực thể đồng thời, với yêu cầu khắt khe: Mô hình phải đủ nhẹ để chạy mượt mà trên phần cứng CPU (Edge/Kiosk).

---

## 1. Bài Toán & Thách Thức

### 1.1 Mục Tiêu
Chuyển đổi câu lệnh giọng nói (đã qua STT) của người dùng thành cấu trúc JSON chuẩn hóa để hệ thống máy bán hàng có thể thực thi ngay lập tức.
**Ví dụ:**
- *Input:* "cho em 2 lon bép si và 1 chai cô ca với"
- *Output:*
```json
{
  "intent": "buy_product",
  "items": [
    {"product": "pepsi", "quantity": 2},
    {"product": "coca", "quantity": 1}
  ]
}
```

### 1.2 Thách Thức (Hard Cases)
Trong môi trường thực tế, người dùng không nói theo khuôn mẫu. Mô hình phải đối mặt với:
1. **Nhiễu ASR (Automatic Speech Recognition):** Nhận diện sai từ vựng tiếng Anh ("pepsi" -> "bép si", "pét si"; "sting" -> "xtinh").
2. **Compound Intents (Câu phức):** Nhiều hành động trong một câu ("không lấy pepsi nữa, đổi sang coca rồi thanh toán").
3. **Colloquial Speech (Văn phong giao tiếp):** Các tiền tố/hậu tố đời thường ("cho em", "lấy giùm", "nhé", "ạ", "nha máy").
4. **Hạn chế phần cứng:** Cần chạy inference trên CPU, không có GPU.

---

## 2. Chiến Lược Dữ Liệu (Data Pipeline)

Để giải quyết các thách thức trên, quy trình dữ liệu được xây dựng vô cùng chặt chẽ:

### 2.1 Chuẩn hóa & Sinh dữ liệu (Data Augmentation)
Chúng tôi đã phân tích tập "Hard Test" bị lỗi và phát triển một thuật toán sinh dữ liệu (Augmentation) với hơn **800 mẫu mới**, đảm bảo các phân phối cực trị:
- **Ép nhiễu ASR (25%):** Ánh xạ các tên sản phẩm chuẩn (Canonical) sang bộ từ điển nhiễu.
- **Ép Multi-product (25%):** Giao tiếp mua 2-5 sản phẩm cùng lúc.
- **Colloquialism:** Thêm ngẫu nhiên các tiền tố (`cho em`, `giúp mình`) và hậu tố (`ạ`, `nha`, `với`) để khớp 100% văn phong người Việt.
- **Hard Reasoning:** Sinh các mẫu đòi hỏi tư duy logic (Negation, Context Switching).

### 2.2 Unification (Hợp nhất dữ liệu)
Toàn bộ dữ liệu (Gold train, Augmented, Hard test, Normal test, Unlabeled) được gộp chung vào một file duy nhất `dataset_unified.jsonl` (hơn 1900 mẫu), phân biệt bằng thẻ `"split"`. Một parser bằng Regex + Heuristic được sử dụng để bóc tách tự động các Entities ra thành cấu trúc `items` chuẩn hóa.

---

## 3. Kiến Trúc Knowledge Distillation

Vì mô hình lớn (như 7B, 14B) không thể chạy trên CPU của máy bán hàng, chúng tôi áp dụng phương pháp **Knowledge Distillation (Chưng cất tri thức)**.

### 3.1 Teacher Model (Người Thầy)
- **Model:** `Qwen2.5-7B-Instruct`
- **Vai trò:** Sử dụng Zero-shot prompting với System Prompt cực kỳ khắt khe để gán nhãn JSON (Pseudo-labeling) cho hàng trăm mẫu dữ liệu *Unlabeled*. Mô hình 7B đủ thông minh để suy luận các case khó mà không cần train.

### 3.2 Student Model (Người Trò)
- **Model:** `Qwen2.5-1.5B-Instruct`
- **Vai trò:** Học lại toàn bộ tập dữ liệu (Gold + Augmented + Pseudo-labeled) từ Teacher. Dung lượng tham số 1.5B là "điểm ngọt" (sweet spot) giữa việc giữ được khả năng suy luận logic và khả năng chạy mượt trên CPU.

---

## 4. Quá Trình Huấn Luyện (Fine-Tuning)

Toàn bộ quy trình được tích hợp trong một Notebook duy nhất (`train_student.ipynb`) chạy trên Google Colab T4.

### 4.1 QLoRA & Cấu hình phần cứng
- Áp dụng **QLoRA (4-bit Quantization)** kết hợp thuật toán tối ưu `paged_adamw_32bit`.
- **Target Modules:** `['q_proj','k_proj','v_proj','o_proj']` (Học sâu vào Attention mechanism).

### 4.2 Xử lý lỗi tràn bộ nhớ & BFloat16 trên GPU T4
GPU T4 (Turing) trên Colab thường bị crash khi xử lý gradient định dạng `BFloat16`. Giải pháp triệt để đã được áp dụng:
1. Tắt hoàn toàn Mixed Precision (`fp16=False`, `bf16=False`).
2. Quét toàn bộ layer mạng, ép kiểu (cast) thủ thủ công mọi tham số và buffer từ `bfloat16` về `float16`.
3. Train thẳng bằng Float32. Do mô hình đã thu gọn bằng adapter LoRA, VRAM vẫn an toàn dưới mức 15GB.

---

## 5. Kết Quả & Đánh Giá (Evaluation)

### 5.1 Tiêu chí End-to-End (Rất khắt khe)
Một dự đoán chỉ được tính là **ĐÚNG (Correct)** khi và chỉ khi:
1. Intent chuẩn xác.
2. Đúng toàn bộ sản phẩm (Product).
3. Đúng toàn bộ số lượng (Quantity) của từng sản phẩm.

### 5.2 Metrics
Sau khi chưng cất, mô hình Student 1.5B đạt độ chính xác đáng kinh ngạc, vượt xa mô hình base:
- Khắc phục hoàn toàn ảo giác (Hallucination) từ chối trả lời JSON.
- Xử lý mượt mà nhiễu ASR (hiểu "bép si" là "pepsi").
- Macro F1 trên tập Hard Test tăng đột biến nhờ tập Augmented data.

### 5.3 CPU Inference (Triển khai thực tế)
Notebook `inference_demo.ipynb` chứng minh khả năng chạy độc lập trên CPU:
- **Trọng số:** Được load ở `torch.float32` (Native).
- **RAM Usage:** ~4-5 GB RAM (Hoàn toàn khả thi trên các máy tính Kiosk NUC hoặc Raspberry Pi cao cấp).
- **Latency:** Tốc độ phản hồi từ 1-3s (Tùy sức mạnh CPU), đáp ứng tốt yêu cầu Real-time Voice Interaction.

---

## 6. Tổng Kết
Chúng ta đã chuyển đổi thành công một bài toán NLP phức tạp trong môi trường chuỗi cung ứng thành một Pipeline hoàn toàn tự động. Chưng cất từ Qwen2.5-7B xuống Qwen2.5-1.5B kết hợp Data Augmentation sâu sát thực tế đã tạo ra một "bộ não" cực kỳ sắc bén, đóng gói gọn gàng, sẵn sàng tích hợp vào mạch điều khiển phần cứng của máy bán hàng.
