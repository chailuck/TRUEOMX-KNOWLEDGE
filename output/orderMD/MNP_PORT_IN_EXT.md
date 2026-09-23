# MNP_PORT_IN_EXT

> Process Configuration for MNP_PORT_IN_EXT.

**Total steps:** 78 | **Unique FMs:** 68 | **Entry point:** CVSS_GET_VALIDATE_APPROVE_CODE | **Generated:** 2026-09-23

> ⚠ Sequence and flow diagrams omitted — 78 activities exceeds the 60-step rendering threshold.

---

## §1 — Process Overview

| Phase | Steps | Description | Key Systems |
|-------|-------|-------------|-------------|
| 1. Approve Code Validation | 1–2 | Validate MNP approve code; retrieve current SIM by MSISDN | CVSS, INTX |
| 2. eSIM & SIM Discovery | 3–8 | Inject eSIM offer, populate promo offer, reserve MSISDN/SIM, get SIM by SIM/ICCID, compute eSIM checksum | OMX, ASRM, INTX |
| 3. Business Validation & Offer Resolution | 9–16 | Business validation, MNP auto shareplan, initial SOC/offer resolution | OMX, TCC, CCBS |
| 4. MSISDN & SIM Lifecycle | 17–24 | MNP port out → port in; SIM reserve; eSIM download (SMDP+); MSISDN/SIM activate; SIM attribute update | ASRM, SMDP |
| 5. Customer Account & OU Creation | 25–41 | Create customer with billing cycle, BRMS offer resolution (2 rounds), create OU/agreement/account, FUP groups | CCBS, OMX, SBM |
| 6. Subscriber Creation & AA Provisioning | 42–51 | Calculate activity reason, create subscriber, CJ verification, add future offers, get UR details, AA activation | CCBS, CJ, AA, OMX, ASRM |
| 7. Credit Assessment | 52–64 | New-account and existing-account credit check, credit class update, MNP credit limit calculation | CVSS, ODS, CCBS, OMX |
| 8. Network & Subscription Provisioning | 65–74 | AA confirmation + network status, data pack, billing charge, package change, MCS registration, FUP member, itemize, SMS | AA, SBM, BL, MCS, INTX, SMS |
| 9. Finalization | 75–78 | Inject itemize0 offer, update agreement on OU, NAS blacklist check, TMN wallet profile creation | OMX, CCBS, NAS, TMN |

---

## §2 — Order Flow

