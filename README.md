# Arhitectură distribuită pentru adaptarea, procesarea și monitorizarea datelor industriale

Acest proiect reprezintă un Proof of Concept pentru o arhitectură distribuită bazată pe microservicii, destinată integrării datelor industriale provenite din surse eterogene. Aplicația primește mesaje JSON specifice unor surse sau furnizori diferiți, le adaptează într-un model intern comun, le transmite între servicii prin gRPC și expune metrici operaționale prin Prometheus.

Ideea centrală a proiectului este separarea clară între formatul extern al datelor și modelul intern folosit de platformă. Sursele externe pot transmite structuri JSON diferite, iar serviciul de ingestie folosește un mecanism de adaptoare pentru a transforma aceste mesaje într-un `NormalizedRecord` comun.

---

## 1. Scopul proiectului

Scopul proiectului este demonstrarea unei platforme extensibile pentru integrarea datelor industriale eterogene. Într-un mediu real, echipamentele, gateway-urile sau API-urile furnizorilor pot trimite date în structuri diferite. Platforma propusă rezolvă această problemă printr-un strat de adaptare care transformă mesajele externe într-un model intern unificat.

Proiectul urmărește:

* primirea datelor externe prin HTTP;
* autentificarea surselor printr-un token static;
* identificarea formatului mesajului prin `schema_type`;
* adaptarea mesajelor vendor-specific într-un model intern comun `NormalizedRecord`;
* acceptarea măsurătorilor parțiale în cazuri realiste de tip `sensor_dropout` sau `missing_branch`;
* transmiterea internă a datelor prin gRPC și Protobuf;
* persistarea datelor normalizate în PostgreSQL;
* evaluarea regulilor de alarmare într-un microserviciu separat;
* persistarea alarmelor generate;
* expunerea metricilor prin Prometheus;
* rularea reproductibilă a platformei prin Docker Compose.

---

## 2. Arhitectură generală



```text
Vendor-specific JSON / External Source
        |
        | HTTP + X-Source-Token
        v
Ingestion Service
        |
        | schema_type -> External Adapter Registry
        v
NormalizedRecord
   |                         |
   | gRPC                    | gRPC
   v                         v
Historian Service        Alarm Service
   |                         |
   v                         v
PostgreSQL              PostgreSQL

Prometheus scrape:
- ingestion-service
- historian-service
- alarm-service
```

Platforma principală este formată din:

* `ingestion-service`
* `historian-service`
* `alarm-service`
* `postgres`
* `prometheus`

Simulatorul este tratat ca instrument extern de testare și demonstrație. El nu pornește implicit cu platforma, ci este disponibil prin profilul Docker Compose `simulation` sau prin comandă separată.

---

## 3. Structura proiectului

```text
.
├── alarm_service/
│   ├── app/
│   ├── Dockerfile
│   └── requirements.txt
│
├── historian_service/
│   ├── app/
│   ├── Dockerfile
│   └── requirements.txt
│
├── ingestion/
│   ├── app/
│   ├── Dockerfile
│   └── requirements.txt
│
├── proto/
│   ├── alarm.proto
│   ├── normalized.proto
│   └── generated/
│
├── simulator/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── simulator_service.py
│
├── prometheus/
│   └── prometheus.yml
│
├── docker-compose.yml
├── .env.example
├── .gitignore
└── requirements.txt
```

### Rolul folderelor principale

| Folder               | Rol                                                                                                 |
| -------------------- | --------------------------------------------------------------------------------------------------- |
| `ingestion/`         | Serviciu HTTP pentru primirea, autentificarea și adaptarea mesajelor externe în `NormalizedRecord`. |
| `historian_service/` | Serviciu gRPC pentru persistarea datelor normalizate în PostgreSQL.                                 |
| `alarm_service/`     | Serviciu gRPC pentru evaluarea regulilor de alarmare și persistarea alarmelor.                      |
| `proto/`             | Contracte Protobuf/gRPC comune între servicii.                                                      |
| `simulator/`         | Generator de mesaje vendor-specific, folosit pentru testare și demonstrație.                        |
| `prometheus/`        | Configurația Prometheus pentru colectarea metricilor.                                               |

Fișierul `requirements.txt` din root este folosit pentru dezvoltare locală și generarea codului gRPC/Protobuf. Fiecare serviciu are propriul `requirements.txt` pentru dependențele necesare în container.

---

## 4. Fluxul de date

Fluxul principal al aplicației este:

