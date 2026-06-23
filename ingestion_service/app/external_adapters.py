from typing import Any

from .models import NormalizedRecord

def _required(mapping: dict[str, Any], key: str, path: str) -> Any:
    value = mapping.get(key)
    if value is None:
        raise ValueError(f"Missing required field '{path}'.")
    return value

def _required_dict(mapping: dict[str, Any], key: str, path: str) -> dict[str, Any]:
    value = _required(mapping, key, path)
    if not isinstance(value, dict):
        raise ValueError(f"Field '{path}' must be an object.")
    return value

def _add_optional_measurement(
    measurements: dict[str, float],
    name: str,
    value: Any,
    path: str,
) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Field '{path}' must be numeric if present.")
    measurements[name] = float(value)


def _require_non_empty_measurements(measurements: dict[str, float]) -> None:
    if not measurements:
        raise ValueError("External message does not contain any valid numeric measurements.")


def adapt_vendor_reactor_v1(message: dict) -> NormalizedRecord:
    device = _required_dict(message, "device", "device")
    telemetry = _required_dict(message, "telemetry", "telemetry")
    status = _required_dict(message, "status", "status")

    measurements: dict[str, float] = {}
    _add_optional_measurement(
        measurements,
        "temperature",
        telemetry.get("temperatureCelsius"),
        "telemetry.temperatureCelsius",
    )
    _add_optional_measurement(
        measurements, "pressure", telemetry.get("pressureBar"), "telemetry.pressureBar"
    )
    _add_optional_measurement(
        measurements, "pv", telemetry.get("processValue"), "telemetry.processValue"
    )
    _add_optional_measurement(
        measurements, "op", telemetry.get("outputPercent"), "telemetry.outputPercent"
    )
    _add_optional_measurement(
        measurements,
        "setpoint",
        telemetry.get("setpointCelsius"),
        "telemetry.setpointCelsius",
    )
    _require_non_empty_measurements(measurements)

    return NormalizedRecord(
        source_id=_required(device, "id", "device.id"),
        source_type="reactor",
        protocol_hint="HTTP",
        event_time=_required(telemetry, "time", "telemetry.time"),
        quality=_required(status, "quality", "status.quality"),
        event_type=status.get("event", "normal"),
        sequence_no=_required(message, "sequence", "sequence"),
        measurements=measurements,
        attributes={
            "state": _required(status, "state", "status.state"),
            "operation_mode": _required(status, "mode", "status.mode"),
            "batch_id": _required(status, "batch", "status.batch"),
        },
    )

def adapt_vendor_compressor_v2(message: dict) -> NormalizedRecord:
    telemetry = message.get("telemetry", [])
    if telemetry is None or not isinstance(telemetry, list):
        raise ValueError("Field 'telemetry' must be a list.")

    measurements: dict[str, float] = {}
    supported_tags = {
        "TEMP": "temperature",
        "PRESS": "pressure",
        "PV": "pv",
        "OP": "op",
        "RPM": "rpm",
    }
    for item in telemetry:
        if not isinstance(item, dict):
            raise ValueError("Each telemetry item must be an object.")
        tag = _required(item, "tag", "telemetry[].tag")
        measurement_name = supported_tags.get(tag)
        if measurement_name is not None:
            _add_optional_measurement(
                measurements,
                measurement_name,
                item.get("value"),
                f"telemetry[{tag}].value",
            )
    _require_non_empty_measurements(measurements)

    control = _required_dict(message, "control", "control")
    health = _required_dict(message, "health", "health")

    return NormalizedRecord(
        source_id=_required(message, "assetId", "assetId"),
        source_type="compressor",
        protocol_hint="MQTT",
        event_time=_required(message, "sentAt", "sentAt"),
        quality=_required(health, "qualityCode", "health.qualityCode"),
        event_type=_required(health, "eventCode", "health.eventCode"),
        sequence_no=_required(message, "sequenceNumber", "sequenceNumber"),
        measurements=measurements,
        attributes={
            "state": _required(message, "deviceState", "deviceState"),
            "control_mode": _required(control, "mode", "control.mode"),
            "zone": _required(control, "area", "control.area"),
        },
    )

