# Phân Tích Dữ Liệu (EDA) - Unified Dataset

## 1. Tổng Quan Dataset
Tập dữ liệu hiện tại (`dataset_unified.jsonl`) là kết quả của việc gộp toàn bộ các tập dữ liệu thành phần (bao gồm tập gốc, tập hard test, và tập sinh tăng cường Augmentation).

- **Tổng số mẫu (Total Samples):** 1,960
- **Phân bổ theo Split:**
  - `test_normal`: 50 mẫu
  - `train_gold`: 150 mẫu
  - `train_augmented`: 810 mẫu
  - `test_hard`: 150 mẫu
  - `unlabeled`: 800 mẫu

## 2. Phân Tích Thống Kê Đặc Trưng

### 2.1 Phân Phối Intent (Ý định)
Thống kê các intent có trong tập dữ liệu (bao gồm cả các nhãn của tập augmented):
- **unknown**: 824 mẫu
- **buy_product**: 344 mẫu
- **payment**: 251 mẫu
- **add_product**: 146 mẫu
- **change_product**: 127 mẫu
- **cancel**: 117 mẫu
- **show_menu**: 79 mẫu
- **greeting**: 37 mẫu
- **help**: 35 mẫu

![Intent Distribution](intent_distribution_new.png)
*Nhận xét:* Dữ liệu đã được định hình lại với độ phủ rộng hơn cho các case hóc búa, không chỉ tập trung riêng vào `buy_product`.

### 2.2 Phân Phối Thực Thể (Entity: Product & Quantity)
Mô hình đã dùng Heuristic/Regex để bóc tách các sản phẩm xuất hiện trong text:
**Sản Phẩm:**
- **coca**: 352 lượt
- **pepsi**: 333 lượt
- **7up**: 276 lượt
- **aquafina**: 264 lượt
- **sting**: 261 lượt

![Product Distribution](product_distribution_new.png)

**Số Lượng (Quantity):**
Thường tập trung vào các số nhỏ (1, 2, 3), nhưng nhờ dữ liệu Augmented, mô hình học được cả các số lượng lớn hơn.
![Quantity Distribution](quantity_distribution_new.png)

### 2.3 Độ Dài Câu Lệnh (Utterance Length)
- **Trung bình:** {np.mean(text_lengths):.2f} từ
- **Ngắn nhất:** {np.min(text_lengths)} từ
- **Dài nhất:** {np.max(text_lengths)} từ

![Text Length Histogram](text_length_histogram_new.png)
*Nhận xét:* Độ dài câu phân bổ dạng chuông nghiêng lệch trái, phù hợp với cách nói chuyện ngắn gọn qua Voice Bot.

### 2.4 Thống Kê Nhiễu ASR (Automatic Speech Recognition)
Dữ liệu Augmented đã chủ động thêm vào rất nhiều nhiễu ASR để ép mô hình học cách ánh xạ về canonical. Dưới đây là tần suất xuất hiện của các cụm từ nhiễu:
- `aqua fina`: 33 lượt
- `bép si`: 31 lượt
- `cô ka`: 28 lượt
- `xtinh`: 25 lượt
- `pét si`: 23 lượt
- `a qua phi na`: 21 lượt
- `co ca`: 21 lượt
- `bảy áp`: 20 lượt
- `pep xi`: 20 lượt
- `cô ca`: 18 lượt
- `sê ven áp`: 16 lượt
- `coca cô la`: 16 lượt
- `pép xì`: 15 lượt
- `seven up`: 14 lượt
- `xì tin`: 11 lượt
- `se vừn ắp`: 8 lượt
- `ác qua`: 8 lượt
- `x ting`: 8 lượt


### 2.5 Đặc Trưng Ngôn Ngữ Giao Tiếp (Colloquialisms)
Tập dữ liệu chứa rất nhiều các tiền tố/hậu tố giao tiếp tự nhiên của người Việt Nam:
- `ạ`: 289 lượt
- `nha`: 277 lượt
- `với`: 205 lượt
- `cho anh`: 42 lượt
- `cho em`: 40 lượt
- `lấy dùm`: 36 lượt
- `cho mình`: 26 lượt
- `giùm em`: 16 lượt
- `giúp mình`: 13 lượt

---
## 3. Kết Luận
Tập dữ liệu `dataset_unified.jsonl` hiện tại có quy mô vượt trội (gần 2000 mẫu), sở hữu đầy đủ tính phức tạp của môi trường thực tế (Nhiễu ASR, câu phức, ngôn ngữ địa phương/giao tiếp). Đây là nền tảng cực kỳ vững chắc để tiến hành quá trình Knowledge Distillation từ Teacher LLM xuống Student LLM.
