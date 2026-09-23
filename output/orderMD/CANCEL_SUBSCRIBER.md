# CANCEL_SUBSCRIBER

> Process Configuration for CANCEL_SUBSCRIBER.

**Total steps:** 79 | **Unique FMs:** 64 | **Entry point:** CCBS_GET_SUBS_LIST

**Order Types handled:** 10 (MNP Port-Out Cancel), 12 (Standard Cancel), 14 (Suspension/Collection)

---

## §2 — Order Flow

| Step | Step ID | FM (ActivityID) | Parameter(s) | PreExecCheck | Previous | Next |
|------|---------|-----------------|--------------|--------------|----------|------|
| 1 | CCBS_GET_SUBS_LIST | CCBS_GET_SUBS_LIST | — | `exists(//ParentOU/OUId) and not(exists(//Subscriber/SubscriberId[./text()])) and not(exists(//Subscriber/MSISDN[./text()]))` | START | CCBS_GET_SUBS_INFO_COLL |
| 2 | CCBS_GET_SUBS_INFO_COLL | CCBS_GET_SUBS_INFO | — | `//OrderType/text()="14"` | CCBS_GET_SUBS_LIST | CCBS_GET_CUST_ACC_SUB_ID |
| 3 | CCBS_GET_CUST_ACC_SUB_ID | CCBS_GET_CUST_ACC_SUB_ID | — | `exists(//Subscriber/MSISDN[./text()])` | CCBS_GET_SUBS_INFO_COLL | CCBS_GET_CUSTOMER_HEADER |
| 4 | CCBS_GET_CUSTOMER_HEADER | CCBS_GET_CUSTOMER_HEADER | — | — | CCBS_GET_CUST_ACC_SUB_ID | CCBS_GET_ACCOUNT_HEADER |
| 5 | CCBS_GET_ACCOUNT_HEADER | CCBS_GET_ACCOUNT_HEADER | — | `not(exists(//Subscriber/SubscriberType)) or //Subscriber/SubscriberType[./text()]!="6A"` | CCBS_GET_CUSTOMER_HEADER | CCBS_GET_BA_HEADER |
| 6 | CCBS_GET_BA_HEADER | CCBS_GET_BA_HEADER | — | `exists(//Customer/Account/AccountID)` | CCBS_GET_ACCOUNT_HEADER | CCBS_GET_AGREEMENT_HEADER |
| 7 | CCBS_GET_AGREEMENT_HEADER | CCBS_GET_AGREEMENT_HEADER | — | `boolean(//AgreementId) and not(exists(//ParentOU/OUId))` | CCBS_GET_BA_HEADER | CCBS_GET_SUBS_INFO |
| 8 | CCBS_GET_SUBS_INFO | CCBS_GET_SUBS_INFO | — | `//OrderType/text()="10" or //OrderType/text()="12"` | CCBS_GET_AGREEMENT_HEADER | CCBS_GET_SUBSCRIBER_HEADER |
| 9 | CCBS_GET_SUBSCRIBER_HEADER | CCBS_GET_SUBSCRIBER_HEADER | — | — | CCBS_GET_SUBS_INFO | GET_SPECIAL_OFFER_INDICATOR |
| 10 | GET_SPECIAL_OFFER_INDICATOR | GET_SPECIAL_OFFER_INDICATOR | ADD_PROP=TR_MULTISIM_IND | `count(//Offers) > 0 or count(//SubscriberOffers) > 0` | CCBS_GET_SUBSCRIBER_HEADER | ASRM_GET_UR_DETAILS_MSISDN |
| 11 | ASRM_GET_UR_DETAILS_MSISDN | ASRM_GET_UR_DETAILS_MSISDN | — | — | GET_SPECIAL_OFFER_INDICATOR | INTX_GET_SIM_INFO_BY_SIM |
| 12 | INTX_GET_SIM_INFO_BY_SIM | INTX_GET_SIM_INFO_BY_SIM | — | — | ASRM_GET_UR_DETAILS_MSISDN | INTX_GET_SIM_INFO_BY_ICCID |
| 13 | INTX_GET_SIM_INFO_BY_ICCID | INTX_GET_SIM_INFO_BY_ICCID | — | — | INTX_GET_SIM_INFO_BY_SIM | INTX_GET_MASTER_MINOR_SIM_INFO |
| 14 | INTX_GET_MASTER_MINOR_SIM_INFO | INTX_GET_MASTER_MINOR_SIM_INFO | — | `(count(//Subscriber/SubscriberOffers[ExtendedInfo[Name="TR_MULTISIM_IND" and (Value="RES" or Value="RCM")]]) > 0) or (count(//Subscriber/SubscriberOffers[ExtendedInfo[Name="TR_MULTISIM_IND" and (Value="REE" or Value="RCE")]]) > 0)` | INTX_GET_SIM_INFO_BY_ICCID | OMX_BIZ_VAL |
| 15 | OMX_BIZ_VAL | OMX_BIZ_VAL | — | — | INTX_GET_MASTER_MINOR_SIM_INFO | OMX_BRMS_DB |
| 16 | OMX_BRMS_DB | OMX_BRMS_DB | — | — | OMX_BIZ_VAL | ATS_ENQUIRY_CAMPAIGN |
| 17 | ATS_ENQUIRY_CAMPAIGN | ATS_ENQUIRY_CAMPAIGN | — | — | OMX_BRMS_DB | CCBS_GET_CUST_ACC_SUB_ID_ATS |
| 18 | CCBS_GET_CUST_ACC_SUB_ID_ATS | CCBS_GET_CUST_ACC_SUB_ID | SOURCE | `boolean(//Subscriber[ExtendedInfo[Name='FE_OR_CCBS' and Value='ATS']])` | ATS_ENQUIRY_CAMPAIGN | CCBS_GET_ACCOUNT_HEADER_ATS |
| 19 | CCBS_GET_ACCOUNT_HEADER_ATS | CCBS_GET_ACCOUNT_HEADER | — | `boolean(//Subscriber[ExtendedInfo[Name='FE_OR_CCBS' and Value='ATS']])` | CCBS_GET_CUST_ACC_SUB_ID_ATS | CCBS_GET_AGREEMENT_HEADER_ATS |
| 20 | CCBS_GET_AGREEMENT_HEADER_ATS | CCBS_GET_AGREEMENT_HEADER | — | `boolean(//Subscriber[ExtendedInfo[Name='FE_OR_CCBS' and Value='ATS']])` | CCBS_GET_ACCOUNT_HEADER_ATS | CCBS_GET_SUBSCRIBER_HEADER_ATS |
| 21 | CCBS_GET_SUBSCRIBER_HEADER_ATS | CCBS_GET_SUBSCRIBER_HEADER | — | `boolean(//Subscriber[ExtendedInfo[Name='FE_OR_CCBS' and Value='ATS']])` | CCBS_GET_AGREEMENT_HEADER_ATS | CCBS_GET_CUSTOMER_HEADER_ATS |
| 22 | CCBS_GET_CUSTOMER_HEADER_ATS | CCBS_GET_CUSTOMER_HEADER | — | `boolean(//Subscriber[ExtendedInfo[Name='FE_OR_CCBS' and Value='ATS']])` | CCBS_GET_SUBSCRIBER_HEADER_ATS | CCBS_GET_SUBS_INFO_ATS |
| 23 | CCBS_GET_SUBS_INFO_ATS | CCBS_GET_SUBS_INFO | — | `boolean(//Subscriber[Status !=67 and Status !=76 and Status !=84 and ExtendedInfo[Name='FE_OR_CCBS' and Value='ATS']])` | CCBS_GET_CUSTOMER_HEADER_ATS | CCBS_GOD_ATS |
| 24 | CCBS_GOD_ATS | CCBS_GOD | — | `count(//BundleInfo[ConvergenceType='MobileSoftBundle'])>0` | CCBS_GET_SUBS_INFO_ATS | ATS_CAMPAIGN_RULE_REMOVE_CAMPAIGN |
| 25 | ATS_CAMPAIGN_RULE_REMOVE_CAMPAIGN | ATS_CAMPAIGN_RULE_REMOVE_CAMPAIGN | — | `count(//BundleInfo[ConvergenceType='MobileSoftBundle'])>0` | CCBS_GOD_ATS | CCBS_RESOLVE_SOC_CODE_BRMS |
| 26 | CCBS_RESOLVE_SOC_CODE_BRMS | CCBS_RESOLVE_SOC_CODE | — | `(count(//BundleInfo[ConvergenceType='MobileSoftBundle'])>0) or (//Subscriber/SubscriberOffers/ExtendedInfo[Name='FE_OR_CCBS' and (Value='BRMS' or Value='BRMS_REMOVE')])` | ATS_CAMPAIGN_RULE_REMOVE_CAMPAIGN | OMX_RESOLVE_SOC_DATA |
| 27 | OMX_RESOLVE_SOC_DATA | OMX_RESOLVE_SOC_DATA | — | `count(//BundleInfo[ConvergenceType='MobileSoftBundle'])>0` | CCBS_RESOLVE_SOC_CODE_BRMS | INTX_GET_TOTAL_OBLIGATION_INFO |
| 28 | INTX_GET_TOTAL_OBLIGATION_INFO | INTX_GET_TOTAL_OBLIGATION_INFO | — | `boolean(//OrderData[ExtendedInfo[Name="CANCEL_TYPE" and Value='endbill']]) and boolean(//Subscriber/SubscriberOffers/ExtendedInfo[Name='FE_OR_CCBS' and Value='BRMS_REMOVE'])` | OMX_RESOLVE_SOC_DATA | OMX_UPDATE_OFFER_PARAMETER |
| 29 | OMX_UPDATE_OFFER_PARAMETER | OMX_UPDATE_OFFER_PARAMETER ⚠ | ACCEPT_AMOUNT=100 | `boolean(//OrderData[ExtendedInfo[Name="CANCEL_TYPE" and Value='endbill']]) and boolean(//Subscriber/SubscriberOffers/ExtendedInfo[Name='FE_OR_CCBS' and Value='BRMS_REMOVE'])` | INTX_GET_TOTAL_OBLIGATION_INFO | CCBS_CHANGE_PACKAGE_SUBSCRIBER_REMOVE |
| 30 | CCBS_CHANGE_PACKAGE_SUBSCRIBER_REMOVE | CCBS_CHANGE_PACKAGE_SUBSCRIBER | REMOVE \| ACTIVITY_REASON=SYSREQ | Complex PreExecCheck | OMX_UPDATE_OFFER_PARAMETER | SBM_VALIDATE |
| 31 | SBM_VALIDATE | SBM_VALIDATE | — | `boolean(//SubscriberOffers[ServiceType[.='86']][ExtendedInfo[...BRMS_REMOVE or ATS_REMOVE]])` | CCBS_CHANGE_PACKAGE_SUBSCRIBER_REMOVE | SBM_CANCEL_DATA_PACK_IMMEDIATE |
| 32 | SBM_CANCEL_DATA_PACK_IMMEDIATE | SBM_CANCEL_DATA_PACK_IMMEDIATE | — | `boolean([ServiceType='86'][DataInfo[PackType='RC']][BRMS_REMOVE or ATS_REMOVE])` | SBM_VALIDATE | SBM_UPDATE_EXPIRED |
| 33 | SBM_UPDATE_EXPIRED | SBM_UPDATE_EXPIRED | — | `boolean([ServiceType='86'][DataInfo[PackType='OC']][BRMS_REMOVE or ATS_REMOVE])` | SBM_CANCEL_DATA_PACK_IMMEDIATE | SBM_BUY_DATA_PACK |
| 34 | SBM_BUY_DATA_PACK | SBM_BUY_DATA_PACK | — | `boolean([ServiceType='86'][FE_OR_CCBS=BRMS or ATS])` | SBM_UPDATE_EXPIRED | BL_CREATE_CHARGE |
| 35 | BL_CREATE_CHARGE | BL_CREATE_CHARGE | — | `boolean([ServiceType='79'][FE_OR_CCBS=BRMS or ATS])` | SBM_BUY_DATA_PACK | CCBS_CHANGE_PACKAGE_SUBSCRIBER |
| 36 | CCBS_CHANGE_PACKAGE_SUBSCRIBER | CCBS_CHANGE_PACKAGE_SUBSCRIBER | ADD \| ACTIVITY_REASON=SYSREQ | `boolean([ServiceType='86'][BRMS or ATS] or [ServiceType='85'/'86'/'68'][ATS] or [ServiceType='85'][BRMS])` | BL_CREATE_CHARGE | OMX_CAL_ORDER |
| 37 | OMX_CAL_ORDER | OMX_CAL_ORDER ⚠ | — | `boolean(//Subscriber[not(FE_OR_CCBS) or FE_OR_CCBS!=ATS])` | CCBS_CHANGE_PACKAGE_SUBSCRIBER | CCBS_UPDATE_BILLING_ARRANGEMENT |
| 38 | CCBS_UPDATE_BILLING_ARRANGEMENT | CCBS_UPDATE_BILLING_ARRANGEMENT | DSD | `boolean(//OrderData[ExtendedInfo[Name="FINAL_BILL"]]) and not-ATS` | OMX_CAL_ORDER | MCS_GET_PACKCODE_FINALL_BILL |
| 39 | MCS_GET_PACKCODE_FINALL_BILL | MCS_GET_PACKCODE | — | `not-ATS and CANCEL_TYPE=endbill` | CCBS_UPDATE_BILLING_ARRANGEMENT | MCS_CANCEL_AFTER_SALE_FINALL_BILL |
| 40 | MCS_CANCEL_AFTER_SALE_FINALL_BILL | MCS_CANCEL_AFTER_SALE | — | `not-ATS and CANCEL_TYPE=endbill` | MCS_GET_PACKCODE_FINALL_BILL | OMX_ADD_FUT_ORDER |
| 41 | OMX_ADD_FUT_ORDER | OMX_ADD_FUT_ORDER | FINALLY=Y | `EFF_TYPE=FUT and not-ATS` | MCS_CANCEL_AFTER_SALE_FINALL_BILL | SBM_FUP_CHANGE_MEMBER |
| 42 | SBM_FUP_CHANGE_MEMBER | SBM_FUP_CHANGE_MEMBER | REMOVE | `count(SubscriberOffers[SPECIAL_OFFER_INDICATOR=FSH or FPL])>0 and not-ATS` | OMX_ADD_FUT_ORDER | AA_GET_SWITCH_FEATURE_OFFER |
| 43 | AA_GET_SWITCH_FEATURE_OFFER | AA_GET_SWITCH_FEATURE_OFFER | — | `SubscriberType!="6A" and not-ATS` | SBM_FUP_CHANGE_MEMBER | CCBS_GOD |
| 44 | CCBS_GOD | CCBS_GOD | — | — | AA_GET_SWITCH_FEATURE_OFFER | OMX_CALC_ACTIVITY_REASON |
| 45 | OMX_CALC_ACTIVITY_REASON | OMX_CALC_ACTIVITY_REASON | CANCEL | `OrderType=10 and not-ATS` | CCBS_GOD | CCBS_MSIM_CANCEL_SIM |
| 46 | CCBS_MSIM_CANCEL_SIM | CCBS_MSIM_CANCEL_SIM | — | `TR_MULTISIM_IND=RCM and not-ATS` | OMX_CALC_ACTIVITY_REASON | OMX_POPULATE_MSIM_INFO |
| 47 | OMX_POPULATE_MSIM_INFO | OMX_POPULATE_MSIM_INFO | SPC=AUTO_CANCEL | `FE_OR_CCBS=CCBS and TR_MULTISIM_IND=RES or RCM and not-ATS` | CCBS_MSIM_CANCEL_SIM | OMX_TRANSFORM_NETWORK_CMD_TO_IOT |
| 48 | OMX_TRANSFORM_NETWORK_CMD_TO_IOT | OMX_TRANSFORM_NETWORK_CMD_TO_IOT | — | `SubscriberType=INB or ICA and not-ATS` | OMX_POPULATE_MSIM_INFO | OMX_GET_SRV_TRX_NO_MSIM_CCD |
| 49 | OMX_GET_SRV_TRX_NO_MSIM_CCD | OMX_GET_SRV_TRX_NO_MSIM | CCD | `MultiSIMInfo/Minor[Source='FE'] and not-6A and not-ATS` | OMX_TRANSFORM_NETWORK_CMD_TO_IOT | AA_ACTIVATE_SUBS_MSIM |
| 50 | AA_ACTIVATE_SUBS_MSIM | AA_ACTIVATE_SUBS_MSIM | CCD \| REMOVE | `MultiSIMInfo/Minor[Source='FE'] and not-6A and not-ATS` | OMX_GET_SRV_TRX_NO_MSIM_CCD | OMX_GET_SRV_TRX_NO_CCD |
| 51 | OMX_GET_SRV_TRX_NO_CCD | OMX_GET_SRV_TRX_NO | CCD | `not-6A and not-ATS and BRMS_REMOVE` | AA_ACTIVATE_SUBS_MSIM | AA_ACTIVATE_SUBS_CCD |
| 52 | AA_ACTIVATE_SUBS_CCD | AA_ACTIVATE_SUBS | CCD | `not-6A and not-ATS and BRMS_REMOVE` | OMX_GET_SRV_TRX_NO_CCD | OMX_GET_SRV_TRX_NO |
| 53 | OMX_GET_SRV_TRX_NO | OMX_GET_SRV_TRX_NO | DSD | `not-6A and not-ATS` | AA_ACTIVATE_SUBS_CCD | AA_ACTIVATE_SUBS |
| 54 | AA_ACTIVATE_SUBS | AA_ACTIVATE_SUBS | DSD | `not-6A and not-ATS` | OMX_GET_SRV_TRX_NO | TVS_REMOVE_COMPO_OTT |
| 55 | TVS_REMOVE_COMPO_OTT | TVS_REMOVE_COMPO_OTT | — | `boolean(//Customer/ExtendedInfo[Name="TVS_CUSTOMER_NUMBER"])` | AA_ACTIVATE_SUBS | BDH_UPDATE_DIRECT_DEBIT_STATUS |
| 56 | BDH_UPDATE_DIRECT_DEBIT_STATUS | BDH_UPDATE_DIRECT_DEBIT_STATUS | — | `boolean(//OrderData[ExtendedInfo[Name="FINAL_BILL"]]) and string-length(//RawAccountID)>0` | TVS_REMOVE_COMPO_OTT | CCBS_CANCEL_SUBS |
| 57 | CCBS_CANCEL_SUBS | CCBS_CANCEL_SUBS | — | `ActivityReason!=MNPHR and !=RFREOT and OrderType!=14 and !=10 and not-ATS` | BDH_UPDATE_DIRECT_DEBIT_STATUS | CCBS_L9_UPDATE_MNP_ATTRIBUTES |
| 58 | CCBS_L9_UPDATE_MNP_ATTRIBUTES | CCBS_L9_UPDATE_MNP_ATTRIBUTES | — | `OrderType=10 and not-ATS` | CCBS_CANCEL_SUBS | CCBS_UPDATE_MNP_REVERSAL_CANCEL |
| 59 | CCBS_UPDATE_MNP_REVERSAL_CANCEL | CCBS_UPDATE_MNP_REVERSAL_CANCEL | — | `ActivityReason=MNPHR or RFREOT and not-ATS` | CCBS_L9_UPDATE_MNP_ATTRIBUTES | CCBS_APPLY_COLL_ACTIVITIES |
| 60 | CCBS_APPLY_COLL_ACTIVITIES | CCBS_APPLY_COLL_ACTIVITIES | CANCEL | `OrderType=14 and not-ATS` | CCBS_UPDATE_MNP_REVERSAL_CANCEL | ASRM_INVOKE_MSISDN_RELEASE |
| 61 | ASRM_INVOKE_MSISDN_RELEASE | ASRM_INVOKE_MSISDN | ACTIVITY=RELEASE | `OrderType!=10 and ActivityReason!=MNPHR/RFREOT and not-ATS` | CCBS_APPLY_COLL_ACTIVITIES | ASRM_INVOKE_MSISDN_PORT_OUT_RELEASE |
| 62 | ASRM_INVOKE_MSISDN_PORT_OUT_RELEASE | ASRM_INVOKE_MSISDN | ACTIVITY=PORT OUT RELEASE | `OrderType=10 and not-ATS` | ASRM_INVOKE_MSISDN_RELEASE | ASRM_INVOKE_MSISDN_PORT_IN_REVERSE |
| 63 | ASRM_INVOKE_MSISDN_PORT_IN_REVERSE | ASRM_INVOKE_MSISDN | ACTIVITY=PORT IN REVERSE | `ActivityReason=MNPHR or RFREOT and not-ATS` | ASRM_INVOKE_MSISDN_PORT_OUT_RELEASE | ASRM_INVOKE_SIM_RELEASE |
| 64 | ASRM_INVOKE_SIM_RELEASE | ASRM_INVOKE_SIM | ACTIVITY=RELEASE | `not-ATS` | ASRM_INVOKE_MSISDN_PORT_IN_REVERSE | ASRM_INVOKE_MINOR_SIM_RELEASE |
| 65 | ASRM_INVOKE_MINOR_SIM_RELEASE | ASRM_INVOKE_MINOR_SIM | ACTIVITY=RELEASE | `TR_MULTISIM_IND=RES or REE and not-ATS` | ASRM_INVOKE_SIM_RELEASE | CVSS_GET_EXISTING_PRODUCT |
| 66 | CVSS_GET_EXISTING_PRODUCT | CVSS_GET_EXISTING_PRODUCT | — | `not-INB/ICA and not-ATS` | ASRM_INVOKE_MINOR_SIM_RELEASE | CVSS_CANCEL_SUBS |
| 67 | CVSS_CANCEL_SUBS | CVSS_CANCEL_SUBS | — | `not-INB/ICA and not-ATS` | CVSS_GET_EXISTING_PRODUCT | STATUS_UPDATE_CREATING_PROFILE |
| 68 | STATUS_UPDATE_CREATING_PROFILE | STATUS_UPDATE_CREATING_PROFILE | — | `not-ATS` | CVSS_CANCEL_SUBS | CREATE_TDS_PROFILE |
| 69 | CREATE_TDS_PROFILE | CREATE_TDS_PROFILE | — | `FE_OR_CCBS=CCBS and ServiceType=85 and not-ATS` | STATUS_UPDATE_CREATING_PROFILE | PSA_UPDATE_DEVICE |
| 70 | PSA_UPDATE_DEVICE | PSA_UPDATE_DEVICE | srType=CANCEL \| deviceStatus=COMPLETE | `SubscriberOffers[TR_SPECIAL_OFFER_IND=IOTBU]` | CREATE_TDS_PROFILE | TDG_CANCEL_SUBSCRIBER |
| 71 | TDG_CANCEL_SUBSCRIBER | TDG_CANCEL_SUBSCRIBER | — | `SubscriberOffers[TR_SPECIAL_OFFER_IND=IOTBU]` | PSA_UPDATE_DEVICE | MCS_GET_PACKCODE |
| 72 | MCS_GET_PACKCODE | MCS_GET_PACKCODE | — | `not-ATS` | TDG_CANCEL_SUBSCRIBER | MCS_CANCEL_AFTER_SALE |
| 73 | MCS_CANCEL_AFTER_SALE | MCS_CANCEL_AFTER_SALE | — | `MCS_CANCEL_AFS=Y` | MCS_GET_PACKCODE | CJ_QUERY_STATE |
| 74 | CJ_QUERY_STATE | CJ_QUERY_STATE | — | `not-ATS` | MCS_CANCEL_AFTER_SALE | SFF_CANCEL_CALL_VERIFY_MOBILE |
| 75 | SFF_CANCEL_CALL_VERIFY_MOBILE | SFF_CANCEL_CALL_VERIFY_MOBILE | — | `CALL_VER_RESULT!=PASS and not-ATS` | CJ_QUERY_STATE | ATS_DEBUNDLE_CAMPAIGN |
| 76 | ATS_DEBUNDLE_CAMPAIGN | ATS_DEBUNDLE_CAMPAIGN | — | `count(//BundleInfo[ConvergenceAction='DebundleCampaign' or 'DebundleProductNumber'])>0` | SFF_CANCEL_CALL_VERIFY_MOBILE | OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE |
| 77 | OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE | OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE | — | `DebundleCampaign or DebundleProductNumber present` | ATS_DEBUNDLE_CAMPAIGN | SEND_SMS_MESSAGE_3CJ |
| 78 | SEND_SMS_MESSAGE_3CJ | SEND_SMS_MESSAGE_3CJ | — | `DebundleCampaign or DebundleProductNumber present` | OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE | APIGW_OPT_IN_OUT |
| 79 | APIGW_OPT_IN_OUT | APIGW_OPT_IN_OUT | ACTION=0 | `FE_OR_CCBS=CCBS and TR_OFFER_GROUP=CBSC` | SEND_SMS_MESSAGE_3CJ | END |