| Step | Step ID | FM (ActivityID) | Parameter(s) | PreExecCheck | Previous | Next |
|------|---------|-----------------|--------------|--------------|----------|------|
| 1 | CVSS_GET_VALIDATE_APPROVE_CODE | CVSS_GET_VALIDATE_APPROVE_CODE | — | `string-length(//maxAllowApproveCode)>0 or string-length(//irApproveCode)>0` | START | INTX_GET_SIM_INFO_BY_MSISDN |
| 2 | INTX_GET_SIM_INFO_BY_MSISDN | INTX_GET_SIM_INFO_BY_MSISDN | — | — | CVSS_GET_VALIDATE_APPROVE_CODE | OMX_INJECT_OFFER_ADD_ESIM |
| 3 | OMX_INJECT_OFFER_ADD_ESIM | OMX_INJECT_OFFER ★ | soc=13513126,serviceType=85,action=ADD,offerName=RSESIM01,level=SUB,checkDup=1,source=FE | PEID and PMATCHID present | INTX_GET_SIM_INFO_BY_MSISDN | OMX_POPULATE_OFFER_PROMOEND |
| 4 | OMX_POPULATE_OFFER_PROMOEND | OMX_POPULATE_OFFER | OFFER=soc=25427629,serviceType=85,action=ADD,offerName=RMVX00000000001,level=SUB,checkDup=1,source=FE | CustomerTypeInfo/Type=73 | OMX_INJECT_OFFER_ADD_ESIM | ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST |
| 5 | ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST | ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST | DEALERCODE=70000776 | PEID and PMATCHID present | OMX_POPULATE_OFFER_PROMOEND | INTX_GET_SIM_INFO_BY_SIM |
| 6 | INTX_GET_SIM_INFO_BY_SIM | INTX_GET_SIM_INFO_BY_SIM | — | PEID=0 AND PMATCHID=0 | ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST | INTX_GET_SIM_INFO_BY_ICCID |
| 7 | INTX_GET_SIM_INFO_BY_ICCID | INTX_GET_SIM_INFO_BY_ICCID | PROJ=ESIM | PEID and PMATCHID present | INTX_GET_SIM_INFO_BY_SIM | OMX_CAL_CHK_SUM_SUB_LEVEL |
| 8 | OMX_CAL_CHK_SUM_SUB_LEVEL | OMX_CAL_CHK_SUM_SUB_LEVEL | — | PEID>0 and PMATCHID>0 | INTX_GET_SIM_INFO_BY_ICCID | OMX_BIZ_VAL |
| 9 | OMX_BIZ_VAL | OMX_BIZ_VAL | — | — | OMX_CAL_CHK_SUM_SUB_LEVEL | TCC_GET_MNP_AUTO_SHAREPLAN |
| 10 | TCC_GET_MNP_AUTO_SHAREPLAN | TCC_GET_MNP_AUTO_SHAREPLAN ★ NEW | — | — | OMX_BIZ_VAL | CCBS_RESOLVE_SOC_CODE_PROP |
| 11 | CCBS_RESOLVE_SOC_CODE_PROP | CCBS_RESOLVE_SOC_CODE | — | `not(exists(//Soc)) or Soc empty` | TCC_GET_MNP_AUTO_SHAREPLAN | CCBS_GOD |
| 12 | CCBS_GOD | CCBS_GOD | — | `count(Offers)>0 or count(SubscriberOffers)>0` | CCBS_RESOLVE_SOC_CODE_PROP | OMX_OFFER_INCLUSION |
| 13 | OMX_OFFER_INCLUSION | OMX_OFFER_INCLUSION | — | `Channel!="EOC"` | CCBS_GOD | CCBS_GET_ACCOUNT_HEADER |
| 14 | CCBS_GET_ACCOUNT_HEADER | CCBS_GET_ACCOUNT_HEADER | — | `string-length(//RawAccountID)>0` | OMX_OFFER_INCLUSION | CCBS_GET_AGREEMENT_INFO |
| 15 | CCBS_GET_AGREEMENT_INFO | CCBS_GET_AGREEMENT_INFO | — | `string-length(//OUId)>0` | CCBS_GET_ACCOUNT_HEADER | GET_SPECIAL_OFFER_INDICATOR |
| 16 | GET_SPECIAL_OFFER_INDICATOR | GET_SPECIAL_OFFER_INDICATOR | — | — | CCBS_GET_AGREEMENT_INFO | ASRM_INVOKE_MSISDN_PORT_OUT |
| 17 | ASRM_INVOKE_MSISDN_PORT_OUT | ASRM_INVOKE_MSISDN | ACTIVITY=PORT OUT | `MSISDN_STATUS='PORT OUT AG'` | GET_SPECIAL_OFFER_INDICATOR | ASRM_INVOKE_MSISDN_PORT_IN |
| 18 | ASRM_INVOKE_MSISDN_PORT_IN | ASRM_INVOKE_MSISDN | ACTIVITY=PORT IN | — | ASRM_INVOKE_MSISDN_PORT_OUT | ASRM_INVOKE_SIM_RESERVE |
| 19 | ASRM_INVOKE_SIM_RESERVE | ASRM_INVOKE_SIM | ACTIVITY=RESERVE | `SIM_PAIR_MSISDN empty AND PEID=0 AND PMATCHID=0` | ASRM_INVOKE_MSISDN_PORT_IN | SMDP_PLUS |
| 20 | SMDP_PLUS | SMDP_PLUS | PROJ=ESIM | `count(Subscriber[ExtendedInfo[ICC_ID_CHG_SUM]])>0` | ASRM_INVOKE_SIM_RESERVE | SMDP_PLUS_CONFIRM |
| 21 | SMDP_PLUS_CONFIRM | SMDP_PLUS_CONFIRM | PROJ=ESIM | `count(Subscriber[ExtendedInfo[ICC_ID_CHG_SUM]])>0` | SMDP_PLUS | ASRM_INVOKE_MSISDN_ACTIVATE |
| 22 | ASRM_INVOKE_MSISDN_ACTIVATE | ASRM_INVOKE_MSISDN | ACTIVITY=ACTIVATE | — | SMDP_PLUS_CONFIRM | ASRM_INVOKE_SIM_ACTIVATE |
| 23 | ASRM_INVOKE_SIM_ACTIVATE | ASRM_INVOKE_SIM | ACTIVITY=ACTIVATE | — | ASRM_INVOKE_MSISDN_ACTIVATE | ASRM_UPDATE_ATTRIBUTE_SIM |
| 24 | ASRM_UPDATE_ATTRIBUTE_SIM | ASRM_UPDATE_ATTRIBUTE_SIM | EXPIRE_SELF=-1 | — | ASRM_INVOKE_SIM_ACTIVATE | CCBS_CREATE_CUST_WITH_CYCLE |
| 25 | CCBS_CREATE_CUST_WITH_CYCLE | CCBS_CREATE_CUST_WITH_CYCLE | — | `not(exists(//RawCustomerId))` | ASRM_UPDATE_ATTRIBUTE_SIM | CCBS_GET_CUSTOMER_HEADER |
| 26 | CCBS_GET_CUSTOMER_HEADER | CCBS_GET_CUSTOMER_HEADER | — | `boolean(//Customer[not(BillCycleNo[./text()])])` | CCBS_CREATE_CUST_WITH_CYCLE | OMX_BRMS_DB |
| 27 | OMX_BRMS_DB | OMX_BRMS_DB | — | — | CCBS_GET_CUSTOMER_HEADER | OMX_RESOLVE_SOC_DATA |
| 28 | OMX_RESOLVE_SOC_DATA | OMX_RESOLVE_SOC_DATA | — | — | OMX_BRMS_DB | CCBS_RESOLVE_SOC_CODE_BRMS |
| 29 | CCBS_RESOLVE_SOC_CODE_BRMS | CCBS_RESOLVE_SOC_CODE | — | `not(exists(//Soc)) or Soc empty` | OMX_RESOLVE_SOC_DATA | CCBS_GOD_BRMS |
| 30 | CCBS_GOD_BRMS | CCBS_GOD | — | `boolean(//SubscriberOffers[ExtendedInfo[BRMS] and ServiceType!=69])` | CCBS_RESOLVE_SOC_CODE_BRMS | CCBS_RESOLVE_SOC_CODE_BRMS_FOR_NEXT_OFFER |
| 31 | CCBS_RESOLVE_SOC_CODE_BRMS_FOR_NEXT_OFFER | CCBS_RESOLVE_SOC_CODE | — | `not(exists(//Soc)) or Soc empty` | CCBS_GOD_BRMS | OMX_CAL_OFFER_FUT_DATE_BRMS |
| 32 | OMX_CAL_OFFER_FUT_DATE_BRMS | OMX_CAL_OFFER_FUT_DATE | `CAL_PARAM_EXP=Y \| EXCLUDE_OFFER=RMVX00000000001` | BRMS offers on subscriber or agreement | CCBS_RESOLVE_SOC_CODE_BRMS_FOR_NEXT_OFFER | OMX_CAL_PP_EXPIRE_DATE |
| 33 | OMX_CAL_PP_EXPIRE_DATE | OMX_CAL_PP_EXPIRE_DATE | — | `SubscriberOffers[OfferName=RMVX00000000001 and FE]` | OMX_CAL_OFFER_FUT_DATE_BRMS | CCBS_CREATE_PARENT_OU |
| 34 | CCBS_CREATE_PARENT_OU | CCBS_CREATE_PARENT_OU | — | `not(exists(//OUId)) or OUId empty` | OMX_CAL_PP_EXPIRE_DATE | CCBS_CREATE_CHILD_OU |
| 35 | CCBS_CREATE_CHILD_OU | CCBS_CREATE_CHILD_OU | — | ParentOU or ChildOU RawOUId missing | CCBS_CREATE_PARENT_OU | CCBS_CREATE_AGREE |
| 36 | CCBS_CREATE_AGREE | CCBS_CREATE_AGREE | — | `not(exists(//RawOUId))` | CCBS_CREATE_CHILD_OU | CCBS_CREATE_ACCT |
| 37 | CCBS_CREATE_ACCT | CCBS_CREATE_ACCT | — | `not(exists(//RawAccountID)) or empty` | CCBS_CREATE_AGREE | CCBS_ADD_AGREEOFFER |
| 38 | CCBS_ADD_AGREEOFFER | CCBS_ADD_AGREEOFFER | — | `count(Offers)>0 and Agreement/Offers[FE_OR_CCBS!='CCBS']` | CCBS_CREATE_ACCT | SBM_FUP_CREATE_GROUP |
| 39 | SBM_FUP_CREATE_GROUP | SBM_FUP_CREATE_GROUP | — | `FSH/FPL non-CCBS>0 AND CCBS=0` | CCBS_ADD_AGREEOFFER | SBM_FUP_CHANGE_TOPPING |
| 40 | SBM_FUP_CHANGE_TOPPING | SBM_FUP_CHANGE_TOPPING | ADD | `FSH FE non-FUT exists AND CCBS FSH/FPL>0` | SBM_FUP_CREATE_GROUP | SBM_FUP_CHANGE_VARIABLE |
| 41 | SBM_FUP_CHANGE_VARIABLE | SBM_FUP_CHANGE_VARIABLE | ADD | `FPL FE non-FUT exists AND CCBS FSH/FPL>0` | SBM_FUP_CHANGE_TOPPING | OMX_CALC_ACTIVITY_REASON |
| 42 | OMX_CALC_ACTIVITY_REASON | OMX_CALC_ACTIVITY_REASON | ACTIVATION | — | SBM_FUP_CHANGE_VARIABLE | CCBS_CREATE_SUBS |
| 43 | CCBS_CREATE_SUBS | CCBS_CREATE_SUBS | — | `not(exists(//Subscriber/SubscriberId))` | OMX_CALC_ACTIVITY_REASON | CJ_CREATE_SUB_CALL_VERIFICATION |
| 44 | CJ_CREATE_SUB_CALL_VERIFICATION | CJ_CREATE_SUB_CALL_VERIFICATION | — | — | CCBS_CREATE_SUBS | OMX_ADD_FUT_OFFER_BRMS |
| 45 | OMX_ADD_FUT_OFFER_BRMS | OMX_ADD_FUT_OFFER | — | FE/BRMS FUT offers on subscriber | CCBS_CREATE_SUBS | ASRM_GET_UR_DETAILS_MSISDN |
| 46 | ASRM_GET_UR_DETAILS_MSISDN | ASRM_GET_UR_DETAILS_MSISDN | — | — | OMX_ADD_FUT_OFFER_BRMS | AA_GET_SWITCH_FEATURE_OFFER |
| 47 | AA_GET_SWITCH_FEATURE_OFFER | AA_GET_SWITCH_FEATURE_OFFER | NAC | `AA=AA` | ASRM_GET_UR_DETAILS_MSISDN | OMX_GET_SRV_TRX_NO |
| 48 | OMX_GET_SRV_TRX_NO | OMX_GET_SRV_TRX_NO | NAC | `AA=AA` | AA_GET_SWITCH_FEATURE_OFFER | AA_ACTIVATE_SUBS |
| 49 | AA_ACTIVATE_SUBS | AA_ACTIVATE_SUBS | NAC | `SubscriberId exists and AA=AA` | OMX_GET_SRV_TRX_NO | OMX_ADD_NXT_PP |
| 50 | OMX_ADD_NXT_PP | OMX_ADD_NXT_PP | — | `ServiceType=80 FE or Agreement Offers` | AA_ACTIVATE_SUBS | OMX_ADD_NEXT_OFFER |
| 51 | OMX_ADD_NEXT_OFFER | OMX_ADD_NEXT_OFFER | — | complex FE/BRMS non-80/69 non-FUT | OMX_ADD_NXT_PP | STATUS_UPDATE_CREATING_PROFILE |
| 52 | STATUS_UPDATE_CREATING_PROFILE | STATUS_UPDATE_CREATING_PROFILE | — | — | OMX_ADD_NEXT_OFFER | CVSS_CREDIT_CHECK_NEW_ACCNT |
| 53 | CVSS_CREDIT_CHECK_NEW_ACCNT | CVSS_CREDIT_CHECK | — | `not(exists(//RawAccountID))` | STATUS_UPDATE_CREATING_PROFILE | ODS_GET_CREDIT_CLASS_CREDIT_LIMIT |
| 54 | ODS_GET_CREDIT_CLASS_CREDIT_LIMIT | ODS_GET_CREDIT_CLASS_CREDIT_LIMIT | — | `Type=73 and CreditClass not F/V0/V1/V3 and SubType not RVI/RVB/...` | CVSS_CREDIT_CHECK_NEW_ACCNT | CCBS_UPD_CREDIT_CLASS_NEW_ACCNT |
| 55 | CCBS_UPD_CREDIT_CLASS_NEW_ACCNT | CCBS_UPD_CREDIT_CLASS | — | `not(exists(//RawAccountID))` | ODS_GET_CREDIT_CLASS_CREDIT_LIMIT | CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT_FOR_ODS |
| 56 | CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT_FOR_ODS | CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT | — | same Type=73 CreditClass check | CCBS_UPD_CREDIT_CLASS_NEW_ACCNT | CALCULATE_MNP_CREDIT_LIMIT |
| 57 | CALCULATE_MNP_CREDIT_LIMIT | CALCULATE_MNP_CREDIT_LIMIT ★ NEW | — | `Type!=73 and OrderType=7` | CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT_FOR_ODS | CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT |
| 58 | CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT | CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT | — | `Type!=73 and not(exists(RawAccountID))` | CALCULATE_MNP_CREDIT_LIMIT | CCBS_UPD_CREDIT_LIMIT |
| 59 | CCBS_UPD_CREDIT_LIMIT | CCBS_UPD_CREDIT_LIMIT | — | `Type!=73 and RawAccountID>0` | CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT | CVSS_GET_EXISTING_PRODUCT |
| 60 | CVSS_GET_EXISTING_PRODUCT | CVSS_GET_EXISTING_PRODUCT | — | `RawCustomerId>0 and RawAccountID>0 and count(Subscriber)>0` | CCBS_UPD_CREDIT_LIMIT | CVSS_GET_AUTO_APPROVE_CODE |
| 61 | CVSS_GET_AUTO_APPROVE_CODE | CVSS_GET_AUTO_APPROVE_CODE | requestType=CV | `Channel ends with '-MF'` | CVSS_GET_EXISTING_PRODUCT | CVSS_CREDIT_CHECK |
| 62 | CVSS_CREDIT_CHECK | CVSS_CREDIT_CHECK | — | `ProductCount=0` | CVSS_GET_AUTO_APPROVE_CODE | CCBS_UPD_CREDIT_CLASS |
| 63 | CCBS_UPD_CREDIT_CLASS | CCBS_UPD_CREDIT_CLASS | — | `ProductCount=0` | CVSS_CREDIT_CHECK | CVSS_UPDATE_SUBSCRIBER_COUNT |
| 64 | CVSS_UPDATE_SUBSCRIBER_COUNT | CVSS_UPDATE_SUBSCRIBER_COUNT | — | `ProductCount>0` | CCBS_UPD_CREDIT_CLASS | AA_CHECK_CONFIRMATION |
| 65 | AA_CHECK_CONFIRMATION | AA_CHECK_CONFIRMATION | `NAC \| UPDATE_NETWORK_STATUS` | `AA=AA` | CVSS_UPDATE_SUBSCRIBER_COUNT | SBM_BUY_DATA_PACK |
| 66 | SBM_BUY_DATA_PACK | SBM_BUY_DATA_PACK | — | `SBM_PROVISIONING!=N and ServiceType=86 FE/BRMS non-FUT` | AA_CHECK_CONFIRMATION | BL_CREATE_CHARGE |
| 67 | BL_CREATE_CHARGE | BL_CREATE_CHARGE | — | `ServiceType=79 FE/BRMS` | SBM_BUY_DATA_PACK | CCBS_CHANGE_PACKAGE_SUBSCRIBER |
| 68 | CCBS_CHANGE_PACKAGE_SUBSCRIBER | CCBS_CHANGE_PACKAGE_SUBSCRIBER | ADD | `FE/BRMS ServiceType 85/86/68 non-contract non-FUT` | BL_CREATE_CHARGE | MCS_REGISTER_SUBSCRIPTION |
| 69 | MCS_REGISTER_SUBSCRIPTION | MCS_REGISTER_SUBSCRIPTION | USE_FE_RECURRING=Y | `ServiceType=69 BRMS/FE` | CCBS_CHANGE_PACKAGE_SUBSCRIBER | OMX_EXP_FUT_OFFER_BRMS |
| 70 | OMX_EXP_FUT_OFFER_BRMS | OMX_EXP_FUT_OFFER | — | `FE/BRMS EXP_TYPE=FUT and EFF_TYPE!=FUT` | MCS_REGISTER_SUBSCRIPTION | CCBS_CREATE_MEMO_FOR_SBM |
| 71 | CCBS_CREATE_MEMO_FOR_SBM | CCBS_CREATE_MEMO_FOR_SBM | `ENTITY_TYPE_ID=6 \| MEMO_TEXT_CONCAT=... \| MEMO_TYPE_ID=90051 \| MEMO_SYSTEM_TEXT=082` | `ServiceType=86 FE/BRMS` | OMX_EXP_FUT_OFFER_BRMS | SBM_FUP_CHANGE_MEMBER |
| 72 | SBM_FUP_CHANGE_MEMBER | SBM_FUP_CHANGE_MEMBER | ADD | `Offers with FSH/FPL > 0` | CCBS_CREATE_MEMO_FOR_SBM | INTX_GET_OFFER_DETAIL |
| 73 | INTX_GET_OFFER_DETAIL | INTX_GET_OFFER_DETAIL | ADD | `ServiceType=80 FE subscriber or agreement` | SBM_FUP_CHANGE_MEMBER | SMSGATEWAY_SEND_SMS |
| 74 | SMSGATEWAY_SEND_SMS | SMSGATEWAY_SEND_SMS | — | — | INTX_GET_OFFER_DETAIL | OMX_INJECT_OFFER_ADD_ITEMIZE0 |
| 75 | OMX_INJECT_OFFER_ADD_ITEMIZE0 | OMX_INJECT_OFFER | soc=13102425,serviceType=85,action=ADD,offerName=ITMBLS02,level=OU,checkDup=1 | `BillFormat=E or S AND SHOW_USAGE_DETAIL=Y` | SMSGATEWAY_SEND_SMS | CCBS_UPDATE_AGREEMENT_ON_UNIT |
| 76 | CCBS_UPDATE_AGREEMENT_ON_UNIT | CCBS_UPDATE_AGREEMENT_ON_UNIT | — | `ParentOU/Agreement exists and non-80 INJECT_OFFER` | OMX_INJECT_OFFER_ADD_ITEMIZE0 | NAS_CHECK_COLLECTION_BLACKLIST |
| 77 | NAS_CHECK_COLLECTION_BLACKLIST | NAS_CHECK_COLLECTION_BLACKLIST | — | — | CCBS_UPDATE_AGREEMENT_ON_UNIT | TMN_CREATE_WALLET_MINIMAL_PROFILE |
| 78 | TMN_CREATE_WALLET_MINIMAL_PROFILE | TMN_CREATE_WALLET_MINIMAL_PROFILE | — | `CustomerTypeInfo/Type=73` | NAS_CHECK_COLLECTION_BLACKLIST | END |

