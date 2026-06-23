from __future__ import annotations
import argparse
import math
import os
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional
import requests
import simpy
import simpy.rt

@dataclass
class EmittedRecord:
    source_id: str
    equipment_type: str
    protocol_hint: str
    ts_ms: int
    iso_ts: str
    payload: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

class BaseSource(ABC):
    def __init__(
        self,
        env: simpy.Environment,
        source_id: str,
        equipment_type: str,
        protocol_hint: str,
        emit_every_s: float,
        rng: random.Random,
        sink: Callable[[EmittedRecord], None],
        anomaly_probability: float = 0.02,
    ) -> None:
        self.env = env
        self.source_id = source_id
        self.equipment_type = equipment_type
        self.protocol_hint = protocol_hint
        self.emit_every_s = emit_every_s
        self.rng = rng
        self.sink = sink
        self.anomaly_probability = anomaly_probability
        self.base_time = datetime.now(timezone.utc)

        self.seq = 0
        self.current_state: Dict[str, float] = {}
        self.env.process(self.run())

    def current_dt(self) -> datetime:
        return self.base_time + timedelta(seconds=self.env.now)

    def now_ms(self) -> int:
        return int(self.current_dt().timestamp() * 1000)

    def now_iso(self) -> str:
        return self.current_dt().isoformat()

    def add_noise(self, value: float, sigma: float) -> float:
        return value + self.rng.gauss(0, sigma)

    def bounded(self, value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def should_inject_anomaly(self) -> bool:
        return self.rng.random() < self.anomaly_probability

    def build_record(self, payload: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> EmittedRecord:
        return EmittedRecord(
            source_id=self.source_id,
            equipment_type=self.equipment_type,
            protocol_hint=self.protocol_hint,
            ts_ms=self.now_ms(),
            iso_ts=self.now_iso(),
            payload=payload,
            metadata=metadata or {},
        )

    def run(self):
        while True:
            payload, metadata = self.generate_payload()
            record = self.build_record(payload, metadata)
            self.sink(record)
            self.seq += 1
            yield self.env.timeout(self.emit_every_s)

    @abstractmethod
    def generate_payload(self) -> tuple[Dict[str, Any], Dict[str, Any]]:
        raise NotImplementedError

class ReactorSource(BaseSource):
    """
    Sursă tip reactor termic..
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.current_state = {
            "temperature": 82.0,
            "pressure": 3.4,
            "pv": 81.5,
            "op": 58.0,
            "setpoint": 85.0,
        }

    def generate_payload(self) -> tuple[Dict[str, Any], Dict[str, Any]]:
        phase = self.env.now / 60.0

        # OP variază lent, ca și cum un regulator ar ajusta comanda
        op_target = 58.0 + 6.0 * math.sin(phase / 2.5)
        self.current_state["op"] += (op_target - self.current_state["op"]) * 0.15
        self.current_state["op"] = self.add_noise(self.current_state["op"], 0.3)
        self.current_state["op"] = self.bounded(self.current_state["op"], 35.0, 80.0)

        # PV urmărește OP cu inerție
        pv_target = 74.0 + 0.18 * self.current_state["op"]
        self.current_state["pv"] += (pv_target - self.current_state["pv"]) * 0.12
        self.current_state["pv"] = self.add_noise(self.current_state["pv"], 0.2)

        # Temperatura urmează PV
        self.current_state["temperature"] += (self.current_state["pv"] - self.current_state["temperature"]) * 0.08
        self.current_state["temperature"] = self.add_noise(self.current_state["temperature"], 0.15)

        # Presiunea depinde ușor de temperatură și de ciclu
        self.current_state["pressure"] = 3.0 + (self.current_state["temperature"] - 70.0) * 0.03
        self.current_state["pressure"] += 0.12 * math.sin(phase)
        self.current_state["pressure"] = self.add_noise(self.current_state["pressure"], 0.03)

        quality = "GOOD"
        event = "normal"
        attributes = {
            "state": "RUNNING",
            "operation_mode": "AUTO",
            "batch_id": f"BATCH-{int(self.env.now // 300) + 1:03d}",
        }

        if self.should_inject_anomaly():
            anomaly_type = self.rng.choice(["temp_spike", "pressure_spike", "sensor_dropout"])
            event = anomaly_type
            if anomaly_type == "temp_spike":
                self.current_state["temperature"] += self.rng.uniform(8.0, 15.0)
                self.current_state["pv"] += self.rng.uniform(5.0, 8.0)
                quality = "SUSPECT"
                attributes["state"] = "ALARM"
            elif anomaly_type == "pressure_spike":
                self.current_state["pressure"] += self.rng.uniform(0.8, 1.8)
                quality = "SUSPECT"
                attributes["state"] = "ALARM"
            elif anomaly_type == "sensor_dropout":
                quality = "BAD"
                attributes["state"] = "DEGRADED"
                payload = {
                    "schema_type": "vendor_reactor_v1",
                    "device": {
                        "id": self.source_id,
                        "type": "chemical_reactor",
                    },
                    "telemetry": {
                        "time": self.now_iso(),
                        "temperatureCelsius": None,
                        "pressureBar": round(self.current_state["pressure"], 3),
                        "processValue": round(self.current_state["pv"], 3),
                        "outputPercent": round(self.current_state["op"], 3),
                        "setpointCelsius": self.current_state["setpoint"],
                    },
                    "status": {
                        "quality": quality,
                        "state": attributes["state"],
                        "mode": attributes["operation_mode"],
                        "batch": attributes["batch_id"],
                        "event": event,
                    },
                    "sequence": self.seq,
                }
                return payload, {"quality": quality, "event": event, "seq": self.seq}

        payload = {
            "schema_type": "vendor_reactor_v1",
            "device": {
                "id": self.source_id,
                "type": "chemical_reactor",
            },
            "telemetry": {
                "time": self.now_iso(),
                "temperatureCelsius": round(self.current_state["temperature"], 3),
                "pressureBar": round(self.current_state["pressure"], 3),
                "processValue": round(self.current_state["pv"], 3),
                "outputPercent": round(self.current_state["op"], 3),
                "setpointCelsius": self.current_state["setpoint"],
            },
            "status": {
                "quality": quality,
                "state": attributes["state"],
                "mode": attributes["operation_mode"],
                "batch": attributes["batch_id"],
                "event": event,
            },
            "sequence": self.seq,
        }
        return payload, {"quality": quality, "event": event, "seq": self.seq}

class CompressorSource(BaseSource):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.current_state = {
            "temperature": 65.0,
            "pressure": 5.6,
            "PV": 64.0,
            "OP": 47.0,
            "rpm": 1450.0,
        }

    def generate_payload(self) -> tuple[Dict[str, Any], Dict[str, Any]]:
        load_factor = 1.0 + 0.12 * math.sin(self.env.now / 45.0)

        self.current_state["OP"] += self.rng.gauss(0, 0.45)
        self.current_state["OP"] = self.bounded(self.current_state["OP"] * load_factor, 25.0, 90.0)

        self.current_state["PV"] += (60.0 + self.current_state["OP"] * 0.16 - self.current_state["PV"]) * 0.18
        self.current_state["PV"] = self.add_noise(self.current_state["PV"], 0.25)

        self.current_state["temperature"] += (self.current_state["PV"] - self.current_state["temperature"]) * 0.1
        self.current_state["temperature"] = self.add_noise(self.current_state["temperature"], 0.12)

        self.current_state["pressure"] = 4.8 + self.current_state["OP"] * 0.022
        self.current_state["pressure"] = self.add_noise(self.current_state["pressure"], 0.04)

        self.current_state["rpm"] = 1200.0 + self.current_state["OP"] * 8.5
        self.current_state["rpm"] = self.add_noise(self.current_state["rpm"], 4.0)

        quality = "GOOD"
        event = "normal"
        attributes = {
            "state": "RUNNING",
            "control_mode": "AUTO",
            "zone": "COMP_AREA_A",
        }

        if self.should_inject_anomaly():
            anomaly_type = self.rng.choice(["overload", "pressure_drop"])
            event = anomaly_type
            quality = "SUSPECT"
            if anomaly_type == "overload":
                self.current_state["temperature"] += self.rng.uniform(5.0, 10.0)
                self.current_state["rpm"] += self.rng.uniform(80.0, 140.0)
                attributes["state"] = "OVERLOADED"
            elif anomaly_type == "pressure_drop":
                self.current_state["pressure"] -= self.rng.uniform(0.7, 1.2)
                attributes["state"] = "LOW_PRESSURE"

        payload = {
            "schema_type": "vendor_compressor_v2",
            "assetId": self.source_id,
            "sentAt": self.now_iso(),
            "telemetry": [
                {"tag": "TEMP", "value": round(self.current_state["temperature"], 3)},
                {"tag": "PRESS", "value": round(self.current_state["pressure"], 3)},
                {"tag": "PV", "value": round(self.current_state["PV"], 3)},
                {"tag": "OP", "value": round(self.current_state["OP"], 3)},
                {"tag": "RPM", "value": round(self.current_state["rpm"], 1)},
            ],
            "deviceState": attributes["state"],
            "control": {
                "mode": attributes["control_mode"],
                "area": attributes["zone"],
            },
            "health": {
                "qualityCode": quality,
                "eventCode": event,
            },
            "sequenceNumber": self.seq,
        }
        return payload, {"quality": quality, "event": event, "seq": self.seq}

class PumpSource(BaseSource):

    def __init__(self, *args, area: str = "PUMP_AREA_B", **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.area = area
        self.current_state = {
            "flow_rate": 42.0,
            "pressure": 2.8,
            "vibration": 3.0,
            "motor_current": 12.0,
        }

    def generate_payload(self) -> tuple[Dict[str, Any], Dict[str, Any]]:
        phase = self.env.now / 50.0
        load_factor = 1.0 + 0.08 * math.sin(phase / 2.0)

        flow_target = 42.0 + 4.0 * math.sin(phase)
        self.current_state["flow_rate"] += (
            flow_target - self.current_state["flow_rate"]
        ) * 0.18
        self.current_state["flow_rate"] = self.add_noise(
            self.current_state["flow_rate"], 0.35
        )
        self.current_state["flow_rate"] = self.bounded(
            self.current_state["flow_rate"], 12.0, 60.0
        )

        self.current_state["pressure"] = 1.9 + self.current_state["flow_rate"] * 0.022
        self.current_state["pressure"] *= load_factor
        self.current_state["pressure"] = self.add_noise(
            self.current_state["pressure"], 0.04
        )

        self.current_state["vibration"] += self.rng.gauss(0, 0.08)
        self.current_state["vibration"] = self.bounded(
            self.current_state["vibration"], 1.5, 5.5
        )

        self.current_state["motor_current"] = (
            7.6 + self.current_state["flow_rate"] * 0.105
        )
        self.current_state["motor_current"] *= load_factor
        self.current_state["motor_current"] = self.add_noise(
            self.current_state["motor_current"], 0.18
        )

        quality = "GOOD"
        event = "normal"
        state = "RUNNING"
        vibration_value: Optional[float] = round(self.current_state["vibration"], 3)

        if self.should_inject_anomaly():
            anomaly_type = self.rng.choice(
                ["low_flow", "high_vibration", "motor_overcurrent", "sensor_dropout"]
            )
            event = anomaly_type
            if anomaly_type == "low_flow":
                self.current_state["flow_rate"] = self.rng.uniform(12.0, 18.5)
                quality = "SUSPECT"
                state = "LOW_FLOW"
            elif anomaly_type == "high_vibration":
                self.current_state["vibration"] = self.rng.uniform(6.2, 8.5)
                vibration_value = round(self.current_state["vibration"], 3)
                quality = "SUSPECT"
                state = "VIBRATION_ALARM"
            elif anomaly_type == "motor_overcurrent":
                self.current_state["motor_current"] = self.rng.uniform(18.5, 22.0)
                quality = "SUSPECT"
                state = "OVERCURRENT"
            elif anomaly_type == "sensor_dropout":
                vibration_value = None
                quality = "BAD"
                state = "DEGRADED"

        payload = {
            "schema_type": "vendor_pump_v1",
            "pump": {
                "id": self.source_id,
                "area": self.area,
            },
            "readings": {
                "flowRateM3h": round(self.current_state["flow_rate"], 3),
                "pressureBar": round(self.current_state["pressure"], 3),
                "vibrationMmS": vibration_value,
                "motorCurrentA": round(self.current_state["motor_current"], 3),
            },
            "status": {
                "quality": quality,
                "state": state,
                "event": event,
            },
            "timestamp": self.now_iso(),
            "sequence": self.seq,
        }
        return payload, {"quality": quality, "event": event, "seq": self.seq}


class TankSource(BaseSource):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.current_state = {
            "level": 72.0,
            "temperature": 24.0,
            "pressure": 1.3,
            "pv": 71.0,
            "mv": 34.0,
        }

    def generate_payload(self) -> tuple[Dict[str, Any], Dict[str, Any]]:
        inflow = 0.45 + 0.05 * math.sin(self.env.now / 120.0)
        outflow = 0.40 + self.current_state["mv"] * 0.0018

        self.current_state["level"] += inflow - outflow
        self.current_state["level"] = self.add_noise(self.current_state["level"], 0.08)
        self.current_state["level"] = self.bounded(self.current_state["level"], 40.0, 95.0)

        self.current_state["mv"] += self.rng.gauss(0, 0.25)
        self.current_state["mv"] = self.bounded(self.current_state["mv"], 15.0, 60.0)

        self.current_state["pv"] += (self.current_state["level"] - self.current_state["pv"]) * 0.2
        self.current_state["pv"] = self.add_noise(self.current_state["pv"], 0.1)

        self.current_state["temperature"] += self.rng.gauss(0, 0.05)
        self.current_state["pressure"] = 1.1 + (self.current_state["level"] - 40.0) * 0.005
        self.current_state["pressure"] = self.add_noise(self.current_state["pressure"], 0.015)

        quality = "GOOD"
        event = "normal"
        attributes = {
            "state": "STABLE",
            "product_type": "PROCESS_WATER",
            "line_id": "LINE_1",
        }

        if self.should_inject_anomaly():
            anomaly_type = self.rng.choice(["level_high", "stuck_mv", "missing_branch"])
            event = anomaly_type
            quality = "SUSPECT"
            if anomaly_type == "level_high":
                self.current_state["level"] += self.rng.uniform(6.0, 10.0)
                self.current_state["pv"] += self.rng.uniform(5.0, 8.0)
                attributes["state"] = "HIGH_LEVEL"
            elif anomaly_type == "stuck_mv":
                self.current_state["mv"] = 35.0
                attributes["state"] = "CONTROL_STUCK"
            elif anomaly_type == "missing_branch":
                attributes["state"] = "PARTIAL_DATA"
                payload = {
                    "schema_type": "opcua_tank_gateway",
                    "nodeId": "ns=2;s=Tank01",
                    "source": {
                        "id": self.source_id,
                        "line": attributes["line_id"],
                    },
                    "timestamp": self.now_iso(),
                    "data": {
                        "Process.TankTemp": round(self.current_state["temperature"], 3),
                        "Process.LinePressure": round(self.current_state["pressure"], 3),
                        "Process.LevelPct": round(self.current_state["level"], 3),
                    },
                    "meta": {
                        "quality": "BAD",
                        "state": attributes["state"],
                        "product": attributes["product_type"],
                        "event": event,
                        "sequence": self.seq,
                    },
                }
                return payload, {"quality": "BAD", "event": event, "seq": self.seq}

        payload = {
            "schema_type": "opcua_tank_gateway",
            "nodeId": "ns=2;s=Tank01",
            "source": {
                "id": self.source_id,
                "line": attributes["line_id"],
            },
            "timestamp": self.now_iso(),
            "data": {
                "Process.TankTemp": round(self.current_state["temperature"], 3),
                "Process.LinePressure": round(self.current_state["pressure"], 3),
                "Process.LevelPct": round(self.current_state["level"], 3),
                "Controller.PV": round(self.current_state["pv"], 3),
                "Controller.MV": round(self.current_state["mv"], 3),
            },
            "meta": {
                "quality": quality,
                "state": attributes["state"],
                "product": attributes["product_type"],
                "event": event,
                "sequence": self.seq,
            },
        }
        return payload, {"quality": quality, "event": event, "seq": self.seq}


class HttpSink:
    def __init__(self, ingest_url: Optional[str] = None) -> None:
        self.ingest_url = ingest_url or os.getenv("INGESTION_URL", "http://localhost:8000/ingest/external")
        self.source_token = os.getenv("INGESTION_API_TOKEN", "dev-source-token")
        self.records: List[EmittedRecord] = []

    def __call__(self, record: EmittedRecord) -> None:
        self.records.append(record)
        response = requests.post(
            self.ingest_url,
            json=record.payload,
            headers={"X-Source-Token": self.source_token},
            timeout=5,
        )
        response.raise_for_status()

class FactorySimulator:
    def __init__(
        self,
        seed: int = 42,
        realtime: bool = False,
        realtime_factor: float = 1.0,
    ) -> None:
        if realtime:
            self.env = simpy.rt.RealtimeEnvironment(
                initial_time=0,
                factor=realtime_factor,
                strict=False,
            )
        else:
            self.env = simpy.Environment(initial_time=0)
        self.rng = random.Random(seed)
        self.sink = HttpSink()
        self.sources: List[BaseSource] = []

    def add_default_sources(self) -> None:
        self.sources.append(
            ReactorSource(
                env=self.env,
                source_id="reactor_01",
                equipment_type="reactor",
                protocol_hint="HTTP",
                emit_every_s=5,
                rng=random.Random(self.rng.randint(1, 10_000)),
                sink=self.sink,
                anomaly_probability=0.03,
            )
        )
        self.sources.append(
            CompressorSource(
                env=self.env,
                source_id="compressor_01",
                equipment_type="compressor",
                protocol_hint="MQTT",
                emit_every_s=3,
                rng=random.Random(self.rng.randint(1, 10_000)),
                sink=self.sink,
                anomaly_probability=0.025,
            )
        )
        self.sources.append(
            TankSource(
                env=self.env,
                source_id="tank_01",
                equipment_type="tank",
                protocol_hint="OPCUA",
                emit_every_s=7,
                rng=random.Random(self.rng.randint(1, 10_000)),
                sink=self.sink,
                anomaly_probability=0.02,
            )
        )
        self.sources.append(
            PumpSource(
                env=self.env,
                source_id="pump_01",
                equipment_type="pump",
                protocol_hint="HTTP",
                emit_every_s=4,
                rng=random.Random(self.rng.randint(1, 10_000)),
                sink=self.sink,
                anomaly_probability=0.025,
                area="PUMP_AREA_B",
            )
        )

    def run(self, until_s: int = 60) -> List[EmittedRecord]:
        self.env.run(until=until_s)
        return self.sink.records

if __name__ == "__main__":
    def read_int_env(name: str, default: int) -> int:
        value = os.getenv(name)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            return default

    def read_float_env(name: str, default: float) -> float:
        value = os.getenv(name)
        if value is None:
            return default
        try:
            parsed = float(value)
        except ValueError:
            return default
        if parsed <= 0:
            return default
        return parsed

    def read_bool_env(name: str, default: bool) -> bool:
        value = os.getenv(name)
        if value is None:
            return default

        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
        return default

    def positive_float(value: str) -> float:
        parsed = float(value)
        if parsed <= 0:
            raise argparse.ArgumentTypeError("must be greater than 0")
        return parsed

    parser = argparse.ArgumentParser(description="Run the industrial source simulator.")
    parser.add_argument(
        "--duration",
        type=int,
        help="Simulation duration in seconds. Overrides SIMULATION_DURATION_SECONDS.",
    )
    parser.add_argument(
        "--realtime",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Use SimPy RealtimeEnvironment. Overrides SIMULATION_REALTIME.",
    )
    parser.add_argument(
        "--factor",
        type=positive_float,
        help="Realtime factor. Overrides SIMULATION_REALTIME_FACTOR.",
    )
    args = parser.parse_args()

    seed = read_int_env("SIMULATION_SEED", 123)
    duration_seconds = (
        args.duration
        if args.duration is not None
        else read_int_env("SIMULATION_DURATION_SECONDS", 60)
    )
    realtime = (
        args.realtime
        if args.realtime is not None
        else read_bool_env("SIMULATION_REALTIME", False)
    )
    realtime_factor = (
        args.factor
        if args.factor is not None
        else read_float_env("SIMULATION_REALTIME_FACTOR", 1.0)
    )

    print(f"Simulation mode: {'realtime' if realtime else 'fast'}")
    print(f"Duration: {duration_seconds} seconds")
    if realtime:
        print(f"Realtime factor: {realtime_factor}")

    sim = FactorySimulator(
        seed=seed,
        realtime=realtime,
        realtime_factor=realtime_factor,
    )
    sim.add_default_sources()
    sim.run(until_s=duration_seconds)
