# POSTPAID_ADD_OFFER_SUB

> **Postpaid Add-Offer Subscription** — End-to-end order orchestration process for adding postpaid service offers (data packs, roaming, content subscriptions, loyalty benefits) to an existing subscriber.

**Total steps:** 84 &nbsp;|&nbsp; **Unique FMs:** 55 &nbsp;|&nbsp; **Phases:** 16 &nbsp;|&nbsp; **Entry point:** `IOM_CHECK_SEQUENCING` &nbsp;|&nbsp; **Generated:** 2026-08-11

---

## §1 — Process Overview

POSTPAID_ADD_OFFER_SUB is the **primary end-to-end order orchestration process** for adding postpaid service offers to an existing subscriber. It is triggered when a customer selects a new add-on service (data pack, roaming, content subscription, or loyalty benefit) through any front-end channel: retail, BSNS enterprise portal, CCBS back-office, or third-party API.

The process follows a structured pipeline:
1. **Collect and validate** — customer, account, subscriber data; blacklist/fraud checks
2. **Resolve and price** — offer catalogue, BRMS evaluation, pricing, exclusion rules
3. **Provision** — CCBS, AA, SBM, MCS, Knox across multiple backend systems
4. **Notify** — SMS, child orders, Knox events, API Gateway opt-in

### Key Facts

| Attribute | Value |
|-----------|-------|
| Entry channels | Retail, BSNS enterprise, CCBS back-office, USSD, API, eTG portal, Apple |
| Entry condition | POMX_ETG / Apple: held in sequencing queue; others: direct |
| Core backend systems | CCBS · AA · SBM · MCS · INTX · OMX Internal |
| Fan-out model | Per-subscriber (POU → Sub, POU → COU → Sub) |
| Offer sources | FE (Front-End), BRMS, CCBS legacy |
| COVID-19 / STUDENT | Many steps skipped for these order types |
| Child orders | Steps 83–84 submit sub-orders to OMX |
| Known bugs | Step 84: orderId not unique; Steps 40/42/44: wrong OPERATION_NAME |

### Legend

- **Conditional step** (PreExecCheck present) — only runs when condition is met
- **Not Found** — rule file missing from codebase
- **Skipped** — FM doc not generated (user choice)
- **Always** — no PreExecCheck; always executed in flow

---

## §2 — Journey at a Glance (16 Phases)

| Phase | Name | Steps | Key Systems | Description |
|-------|------|-------|-------------|-------------|
| 1 | Order Entry & Sequencing | 1 | OMX Internal | Gate for sequential-channel orders (eTG, Apple) |
| 2 | Customer & Account Data Collection | 2–10 | CCBS, Blacklist | Subscriber, customer, fraud, account, billing data |
| 3 | Subscriber Status & Eligibility | 11–12 | CCBS, INTX | Full subscriber service data, Knox preferences |
| 4 | Offer Catalogue Resolution | 13–17 | CCBS, BRMS | SOC resolution, BRMS evaluation, GOD enrichment |
| 5 | Extended Offer & Pricing Data | 18–24 | OMX, CCBS, MCS | SOC attributes, pricing, future dates, exclusion rules |
| 6 | Financial & Content Service Assessment | 25–28 | BL, MLDD, MCS, INTX | Uninvoiced charges, MCS data, credit obligation check |
| 7 | Special Feature & MultiSIM Detection | 29–34 | AA, OMX, INTX | Switch features, MultiSIM flags (RES/REE), SIM data |
| 8 | Pre-Provisioning Calculations | 35–37 | OMX, CVSS | Future companion offers, discounts, credit notification |
| 9 | MultiSIM & Switch Feature Provisioning | 38–46 | ASRM, OMX, AA | Reserve→Activate SIM, MultiSIM ADD/UPDATE, SwitchFeature |
| 10 | Credit Limit Management | 47–49 | OMX, CCBS | IR and TPC credit limit calculations for corporate accounts |
| 11 | SBM Data Pack Management | 50–57 | SBM, OMX, CCBS | FUP cap, data packs ST86/87/88, future scheduling |
| 12 | Billing Charges | 58 | BL Billing | One-time billing charge creation (ST=79) |
| 13 | CCBS Package Provisioning | 59–63 | CCBS, MCS | Remove old packages, add new, MCS content registration |
| 14 | Knox Enterprise Device Management | 64–70 | PSA, Knox, Kafka | Knox device registration, status activation, B2B notification |
| 15 | Supplementary & Ancillary Actions | 71–79 | TDG, OMX, BDH, CCBS | IoT subscriber, installment, SIM/address updates, memos |
| 16 | Order Completion & Notification | 80–84 | AA, SMS, APIGW, OMX | AA confirmation, SMS, CBSC opt-in, child orders |

---

## §3 — Step-by-Step Order Journey

---

### Phase 1 — Order Entry & Sequencing (Step 1)

**Business context:** Determine whether this order requires sequential processing. POMX_ETG and Apple channel orders are held in a sequencing queue to prevent concurrent conflicts when multiple orders arrive for the same subscriber.

#### Step 1 — Order Sequencing Check

| Field | Value |
|-------|-------|
| **FM (ActivityID)** | `IOM_CHECK_SEQUENCING` |
| **System** | OMX Internal |
| **Doc** | [Request_IOM_CHECK_SEQUENCING.html](../FMlogic/Request_IOM_CHECK_SEQUENCING.html) |

**Purpose:** Holds the order in a sequencing queue to prevent parallel processing conflicts when the same subscriber has multiple orders in flight through the POMX_ETG or Apple channel.

**When active:** Only for POMX_ETG (eTG portal) or Apple channel orders

```xpath
/ns0:OrderRequest/OrderData/Channel/text()="POMX_ETG" or
/ns0:OrderRequest/OrderData/Channel/text()="APPLE"
```

---

### Phase 2 — Customer & Account Data Collection (Steps 2–10)

**Business context:** Gather all core data needed for the rest of the process: subscriber identity, customer profile, blacklist/fraud status, account details, billing account, and service agreement. Steps 5–7 (blacklist checks) are skipped for government accounts, COVID-19 relief orders, and Student channel.

#### Step 2 — Load Subscriber Base Record

| Field | Value |
|-------|-------|
| **FM** | `CCBS_GET_SUBSCRIBER_HEADER` | **System** | CCBS |
| **Doc** | [Request_CCBS_GET_SUBSCRIBER_HEADER.html](../FMlogic/Request_CCBS_GET_SUBSCRIBER_HEADER.html) |

**Purpose:** Retrieves the subscriber's core identification data from CCBS, establishing the subscriber context required by all subsequent steps.

**When active:** When a `SubscriberId` is present in the order

```xpath
exists(//Subscriber/SubscriberId)
```

#### Step 3 — Resolve Customer & Account ID Hierarchy

**FM:** `CCBS_GET_CUST_ACC_SUB_ID` | **System:** CCBS | [Doc](../FMlogic/Request_CCBS_GET_CUST_ACC_SUB_ID.html)

**Purpose:** Retrieves the linked customer, account, and subscriber IDs, establishing the complete account hierarchy. Mapping required for downstream calls that must reference customer or account independently.

**When active:** Always executed (no condition)

#### Step 4 — Fetch Customer Profile & Address

**FM:** `CCBS_GET_CUSTOMER_HEADER` | **System:** CCBS | **Params:** `GET_NAME_ADDRESS=Y` | [Doc](../FMlogic/Request_CCBS_GET_CUSTOMER_HEADER.html)

**Purpose:** Retrieves customer name and address details. Required for billing correspondence, KYC verification, and address-based eligibility checks.

**When active:** Always executed (no condition)

#### Step 5 — General Blacklist Screening

**FM:** `BLACKLIST_CHECK_BLACKLIST` | **System:** Blacklist | [Doc](../FMlogic/Request_BLACKLIST_CHECK_BLACKLIST.html)

**Purpose:** Checks whether the customer appears on the general blacklist. Blocks service activation for known non-paying or banned customers before any provisioning begins.

**When active:** Skipped for government/special accounts (CustomerType=70), COVID-19 relief orders, and Student channel

```xpath
/ns0:OrderRequest/OrderData/Customer/CustomerTypeInfo/Type/text()!="70"
and not(starts-with(/ns0:OrderRequest/OrderData/OrderID,"COVID19"))
and /ns0:OrderRequest/OrderData/Channel/text()!="STUDENT"
```

#### Step 6 — Collections Blacklist Check

**FM:** `BLACKLIST_CHECK_COLL_BY_ID_NUM` | **System:** Blacklist | [Doc](../FMlogic/Request_BLACKLIST_CHECK_COLL_BY_ID_NUM.html)

**Purpose:** Verifies the customer is not listed in the collections system by ID number. Prevents new service additions for customers with outstanding debt referred to collections.

**When active:** Same conditions as Step 5

#### Step 7 — Fraud Screening

**FM:** `BLACKLIST_CHECK_FRAUD` | **System:** Blacklist | [Doc](../FMlogic/Request_BLACKLIST_CHECK_FRAUD.html)

**Purpose:** Screens the customer and order against the fraud detection list.

**When active:** Same conditions as Steps 5–6

#### Step 8 — Fetch Account Information

**FM:** `CCBS_GET_ACCOUNT_HEADER` | **System:** CCBS | [Doc](../FMlogic/Request_CCBS_GET_ACCOUNT_HEADER.html)

**Purpose:** Retrieves account-level data including billing settings and account status. **When active:** Always

#### Step 9 — Fetch Billing Account Details

**FM:** `CCBS_GET_BA_HEADER` | **System:** CCBS | **Params:** `GET_NAME_ADDRESS=Y` | [Doc](../FMlogic/Request_CCBS_GET_BA_HEADER.html)

**Purpose:** Retrieves billing account header including name and address. **When active:** Always

#### Step 10 — Fetch Service Agreement

**FM:** `CCBS_GET_AGREEMENT_HEADER` | **System:** CCBS | [Doc](../FMlogic/Request_CCBS_GET_AGREEMENT_HEADER.html)

**Purpose:** Retrieves the subscriber's service agreement details. **When active:** Always

---

### Phase 3 — Subscriber Status & Eligibility (Steps 11–12)

**Business context:** Retrieve full subscriber service data (current packages, SIMs, extended info) and Knox MDM preferences for enterprise BSNS orders.

#### Step 11 — Retrieve Full Subscriber Service Data

**FM:** `CCBS_GET_SUBS_INFO` | **System:** CCBS | [Doc](../FMlogic/Request_CCBS_GET_SUBS_INFO.html)