> ⚠ = FM rule file not found (internal OMX function)

---

## §3 — Order Journey Phases

### Phase 1: Data Collection (Steps 1–16)
Gather subscriber, account, BA, agreement, and SIM information from CCBS/INTX/ASRM. Business validation and BRMS rule evaluation.

### Phase 2: ATS SoftBundle Path (Steps 17–27)
Gate: `FE_OR_CCBS=ATS`. Enquire and remove ATS campaign; re-fetch CCBS data for ATS subscribers; remove SOC codes for SoftBundle.

### Phase 3: Zero Final Bill (Steps 28–29)
Gate: `CANCEL_TYPE=endbill`. Get obligation info and update offer parameter for BRMS_REMOVE subscribers.

### Phase 4: Package/SOC Changes (Steps 30–36)
Remove and add SOC packages via CCBS. Handle SBM data pack cancel/expire/buy. BL charge creation.

### Phase 5: Billing & Profile (Steps 37–43)
OMX calculate order, update billing arrangement, MCS final bill, future order, SBM FUP member removal, AA feature removal.

### Phase 6: Core CCBS GOD + MultiSIM (Steps 44–54)
CCBS_GOD data enrichment. MultiSIM cancel/populate/transform, AA/network SIM operations.

### Phase 7: TVS & Direct Debit (Steps 55–56)
Gate: `TVS_CUSTOMER_NUMBER`. Remove OTT component; update direct debit status for final bill.

