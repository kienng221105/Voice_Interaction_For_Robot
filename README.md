# Voice Vending Machine - Local Edge Demo

Dự án này là hệ thống Trợ lý Giọng nói cho Máy Bán hàng tự động (Voice Vending Machine) được thiết kế tối ưu hóa để chạy hoàn toàn trên Thiết bị biên (Local/Edge Computing) không cần phụ thuộc mạng lưới Đám mây (Cloud) cho quá trình xử lý ngôn ngữ NLP.

Hệ thống bao gồm:
- **STT (Speech-to-Text)**: Sử dụng API Groq Whisper để nhận dạng giọng nói siêu tốc.
- **NLP (Natural Language Processing)**: Chạy hoàn toàn dưới Local bằng phần mềm Ollama với mô hình đã được Fine-tune chuyên biệt (`vending-student` 1.5B) cho độ chính xác cao và độ trễ cực thấp (< 3.5s).
- **Web UI & Business Logic**: Giao diện Kiosk hiển thị trực quan và Server điều phối xử lý bán hàng (Cart, Inventory, Payment).
- **Hardware Integration**: Kết nối với phần cứng ESP32 qua giao thức MQTT để nhả hàng thực tế (kèm script Mock để giả lập khi không có mạch thật).

---

## 🛠 Yêu cầu hệ thống (Prerequisites)

Để chạy được Demo trên máy tính mới, bạn cần cài đặt các phần mềm sau:

1. **Python 3.10+**: Đảm bảo đã thêm Python vào `PATH`.
2. **Git**: Để clone mã nguồn.
3. **Ollama**: Phần mềm để chạy Local LLM. Tải và cài đặt tại [ollama.com](https://ollama.com/).

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
   - **MacOS/Linux**:
     ```bash
     export GROQ_API_KEY="gsk_xxxxxxxxxxxxxxxxxxxx"
     ```

### Bước 5: Cài đặt Giọng đọc Tiếng Việt (Cho Windows)
Để hệ thống phản hồi bằng giọng nói tự nhiên, bạn cần đảm bảo Windows đã cài sẵn gói giọng nói Tiếng Việt:
1. Mở **Settings** (Win + I) -> **Time & Language** -> **Speech**.
2. Chọn **Add voices** -> Tìm **`Vietnamese`** và cài đặt.
3. Khởi động lại trình duyệt web để nó cập nhật danh sách giọng nói.

### Bước 6: Khởi động Toàn bộ Hệ thống
Chỉ cần chạy file Batch sau để bật đồng loạt 4 luồng xử lý:
```cmd
start_demo.bat
```
Script này sẽ tự động:
- Bật Mock ESP32 Hardware (Giả lập phần cứng motor).
- Bật Local NLP Server (Gọi Ollama).
- Bật Web App Server (FastAPI).
- Tự động mở trình duyệt web lên trang giao diện máy bán hàng (`http://localhost:8000`).

---

## 🎮 Cách sử dụng Giao diện Demo

1. Trên trình duyệt, bấm nút **Bắt đầu Trải nghiệm**.
2. Bấm vào biểu tượng **Microphone**, sau đó nói lệnh (Ví dụ: *"Cho mình một chai coca"* hoặc *"Cho thêm hai chai aquafina nữa"*).
3. Hệ thống sẽ nhận diện, cập nhật giỏ hàng lập tức và máy giả lập ESP32 sẽ hiển thị log đang quay motor rớt hàng.
4. Tận hưởng độ trễ E2E siêu mượt (< 3.5s) của hệ thống Local Edge AI!

---

## 📂 Cấu trúc mã nguồn (Project Structure)

Dưới đây là cây thư mục các tệp tin trong bản Demo này và tác dụng của chúng:

```text
Voice_Interaction_For_Robot/
├── start_demo.bat        # Script khởi động tự động toàn bộ hệ thống
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
