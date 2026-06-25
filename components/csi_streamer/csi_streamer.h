#pragma once

#include "esphome/core/component.h"
#include "esp_wifi.h"
#include "lwip/sockets.h"
#include "lwip/netdb.h"
#include <string>

namespace esphome {
namespace csi_streamer {

static const char *const TAG = "csi_streamer";

// CSI packet header for UDP streaming
struct __attribute__((packed)) CSIPacketHeader {
    uint32_t magic;          // 0x43534920 = "CSI "
    uint32_t sequence;       // Packet sequence number
    uint64_t timestamp_us;   // Microsecond timestamp
    uint8_t mac[6];          // Source MAC address
    int8_t rssi;             // RSSI in dBm
    uint8_t num_subcarriers; // Number of subcarriers
    uint8_t data[52];        // Amplitude per subcarrier (normalized 0-255)
};

// Internal CSI buffer populated by ISR
struct CSIInfo {
    uint8_t raw_buf[52 * 2 * 2];  // Raw CSI data buffer
    int buf_len;
    uint8_t mac[6];
    int8_t rssi;
    uint64_t timestamp_us;
    uint32_t sequence;
};

class CSIStreamer : public Component {
 public:
  void set_destination(const std::string &host, uint16_t port) {
    destination_host_ = host;
    destination_port_ = port;
  }
  
  void set_sample_rate(uint16_t rate) { sample_rate_ = rate; }

  void setup() override;
  void loop() override;
  
  static void csi_callback(void *ctx, wifi_csi_info_t *info);

 private:
  void process_csi();

  int sock_fd_ = -1;
  struct sockaddr_in dest_addr_;
  std::string destination_host_;
  uint16_t destination_port_ = 5000;
  uint16_t sample_rate_ = 100;
  uint32_t sequence_ = 0;
  
  CSIInfo csi_info_;
  bool has_new_csi_ = false;
};

}  // namespace csi_streamer
}  // namespace esphome