### Phase 8: Core Cancellation (Steps 57–65)
CCBS subscriber cancel (standard), MNP L9 attribute updates (port-out=79, reversal=86), CCBS collection activities for OT=14, ASRM MSISDN/SIM release.

### Phase 9: Profile & Post-Cancel (Steps 66–79)
CVSS cancel, TDS profile creation, PSA/TDG IoT device cancel, MCS after-sale cancel, CJ call-verify state query, SFF cancel call verify, ATS debundle campaign, SMS notifications, APIGW opt-in/out.

---

## §3 — PreExecCheck Details

### Step 1 — CCBS_GET_SUBS_LIST
**FM:** `CCBS_GET_SUBS_LIST`
```xpath
exists(//ParentOU/OUId) and not(exists(//Subscriber/SubscriberId[./text()])) and not(exists(//Subscriber/MSISDN[./text()]))
```

### Step 2 — CCBS_GET_SUBS_INFO_COLL
**FM:** `CCBS_GET_SUBS_INFO`
```xpath
//OrderType/text()="14"
```

### Step 3 — CCBS_GET_CUST_ACC_SUB_ID
**FM:** `CCBS_GET_CUST_ACC_SUB_ID`
```xpath
exists(//Subscriber/MSISDN[./text()])
```

### Step 5 — CCBS_GET_ACCOUNT_HEADER
**FM:** `CCBS_GET_ACCOUNT_HEADER`
```xpath
not(exists(//Subscriber/SubscriberType)) or //Subscriber/SubscriberType[./text()]!="6A"
```

