#pragma once

#include "esphome/core/component.h"
#include "esp_wifi.h"
#include "lwip/sockets.h"
#include "lwip/netdb.h"
#include <string>

namespace esphome {
namespace csi_streamer {

struct __attribute__((packed)) CSIPacketHeader {
    uint32_t magic;
    uint32_t sequence;
    uint64_t timestamp_us;
    uint8_t mac[6];
    int8_t rssi;
    uint8_t num_subcarriers;
    uint8_t data[52];
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
  void process_csi(wifi_csi_info_t *info);

  int sock_fd_ = -1;
  struct sockaddr_in dest_addr_;
  std::string destination_host_;
  uint16_t destination_port_ = 5000;
  uint16_t sample_rate_ = 100;
  uint32_t sequence_ = 0;
};

}  // namespace csi_streamer
}  // namespace esphome