> ★ NEW = newly generated FM doc this session

---

## §3 — PreExecCheck Details

### Step 1 — CVSS_GET_VALIDATE_APPROVE_CODE
**FM:** `CVSS_GET_VALIDATE_APPROVE_CODE`
```xpath
string-length(//maxAllowApproveCode)>0 or string-length(//irApproveCode)>0
```
Runs only when an approve code (standard or IR) is present in the order context.

### Step 3 — OMX_INJECT_OFFER_ADD_ESIM
**FM:** `OMX_INJECT_OFFER`
```xpath
PEID and PMATCHID present (eSIM profile exists)
```
Inject eSIM offer only when eSIM profile ID (PEID) and match ID (PMATCHID) are populated.

### Step 4 — OMX_POPULATE_OFFER_PROMOEND
**FM:** `OMX_POPULATE_OFFER`
```xpath
CustomerTypeInfo/Type=73
```
Populate promotional end date offer only for corporate (Type=73) customers.

### Step 5 — ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST
**FM:** `ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST`
```xpath
PEID and PMATCHID present
```
Reserve eSIM profile resource only when eSIM PEID/PMATCHID are set.

### Step 6 — INTX_GET_SIM_INFO_BY_SIM
**FM:** `INTX_GET_SIM_INFO_BY_SIM`
```xpath
PEID=0 AND PMATCHID=0
```
Physical SIM lookup — only when eSIM identifiers are absent.

