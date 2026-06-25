#include "csi_streamer.h"
#include "esphome/core/log.h"
#include "esp_wifi.h"
#include "lwip/sockets.h"
#include "lwip/netdb.h"
#include <cstring>

namespace esphome {
namespace csi_streamer {

// Raw CSI buffer size: 52 subcarriers * 2 (real+imag) * 2 bytes = 208 bytes
static const int RAW_BUF_SIZE = 52 * 2 * 2;

void CSIStreamer::setup() {
    ESP_LOGI(TAG, "CSI Streamer setup");
    
    // Create UDP socket FIRST
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
        close(sock_fd_);
        sock_fd_ = -1;
        return;
    }
    dest_addr_.sin_addr.s_addr = addr.addr;
    
    // Mark setup complete - safe to process CSI now
    setup_complete_ = true;
    
    // Configure WiFi CSI
    wifi_csi_config_t csi_config;
    memset(&csi_config, 0, sizeof(csi_config));
    csi_config.lltf_en = 1;
    csi_config.htltf_en = 1;
    csi_config.stbc_htltf2_en = 1;
    csi_config.ltf_merge_en = 1;
    csi_config.channel_filter_en = 1;
    csi_config.manu_scale = 0;
    csi_config.shift = 0;
    
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
    if (!setup_complete_ || !has_new_csi_) return;
    has_new_csi_ = false;
    process_csi();
}

// Called from ISR - must be fast and not use any blocking calls
void CSIStreamer::csi_callback(void *ctx, wifi_csi_info_t *info) {
    CSIStreamer *self = static_cast<CSIStreamer *>(ctx);
    
    // Don't buffer data until setup is complete
    if (!self->setup_complete_) return;
    if (info == nullptr || info->buf == nullptr) return;
    
    // Copy raw CSI data out of the ISR context immediately
    self->csi_info_.buf_len = info->len;
    memcpy(self->csi_info_.mac, info->mac, 6);
    self->csi_info_.rssi = info->rx_ctrl.rssi;
    self->csi_info_.timestamp_us = esp_timer_get_time();
    self->csi_info_.sequence = self->sequence_++;
    
    // Copy raw bytes directly (up to RAW_BUF_SIZE)
    int copy_len = (info->len < RAW_BUF_SIZE) ? info->len : RAW_BUF_SIZE;
    memcpy(self->csi_info_.raw_buf, info->buf, copy_len);
    
    self->has_new_csi_ = true;
}

void CSIStreamer::process_csi() {
    if (sock_fd_ < 0) return;
    
    CSIPacketHeader header;
    header.magic = 0x43534920;  // "CSI "
    header.sequence = csi_info_.sequence;
    header.timestamp_us = csi_info_.timestamp_us;
    memcpy(header.mac, csi_info_.mac, 6);
    header.rssi = csi_info_.rssi;
    header.num_subcarriers = 52;
    
    int16_t *csi_buf = reinterpret_cast<int16_t *>(csi_info_.raw_buf);
    int num_sc = (csi_info_.buf_len < 104) ? (csi_info_.buf_len / 2) : 52;
    
    for (int i = 0; i < num_sc; i++) {
        int16_t real = csi_buf[i * 2];
        int16_t imag = csi_buf[i * 2 + 1];
        // Simple amplitude: |real| + |imag| (clamped to 255)
        int amp = (int)abs(real) + (int)abs(imag);
        header.data[i] = (amp > 255) ? 255 : (uint8_t)amp;
    }
    
    for (int i = num_sc; i < 52; i++) {
        header.data[i] = 0;
    }
    
    sendto(sock_fd_, &header, sizeof(header), 0,
           (struct sockaddr *)&dest_addr_, sizeof(dest_addr_));
}

}  // namespace csi_streamer
}  // namespace esphome
