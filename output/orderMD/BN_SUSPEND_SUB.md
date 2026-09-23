# BN_SUSPEND_SUB

> Process Configuration for BN_SUSPEND_SUB.

**Total steps:** 5 | **Unique FMs:** 5 | **Entry point:** CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE

---

## §2 — Order Flow

| Step | Step ID | FM (ActivityID) | Parameter(s) | PreExecCheck | Previous | Next | FM Doc |
|------|---------|-----------------|--------------|--------------|----------|------|--------|
| 1 | CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE | CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE | — | — | START | OMX_BIZ_VAL | Existing |
| 2 | OMX_BIZ_VAL | OMX_BIZ_VAL | — | — | CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE | CCBS_SUSPEND_SUBS | Existing |
| 3 | CCBS_SUSPEND_SUBS | CCBS_SUSPEND_SUBS | — | — | OMX_BIZ_VAL | CCBS_GET_CUST_ACC_SUB_ID | Generated |
| 4 | CCBS_GET_CUST_ACC_SUB_ID | CCBS_GET_CUST_ACC_SUB_ID | — | `boolean(//Subscriber[ExtendedInfo[Name='COLLECTION_WAIVER' and (Value='N' or Value='Y')]]) and not(exists(//Account/AccountID))` | CCBS_SUSPEND_SUBS | CCBS_UPDATE_ACCOUNT_FIX_INFO | Existing |
| 5 | CCBS_UPDATE_ACCOUNT_FIX_INFO | CCBS_UPDATE_ACCOUNT_FIX_INFO | — | `boolean(//Subscriber[ExtendedInfo[Name='COLLECTION_WAIVER' and (Value='N' or Value='Y')]])` | CCBS_GET_CUST_ACC_SUB_ID | END | ✓ Generated |

---

## §3 — PreExecCheck Details

### Step 4 — CCBS_GET_CUST_ACC_SUB_ID

**FM:** `CCBS_GET_CUST_ACC_SUB_ID`

```xpath
boolean(//Subscriber[ExtendedInfo[Name='COLLECTION_WAIVER' and (Value='N' or Value='Y')]])
and not(exists(//Account/AccountID))
```

Fires only when at least one subscriber has `COLLECTION_WAIVER='Y'` or `'N'` AND the account details (AccountID) have not yet been loaded. Prevents a redundant CCBS call if the account was already retrieved earlier in the flow.

### Step 5 — CCBS_UPDATE_ACCOUNT_FIX_INFO

**FM:** `CCBS_UPDATE_ACCOUNT_FIX_INFO` — [Generated](../FMlogic/Request_CCBS_UPDATE_ACCOUNT_FIX_INFO.html)

```xpath
boolean(//Subscriber[ExtendedInfo[Name='COLLECTION_WAIVER' and (Value='N' or Value='Y')]])
```

Fires only when at least one subscriber has `COLLECTION_WAIVER='Y'` or `'N'`. If no subscriber has this ExtendedInfo, the account fix-info update is skipped. Note: the FM contains an internal `break;` — it fires at most once per ParentOU even when multiple subscribers qualify.

---

## §4 — FM Documentation Index

| FM (ActivityID) | Used in Steps | Status | Doc Link |
|-----------------|---------------|--------|----------|
| CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE | 1 | Existing | [Request_CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE.html](../FMlogic/Request_CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE.html) |
| OMX_BIZ_VAL | 2 | Existing | [Request_OMX_BIZ_VAL.html](../FMlogic/Request_OMX_BIZ_VAL.html) |
| CCBS_SUSPEND_SUBS | 3 | Generated | [Request_CCBS_SUSPEND_SUBS.html](../FMlogic/Request_CCBS_SUSPEND_SUBS.html) |
| CCBS_GET_CUST_ACC_SUB_ID | 4 | Existing | [Request_CCBS_GET_CUST_ACC_SUB_ID.html](../FMlogic/Request_CCBS_GET_CUST_ACC_SUB_ID.html) |
| CCBS_UPDATE_ACCOUNT_FIX_INFO | 5 | ✓ Generated | [Request_CCBS_UPDATE_ACCOUNT_FIX_INFO.html](../FMlogic/Request_CCBS_UPDATE_ACCOUNT_FIX_INFO.html) |

---

## §5 — Sequence Diagram

```mermaid
sequenceDiagram
    participant O as OrderOrchestrator
    participant CCBS as CCBS
    participant OMX as OMX

    O->>CCBS: CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE
    CCBS-->>O: response
    O->>OMX: OMX_BIZ_VAL
    OMX-->>O: response
    O->>CCBS: CCBS_SUSPEND_SUBS
    CCBS-->>O: response
    opt COLLECTION_WAIVER=Y/N and no AccountID
        O->>CCBS: CCBS_GET_CUST_ACC_SUB_ID
        CCBS-->>O: response
    end
    opt COLLECTION_WAIVER=Y/N
        O->>CCBS: CCBS_UPDATE_ACCOUNT_FIX_INFO
        CCBS-->>O: response
        Note over O,CCBS: Account-level; break after first subscriber; CollectionPermanentWaiveInd 89/78
    end
```

> Conditional steps wrapped in `opt` blocks. Full HTML with flowchart: `output/order/BN_SUSPEND_SUB.html`

---

*TRUE Corporation OMX · Order Journey Documentation · BN_SUSPEND_SUB*