```text
Vendor JSON -> Ingestion Adapter -> NormalizedRecord -> gRPC -> Historian + Alarm Service
```

1. O sursă externă trimite un mesaj JSON către `POST /ingest/external`.
2. Mesajul conține câmpul `schema_type`, care indică structura sau furnizorul mesajului.
3. `ingestion-service` selectează adaptorul potrivit din registry.
4. Adaptorul transformă mesajul extern într-un `NormalizedRecord`.
5. `NormalizedRecord` este transmis prin gRPC către:

   * `historian-service`, pentru stocare;
   * `alarm-service`, pentru evaluarea regulilor de alarmare.
6. Datele și alarmele sunt persistate în PostgreSQL.
7. Serviciile expun metrici care sunt colectate de Prometheus.

### Tratarea datelor parțiale

În scenarii industriale reale, unele valori pot lipsi temporar din cauza unui senzor defect, a unei întreruperi de comunicație sau a unui gateway care nu transmite toate ramurile de date. Din acest motiv, adaptoarele permit măsurători parțiale: câmpurile de identificare, timp, calitate și eveniment rămân obligatorii, dar valorile numerice din `measurements` sunt adăugate doar dacă există și sunt valide.

Exemple:

* la `sensor_dropout`, reactorul poate transmite `temperatureCelsius = null`, iar `NormalizedRecord.measurements` va conține celelalte măsurători disponibile;
* la `missing_branch`, tank-ul poate transmite doar valorile de proces, fără `Controller.PV` și `Controller.MV`;
* regulile de alarmare verifică explicit existența unei măsurători înainte de aplicarea pragurilor, pentru a evita alarme false generate de valori lipsă.

---

## 5. Servicii componente

### 5.1 Ingestion Service

Serviciul de ingestie este punctul de intrare în sistem.

Responsabilități:

* expune endpointul `POST /ingest/external`;
* validează headerul `X-Source-Token`;
* primește mesaje JSON specifice unor surse/furnizori diferiți;
* identifică schema mesajului prin `schema_type`;
* aplică adaptorul corespunzător;
* construiește modelul intern `NormalizedRecord`;
* acceptă măsurători parțiale atunci când datele sunt marcate ca degradate sau incomplete;
* trimite datele normalizate către `historian-service` prin gRPC;
* trimite datele normalizate către `alarm-service` prin gRPC;
* expune metrici Prometheus la `/metrics`.

Endpointuri:

| Endpoint                | Descriere                                                       |
| ----------------------- | --------------------------------------------------------------- |
| `GET /health`           | Verificare simplă de disponibilitate.                           |
| `POST /ingest/external` | Primire mesaje JSON vendor-specific. Necesită `X-Source-Token`. |
| `GET /metrics`          | Metrici în format Prometheus.                                   |

### 5.2 External Adapter Registry

`ingestion-service` folosește un registry de adaptoare externe. Fiecare adaptor este responsabil pentru transformarea unui anumit tip de mesaj extern în `NormalizedRecord`.

Scheme suportate:

| `schema_type`          | Sursă simulată    | Rol                                                             |
| ---------------------- | ----------------- | --------------------------------------------------------------- |
| `vendor_reactor_v1`    | Reactor           | Mesaj JSON de tip API vendor.                                   |
| `vendor_compressor_v2` | Compresor         | Mesaj JSON de tip telemetry/MQTT.                               |
| `opcua_tank_gateway`   | Rezervor/tank     | Mesaj JSON provenit dintr-un gateway OPC UA.                    |
| `vendor_pump_v1`       | Pompă industrială | Mesaj JSON de tip API vendor pentru validarea extensibilității. |

Mecanismul este extensibil. Pentru o nouă sursă se poate adăuga un nou adaptor și o nouă intrare în registry, fără modificarea serviciilor din aval.

### 5.3 Historian Service

Serviciul historian primește date normalizate prin gRPC și le persistă în PostgreSQL.

Responsabilități:

* implementează serviciul gRPC `HistorianService`;
* primește mesaje `NormalizedRecordMessage`;
* persistă datele în tabela `normalized_records`;
* salvează `measurements` și `attributes` ca JSONB;
* expune metrici Prometheus pe portul `9101`.

Metrici principale:

* `historian_records_stored_total`
* `historian_store_errors_total`

### 5.4 Alarm Service

Serviciul de alarmare primește date normalizate prin gRPC, aplică reguli simple și persistă alarmele generate.

Responsabilități:

