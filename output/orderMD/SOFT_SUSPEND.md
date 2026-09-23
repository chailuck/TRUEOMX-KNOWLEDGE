# SOFT_SUSPEND

> Soft suspend a postpaid subscriber, including Knox device lock phase, billing adjustments, and downstream system updates.

**Total steps:** 31 | **Unique FMs:** 29 | **Entry point:** CCBS_GET_CUST_ACC_SUB_ID

---

## §2 — Order Flow

| Step | Step ID | FM (ActivityID) | Parameter(s) | PreExecCheck | Notes |
|------|---------|-----------------|--------------|--------------|-------|
| 1 | CCBS_GET_CUST_ACC_SUB_ID | CCBS_GET_CUST_ACC_SUB_ID | — | — | |
| 2 | CCBS_SUSPEND_SUBSCRIBER | CCBS_SUSPEND_SUBSCRIBER | — | — | |
| 3 | SBM_SUSPEND_SUBSCRIBER | SBM_SUSPEND_SUBSCRIBER | — | — | |
| 4 | NAS_SUSPEND_SUBSCRIBER | NAS_SUSPEND_SUBSCRIBER | — | — | |
| 5 | ATS_SUSPEND_SUBSCRIBER | ATS_SUSPEND_SUBSCRIBER | — | — | |
| 6 | MCS_SUSPEND_SUBSCRIBER | MCS_SUSPEND_SUBSCRIBER | — | — | |
| 7 | PSA_SUSPEND_SUBSCRIBER | PSA_SUSPEND_SUBSCRIBER | — | — | |
| 8 | CCBS_GET_AR_ACCOUNT | CCBS_GET_AR_ACCOUNT | — | — | |
| 9 | AR_SUSPEND_SUBSCRIBER | AR_SUSPEND_SUBSCRIBER | — | — | |
| 10 | CRM_SUSPEND_SUBSCRIBER | CRM_SUSPEND_SUBSCRIBER | — | — | |
| 11 | TDG_SUSPEND_SUBSCRIBER | TDG_SUSPEND_SUBSCRIBER | — | — | |
| 12 | CCBS_GET_SUBSC_OFFER | CCBS_GET_SUBSC_OFFER | — | — | |
| 13 | OMX_ADD_SUBSCRIBER_OFFER | OMX_ADD_SUBSCRIBER_OFFER ⚠ | — | Conditional | Rule file NOT FOUND |
| 14 | OMX_ADD_FUT_FULL_SUSPEND | OMX_ADD_FUT_FULL_SUSPEND | ActivityReason | — | Dispatches OMX_ADD_FUTURE event; hardcoded "true" return |
| 15 | OMX_SUBMIT_POSTPAID_CHANGE_PACKAGE | OMX_SUBMIT_POSTPAID_CHANGE_PACKAGE | ORDER_TYPE \| OFFER | — | Dispatches OMX_CREATE_CHILD_ORDER; subscriber loop |
| 16 | ICC_CHECK_DEVICE_LOCK | ICC_CHECK_DEVICE_LOCK | — | Conditional | Knox device lock phase begins |
| 17 | ICC_GET_DEVICE_INFO | ICC_GET_DEVICE_INFO | — | Conditional | |
| 18 | ICC_GET_IMEI | ICC_GET_IMEI | — | Conditional | |
| 19 | ICC_GET_SUBSCRIBER_INFO | ICC_GET_SUBSCRIBER_INFO | — | Conditional | |
| 20 | ICC_CHECK_LOCK_ELIGIBILITY | ICC_CHECK_LOCK_ELIGIBILITY | — | Conditional | |
| 21 | ICC_REQUEST_DEVICE_LOCK | ICC_REQUEST_DEVICE_LOCK | — | Conditional | |
| 22 | PSA_UPDATE_KNOX_STATUS | PSA_UPDATE_KNOX_STATUS | — | — | |
| 23 | OMX_NOTI_TO_KAFKA_NOTIFY | OMX_NOTI_TO_KAFKA | knoxEvent=NOTIFY | — | First Kafka notification |
| 24 | ICC_LOCK_DEVICE | ICC_LOCK_DEVICE | — | Conditional | |
| 25 | OMX_NOTI_TO_KAFKA_LOCK | OMX_NOTI_TO_KAFKA | knoxEvent=LOCK | — | Second Kafka notification |
| 26 | PSA_UPDATE_KNOX_STATUS_LOCK ⚠ | PSA_UPDATE_KNOX_STATUS | — | — | extId anomaly: PSA_UPDATE_KNOX_STATUS_LOCK |
| 27 | OMX_NOTI_COMPLETE | OMX_NOTI_COMPLETE | — | — | |
| 28 | CCS_SUSPEND_SUBSCRIBER | CCS_SUSPEND_SUBSCRIBER | — | — | |
| 29 | ICC_TVS_SUBMIT_ORDER_DISC | ICC_TVS_SUBMIT_ORDER | REASON=TDISCOTT | Non-CCBS condition | TVS discount order |
| 30 | ICC_TVS_SUBMIT_ORDER_FULL | ICC_TVS_SUBMIT_ORDER | REASON=TFULLOTT | CCBS condition | TVS full order |
| 31 | OMX_UPDATE_ORDER_STATUS | OMX_UPDATE_ORDER_STATUS | — | — | Final step |

