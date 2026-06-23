#include "csi_streamer.h"
#include "esphome/core/log.h"
#include "esp_wifi.h"
#include "lwip/sockets.h"
#include "lwip/netdb.h"
#include <cstring>
#include <cmath>

namespace esphome {
namespace csi_streamer {

static const char *const TAG = "csi_streamer";

void CSIStreamer::setup() {
    ESP_LOGI(TAG, "CSI Streamer setup");
    
    sock_fd_ = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (sock_fd_ < 0) {
        ESP_LOGE(TAG, "Failed to create UDP socket: %d", errno);
        return;
    }
    
    memset(&dest_addr_, 0, sizeof(dest_addr_));
    dest_addr_.sin_family = AF_INET;
    dest_addr_.sin_port = htons(destination_port_);
    
    ip4_addr_t addr;
    if (!ip4addr_aton(destination_host_.c_str(), &addr)) {
        ESP_LOGE(TAG, "Invalid destination IP: %s", destination_host_.c_str());
        return;
    }
    dest_addr_.sin_addr.s_addr = addr.addr;
    
    wifi_csi_config_t csi_config;
    memset(&csi_config, 0, sizeof(csi_config));
    csi_config.lltf_en = 1;
    csi_config.htltf_en = 1;
    
    esp_err_t err = esp_wifi_set_csi_config(&csi_config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to configure CSI: %s", esp_err_to_name(err));
        return;
    }
    
    err = esp_wifi_set_csi_rx_cb(&csi_callback, this);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to set CSI callback: %s", esp_err_to_name(err));
        return;
    }
    
    err = esp_wifi_set_csi(true);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to enable CSI: %s", esp_err_to_name(err));
        return;
    }
    
    ESP_LOGI(TAG, "CSI Streamer initialized, streaming to %s:%d",
             destination_host_.c_str(), destination_port_);
}

void CSIStreamer::loop() {
    // Rate limiting handled by CSI callback frequency
}

void CSIStreamer::csi_callback(void *ctx, wifi_csi_info_t *info) {
    CSIStreamer *self = static_cast<CSIStreamer *>(ctx);
    self->process_csi(info);
}

void CSIStreamer::process_csi(wifi_csi_info_t *info) {
    if (sock_fd_ < 0) return;
    if (info == nullptr || info->buf == nullptr) return;
    
    CSIPacketHeader header;
    header.magic = 0x43534920;
    header.sequence = sequence_++;
    header.timestamp_us = esp_timer_get_time();
    memcpy(header.mac, info->mac, 6);
    header.rssi = info->rx_ctrl.rssi;
    header.num_subcarriers = 52;
    
    int16_t *csi_buf = reinterpret_cast<int16_t *>(info->buf);
    int num_sc = std::min(52, (int)info->len / 2);
    
    for (int i = 0; i < num_sc; i++) {
        int16_t real = csi_buf[i * 2];
        int16_t imag = csi_buf[i * 2 + 1];
        float amplitude = sqrtf((float)real * real + (float)imag * imag);
        header.data[i] = (uint8_t)(amplitude > 255.0f ? 255 : (int)amplitude);
    }
    
    for (int i = num_sc; i < 52; i++) {
        header.data[i] = 0;
    }
    
    ssize_t sent = sendto(sock_fd_, &header, sizeof(header), 0,
                          (struct sockaddr *)&dest_addr_, sizeof(dest_addr_));
    
    if (sent < 0) {
        ESP_LOGW(TAG, "UDP send failed: %d", errno);
    }
}

}  // namespace csi_streamer
}  // namespace esphome