* implementează serviciul gRPC `AlarmService`;
* evaluează reguli pentru reactor, compresor, tank și pompă;
* verifică existența unei măsurători înainte de aplicarea unui prag numeric;
* generează alarme cu cod, severitate și mesaj;
* persistă alarmele în tabela `alarm_events`;
* expune metrici Prometheus pe portul `9102`.

Metrici principale:

* `alarm_records_evaluated_total`
* `alarm_events_generated_total`
* `alarm_events_by_code_total{code="...", severity="..."}`
* `alarm_persistence_errors_total`

Exemple de reguli:

| Sursă     | Regulă                  | Alarmă               |
| --------- | ----------------------- | -------------------- |
| Reactor   | `temperature > 90`      | `HIGH_TEMPERATURE`   |
| Reactor   | `pressure > 4.2`        | `HIGH_PRESSURE`      |
| Compresor | `pressure < 5.0`        | `LOW_PRESSURE`       |
| Compresor | `rpm > 1700`            | `HIGH_RPM`           |
| Tank      | `level > 78`            | `HIGH_LEVEL`         |
| Tank      | `state = CONTROL_STUCK` | `CONTROL_STUCK`      |
| Pompă     | `flow_rate < 20.0`      | `LOW_FLOW`           |
| Pompă     | `pressure > 5.0`        | `HIGH_PRESSURE`      |
| Pompă     | `vibration > 6.0`       | `HIGH_VIBRATION`     |
| Pompă     | `motor_current > 18.0`  | `HIGH_MOTOR_CURRENT` |

### 5.5 Simulator Service

Simulatorul generează mesaje JSON diferite pentru patru surse industriale:

* reactor;
* compresor;
* rezervor / tank;
* pompă industrială.

El emulează surse externe cu structuri diferite, nu un format unic prestabilit. Acest lucru permite demonstrarea mecanismului de adaptare din `ingestion-service`.

Important: simulatorul nu este considerat componentă internă obligatorie a platformei. El este un instrument de testare și demonstrație, echivalent cu o sursă externă de date.

### 5.6 Prometheus

Prometheus colectează metricile expuse de serviciile principale:

* `ingestion-service:8000/metrics`
* `historian-service:9101/metrics`
* `alarm-service:9102/metrics`

Configurația se află în:

```text
prometheus/prometheus.yml
```

Intervalul de scrape este configurat la 5 secunde.

---

## 6. Exemple de mesaje externe

### Reactor — `vendor_reactor_v1`

```json
{
  "schema_type": "vendor_reactor_v1",
  "device": {
    "id": "reactor_01",
    "type": "chemical_reactor"
  },
  "telemetry": {
    "time": "2026-05-08T16:30:23.256578+00:00",
    "temperatureCelsius": 86.833,
    "pressureBar": 3.453,
    "processValue": 83.934,
    "outputPercent": 54.227,
    "setpointCelsius": 85.0
  },
  "status": {
    "quality": "GOOD",
    "state": "RUNNING",
    "mode": "AUTO",
    "batch": "BATCH-002",
    "event": "normal"
  },
  "sequence": 119
}
```

### Compresor — `vendor_compressor_v2`

```json
{
  "schema_type": "vendor_compressor_v2",
  "assetId": "compressor_01",
  "sentAt": "2026-05-08T16:30:25.256608+00:00",
  "telemetry": [
    {"tag": "TEMP", "value": 64.118},
    {"tag": "PRESS", "value": 5.632},
    {"tag": "PV", "value": 64.655},
    {"tag": "OP", "value": 35.88},
    {"tag": "RPM", "value": 1513.3}
  ],
  "deviceState": "RUNNING",
  "control": {
    "mode": "AUTO",
    "area": "COMP_AREA_A"
  },
  "health": {
    "qualityCode": "GOOD",
    "eventCode": "normal"
  },
  "sequenceNumber": 199
}
```

### Tank — `opcua_tank_gateway`

```json
{
  "schema_type": "opcua_tank_gateway",
  "nodeId": "ns=2;s=Tank01",
  "source": {
    "id": "tank_01",
    "line": "LINE_1"
  },
  "timestamp": "2026-05-08T16:30:27.256608+00:00",
  "data": {
    "Process.TankTemp": 24.235,
    "Process.LinePressure": 1.256,
    "Process.LevelPct": 72.339,
    "Controller.PV": 72.227,
    "Controller.MV": 33.52
  },
  "meta": {
    "quality": "GOOD",
    "state": "STABLE",
    "product": "PROCESS_WATER",
    "event": "normal",
    "sequence": 8
  }
}
```