---

## §3 — Sub-flow Phases

### Phase 1 — Core Suspend (Steps 1–11)

Sequential suspension across all downstream systems: CCBS → SBM → NAS → ATS → MCS → PSA → AR → CRM → TDG.

### Phase 2 — OMX Future Orders (Steps 12–15)

- Step 12: Get subscriber offers from CCBS
- Step 13: Add subscriber offer to OMX (`OMX_ADD_SUBSCRIBER_OFFER` — rule file not found)
- Step 14: Schedule future full suspend (`OMX_ADD_FUT_FULL_SUSPEND` — dispatches `OMX_ADD_FUTURE`; effectiveDate driven by ActivityReason: BALOS/SUFIC/SCVG)
- Step 15: Submit postpaid change package child orders (`OMX_SUBMIT_POSTPAID_CHANGE_PACKAGE` — dispatches `OMX_CREATE_CHILD_ORDER`; loops all subscribers)

### Phase 3 — Knox Device Lock (Steps 16–27)

All ICC steps are conditionally executed (device lock eligibility gate):
- Steps 16–20: Device info + eligibility check
- Step 21: Request device lock
- Step 22: PSA status update
- Step 23: Kafka NOTIFY event
- Step 24: Lock device
- Step 25: Kafka LOCK event
- Step 26: PSA status update (extId anomaly: `PSA_UPDATE_KNOX_STATUS_LOCK`)
- Step 27: Notify complete

### Phase 4 — Downstream Finalisation (Steps 28–31)

CCS suspend → ICC TVS orders (×2, different reason codes) → OMX order status update.

---

## §4 — FM Documentation Index

| FM (ActivityID) | Steps | Doc |
|-----------------|-------|-----|
| CCBS_GET_CUST_ACC_SUB_ID | 1 | [Request_CCBS_GET_CUST_ACC_SUB_ID.html](../FMlogic/Request_CCBS_GET_CUST_ACC_SUB_ID.html) |
| OMX_ADD_FUT_FULL_SUSPEND | 14 | [Request_OMX_ADD_FUT_FULL_SUSPEND.html](../FMlogic/Request_OMX_ADD_FUT_FULL_SUSPEND.html) |
| OMX_SUBMIT_POSTPAID_CHANGE_PACKAGE | 15 | [Request_OMX_SUBMIT_POSTPAID_CHANGE_PACKAGE.html](../FMlogic/Request_OMX_SUBMIT_POSTPAID_CHANGE_PACKAGE.html) |
| OMX_ADD_SUBSCRIBER_OFFER | 13 | ⚠ Rule file not found |
| OMX_NOTI_TO_KAFKA | 23, 25 | Existing doc |
| ICC_TVS_SUBMIT_ORDER | 29, 30 | Existing doc |
| PSA_UPDATE_KNOX_STATUS | 22, 26 | Existing doc |

---

## §5 — Sequence Diagram

