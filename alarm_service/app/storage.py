from proto.generated import alarm_pb2, normalized_pb2

from .db import AlarmEventRow, SessionLocal


def save_alarm_events(
    record: normalized_pb2.NormalizedRecordMessage,
    alarms: list[alarm_pb2.AlarmMessage],
) -> None:
    if not alarms:
        return
    rows = [
        AlarmEventRow(
            source_id=record.source_id,
            source_type=record.source_type,
            event_time=record.event_time,
            quality=record.quality,
            event_type=record.event_type,
            sequence_no=record.sequence_no,
            alarm_code=alarm.code,
            severity=alarm.severity,
            message=alarm.message,
            measurements=dict(record.measurements),
            attributes=dict(record.attributes),
        )
        for alarm in alarms
    ]

    with SessionLocal() as session:
        session.add_all(rows)
        session.commit()