**Purpose:** Fetches comprehensive subscriber data: current active services, packages, SIM details, extended info flags (TR_SPECIAL_OFFER_IND, FE_OR_CCBS, IMEI_KNOX, etc.). **Primary data source for all downstream steps.**

**When active:** Skipped if subscriber Status = 84 (disconnecting), 67 (pending disconnection), or 76 (suspended)

```xpath
boolean(//Subscriber[Status !=67 and Status !=76 and Status !=84])
```

#### Step 12 — Retrieve Knox Device Preferences

**FM:** `INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST` | **System:** INTX | [Doc](../FMlogic/Request_INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST.html)

**Purpose:** Fetches Knox MDM enrollment preferences for enterprise BSNS orders where a Knox IMEI is already registered in CCBS.

**When active:** BSNS channel orders where subscriber has a Knox IMEI in CCBS

```xpath
starts-with(/ns0:OrderRequest/OrderData/OrderID,"BSNS")
and boolean(//Subscriber/SubscriberOffers[
  ExtendedInfo[Name='FE_OR_CCBS' and Value='CCBS']
  and ExtendedInfo[Name='IMEI_KNOX' and Value!='']])
```

---

### Phase 4 — Offer Catalogue Resolution (Steps 13–17)

**Business context:** Resolve all selected offers to their full CCBS service definitions. Run BRMS evaluation to add rule-engine-sourced offers, then resolve SOC codes and fetch full GOD data.

#### Step 13 — Resolve Missing Offer SOC Codes

**FM:** `CCBS_RESOLVE_SOC_CODE` | **System:** CCBS | [Doc](../FMlogic/Request_CCBS_RESOLVE_SOC_CODE.html)

**Purpose:** Looks up CCBS Service Offer Codes (SOC) for offers missing SOC values. SOC codes are mandatory for CCBS package provisioning.

**When active:** When one or more subscriber offers are missing their SOC code

#### Step 14 — Retrieve FE/BRMS Offer Details (CCBS GOD)

**FM:** `CCBS_GOD` | **System:** CCBS | [Doc](../FMlogic/Request_CCBS_GOD.html)

**Purpose:** Calls CCBS 'Get Offer Details' API to enrich Front-End and BRMS offers with full service definitions (service type, pricing flags, SocProperties, provisioning attributes).

**When active:** When the order contains FE or BRMS sourced offers

#### Step 15 — BRMS Offer Eligibility Evaluation

**FM:** `OMX_BRMS_DB` | **System:** OMX / BRMS | [Doc](../FMlogic/Request_OMX_BRMS_DB.html)

**Purpose:** Invokes the Business Rules Management System to evaluate eligibility and add BRMS-sourced offers. Returns rule-engine offers based on customer profile and contract.

**When active:** When FE offers are present; skipped for COVID-19, BSNS, and STUDENT

#### Step 16 — Resolve BRMS Offer SOC Codes

**FM:** `CCBS_RESOLVE_SOC_CODE` *(same FM as Step 13)* | **System:** CCBS

**Purpose:** Resolves SOC codes specifically for BRMS-sourced offers added by Step 15.

**When active:** When BRMS offers exist; skipped for COVID-19 and STUDENT

#### Step 17 — Retrieve BRMS Offer Details (CCBS GOD)

**FM:** `CCBS_GOD` *(same FM as Step 14)* | **System:** CCBS

**Purpose:** Enriches BRMS offers with full CCBS service details after SOC code resolution.

**When active:** When BRMS offers exist; skipped for COVID-19 and STUDENT

---

### Phase 5 — Extended Offer & Pricing Data (Steps 18–24)

**Business context:** Retrieve extended SOC attributes, MCS charge info, future-order conflicts, and effective dates. Apply offer inclusion and exclusion rules, then retrieve pricing rates.

#### Step 18 — Resolve Extended SOC & Provisioning Attributes

**FM:** `OMX_RESOLVE_SOC_DATA` | **System:** OMX Internal | [Doc](../FMlogic/Request_OMX_RESOLVE_SOC_DATA.html)

**Purpose:** Retrieves extended provisioning attributes: SBM_PROVISIONING flags, FUP indicators, special offer types. These control which SBM/AA provisioning steps fire for each offer.

**When active:** Always executed except for COVID-19 orders

#### Step 19 — Retrieve MCS TPC Charge Information

**FM:** `MCS_GET_CHARGE_INFO` | **System:** MCS | [Doc](../FMlogic/Request_MCS_GET_CHARGE_INFO.html)

**Purpose:** Fetches charge and tariff information from MCS for TPC (True Partner Content) offers with service type 85 or 69.

**When active:** Only for TPC-branded offers with ST=85 or 69 that are not flagged as recurring

#### Step 20 — Retrieve Existing Future Order Information

**FM:** `OMX_GET_FUT_INFO_BY_SUB` | **System:** OMX Internal | [Doc](../FMlogic/Request_OMX_GET_FUT_INFO_BY_SUB.html)

**Purpose:** Fetches future-dated orders currently pending for this subscriber. Used to detect scheduling conflicts.

**When active:** Always executed except for COVID-19 orders

#### Step 21 — Calculate Future Offer Effective Dates

**FM:** `OMX_CAL_OFFER_FUT_DATE` | **System:** OMX Internal | **Params:** `CAL_PARAM_EXP=Y` | [Doc](../FMlogic/Request_OMX_CAL_OFFER_FUT_DATE.html)

**Purpose:** Computes the correct effective start date for future-dated (EFF_TYPE=FUT) offers, accounting for billing cycle boundaries.

**When active:** Only when future-dated FE or BRMS offers exist; skipped for COVID-19

#### Step 22 — Apply Offer Inclusion Business Rules ⚠ NOT FOUND

**FM:** `OMX_OFFER_INCLUSION` | **System:** OMX Internal | **Status:** ⚠ Rule file not found

**Purpose:** Evaluates offer inclusion rules — ensures required companion offers or bundles are included where business rules mandate it.

> **Migration Impact:** Offer inclusion logic is undocumented. Must be sourced from business specifications or BRMS configuration.

#### Step 23 — Apply Offer Exclusion Rules

**FM:** `CCBS_OFFER_EXCLUSION` | **System:** CCBS | [Doc](../FMlogic/Request_CCBS_OFFER_EXCLUSION.html)

**Purpose:** Evaluates CCBS exclusion rules and removes conflicting or ineligible offers. Ensures mutually exclusive services are not provisioned together.

**When active:** For immediate or logical-date provision orders; skipped for COVID-19 and STUDENT

#### Step 24 — Retrieve Offer Pricing Rates

**FM:** `OMX_GET_OFFER_RATE` | **System:** OMX Internal | [Doc](../FMlogic/Request_OMX_GET_OFFER_RATE.html)

**Purpose:** Fetches current pricing rates for FE and BRMS offers with service type 85 or 68. Used for billing charge creation and credit obligation checks.

**When active:** Only for FE/BRMS offers with ST=85 or 68; skipped for COVID-19 and STUDENT

---

### Phase 6 — Financial & Content Service Assessment (Steps 25–28)

**Business context:** Assess financial exposure: check uninvoiced charges, retrieve MCS subscriber data, mark MCS subscriptions as used, and run credit obligation checks.

#### Step 25 — Check Existing Uninvoiced Charges

**FM:** `BL_LIST_UNINVOICED_CHARGES` | **System:** BL Billing | [Doc](../FMlogic/Request_BL_LIST_UNINVOICED_CHARGES.html)

**Purpose:** Queries the billing system for uninvoiced charges for service types 85/86/87. Prevents double-billing when charges are already pending.

**When active:** FE/BRMS offers ST=85/86/87 with non-zero price, immediate or logical-date execution

#### Step 26 — Retrieve MCS Subscriber Profile Data

**FM:** `MLDD_GET_SUB_DATA` | **System:** MLDD | [Doc](../FMlogic/Request_MLDD_GET_SUB_DATA.html)

**Purpose:** Fetches MCS subscriber data (pack code, flow ID) from MLDD. Required to resolve MCS subscription details.

**When active:** Only when MCS_PACKCODE and FLOW_ID are both present in extended info

#### Step 27 — Mark MCS Subscription Slot as Used

**FM:** `MCS_SUBSCRIPTION_MARKUSED` | **System:** MCS | **Params:** `DEFAULT_FLOW_ID=FVM003` | [Doc](../FMlogic/Request_MCS_SUBSCRIPTION_MARKUSED.html)

**Purpose:** Marks the MCS subscription record as 'used'. Prevents double-allocation of the same slot across concurrent orders.

**When active:** Only for FE or BRMS offers with MCS service type 69 (content subscription)

#### Step 28 — Credit Obligation Assessment

**FM:** `INTX_GET_TOTAL_OBLIGATION_INFO` | **System:** INTX | [Doc](../FMlogic/Request_INTX_GET_TOTAL_OBLIGATION_INFO.html)

**Purpose:** Retrieves the subscriber's total outstanding financial obligation from INTX. **Critical credit risk gate** — may reject the order if obligations exceed credit limits.

**When active:** Skipped for e-wallet (TMNWEBEWAL/TMNMBAEWAL), USSD714, 711POSCASH, future channels, suspended subscribers (Status 67/76/84), zero-rate offers, credit waiver active (`CreditLimitWaiverInd=U`), COVID-19, or `skipCheckCreditLimit=Y`

```xpath
Channel not in (TMNWEBEWAL, TMNMBAEWAL, USSD714, 711POSCASH, FUT_*)
and Subscriber Status not in (67, 76, 84)
and sum(FE/BRMS OfferRate) > 0
and CreditLimitWaiverInd != "U"
and not(COVID19)
and skipCheckCreditLimit != "Y"
```

---

### Phase 7 — Special Feature & MultiSIM Detection (Steps 29–34)

**Business context:** Identify switch-feature offers, set MultiSIM eligibility flags (TR_MULTISIM_IND=RES for new reservation, REE for existing enrollment), retrieve SIM relationship data. These flags gate the entire MultiSIM provisioning phase (Steps 38–46).

#### Step 29 — Identify Switch Feature Upgrade Path

**FM:** `AA_GET_SWITCH_FEATURE_OFFER` | **System:** AA | [Doc](../FMlogic/Request_AA_GET_SWITCH_FEATURE_OFFER.html)

**Purpose:** Queries AA for switch feature offers associated with this subscription. Switch features handle SIM upgrade and handset service transitions.

**When active:** For immediate or logical-date provision orders; skipped for COVID-19 and STUDENT