### Pompă — `vendor_pump_v1`

```json
{
  "schema_type": "vendor_pump_v1",
  "pump": {
    "id": "pump_01",
    "area": "PUMP_AREA_B"
  },
  "readings": {
    "flowRateM3h": 42.5,
    "pressureBar": 2.8,
    "vibrationMmS": 3.2,
    "motorCurrentA": 12.4
  },
  "status": {
    "quality": "GOOD",
    "state": "RUNNING",
    "event": "normal"
  },
  "timestamp": "2026-05-08T16:40:00+00:00",
  "sequence": 1
}
```

Toate aceste mesaje sunt transformate într-un `NormalizedRecord` cu aceeași structură internă.

---

## 7. Model intern normalizat

După adaptare, mesajele externe sunt reduse la modelul comun `NormalizedRecord`:

```text
source_id
source_type
protocol_hint
event_time
quality
event_type
sequence_no
measurements
attributes
```

Exemplu pentru pompă:

```json
{
  "source_id": "pump_01",
  "source_type": "pump",
  "protocol_hint": "HTTP",
  "event_time": "2026-05-08T16:40:00+00:00",
  "quality": "GOOD",
  "event_type": "normal",
  "sequence_no": 1,
  "measurements": {
    "flow_rate": 42.5,
    "pressure": 2.8,
    "vibration": 3.2,
    "motor_current": 12.4
  },
  "attributes": {
    "state": "RUNNING",
    "area": "PUMP_AREA_B"
  }
}
```

---

## 8. Contracte gRPC / Protobuf

Contractele sunt definite în folderul `proto/`.

### `normalized.proto`

Definește modelul intern comun folosit între servicii:

* `source_id`
* `source_type`
* `protocol_hint`
* `event_time`
* `quality`
* `event_type`
* `sequence_no`
* `measurements`
* `attributes`

### `alarm.proto`

Definește răspunsul serviciului de alarmare:

* `AlarmMessage`
* `AlarmEvaluationResponse`
* `AlarmService`

Fișierele generate Python se află în:

```text
proto/generated/
```

---

## 9. Configurare prin variabile de mediu

Proiectul include un fișier `.env.example` cu valorile implicite pentru rulare locală.

Pentru a crea configurația locală:

```powershell
Copy-Item .env.example .env
```

Acest pas este opțional, deoarece `docker-compose.yml` conține fallback-uri pentru valorile implicite.

Variabile importante:

| Variabilă                     | Descriere                                   | Valoare implicită                               |
| ----------------------------- | ------------------------------------------- | ----------------------------------------------- |
| `POSTGRES_USER`               | Utilizator PostgreSQL                       | `postgres`                                      |
| `POSTGRES_PASSWORD`           | Parolă PostgreSQL                           | `postgres`                                      |
| `POSTGRES_DB`                 | Baza de date folosită de aplicație          | `factory_historian`                             |
| `INGESTION_API_TOKEN`         | Token pentru autentificarea surselor        | `dev-source-token`                              |
| `INGESTION_URL`               | URL-ul către ingestion folosit de simulator | `http://ingestion-service:8000/ingest/external` |
| `HISTORIAN_GRPC_TARGET`       | Target gRPC pentru historian                | `historian-service:50051`                       |
| `ALARM_GRPC_TARGET`           | Target gRPC pentru alarm-service            | `alarm-service:50052`                           |
| `HISTORIAN_METRICS_PORT`      | Port metrici historian                      | `9101`                                          |
| `ALARM_METRICS_PORT`          | Port metrici alarm-service                  | `9102`                                          |
| `PROMETHEUS_PORT`             | Port UI Prometheus                          | `9090`                                          |
| `SIMULATION_DURATION_SECONDS` | Durata simulată a rularii simulatorului     | `600`                                           |
| `SIMULATION_SEED`             | Seed pentru reproductibilitatea simulării   | `123`                                           |

Fișierul `.env` nu trebuie urcat în repository.

---

## 10. Rularea platformei

Pentru a porni platforma principală:

```powershell
docker compose up --build
```

Această comandă pornește:

* PostgreSQL;
* ingestion-service;
* historian-service;
* alarm-service;
* Prometheus.

Simulatorul nu pornește implicit, deoarece este configurat ca serviciu opțional prin profilul `simulation`.

Verificare containere:

```powershell
docker compose ps
```

