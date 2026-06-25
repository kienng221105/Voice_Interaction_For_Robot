# Giao Thức Đánh Giá Mô Hình SLU (Evaluation Protocol)

Tài liệu này định nghĩa các công thức toán học và logic thuật toán khắt khe nhất được sử dụng trong giai đoạn Evaluation (Phase 6) của mô hình Student `Qwen2.5-1.5B-Instruct` cho dự án Vending Machine.

Toàn bộ các phép đo này tập trung vào 2 phần: **Phân loại Intent** và **Trích xuất Entity (Items)** dưới định dạng JSON.

---

## 1. Đánh Giá Intent (Ý Định)

Vì bài toán có nhiều lớp (Multi-class classification) với 9 intents khác nhau (`buy_product`, `payment`, `cancel`, `change_product`, v.v.), chúng ta sử dụng Accuracy và Macro F1-Score.

### 1.1 Intent Accuracy (Độ chính xác tổng thể)
Công thức cơ bản nhất đo lường tỷ lệ đoán đúng Intent trên tổng số câu.
**Công thức:**
$$ Accuracy = \frac{TP + TN}{TP + TN + FP + FN} = \frac{\sum_{i=1}^{N} I(\hat{y}_i = y_i)}{N} $$
Trong đó:
- $N$: Tổng số mẫu test.
- $y_i$: Intent thực tế (Ground Truth) của mẫu $i$.
- $\hat{y}_i$: Intent do mô hình dự đoán.
- Hàm chỉ thị $I(x) = 1$ nếu đúng, $0$ nếu sai.

### 1.2 Intent Macro F1-Score
Bởi vì dữ liệu bị mất cân bằng trầm trọng (Ví dụ: 101 mẫu `buy_product` nhưng chỉ có 10 mẫu `unknown`), Accuracy thường bị sai lệch. Do đó, **Macro F1** được tính toán để đảm bảo mô hình không dự đoán thiên vị.
**Công thức tính cho lớp $c$:**
$$ Precision_c = \frac{TP_c}{TP_c + FP_c} $$
$$ Recall_c = \frac{TP_c}{TP_c + FN_c} $$
$$ F1_c = 2 \times \frac{Precision_c \times Recall_c}{Precision_c + Recall_c} $$
**Macro F1:** (Trung bình cộng F1 của tất cả các lớp)
$$ Macro\_F1 = \frac{1}{C} \sum_{c=1}^{C} F1_c $$
Trong đó $C = 9$ là tổng số intents. Công thức này phạt rất nặng nếu mô hình đoán sai các intent hiếm (như `greeting`, `help`).

---

## 2. Trích Xuất Entity (Slot Filling Matching Logic)

Trong dự án này, mô hình phải trả về một mảng `items` định dạng JSON. Việc đánh giá phần này không dựa trên token-level thông thường mà dựa trên **Đối sánh Cấu trúc Dữ liệu (Exact Data Match)**.

### 2.1 Cấu trúc đầu ra
Mỗi Entity chuẩn bao gồm:
```json
{
  "product": "coca",
  "quantity": 2
}
```

### 2.2 Thuật toán `match_items` (Strict Matching)
Hàm `match_items(pred_items, true_items)` trong Code đánh giá (Phase 6) hoạt động theo các nguyên tắc cực kỳ nghiêm ngặt:

1. **Kiểm tra độ dài:** Kích thước mảng dự đoán phải khớp chính xác với ground truth. (Ví dụ: Sự thật có 2 sản phẩm, đoán 3 sản phẩm -> **SAI**).
2. **Sắp xếp thứ tự (Sorting):** Mảng được sort theo Alphabet của `product` để triệt tiêu độ lệch thứ tự (Ví dụ: `[coca, pepsi]` và `[pepsi, coca]` được coi là bằng nhau).
3. **So khớp phần tử (Element-wise Check):** Duyệt qua từng object, đối chiếu 2 trường:
   - `pred['product'] == true['product']` (Chỉ chấp nhận Canonical Name chuẩn hóa).
   - `pred['quantity'] == true['quantity']` (Chỉ cần sai lệch 1 số lượng -> **SAI**).

Chỉ khi vượt qua 100% 3 vòng kiểm tra trên, mảng Items mới được tính là `items_match = True`.

---

## 3. End-to-End Accuracy (Thước Đo Tối Thượng)

Đây là thước đo quan trọng nhất quyết định khả năng deploy của mô hình vào Kiosk máy bán hàng tự động thực tế.

**Logic đánh giá:** Máy bán hàng chỉ nhả đúng món khi và chỉ khi nó hiểu đúng MỤC ĐÍCH (Intent), LẤY ĐÚNG MÓN (Product), và ĐÚNG SỐ LƯỢNG (Quantity) CÙNG MỘT LÚC.

**Định nghĩa một ca đoán ĐÚNG:**
$$ E2E\_Correct_i = (Intent\_Match_i \text{ IS TRUE}) \land (Items\_Match_i \text{ IS TRUE}) $$

**Công thức E2E Accuracy:**
$$ End\_to\_End\_Accuracy = \frac{\sum_{i=1}^{N} E2E\_Correct_i}{N} \times 100\% $$

- Nếu Intent đoán đúng là `buy_product`, đoán đúng cả sản phẩm `coca` nhưng sai số lượng (Đoán 2 thay vì 3) -> Điểm câu này = 0.
- Sự khắt khe của công thức này phản ánh chính xác rủi ro khi mô hình sai phạm trong quá trình vận hành kinh doanh (tránh việc bán thiếu/thừa hoặc sai đồ cho khách hàng).
