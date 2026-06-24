"""
CSI Streamer External Component for ESPHome
Captures raw WiFi CSI data and streams via UDP.

Based on Espressif esp-csi reference implementation:
https://github.com/espressif/esp-csi
"""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components.esp32 import add_idf_sdkconfig_option
from esphome.const import CONF_ID, CONF_PORT

CODEOWNERS = ["@custom"]
DEPENDENCIES = ["wifi"]
AUTO_LOAD = []

CONF_DESTINATION_HOST = "destination_host"
CONF_DESTINATION_PORT = "destination_port"
CONF_SAMPLE_RATE = "sample_rate"

csi_streamer_ns = cg.esphome_ns.namespace("csi_streamer")
CSIStreamer = csi_streamer_ns.class_("CSIStreamer", cg.Component)

CONFIG_SCHEMA = cv.Schema({
    cv.GenerateID(): cv.declare_id(CSIStreamer),
    cv.Optional(CONF_DESTINATION_HOST, default="192.168.68.1"): cv.string,
    cv.Optional(CONF_DESTINATION_PORT, default=5000): cv.port,
    cv.Optional(CONF_SAMPLE_RATE, default=100): cv.int_range(min=1, max=1000),
}).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_destination(
        config[CONF_DESTINATION_HOST],
        config[CONF_DESTINATION_PORT]
    ))
    cg.add(var.set_sample_rate(config[CONF_SAMPLE_RATE]))

    # Enable PM (required for freertos_hooks.c to compile - calls esp_pm_impl_idle_hook)
    # but disable WiFi-specific PM features that conflict with CSI
    add_idf_sdkconfig_option("CONFIG_PM_ENABLE", True)
    add_idf_sdkconfig_option("CONFIG_ESP_WIFI_CSI_ENABLED", True)
    add_idf_sdkconfig_option("CONFIG_ESP_WIFI_STA_DISCONNECTED_PM_ENABLE", False)
    add_idf_sdkconfig_option("CONFIG_ESP_WIFI_AMPDU_TX_ENABLED", False)
    add_idf_sdkconfig_option("CONFIG_ESP_WIFI_AMPDU_RX_ENABLED", False)
    add_idf_sdkconfig_option("CONFIG_ESP_WIFI_DYNAMIC_RX_BUFFER_NUM", 128)
