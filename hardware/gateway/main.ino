#include <SPI.h>
#include <LoRa.h>
#include <ArduinoJson.h>

#define NSS 5
#define RST 27
#define DIO0 26

const long LORA_FREQUENCY = 433E6;
const size_t JSON_DOC_CAPACITY = 1536;

String incomingPacket;

bool normalizePacket(const String& rawPacket, String& normalizedPacket) {
  StaticJsonDocument<JSON_DOC_CAPACITY> inputDoc;
  DeserializationError error = deserializeJson(inputDoc, rawPacket);

  if (error) {
    return false;
  }

  StaticJsonDocument<JSON_DOC_CAPACITY> outputDoc;

  const char* nodeId = inputDoc["id"] | "";
  if (strlen(nodeId) == 0) {
    return false;
  }

  outputDoc["id"] = nodeId;
  outputDoc["lat"] = inputDoc["lat"] | 0.0;
  outputDoc["lon"] = inputDoc["lon"] | 0.0;
  outputDoc["hr"] = inputDoc["hr"] | 0;
  outputDoc["cmd"] = inputDoc["cmd"] | "";

  JsonArray normalizedEnemies = outputDoc["en"].to<JsonArray>();
  JsonArray inputEnemies = inputDoc["en"].as<JsonArray>();

  int fallbackEnemyId = 1;
  if (!inputEnemies.isNull()) {
    for (JsonObject enemy : inputEnemies) {
      JsonObject normalizedEnemy = normalizedEnemies.add<JsonObject>();
      normalizedEnemy["i"] = enemy["i"] | fallbackEnemyId;
      normalizedEnemy["lat"] = enemy["lat"] | 0.0;
      normalizedEnemy["lon"] = enemy["lon"] | 0.0;
      fallbackEnemyId++;
    }
  }

  normalizedPacket = "";
  serializeJson(outputDoc, normalizedPacket);
  return true;
}

void setup() {
  Serial.begin(9600);
  LoRa.setPins(NSS, RST, DIO0);

  if (!LoRa.begin(LORA_FREQUENCY)) {
    Serial.println("LoRa FAIL");
    while (1) {
      delay(100);
    }
  }

  LoRa.setSpreadingFactor(9);
  LoRa.setSignalBandwidth(125E3);
  LoRa.setCodingRate4(5);
  LoRa.enableCrc();
}

void loop() {
  int packetSize = LoRa.parsePacket();
  if (!packetSize) {
    delay(10);
    return;
  }

  incomingPacket = "";
  while (LoRa.available()) {
    incomingPacket += (char)LoRa.read();
  }

  String normalizedPacket;
  if (normalizePacket(incomingPacket, normalizedPacket)) {
    Serial.println(normalizedPacket);
  }
}
