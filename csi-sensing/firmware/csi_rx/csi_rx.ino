/*
 * csi_rx.ino  -  ESP32-C6 CSI receiver / sensor
 * ----------------------------------------------
 * Part of the ESP32-DIV csi-sensing webapp (ruview-inspired Wi-Fi sensing).
 *
 * Role
 *   Connects to the csi_tx SoftAP, enables CSI capture, and for every packet
 *   it receives from the TX it emits one CSI record. Records are printed as
 *   compact JSON lines over USB serial at 921600 baud. The host bridge
 *   (host/serial_bridge.py) forwards those lines to the Docker server.
 *
 *   Serial was chosen as the default because it is the most reliable, needs
 *   no network reconfiguration, and never competes with the CSI Wi-Fi link.
 *   A Wi-Fi/TCP streaming variant is described in csi-sensing/README.md.
 *
 * Output line format (one JSON object per received packet):
 *   {"t":<uint32 micros>,"rssi":<int>,"n":<subcarriers>,"csi":[i0,q0,i1,q1,...]}
 *   - csi is raw signed int8 I/Q interleaved, 2 bytes per subcarrier.
 *   - amplitude of subcarrier k = sqrt(i_k^2 + q_k^2), computed on the server.
 *
 * Board: ESP32-C6 Dev Module, Arduino-ESP32 core >= 3.0.x.
 */

#include <WiFi.h>
#include "esp_wifi.h"

// ---- Must match csi_tx.ino ----
#define CSI_SSID     "csi-sense"
#define CSI_PASSWORD "csisense123"
// --------------------------------

#define SERIAL_BAUD  921600

// Ring-ish single-slot handoff from the Wi-Fi callback to loop().
// The CSI callback runs in Wi-Fi task context: keep it tiny, copy out, print
// from loop() to avoid blocking the RF stack.
static volatile bool     g_have = false;
static uint8_t           g_buf[256];
static volatile int      g_len = 0;
static volatile int      g_rssi = 0;
static volatile uint32_t g_ts = 0;

// CSI receive callback - fires for each received packet once CSI is enabled.
void IRAM_ATTR onCsi(void *ctx, wifi_csi_info_t *info) {
  if (!info || !info->buf || info->len <= 0) return;
  if (g_have) return;                      // previous sample not yet flushed
  int len = info->len;
  if (len > (int)sizeof(g_buf)) len = sizeof(g_buf);
  memcpy(g_buf, info->buf, len);
  g_len  = len;
  g_rssi = info->rx_ctrl.rssi;
  g_ts   = (uint32_t)(esp_timer_get_time() & 0xFFFFFFFF);
  g_have = true;
}

void enableCsi() {
  wifi_csi_config_t cfg = {};
  cfg.lltf_en           = true;   // legacy long training field
  cfg.htltf_en          = true;   // HT long training field
  cfg.stbc_htltf2_en    = true;
  cfg.ltf_merge_en      = true;
  cfg.channel_filter_en = true;
  cfg.manu_scale        = false;  // let hardware auto-scale
  esp_wifi_set_csi_config(&cfg);
  esp_wifi_set_csi_rx_cb(onCsi, NULL);
  esp_wifi_set_csi(true);
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(200);
  Serial.println();
  Serial.println("[csi_rx] ESP32-C6 CSI receiver starting");

  WiFi.mode(WIFI_STA);
  WiFi.begin(CSI_SSID, CSI_PASSWORD);
  Serial.printf("[csi_rx] joining \"%s\"", CSI_SSID);
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries++ < 60) {
    delay(250);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[csi_rx] WARNING: not connected. Check csi_tx is running.");
  } else {
    Serial.printf("[csi_rx] connected, IP %s, RSSI %d\n",
                  WiFi.localIP().toString().c_str(), WiFi.RSSI());
  }

  enableCsi();
  Serial.println("[csi_rx] CSI enabled. Streaming JSON lines...");
}

void loop() {
  if (!g_have) return;

  // Snapshot the shared slot.
  int      len  = g_len;
  int      rssi = g_rssi;
  uint32_t ts   = g_ts;
  static uint8_t local[256];
  memcpy(local, g_buf, len);
  g_have = false;                          // release slot for next callback

  int n = len / 2;                         // 2 int8 (I,Q) per subcarrier

  // Build the JSON line. Manual assembly keeps it fast and allocation-free.
  Serial.print("{\"t\":");
  Serial.print(ts);
  Serial.print(",\"rssi\":");
  Serial.print(rssi);
  Serial.print(",\"n\":");
  Serial.print(n);
  Serial.print(",\"csi\":[");
  for (int i = 0; i < len; i++) {
    Serial.print((int8_t)local[i]);
    if (i != len - 1) Serial.print(',');
  }
  Serial.println("]}");
}
