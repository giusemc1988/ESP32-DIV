/*
 * csi_tx.ino  -  ESP32-C6 CSI "illuminator" (transmitter)
 * --------------------------------------------------------
 * Part of the ESP32-DIV csi-sensing webapp (ruview-inspired Wi-Fi sensing).
 *
 * Role
 *   This board is a SoftAP that blasts a steady stream of UDP packets on a
 *   fixed channel. It does NOT compute anything. Its only job is to keep the
 *   RF "light" on so the RX board sees a constant packet rate and can measure
 *   how the channel (CSI) changes as people move/breathe in the room.
 *
 * Why a fixed, high packet rate matters
 *   CSI is only produced when the RX receives a packet. Your detection
 *   time-resolution == this packet rate. For breathing (~0.2-0.5 Hz) and
 *   motion you want a steady >= 100 Hz stream. Jitter/gaps = bad breathing FFT.
 *
 * Pair with: csi_rx.ino on the second ESP32-C6.
 *
 * Board: any ESP32-C6 (Arduino-ESP32 core >= 3.0.x, which has the C6 Wi-Fi 6
 *        stack + CSI support). Tools > Board > "ESP32C6 Dev Module".
 */

#include <WiFi.h>
#include <WiFiUdp.h>
#include "esp_wifi.h"

// ---- Must match csi_rx.ino ----
#define CSI_SSID     "csi-sense"
#define CSI_PASSWORD "csisense123"     // >= 8 chars
#define CSI_CHANNEL  6                  // pick a quiet channel (1/6/11)
#define PING_HZ      120                // packets/sec -> CSI sample rate at RX
// --------------------------------

WiFiUDP udp;
const uint16_t PING_PORT = 5005;
IPAddress broadcastIp(192, 168, 4, 255);   // SoftAP subnet broadcast
uint32_t seq = 0;
uint32_t lastPing = 0;
const uint32_t pingIntervalUs = 1000000UL / PING_HZ;

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println();
  Serial.println("[csi_tx] ESP32-C6 CSI illuminator starting");

  // SoftAP on a FIXED channel so RX and TX always share the same PHY channel.
  WiFi.mode(WIFI_AP);
  bool ok = WiFi.softAP(CSI_SSID, CSI_PASSWORD, CSI_CHANNEL, 0 /*visible*/, 4);
  Serial.printf("[csi_tx] SoftAP \"%s\" ch=%d -> %s\n",
                CSI_SSID, CSI_CHANNEL, ok ? "up" : "FAILED");
  Serial.printf("[csi_tx] AP IP: %s\n", WiFi.softAPIP().toString().c_str());

  // Lock the rate to a low, robust MCS. A fixed rate keeps CSI comparable
  // frame-to-frame (rate hopping changes the subcarrier structure).
  esp_wifi_config_11b_rate(WIFI_IF_AP, true);   // allow 11b basic rates
  esp_wifi_internal_set_fix_rate(WIFI_IF_AP, true, WIFI_PHY_RATE_6M);

  udp.begin(PING_PORT);
  Serial.printf("[csi_tx] Pinging broadcast @ %d Hz\n", PING_HZ);
}

void loop() {
  uint32_t now = micros();
  if ((uint32_t)(now - lastPing) >= pingIntervalUs) {
    lastPing = now;
    // Small fixed payload; contents don't matter, the RF packet does.
    char buf[16];
    int n = snprintf(buf, sizeof(buf), "P%lu", (unsigned long)seq++);
    udp.beginPacket(broadcastIp, PING_PORT);
    udp.write((const uint8_t*)buf, n);
    udp.endPacket();
  }
}