### Step 6 — CCBS_GET_BA_HEADER
**FM:** `CCBS_GET_BA_HEADER`
```xpath
exists(//Customer/Account/AccountID)
```

### Step 7 — CCBS_GET_AGREEMENT_HEADER
**FM:** `CCBS_GET_AGREEMENT_HEADER`
```xpath
boolean(//AgreementId) and not(exists(//ParentOU/OUId))
```

### Step 8 — CCBS_GET_SUBS_INFO
**FM:** `CCBS_GET_SUBS_INFO`
```xpath
//OrderType/text()="10" or //OrderType/text()="12"
```

### Step 10 — GET_SPECIAL_OFFER_INDICATOR
**FM:** `GET_SPECIAL_OFFER_INDICATOR`
```xpath
count(//Offers) > 0 or count(//SubscriberOffers) > 0
```

### Step 14 — INTX_GET_MASTER_MINOR_SIM_INFO
**FM:** `INTX_GET_MASTER_MINOR_SIM_INFO`
```xpath
(count(//Subscriber/SubscriberOffers[ExtendedInfo[Name="TR_MULTISIM_IND" and (Value="RES" or Value="RCM")]]) > 0)
or (count(//Subscriber/SubscriberOffers[ExtendedInfo[Name="TR_MULTISIM_IND" and (Value="REE" or Value="RCE")]]) > 0)
```