### Step 7 — INTX_GET_SIM_INFO_BY_ICCID
**FM:** `INTX_GET_SIM_INFO_BY_ICCID` | **Parameter:** PROJ=ESIM
```xpath
PEID and PMATCHID present
```
eSIM-specific ICCID lookup when eSIM PEID/PMATCHID present.

### Step 8 — OMX_CAL_CHK_SUM_SUB_LEVEL
**FM:** `OMX_CAL_CHK_SUM_SUB_LEVEL`
```xpath
PEID>0 and PMATCHID>0
```
Compute subscriber-level ICC_ID Luhn checksum for eSIM download gate.

### Step 11 — CCBS_RESOLVE_SOC_CODE_PROP
**FM:** `CCBS_RESOLVE_SOC_CODE`
```xpath
not(exists(//Soc)) or Soc empty
```
Resolve SOC codes from CCBS only when SOC data is not already present.

### Step 12 — CCBS_GOD
**FM:** `CCBS_GOD`
```xpath
count(Offers)>0 or count(SubscriberOffers)>0
```
Get offer details only when offers exist in the order.

### Step 13 — OMX_OFFER_INCLUSION
**FM:** `OMX_OFFER_INCLUSION`
```xpath
Channel!="EOC"
```
Offer inclusion check skipped for EOC (end-of-contract) channel orders.

