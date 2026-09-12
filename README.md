# CITADEL Secure Edge Operations

CITADEL is a secure edge telemetry platform for disconnected and untrusted environments. It authenticates distributed devices, encrypts messages, blocks replay and tampering attempts, enforces role-based access, and maintains a replicated tamper-evident history of security decisions while preserving the original navigation, communication, event-monitoring, and personnel-safety dashboard. Operational data now comes only from verified hardware packets; there is no automatic operational-data generator.

## Implemented security

- AES-256-GCM encrypted telemetry with an HMAC-SHA256 envelope.
- Unique device credentials encrypted at rest with an environment-provided master key.
- Strict packet schema, payload limits, timestamps, nonces, monotonic sequence numbers, and persistent replay state.
- PENDING, TRUSTED, and REVOKED device lifecycle with administrator controls.
- Security-operator and administrator roles with backend authorization.
- CSRF checks, login throttling, session cookie controls, restricted CORS, CSP, and other response headers.
- SQLite persistence for users, devices, replay state, packet decisions, audit blocks, and validator votes.
- Three independent local validators and a two-of-three approval rule.
- Full-chain verification of block hashes, links, validator signatures, and quorum.
- Security Operations UI with device trust, security events, ledger status, safe packet metadata, and an isolated attack lab.
- Disabled legacy unsigned ingestion. Accepted packets alone update operations.
- Safe rendering of incoming messages through textContent.

This is a permissioned demonstration ledger. Validators independently authenticate proposed block hashes using separate derived keys. It demonstrates consensus and tamper evidence locally; it is not a public cryptocurrency network.

## Trust flow

ESP or simulator -> encrypted authenticated packet -> untrusted transport -> verification gateway -> accepted operational state -> digest-only audit event -> three validators -> two-of-three confirmed block.

Encryption provides confidentiality. Authentication establishes that a holder of an enrolled secret created the packet. Nonces, timestamps, and sequences establish freshness. The ledger makes security decisions tamper-evident. These controls do not prove that a compromised sensor reports truthful measurements and do not prevent radio jamming.

## Run with hardware

1. Open PowerShell in this folder.
2. Copy .env.example to .env and replace its secrets.
3. Connect the LoRa gateway ESP32 by USB.
4. Find its COM port in Windows Device Manager.
5. Set ENABLE_SERIAL_INGEST=true, SERIAL_PORT=COMx, and SERIAL_BAUD_RATE=115200 in the shell.
6. Run: .\.venv\Scripts\python.exe backend\app.py
7. Open http://127.0.0.1:5000

Local demonstration accounts:

- Administrator: admin / CitadelDemo!2026
- Security operator: operator / OperatorDemo!2026
- Viewer: viewer / ViewerDemo!2026

Change these before sharing the application. They are documented development credentials.

## Demonstration sequence

Open Security and run: Valid Packet, Unknown Device, Tamper Message, Replay Packet, Stale Packet, Revoked Device, and Tamper Ledger. Each simulation shows the gateway decision and its audit event. The lab generates synthetic data and never targets external systems.

Administrators can also enroll a new device, approve or revoke it, reset its sequence state, and take validators offline to demonstrate loss of quorum. A newly generated provisioning secret is displayed once for the local demo.

## Test

Run: .\.venv\Scripts\python.exe -m unittest discover -s backend\tests -v

## Hardware wiring

Use the same 3.3 V logic and a common ground. Verify the pin labels printed on your specific LoRa module before applying power.

Soldier ESP32 to SX1276/SX1278 LoRa:

- 3.3V -> VCC
- GND -> GND
- GPIO18 -> SCK
- GPIO19 -> MISO
- GPIO23 -> MOSI
- GPIO5 -> NSS/CS
- GPIO27 -> RESET
- GPIO26 -> DIO0

Soldier ESP32 to MAX30102:

- 3.3V -> VIN
- GND -> GND
- GPIO21 -> SDA
- GPIO22 -> SCL

Vosk edge computer or Raspberry Pi UART to soldier ESP32:

- Vosk TX -> ESP32 GPIO16 (RX2)
- Vosk RX -> ESP32 GPIO17 (TX2), if two-way communication is required
- GND -> GND
- UART speed: 115200
- Send one UTF-8 transcription per line, ending with newline

Gateway ESP32 to LoRa uses the same LoRa pin mapping. Connect the gateway ESP32 to the backend laptop through USB; its firmware emits one complete secured JSON envelope per serial line at 115200 baud.

## Arduino libraries

Install ArduinoJson, LoRa by Sandeep Mistry, and SparkFun MAX3010x Pulse and Proximity Sensor Library. AES-GCM, HMAC, Preferences, SPI, Wire, and base64 use ESP32 platform libraries.

Before flashing, replace DEVICE_ID and DEVICE_SECRET in hardware/soldier_node/main.ino. They must match a trusted device in the backend database. The built-in S1 development credential matches the seeded local S1 record; do not use it outside a demonstration.

## Data path

MAX30102 and Vosk -> soldier ESP32 -> AES-GCM encryption and HMAC -> fragmented LoRa transmission -> gateway reassembly -> USB serial -> Flask verification -> operational dashboard and audit ledger.

The gateway never decrypts or changes the protected packet. The backend rejects it before updating the dashboard if identity, HMAC, sequence, nonce, payload, device status, or timestamp checks fail.

## Packet notes

The packet contains protocol version, device ID, sequence number, timestamp, message type, a 96-bit nonce, encrypted payload, previous-event hash, and authentication tag. Signed JSON keys are sorted and serialized with compact separators.

The soldier firmware now creates the same AES-GCM and HMAC-SHA256 envelope expected by the backend, uses a fresh 96-bit nonce, and persists its sequence counter. Because the envelope is larger than one LoRa packet, it is split into numbered 180-byte fragments and reassembled by the gateway. Ledger blocks and validator keys are never transmitted to soldier nodes.

Clockless nodes send timestamp 0 and rely on persistent sequence and nonce freshness. If a node supplies a non-zero time, the backend applies its configured clock-skew limit.

Vosk edge speech recognition remains an upstream input: its UART transcription is placed inside the encrypted payload. Cryptographic verification does not certify transcription accuracy.

The Security Demo Lab intentionally creates synthetic attack packets so judges can see the controls work. Those packets are isolated and clearly labeled; they are never presented as live operational sensor data.
