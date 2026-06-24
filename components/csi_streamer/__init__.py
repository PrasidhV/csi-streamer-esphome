"""
CSI Streamer External Component for ESPHome
Captures raw WiFi CSI data and streams via UDP.
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

FLAG_CSI = "-DCONFIG_ESP_WIFI_CSI_ENABLED=y"
FLAG_BA_WIN = "-DCONFIG_ESP_WIFI_RX_BA_WIN=4"
FLAGS_PM = [
    "-DCONFIG_PM_ENABLE=n",
    "-DCONFIG_ESP_WIFI_STA_DISCONNECTED_PM_ENABLE=n",
    "-DCONFIG_ESP_WIFI_AMPDU_TX_ENABLED=n",
    "-DCONFIG_ESP_WIFI_AMPDU_RX_ENABLED=n",
]

async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_destination(
        config[CONF_DESTINATION_HOST],
        config[CONF_DESTINATION_PORT]
    ))
    cg.add(var.set_sample_rate(config[CONF_SAMPLE_RATE]))

    # These target the build environment — safe on all ESP-IDF versions.
    cg.add_platformio_option("build_flags", [
        FLAG_CSI,
        FLAG_BA_WIN,
        # The remaining buffer settings have caused redefinition warnings on
        # ESP-IDF 5.5.x (CONFIG_ESP_WIFI_CSI_ENABLED is already set by the
        # sdkconfig processor when you enable CSI) or are simply not needed.
        # Keeping the flags to a minimum avoids both the compile error and
        # unnecessary configuration.
    ])
