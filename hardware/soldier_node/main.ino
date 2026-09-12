#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

const char* WIFI_SSID = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Replace with the IP address of the laptop/PC running the Flask backend.
const char* BACKEND_URL = "http://YOUR_LAPTOP_IP:5000/esp-data";

const char* NODE_ID = "S1";
const unsigned long SEND_INTERVAL_MS = 3000;
const int MAX_ENEMIES = 5;
const bool DEBUG_SERIAL = true;

const char* COMMAND_MESSAGES[] = {
  "enemy ahead need backup",
  "hold position",
  "area clear moving ahead",
  "need medical assistance",
  "enemy spotted on the east ridge"
};
const int COMMAND_MESSAGE_COUNT = sizeof(COMMAND_MESSAGES) / sizeof(COMMAND_MESSAGES[0]);

unsigned long lastSendAt = 0;

struct EnemyContact {
  int id;
  float lat;
  float lon;
};

struct SensorPacket {
  float lat;
  float lon;
  int hr;
  const char* cmd;
  int enemyCount;
  EnemyContact enemies[MAX_ENEMIES];
};

void connectToWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  if (DEBUG_SERIAL) {
    Serial.print("Connecting to WiFi");
  }
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    if (DEBUG_SERIAL) {
      Serial.print(".");
    }
  }

  if (DEBUG_SERIAL) {
    Serial.println();
    Serial.print("WiFi connected. ESP IP: ");
    Serial.println(WiFi.localIP());
  }
}

SensorPacket readSensors() {
  SensorPacket packet;

  // Simulated values. Replace these later with real sensor/GPS data.
  packet.lat = 12.97230 + (random(-20, 21) / 100000.0);
  packet.lon = 79.16850 + (random(-20, 21) / 100000.0);
  packet.hr = random(78, 110);
  packet.cmd = random(0, 3) == 0
    ? COMMAND_MESSAGES[random(0, COMMAND_MESSAGE_COUNT)]
    : "NULL";
  packet.enemyCount = random(0, MAX_ENEMIES + 1);

  for (int index = 0; index < packet.enemyCount; index++) {
    packet.enemies[index].id = index + 1;
    packet.enemies[index].lat = packet.lat + (random(-12, 13) / 100000.0);
    packet.enemies[index].lon = packet.lon + (random(-12, 13) / 100000.0);
  }

  return packet;
}

void sendPacketToBackend(const SensorPacket& packet) {
  if (WiFi.status() != WL_CONNECTED) {
    if (DEBUG_SERIAL) {
      Serial.println("WiFi disconnected. Reconnecting...");
    }
    connectToWiFi();
  }

  HTTPClient http;
  http.begin(BACKEND_URL);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(5000);

  StaticJsonDocument<1024> doc;
  doc["id"] = NODE_ID;
  doc["lat"] = packet.lat;
  doc["lon"] = packet.lon;
  doc["hr"] = packet.hr;
  doc["cmd"] = packet.cmd;

  JsonArray enemies = doc["en"].to<JsonArray>();
  for (int index = 0; index < packet.enemyCount; index++) {
    JsonObject enemy = enemies.add<JsonObject>();
    enemy["i"] = packet.enemies[index].id;
    enemy["lat"] = packet.enemies[index].lat;
    enemy["lon"] = packet.enemies[index].lon;
  }

  String requestBody;
  serializeJson(doc, requestBody);

  if (DEBUG_SERIAL) {
    Serial.println("Sending payload:");
    Serial.println(requestBody);
  }

  int responseCode = http.POST(requestBody);
  if (DEBUG_SERIAL) {
    Serial.print("HTTP response code: ");
    Serial.println(responseCode);
  }

  if (responseCode > 0) {
    if (DEBUG_SERIAL) {
      String responseBody = http.getString();
      Serial.println("Backend response:");
      Serial.println(responseBody);
    } else {
      http.getString();
    }
  } else if (DEBUG_SERIAL) {
    Serial.println("HTTP request failed. Check WiFi, laptop IP, and firewall.");
  }

  http.end();
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  randomSeed(micros());
  connectToWiFi();
}

void loop() {
  if (millis() - lastSendAt < SEND_INTERVAL_MS) {
    delay(50);
    return;
  }

  lastSendAt = millis();
  SensorPacket packet = readSensors();
  sendPacketToBackend(packet);
}