### Step 18 — CCBS_GET_CUST_ACC_SUB_ID_ATS
**FM:** `CCBS_GET_CUST_ACC_SUB_ID`
```xpath
boolean(//Subscriber[ExtendedInfo[Name='FE_OR_CCBS' and Value='ATS']])
```

### Step 24 — CCBS_GOD_ATS
**FM:** `CCBS_GOD`
```xpath
count(//BundleInfo[ConvergenceType='MobileSoftBundle'])>0
```

### Step 25 — ATS_CAMPAIGN_RULE_REMOVE_CAMPAIGN
**FM:** `ATS_CAMPAIGN_RULE_REMOVE_CAMPAIGN`
```xpath
count(//BundleInfo[ConvergenceType='MobileSoftBundle'])>0
```

### Step 55 — TVS_REMOVE_COMPO_OTT
**FM:** `TVS_REMOVE_COMPO_OTT`
```xpath
boolean(//Customer/ExtendedInfo[Name="TVS_CUSTOMER_NUMBER"])
```

### Step 57 — CCBS_CANCEL_SUBS
**FM:** `CCBS_CANCEL_SUBS`
```xpath
//SubscriberActivityInfo/ActivityReason/text()!="MNPHR" and //SubscriberActivityInfo/ActivityReason/text()!="RFREOT"
and //OrderType/text()!="14" and //OrderType/text()!="10"
and boolean(//Subscriber[not(ExtendedInfo[Name='FE_OR_CCBS']) or (ExtendedInfo[Name='FE_OR_CCBS' and Value!='ATS'])])
```

