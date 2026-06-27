# Báo Cáo Kỹ Thuật: Distillation & Tối Ưu Hóa Kiosk Edge CPU (Llama.cpp)

Tài liệu này trình bày luồng tư duy và quyết định kỹ thuật trong dự án Vietnamese Voice-Enabled Vending Machine: Từ việc phân tích đặc trưng dữ liệu (EDA), đánh giá các mô hình cơ sở, chưng cất tri thức (Knowledge Distillation), cho đến hành trình tối ưu hóa cực hạn để triển khai lên CPU Edge bằng GGUF/Llama.cpp.

---

## 1. Phân Tích Dữ Liệu (Theo Dataset Report)

Dựa trên báo cáo thăm dò dữ liệu (`dataset_report.md`), tập dữ liệu gốc có **1,961 mẫu** (Unified data gồm Gold, Pseudo-labels, Augmented). Các phân tích cốt lõi cho thấy:

### 1.1. Phân phối Intent và Entity
- **Sản phẩm (Product):** Phân phối khá đồng đều giữa 5 sản phẩm cốt lõi (7up, coca, aquafina, sting, pepsi).
- **Hard Reasoning:** Đã bổ sung các câu có ngữ pháp lắt léo ("thôi không lấy A nữa đổi sang B", "hủy cái đầu đi lấy cái thứ hai").

### 1.2. Thách Thức Từ ASR Noise
- Nhận diện giọng nói (STT) gây ra nhiễu từ vựng nghiêm trọng với các từ tiếng Anh. Ví dụ: `aqua fina`, `xtinh`, `seven up`, `bép si`, `cô ka`.
- Việc ép mô hình phải hiểu âm thanh tiếng Việt ("bép si") và ánh xạ về chuẩn tiếng Anh ("pepsi") là một thách thức sinh văn bản lớn.

---

## 2. Quyết Định Distillation

Dựa vào `benchmark_report.md`, bài toán yêu cầu **Joint Intent & Slot Filling** (Xuất trực tiếp cấu trúc JSON chứa cả Intent và Entity).

### 2.1. Tại sao chọn Knowledge Distillation (LLM)?
- **Teacher Model (Qwen2.5-7B-Instruct):** Đủ thông minh để hiểu ASR noise, tự trích xuất Entity chuẩn xác. Tuy nhiên, nó quá nặng, yêu cầu GPU VRAM cao, **không thể chạy trên CPU Kiosk của máy bán hàng**.
- **Giải pháp Distillation:** 
   - Dùng Teacher (7B) gán nhãn tự động (Pseudo-labeling) cho hàng trăm mẫu Unlabeled.
   - Huấn luyện một Student Model nhỏ hơn là **Qwen2.5-1.5B-Instruct**. 1.5B đủ nhỏ để chạy mượt trên CPU, nhưng nhờ được học từ Teacher, nó vẫn giữ được khả năng suy luận (reasoning) định dạng JSON.

---

## 3. Chưng Cất Tri Thức (Student Fine-Tuning)

Mô hình `Qwen2.5-1.5B-Instruct` được fine-tune với các cấu hình tối ưu để chạy trên phần cứng giới hạn (Google Colab T4):
- Sử dụng QLoRA để đóng băng Base model, chỉ huấn luyện lớp Adapter.
- Tắt bfloat16 (do T4 không hỗ trợ native) để tránh tràn bộ nhớ và crash hệ thống.
- **Kết quả bản PyTorch Gốc:** Đạt End-to-End Accuracy 92% (Normal) và 86% (Hard Test). Tuy nhiên, nếu chạy mô hình PyTorch (chưa Merge) này trên CPU, **độ trễ lên tới 20 giây/câu**, hoàn toàn không khả thi cho máy bán hàng thời gian thực.

---

## 4. Hành Trình Tối Ưu Hóa Cho Kiosk Edge (Llama.cpp & GGUF)

Để giảm độ trễ từ 20 giây xuống mức < 2 giây, toàn bộ Pipeline đã được di chuyển sang kiến trúc `llama.cpp` thông qua các bước khoa học nghiêm ngặt:

### 4.1. Merge Model & Vấn Đề Sai Số Kiểu Dữ Liệu (Merge Degradation)
Thay vì load song song Base + Adapter (gây chậm), hai lớp này phải được cộng gộp ($W = W_{base} + W_{lora}$).
- **Thất bại ban đầu:** Khi gộp bằng chuẩn `float32`, sự sai số làm tròn thập phân đã khiến E2E Accuracy trên tập Hard Test tụt thê thảm từ 86% xuống 68%.
- **Khắc phục:** Cấu trúc gộp được tinh chỉnh ép buộc sử dụng chuẩn `torch.float16` thuần khiết của mô hình nguyên bản. Mô hình sau đó được dịch sang định dạng `GGUF FP16` (Nặng 3.1GB) và khôi phục thành công 100% độ chính xác của bản gốc (Hard Test 86%).

### 4.2. Ép Xung Lượng Tử Hóa (Quantization) & Vấn đề Ảo Giác (Hallucination)
Mô hình FP16 3.1GB chạy trên CPU tốn khoảng 2.1 giây/câu. Để tối ưu hơn cho các Raspberry Pi/Mini PC tại Kiosk, mô hình tiếp tục được nén (Quantize):
- **Bản 4-bit (Q4_K_M - 940MB):** Tốc độ cực nhanh (0.9 giây/câu). Tuy nhiên, do bị nén quá thô bạo (từ 65536 giá trị xuống 16 giá trị), không gian Vector của các từ bị nhiễu ASR ("bép si") bị trượt. Mô hình sinh ra **ảo giác**, nhầm lẫn biến "bép si" thành "sting" trong các câu đổi hàng phức tạp.
- **Bản 8-bit (Q8_0 - 1.6GB):** Sự cân bằng hoàn hảo. Độ trễ 1.5 giây/câu (rất mượt mà cho trải nghiệm Kiosk). Độ phân giải 8-bit giữ vững kết nối toán học của từ "bép si", đạt điểm E2E **92%**, hoàn toàn triệt tiêu lỗi ảo giác của bản 4-bit.

---

## 5. Kết Luận Khuyến Nghị Triển Khai

Việc ứng dụng Knowledge Distillation (7B $\rightarrow$ 1.5B), kết hợp với C/C++ Engine của `llama.cpp` và nén GGUF 8-bit, đã giải quyết trọn vẹn bài toán máy bán hàng:
1. **Thông minh:** Xuất cấu trúc JSON chính xác, chống chịu mọi ASR Typos nhờ tập Augmented Data.
2. **Siêu nhẹ:** Model chỉ nặng 1.6GB, không đòi hỏi GPU đắt đỏ.
3. **Thực gian thực:** Phản hồi trên CPU trung bình chỉ **1.5 giây**.

**$\rightarrow$ Khuyến nghị Production:** Sử dụng tệp `student_1.5b_q8_0.gguf` triển khai chính thức trên thiết bị Edge bằng thư viện `llama-cpp-python`.