#### Step 30 — Detect Special Offer Flags (MultiSIM & Loyalty)

**FM:** `GET_SPECIAL_OFFER_INDICATOR` | **System:** OMX Internal | **Params:** `ADD_PROP=TR_MULTISIM_IND | CHECK_LOYALTY_SOC=Y` | [Doc](../FMlogic/Request_GET_SPECIAL_OFFER_INDICATOR.html)

**Purpose:** Adds two critical flags: `TR_MULTISIM_IND` (RES=new reservation, REE=existing enrolled) and loyalty SOC eligibility. **Gates the entire MultiSIM provisioning sub-process (Steps 38–46) and loyalty benefit submission (Step 83).**

**When active:** For immediate or logical-date provision orders; skipped for COVID-19 and STUDENT

#### Step 31 — Retrieve Minor SIM Details

**FM:** `INTX_GET_SIM_INFO_BY_SIM` | **System:** INTX | [Doc](../FMlogic/Request_INTX_GET_SIM_INFO_BY_SIM.html)

**Purpose:** Fetches information about the minor SIM (data-only SIM in a MultiSIM pair). Required before reserving the minor SIM resource in ASRM.

**When active:** Only when `TR_MULTISIM_IND = 'RES'`

#### Step 32 — Retrieve MultiSIM Master/Minor Relationship

**FM:** `INTX_GET_MASTER_MINOR_SIM_INFO` | **System:** INTX | [Doc](../FMlogic/Request_INTX_GET_MASTER_MINOR_SIM_INFO.html)

**Purpose:** Fetches the complete master-minor SIM relationship for both voice SIM and data SIM.

**When active:** When `TR_MULTISIM_IND = 'RES'` or `TR_MULTISIM_IND = 'REE'`

#### Step 33 — Search for Conflicting Future Orders

**FM:** `OMX_SEARCH_FUT` | **System:** OMX Internal | **Params:** `STATUS=1 | ORDER_TYPE=12` | [Doc](../FMlogic/Request_OMX_SEARCH_FUT.html)

**Purpose:** Searches the existing future-order queue for the subscriber. Identifies conflicts or duplicates with the current offer.

**When active:** FE/BRMS offers with ST=85/86/87 and non-zero price

#### Step 34 — Business Validation Rules ⚠ NOT FOUND

**FM:** `OMX_BIZ_VAL` | **System:** OMX Internal | **Status:** ⚠ Rule file not found

**Purpose:** Applies configurable business validation rules that may reject or modify the order.

> **Migration Impact:** Custom business validation logic is unknown. Missing rules could lead to orders being accepted that should be rejected.

---

### Phase 8 — Pre-Provisioning Calculations (Steps 35–37)

**Business context:** Schedule related companion future offers, calculate full-bill-cycle discounts, and notify the credit evaluation system of new subscriber additions.

#### Step 35 — Schedule Related Companion Future Offer

**FM:** `OMX_ADD_FUT_OFFER` | **System:** OMX Internal | [Doc](../FMlogic/Request_OMX_ADD_FUT_OFFER.html)

**Purpose:** Creates a future-dated order entry for companion offers that must activate alongside a primary future offer (those WITH a `RELATED_OFFER` reference).

**When active:** FE/BRMS future-dated offers exist WITH a `RELATED_OFFER` reference and not IR data offers

#### Step 36 — Calculate Full Billing Cycle Discount

**FM:** `OMX_CAL_DISCOUNT_FULL_BILL` | **System:** OMX Internal | [Doc](../FMlogic/Request_OMX_CAL_DISCOUNT_FULL_BILL.html)

**Purpose:** Computes the discount for offers spanning a full billing cycle. Used for proration when an offer's effective date falls mid-cycle.

**When active:** Future-dated FE/BRMS offers with related offers; skipped for COVID-19 and STUDENT

#### Step 37 — Notify Credit System of New Subscriber

**FM:** `CVSS_UPDATE_SUBSCRIBER_COUNT` | **System:** CVSS | [Doc](../FMlogic/Request_CVSS_UPDATE_SUBSCRIBER_COUNT.html)

**Purpose:** Notifies the credit evaluation system that a new subscriber service has been added. Updates the account's subscriber count for credit limit recalculation.

**When active:** When `EVAL_CREDIT_FLG=Y` and offer is for immediate or logical-date execution

---

### Phase 9 — MultiSIM & Switch Feature Provisioning (Steps 38–46)

**Business context:** Reserve and activate minor SIM resources in ASRM, populate MultiSIM context, obtain service transaction numbers, and call AA to provision MultiSIM (ADD or UPDATE) and standard SwitchFeature services. The two-phase **reserve→activate** pattern ensures idempotent SIM resource allocation.

#### Step 38 — Reserve Minor SIM Resource

**FM:** `ASRM_INVOKE_MINOR_SIM` | **System:** ASRM | **Params:** `ACTIVITY=RESERVE` | [Doc](../FMlogic/Request_ASRM_INVOKE_MINOR_SIM.html)

**Purpose:** Reserves the minor SIM slot in ASRM. Locks the resource preventing concurrent order allocation.

**When active:** FE or BRMS offers present AND `TR_MULTISIM_IND = 'RES'`

#### Step 39 — Copy MultiSIM Info into Order Context

**FM:** `OMX_POPULATE_MSIM_INFO` | **System:** OMX Internal | [Doc](../FMlogic/Request_OMX_POPULATE_MSIM_INFO.html)

**Purpose:** Copies the reserved minor SIM details (MSISDN, IMSI, SIM serial) into the working order context for the AA activation call.

**When active:** FE offers present AND `TR_MULTISIM_IND = 'RES'`

#### Step 40 — Get Transaction Number for MultiSIM Add

**FM:** `OMX_GET_SRV_TRX_NO_MSIM` | **System:** OMX Internal | **Params:** `CCD` | [Doc](../FMlogic/Request_OMX_GET_SRV_TRX_NO_MSIM.html)

**Purpose:** Requests a service transaction number for a new MultiSIM enrollment (ADD). Ensures idempotent processing in AA.

**When active:** Minor SIM Source=FE, SBM_PROVISIONING allowed, immediate or logical-date execution

#### Step 41 — Activate MultiSIM Service (New Enrollment)

**FM:** `AA_ACTIVATE_SUBS_MSIM` | **System:** AA | **Params:** `CCD | ADD` | [Doc](../FMlogic/Request_AA_ACTIVATE_SUBS_MSIM.html)

**Purpose:** Sends the MultiSIM ADD request to AA. Creates the master-minor SIM relationship at the network level.

**When active:** Same as Step 40

#### Step 42 — Get Transaction Number for MultiSIM Update

**FM:** `OMX_GET_SRV_TRX_NO_MSIM` | **System:** OMX Internal | **Params:** `CCD`

**Purpose:** Requests a transaction number for updating an existing MultiSIM association.

**When active:** Previous MultiSIM exists (PREV_MSIM), no RES/RCM conflict, SBM_PROVISIONING allowed, SwitchFeature offer present

#### Step 43 — Activate MultiSIM Service (Update)

**FM:** `AA_ACTIVATE_SUBS_MSIM` | **System:** AA | **Params:** `CCD | UPDATE`

**Purpose:** Sends the MultiSIM UPDATE request to AA. Modifies an existing master-minor SIM relationship.

**When active:** Same as Step 42

#### Step 44 — Get Service Transaction Number (Standard)

**FM:** `OMX_GET_SRV_TRX_NO` | **System:** OMX Internal | **Params:** `CCD` | [Doc](../FMlogic/Request_OMX_GET_SRV_TRX_NO.html)

**Purpose:** Obtains a service transaction number for standard (non-MultiSIM) service activation with a SwitchFeature offer.

**When active:** Not a MultiSIM minor SIM (FE source), not a previous MSIM update, SBM_PROVISIONING allowed, SwitchFeature offer present

#### Step 45 — Activate Subscriber Service (Standard SwitchFeature)

**FM:** `AA_ACTIVATE_SUBS` | **System:** AA | **Params:** `CCD` | [Doc](../FMlogic/Request_AA_ACTIVATE_SUBS.html)

**Purpose:** Sends the standard service activation to AA for SwitchFeature offers. Core provisioning call for handset service upgrades and SIM switches not involving MultiSIM.

**When active:** Same as Step 44

#### Step 46 — Activate Minor SIM Resource in ASRM

**FM:** `ASRM_INVOKE_MINOR_SIM` | **System:** ASRM | **Params:** `ACTIVITY=ACTIVATE`

**Purpose:** Finalizes the minor SIM activation in ASRM after AA creates the MultiSIM link. Completes the reserve→activate lifecycle.

**When active:** FE or BRMS offers present AND `TR_MULTISIM_IND = 'RES'` (same condition as Step 38)

---

### Phase 10 — Credit Limit Management (Steps 47–49)

**Business context:** Calculate and apply credit limit adjustments for corporate postpaid customers (CustomerType=73) adding international roaming or TPC services.

#### Step 47 — Calculate IR Credit Limit Adjustment

**FM:** `OMX_CAL_CREDIT_LIMIT_FOR_IR` | **System:** OMX Internal | [Doc](../FMlogic/Request_OMX_CAL_CREDIT_LIMIT_FOR_IR.html)

**Purpose:** Calculates the credit limit increase needed to accommodate international roaming charges for corporate postpaid accounts.

**When active:** `CAL_CR_FLG=Y`, CustomerType=73, no credit waiver, immediate or logical-date execution

#### Step 48 — Apply Credit Limit Change to Account

**FM:** `CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO` | **System:** CCBS | [Doc](../FMlogic/Request_CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO.html)

**Purpose:** Updates the subscriber's credit limit in CCBS based on the IR calculation from Step 47.

**When active:** `CAL_CR_FLG=Y`, `IS_CHANGE_CREDIT_LIMIT=Y`, CustomerType=73, PersonalCreditLimit > 0

#### Step 49 — Apply TPC Credit Limit Adjustment

**FM:** `CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO` *(same FM as Step 48)* | **System:** CCBS | **Params:** `CAL_CREDITLIMIT=Y | reasonCode=G165`

**Purpose:** Applies a separate credit limit adjustment for TPC SOC offers (reason code G165), independent of the IR credit limit flow.

**When active:** CustomerType=73, TPC SOC present, not a recurring subscription, PersonalCreditLimit > 0

---

### Phase 11 — SBM Data Pack Management (Steps 50–57)

**Business context:** Provision SBM data packs: adjust FUP speed caps, buy data packs (ST 86/87), add 3G prepaid bundles (ST 88), schedule future offers, and cancel or expire existing SBM packs.