### Step 58 — CCBS_L9_UPDATE_MNP_ATTRIBUTES
**FM:** `CCBS_L9_UPDATE_MNP_ATTRIBUTES`
```xpath
(//OrderType/text()="10")
and boolean(//Subscriber[not(ExtendedInfo[Name='FE_OR_CCBS']) or (ExtendedInfo[Name='FE_OR_CCBS' and Value!='ATS'])])
```

### Step 59 — CCBS_UPDATE_MNP_REVERSAL_CANCEL
**FM:** `CCBS_UPDATE_MNP_REVERSAL_CANCEL`
```xpath
(//SubscriberActivityInfo/ActivityReason/text()="MNPHR" or //SubscriberActivityInfo/ActivityReason/text()="RFREOT")
and boolean(//Subscriber[not(ExtendedInfo[Name='FE_OR_CCBS']) or (ExtendedInfo[Name='FE_OR_CCBS' and Value!='ATS'])])
```

### Step 60 — CCBS_APPLY_COLL_ACTIVITIES
**FM:** `CCBS_APPLY_COLL_ACTIVITIES`
```xpath
(//OrderType/text()="14")
and boolean(//Subscriber[not(ExtendedInfo[Name='FE_OR_CCBS']) or (ExtendedInfo[Name='FE_OR_CCBS' and Value!='ATS'])])
```

### Step 75 — SFF_CANCEL_CALL_VERIFY_MOBILE
**FM:** `SFF_CANCEL_CALL_VERIFY_MOBILE`
```xpath
boolean(//SubscriberOffers/ExtendedInfo[Name="CALL_VER_RESULT" and Value!='PASS'])
and boolean(//Subscriber[not(ExtendedInfo[Name='FE_OR_CCBS']) or (ExtendedInfo[Name='FE_OR_CCBS' and Value!='ATS'])])
```

---

## §4 — FM Documentation Index