### Step 14 — CCBS_GET_ACCOUNT_HEADER
**FM:** `CCBS_GET_ACCOUNT_HEADER`
```xpath
string-length(//RawAccountID)>0
```
Get account header only for existing accounts (RawAccountID populated).

### Step 15 — CCBS_GET_AGREEMENT_INFO
**FM:** `CCBS_GET_AGREEMENT_INFO`
```xpath
string-length(//OUId)>0
```
Get agreement info only for existing OUs (OUId populated).

### Step 17 — ASRM_INVOKE_MSISDN_PORT_OUT
**FM:** `ASRM_INVOKE_MSISDN` | **Parameter:** ACTIVITY=PORT OUT
```xpath
MSISDN_STATUS='PORT OUT AG'
```
Port Out only when MSISDN status is already in 'PORT OUT AG' (agreed to port out).

### Step 19 — ASRM_INVOKE_SIM_RESERVE
**FM:** `ASRM_INVOKE_SIM` | **Parameter:** ACTIVITY=RESERVE
```xpath
SIM_PAIR_MSISDN empty AND PEID=0 AND PMATCHID=0
```
Reserve physical SIM only when no paired MSISDN and no eSIM profile.

### Step 20 — SMDP_PLUS
**FM:** `SMDP_PLUS` | **Parameter:** PROJ=ESIM
```xpath
count(Subscriber[ExtendedInfo[ICC_ID_CHG_SUM]])>0
```
eSIM download only when ICC_ID checksum (ICC_ID_CHG_SUM) has been computed.

### Step 21 — SMDP_PLUS_CONFIRM
**FM:** `SMDP_PLUS_CONFIRM` | **Parameter:** PROJ=ESIM
```xpath
count(Subscriber[ExtendedInfo[ICC_ID_CHG_SUM]])>0
```
eSIM download confirmation — same gate as SMDP_PLUS step.

### Step 25 — CCBS_CREATE_CUST_WITH_CYCLE
**FM:** `CCBS_CREATE_CUST_WITH_CYCLE`
```xpath
not(exists(//RawCustomerId))
```
Create new customer in CCBS only when no existing RawCustomerId.

### Step 26 — CCBS_GET_CUSTOMER_HEADER
**FM:** `CCBS_GET_CUSTOMER_HEADER`
```xpath
boolean(//Customer[not(BillCycleNo[./text()])])
```
Get customer header only when BillCycleNo is absent (new account needs billing cycle resolved).

### Step 29 — CCBS_RESOLVE_SOC_CODE_BRMS
**FM:** `CCBS_RESOLVE_SOC_CODE`
```xpath
not(exists(//Soc)) or Soc empty
```
BRMS round 1 SOC resolution — only when SOC not yet populated.

### Step 30 — CCBS_GOD_BRMS
**FM:** `CCBS_GOD`
```xpath
boolean(//SubscriberOffers[ExtendedInfo[BRMS] and ServiceType!=69])
```
Get BRMS offer details for non-MCS (ServiceType≠69) subscriber offers marked as BRMS.

### Step 31 — CCBS_RESOLVE_SOC_CODE_BRMS_FOR_NEXT_OFFER
**FM:** `CCBS_RESOLVE_SOC_CODE`
```xpath
not(exists(//Soc)) or Soc empty
```
BRMS round 2 — resolve SOC for next-cycle offers.

### Step 32 — OMX_CAL_OFFER_FUT_DATE_BRMS
**FM:** `OMX_CAL_OFFER_FUT_DATE` | **Parameter:** CAL_PARAM_EXP=Y | EXCLUDE_OFFER=RMVX00000000001
```xpath
BRMS offers on subscriber or agreement
```
Calculate future effective date for BRMS offers, excluding promo-end offer.

### Step 33 — OMX_CAL_PP_EXPIRE_DATE
**FM:** `OMX_CAL_PP_EXPIRE_DATE`
```xpath
SubscriberOffers[OfferName=RMVX00000000001 and FE]
```
Calculate PP expiry date only when promo-end offer (RMVX00000000001) is present as FE offer.

### Step 34 — CCBS_CREATE_PARENT_OU
**FM:** `CCBS_CREATE_PARENT_OU`
```xpath
not(exists(//OUId)) or OUId empty
```
Create parent OU only when OUId not yet assigned.

### Step 35 — CCBS_CREATE_CHILD_OU
**FM:** `CCBS_CREATE_CHILD_OU`
```xpath
ParentOU or ChildOU RawOUId missing
```
Create child OU when required OU structure is incomplete.

### Step 36 — CCBS_CREATE_AGREE
**FM:** `CCBS_CREATE_AGREE`
```xpath
not(exists(//RawOUId))
```
Create agreement only when OU ID (RawOUId) not yet assigned.

### Step 37 — CCBS_CREATE_ACCT
**FM:** `CCBS_CREATE_ACCT`
```xpath
not(exists(//RawAccountID)) or empty
```
Create account only when RawAccountID is absent.

### Step 38 — CCBS_ADD_AGREEOFFER
**FM:** `CCBS_ADD_AGREEOFFER`
```xpath
count(Offers)>0 and Agreement/Offers[FE_OR_CCBS!='CCBS']
```
Add agreement-level offers (from FE, not purely CCBS-driven).

### Step 39 — SBM_FUP_CREATE_GROUP
**FM:** `SBM_FUP_CREATE_GROUP`
```xpath
FSH/FPL non-CCBS>0 AND CCBS=0
```
Create FUP group only when there are non-CCBS FSH/FPL offers and no CCBS FSH/FPL group exists.

### Step 40 — SBM_FUP_CHANGE_TOPPING
**FM:** `SBM_FUP_CHANGE_TOPPING` | **Parameter:** ADD
```xpath
FSH FE non-FUT exists AND CCBS FSH/FPL>0
```
Add topping to existing CCBS FUP group when FSH offers are present.

### Step 41 — SBM_FUP_CHANGE_VARIABLE
**FM:** `SBM_FUP_CHANGE_VARIABLE` | **Parameter:** ADD
```xpath
FPL FE non-FUT exists AND CCBS FSH/FPL>0
```
Add variable data to existing CCBS FUP group when FPL offers are present.

