idf_component_register(
    SRCS "csi_streamer.cpp"
    INCLUDE_DIRS "."
    REQUIRES esp_wifi esp_common lwip esp_timer esp_hw_support
)