| FM (ActivityID) | Used in Steps | Status | Doc Link |
|-----------------|---------------|--------|----------|
| CCBS_GET_SUBS_LIST | 1 | ✓ | [Request_CCBS_GET_SUBS_LIST.html](../FMlogic/Request_CCBS_GET_SUBS_LIST.html) |
| CCBS_GET_SUBS_INFO | 2, 8, 23 | ✓ | [Request_CCBS_GET_SUBS_INFO.html](../FMlogic/Request_CCBS_GET_SUBS_INFO.html) |
| CCBS_GET_CUST_ACC_SUB_ID | 3, 18 | ✓ | [Request_CCBS_GET_CUST_ACC_SUB_ID.html](../FMlogic/Request_CCBS_GET_CUST_ACC_SUB_ID.html) |
| CCBS_GET_CUSTOMER_HEADER | 4, 22 | ✓ | [Request_CCBS_GET_CUSTOMER_HEADER.html](../FMlogic/Request_CCBS_GET_CUSTOMER_HEADER.html) |
| CCBS_GET_ACCOUNT_HEADER | 5, 19 | ✓ | [Request_CCBS_GET_ACCOUNT_HEADER.html](../FMlogic/Request_CCBS_GET_ACCOUNT_HEADER.html) |
| CCBS_GET_BA_HEADER | 6 | ✓ | [Request_CCBS_GET_BA_HEADER.html](../FMlogic/Request_CCBS_GET_BA_HEADER.html) |
| CCBS_GET_AGREEMENT_HEADER | 7, 20 | ✓ | [Request_CCBS_GET_AGREEMENT_HEADER.html](../FMlogic/Request_CCBS_GET_AGREEMENT_HEADER.html) |
| CCBS_GET_SUBSCRIBER_HEADER | 9, 21 | ✓ | [Request_CCBS_GET_SUBSCRIBER_HEADER.html](../FMlogic/Request_CCBS_GET_SUBSCRIBER_HEADER.html) |
| GET_SPECIAL_OFFER_INDICATOR | 10 | ✓ | [Request_GET_SPECIAL_OFFER_INDICATOR.html](../FMlogic/Request_GET_SPECIAL_OFFER_INDICATOR.html) |
| ASRM_GET_UR_DETAILS_MSISDN | 11 | ✓ | [Request_ASRM_GET_UR_DETAILS_MSISDN.html](../FMlogic/Request_ASRM_GET_UR_DETAILS_MSISDN.html) |
| INTX_GET_SIM_INFO_BY_SIM | 12 | ✓ | [Request_INTX_GET_SIM_INFO_BY_SIM.html](../FMlogic/Request_INTX_GET_SIM_INFO_BY_SIM.html) |
| INTX_GET_SIM_INFO_BY_ICCID | 13 | ✓ | [Request_INTX_GET_SIM_INFO_BY_ICCID.html](../FMlogic/Request_INTX_GET_SIM_INFO_BY_ICCID.html) |
| INTX_GET_MASTER_MINOR_SIM_INFO | 14 | ✓ | [Request_INTX_GET_MASTER_MINOR_SIM_INFO.html](../FMlogic/Request_INTX_GET_MASTER_MINOR_SIM_INFO.html) |
| OMX_BIZ_VAL | 15 | ✓ | [Request_OMX_BIZ_VAL.html](../FMlogic/Request_OMX_BIZ_VAL.html) |
| OMX_BRMS_DB | 16 | ✓ | [Request_OMX_BRMS_DB.html](../FMlogic/Request_OMX_BRMS_DB.html) |
| ATS_ENQUIRY_CAMPAIGN | 17 | ✓ | [Request_ATS_ENQUIRY_CAMPAIGN.html](../FMlogic/Request_ATS_ENQUIRY_CAMPAIGN.html) |
| CCBS_GOD | 24, 44 | ✓ | [Request_CCBS_GOD.html](../FMlogic/Request_CCBS_GOD.html) |
| ATS_CAMPAIGN_RULE_REMOVE_CAMPAIGN | 25 | ✓ NEW | [Request_ATS_CAMPAIGN_RULE_REMOVE_CAMPAIGN.html](../FMlogic/Request_ATS_CAMPAIGN_RULE_REMOVE_CAMPAIGN.html) |
| CCBS_RESOLVE_SOC_CODE | 26 | ✓ | [Request_CCBS_RESOLVE_SOC_CODE.html](../FMlogic/Request_CCBS_RESOLVE_SOC_CODE.html) |
| OMX_RESOLVE_SOC_DATA | 27 | ✓ | [Request_OMX_RESOLVE_SOC_DATA.html](../FMlogic/Request_OMX_RESOLVE_SOC_DATA.html) |
| INTX_GET_TOTAL_OBLIGATION_INFO | 28 | ✓ | [Request_INTX_GET_TOTAL_OBLIGATION_INFO.html](../FMlogic/Request_INTX_GET_TOTAL_OBLIGATION_INFO.html) |
| OMX_UPDATE_OFFER_PARAMETER | 29 | ⚠ NOT FOUND | — (internal OMX function) |
| CCBS_CHANGE_PACKAGE_SUBSCRIBER | 30, 36 | ✓ | [Request_CCBS_CHANGE_PACKAGE_SUBSCRIBER.html](../FMlogic/Request_CCBS_CHANGE_PACKAGE_SUBSCRIBER.html) |
| SBM_VALIDATE | 31 | ✓ | [Request_SBM_VALIDATE.html](../FMlogic/Request_SBM_VALIDATE.html) |
| SBM_CANCEL_DATA_PACK_IMMEDIATE | 32 | ✓ | [Request_SBM_CANCEL_DATA_PACK_IMMEDIATE.html](../FMlogic/Request_SBM_CANCEL_DATA_PACK_IMMEDIATE.html) |
| SBM_UPDATE_EXPIRED | 33 | ✓ | [Request_SBM_UPDATE_EXPIRED.html](../FMlogic/Request_SBM_UPDATE_EXPIRED.html) |
| SBM_BUY_DATA_PACK | 34 | ✓ | [Request_SBM_BUY_DATA_PACK.html](../FMlogic/Request_SBM_BUY_DATA_PACK.html) |
| BL_CREATE_CHARGE | 35 | ✓ | [Request_BL_CREATE_CHARGE.html](../FMlogic/Request_BL_CREATE_CHARGE.html) |
| OMX_CAL_ORDER | 37 | ⚠ NOT FOUND | — (internal OMX function) |
| CCBS_UPDATE_BILLING_ARRANGEMENT | 38 | ✓ | [Request_CCBS_UPDATE_BILLING_ARRANGEMENT.html](../FMlogic/Request_CCBS_UPDATE_BILLING_ARRANGEMENT.html) |
| MCS_GET_PACKCODE | 39, 72 | ✓ | [Request_MCS_GET_PACKCODE.html](../FMlogic/Request_MCS_GET_PACKCODE.html) |
| MCS_CANCEL_AFTER_SALE | 40, 73 | ✓ | [Request_MCS_CANCEL_AFTER_SALE.html](../FMlogic/Request_MCS_CANCEL_AFTER_SALE.html) |
| OMX_ADD_FUT_ORDER | 41 | ✓ | [Request_OMX_ADD_FUT_ORDER.html](../FMlogic/Request_OMX_ADD_FUT_ORDER.html) |
| SBM_FUP_CHANGE_MEMBER | 42 | ✓ | [Request_SBM_FUP_CHANGE_MEMBER.html](../FMlogic/Request_SBM_FUP_CHANGE_MEMBER.html) |
| AA_GET_SWITCH_FEATURE_OFFER | 43 | ✓ | [Request_AA_GET_SWITCH_FEATURE_OFFER.html](../FMlogic/Request_AA_GET_SWITCH_FEATURE_OFFER.html) |
| OMX_CALC_ACTIVITY_REASON | 45 | ✓ | [Request_OMX_CALC_ACTIVITY_REASON.html](../FMlogic/Request_OMX_CALC_ACTIVITY_REASON.html) |
| CCBS_MSIM_CANCEL_SIM | 46 | ✓ | [Request_CCBS_MSIM_CANCEL_SIM.html](../FMlogic/Request_CCBS_MSIM_CANCEL_SIM.html) |
| OMX_POPULATE_MSIM_INFO | 47 | ✓ | [Request_OMX_POPULATE_MSIM_INFO.html](../FMlogic/Request_OMX_POPULATE_MSIM_INFO.html) |
| OMX_TRANSFORM_NETWORK_CMD_TO_IOT | 48 | ✓ | [Request_OMX_TRANSFORM_NETWORK_CMD_TO_IOT.html](../FMlogic/Request_OMX_TRANSFORM_NETWORK_CMD_TO_IOT.html) |
| OMX_GET_SRV_TRX_NO_MSIM | 49 | ✓ | [Request_OMX_GET_SRV_TRX_NO_MSIM.html](../FMlogic/Request_OMX_GET_SRV_TRX_NO_MSIM.html) |
| AA_ACTIVATE_SUBS_MSIM | 50 | ✓ | [Request_AA_ACTIVATE_SUBS_MSIM.html](../FMlogic/Request_AA_ACTIVATE_SUBS_MSIM.html) |
| OMX_GET_SRV_TRX_NO | 51, 53 | ✓ | [Request_OMX_GET_SRV_TRX_NO.html](../FMlogic/Request_OMX_GET_SRV_TRX_NO.html) |
| AA_ACTIVATE_SUBS | 52, 54 | ✓ | [Request_AA_ACTIVATE_SUBS.html](../FMlogic/Request_AA_ACTIVATE_SUBS.html) |
| TVS_REMOVE_COMPO_OTT | 55 | ✓ NEW | [Request_TVS_REMOVE_COMPO_OTT.html](../FMlogic/Request_TVS_REMOVE_COMPO_OTT.html) |
| BDH_UPDATE_DIRECT_DEBIT_STATUS | 56 | ✓ | [Request_BDH_UPDATE_DIRECT_DEBIT_STATUS.html](../FMlogic/Request_BDH_UPDATE_DIRECT_DEBIT_STATUS.html) |
| CCBS_CANCEL_SUBS | 57 | ✓ NEW | [Request_CCBS_CANCEL_SUBS.html](../FMlogic/Request_CCBS_CANCEL_SUBS.html) |
| CCBS_L9_UPDATE_MNP_ATTRIBUTES | 58 | ✓ NEW | [Request_CCBS_L9_UPDATE_MNP_ATTRIBUTES.html](../FMlogic/Request_CCBS_L9_UPDATE_MNP_ATTRIBUTES.html) |
| CCBS_UPDATE_MNP_REVERSAL_CANCEL | 59 | ✓ NEW | [Request_CCBS_UPDATE_MNP_REVERSAL_CANCEL.html](../FMlogic/Request_CCBS_UPDATE_MNP_REVERSAL_CANCEL.html) |
| CCBS_APPLY_COLL_ACTIVITIES | 60 | ✓ | [Request_CCBS_APPLY_COLL_ACTIVITIES.html](../FMlogic/Request_CCBS_APPLY_COLL_ACTIVITIES.html) |
| ASRM_INVOKE_MSISDN | 61, 62, 63 | ✓ | [Request_ASRM_INVOKE_MSISDN.html](../FMlogic/Request_ASRM_INVOKE_MSISDN.html) |
| ASRM_INVOKE_SIM | 64 | ✓ | [Request_ASRM_INVOKE_SIM.html](../FMlogic/Request_ASRM_INVOKE_SIM.html) |
| ASRM_INVOKE_MINOR_SIM | 65 | ✓ | [Request_ASRM_INVOKE_MINOR_SIM.html](../FMlogic/Request_ASRM_INVOKE_MINOR_SIM.html) |
| CVSS_GET_EXISTING_PRODUCT | 66 | ✓ | [Request_CVSS_GET_EXISTING_PRODUCT.html](../FMlogic/Request_CVSS_GET_EXISTING_PRODUCT.html) |
| CVSS_CANCEL_SUBS | 67 | ✓ | [Request_CVSS_CANCEL_SUBS.html](../FMlogic/Request_CVSS_CANCEL_SUBS.html) |
| STATUS_UPDATE_CREATING_PROFILE | 68 | ✓ | [Request_STATUS_UPDATE_CREATING_PROFILE.html](../FMlogic/Request_STATUS_UPDATE_CREATING_PROFILE.html) |
| CREATE_TDS_PROFILE | 69 | ✓ | [Request_CREATE_TDS_PROFILE.html](../FMlogic/Request_CREATE_TDS_PROFILE.html) |
| PSA_UPDATE_DEVICE | 70 | ✓ | [Request_PSA_UPDATE_DEVICE.html](../FMlogic/Request_PSA_UPDATE_DEVICE.html) |
| TDG_CANCEL_SUBSCRIBER | 71 | ✓ | [Request_TDG_CANCEL_SUBSCRIBER.html](../FMlogic/Request_TDG_CANCEL_SUBSCRIBER.html) |
| CJ_QUERY_STATE | 74 | ✓ | [Request_CJ_QUERY_STATE.html](../FMlogic/Request_CJ_QUERY_STATE.html) |
| SFF_CANCEL_CALL_VERIFY_MOBILE | 75 | ✓ NEW | [Request_SFF_CANCEL_CALL_VERIFY_MOBILE.html](../FMlogic/Request_SFF_CANCEL_CALL_VERIFY_MOBILE.html) |
| ATS_DEBUNDLE_CAMPAIGN | 76 | ✓ | [Request_ATS_DEBUNDLE_CAMPAIGN.html](../FMlogic/Request_ATS_DEBUNDLE_CAMPAIGN.html) |
| OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE | 77 | ✓ | [Request_OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE.html](../FMlogic/Request_OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE.html) |
| SEND_SMS_MESSAGE_3CJ | 78 | ✓ | [Request_SEND_SMS_MESSAGE_3CJ.html](../FMlogic/Request_SEND_SMS_MESSAGE_3CJ.html) |
| APIGW_OPT_IN_OUT | 79 | ✓ | [Request_APIGW_OPT_IN_OUT.html](../FMlogic/Request_APIGW_OPT_IN_OUT.html) |

