# Request_CCBS_UPDATE_CUSTOMER_NAME_ADDRESS

## §1 — Overview & Purpose

Updates customer name and address in CCBS. A **3-way `xsl:choose`** on `NameType` determines the payload variant:
- **CORP (nameType=66):** 8 core name elements + conditional extended corporate block
- **INDY (nameType=73):** 10 core name elements + conditional extended individual block
- **Default (nameType=69):** element2=PrefContactNumber only + conditional extended block

Uses **IntraActivitySequencing** (ActionRequestEvent + SendFirstRequestEvent). One request per customer. `ActionResponseEvent` in response handler is **active** (not commented out — unlike CCBS_CHANGE_CUSTOMER_GENERAL_INFO).

> **Note:** LogicalDate is mapped to both `enclosedClientInfo.logicalDate` and `ActivityDateInfo.activityDate`.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_UPDATE_CUSTOMER_NAME_ADDRESS` |
| Activity ID | `CCBS_UPDATE_CUSTOMER_NAME_ADDRESS` |
| Fan-in | IntraActivitySequencing (ActionRequestEvent + ActionResponseEvent — both active) |
| Send pattern | `Event.assertEvent` + `IntraActivitySequencing.SendFirstRequestEvent` |
| RefID | `Customer.RefId` (single request) |

---

## §5 — Execution Flow

1. Read LogicalDate singleton
2. Evaluate PreExecCheck; if resubmit: PurgePendingRequestsBeforeResubmit
3. Build `UpdateCustomerNameAddressRequest` via XSLT (3-way NameType branch)
4. `Event.assertEvent(reqEvent)` — add to working memory
5. `IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)`
6. Send audit log
7. `IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)`
8. Set WAITING_RESPONSE; persist to DB

---

## §8 — System & Integration Dependencies

### §8.2 — ESB/JMS Channel

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `CCBS_UPDATE_CUSTOMER_NAME_ADDRESS` | Update customer name & address |
| [INBOUND] | `CCBS_UPDATE_CUSTOMER_NAME_ADDRESS` (response) | Confirmation |

### §8.3 — NameType Branch Table

| NameType | nameType Code | Name Elements | Extended Block |
|----------|--------------|--------------|----------------|
| CORP | 66 | 8 elements | Language, AuthFirstName, AuthLastName, AuthPersonalId, POAName, POAPersonalId — conditional on isExtendedNameInfoExist |
| INDY | 73 | 10 elements | Language, PrefContactNumber, HomePhone, BizPhone, privatePhone, AuthFirstName, AuthLastName, AuthPersonalId — conditional on isExtendedNameInfoExist |
| Default | 69 | element2=PrefContactNumber only | Full extended block (all 10 sub-fields) — conditional on isExtendedNameInfoExist |

### §8.4 — Address Block

15 `addressElements`; `addressType`: `"66"` if NameType=CORP, else `"73"`.

---

## §10 — XSLT Field Mapping

```text
createEvent / event
├── JMSPriority              ← $orderRequest/OrderPriority                [Always]
├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId      [Always]
├── OrderID                  ← $orderRequest/OrderData/OrderID            [Always]
├── RefID                    ← $orderRequest/OrderData/Customer/RefId     [Always]
├── UserName / PassWord      ← User / Password                            [Credential-gated]
├── OrderType                ← $orderRequest/OrderData/OrderType          [Conditional]
└── payload / UpdateCustomerNameAddressRequest
    ├── CustomerIdInfo / CustomerNo  ← Customer/CustomerId                [Conditional]
    ├── enclosedClientInfo / logicalDate  ← LogicalDate.currentDate       [Conditional]
    ├── CustomerNameInfo  [xsl:choose on NameType]
    │   ├── CORP branch (nameType=66)
    │   │   ├── nameType  ← "66"                                          [Always]
    │   │   ├── element1..element8  ← Customer.NameInfo fields            [Always]
    │   │   └── ExtendedNameInfo                                          [Conditional: isExtendedNameInfoExist]
    │   ├── INDY branch (nameType=73)
    │   │   ├── nameType  ← "73"                                          [Always]
    │   │   ├── element1..element10  ← Customer.NameInfo fields           [Always]
    │   │   └── ExtendedNameInfo                                          [Conditional: isExtendedNameInfoExist]
    │   └── Default branch (nameType=69)
    │       ├── nameType  ← "69"                                          [Always]
    │       ├── element2  ← Customer.PrefContactNumber                    [Always]
    │       └── ExtendedNameInfo (full)                                   [Conditional: isExtendedNameInfoExist]
    ├── CustomerAddressInfo
    │   ├── addressType  ← "66" if CORP, else "73"                        [Conditional]
    │   └── addressElement1..15  ← Customer.AddressInfo fields            [Always]
    ├── ActivityDateInfo / activityDate  ← LogicalDate.currentDate        [Conditional]
    └── ActivityInfo / ActivityReason  ← ActivityReason or "CREQ"         [Always]
```

---

## §17 — Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| 3-way NameType branch — different field sets per variant | [HIGH] | Document all three variants in new API spec; validate NameType at entry |
| IntraActivitySequencing ActionResponseEvent is ACTIVE | [MEDIUM] | Verify engine compatibility in modernized platform |
| Extended name block (10+ sub-fields) silently skipped if isExtendedNameInfoExist missing | [MEDIUM] | Validate flag before update |
| LogicalDate injected twice (enclosedClientInfo + ActivityDateInfo) | [LOW] | Confirm both fields serve distinct CCBS purposes |

---

## §19 — Response Message Rule

### §19.1 — Overview

`Response_CCBS_UPDATE_CUSTOMER_NAME_ADDRESS`: Creates `CCBS_UpdateCustomerNameAddress` concept. Uses `IntraActivitySequencing.ActionResponseEvent(currActivity)` — active (not commented out).

### §19.3 — Response Concept

```text
CCBS_UpdateCustomerNameAddress
├── extId               ← OMXUtils:generateTrackingID()          [Always]
├── ResponseCode        ← $eventResponse/ResponseCode            [Conditional]
├── ResponseMessage     ← $eventResponse/ResponseMsg             [Conditional]
├── CompletionStatus    ← $eventResponse/CompletionStatus        [Conditional]
└── ReferenceId         ← $eventResponse/RefID                   [Conditional]
```

### §19.4 — Fan-in

```xpath
// ActionResponseEvent is ACTIVE here (not commented out)
IntraActivitySequencing.ActionResponseEvent(currActivity)
// Note: simple count fan-in is commented out in source
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