#### Step 50 — Adjust Data Speed Cap Maximum

**FM:** `SBM_FUP_CHANGE_CAP_MAX` | **System:** SBM | **Params:** `ADD` | [Doc](../FMlogic/Request_SBM_FUP_CHANGE_CAP_MAX.html)

**Purpose:** Increases the FUP data speed cap maximum in SBM for FCA (Fair Cap Add) special offers.

**When active:** FE or BRMS offers with `SPECIAL_OFFER_INDICATOR=FCA` and immediate or logical-date execution

#### Step 51 — Activate SBM Data Pack

**FM:** `SBM_BUY_DATA_PACK` | **System:** SBM | [Doc](../FMlogic/Request_SBM_BUY_DATA_PACK.html)

**Purpose:** Provisions a data pack through SBM for service types 86 (data add-on) and 87 (SBM-managed data services). Primary SBM activation call.

**When active:** SBM_PROVISIONING allowed AND FE or BRMS offers with ST=86 or 87

#### Step 52 — Add 3G Prepaid Bundle via SBM

**FM:** `SBM_ADD_3GPREPAID` | **System:** SBM | [Doc](../FMlogic/Request_SBM_ADD_3GPREPAID.html)

**Purpose:** Adds a 3G prepaid data bundle (service type 88) through SBM. Used for hybrid prepaid/postpaid bundle offers.

**When active:** FE or BRMS offers with ST=88

#### Step 53 — Schedule Standalone Future Offer

**FM:** `OMX_ADD_FUT_OFFER` | **System:** OMX Internal

**Purpose:** Creates a future-dated order entry for FE/BRMS offers WITHOUT a RELATED_OFFER reference (contrast with Step 35 which handles offers WITH related offers).

**When active:** FE or BRMS future-dated offers exist WITHOUT a `RELATED_OFFER` reference

#### Step 54 — Resolve SOC Code for SBM Pack Cancellation

**FM:** `CCBS_RESOLVE_SOC_CODE` | **System:** CCBS

**Purpose:** Looks up the SOC code for existing SBM offers needing immediate cancellation that are missing their SOC.

**When active:** SBM offer missing SOC and `EXP_TYPE=IM`

#### Step 55 — Cancel SBM Pack (Immediate)

**FM:** `CCBS_CHANGE_PACKAGE_SUBSCRIBER` | **System:** CCBS | **Params:** `REMOVE`

**Purpose:** Removes an existing SBM data pack from CCBS. Used when replacing an existing SBM pack with the new offer being added.

**When active:** SBM offers flagged for immediate expiry (`EXP_TYPE=IM`)

#### Step 56 — Schedule SBM Pack for Future Expiry

**FM:** `OMX_ADD_FUT_OFFER` | **System:** OMX Internal

**Purpose:** Creates a future-dated order to expire the current SBM pack at the next billing cycle boundary. Used when transitioning packs on a future date rather than immediately.

**When active:** SBM offers flagged for future-dated expiry (`EXP_TYPE=FUT`)

#### Step 57 — Update Network Status Post-SBM ⚠ NOT FOUND

**FM:** `UPDATE_NETWORK_STATUS` | **System:** Unknown | **Status:** ⚠ Rule file not found

**Purpose:** Updates the network-level provisioning status after SBM data pack provisioning for ST=86 and ST=87.

> **Migration Impact:** Post-SBM network status update logic is undocumented. May be handled by SBM internally.

---

### Phase 12 — Billing Charges (Step 58)

#### Step 58 — Create One-Time Billing Charge

**FM:** `BL_CREATE_CHARGE` | **System:** BL Billing | [Doc](../FMlogic/Request_BL_CREATE_CHARGE.html)

**Purpose:** Creates a one-time charge entry in the BL billing system for service type 79 (manual/one-time fee) offers. Generates the billing record for the subscriber's next invoice.

**When active:** FE or BRMS offers with ST=79 and immediate or logical-date execution

---

### Phase 13 — CCBS Package Provisioning (Steps 59–63)

**Business context:** Core CCBS package changes: remove old packages, add new packages, and register content subscriptions with MCS. These are the primary activation calls for most offer service types.

#### Step 59 — Remove Old Package from Subscriber

**FM:** `CCBS_CHANGE_PACKAGE_SUBSCRIBER` | **System:** CCBS | **Params:** `REMOVE`

**Purpose:** Removes the subscriber's existing package(s) for FE_REMOVE type offers being replaced. Handles ST=85/86/87/68.

**When active:** FE_REMOVE offers with ST=85/86/87/68, not EFF_ORD_DT, not LOGICALDATE_PROV

#### Step 60 — Remove Old Loyalty SOC Package

**FM:** `CCBS_CHANGE_PACKAGE_SUBSCRIBER` | **System:** CCBS | **Params:** `REMOVE`

**Purpose:** Removes the subscriber's previous loyalty SOC package when upgrading loyalty offer.

**When active:** `CCBS OLD_LOYALTY_SOC = 'Y'`

#### Step 61 — Add New Package to Subscriber

**FM:** `CCBS_CHANGE_PACKAGE_SUBSCRIBER` | **System:** CCBS | **Params:** `ADD`

**Purpose:** **Primary CCBS provisioning call** — adds the new offer package, activating the new service contract/SOC for ST=85/86/87/68.

**When active:** FE or BRMS offers with ST=85/86/87/68, not EFF_ORD_DT, not LOGICALDATE_PROV

#### Step 62 — Register Recurring MCS Subscription

**FM:** `MCS_REGISTER_SUBSCRIPTION` | **System:** MCS | **Params:** `USE_FE_RECURRING=Y` | [Doc](../FMlogic/Request_MCS_REGISTER_SUBSCRIPTION.html)

**Purpose:** Registers a recurring content subscription in MCS (ST=69) using the front-end recurring flow.

**When active:** FE or BRMS offers with ST=69 that are not TPC-branded

#### Step 63 — Register TPC Content Service in MCS

**FM:** `MCS_REGISTER` | **System:** MCS | [Doc](../FMlogic/Request_MCS_REGISTER.html)

**Purpose:** Registers a TPC (True Partner Content) subscription or one-time service in MCS for ST=85 and 69.

**When active:** TPC-branded offers (`TR_SPECIAL_OFFER_IND=TPC`) with ST=85 or 69, not RECURRING_SOC

---

### Phase 14 — Knox Enterprise Device Management (Steps 64–70)

**Business context:** Register and activate devices in Samsung Knox MDM. Publishes ADD and NOTIFY events to Kafka. Knox steps fire only when IMEI_KNOX is populated on the offer.

#### Step 64 — Fetch Knox Device Information

**FM:** `PSA_GET_DEVICE_INFO` | **System:** PSA | [Doc](../FMlogic/Request_PSA_GET_DEVICE_INFO.html)

**Purpose:** Fetches the device's current Knox MDM enrollment status from PSA. Required before saving or updating Knox-enrolled devices.

**When active:** Any FE, BRMS, or CCBS offer with IMEI_KNOX populated

#### Step 65 — Register Device in Knox MDM

**FM:** `KNOX_SAVE_DEVICE` | **System:** Knox MDM | [Doc](../FMlogic/Request_KNOX_SAVE_DEVICE.html)

**Purpose:** Registers or updates the device in Samsung Knox MDM. Creates the Knox enrollment record enabling enterprise MDM capabilities.

**When active:** FE or BRMS offers with IMEI_KNOX present

#### Step 66 — Publish Knox Device Add Event to Kafka

**FM:** `OMX_NOTI_TO_KAFKA` | **System:** Kafka | **Params:** `knoxEvent=ADD` | [Doc](../FMlogic/Request_OMX_NOTI_TO_KAFKA.html)

**Purpose:** Publishes a Knox 'ADD' event to the Kafka event stream. Notifies downstream consumers that a new device has been enrolled.

**When active:** FE or BRMS offers with IMEI_KNOX present

#### Step 67 — Activate Knox Device Status

**FM:** `PSA_UPDATE_KNOX_STATUS` | **System:** PSA | **Params:** `KNOX_STATUS=ACTIVE` | [Doc](../FMlogic/Request_PSA_UPDATE_KNOX_STATUS.html)

**Purpose:** Sets the device's Knox status to ACTIVE in PSA. Completes the Knox enrollment lifecycle.

**When active:** FE or BRMS offers with IMEI_KNOX present

#### Step 68 — Send Knox B2B Device Notification

**FM:** `KNOX_NOTIFICATION_DEVICE` | **System:** Knox / BSNS | **Params:** `TEL=1242` | [Doc](../FMlogic/Request_KNOX_NOTIFICATION_DEVICE.html)

**Purpose:** Sends a Knox device notification to the enterprise B2B system for BSNS orders. Notifies the enterprise Knox administrator that a new device has been enrolled.

**When active:** BSNS orders with CCBS Knox IMEI enrolled and `COLLECTION_IND != 'N'`

#### Step 69 — Publish Knox Notify Event to Kafka

**FM:** `OMX_NOTI_TO_KAFKA` | **System:** Kafka | **Params:** `knoxEvent=NOTIFY`

**Purpose:** Publishes a Knox 'NOTIFY' event to Kafka signaling Knox device notification is complete.

**When active:** Same as Step 68

#### Step 70 — Update Device Status to Active in PSA

**FM:** `PSA_UPDATE_DEVICE` | **System:** PSA | **Params:** `deviceStatus=ACTIVE` | [Doc](../FMlogic/Request_PSA_UPDATE_DEVICE.html)

**Purpose:** Updates the device's overall status to ACTIVE in PSA for material/device items not associated with FE or CCBS offers.

**When active:** MaterialInfo present AND no FE_OR_CCBS ExtendedInfo flag

---

### Phase 15 — Supplementary & Ancillary Actions (Steps 71–79)

**Business context:** Handle specialized add-ons: TDG IoT subscriber creation, next-offer pre-booking, installment sale contracts, subscriber/account updates, SBM memos, and cleanup of conflicting future offers.

#### Step 71 — Create TDG IoT/Data Subscriber

**FM:** `TDG_CREATE_SUBSCRIBER` | **System:** TDG | [Doc](../FMlogic/Request_TDG_CREATE_SUBSCRIBER.html)

**Purpose:** Creates a subscriber record in the TDG IoT platform for service type 70 (IoT/M2M data service).

**When active:** Any subscriber offer has ST=70

#### Step 72 — Schedule Next-Cycle Offer