### Step 43 — CCBS_CREATE_SUBS
**FM:** `CCBS_CREATE_SUBS`
```xpath
not(exists(//Subscriber/SubscriberId))
```
Create subscriber in CCBS only when SubscriberId not yet assigned.

### Step 45 — OMX_ADD_FUT_OFFER_BRMS
**FM:** `OMX_ADD_FUT_OFFER`
```xpath
FE/BRMS FUT offers on subscriber
```
Add future-dated offers sourced from FE or BRMS evaluation.

### Steps 47–48 — AA_GET_SWITCH_FEATURE_OFFER, OMX_GET_SRV_TRX_NO
**FM:** `AA_GET_SWITCH_FEATURE_OFFER` / `OMX_GET_SRV_TRX_NO` | **Parameter:** NAC
```xpath
ExtendedInfo[Name='AA']/Value='AA'
```
AA provisioning only when AA=AA flag is set on subscriber.

### Step 49 — AA_ACTIVATE_SUBS
**FM:** `AA_ACTIVATE_SUBS` | **Parameter:** NAC
```xpath
SubscriberId exists and AA=AA
```
Activate subscriber in AA only when SubscriberId assigned and AA flag set.

### Step 50 — OMX_ADD_NXT_PP
**FM:** `OMX_ADD_NXT_PP`
```xpath
ServiceType=80 FE or Agreement Offers
```
Add next PP cycle offer for ServiceType=80 (post-paid) offers from FE or agreement.

### Step 51 — OMX_ADD_NEXT_OFFER
**FM:** `OMX_ADD_NEXT_OFFER`
```xpath
complex FE/BRMS non-ServiceType-80/69 non-FUT
```
Add non-PP, non-MCS next-cycle offers from FE or BRMS (excluding future-dated).

### Step 53 — CVSS_CREDIT_CHECK_NEW_ACCNT
**FM:** `CVSS_CREDIT_CHECK`
```xpath
not(exists(//RawAccountID))
```
Credit check for new accounts only (no existing RawAccountID).

### Step 54 — ODS_GET_CREDIT_CLASS_CREDIT_LIMIT
**FM:** `ODS_GET_CREDIT_CLASS_CREDIT_LIMIT`
```xpath
Type=73 and CreditClass not in (F, V0, V1, V3) and SubType not in (RVI, RVB, ...)
```
Get ODS-based credit class/limit for corporate (Type=73) customers who are not in certain pre-approved classes.

### Step 55 — CCBS_UPD_CREDIT_CLASS_NEW_ACCNT
**FM:** `CCBS_UPD_CREDIT_CLASS`
```xpath
not(exists(//RawAccountID))
```
Update credit class for new accounts.

### Step 56 — CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT_FOR_ODS
**FM:** `CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT`
```xpath
same Type=73 CreditClass check as step 54
```
Update credit limit in CCBS for corporate new accounts using ODS-derived limit.

### Step 57 — CALCULATE_MNP_CREDIT_LIMIT
**FM:** `CALCULATE_MNP_CREDIT_LIMIT` ★ NEW
```xpath
Type!=73 and OrderType=7
```
Calculate MNP-specific credit limit for non-corporate (Type≠73) MNP (OrderType=7) orders.

### Step 58 — CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT
**FM:** `CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT`
```xpath
Type!=73 and not(exists(RawAccountID))
```
Update credit limit for non-corporate new accounts.

### Step 59 — CCBS_UPD_CREDIT_LIMIT
**FM:** `CCBS_UPD_CREDIT_LIMIT`
```xpath
Type!=73 and RawAccountID>0
```
Update credit limit for non-corporate existing accounts.

### Step 60 — CVSS_GET_EXISTING_PRODUCT
**FM:** `CVSS_GET_EXISTING_PRODUCT`
```xpath
RawCustomerId>0 and RawAccountID>0 and count(Subscriber)>0
```
Retrieve existing product/subscription count from CVSS for credit scoring.

### Step 61 — CVSS_GET_AUTO_APPROVE_CODE
**FM:** `CVSS_GET_AUTO_APPROVE_CODE` | **Parameter:** requestType=CV
```xpath
Channel ends with '-MF'
```
Auto approve code retrieval only for mobile-first (channel ending '-MF') orders.

### Steps 62–63 — CVSS_CREDIT_CHECK, CCBS_UPD_CREDIT_CLASS
**FM:** `CVSS_CREDIT_CHECK` / `CCBS_UPD_CREDIT_CLASS`
```xpath
ProductCount=0
```
Full credit check + class update only for customers with no existing products.

### Step 64 — CVSS_UPDATE_SUBSCRIBER_COUNT
**FM:** `CVSS_UPDATE_SUBSCRIBER_COUNT`
```xpath
ProductCount>0
```
Update subscriber count only when customer already has existing products.

### Step 65 — AA_CHECK_CONFIRMATION
**FM:** `AA_CHECK_CONFIRMATION` | **Parameter:** NAC | UPDATE_NETWORK_STATUS
```xpath
ExtendedInfo[Name='AA']/Value='AA'
```
AA network status confirmation only for AA-provisioned subscribers.

### Step 66 — SBM_BUY_DATA_PACK
**FM:** `SBM_BUY_DATA_PACK`
```xpath
SBM_PROVISIONING!=N and ServiceType=86 FE/BRMS non-FUT
```
Buy data pack in SBM for ServiceType=86 (data) non-future offers when SBM provisioning is enabled.

### Step 67 — BL_CREATE_CHARGE
**FM:** `BL_CREATE_CHARGE`
```xpath
ServiceType=79 FE/BRMS
```
Create billing charge for ServiceType=79 one-time charge offers.

### Step 68 — CCBS_CHANGE_PACKAGE_SUBSCRIBER
**FM:** `CCBS_CHANGE_PACKAGE_SUBSCRIBER` | **Parameter:** ADD
```xpath
FE/BRMS ServiceType 85/86/68 non-contract non-FUT
```
Add package to subscriber for non-contract, non-future offers in ServiceTypes 85/86/68.

### Step 69 — MCS_REGISTER_SUBSCRIPTION
**FM:** `MCS_REGISTER_SUBSCRIPTION` | **Parameter:** USE_FE_RECURRING=Y
```xpath
ServiceType=69 BRMS/FE
```
Register MCS (recurring charging) subscription for ServiceType=69 offers.

### Step 70 — OMX_EXP_FUT_OFFER_BRMS
**FM:** `OMX_EXP_FUT_OFFER`
```xpath
FE/BRMS EXP_TYPE=FUT and EFF_TYPE!=FUT
```
Expire future-typed offers whose effective type is no longer future.

