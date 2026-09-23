# Request_TVS_REMOVE_COMPO_OTT

## §1 Overview & Purpose

Sends a **RemoveComponentOTT** request to TVS (True Vision) when a subscriber with a TVS account is cancelled. The request cancels the OTT component, processes equipment return, and unregisters the mobile-TVS relationship (`UnRegisterRelation`).

Used in **CANCEL_SUBSCRIBER** process — Step 55 — gated on `TVS_CUSTOMER_NUMBER` presence. Iterates both ParentOU and ChildOU subscribers.

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule | `Rules.OMConsumers.OMXFM.Request.Request_TVS_REMOVE_COMPO_OTT` |
| Priority | 5 |
| ForwardChain | true |
| Author | 01HW2418126 |
| Dispatch | Per-subscriber (ParentOU + ChildOU) |

## §4 Rule Conditions (WHEN)

1. `orderCurrentActivity.ActivityID == "TVS_REMOVE_COMPO_OTT"`
2. `orderCurrentActivity.Status == "WAITING"`
3. ExtId and NextActivityID match

## §5 Execution Flow

1. Resubmit check
2. Iterate ParentOU subscribers — skip already responded
3. Per-subscriber: evaluate PreExecCheck (TVS_CUSTOMER_NUMBER check)
4. Build and send TVS_REMOVE_COMPO_OTT event
5. Send audit log
6. Repeat for ChildOU subscribers
7. Status="1" or SkipActivity("4")

## §8 System & Integration Dependencies

### §8.2 ESB / JMS Channel

| Direction | Event | Purpose |
|-----------|-------|---------|
| [OUTBOUND] | TVS_REMOVE_COMPO_OTT | Cancel OTT, return equipment, unregister relation |
| [OUTBOUND] | Logger | Audit |

### §8.5 ExtendedInfo Fields

| Key | Usage |
|-----|-------|
| `TVS_CUSTOMER_NUMBER` | PreExecCheck gate + Customer_No |
| `TVS_EQUMENT_RETURN_FLAG` | EqumentReturnFlag |
| `TVS_RETURN_EQUIPT` | Tokenized equipment list (type:serial:returnFlag) |
| `TVS_DEPOT_KEY` | AgentKey in RefundWorkOrder |

## §9 Payload Build

Schema: `ns1:RemoveComponentOTTRequest` with 3 sub-elements:

| Sub-element | Purpose | Key Fields |
|-------------|---------|-----------|
| `TVS_RequestCancelOTT` | Cancel OTT | Customer_No, Channel="CancelOTT", Cancel_ReasonCode="4695" |
| `TVS_CustReturnEquipt` | Return equipment | Tokenized TVS_RETURN_EQUIPT (type:serial:returnFlag) |
| `TVS_UnRegisterRelation` | Unregister TMV link | TVSNO, Relatenumber=MSISDN, Relateiontype="TMV" |

RefundWorkOrder: ConvergenceRefOrderNo=OMXTrackingId, REASONkey="113", ProblemDescription="ยกเลิกสมาชิก"
HardwareProduct: HardwareGroup="OTT", HardwareType="TRUETV", Point="1"

## §10 XSLT Field Mapping Tree

```text
createEvent → event
├── JMSPriority/JMSCorrelationID/OrderID/RefID/OrderType  [Conditional]
└── payload
    └── ns1:RemoveComponentOTTRequest
        ├── TVS_RequestCancelOTT
        │   ├── ns1:Customer_No    ← ExtendedInfo[TVS_CUSTOMER_NUMBER]/Value
        │   ├── ns1:Channel        ← "CancelOTT"
        │   ├── ns1:Cancel_Date    ← tib:format-date('dd/MM/yyyy', current-date())
        │   ├── ns1:Cancel_ReasonCode ← "4695"
        │   ├── ns1:EqumentReturnFlag ← ExtendedInfo[TVS_EQUMENT_RETURN_FLAG]/Value
        │   └── ns1:TVS_RefundWorkOrder
        │       ├── ns1:AgentKey   ← ExtendedInfo[TVS_DEPOT_KEY]/Value
        │       └── ns1:REASONkey  ← "113"
        ├── TVS_CustReturnEquipt
        │   └── [for each token in TVS_RETURN_EQUIPT (type:serial:returnFlag)]
        │       ├── ns1:Equipt_Type  ← substring-before(., ':')
        │       ├── ns1:SerialNo     ← middle token
        │       ├── ns1:ReturnFlag   ← last token
        │       ├── ns1:Platform     ← "OTT"
        │       └── ns1:ModelType    ← "TrueTV"
        └── TVS_UnRegisterRelation
            ├── ns1:Type         ← "UnRegisterRelation"
            ├── ns1:TVSNO        ← ExtendedInfo[TVS_CUSTOMER_NUMBER]/Value
            ├── ns1:Relatenumber ← $psub/MSISDN (or $csub/MSISDN)
            └── ns1:Relateiontype ← "TMV"
```

## §17 Migration Notes

- **R1:** TVS_CUSTOMER_NUMBER must be populated upstream
- **R2:** TVS_RETURN_EQUIPT colon-delimited triplet format — preserve parsing logic
- **R3:** AUDIT_TRACE label says "TDG_UPDATE_SERIAL" — copy-paste error in legacy code; correct in modernization
- **Risk:** [MEDIUM] — Per-subscriber loop; fan-in count must match all subscribers

## §19 Response Message Rule

**Fan-in:** `count(Response[ResponseCode ends in "000"]) == RequestCount`
**Response audit:** OPERATION_NAME="TVS_REMOVE_COMPO_OTT", AUDIT_TRACE="Response received for TVS_REMOVE_COMPO_OTT"

---
*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