**FM:** `OMX_ADD_NEXT_OFFER` | **System:** OMX Internal | **Status:** — Skipped

**Purpose:** Creates a 'next offer' record in OMX to pre-schedule the subscriber's next renewal for the following billing cycle.

**When active:** FE or BRMS offers with ST=85/86/87/68 for immediate execution

#### Step 73 — Register Device Installment Sale

**FM:** `BDH_INSTALLMENT_SALE` | **System:** BDH | [Doc](../FMlogic/Request_BDH_INSTALLMENT_SALE.html)

**Purpose:** Creates an installment sale contract in BDH for device financing offers (`TR_OFFER_GROUP=CT_INST`). Establishes the monthly payment schedule.

**When active:** FE offers include related offers with `TR_OFFER_GROUP=CT_INST`

#### Step 74 — Update Subscriber Identity Info (IMSI/SIM)

**FM:** `CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO` | **System:** CCBS | [Doc](../FMlogic/Request_CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO.html)

**Purpose:** Updates the subscriber's general information in CCBS — primarily IMSI alias assignment or SIM split period data.

**When active:** When `count(IMSIAlias) > 0` or `count(SplitPeriod) > 0`

#### Step 75 — Update Account Billing Address

**FM:** `CCBS_UPDATE_ACCOUNT_NAME_ADDRESS` | **System:** CCBS | [Doc](../FMlogic/Request_CCBS_UPDATE_ACCOUNT_NAME_ADDRESS.html)

**Purpose:** Updates the account's name and address in CCBS when a new payment channel with different billing details is selected.

**When active:** When `count(PayChannelFeeInfo) > 0`

#### Step 76 — Create SBM Transaction Memo in CCBS

**FM:** `CCBS_CREATE_MEMO_FOR_SBM` | **System:** CCBS | **Params:** `ENTITY_TYPE_ID=6 | MEMO_TYPE_ID=90051 | MEMO_SYSTEM_TEXT=082` | [Doc](../FMlogic/Request_CCBS_CREATE_MEMO_FOR_SBM.html)

**Purpose:** Creates an audit memo in CCBS documenting the SBM data pack transaction. Provides a human-readable service history note visible to CS agents.

**When active:** SBM_PROVISIONING active, FE/BRMS offer ST=86, immediate or logical-date execution

#### Step 77 — Set Order Status to Creating Profile ⚠ NOT FOUND

**FM:** `STATUS_UPDATE_CREATING_PROFILE` | **System:** Unknown | **Status:** ⚠ Rule file not found

**Purpose:** Updates the OMX order status to indicate the profile creation phase has begun.

> **Migration Impact:** Order status lifecycle is incomplete. The "Creating Profile" status transition is not captured.

#### Step 78 — Expire Conflicting Future Offer

**FM:** `OMX_EXP_FUT_OFFER` | **System:** OMX Internal | **Status:** — Skipped

**Purpose:** Expires an existing future-dated order superseded by the current offer activation.

**When active:** Immediate FE/BRMS offers (ST≠69) with conflicting future-dated record (`EXP_TYPE=FUT`); skipped for COVID-19

#### Step 79 — Expire Future Related/Companion Offer

**FM:** `OMX_EXP_FUT_RELATED_OFFER` | **System:** OMX Internal | [Doc](../FMlogic/Request_OMX_EXP_FUT_RELATED_OFFER.html)

**Purpose:** Expires existing future-dated related/companion offers superseded by the current activation.

**When active:** RelatedOffersArray FE/BRMS offers are immediate-effective but have `EXP_TYPE=FUT`; skipped for COVID-19 and STUDENT

---

### Phase 16 — Order Completion & Notification (Steps 80–84)

**Business context:** Finalize the order: verify AA activation, send customer SMS, trigger CBSC opt-in/out, and submit loyalty benefit and IR removal child orders to OMX.

#### Step 80 — Verify Service Activation Confirmation

**FM:** `AA_CHECK_CONFIRMATION` | **System:** AA | **Params:** `CCD | UPDATE_NETWORK_STATUS` | **Status:** — Skipped

**Purpose:** Verifies that AA service activation (Steps 41–45) has been confirmed. **Synchronization gate** — ensures provisioning is fully confirmed before customer notifications.

**When active:** MultiSIMInfo present OR (SBM_PROVISIONING allowed AND SwitchFeature offer present AND immediate/logical-date execution)

#### Step 81 — Send SMS Notification to Subscriber

**FM:** `SMSGATEWAY_SEND_SMS` | **System:** SMS Gateway | [Doc](../FMlogic/Request_SMSGATEWAY_SEND_SMS.html)

**Purpose:** Sends a service confirmation SMS to the subscriber's mobile number. Informs the customer that their new service has been activated.

**When active:** Subscriber has a MSISDN, and the channel is not CCBS/OMX (excluding ST=68), OR is SFF channel with ST=68 or 85

#### Step 82 — Trigger CBSC Offer Opt-In via API Gateway

**FM:** `APIGW_OPT_IN_OUT` | **System:** APIGW / CBSC | **Params:** `ACTION=1` | [Doc](../FMlogic/Request_APIGW_OPT_IN_OUT.html)

**Purpose:** Sends an opt-in request to the API Gateway for CBSC (Central Bundled Service Center) offers. Registers the subscriber's enrollment with CBSC.

**When active:** FE offers with `TR_OFFER_GROUP=CBSC` in SocProperties

#### Step 83 — Submit Loyalty Benefit Child Order

**FM:** `OMX_SUBMIT_POSTPAID_ADD_BENEFIT` | **System:** OMX Child Order | **Params:** `ORDER_TYPE=11022` | [Doc](../FMlogic/Request_OMX_SUBMIT_POSTPAID_ADD_BENEFIT.html)

**Purpose:** Submits a child order to OMX to provision loyalty benefit services. Fans out one child order per subscriber (POU and COU). Uses `TR_SPECIAL_OFFER_IND=LY` filter. Response captures `childOmxTrackingId`.

**When active:** Order includes LOYALTY extended info (subscriber qualifies for loyalty benefit); skipped for COVID-19

```xpath
ExtendedInfo LOYALTY != ""
and not(starts-with(OrderID,"COVID19"))
```

#### Step 84 — Submit IR Add-On Pack Removal Child Order

**FM:** `OMX_SUBMIT_REMOVE_OFFER` | **System:** OMX Child Order | **Params:** `ORDER_TYPE=4 | SERVICE_TYPE=85` | [Doc](../FMlogic/Request_OMX_SUBMIT_REMOVE_OFFER.html)

**Purpose:** Submits a child order to OMX to remove an existing IR (International Roaming) add-on pack. Uses REMOVE_PACK ExtendedInfo filter.

> **⚠ Known bugs:** `orderId = 'IR_'+OrderID` — not unique per subscriber when fan-out occurs; logger blocks have wrong `OPERATION_NAME`.

**When active:** `ADD_IR_PACK = 'Y'` in the order's extended info

---

## §4 — Technical Reference Table