### Step 71 — CCBS_CREATE_MEMO_FOR_SBM
**FM:** `CCBS_CREATE_MEMO_FOR_SBM`
```xpath
ServiceType=86 FE/BRMS
```
Create SBM-related CCBS memo for ServiceType=86 data offers.

### Step 72 — SBM_FUP_CHANGE_MEMBER
**FM:** `SBM_FUP_CHANGE_MEMBER` | **Parameter:** ADD
```xpath
Offers with FSH/FPL > 0
```
Add subscriber as FUP group member when FSH or FPL offers are present.

### Step 73 — INTX_GET_OFFER_DETAIL
**FM:** `INTX_GET_OFFER_DETAIL` | **Parameter:** ADD
```xpath
ServiceType=80 FE subscriber or agreement
```
Get offer detail from INTX for ServiceType=80 (post-paid) offers.

### Step 75 — OMX_INJECT_OFFER_ADD_ITEMIZE0
**FM:** `OMX_INJECT_OFFER`
```xpath
BillFormat=E or S AND SHOW_USAGE_DETAIL=Y
```
Inject itemized billing offer (ITMBLS02) only for e-bill or S-format with usage detail enabled.

### Step 76 — CCBS_UPDATE_AGREEMENT_ON_UNIT
**FM:** `CCBS_UPDATE_AGREEMENT_ON_UNIT`
```xpath
ParentOU/Agreement exists and non-80 INJECT_OFFER
```
Update agreement on OU level when INJECT_OFFER was added for non-ServiceType-80 offers.

### Step 78 — TMN_CREATE_WALLET_MINIMAL_PROFILE
**FM:** `TMN_CREATE_WALLET_MINIMAL_PROFILE`
```xpath
CustomerTypeInfo/Type=73
```
Create True Money wallet minimal profile only for corporate (Type=73) customers.

---

## §4 — FM Documentation Index