Verificare ingestion:

```powershell
curl.exe http://localhost:8000/health
```

Verificare Prometheus:

```text
http://localhost:9090
```

În Prometheus UI se poate accesa:

```text
Status -> Targets
```

Targeturile pentru ingestion, historian și alarm-service trebuie să fie `UP`.

---

## 11. Rularea simulatorului

După ce platforma este pornită, simulatorul poate fi rulat separat:

```powershell
docker compose run --rm simulator-service
```

Cu durată simulată personalizată:

```powershell
docker compose run --rm -e SIMULATION_DURATION_SECONDS=300 simulator-service
```

Cu seed reproductibil:

```powershell
docker compose run --rm `
  -e SIMULATION_DURATION_SECONDS=300 `
  -e SIMULATION_SEED=123 `
  simulator-service
```

Durata simulatorului este durată de proces simulat, nu timp real. Simulatorul folosește SimPy și rulează evenimentele cât de repede poate mediul de execuție.

---

## 12. Verificarea bazei de date

Intrare în PostgreSQL:

```powershell
docker compose exec postgres psql -U postgres -d factory_historian
```

Listare tabele:

```sql
\dt
```

Număr de înregistrări:

```sql
SELECT COUNT(*) FROM normalized_records;
SELECT COUNT(*) FROM alarm_events;
```

Ultimele date normalizate:

```sql
SELECT id, source_id, source_type, quality, event_type, sequence_no
FROM normalized_records
ORDER BY id DESC
LIMIT 10;
```

Ultimele alarme:

```sql
SELECT id, source_id, alarm_code, severity, sequence_no
FROM alarm_events
ORDER BY id DESC
LIMIT 10;
```

Înregistrări pe tip de sursă, eveniment și calitate:

```sql
SELECT source_type, event_type, quality, COUNT(*)
FROM normalized_records
GROUP BY source_type, event_type, quality
ORDER BY source_type, COUNT(*) DESC;
```

Alarme grupate pe cod și severitate:

```sql
SELECT alarm_code, severity, COUNT(*) AS total
FROM alarm_events
GROUP BY alarm_code, severity
ORDER BY total DESC;
```

Golirea tabelelor pentru un test curat:

```sql
TRUNCATE TABLE alarm_events, normalized_records RESTART IDENTITY;
```

Ieșire din PostgreSQL:

```sql
\q
```

---

## 13. Verificarea metricilor

### Endpointuri directe

Ingestion:

```powershell
curl.exe http://localhost:8000/metrics
```

Historian:

```powershell
curl.exe http://localhost:9101/metrics
```

Alarm-service:

```powershell
curl.exe http://localhost:9102/metrics
```

### Query-uri utile în Prometheus

Mesaje primite de ingestion:

```promql
ingestion_records_received_total
```

Mesaje adaptate/normalizate:

```promql
ingestion_records_normalized_total
```

Înregistrări persistate de historian:

```promql
historian_records_stored_total
```

Mesaje evaluate de alarm-service:

```promql
alarm_records_evaluated_total
```

Alarme generate:

```promql
alarm_events_generated_total
```

Alarme grupate pe cod și severitate:

```promql
sum by (code, severity) (alarm_events_by_code_total)
```

Erori gRPC către historian:

```promql
ingestion_historian_errors_total
```

Erori gRPC către alarm-service:

```promql
ingestion_alarm_errors_total
```

Eșecuri de autentificare:

```promql
ingestion_auth_failures_total
```

Observație: metricile Prometheus de tip counter reflectă activitatea serviciului de la ultima pornire a procesului. Tabelele PostgreSQL păstrează istoricul complet până când sunt golite explicit.

---

## 14. Testarea autentificării

Endpointul `POST /ingest/external` necesită headerul:

```text
X-Source-Token: dev-source-token
```

Requesturile fără token sau cu token greșit trebuie să întoarcă `401 Unauthorized`.

Comportament așteptat:

| Caz                               | Rezultat așteptat                                                      |
| --------------------------------- | ---------------------------------------------------------------------- |
| Payload valid fără token          | `401 Unauthorized`                                                     |
| Payload valid cu token greșit     | `401 Unauthorized`                                                     |
| Payload valid cu token corect     | `200 OK`                                                               |
| Token corect, dar payload invalid | `400 Bad Request` sau `422 Unprocessable Entity`, în funcție de eroare |

---

## 15. Scenarii demo recomandate

### Scenariul 1 — rulare normală

1. Pornește platforma:

```powershell
docker compose up --build
```

2. Rulează simulatorul:

```powershell
docker compose run --rm simulator-service
```

3. Verifică logurile ingestion:

```powershell
docker compose logs ingestion-service --tail=50
```

4. Verifică baza de date:

```sql
SELECT COUNT(*) FROM normalized_records;
SELECT COUNT(*) FROM alarm_events;
```

5. Verifică Prometheus UI:

```text
http://localhost:9090
```

### Scenariul 2 — verificare surse și evenimente

```sql
SELECT source_type, event_type, quality, COUNT(*)
FROM normalized_records
GROUP BY source_type, event_type, quality
ORDER BY source_type, COUNT(*) DESC;
```

Acest query permite verificarea faptului că simulatorul produce evenimente normale și anomalii pentru mai multe tipuri de surse.

### Scenariul 3 — verificare alarme

În Prometheus:

```promql
sum by (code, severity) (alarm_events_by_code_total)
```

În PostgreSQL:

```sql
SELECT alarm_code, severity, COUNT(*) AS total
FROM alarm_events
GROUP BY alarm_code, severity
ORDER BY total DESC;
```

### Scenariul 4 — test autentificare

Trimite un request cu payload valid, dar fără `X-Source-Token`. Rezultatul trebuie să fie `401 Unauthorized`, iar metrica `ingestion_auth_failures_total` trebuie să crească.

### Scenariul 5 — verificare observabilitate

Rulează simulatorul de mai multe ori și urmărește creșterea metricilor:

```promql
ingestion_records_received_total
historian_records_stored_total
alarm_events_generated_total
```

### Scenariul 6 — extensibilitate prin sursă nouă

Sursa `vendor_pump_v1` demonstrează că sistemul poate fi extins prin:

* adăugarea unui adaptor nou în `ingestion-service`;
* adăugarea unei surse noi în simulator;
* adăugarea unui bloc de reguli în `alarm-service`;
* fără modificarea contractelor Protobuf, a serviciului historian, a schemei bazei de date sau a configurației Prometheus.

---

## 16. Regenerarea fișierelor Protobuf/gRPC

Fișierele generate se află în `proto/generated/` și sunt folosite la runtime de servicii.

Pentru dezvoltare locală, se pot instala dependențele din root:

```powershell
pip install -r requirements.txt
```

Comandă orientativă de regenerare:

```powershell
python -m grpc_tools.protoc `
  -I proto `
  --python_out=proto/generated `
  --grpc_python_out=proto/generated `
  proto/normalized.proto proto/alarm.proto