| # | Step ExtId | FM (ActivityID) | System | Parameter(s) | Trigger Condition | Doc |
|---|-----------|-----------------|--------|--------------|-------------------|-----|
| 1 | IOM_CHECK_SEQUENCING | `IOM_CHECK_SEQUENCING` | OMX Internal | — | POMX_ETG or APPLE | [link](../FMlogic/Request_IOM_CHECK_SEQUENCING.html) |
| 2 | CCBS_GET_SUBSCRIBER_HEADER | `CCBS_GET_SUBSCRIBER_HEADER` | CCBS | — | SubscriberId present | [link](../FMlogic/Request_CCBS_GET_SUBSCRIBER_HEADER.html) |
| 3 | CCBS_GET_CUST_ACC_SUB_ID | `CCBS_GET_CUST_ACC_SUB_ID` | CCBS | — | Always | [link](../FMlogic/Request_CCBS_GET_CUST_ACC_SUB_ID.html) |
| 4 | CCBS_GET_CUSTOMER_HEADER | `CCBS_GET_CUSTOMER_HEADER` | CCBS | GET_NAME_ADDRESS=Y | Always | [link](../FMlogic/Request_CCBS_GET_CUSTOMER_HEADER.html) |
| 5 | BLACKLIST_CHECK_BLACKLIST | `BLACKLIST_CHECK_BLACKLIST` | Blacklist | — | Not COVID19/STUDENT/type=70 | [link](../FMlogic/Request_BLACKLIST_CHECK_BLACKLIST.html) |
| 6 | BLACKLIST_CHECK_COLL_BY_ID_NUM | `BLACKLIST_CHECK_COLL_BY_ID_NUM` | Blacklist | — | Same as Step 5 | [link](../FMlogic/Request_BLACKLIST_CHECK_COLL_BY_ID_NUM.html) |
| 7 | BLACKLIST_CHECK_FRAUD | `BLACKLIST_CHECK_FRAUD` | Blacklist | — | Same as Step 5 | [link](../FMlogic/Request_BLACKLIST_CHECK_FRAUD.html) |
| 8 | CCBS_GET_ACCOUNT_HEADER | `CCBS_GET_ACCOUNT_HEADER` | CCBS | — | Always | [link](../FMlogic/Request_CCBS_GET_ACCOUNT_HEADER.html) |
| 9 | CCBS_GET_BA_HEADER | `CCBS_GET_BA_HEADER` | CCBS | GET_NAME_ADDRESS=Y | Always | [link](../FMlogic/Request_CCBS_GET_BA_HEADER.html) |
| 10 | CCBS_GET_AGREEMENT_HEADER | `CCBS_GET_AGREEMENT_HEADER` | CCBS | — | Always | [link](../FMlogic/Request_CCBS_GET_AGREEMENT_HEADER.html) |
| 11 | CCBS_GET_SUBS_INFO | `CCBS_GET_SUBS_INFO` | CCBS | — | Status≠67/76/84 | [link](../FMlogic/Request_CCBS_GET_SUBS_INFO.html) |
| 12 | INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST | `INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST` | INTX | — | BSNS + Knox IMEI | [link](../FMlogic/Request_INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST.html) |
| 13 | CCBS_RESOLVE_SOC_CODE | `CCBS_RESOLVE_SOC_CODE` | CCBS | — | Missing SOC | [link](../FMlogic/Request_CCBS_RESOLVE_SOC_CODE.html) |
| 14 | CCBS_GOD | `CCBS_GOD` | CCBS | — | FE or BRMS offers | [link](../FMlogic/Request_CCBS_GOD.html) |
| 15 | OMX_BRMS_DB | `OMX_BRMS_DB` | OMX/BRMS | — | FE offers, not COVID19/BSNS/STUDENT | [link](../FMlogic/Request_OMX_BRMS_DB.html) |
| 16 | CCBS_RESOLVE_SOC_CODE_BRMS | `CCBS_RESOLVE_SOC_CODE` | CCBS | — | BRMS offers | [link](../FMlogic/Request_CCBS_RESOLVE_SOC_CODE.html) |
| 17 | CCBS_GOD_BRMS | `CCBS_GOD` | CCBS | — | BRMS offers | [link](../FMlogic/Request_CCBS_GOD.html) |
| 18 | OMX_RESOLVE_SOC_DATA | `OMX_RESOLVE_SOC_DATA` | OMX Internal | — | Not COVID19 | [link](../FMlogic/Request_OMX_RESOLVE_SOC_DATA.html) |
| 19 | MCS_GET_CHARGE_INFO | `MCS_GET_CHARGE_INFO` | MCS | — | TPC ST=85/69, not recurring | [link](../FMlogic/Request_MCS_GET_CHARGE_INFO.html) |
| 20 | OMX_GET_FUT_INFO_BY_SUB | `OMX_GET_FUT_INFO_BY_SUB` | OMX Internal | — | Not COVID19 | [link](../FMlogic/Request_OMX_GET_FUT_INFO_BY_SUB.html) |
| 21 | OMX_CAL_OFFER_FUT_DATE | `OMX_CAL_OFFER_FUT_DATE` | OMX Internal | CAL_PARAM_EXP=Y | FE/BRMS EFF_TYPE=FUT | [link](../FMlogic/Request_OMX_CAL_OFFER_FUT_DATE.html) |
| 22 | OMX_OFFER_INCLUSION | `OMX_OFFER_INCLUSION` | OMX Internal | — | Not EOC/COVID19/STUDENT | ⚠ Not Found |
| 23 | CCBS_OFFER_EXCLUSION | `CCBS_OFFER_EXCLUSION` | CCBS | — | Not COVID19/STUDENT | [link](../FMlogic/Request_CCBS_OFFER_EXCLUSION.html) |
| 24 | OMX_GET_OFFER_RATE | `OMX_GET_OFFER_RATE` | OMX Internal | — | FE/BRMS ST=85/68 | [link](../FMlogic/Request_OMX_GET_OFFER_RATE.html) |
| 25 | BL_LIST_UNINVOICED_CHARGES | `BL_LIST_UNINVOICED_CHARGES` | BL Billing | — | FE/BRMS ST=85/86/87, rate>0 | [link](../FMlogic/Request_BL_LIST_UNINVOICED_CHARGES.html) |
| 26 | MLDD_GET_SUB_DATA | `MLDD_GET_SUB_DATA` | MLDD | — | MCS_PACKCODE+FLOW_ID present | [link](../FMlogic/Request_MLDD_GET_SUB_DATA.html) |
| 27 | MCS_SUBSCRIPTION_MARKUSED | `MCS_SUBSCRIPTION_MARKUSED` | MCS | DEFAULT_FLOW_ID=FVM003 | FE/BRMS ST=69 | [link](../FMlogic/Request_MCS_SUBSCRIPTION_MARKUSED.html) |
| 28 | INTX_GET_TOTAL_OBLIGATION_INFO | `INTX_GET_TOTAL_OBLIGATION_INFO` | INTX | — | Complex credit check gate | [link](../FMlogic/Request_INTX_GET_TOTAL_OBLIGATION_INFO.html) |
| 29 | AA_GET_SWITCH_FEATURE_OFFER | `AA_GET_SWITCH_FEATURE_OFFER` | AA | — | Immediate/LOGICALDATE | [link](../FMlogic/Request_AA_GET_SWITCH_FEATURE_OFFER.html) |
| 30 | GET_SPECIAL_OFFER_INDICATOR | `GET_SPECIAL_OFFER_INDICATOR` | OMX Internal | ADD_PROP=TR_MULTISIM_IND\|CHECK_LOYALTY_SOC=Y | Immediate/LOGICALDATE | [link](../FMlogic/Request_GET_SPECIAL_OFFER_INDICATOR.html) |
| 31 | INTX_GET_SIM_INFO_BY_SIM | `INTX_GET_SIM_INFO_BY_SIM` | INTX | — | TR_MULTISIM_IND=RES | [link](../FMlogic/Request_INTX_GET_SIM_INFO_BY_SIM.html) |
| 32 | INTX_GET_MASTER_MINOR_SIM_INFO | `INTX_GET_MASTER_MINOR_SIM_INFO` | INTX | — | TR_MULTISIM_IND=RES or REE | [link](../FMlogic/Request_INTX_GET_MASTER_MINOR_SIM_INFO.html) |
| 33 | OMX_SEARCH_FUT | `OMX_SEARCH_FUT` | OMX Internal | STATUS=1\|ORDER_TYPE=12 | FE/BRMS ST=85/86/87, rate>0 | [link](../FMlogic/Request_OMX_SEARCH_FUT.html) |
| 34 | OMX_BIZ_VAL | `OMX_BIZ_VAL` | OMX Internal | — | Not COVID19/STUDENT | ⚠ Not Found |
| 35 | OMX_ADD_FUT_OFFER_RELATED | `OMX_ADD_FUT_OFFER` | OMX Internal | — | FE/BRMS FUT+RELATED_OFFER | [link](../FMlogic/Request_OMX_ADD_FUT_OFFER.html) |
| 36 | OMX_CAL_DISCOUNT_FULL_BILL | `OMX_CAL_DISCOUNT_FULL_BILL` | OMX Internal | — | FE/BRMS FUT+RELATED_OFFER | [link](../FMlogic/Request_OMX_CAL_DISCOUNT_FULL_BILL.html) |
| 37 | CVSS_UPDATE_SUBSCRIBER_COUNT | `CVSS_UPDATE_SUBSCRIBER_COUNT` | CVSS | — | EVAL_CREDIT_FLG=Y | [link](../FMlogic/Request_CVSS_UPDATE_SUBSCRIBER_COUNT.html) |
| 38 | ASRM_INVOKE_MINOR_SIM_RESERVE | `ASRM_INVOKE_MINOR_SIM` | ASRM | ACTIVITY=RESERVE | FE/BRMS+TR_MULTISIM_IND=RES | [link](../FMlogic/Request_ASRM_INVOKE_MINOR_SIM.html) |
| 39 | OMX_POPULATE_MSIM_INFO | `OMX_POPULATE_MSIM_INFO` | OMX Internal | — | FE+TR_MULTISIM_IND=RES | [link](../FMlogic/Request_OMX_POPULATE_MSIM_INFO.html) |
| 40 | OMX_GET_SRV_TRX_NO_MSIM_ADD | `OMX_GET_SRV_TRX_NO_MSIM` | OMX Internal | CCD | Minor FE, SBM_PROV OK | [link](../FMlogic/Request_OMX_GET_SRV_TRX_NO_MSIM.html) |
| 41 | AA_ACTIVATE_SUBS_MSIM_ADD | `AA_ACTIVATE_SUBS_MSIM` | AA | CCD\|ADD | Same as Step 40 | [link](../FMlogic/Request_AA_ACTIVATE_SUBS_MSIM.html) |
| 42 | OMX_GET_SRV_TRX_NO_MSIM_UPDATE | `OMX_GET_SRV_TRX_NO_MSIM` | OMX Internal | CCD | PREV_MSIM+SwitchFeature | [link](../FMlogic/Request_OMX_GET_SRV_TRX_NO_MSIM.html) |
| 43 | AA_ACTIVATE_SUBS_MSIM_UPDATE | `AA_ACTIVATE_SUBS_MSIM` | AA | CCD\|UPDATE | Same as Step 42 | [link](../FMlogic/Request_AA_ACTIVATE_SUBS_MSIM.html) |
| 44 | OMX_GET_SRV_TRX_NO | `OMX_GET_SRV_TRX_NO` | OMX Internal | CCD | Not minor FE, SwitchFeature | [link](../FMlogic/Request_OMX_GET_SRV_TRX_NO.html) |
| 45 | AA_ACTIVATE_SUBS | `AA_ACTIVATE_SUBS` | AA | CCD | Same as Step 44 | [link](../FMlogic/Request_AA_ACTIVATE_SUBS.html) |
| 46 | ASRM_INVOKE_MINOR_SIM_ACTIVATE | `ASRM_INVOKE_MINOR_SIM` | ASRM | ACTIVITY=ACTIVATE | FE/BRMS+TR_MULTISIM_IND=RES | [link](../FMlogic/Request_ASRM_INVOKE_MINOR_SIM.html) |
| 47 | OMX_CAL_CREDIT_LIMIT_FOR_IR | `OMX_CAL_CREDIT_LIMIT_FOR_IR` | OMX Internal | — | CAL_CR_FLG=Y, CustomerType=73 | [link](../FMlogic/Request_OMX_CAL_CREDIT_LIMIT_FOR_IR.html) |
| 48 | CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO | `CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO` | CCBS | — | IS_CHANGE_CREDIT_LIMIT=Y | [link](../FMlogic/Request_CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO.html) |
| 49 | CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO_TPC | `CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO` | CCBS | CAL_CREDITLIMIT=Y\|reasonCode=G165 | CustomerType=73, TPC SOC | [link](../FMlogic/Request_CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO.html) |
| 50 | SBM_FUP_CHANGE_CAP_MAX | `SBM_FUP_CHANGE_CAP_MAX` | SBM | ADD | FE/BRMS SPECIAL_OFFER_IND=FCA | [link](../FMlogic/Request_SBM_FUP_CHANGE_CAP_MAX.html) |
| 51 | SBM_BUY_DATA_PACK | `SBM_BUY_DATA_PACK` | SBM | — | SBM_PROV+FE/BRMS ST=86/87 | [link](../FMlogic/Request_SBM_BUY_DATA_PACK.html) |
| 52 | SBM_ADD_3GPREPAID | `SBM_ADD_3GPREPAID` | SBM | — | FE/BRMS ST=88 | [link](../FMlogic/Request_SBM_ADD_3GPREPAID.html) |
| 53 | OMX_ADD_FUT_OFFER | `OMX_ADD_FUT_OFFER` | OMX Internal | — | FE/BRMS FUT, no RELATED_OFFER | [link](../FMlogic/Request_OMX_ADD_FUT_OFFER.html) |
| 54 | CCBS_RESOLVE_SOC_CODE_SBM_CANCEL | `CCBS_RESOLVE_SOC_CODE` | CCBS | — | SBM missing SOC+EXP_TYPE=IM | [link](../FMlogic/Request_CCBS_RESOLVE_SOC_CODE.html) |
| 55 | SBM_CANCEL_PACK | `CCBS_CHANGE_PACKAGE_SUBSCRIBER` | CCBS | REMOVE | SBM EXP_TYPE=IM | [link](../FMlogic/Request_CCBS_CHANGE_PACKAGE_SUBSCRIBER.html) |
| 56 | SBM_EXPIRE_PACK | `OMX_ADD_FUT_OFFER` | OMX Internal | — | SBM EXP_TYPE=FUT | [link](../FMlogic/Request_OMX_ADD_FUT_OFFER.html) |
| 57 | UPDATE_NETWORK_STATUS | `UPDATE_NETWORK_STATUS` | Unknown | — | SBM_PROV+FE/BRMS ST=86/87 | ⚠ Not Found |
| 58 | BL_CREATE_CHARGE | `BL_CREATE_CHARGE` | BL Billing | — | FE/BRMS ST=79 | [link](../FMlogic/Request_BL_CREATE_CHARGE.html) |
| 59 | CCBS_CHANGE_PACKAGE_SUBSCRIBER_REMOVE | `CCBS_CHANGE_PACKAGE_SUBSCRIBER` | CCBS | REMOVE | FE_REMOVE ST=85/86/87/68 | [link](../FMlogic/Request_CCBS_CHANGE_PACKAGE_SUBSCRIBER.html) |
| 60 | CCBS_CHANGE_PACKAGE_SUBSCRIBER_REMOVE_LOYALTY | `CCBS_CHANGE_PACKAGE_SUBSCRIBER` | CCBS | REMOVE | OLD_LOYALTY_SOC=Y | [link](../FMlogic/Request_CCBS_CHANGE_PACKAGE_SUBSCRIBER.html) |
| 61 | CCBS_CHANGE_PACKAGE_SUBSCRIBER | `CCBS_CHANGE_PACKAGE_SUBSCRIBER` | CCBS | ADD | FE/BRMS ST=85/86/87/68 | [link](../FMlogic/Request_CCBS_CHANGE_PACKAGE_SUBSCRIBER.html) |
| 62 | MCS_REGISTER_SUBSCRIPTION | `MCS_REGISTER_SUBSCRIPTION` | MCS | USE_FE_RECURRING=Y | FE/BRMS ST=69, not TPC | [link](../FMlogic/Request_MCS_REGISTER_SUBSCRIPTION.html) |
| 63 | MCS_REGISTER | `MCS_REGISTER` | MCS | — | TPC ST=85/69, not recurring | [link](../FMlogic/Request_MCS_REGISTER.html) |
| 64 | PSA_GET_DEVICE_INFO | `PSA_GET_DEVICE_INFO` | PSA | — | IMEI_KNOX present | [link](../FMlogic/Request_PSA_GET_DEVICE_INFO.html) |
| 65 | KNOX_SAVE_DEVICE | `KNOX_SAVE_DEVICE` | Knox MDM | — | FE/BRMS IMEI_KNOX | [link](../FMlogic/Request_KNOX_SAVE_DEVICE.html) |
| 66 | OMX_NOTIFY_KNOX_EVENT | `OMX_NOTI_TO_KAFKA` | Kafka | knoxEvent=ADD | FE/BRMS IMEI_KNOX | [link](../FMlogic/Request_OMX_NOTI_TO_KAFKA.html) |
| 67 | PSA_UPDATE_KNOX_STATUS | `PSA_UPDATE_KNOX_STATUS` | PSA | KNOX_STATUS=ACTIVE | FE/BRMS IMEI_KNOX | [link](../FMlogic/Request_PSA_UPDATE_KNOX_STATUS.html) |
| 68 | KNOX_NOTIFICATION_DEVICE | `KNOX_NOTIFICATION_DEVICE` | Knox/BSNS | TEL=1242 | BSNS+CCBS Knox IMEI | [link](../FMlogic/Request_KNOX_NOTIFICATION_DEVICE.html) |
| 69 | OMX_NOTIFY_KNOX_EVENT_NOTIFY | `OMX_NOTI_TO_KAFKA` | Kafka | knoxEvent=NOTIFY | Same as Step 68 | [link](../FMlogic/Request_OMX_NOTI_TO_KAFKA.html) |
| 70 | PSA_UPDATE_DEVICE | `PSA_UPDATE_DEVICE` | PSA | deviceStatus=ACTIVE | MaterialInfo, no FE_OR_CCBS | [link](../FMlogic/Request_PSA_UPDATE_DEVICE.html) |
| 71 | TDG_CREATE_SUBSCRIBER | `TDG_CREATE_SUBSCRIBER` | TDG | — | ST=70 | [link](../FMlogic/Request_TDG_CREATE_SUBSCRIBER.html) |
| 72 | OMX_ADD_NEXT_OFFER | `OMX_ADD_NEXT_OFFER` | OMX Internal | — | FE/BRMS ST=85/86/87/68, immediate | — Skipped |
| 73 | BDH_INSTALLMENT_SALE | `BDH_INSTALLMENT_SALE` | BDH | — | FE TR_OFFER_GROUP=CT_INST | [link](../FMlogic/Request_BDH_INSTALLMENT_SALE.html) |
| 74 | CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO | `CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO` | CCBS | — | IMSIAlias or SplitPeriod | [link](../FMlogic/Request_CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO.html) |
| 75 | CCBS_UPDATE_ACCOUNT_NAME_ADDRESS | `CCBS_UPDATE_ACCOUNT_NAME_ADDRESS` | CCBS | — | PayChannelFeeInfo present | [link](../FMlogic/Request_CCBS_UPDATE_ACCOUNT_NAME_ADDRESS.html) |
| 76 | CCBS_CREATE_MEMO_FOR_SBM | `CCBS_CREATE_MEMO_FOR_SBM` | CCBS | ENTITY_TYPE_ID=6\|MEMO_TYPE_ID=90051 | SBM_PROV+FE/BRMS ST=86 | [link](../FMlogic/Request_CCBS_CREATE_MEMO_FOR_SBM.html) |
| 77 | STATUS_UPDATE_CREATING_PROFILE | `STATUS_UPDATE_CREATING_PROFILE` | Unknown | — | Immediate/LOGICALDATE | ⚠ Not Found |
| 78 | OMX_EXP_FUT_OFFER | `OMX_EXP_FUT_OFFER` | OMX Internal | — | Immediate FE/BRMS, EXP_TYPE=FUT | — Skipped |
| 79 | OMX_EXP_FUT_RELATED_OFFER | `OMX_EXP_FUT_RELATED_OFFER` | OMX Internal | — | RelatedOffers FUT | [link](../FMlogic/Request_OMX_EXP_FUT_RELATED_OFFER.html) |
| 80 | AA_CHECK_CONFIRMATION | `AA_CHECK_CONFIRMATION` | AA | CCD\|UPDATE_NETWORK_STATUS | MultiSIMInfo or SwitchFeature | — Skipped |
| 81 | SMSGATEWAY_SEND_SMS | `SMSGATEWAY_SEND_SMS` | SMS Gateway | — | Has MSISDN, non-backoffice | [link](../FMlogic/Request_SMSGATEWAY_SEND_SMS.html) |
| 82 | APIGW_OPT_IN_OUT | `APIGW_OPT_IN_OUT` | APIGW/CBSC | ACTION=1 | FE TR_OFFER_GROUP=CBSC | [link](../FMlogic/Request_APIGW_OPT_IN_OUT.html) |
| 83 | OMX_SUBMIT_POSTPAID_ADD_BENEFIT | `OMX_SUBMIT_POSTPAID_ADD_BENEFIT` | OMX Child | ORDER_TYPE=11022 | LOYALTY extended info | [link](../FMlogic/Request_OMX_SUBMIT_POSTPAID_ADD_BENEFIT.html) |
| 84 | OMX_SUBMIT_REMOVE_OFFER_IR | `OMX_SUBMIT_REMOVE_OFFER` | OMX Child | ORDER_TYPE=4\|SERVICE_TYPE=85 | ADD_IR_PACK=Y | [link](../FMlogic/Request_OMX_SUBMIT_REMOVE_OFFER.html) |

