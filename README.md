# Voice Vending Machine - Local Edge Demo (Giai đoạn 5)

Dự án này là hệ thống Trợ lý Giọng nói cho Máy Bán hàng tự động (Voice Vending Machine) được thiết kế tối ưu hóa để chạy một phần trên Local Edge Computing và tích hợp thanh toán tự động qua VietQR (payOS).

Hệ thống bao gồm:
- **STT (Speech-to-Text)**: Sử dụng API Groq Whisper để nhận dạng giọng nói siêu tốc. Có bộ lọc chống ảo giác mạnh mẽ.
- **NLP (Natural Language Processing)**: Chạy hoàn toàn dưới Local bằng phần mềm Ollama với mô hình đã được Fine-tune chuyên biệt (`vending-student` 1.5B) cho độ chính xác cao và độ trễ cực thấp (< 3.5s).
- **Web UI & Business Logic**: Giao diện Kiosk hiển thị trực quan và Server điều phối xử lý bán hàng (Cart, Inventory, Thanh toán tự động qua PayOS).
- **Hardware Integration (ESP32)**: Kết nối với phần cứng ESP32 qua giao thức MQTT (HiveMQ) để nhả hàng thực tế. Hỗ trợ phát âm thanh TTS trực tiếp từ ESP32 qua giao thức I2S.

---

## 🛠 Yêu cầu hệ thống (Prerequisites)

Để chạy được Demo trên máy tính mới, bạn cần cài đặt các phần mềm sau:

