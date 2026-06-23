from .db import NormalizedRecordRow, SessionLocal
from .models import NormalizedRecord

def save_normalized_record(record: NormalizedRecord) -> None:
    row = NormalizedRecordRow(**record.model_dump())
    with SessionLocal() as session:
        session.add(row)
        session.commit()