---

## §5 — Coverage Gaps & Missing Rule Files

### Step 22 — OMX_OFFER_INCLUSION

Rule file `Request_OMX_OFFER_INCLUSION.rule` was not found. This step applies offer inclusion business rules ensuring required companion offers, bundles, or promotional packs are included with the primary offer.

> **Migration Impact:** Inclusion logic is undocumented. Must be sourced from business specifications or BRMS configuration rather than BE rule code.

### Step 34 — OMX_BIZ_VAL

Rule file `Request_OMX_BIZ_VAL.rule` was not found. Applies configurable business validation rules that may reject or modify the order based on subscriber eligibility criteria.

> **Migration Impact:** Custom business validation logic is unknown. Missing rules could lead to orders being accepted that should be rejected.

### Step 57 — UPDATE_NETWORK_STATUS

Rule file `Request_UPDATE_NETWORK_STATUS.rule` was not found. Expected to update network-level provisioning status after SBM data pack provisioning for ST=86/87.

> **Migration Impact:** Post-SBM network status update is undocumented. May be handled by SBM internally or by network middleware not present in this codebase.

### Step 77 — STATUS_UPDATE_CREATING_PROFILE

Rule file `Request_STATUS_UPDATE_CREATING_PROFILE.rule` was not found. Expected to update the OMX order status to "Creating Profile" state during provisioning.

> **Migration Impact:** Order status lifecycle is incomplete. The "Creating Profile" status transition is not captured, making order state tracking analysis partial.

---

## §6 — FM Documentation Index