```

După regenerare, trebuie verificat că importurile din `proto/generated/` rămân compatibile cu restul proiectului.

---

## 17. Tehnologii folosite

* Python 3.12
* FastAPI
* Uvicorn
* gRPC
* Protocol Buffers
* Pydantic
* SQLAlchemy
* PostgreSQL
* Docker
* Docker Compose
* Prometheus
* SimPy
* Requests

---

## 18. Direcții viitoare

Posibile extinderi ale proiectului:

* dashboard Grafana pentru vizualizarea metricilor Prometheus;
* metrici de latență prin histograme Prometheus;
* migrații de bază de date cu Alembic;
* autentificare mai avansată între componente;
* TLS/mTLS pentru comunicația gRPC internă;
* integrare cu surse reale MQTT sau OPC UA;
* folosirea unui broker de mesaje pentru decuplare suplimentară;
* mapping configurabil prin YAML/JSON pentru surse noi, astfel încât unele integrări să poată fi realizate fără modificarea codului;
* tracing distribuit cu OpenTelemetry;
* rulare în Kubernetes.

---

## 19. Observații finale

Simulatorul este inclus în proiect pentru testare și demonstrație, dar nu este parte obligatorie din platforma internă. Platforma propriu-zisă este formată din serviciul de ingestie, serviciul historian, serviciul de alarmare, baza de date și sistemul de monitorizare.

Proiectul demonstrează un flux complet de integrare a datelor industriale: de la primirea mesajelor JSON eterogene, până la adaptarea lor într-un model intern comun, comunicarea prin gRPC, stocare, alarmare și observabilitate prin Prometheus.

Adăugarea sursei `vendor_pump_v1` demonstrează extensibilitatea arhitecturii: o sursă nouă poate fi integrată printr-un adaptor nou și reguli dedicate, fără modificarea serviciilor din aval sau a contractelor gRPC existente.