```mermaid
sequenceDiagram
    participant O as OrderOrchestrator
    participant CCBS as CCBS
    participant SBM as SBM
    participant NAS as NAS
    participant ATS as ATS
    participant OMX as OMX
    participant ICC as ICC
    participant PSA as PSA
    participant Kafka as Kafka

    O->>CCBS: CCBS_GET_CUST_ACC_SUB_ID
    CCBS-->>O: response
    O->>CCBS: CCBS_SUSPEND_SUBSCRIBER
    CCBS-->>O: response
    O->>SBM: SBM_SUSPEND_SUBSCRIBER
    SBM-->>O: response
    O->>NAS: NAS_SUSPEND_SUBSCRIBER
    NAS-->>O: response
    O->>ATS: ATS_SUSPEND_SUBSCRIBER
    ATS-->>O: response
    Note over O,ATS: [MCS, PSA, AR, CRM, TDG suspend steps omitted for brevity]
    O->>CCBS: CCBS_GET_SUBSC_OFFER
    CCBS-->>O: response
    O->>OMX: OMX_ADD_SUBSCRIBER_OFFER [rule not found]
    OMX-->>O: response
    O->>OMX: OMX_ADD_FUT_FULL_SUSPEND [ActivityReason]
    OMX-->>O: response (hardcoded true)
    Note over O,OMX: FM dispatches OMX_ADD_FUTURE event
    O->>OMX: OMX_SUBMIT_POSTPAID_CHANGE_PACKAGE [ORDER_TYPE|OFFER]
    OMX-->>O: response
    Note over O,OMX: FM dispatches OMX_CREATE_CHILD_ORDER; subscriber loop
    opt Knox device lock eligible
        O->>ICC: ICC_CHECK_DEVICE_LOCK / ICC_GET_DEVICE_INFO / ICC_GET_IMEI
        ICC-->>O: response
        O->>ICC: ICC_CHECK_LOCK_ELIGIBILITY
        ICC-->>O: response
        O->>ICC: ICC_REQUEST_DEVICE_LOCK
        ICC-->>O: response
        O->>PSA: PSA_UPDATE_KNOX_STATUS
        PSA-->>O: response
        O->>Kafka: OMX_NOTI_TO_KAFKA [knoxEvent=NOTIFY]
        Kafka-->>O: response
        O->>ICC: ICC_LOCK_DEVICE
        ICC-->>O: response
        O->>Kafka: OMX_NOTI_TO_KAFKA [knoxEvent=LOCK]
        Kafka-->>O: response
        O->>PSA: PSA_UPDATE_KNOX_STATUS_LOCK
        PSA-->>O: response
    end
    O->>OMX: OMX_NOTI_COMPLETE
    OMX-->>O: response
    O->>ICC: ICC_TVS_SUBMIT_ORDER [REASON=TDISCOTT]
    ICC-->>O: response
    O->>ICC: ICC_TVS_SUBMIT_ORDER [REASON=TFULLOTT]
    ICC-->>O: response
    O->>OMX: OMX_UPDATE_ORDER_STATUS
    OMX-->>O: response
```

---

## §6 — Anomalies & Warnings

| Step | Anomaly | Details |
|------|---------|---------|
| 13 | Rule not found | `OMX_ADD_SUBSCRIBER_OFFER` rule file missing — activity documented from ProcessConfig only |
| 14 | Event naming | `OMX_ADD_FUT_FULL_SUSPEND` dispatches `OMX_ADD_FUTURE` JMS event |
| 14 | Hardcoded return | Response handler always returns "true" — no fan-in ResponseCode check |
| 15 | Event naming | `OMX_SUBMIT_POSTPAID_CHANGE_PACKAGE` dispatches `OMX_CREATE_CHILD_ORDER` JMS event |
| 23, 25 | FM reuse | `OMX_NOTI_TO_KAFKA` called twice with different `knoxEvent` values (NOTIFY / LOCK) |
| 26 | extId anomaly | Step 26 extId=`PSA_UPDATE_KNOX_STATUS_LOCK` but ActivityID=`PSA_UPDATE_KNOX_STATUS` |
| 29, 30 | FM reuse | `ICC_TVS_SUBMIT_ORDER` called twice with different REASON (TDISCOTT / TFULLOTT) |

---

*TRUE Corporation OMX · Order Journey Documentation*
