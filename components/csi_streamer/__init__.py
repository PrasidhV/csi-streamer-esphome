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

async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_destination(
        config[CONF_DESTINATION_HOST],
        config[CONF_DESTINATION_PORT]
    ))
    cg.add(var.set_sample_rate(config[CONF_SAMPLE_RATE]))

    # Use PlatformIO build flags to inject defines that ESPHome's sdkconfig
    # doesn't provide by default. This avoids redefinition warnings from
    # sdkconfig.h and ensures these macros are available before any headers
    # are processed by the compiler.
    #
    # Only CSI and RX_BA_WIN are needed—these are required for CSI to compile
    # and for the WiFi macro WIFI_INIT_CONFIG_DEFAULT() to not fail.
    # PM, AMPDU, buffer settings—let ESPHome use its defaults; overriding them
    # previously caused both PM linking errors and redefinition warnings.
    cg.add_platformio_option("build_flags", [FLAG_CSI, FLAG_BA_WIN])
