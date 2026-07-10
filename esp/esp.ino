#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <WiFiManager.h>
#include <vector>
#include <PubSubClient.h>
#include <Audio.h>

const int MACHINE_ID = 1;

const char *mqtt_server = "";
const int mqtt_port = 8883; 
const char *mqtt_user = "";
const char *mqtt_pass = "";

WiFiClientSecure espClient;
PubSubClient client(espClient);

#define I2S_BCLK 27
#define I2S_LRC 26
#define I2S_DOUT 25
Audio audio;

const int RELAY_PINS[4] = {22, 23, 4, 13};
const int SWITCH_PINS[4] = {14, 18, 19, 21};

const uint32_t TIMEOUT_MS = 5000;
const uint32_t DEBOUNCE_US = 5000;

// Cờ trạng thái cho 4 motor
volatile bool seenClosed[4] = {false, false, false, false};
volatile bool stopNow[4] = {false, false, false, false};
volatile uint32_t lastEdgeUs[4] = {0, 0, 0, 0};

void IRAM_ATTR handleISR(int index)
{
    uint32_t now = micros();
    if (now - lastEdgeUs[index] < DEBOUNCE_US)
        return;
    lastEdgeUs[index] = now;

    int lvl = digitalRead(SWITCH_PINS[index]);
    if (lvl == LOW)
    {
        seenClosed[index] = true;
    }
    else
    {
        if (seenClosed[index])
            stopNow[index] = true;
    }
}

void IRAM_ATTR isrSlot0() { handleISR(0); }
void IRAM_ATTR isrSlot1() { handleISR(1); }
void IRAM_ATTR isrSlot2() { handleISR(2); }
void IRAM_ATTR isrSlot3() { handleISR(3); }

// ================= HÀM QUAY MOTOR 1 VÒNG ========
bool vendOnce(int index)
{
    uint32_t t0 = millis();

    // 1. RÀ GỐC (HOMING): Xả công tắc nếu đang bị đè
    if (digitalRead(SWITCH_PINS[index]) == LOW)
    {
        Serial.printf("[VEND] Khay %d dang bi de. Xa cho het de...\n", index + 1);
        digitalWrite(RELAY_PINS[index], LOW); // BẬT MOTOR ĐỂ XẢ KẸT
        
        while (digitalRead(SWITCH_PINS[index]) == LOW)
        {
            audio.loop(); // Giữ loa không bị vấp
            if (millis() - t0 > TIMEOUT_MS)
            {
                digitalWrite(RELAY_PINS[index], HIGH); // Tắt khẩn cấp
                Serial.printf("[ERR] Khay %d ket cung khi dang reset!\n", index + 1);
                return false;
            }
            delay(1);
        }
        delay(50); // Trễ một chút để lò xo trượt hẳn ra khỏi công tắc
    }

    // 2. CHUẨN BỊ CHU TRÌNH CHÍNH (Xóa cờ nhiễu do quá trình xả kẹt gây ra)
    seenClosed[index] = false;
    stopNow[index] = false;
    
    digitalWrite(RELAY_PINS[index], LOW); // Đảm bảo motor ON
    Serial.printf("[VEND] Motor khay %d ON\n", index + 1);

    // 3. Chờ cho đến khi hoàn thành chu trình: OPEN -> CLOSED -> OPEN (Bắt bằng Ngắt ISR)
    t0 = millis();
    while (!stopNow[index])
    {
        audio.loop();
        if (millis() - t0 > TIMEOUT_MS)
        {
            digitalWrite(RELAY_PINS[index], HIGH); // Tắt motor khẩn cấp
            Serial.printf("[ERR] Khay %d ket hoac qua gio!\n", index + 1);
            return false;
        }
        delay(1);
    }

    // 4. TẮT motor
    digitalWrite(RELAY_PINS[index], HIGH);
    Serial.printf("[VEND] Motor khay %d OFF (Hoan thanh)\n", index + 1);
    return true;
}

// ================= HÀM CỨU MOTOR (NHÍCH 1 CHÚT RỒI NGẮT) =================
void nudgeMotor(int index)
{
    Serial.printf("[CỨU HỘ] Dang nhich motor khay %d...\n", index + 1);

    // Bật motor
    digitalWrite(RELAY_PINS[index], LOW);

    // Giữ motor quay trong 100 mili-giây
    uint32_t t0 = millis();
    while (millis() - t0 < 100)
    {
        audio.loop(); // Nuôi loa liên tục
        delay(1);
    }

    // Tắt motor
    digitalWrite(RELAY_PINS[index], HIGH);
    Serial.printf("[CỨU HỘ] Da ngat motor khay %d.\n", index + 1);
}

