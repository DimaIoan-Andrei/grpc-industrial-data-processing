from proto.generated import alarm_pb2, normalized_pb2


def evaluate_alarms(
    record: normalized_pb2.NormalizedRecordMessage,
) -> list[alarm_pb2.AlarmMessage]:
    alarms: list[alarm_pb2.AlarmMessage] = []
    measurements = record.measurements
    attributes = record.attributes

    def add_alarm(code: str, severity: str, message: str) -> None:
        alarms.append(
            alarm_pb2.AlarmMessage(
                code=code,
                severity=severity,
                message=message,
            )
        )

    if record.source_type == "reactor":
        if "temperature" in measurements and measurements["temperature"] > 90:
            add_alarm(
                "HIGH_TEMPERATURE",
                "HIGH",
                "Reactor temperature is above 90.",
            )
        if "pressure" in measurements and measurements["pressure"] > 4.2:
            add_alarm(
                "HIGH_PRESSURE",
                "HIGH",
                "Reactor pressure is above 4.2.",
            )
        if record.quality == "BAD":
            add_alarm(
                "BAD_DATA_QUALITY",
                "MEDIUM",
                "Reactor data quality is BAD.",
            )

    if record.source_type == "compressor":
        if "pressure" in measurements and measurements["pressure"] < 5.0:
            add_alarm(
                "LOW_PRESSURE",
                "HIGH",
                "Compressor pressure is below 5.0.",
            )
        if "rpm" in measurements and measurements["rpm"] > 1800:
            add_alarm(
                "HIGH_RPM",
                "MEDIUM",
                "Compressor RPM is above 1800.",
            )
        if attributes.get("state") == "OVERLOADED":
            add_alarm(
                "OVERLOAD_STATE",
                "HIGH",
                "Compressor state is OVERLOADED.",
            )
        if record.quality == "BAD":
            add_alarm(
                "BAD_DATA_QUALITY",
                "MEDIUM",
                "Compressor data quality is BAD.",
            )

    if record.source_type == "tank":
        if "level" in measurements and measurements["level"] > 78:
            add_alarm(
                "HIGH_LEVEL",
                "HIGH",
                "Tank level is above 78.",
            )
        if attributes.get("state") == "CONTROL_STUCK":
            add_alarm(
                "CONTROL_STUCK",
                "MEDIUM",
                "Tank control state is CONTROL_STUCK.",
            )
        if record.quality == "BAD":
            add_alarm(
                "INCOMPLETE_DATA",
                "MEDIUM",
                "Tank data quality is BAD.",
            )

    if record.source_type == "pump":
        if "flow_rate" in measurements and measurements["flow_rate"] < 20.0:
            add_alarm(
                "LOW_FLOW",
                "HIGH",
                "Pump flow rate is below 20.0 m3/h.",
            )
        if "pressure" in measurements and measurements["pressure"] > 5.0:
            add_alarm(
                "HIGH_PRESSURE",
                "HIGH",
                "Pump pressure is above 5.0 bar.",
            )
        if "vibration" in measurements and measurements["vibration"] > 6.0:
            add_alarm(
                "HIGH_VIBRATION",
                "HIGH",
                "Pump vibration is above 6.0 mm/s.",
            )
        if "motor_current" in measurements and measurements["motor_current"] > 18.0:
            add_alarm(
                "HIGH_MOTOR_CURRENT",
                "MEDIUM",
                "Pump motor current is above 18.0 A.",
            )
        if record.quality == "BAD":
            add_alarm(
                "BAD_DATA_QUALITY",
                "MEDIUM",
                "Pump data quality is BAD.",
            )

    return alarms