---

## §5 — Sequence Diagram

> **Omitted** — process has 79 activities (threshold: 60). See [CANCEL_SUBSCRIBER.html](../order/CANCEL_SUBSCRIBER.html) for the full interactive flow table.

---

## §6 — Migration Notes

### Key Decision Points
- **OT=10** (port-out cancel): Triggers CCBS_L9_UPDATE_MNP_ATTRIBUTES (L9PortInd=79), ASRM PORT OUT RELEASE
- **OT=12** (standard cancel): Main flow; CCBS_CANCEL_SUBS, ASRM RELEASE
- **OT=14** (suspension): CCBS_APPLY_COLL_ACTIVITIES gate
- **ActivityReason=MNPHR/RFREOT**: MNP reversal path → CCBS_UPDATE_MNP_REVERSAL_CANCEL (L9PortInd=86)
- **FE_OR_CCBS=ATS**: Parallel ATS data-collection loop (steps 18–23)
- **CANCEL_TYPE=endbill**: ZeroFinalBill path (steps 28–29)

### High-Risk Items
- portOutIndicator 89 vs 78 in CCBS_CANCEL_SUBS (billing)
- L9PortInd 79 vs 86 in MNP updates (MNP record consistency)
- Back-date calculation in CCBS_CANCEL_SUBS with OLD_BAN_DATE guard
- TVS AUDIT_TRACE copy-paste error ("TDG_UPDATE_SERIAL")
- OMX_UPDATE_OFFER_PARAMETER and OMX_CAL_ORDER are internal functions (no rule files)

---

*TRUE Corporation OMX · Order Journey Documentation*