def adapt_opcua_tank_gateway(message: dict) -> NormalizedRecord:
    source = _required_dict(message, "source", "source")
    meta = _required_dict(message, "meta", "meta")
    data = message.get("data", {})
    if data is None or not isinstance(data, dict):
        raise ValueError("Field 'data' must be an object.")

    measurements: dict[str, float] = {}
    _add_optional_measurement(
        measurements, "temperature", data.get("Process.TankTemp"), "data.Process.TankTemp"
    )
    _add_optional_measurement(
        measurements,
        "pressure",
        data.get("Process.LinePressure"),
        "data.Process.LinePressure",
    )
    _add_optional_measurement(
        measurements, "level", data.get("Process.LevelPct"), "data.Process.LevelPct"
    )
    _add_optional_measurement(
        measurements, "pv", data.get("Controller.PV"), "data.Controller.PV"
    )
    _add_optional_measurement(
        measurements, "mv", data.get("Controller.MV"), "data.Controller.MV"
    )
    _require_non_empty_measurements(measurements)

    return NormalizedRecord(
        source_id=_required(source, "id", "source.id"),
        source_type="tank",
        protocol_hint="OPCUA",
        event_time=_required(message, "timestamp", "timestamp"),
        quality=_required(meta, "quality", "meta.quality"),
        event_type=_required(meta, "event", "meta.event"),
        sequence_no=_required(meta, "sequence", "meta.sequence"),
        measurements=measurements,
        attributes={
            "state": _required(meta, "state", "meta.state"),
            "product_type": _required(meta, "product", "meta.product"),
            "line_id": _required(source, "line", "source.line"),
        },
    )

def adapt_vendor_pump_v1(message: dict) -> NormalizedRecord:
    pump = _required_dict(message, "pump", "pump")
    readings = _required_dict(message, "readings", "readings")
    status = _required_dict(message, "status", "status")

    source_id = _required(pump, "id", "pump.id")
    area = _required(pump, "area", "pump.area")
    event_time = _required(message, "timestamp", "timestamp")
    quality = _required(status, "quality", "status.quality")
    state = _required(status, "state", "status.state")
    event_type = _required(status, "event", "status.event")
    sequence_no = _required(message, "sequence", "sequence")

    measurements: dict[str, float] = {}
    _add_optional_measurement(
        measurements, "flow_rate", readings.get("flowRateM3h"), "readings.flowRateM3h"
    )
    _add_optional_measurement(
        measurements, "pressure", readings.get("pressureBar"), "readings.pressureBar"
    )
    _add_optional_measurement(
        measurements, "vibration", readings.get("vibrationMmS"), "readings.vibrationMmS"
    )
    _add_optional_measurement(
        measurements,
        "motor_current",
        readings.get("motorCurrentA"),
        "readings.motorCurrentA",
    )
    _require_non_empty_measurements(measurements)

    return NormalizedRecord(
        source_id=source_id,
        source_type="pump",
        protocol_hint="HTTP",
        event_time=event_time,
        quality=quality,
        event_type=event_type,
        sequence_no=sequence_no,
        measurements=measurements,
        attributes={
            "state": state,
            "area": area,
        },
    )

EXTERNAL_ADAPTER_REGISTRY = {
    "vendor_reactor_v1": adapt_vendor_reactor_v1,
    "vendor_compressor_v2": adapt_vendor_compressor_v2,
    "opcua_tank_gateway": adapt_opcua_tank_gateway,
    "vendor_pump_v1": adapt_vendor_pump_v1,
}

def adapt_external_message(message: dict) -> NormalizedRecord:
    if not isinstance(message, dict):
        raise ValueError("External message must be a dictionary.")

    schema_type = message.get("schema_type")
    if schema_type is None:
        raise ValueError("Missing required field 'schema_type'.")

    adapter = EXTERNAL_ADAPTER_REGISTRY.get(schema_type)
    if adapter is None:
        raise ValueError(f"Unknown external schema_type '{schema_type}'.")

    return adapter(message)