| FM (ActivityID) | Used in Steps | System | Doc |
|-----------------|---------------|--------|-----|
| `IOM_CHECK_SEQUENCING` | 1 | OMX Internal | [link](../FMlogic/Request_IOM_CHECK_SEQUENCING.html) |
| `CCBS_GET_SUBSCRIBER_HEADER` | 2 | CCBS | [link](../FMlogic/Request_CCBS_GET_SUBSCRIBER_HEADER.html) |
| `CCBS_GET_CUST_ACC_SUB_ID` | 3 | CCBS | [link](../FMlogic/Request_CCBS_GET_CUST_ACC_SUB_ID.html) |
| `CCBS_GET_CUSTOMER_HEADER` | 4 | CCBS | [link](../FMlogic/Request_CCBS_GET_CUSTOMER_HEADER.html) |
| `BLACKLIST_CHECK_BLACKLIST` | 5 | Blacklist | [link](../FMlogic/Request_BLACKLIST_CHECK_BLACKLIST.html) |
| `BLACKLIST_CHECK_COLL_BY_ID_NUM` | 6 | Blacklist | [link](../FMlogic/Request_BLACKLIST_CHECK_COLL_BY_ID_NUM.html) |
| `BLACKLIST_CHECK_FRAUD` | 7 | Blacklist | [link](../FMlogic/Request_BLACKLIST_CHECK_FRAUD.html) |
| `CCBS_GET_ACCOUNT_HEADER` | 8 | CCBS | [link](../FMlogic/Request_CCBS_GET_ACCOUNT_HEADER.html) |
| `CCBS_GET_BA_HEADER` | 9 | CCBS | [link](../FMlogic/Request_CCBS_GET_BA_HEADER.html) |
| `CCBS_GET_AGREEMENT_HEADER` | 10 | CCBS | [link](../FMlogic/Request_CCBS_GET_AGREEMENT_HEADER.html) |
| `CCBS_GET_SUBS_INFO` | 11 | CCBS | [link](../FMlogic/Request_CCBS_GET_SUBS_INFO.html) |
| `INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST` | 12 | INTX | [link](../FMlogic/Request_INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST.html) |
| `CCBS_RESOLVE_SOC_CODE` | 13, 16, 54 | CCBS | [link](../FMlogic/Request_CCBS_RESOLVE_SOC_CODE.html) |
| `CCBS_GOD` | 14, 17 | CCBS | [link](../FMlogic/Request_CCBS_GOD.html) |
| `OMX_BRMS_DB` | 15 | OMX/BRMS | [link](../FMlogic/Request_OMX_BRMS_DB.html) |
| `OMX_RESOLVE_SOC_DATA` | 18 | OMX Internal | [link](../FMlogic/Request_OMX_RESOLVE_SOC_DATA.html) |
| `MCS_GET_CHARGE_INFO` | 19 | MCS | [link](../FMlogic/Request_MCS_GET_CHARGE_INFO.html) |
| `OMX_GET_FUT_INFO_BY_SUB` | 20 | OMX Internal | [link](../FMlogic/Request_OMX_GET_FUT_INFO_BY_SUB.html) |
| `OMX_CAL_OFFER_FUT_DATE` | 21 | OMX Internal | [link](../FMlogic/Request_OMX_CAL_OFFER_FUT_DATE.html) |
| `OMX_OFFER_INCLUSION` | 22 | OMX Internal | ⚠ Not Found |
| `CCBS_OFFER_EXCLUSION` | 23 | CCBS | [link](../FMlogic/Request_CCBS_OFFER_EXCLUSION.html) |
| `OMX_GET_OFFER_RATE` | 24 | OMX Internal | [link](../FMlogic/Request_OMX_GET_OFFER_RATE.html) |
| `BL_LIST_UNINVOICED_CHARGES` | 25 | BL Billing | [link](../FMlogic/Request_BL_LIST_UNINVOICED_CHARGES.html) |
| `MLDD_GET_SUB_DATA` | 26 | MLDD | [link](../FMlogic/Request_MLDD_GET_SUB_DATA.html) |
| `MCS_SUBSCRIPTION_MARKUSED` | 27 | MCS | [link](../FMlogic/Request_MCS_SUBSCRIPTION_MARKUSED.html) |
| `INTX_GET_TOTAL_OBLIGATION_INFO` | 28 | INTX | [link](../FMlogic/Request_INTX_GET_TOTAL_OBLIGATION_INFO.html) |
| `AA_GET_SWITCH_FEATURE_OFFER` | 29 | AA | [link](../FMlogic/Request_AA_GET_SWITCH_FEATURE_OFFER.html) |
| `GET_SPECIAL_OFFER_INDICATOR` | 30 | OMX Internal | [link](../FMlogic/Request_GET_SPECIAL_OFFER_INDICATOR.html) |
| `INTX_GET_SIM_INFO_BY_SIM` | 31 | INTX | [link](../FMlogic/Request_INTX_GET_SIM_INFO_BY_SIM.html) |
| `INTX_GET_MASTER_MINOR_SIM_INFO` | 32 | INTX | [link](../FMlogic/Request_INTX_GET_MASTER_MINOR_SIM_INFO.html) |
| `OMX_SEARCH_FUT` | 33 | OMX Internal | [link](../FMlogic/Request_OMX_SEARCH_FUT.html) |
| `OMX_BIZ_VAL` | 34 | OMX Internal | ⚠ Not Found |
| `OMX_ADD_FUT_OFFER` | 35, 53, 56 | OMX Internal | [link](../FMlogic/Request_OMX_ADD_FUT_OFFER.html) |
| `OMX_CAL_DISCOUNT_FULL_BILL` | 36 | OMX Internal | [link](../FMlogic/Request_OMX_CAL_DISCOUNT_FULL_BILL.html) |
| `CVSS_UPDATE_SUBSCRIBER_COUNT` | 37 | CVSS | [link](../FMlogic/Request_CVSS_UPDATE_SUBSCRIBER_COUNT.html) |
| `ASRM_INVOKE_MINOR_SIM` | 38, 46 | ASRM | [link](../FMlogic/Request_ASRM_INVOKE_MINOR_SIM.html) |
| `OMX_POPULATE_MSIM_INFO` | 39 | OMX Internal | [link](../FMlogic/Request_OMX_POPULATE_MSIM_INFO.html) |
| `OMX_GET_SRV_TRX_NO_MSIM` | 40, 42 | OMX Internal | [link](../FMlogic/Request_OMX_GET_SRV_TRX_NO_MSIM.html) |
| `AA_ACTIVATE_SUBS_MSIM` | 41, 43 | AA | [link](../FMlogic/Request_AA_ACTIVATE_SUBS_MSIM.html) |
| `OMX_GET_SRV_TRX_NO` | 44 | OMX Internal | [link](../FMlogic/Request_OMX_GET_SRV_TRX_NO.html) |
| `AA_ACTIVATE_SUBS` | 45 | AA | [link](../FMlogic/Request_AA_ACTIVATE_SUBS.html) |
| `OMX_CAL_CREDIT_LIMIT_FOR_IR` | 47 | OMX Internal | [link](../FMlogic/Request_OMX_CAL_CREDIT_LIMIT_FOR_IR.html) |
| `CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO` | 48, 49 | CCBS | [link](../FMlogic/Request_CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO.html) |
| `SBM_FUP_CHANGE_CAP_MAX` | 50 | SBM | [link](../FMlogic/Request_SBM_FUP_CHANGE_CAP_MAX.html) |
| `SBM_BUY_DATA_PACK` | 51 | SBM | [link](../FMlogic/Request_SBM_BUY_DATA_PACK.html) |
| `SBM_ADD_3GPREPAID` | 52 | SBM | [link](../FMlogic/Request_SBM_ADD_3GPREPAID.html) |
| `BL_CREATE_CHARGE` | 58 | BL Billing | [link](../FMlogic/Request_BL_CREATE_CHARGE.html) |
| `CCBS_CHANGE_PACKAGE_SUBSCRIBER` | 55, 59, 60, 61 | CCBS | [link](../FMlogic/Request_CCBS_CHANGE_PACKAGE_SUBSCRIBER.html) |
| `MCS_REGISTER_SUBSCRIPTION` | 62 | MCS | [link](../FMlogic/Request_MCS_REGISTER_SUBSCRIPTION.html) |
| `MCS_REGISTER` | 63 | MCS | [link](../FMlogic/Request_MCS_REGISTER.html) |
| `PSA_GET_DEVICE_INFO` | 64 | PSA | [link](../FMlogic/Request_PSA_GET_DEVICE_INFO.html) |
| `KNOX_SAVE_DEVICE` | 65 | Knox MDM | [link](../FMlogic/Request_KNOX_SAVE_DEVICE.html) |
| `OMX_NOTI_TO_KAFKA` | 66, 69 | Kafka | [link](../FMlogic/Request_OMX_NOTI_TO_KAFKA.html) |
| `PSA_UPDATE_KNOX_STATUS` | 67 | PSA | [link](../FMlogic/Request_PSA_UPDATE_KNOX_STATUS.html) |
| `KNOX_NOTIFICATION_DEVICE` | 68 | Knox/BSNS | [link](../FMlogic/Request_KNOX_NOTIFICATION_DEVICE.html) |
| `PSA_UPDATE_DEVICE` | 70 | PSA | [link](../FMlogic/Request_PSA_UPDATE_DEVICE.html) |
| `TDG_CREATE_SUBSCRIBER` | 71 | TDG | [link](../FMlogic/Request_TDG_CREATE_SUBSCRIBER.html) |
| `BDH_INSTALLMENT_SALE` | 73 | BDH | [link](../FMlogic/Request_BDH_INSTALLMENT_SALE.html) |
| `CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO` | 74 | CCBS | [link](../FMlogic/Request_CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO.html) |
| `CCBS_UPDATE_ACCOUNT_NAME_ADDRESS` | 75 | CCBS | [link](../FMlogic/Request_CCBS_UPDATE_ACCOUNT_NAME_ADDRESS.html) |
| `CCBS_CREATE_MEMO_FOR_SBM` | 76 | CCBS | [link](../FMlogic/Request_CCBS_CREATE_MEMO_FOR_SBM.html) |
| `OMX_EXP_FUT_RELATED_OFFER` | 79 | OMX Internal | [link](../FMlogic/Request_OMX_EXP_FUT_RELATED_OFFER.html) |
| `SMSGATEWAY_SEND_SMS` | 81 | SMS Gateway | [link](../FMlogic/Request_SMSGATEWAY_SEND_SMS.html) |
| `APIGW_OPT_IN_OUT` | 82 | APIGW/CBSC | [link](../FMlogic/Request_APIGW_OPT_IN_OUT.html) |
| `OMX_SUBMIT_POSTPAID_ADD_BENEFIT` | 83 | OMX Child Order | [link](../FMlogic/Request_OMX_SUBMIT_POSTPAID_ADD_BENEFIT.html) |
| `OMX_SUBMIT_REMOVE_OFFER` | 84 | OMX Child Order | [link](../FMlogic/Request_OMX_SUBMIT_REMOVE_OFFER.html) |

---

*TRUE Corporation OMX · Order Journey Documentation · POSTPAID_ADD_OFFER_SUB · 2026-08-11*