1. **Python 3.10+**: Đảm bảo đã thêm Python vào `PATH`.
2. **Git**: Để clone mã nguồn.
3. **Ollama**: Phần mềm để chạy Local LLM. Tải và cài đặt tại [ollama.com](https://ollama.com/).
4. **Ngrok**: Dùng để mở Webhook ra public cho PayOS gọi về máy tính local.

---

## 🚀 Hướng dẫn Cài đặt & Chạy Demo

### Bước 1: Clone mã nguồn
```bash
git clone <URL_CUA_REPO_NAY>
cd Voice_Interaction_For_Robot
```

### Bước 2: Cài đặt thư viện Python
Mở Terminal/Command Prompt trong thư mục dự án và chạy:
```bash
pip install -r requirements.txt
```

### Bước 3: Tải Model và Nạp vào Ollama
Dự án sử dụng mô hình GGUF đã được fine-tune (`student_1.5b_q8_0.gguf`). Vì file này khá nặng (1.6GB) nên không được đưa lên Git.

1. Tải file `student_1.5b_q8_0.gguf` từ [https://drive.google.com/file/d/1ky7b68l8cnA7goJUK7ZEvVVjKK2rZ-6E/view?usp=sharing] và đặt nó vào **thư mục gốc của dự án**.
2. Mở Terminal tại thư mục gốc và chạy lệnh nạp mô hình vào Ollama:
```bash
ollama create vending-student -f Modelfile
```
*Lưu ý: Đảm bảo phần mềm Ollama đang được bật ngầm ở dưới taskbar.*

### Bước 4: Thiết lập Groq API Key (Dùng cho STT)
Để tính năng nhận diện giọng nói (STT) hoạt động siêu tốc, bạn cần có Groq API Key.

1. Truy cập [console.groq.com](https://console.groq.com/keys) để lấy API Key miễn phí.
2. Sét biến môi trường trên máy:
   - **Windows (Command Prompt)**:
     ```cmd
     set GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
     ```
   - **Windows (PowerShell)**:
     ```powershell
     $env:GROQ_API_KEY="gsk_xxxxxxxxxxxxxxxxxxxx"
     ```

### Bước 5: Thiết lập Mạng cho ESP32 (Khi mang ra Lab)
Khi chạy thực tế ở địa điểm mới (như Lab):
1. Cấp nguồn cho ESP32. Nếu không có WiFi cũ, ESP32 sẽ phát WiFi tên `AutoConnectAP` (Mật khẩu: `12345678`).
2. Dùng điện thoại kết nối vào `AutoConnectAP`. Truy cập `192.168.4.1`, chọn cấu hình WiFi của Lab và nhập mật khẩu.
3. ESP32 sẽ tự khởi động lại và kết nối mạng.
4. **LƯU Ý QUAN TRỌNG:** Laptop chạy Server (file `start_demo.bat`) cũng phải **BẮT BUỘC** kết nối chung mạng WiFi với ESP32 để ESP32 có thể tải file âm thanh TTS từ Laptop.

### Bước 6: Khởi động Toàn bộ Hệ thống
Chỉ cần chạy file Batch sau để bật đồng loạt toàn bộ server:
```cmd
start_demo.bat
```
Script này sẽ tự động trải qua 5 bước:
1. Giải phóng Port 8000 và dọn dẹp các luồng Ngrok chạy ngầm.
2. Bỏ qua Mock ESP32 (vì dùng phần cứng thật).
3. Bật Local NLP Server (Xử lý STT + LLM bằng luồng bất đồng bộ để tránh bị văng mic).
4. Bật Web App Server (FastAPI).
5. Tự động bật Ngrok mở Webhook cho PayOS với tên miền tĩnh.

Sau 3 giây, giao diện Kiosk sẽ tự động hiện trên trình duyệt web (`http://localhost:8000`).

---

## 🎮 Cách sử dụng Giao diện Demo

1. Trên trình duyệt, bấm vào biểu tượng **Microphone**, sau đó nói lệnh (Ví dụ: *"Cho mình một chai coca"* hoặc *"Cho thêm hai chai pepsi nữa"*).
2. Khi đã chọn đủ, nói *"Thanh toán"*. Hệ thống sẽ sinh mã QR VietQR (thông qua PayOS).
3. Sử dụng App Ngân hàng quét mã QR để chuyển khoản thực tế. 
4. Hệ thống sẽ tự động bắt Webhook từ PayOS, báo "Thanh toán thành công" và gửi lệnh nhả hàng (kèm link âm thanh) xuống ESP32.
5. Nếu trong lúc mở QR khách hàng lỡ thay đổi ý định (ví dụ nói *"Thêm 1 sting"*), mã QR sẽ tự động ẩn đi để hiển thị giỏ hàng mới cập nhật. Nếu mã QR hết 5 phút sẽ tự mờ đi cảnh báo hết hạn.

---

## 📂 Cấu trúc mã nguồn (Project Structure)

Dưới đây là cây thư mục các tệp tin trong bản Demo này và tác dụng của chúng:

```text
Voice_Interaction_For_Robot/
├── start_demo.bat        # Script khởi động tự động toàn bộ hệ thống (gồm cả Ngrok)
├── Modelfile             # File cấu hình để nạp model GGUF vào Ollama
├── requirements.txt      # Danh sách các thư viện Python cần cài đặt
├── stt_server.py         # Server chuyển Giọng nói thành Văn bản (Dùng Groq API)
├── nlp_server.py         # Server Xử lý Ngôn ngữ Tự nhiên (Chạy Local LLM bằng Ollama)
├── run_mock_esp.py       # Script giả lập phần cứng ESP32 (Lắng nghe lệnh MQTT & in log quay motor)
├── esp/
│   └── esp.ino           # Code C++ Firmware thực tế nạp cho vi điều khiển ESP32 vật lý
├── client/               # Toàn bộ mã nguồn Web UI và Logic xử lý tại Local (Edge)
│   ├── web_app.py        # Local Web Server (FastAPI) phục vụ giao diện Kiosk
│   ├── web/static/       # Giao diện người dùng HTML/CSS/JS (Giỏ hàng, Microphone, Hoạt ảnh)
│   ├── business/         # Tầng Logic nghiệp vụ điều phối các ý định (Buy, Confirm, Cancel)
│   ├── core/             # Lõi hệ thống: Quản lý Giỏ hàng, Kho hàng JSON, kết nối MQTT
│   └── network/          # Các module giao tiếp mạng nội bộ
└── voice_vending/        # Tầng thư viện nền tảng (Base Framework) dùng chung
    ├── config/           # File cấu hình (config.yaml) và cơ sở dữ liệu kho giả lập (inventory.json)
    ├── device/           # Adapter giao tiếp giữa Logic phần mềm và Phần cứng (MQTT/Mock)
    └── services/         # Dịch vụ quản lý luồng lệnh xả hàng (Command Queue) và Hàng tồn kho
```
