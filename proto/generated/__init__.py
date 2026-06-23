import sys

from . import normalized_pb2

sys.modules.setdefault("normalized_pb2", normalized_pb2)

from . import alarm_pb2

sys.modules.setdefault("alarm_pb2", alarm_pb2)