// ================= HÀM XỬ LÝ KHI NHẬN ĐƯỢC LỆNH MUA HÀNG =================
void mqttCallback(char *topic, uint8_t *payload, unsigned int length)
{
    String message;
    for (int i = 0; i < length; i++)
    {
        message += (char)payload[i];
    }

    Serial.print("Da nhan lenh tu HiveMQ Topic [");
    Serial.print(topic);
    Serial.print("]: ");
    Serial.println(message);

    String loiNhoi = "Bạn đã thanh toán thành công, bạn chờ trong giây lát để lấy nước";

    for (int i = 0; i < 4; i++)
    {
        String slotTag = "SLOT:" + String(i + 1);

        if (message.indexOf(slotTag) >= 0)
        {
            Serial.println("Dang phat thong bao...");
            audio.connecttospeech(loiNhoi.c_str(), "vi");
            while (audio.isRunning())
            {
                audio.loop();
            }

            // Gọi hàm trả hàng
            bool success = vendOnce(i);
            if (success)
            {
                Serial.println("Tra hang thanh cong!");
            }
            else
            {
                Serial.println("Loi tra hang!");
            }
        }
    }
}

// ================= HÀM KẾT NỐI VÀ DUY TRÌ MQTT =================
void reconnectMQTT()
{
    while (!client.connected())
    {
        Serial.print("Dang thu ket noi MQTT den HiveMQ... ");

        String clientId = "ESP32Client-";
        clientId += String(random(0xffff), HEX);

        if (client.connect(clientId.c_str(), mqtt_user, mqtt_pass))
        {
            Serial.println("THANH CONG!");
            String topicName = "vending/machine/" + String(MACHINE_ID);
            client.subscribe(topicName.c_str());
            Serial.print("Da lang nghe Topic: ");
            Serial.println(topicName);
        }
        else
        {
            Serial.print("THAT BAI, Ma loi = ");
            Serial.print(client.state());
            Serial.println(" (Cho 5 giay roi thu lai)");

            for (int k = 0; k < 500; k++)
            {
                audio.loop();
                delay(10);
            }
        }
    }
}

// ================= SETUP =================
void setup()
{
    Serial.begin(115200);

    for (int i = 0; i < 4; i++)
    {
        pinMode(RELAY_PINS[i], OUTPUT);
        digitalWrite(RELAY_PINS[i], HIGH);
        pinMode(SWITCH_PINS[i], INPUT_PULLUP);
    }
    attachInterrupt(digitalPinToInterrupt(SWITCH_PINS[0]), isrSlot0, CHANGE);
    attachInterrupt(digitalPinToInterrupt(SWITCH_PINS[1]), isrSlot1, CHANGE);
    attachInterrupt(digitalPinToInterrupt(SWITCH_PINS[2]), isrSlot2, CHANGE);
    attachInterrupt(digitalPinToInterrupt(SWITCH_PINS[3]), isrSlot3, CHANGE);

    WiFiManager wm;
    std::vector<const char *> menu = {"wifi", "sep", "restart", "exit"};
    wm.setMenu(menu);

    bool res = wm.autoConnect("AutoConnectAP", "12345678");

    if (!res)
    {
        Serial.println("Failed to connect");
    }
    else
    {
        Serial.println("\nDa ket noi WiFi thanh cong! yeey :)");
    }

    espClient.setInsecure();
    client.setServer(mqtt_server, mqtt_port);
    client.setCallback(mqttCallback);

    audio.setPinout(I2S_BCLK, I2S_LRC, I2S_DOUT);
    audio.setVolume(21);

    audio.connecttospeech("Hệ thống bán nước tự động đã sẵn sàng", "vi");
    while (audio.isRunning())
    {
        audio.loop();
    }
    Serial.println("Da khoi dong xong am thanh!");

    Serial.println("\n--- HUONG DAN CUU HO MOTOR ---");
    Serial.println("Go vao Serial Monitor: a (khay 1), b (khay 2), c (khay 3), d (khay 4)");
    Serial.println("------------------------------\n");
}

// ================= VÒNG LẶP CHÍNH =================
void loop()
{
    audio.loop();

    if (!client.connected())
    {
        reconnectMQTT();
    }

    client.loop();

    if (Serial.available() > 0)
    {
        char c = Serial.read();

        if (c == '\n' || c == '\r')
            return;

        if (c == 'a' || c == 'A') nudgeMotor(0);
        else if (c == 'b' || c == 'B') nudgeMotor(1);
        else if (c == 'c' || c == 'C') nudgeMotor(2);
        else if (c == 'd' || c == 'D') nudgeMotor(3);
        else Serial.println("Phim khong hop le. Go a, b, c, hoac d de cuu motor 1, 2, 3, 4.");
    }
}