| FM (ActivityID) | Steps | Status |
|-----------------|-------|--------|
| CVSS_GET_VALIDATE_APPROVE_CODE | 1 | [✓ Generated](../FMlogic/Request_CVSS_GET_VALIDATE_APPROVE_CODE.html) |
| INTX_GET_SIM_INFO_BY_MSISDN | 2 | [✓ Generated](../FMlogic/Request_INTX_GET_SIM_INFO_BY_MSISDN.html) |
| OMX_INJECT_OFFER | 3, 75 | [✓ Generated](../FMlogic/Request_OMX_INJECT_OFFER.html) |
| OMX_POPULATE_OFFER | 4 | [✓ Generated](../FMlogic/Request_OMX_POPULATE_OFFER.html) |
| ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST | 5 | [✓ Generated](../FMlogic/Request_ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST.html) |
| INTX_GET_SIM_INFO_BY_SIM | 6 | [✓ Generated](../FMlogic/Request_INTX_GET_SIM_INFO_BY_SIM.html) |
| INTX_GET_SIM_INFO_BY_ICCID | 7 | [✓ Generated](../FMlogic/Request_INTX_GET_SIM_INFO_BY_ICCID.html) |
| OMX_CAL_CHK_SUM_SUB_LEVEL | 8 | [✓ Generated](../FMlogic/Request_OMX_CAL_CHK_SUM_SUB_LEVEL.html) |
| OMX_BIZ_VAL | 9 | [✓ Generated](../FMlogic/Request_OMX_BIZ_VAL.html) |
| TCC_GET_MNP_AUTO_SHAREPLAN | 10 | [★ NEW](../FMlogic/Request_TCC_GET_MNP_AUTO_SHAREPLAN.html) |
| CCBS_RESOLVE_SOC_CODE | 11, 29, 31 | [✓ Generated](../FMlogic/Request_CCBS_RESOLVE_SOC_CODE.html) |
| CCBS_GOD | 12, 30 | [✓ Generated](../FMlogic/Request_CCBS_GOD.html) |
| OMX_OFFER_INCLUSION | 13 | [✓ Generated](../FMlogic/Request_OMX_OFFER_INCLUSION.html) |
| CCBS_GET_ACCOUNT_HEADER | 14 | [✓ Generated](../FMlogic/Request_CCBS_GET_ACCOUNT_HEADER.html) |
| CCBS_GET_AGREEMENT_INFO | 15 | [✓ Generated](../FMlogic/Request_CCBS_GET_AGREEMENT_INFO.html) |
| GET_SPECIAL_OFFER_INDICATOR | 16 | [✓ Generated](../FMlogic/Request_GET_SPECIAL_OFFER_INDICATOR.html) |
| ASRM_INVOKE_MSISDN | 17, 18, 22 | [✓ Generated](../FMlogic/Request_ASRM_INVOKE_MSISDN.html) |
| ASRM_INVOKE_SIM | 19, 23 | [✓ Generated](../FMlogic/Request_ASRM_INVOKE_SIM.html) |
| SMDP_PLUS | 20 | [✓ Generated](../FMlogic/Request_SMDP_PLUS.html) |
| SMDP_PLUS_CONFIRM | 21 | [✓ Generated](../FMlogic/Request_SMDP_PLUS_CONFIRM.html) |
| ASRM_UPDATE_ATTRIBUTE_SIM | 24 | [✓ Generated](../FMlogic/Request_ASRM_UPDATE_ATTRIBUTE_SIM.html) |
| CCBS_CREATE_CUST_WITH_CYCLE | 25 | [✓ Generated](../FMlogic/Request_CCBS_CREATE_CUST_WITH_CYCLE.html) |
| CCBS_GET_CUSTOMER_HEADER | 26 | [✓ Generated](../FMlogic/Request_CCBS_GET_CUSTOMER_HEADER.html) |
| OMX_BRMS_DB | 27 | [✓ Generated](../FMlogic/Request_OMX_BRMS_DB.html) |
| OMX_RESOLVE_SOC_DATA | 28 | [✓ Generated](../FMlogic/Request_OMX_RESOLVE_SOC_DATA.html) |
| OMX_CAL_OFFER_FUT_DATE | 32 | [✓ Generated](../FMlogic/Request_OMX_CAL_OFFER_FUT_DATE.html) |
| OMX_CAL_PP_EXPIRE_DATE | 33 | [✓ Generated](../FMlogic/Request_OMX_CAL_PP_EXPIRE_DATE.html) |
| CCBS_CREATE_PARENT_OU | 34 | [✓ Generated](../FMlogic/Request_CCBS_CREATE_PARENT_OU.html) |
| CCBS_CREATE_CHILD_OU | 35 | [✓ Generated](../FMlogic/Request_CCBS_CREATE_CHILD_OU.html) |
| CCBS_CREATE_AGREE | 36 | [✓ Generated](../FMlogic/Request_CCBS_CREATE_AGREE.html) |
| CCBS_CREATE_ACCT | 37 | [✓ Generated](../FMlogic/Request_CCBS_CREATE_ACCT.html) |
| CCBS_ADD_AGREEOFFER | 38 | [✓ Generated](../FMlogic/Request_CCBS_ADD_AGREEOFFER.html) |
| SBM_FUP_CREATE_GROUP | 39 | [✓ Generated](../FMlogic/Request_SBM_FUP_CREATE_GROUP.html) |
| SBM_FUP_CHANGE_TOPPING | 40 | [✓ Generated](../FMlogic/Request_SBM_FUP_CHANGE_TOPPING.html) |
| SBM_FUP_CHANGE_VARIABLE | 41 | [✓ Generated](../FMlogic/Request_SBM_FUP_CHANGE_VARIABLE.html) |
| OMX_CALC_ACTIVITY_REASON | 42 | [✓ Generated](../FMlogic/Request_OMX_CALC_ACTIVITY_REASON.html) |
| CCBS_CREATE_SUBS | 43 | [✓ Generated](../FMlogic/Request_CCBS_CREATE_SUBS.html) |
| CJ_CREATE_SUB_CALL_VERIFICATION | 44 | [✓ Generated](../FMlogic/Request_CJ_CREATE_SUB_CALL_VERIFICATION.html) |
| OMX_ADD_FUT_OFFER | 45 | [✓ Generated](../FMlogic/Request_OMX_ADD_FUT_OFFER.html) |
| ASRM_GET_UR_DETAILS_MSISDN | 46 | [✓ Generated](../FMlogic/Request_ASRM_GET_UR_DETAILS_MSISDN.html) |
| AA_GET_SWITCH_FEATURE_OFFER | 47 | [✓ Generated](../FMlogic/Request_AA_GET_SWITCH_FEATURE_OFFER.html) |
| OMX_GET_SRV_TRX_NO | 48 | [✓ Generated](../FMlogic/Request_OMX_GET_SRV_TRX_NO.html) |
| AA_ACTIVATE_SUBS | 49 | [✓ Generated](../FMlogic/Request_AA_ACTIVATE_SUBS.html) |
| OMX_ADD_NXT_PP | 50 | [✓ Generated](../FMlogic/Request_OMX_ADD_NXT_PP.html) |
| OMX_ADD_NEXT_OFFER | 51 | [✓ Generated](../FMlogic/Request_OMX_ADD_NEXT_OFFER.html) |
| STATUS_UPDATE_CREATING_PROFILE | 52 | [✓ Generated](../FMlogic/Request_STATUS_UPDATE_CREATING_PROFILE.html) |
| CVSS_CREDIT_CHECK | 53, 62 | [✓ Generated](../FMlogic/Request_CVSS_CREDIT_CHECK.html) |
| ODS_GET_CREDIT_CLASS_CREDIT_LIMIT | 54 | [✓ Generated](../FMlogic/Request_ODS_GET_CREDIT_CLASS_CREDIT_LIMIT.html) |
| CCBS_UPD_CREDIT_CLASS | 55, 63 | [✓ Generated](../FMlogic/Request_CCBS_UPD_CREDIT_CLASS.html) |
| CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT | 56, 58 | [✓ Generated](../FMlogic/Request_CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT.html) |
| CALCULATE_MNP_CREDIT_LIMIT | 57 | [★ NEW](../FMlogic/Request_CALCULATE_MNP_CREDIT_LIMIT.html) |
| CCBS_UPD_CREDIT_LIMIT | 59 | [✓ Generated](../FMlogic/Request_CCBS_UPD_CREDIT_LIMIT.html) |
| CVSS_GET_EXISTING_PRODUCT | 60 | [✓ Generated](../FMlogic/Request_CVSS_GET_EXISTING_PRODUCT.html) |
| CVSS_GET_AUTO_APPROVE_CODE | 61 | [✓ Generated](../FMlogic/Request_CVSS_GET_AUTO_APPROVE_CODE.html) |
| CVSS_UPDATE_SUBSCRIBER_COUNT | 64 | [✓ Generated](../FMlogic/Request_CVSS_UPDATE_SUBSCRIBER_COUNT.html) |
| AA_CHECK_CONFIRMATION | 65 | [✓ Generated](../FMlogic/Request_AA_CHECK_CONFIRMATION.html) |
| SBM_BUY_DATA_PACK | 66 | [✓ Generated](../FMlogic/Request_SBM_BUY_DATA_PACK.html) |
| BL_CREATE_CHARGE | 67 | [✓ Generated](../FMlogic/Request_BL_CREATE_CHARGE.html) |
| CCBS_CHANGE_PACKAGE_SUBSCRIBER | 68 | [✓ Generated](../FMlogic/Request_CCBS_CHANGE_PACKAGE_SUBSCRIBER.html) |
| MCS_REGISTER_SUBSCRIPTION | 69 | [✓ Generated](../FMlogic/Request_MCS_REGISTER_SUBSCRIPTION.html) |
| OMX_EXP_FUT_OFFER | 70 | [✓ Generated](../FMlogic/Request_OMX_EXP_FUT_OFFER.html) |
| CCBS_CREATE_MEMO_FOR_SBM | 71 | [✓ Generated](../FMlogic/Request_CCBS_CREATE_MEMO_FOR_SBM.html) |
| SBM_FUP_CHANGE_MEMBER | 72 | [✓ Generated](../FMlogic/Request_SBM_FUP_CHANGE_MEMBER.html) |
| INTX_GET_OFFER_DETAIL | 73 | [✓ Generated](../FMlogic/Request_INTX_GET_OFFER_DETAIL.html) |
| SMSGATEWAY_SEND_SMS | 74 | [✓ Generated](../FMlogic/Request_SMSGATEWAY_SEND_SMS.html) |
| CCBS_UPDATE_AGREEMENT_ON_UNIT | 76 | [✓ Generated](../FMlogic/Request_CCBS_UPDATE_AGREEMENT_ON_UNIT.html) |
| NAS_CHECK_COLLECTION_BLACKLIST | 77 | [✓ Generated](../FMlogic/Request_NAS_CHECK_COLLECTION_BLACKLIST.html) |
| TMN_CREATE_WALLET_MINIMAL_PROFILE | 78 | [✓ Generated](../FMlogic/Request_TMN_CREATE_WALLET_MINIMAL_PROFILE.html) |

> ★ NEW = newly generated FM doc | ✓ = pre-existing FM doc

---

*TRUE Corporation OMX · Order Journey Documentation*
