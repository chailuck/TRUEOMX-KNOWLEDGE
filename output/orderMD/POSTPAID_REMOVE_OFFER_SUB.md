# POSTPAID_REMOVE_OFFER_SUB

> Process Configuration for POSTPAID_REMOVE_OFFER_SUB.

**Total steps:** 74 | **Unique FMs:** 55 | **Entry point:** CCBS_GET_CUST_ACC_SUB_ID | **Not Found FMs:** 4

---

## §2 — Order Flow

| Step | Step ID | FM (ActivityID) | Parameter(s) | PreExecCheck | Previous | Next |
|------|---------|-----------------|--------------|--------------|----------|------|
| 1 | CCBS_GET_CUST_ACC_SUB_ID | CCBS_GET_CUST_ACC_SUB_ID | — | — | START | CCBS_GET_CUSTOMER_HEADER |
| 2 | CCBS_GET_CUSTOMER_HEADER | CCBS_GET_CUSTOMER_HEADER | — | — | CCBS_GET_CUST_ACC_SUB_ID | CCBS_GET_SUBSCRIBER_HEADER |
| 3 | CCBS_GET_SUBSCRIBER_HEADER | CCBS_GET_SUBSCRIBER_HEADER | — | — | CCBS_GET_CUSTOMER_HEADER | CCBS_GET_ACCOUNT_HEADER |
| 4 | CCBS_GET_ACCOUNT_HEADER | CCBS_GET_ACCOUNT_HEADER | — | — | CCBS_GET_SUBSCRIBER_HEADER | CCBS_GET_AGREEMENT_HEADER |
| 5 | CCBS_GET_AGREEMENT_HEADER | CCBS_GET_AGREEMENT_HEADER | — | — | CCBS_GET_ACCOUNT_HEADER | CCBS_GET_SUBS_INFO |
| 6 | CCBS_GET_SUBS_INFO | CCBS_GET_SUBS_INFO | ADD_RELATED=Y | `boolean(//Subscriber[Status !=67 and Status !=76 and Status !=84])` | CCBS_GET_AGREEMENT_HEADER | GET_PROFILE_FROM_CCP_ALL |
| 7 | GET_PROFILE_FROM_CCP_ALL | GET_PROFILE_FROM_CCP_ALL | — | `substring(//Customer/Account/.../AccountSubType/text(),1,2)='HY'` | CCBS_GET_SUBS_INFO | CCBS_RESOLVE_SOC_CODE |
| 8 | CCBS_RESOLVE_SOC_CODE | CCBS_RESOLVE_SOC_CODE | — | `boolean(//SubscriberOffers[not(Soc/text())])` | GET_PROFILE_FROM_CCP_ALL | CCBS_GOD |
| 9 | CCBS_GOD | CCBS_GOD | — | `boolean(//SubscriberOffers[ExtendedInfo[Name='FE_OR_CCBS' and (Value='FE' or Value='BRMS_REMOVE')]])` | CCBS_RESOLVE_SOC_CODE | MVP_CHECK_DEVICES |
| 10 | MVP_CHECK_DEVICES | MVP_CHECK_DEVICES | — | `boolean(//SubscriberOffers[ExtendedInfo[Name='TR_OFFER_GROUP' and (Value='NETH'...)]])` or `...EMP006...` | CCBS_GOD | OMX_BRMS_DB |
| 11 | OMX_BRMS_DB | OMX_BRMS_DB | — | `boolean(//Subscriber/SubscriberOffers[1]...) and not(starts-with(...OrderID,'5G-CHILD'))` | MVP_CHECK_DEVICES | CCBS_RESOLVE_SOC_CODE_BRMS |
| 12 | CCBS_RESOLVE_SOC_CODE_BRMS | CCBS_RESOLVE_SOC_CODE | — | `boolean(//SubscriberOffers[ExtendedInfo[Name='FE_OR_CCBS' and (Value='BRMS_REMOVE' or Value='BRMS_ADD')]])` | OMX_BRMS_DB | OMX_RESOLVE_SOC_DATA |
| 13 | OMX_RESOLVE_SOC_DATA | OMX_RESOLVE_SOC_DATA | — | — | CCBS_RESOLVE_SOC_CODE_BRMS | OMX_CAL_NEXT_BILL_DATE |
| 14 | OMX_CAL_NEXT_BILL_DATE | OMX_CAL_NEXT_BILL_DATE | — | `boolean(//SubscriberOffers[(ServiceType='86' or '87') and DataInfo[PackType='RC'] and ... EffectiveNextBillInd='Y'])` | OMX_RESOLVE_SOC_DATA | OMX_CAL_OFFER_FUT_DATE |
| 15 | OMX_CAL_OFFER_FUT_DATE | OMX_CAL_OFFER_FUT_DATE | — | `boolean(//Subscriber/SubscriberOffers[1] and //SubscriberOffers[ExtendedInfo[Name='FE_OR_CCBS' and (Value='FE' or Value='BRMS_REMOVE')]])` | OMX_CAL_NEXT_BILL_DATE | OMX_EXP_FUT_OFFER |
| 16 | OMX_EXP_FUT_OFFER | OMX_EXP_FUT_OFFER | — | `boolean(//SubscriberOffers[ExtendedInfo[Name='FE_OR_CCBS'...] and ExtendedInfo[Name='EXP_TYPE' and Value='FUT']])` | OMX_CAL_OFFER_FUT_DATE | OMX_OFFER_INCLUSION |
| 17 | OMX_OFFER_INCLUSION | OMX_OFFER_INCLUSION ⚠ | — | `Channel!="EOC" and (not(EXP_TYPE) or EXP_TYPE!='FUT' or LOGICALDATE_PROV)` | OMX_EXP_FUT_OFFER | SBM_VALIDATE |
| 18 | SBM_VALIDATE | SBM_VALIDATE | — | `(not SBM_PROVISIONING or Value!='N') and count(//SubscriberOffers[(ServiceType='86' or '87') and FE_OR_CCBS='FE']) > 0 and ...` | OMX_OFFER_INCLUSION | OMX_BIZ_VAL |
| 19 | OMX_BIZ_VAL | OMX_BIZ_VAL ⚠ | — | `(not(EXP_TYPE) or EXP_TYPE!='FUT' or LOGICALDATE_PROV)` | SBM_VALIDATE | ATS_ENQUIRY_CAMPAIGN |
| 20 | ATS_ENQUIRY_CAMPAIGN | ATS_ENQUIRY_CAMPAIGN | — | `not(Channel ends with '-MF') and Channel not starts with 'FUT'` | OMX_BIZ_VAL | CCBS_GET_CUST_ACC_SUB_ID_ATS |
| 21 | CCBS_GET_CUST_ACC_SUB_ID_ATS | CCBS_GET_CUST_ACC_SUB_ID | SOURCE | `boolean(//Subscriber[ExtendedInfo[Name='FE_OR_CCBS' and Value='ATS']])` | ATS_ENQUIRY_CAMPAIGN | CCBS_GET_ACCOUNT_HEADER_ATS |
| 22 | CCBS_GET_ACCOUNT_HEADER_ATS | CCBS_GET_ACCOUNT_HEADER | — | `boolean(//Subscriber[ExtendedInfo[Name='FE_OR_CCBS' and Value='ATS']])` | CCBS_GET_CUST_ACC_SUB_ID_ATS | CCBS_GET_AGREEMENT_HEADER_ATS |
| 23 | CCBS_GET_AGREEMENT_HEADER_ATS | CCBS_GET_AGREEMENT_HEADER | — | `boolean(//Subscriber[ExtendedInfo[Name='FE_OR_CCBS' and Value='ATS']])` | CCBS_GET_ACCOUNT_HEADER_ATS | CCBS_GET_SUBSCRIBER_HEADER_ATS |
| 24 | CCBS_GET_SUBSCRIBER_HEADER_ATS | CCBS_GET_SUBSCRIBER_HEADER | — | `boolean(//Subscriber[ExtendedInfo[Name='FE_OR_CCBS' and Value='ATS']])` | CCBS_GET_AGREEMENT_HEADER_ATS | CCBS_GET_CUSTOMER_HEADER_ATS |
| 25 | CCBS_GET_CUSTOMER_HEADER_ATS | CCBS_GET_CUSTOMER_HEADER | — | `boolean(//Subscriber[ExtendedInfo[Name='FE_OR_CCBS' and Value='ATS']])` | CCBS_GET_SUBSCRIBER_HEADER_ATS | CCBS_GET_SUBS_INFO_ATS |
| 26 | CCBS_GET_SUBS_INFO_ATS | CCBS_GET_SUBS_INFO | — | `boolean(//Subscriber[ExtendedInfo[Name='FE_OR_CCBS' and Value='ATS']])` | CCBS_GET_CUSTOMER_HEADER_ATS | CCBS_GOD_ATS |
| 27 | CCBS_GOD_ATS | CCBS_GOD | — | `boolean(//Subscriber[ExtendedInfo[Name='FE_OR_CCBS' and Value='ATS']])` | CCBS_GET_SUBS_INFO_ATS | OMX_GET_OFFER_RATE |
| 28 | OMX_GET_OFFER_RATE | OMX_GET_OFFER_RATE | — | `boolean(//SubscriberOffers[FE_OR_CCBS in ('FE','CCBS') and ServiceType='80'] and CampaignCode exists)` | CCBS_GOD_ATS | ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN |
| 29 | ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN | ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN | — | `count(//BundleInfo[ConvergenceType='MobileSoftBundle'])>0` | OMX_GET_OFFER_RATE | CCBS_RESOLVE_SOC_CODE_ATS |
| 30 | CCBS_RESOLVE_SOC_CODE_ATS | CCBS_RESOLVE_SOC_CODE | — | `boolean(//Subscriber[ExtendedInfo[Name='FE_OR_CCBS' and Value='ATS']])` | ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN | OMX_RESOLVE_SOC_DATA_ATS |
| 31 | OMX_RESOLVE_SOC_DATA_ATS | OMX_RESOLVE_SOC_DATA | — | `boolean(//Subscriber[ExtendedInfo[Name='FE_OR_CCBS' and Value='ATS']])` | CCBS_RESOLVE_SOC_CODE_ATS | GET_SPECIAL_OFFER_INDICATOR |
| 32 | GET_SPECIAL_OFFER_INDICATOR | GET_SPECIAL_OFFER_INDICATOR | ADD_PROP=TR_MULTISIM_IND | `(not EXP_TYPE or EXP_TYPE!='FUT' or LOGICALDATE_PROV) and non-ATS subscribers` | OMX_RESOLVE_SOC_DATA_ATS | INTX_GET_MASTER_MINOR_SIM_INFO |
| 33 | INTX_GET_MASTER_MINOR_SIM_INFO | INTX_GET_MASTER_MINOR_SIM_INFO | — | `count(//SubscriberOffers[TR_MULTISIM_IND in ('RCM','RES','RCE','REE')]) > 0 and non-ATS subscribers` | GET_SPECIAL_OFFER_INDICATOR | INTX_GET_SIM_INFO_BY_SIM |
| 34 | INTX_GET_SIM_INFO_BY_SIM | INTX_GET_SIM_INFO_BY_SIM | — | `count(//Subscriber/ExtendedInfo[Name='MSIM_TO_CANCEL']) > 0 and non-ATS subscribers` | INTX_GET_MASTER_MINOR_SIM_INFO | ASRM_INVOKE_MINOR_SIM_RELEASE |
| 35 | ASRM_INVOKE_MINOR_SIM_RELEASE | ASRM_INVOKE_MINOR_SIM | ACTIVITY=RELEASE | `count(//SubscriberOffers[TR_MULTISIM_IND in ('RCM','RES') and FE_OR_CCBS in ('FE','BRMS_REMOVE')]) > 0 and non-ATS` | INTX_GET_SIM_INFO_BY_SIM | AA_GET_SWITCH_FEATURE_OFFER |
| 36 | AA_GET_SWITCH_FEATURE_OFFER | AA_GET_SWITCH_FEATURE_OFFER | — | `(not EXP_TYPE or EXP_TYPE!='FUT' or LOGICALDATE_PROV) and non-ATS subscribers` | ASRM_INVOKE_MINOR_SIM_RELEASE | SBM_FUP_CHANGE_CAP_MAX |
| 37 | SBM_FUP_CHANGE_CAP_MAX | SBM_FUP_CHANGE_CAP_MAX | REMOVE | `FE_OR_CCBS in (FE,BRMS_REMOVE) and SPECIAL_OFFER_INDICATOR='FCA' and not EXP_TYPE FUT and non-ATS` | AA_GET_SWITCH_FEATURE_OFFER | OMX_CREATE_SUB_OFFER_BAR_SOC |
| 38 | OMX_CREATE_SUB_OFFER_BAR_SOC | OMX_CREATE_SUB_OFFER_BAR_SOC | — | `FE_OR_CCBS='CCBS' and ServiceType='85' and not EXP_TYPE FUT and non-ATS subscribers` | SBM_FUP_CHANGE_CAP_MAX | CCBS_MSIM_CANCEL_SIM |
| 39 | CCBS_MSIM_CANCEL_SIM | CCBS_MSIM_CANCEL_SIM | — | `MSIM_TO_CANCEL exists and TR_MULTISIM_IND='RCM' and FE_OR_CCBS in (FE,BRMS_REMOVE) and non-ATS` | OMX_CREATE_SUB_OFFER_BAR_SOC | SBM_CANCEL_PACK_PREPAID |
| 40 | SBM_CANCEL_PACK_PREPAID | SBM_CANCEL_PACK_PREPAID | — | `FE_OR_CCBS='BRMS_REMOVE' and ServiceType='88' and not EXP_TYPE FUT and non-ATS subscribers` | CCBS_MSIM_CANCEL_SIM | CCBS_CHANGE_PACKAGE_SUBSCRIBER_REMOVE |
| 41 | CCBS_CHANGE_PACKAGE_SUBSCRIBER_REMOVE | CCBS_CHANGE_PACKAGE_SUBSCRIBER | REMOVE | `(FE/BRMS_REMOVE/DMC_REMOVE and ServiceType in (85,86,87,68) and no MSIM RCM/RES) or ATS_REMOVE or IOTBU` | SBM_CANCEL_PACK_PREPAID | MCS_CANCEL_SUBSCRIPTION |
| 42 | MCS_CANCEL_SUBSCRIPTION | MCS_CANCEL_SUBSCRIPTION | — | `FE_OR_CCBS in ('BRMS_REMOVE','FE') and ServiceType='69'` | CCBS_CHANGE_PACKAGE_SUBSCRIBER_REMOVE | SBM_VALIDATE_ATS |
| 43 | SBM_VALIDATE_ATS | SBM_VALIDATE | — | `ServiceType='86' and FE_OR_CCBS='ATS_REMOVE'` | MCS_CANCEL_SUBSCRIPTION | OMX_REMOVE_NXTOFR_FROM_PREV_SOC |
| 44 | OMX_REMOVE_NXTOFR_FROM_PREV_SOC | OMX_REMOVE_NXTOFR_FROM_PREV_SOC | — | `FE/BRMS_REMOVE and ServiceType in (85,86,87,68) and not EXP_TYPE FUT and non-ATS` | SBM_VALIDATE_ATS | SBM_CANCEL_DATA_PACK_IMMEDIATE |
| 45 | SBM_CANCEL_DATA_PACK_IMMEDIATE | SBM_CANCEL_DATA_PACK_IMMEDIATE | — | `(not SBM_PROVISIONING or Value!='N') and ServiceType in(86,87) and PackType='RC' and FE/BRMS_REMOVE) or ATS_REMOVE` | OMX_REMOVE_NXTOFR_FROM_PREV_SOC | SBM_UPDATE_EXPIRED |
| 46 | SBM_UPDATE_EXPIRED | SBM_UPDATE_EXPIRED | — | `(not SBM_PROVISIONING or Value!='N') and ServiceType in(86,87) and PackType='OC' and FE/BRMS_REMOVE) or ATS_REMOVE` | SBM_CANCEL_DATA_PACK_IMMEDIATE | SBM_BUY_DATA_PACK |
| 47 | SBM_BUY_DATA_PACK | SBM_BUY_DATA_PACK | — | `ServiceType='86' and FE_OR_CCBS='ATS'` | SBM_UPDATE_EXPIRED | BL_CREATE_CHARGE |
| 48 | BL_CREATE_CHARGE | BL_CREATE_CHARGE | — | `ServiceType='79' and FE_OR_CCBS='ATS'` | SBM_BUY_DATA_PACK | CCBS_CHANGE_PACKAGE_SUBSCRIBER |
| 49 | CCBS_CHANGE_PACKAGE_SUBSCRIBER | CCBS_CHANGE_PACKAGE_SUBSCRIBER | ADD | `ServiceType in (85,86,68) and FE_OR_CCBS in ('ATS','BRMS_ADD')` | BL_CREATE_CHARGE | UPDATE_NETWORK_STATUS |
| 50 | UPDATE_NETWORK_STATUS | UPDATE_NETWORK_STATUS ⚠ | — | `(not SBM_PROVISIONING or Value!='N') and ServiceType in(86,87) and FE/BRMS_REMOVE and not EXP_TYPE FUT and non-ATS` | CCBS_CHANGE_PACKAGE_SUBSCRIBER | STATUS_UPDATE_CREATING_PROFILE |
| 51 | STATUS_UPDATE_CREATING_PROFILE | STATUS_UPDATE_CREATING_PROFILE ⚠ | — | `(not EXP_TYPE or EXP_TYPE!='FUT' or LOGICALDATE_PROV) and non-ATS subscribers` | UPDATE_NETWORK_STATUS | OMX_POPULATE_MSIM_INFO |
| 52 | OMX_POPULATE_MSIM_INFO | OMX_POPULATE_MSIM_INFO | — | `FE_OR_CCBS='FE' and TR_MULTISIM_IND in ('RES','RCM') and non-ATS subscribers` | STATUS_UPDATE_CREATING_PROFILE | OMX_GET_SRV_TRX_NO |
| 53 | OMX_GET_SRV_TRX_NO | OMX_GET_SRV_TRX_NO | CCD | `not MSIM Minor[Source=FE] and not PREV_MSIM and PROVISIONING!='N' and SwitchFeature exists and not EXP_TYPE FUT and non-ATS` | OMX_POPULATE_MSIM_INFO | AA_ACTIVATE_SUBS |
| 54 | AA_ACTIVATE_SUBS | AA_ACTIVATE_SUBS | CCD | `(same as step 53 — not MSIM FE, not PREV_MSIM, PROVISIONING!='N', SwitchFeature, not EXP_TYPE FUT, non-ATS)` | OMX_GET_SRV_TRX_NO | OMX_GET_SRV_TRX_NO_MSIM_REMOVE |
| 55 | OMX_GET_SRV_TRX_NO_MSIM_REMOVE | OMX_GET_SRV_TRX_NO_MSIM | CCD | `MSIM Minor[Source=FE] and PROVISIONING!='N' and not EXP_TYPE FUT and non-ATS subscribers` | AA_ACTIVATE_SUBS | AA_ACTIVATE_SUBS_MSIM_REMOVE |
| 56 | AA_ACTIVATE_SUBS_MSIM_REMOVE | AA_ACTIVATE_SUBS_MSIM | CCD, REMOVE | `MSIM Minor[Source=FE] and PROVISIONING!='N' and not EXP_TYPE FUT and non-ATS subscribers` | OMX_GET_SRV_TRX_NO_MSIM_REMOVE | OMX_GET_SRV_TRX_NO_MSIM_UPDATE |
| 57 | OMX_GET_SRV_TRX_NO_MSIM_UPDATE | OMX_GET_SRV_TRX_NO_MSIM | CCD | `PREV_MSIM exists and no FE TR_MULTISIM_IND RES/RCM and PROVISIONING!='N' and SwitchFeature and not EFF_TYPE FUT and non-ATS` | AA_ACTIVATE_SUBS_MSIM_REMOVE | AA_ACTIVATE_SUBS_MSIM_UPDATE |
| 58 | AA_ACTIVATE_SUBS_MSIM_UPDATE | AA_ACTIVATE_SUBS_MSIM | CCD, UPDATE | `(same as step 57)` | OMX_GET_SRV_TRX_NO_MSIM_UPDATE | AA_CHECK_CONFIRMATION |
| 59 | AA_CHECK_CONFIRMATION | AA_CHECK_CONFIRMATION | CCD, UPDATE_NETWORK_STATUS | `MultiSIMInfo exists or (PROVISIONING!='N' and SwitchFeature and not EXP_TYPE FUT and non-ATS)` | AA_ACTIVATE_SUBS_MSIM_UPDATE | PSA_GET_DEVICE_INFO |
| 60 | PSA_GET_DEVICE_INFO | PSA_GET_DEVICE_INFO | — | `FE_OR_CCBS='FE' and IMEI_KNOX not empty and non-ATS subscribers` | AA_CHECK_CONFIRMATION | OMX_NOTIFY_KNOX_EVENT_COMPLETE |
| 61 | OMX_NOTIFY_KNOX_EVENT_COMPLETE | OMX_NOTI_TO_KAFKA | knoxEvent=COMPLETE | `FE_OR_CCBS='FE' and IMEI_KNOX not empty and non-ATS subscribers` | PSA_GET_DEVICE_INFO | PSA_UPDATE_KNOX_STATUS |
| 62 | PSA_UPDATE_KNOX_STATUS | PSA_UPDATE_KNOX_STATUS | KNOX_STATUS=COMPLETE | `FE_OR_CCBS='FE' and IMEI_KNOX not empty and non-ATS subscribers` | OMX_NOTIFY_KNOX_EVENT_COMPLETE | CCBS_GOD_ALL |
| 63 | CCBS_GOD_ALL | CCBS_GOD | — | `FE_OR_CCBS='FE' and ServiceType='85' and non-ATS subscribers` | PSA_UPDATE_KNOX_STATUS | CREATE_TDS_PROFILE |
| 64 | CREATE_TDS_PROFILE | CREATE_TDS_PROFILE | — | `FE_OR_CCBS in (FE,BRMS_REMOVE) and ServiceType='85' and non-ATS subscribers` | CCBS_GOD_ALL | CRM_CREATE_CLOSE_SR_MOBILE |
| 65 | CRM_CREATE_CLOSE_SR_MOBILE | CRM_CREATE_CLOSE_SR_MOBILE | PRODUCT_TYPE=Postpay | `SR_ISSUE exists and SR_RESOLUTION exists and SR_SUBCATEGORY exists` | CREATE_TDS_PROFILE | PSA_UPDATE_DEVICE |
| 66 | PSA_UPDATE_DEVICE | PSA_UPDATE_DEVICE | srType=CANCEL, deviceStatus=COMPLETE | `FE_OR_CCBS='FE' and TR_SPECIAL_OFFER_IND=IOTBU and Channel!='FUT'` | CRM_CREATE_CLOSE_SR_MOBILE | TDG_CANCEL_SUBSCRIBER |
| 67 | TDG_CANCEL_SUBSCRIBER | TDG_CANCEL_SUBSCRIBER | — | `FE_OR_CCBS='FE' and TR_SPECIAL_OFFER_IND=IOTBU and Channel!='FUT'` | PSA_UPDATE_DEVICE | MCS_GET_PACKCODE |
| 68 | MCS_GET_PACKCODE | MCS_GET_PACKCODE | — | — | TDG_CANCEL_SUBSCRIBER | MCS_CANCEL_AFTER_SALE |
| 69 | MCS_CANCEL_AFTER_SALE | MCS_CANCEL_AFTER_SALE | — | `boolean(//Subscriber[ExtendedInfo[Name='MCS_CANCEL_AFS' and Value='Y']])` | MCS_GET_PACKCODE | SMSGATEWAY_SEND_SMS |
| 70 | SMSGATEWAY_SEND_SMS | SMSGATEWAY_SEND_SMS | — | `Subscriber has MSISDN and Channel not CCBS/OMX and non-ATS subscribers` | MCS_CANCEL_AFTER_SALE | ATS_DEBUNDLE_CAMPAIGN |
| 71 | ATS_DEBUNDLE_CAMPAIGN | ATS_DEBUNDLE_CAMPAIGN | — | `count(//BundleInfo[ConvergenceAction='DebundleCampaign'] or 'DebundleProductNumber')>0` | SMSGATEWAY_SEND_SMS | OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE |
| 72 | OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE | OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE | — | `count(//BundleInfo[ConvergenceAction='DebundleCampaign'])>0 or count(DebundleProductNumber)>0` | ATS_DEBUNDLE_CAMPAIGN | SEND_SMS_MESSAGE_3CJ |
| 73 | SEND_SMS_MESSAGE_3CJ | SEND_SMS_MESSAGE_3CJ | — | `count(//BundleInfo[ConvergenceAction='DebundleCampaign'])>0 or count(DebundleProductNumber)>0` | OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE | APIGW_OPT_IN_OUT |
| 74 | APIGW_OPT_IN_OUT | APIGW_OPT_IN_OUT | ACTION=0 | `FE_OR_CCBS='FE' and SocProperties contains TR_OFFER_GROUP=CBSC` | SEND_SMS_MESSAGE_3CJ | END |

⚠ = FM rule file not found (internal OMX function, not a TIBCO BE rule)

---

## §3 — PreExecCheck Details

### Step 6 — CCBS_GET_SUBS_INFO

**FM:** `CCBS_GET_SUBS_INFO`

```xpath
boolean(//Subscriber[Status !=67 and Status !=76 and Status !=84])
```

---

### Step 7 — GET_PROFILE_FROM_CCP_ALL

**FM:** `GET_PROFILE_FROM_CCP_ALL`

```xpath
substring(//Customer/Account/AccountManagementInfo/AccountSubType/text(),1,2)='HY'
```

---

### Step 8 — CCBS_RESOLVE_SOC_CODE

**FM:** `CCBS_RESOLVE_SOC_CODE`

```xpath
boolean(//SubscriberOffers[not(Soc/text())])
```

---

### Step 9 — CCBS_GOD

**FM:** `CCBS_GOD`

```xpath
boolean(//SubscriberOffers[ExtendedInfo[Name='FE_OR_CCBS' and (Value='FE' or Value='BRMS_REMOVE')]])
```

---

### Step 10 — MVP_CHECK_DEVICES

**FM:** `MVP_CHECK_DEVICES`

```xpath
boolean(//SubscriberOffers[ExtendedInfo[Name='TR_OFFER_GROUP' and (Value='NETH' or Value='SMRH' or Value='RETH' or Value='RSMH' or Value='REDH')]])
or boolean(//SubscriberOffers[ExtendedInfo[Name='FE_OR_CCBS' and Value='FE'] and (OfferName='DGT024' or OfferName = 'EMP006')])
```

---

### Step 11 — OMX_BRMS_DB

**FM:** `OMX_BRMS_DB`

```xpath
boolean(//Subscriber/SubscriberOffers[1] and //SubscriberOffers[ExtendedInfo[Name='FE_OR_CCBS' and Value='FE']])
and not(starts-with(/ns0:OrderRequest/OrderData/OrderID,"5G-CHILD"))
```

---

### Step 12 — CCBS_RESOLVE_SOC_CODE_BRMS

**FM:** `CCBS_RESOLVE_SOC_CODE`

```xpath
boolean(//SubscriberOffers[ExtendedInfo[Name='FE_OR_CCBS' and (Value='BRMS_REMOVE' or Value='BRMS_ADD')]])
```

---

### Step 14 — OMX_CAL_NEXT_BILL_DATE

**FM:** `OMX_CAL_NEXT_BILL_DATE`

```xpath
boolean(//SubscriberOffers[(ServiceType='86' or ServiceType='87') and DataInfo[PackType='RC']
  and ExtendedInfo[Name='FE_OR_CCBS' and (Value='FE' or Value='BRMS_REMOVE')]
  and EffectiveNextBillInd='Y'])
```

---

### Step 15 — OMX_CAL_OFFER_FUT_DATE

**FM:** `OMX_CAL_OFFER_FUT_DATE`

```xpath
boolean(//Subscriber/SubscriberOffers[1]
  and //SubscriberOffers[ExtendedInfo[Name='FE_OR_CCBS' and (Value='FE' or Value='BRMS_REMOVE')]])
```

---

### Step 16 — OMX_EXP_FUT_OFFER

**FM:** `OMX_EXP_FUT_OFFER`

```xpath
boolean(//Subscriber/SubscriberOffers[1]
  and //SubscriberOffers[ExtendedInfo[Name='FE_OR_CCBS' and (Value='FE' or Value='BRMS_REMOVE')]
    and ExtendedInfo[Name='EXP_TYPE' and Value='FUT']])
```

---

### Step 17 — OMX_OFFER_INCLUSION ⚠ Not Found

**FM:** `OMX_OFFER_INCLUSION`

```xpath
/ns0:OrderRequest/OrderData/Channel/text()!="EOC"
and ((not(boolean(//SubscriberOffers[ExtendedInfo[Name='EXP_TYPE']]))
  or boolean(//SubscriberOffers[ExtendedInfo[Name='EXP_TYPE' and Value!='FUT']]))
  or boolean(//SubscriberOffers[ExtendedInfo[Name='LOGICALDATE_PROV']]))
```

---

### Step 18 — SBM_VALIDATE

**FM:** `SBM_VALIDATE`

```xpath
(not(boolean(/ns0:OrderRequest/OrderData[ExtendedInfo[Name='SBM_PROVISIONING']]))
  or boolean(/ns0:OrderRequest/OrderData[ExtendedInfo[Name='SBM_PROVISIONING' and Value!='N']]))
and (count(//SubscriberOffers[(ServiceType='86' or ServiceType='87')
  and ExtendedInfo[Name='FE_OR_CCBS' and Value='FE']]) > 0)
and ((not(boolean(//SubscriberOffers[ExtendedInfo[Name='EXP_TYPE']]))
  or boolean(//SubscriberOffers[ExtendedInfo[Name='EXP_TYPE' and Value!='FUT']]))
  or boolean(//SubscriberOffers[ExtendedInfo[Name='LOGICALDATE_PROV']]))
```

---

### Step 20 — ATS_ENQUIRY_CAMPAIGN

**FM:** `ATS_ENQUIRY_CAMPAIGN`

```xpath
not(substring(//OrderData/Channel/text(),string-length(//OrderData/Channel/text())-2)='-MF')
and substring(/ns0:OrderRequest/OrderData/Channel/text(),1,3)!='FUT'
```

---

### Step 29 — ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN

**FM:** `ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN`

```xpath
count(//BundleInfo[ConvergenceType='MobileSoftBundle'])>0
```

---

### Step 65 — CRM_CREATE_CLOSE_SR_MOBILE

**FM:** `CRM_CREATE_CLOSE_SR_MOBILE`

```xpath
exists(//OrderData/ExtendedInfo[Name="SR_ISSUE" and Value!=''])
and exists(//OrderData/ExtendedInfo[Name="SR_RESOLUTION" and Value!=''])
and exists(//OrderData/ExtendedInfo[Name="SR_SUBCATEGORY" and Value!=''])
```

---

### Step 71 — ATS_DEBUNDLE_CAMPAIGN

**FM:** `ATS_DEBUNDLE_CAMPAIGN`

```xpath
count(//BundleInfo[ConvergenceAction='DebundleCampaign'] or //BundleInfo[ConvergenceAction='DebundleProductNumber'])>0
```

---

### Steps 72–73 — OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE / SEND_SMS_MESSAGE_3CJ

**FM:** `OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE` / `SEND_SMS_MESSAGE_3CJ`

```xpath
(count(//BundleInfo[ConvergenceAction='DebundleCampaign'])>0
  or count(//BundleInfo[ConvergenceAction='DebundleProductNumber'])>0)
```

---

### Step 74 — APIGW_OPT_IN_OUT

**FM:** `APIGW_OPT_IN_OUT`

```xpath
boolean(//SubscriberOffers[ExtendedInfo[Name='FE_OR_CCBS' and Value='FE']
  and contains(SocProperties,'TR_OFFER_GROUP=CBSC')])
```

---

## §4 — FM Documentation Index

| FM (ActivityID) | Used in Steps | Doc Link |
|-----------------|---------------|----------|
| CCBS_GET_CUST_ACC_SUB_ID | 1, 21 | [Request_CCBS_GET_CUST_ACC_SUB_ID.html](../FMlogic/Request_CCBS_GET_CUST_ACC_SUB_ID.html) |
| CCBS_GET_CUSTOMER_HEADER | 2, 25 | [Request_CCBS_GET_CUSTOMER_HEADER.html](../FMlogic/Request_CCBS_GET_CUSTOMER_HEADER.html) |
| CCBS_GET_SUBSCRIBER_HEADER | 3, 24 | [Request_CCBS_GET_SUBSCRIBER_HEADER.html](../FMlogic/Request_CCBS_GET_SUBSCRIBER_HEADER.html) |
| CCBS_GET_ACCOUNT_HEADER | 4, 22 | [Request_CCBS_GET_ACCOUNT_HEADER.html](../FMlogic/Request_CCBS_GET_ACCOUNT_HEADER.html) |
| CCBS_GET_AGREEMENT_HEADER | 5, 23 | [Request_CCBS_GET_AGREEMENT_HEADER.html](../FMlogic/Request_CCBS_GET_AGREEMENT_HEADER.html) |
| CCBS_GET_SUBS_INFO | 6, 26 | [Request_CCBS_GET_SUBS_INFO.html](../FMlogic/Request_CCBS_GET_SUBS_INFO.html) |
| GET_PROFILE_FROM_CCP_ALL | 7 | [Request_GET_PROFILE_FROM_CCP_ALL.html](../FMlogic/Request_GET_PROFILE_FROM_CCP_ALL.html) |
| CCBS_RESOLVE_SOC_CODE | 8, 12, 30 | [Request_CCBS_RESOLVE_SOC_CODE.html](../FMlogic/Request_CCBS_RESOLVE_SOC_CODE.html) |
| CCBS_GOD | 9, 27, 63 | [Request_CCBS_GOD.html](../FMlogic/Request_CCBS_GOD.html) |
| MVP_CHECK_DEVICES | 10 | [Request_MVP_CHECK_DEVICES.html](../FMlogic/Request_MVP_CHECK_DEVICES.html) |
| OMX_BRMS_DB | 11 | [Request_OMX_BRMS_DB.html](../FMlogic/Request_OMX_BRMS_DB.html) |
| OMX_RESOLVE_SOC_DATA | 13, 31 | [Request_OMX_RESOLVE_SOC_DATA.html](../FMlogic/Request_OMX_RESOLVE_SOC_DATA.html) |
| OMX_CAL_NEXT_BILL_DATE | 14 | [Request_OMX_CAL_NEXT_BILL_DATE.html](../FMlogic/Request_OMX_CAL_NEXT_BILL_DATE.html) |
| OMX_CAL_OFFER_FUT_DATE | 15 | [Request_OMX_CAL_OFFER_FUT_DATE.html](../FMlogic/Request_OMX_CAL_OFFER_FUT_DATE.html) |
| OMX_EXP_FUT_OFFER | 16 | [Request_OMX_EXP_FUT_OFFER.html](../FMlogic/Request_OMX_EXP_FUT_OFFER.html) |
| OMX_OFFER_INCLUSION | 17 | ⚠ Not Found |
| SBM_VALIDATE | 18, 43 | [Request_SBM_VALIDATE.html](../FMlogic/Request_SBM_VALIDATE.html) |
| OMX_BIZ_VAL | 19 | ⚠ Not Found |
| ATS_ENQUIRY_CAMPAIGN | 20 | [Request_ATS_ENQUIRY_CAMPAIGN.html](../FMlogic/Request_ATS_ENQUIRY_CAMPAIGN.html) |
| OMX_GET_OFFER_RATE | 28 | [Request_OMX_GET_OFFER_RATE.html](../FMlogic/Request_OMX_GET_OFFER_RATE.html) |
| ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN | 29 | [Request_ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN.html](../FMlogic/Request_ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN.html) |
| GET_SPECIAL_OFFER_INDICATOR | 32 | [Request_GET_SPECIAL_OFFER_INDICATOR.html](../FMlogic/Request_GET_SPECIAL_OFFER_INDICATOR.html) |
| INTX_GET_MASTER_MINOR_SIM_INFO | 33 | [Request_INTX_GET_MASTER_MINOR_SIM_INFO.html](../FMlogic/Request_INTX_GET_MASTER_MINOR_SIM_INFO.html) |
| INTX_GET_SIM_INFO_BY_SIM | 34 | [Request_INTX_GET_SIM_INFO_BY_SIM.html](../FMlogic/Request_INTX_GET_SIM_INFO_BY_SIM.html) |
| ASRM_INVOKE_MINOR_SIM | 35 | [Request_ASRM_INVOKE_MINOR_SIM.html](../FMlogic/Request_ASRM_INVOKE_MINOR_SIM.html) |
| AA_GET_SWITCH_FEATURE_OFFER | 36 | [Request_AA_GET_SWITCH_FEATURE_OFFER.html](../FMlogic/Request_AA_GET_SWITCH_FEATURE_OFFER.html) |
| SBM_FUP_CHANGE_CAP_MAX | 37 | [Request_SBM_FUP_CHANGE_CAP_MAX.html](../FMlogic/Request_SBM_FUP_CHANGE_CAP_MAX.html) |
| OMX_CREATE_SUB_OFFER_BAR_SOC | 38 | [Request_OMX_CREATE_SUB_OFFER_BAR_SOC.html](../FMlogic/Request_OMX_CREATE_SUB_OFFER_BAR_SOC.html) |
| CCBS_MSIM_CANCEL_SIM | 39 | [Request_CCBS_MSIM_CANCEL_SIM.html](../FMlogic/Request_CCBS_MSIM_CANCEL_SIM.html) |
| SBM_CANCEL_PACK_PREPAID | 40 | [Request_SBM_CANCEL_PACK_PREPAID.html](../FMlogic/Request_SBM_CANCEL_PACK_PREPAID.html) |
| CCBS_CHANGE_PACKAGE_SUBSCRIBER | 41, 49 | [Request_CCBS_CHANGE_PACKAGE_SUBSCRIBER.html](../FMlogic/Request_CCBS_CHANGE_PACKAGE_SUBSCRIBER.html) |
| MCS_CANCEL_SUBSCRIPTION | 42 | [Request_MCS_CANCEL_SUBSCRIPTION.html](../FMlogic/Request_MCS_CANCEL_SUBSCRIPTION.html) |
| OMX_REMOVE_NXTOFR_FROM_PREV_SOC | 44 | [Request_OMX_REMOVE_NXTOFR_FROM_PREV_SOC.html](../FMlogic/Request_OMX_REMOVE_NXTOFR_FROM_PREV_SOC.html) |
| SBM_CANCEL_DATA_PACK_IMMEDIATE | 45 | [Request_SBM_CANCEL_DATA_PACK_IMMEDIATE.html](../FMlogic/Request_SBM_CANCEL_DATA_PACK_IMMEDIATE.html) |
| SBM_UPDATE_EXPIRED | 46 | [Request_SBM_UPDATE_EXPIRED.html](../FMlogic/Request_SBM_UPDATE_EXPIRED.html) |
| SBM_BUY_DATA_PACK | 47 | [Request_SBM_BUY_DATA_PACK.html](../FMlogic/Request_SBM_BUY_DATA_PACK.html) |
| BL_CREATE_CHARGE | 48 | [Request_BL_CREATE_CHARGE.html](../FMlogic/Request_BL_CREATE_CHARGE.html) |
| UPDATE_NETWORK_STATUS | 50 | ⚠ Not Found |
| STATUS_UPDATE_CREATING_PROFILE | 51 | ⚠ Not Found |
| OMX_POPULATE_MSIM_INFO | 52 | [Request_OMX_POPULATE_MSIM_INFO.html](../FMlogic/Request_OMX_POPULATE_MSIM_INFO.html) |
| OMX_GET_SRV_TRX_NO | 53 | [Request_OMX_GET_SRV_TRX_NO.html](../FMlogic/Request_OMX_GET_SRV_TRX_NO.html) |
| AA_ACTIVATE_SUBS | 54 | [Request_AA_ACTIVATE_SUBS.html](../FMlogic/Request_AA_ACTIVATE_SUBS.html) |
| OMX_GET_SRV_TRX_NO_MSIM | 55, 57 | [Request_OMX_GET_SRV_TRX_NO_MSIM.html](../FMlogic/Request_OMX_GET_SRV_TRX_NO_MSIM.html) |
| AA_ACTIVATE_SUBS_MSIM | 56, 58 | [Request_AA_ACTIVATE_SUBS_MSIM.html](../FMlogic/Request_AA_ACTIVATE_SUBS_MSIM.html) |
| AA_CHECK_CONFIRMATION | 59 | [Request_AA_CHECK_CONFIRMATION.html](../FMlogic/Request_AA_CHECK_CONFIRMATION.html) |
| PSA_GET_DEVICE_INFO | 60 | [Request_PSA_GET_DEVICE_INFO.html](../FMlogic/Request_PSA_GET_DEVICE_INFO.html) |
| OMX_NOTI_TO_KAFKA | 61 | [Request_OMX_NOTI_TO_KAFKA.html](../FMlogic/Request_OMX_NOTI_TO_KAFKA.html) |
| PSA_UPDATE_KNOX_STATUS | 62 | [Request_PSA_UPDATE_KNOX_STATUS.html](../FMlogic/Request_PSA_UPDATE_KNOX_STATUS.html) |
| CREATE_TDS_PROFILE | 64 | [Request_CREATE_TDS_PROFILE.html](../FMlogic/Request_CREATE_TDS_PROFILE.html) |
| CRM_CREATE_CLOSE_SR_MOBILE | 65 | [Request_CRM_CREATE_CLOSE_SR_MOBILE.html](../FMlogic/Request_CRM_CREATE_CLOSE_SR_MOBILE.html) |
| PSA_UPDATE_DEVICE | 66 | [Request_PSA_UPDATE_DEVICE.html](../FMlogic/Request_PSA_UPDATE_DEVICE.html) |
| TDG_CANCEL_SUBSCRIBER | 67 | [Request_TDG_CANCEL_SUBSCRIBER.html](../FMlogic/Request_TDG_CANCEL_SUBSCRIBER.html) |
| MCS_GET_PACKCODE | 68 | [Request_MCS_GET_PACKCODE.html](../FMlogic/Request_MCS_GET_PACKCODE.html) |
| MCS_CANCEL_AFTER_SALE | 69 | [Request_MCS_CANCEL_AFTER_SALE.html](../FMlogic/Request_MCS_CANCEL_AFTER_SALE.html) |
| SMSGATEWAY_SEND_SMS | 70 | [Request_SMSGATEWAY_SEND_SMS.html](../FMlogic/Request_SMSGATEWAY_SEND_SMS.html) |
| ATS_DEBUNDLE_CAMPAIGN | 71 | [Request_ATS_DEBUNDLE_CAMPAIGN.html](../FMlogic/Request_ATS_DEBUNDLE_CAMPAIGN.html) |
| OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE | 72 | [Request_OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE.html](../FMlogic/Request_OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE.html) |
| SEND_SMS_MESSAGE_3CJ | 73 | [Request_SEND_SMS_MESSAGE_3CJ.html](../FMlogic/Request_SEND_SMS_MESSAGE_3CJ.html) |
| APIGW_OPT_IN_OUT | 74 | [Request_APIGW_OPT_IN_OUT.html](../FMlogic/Request_APIGW_OPT_IN_OUT.html) |

---

## §5 — Sequence Diagram

> Sequence diagram omitted — 74 activities exceeds the 60-step readability limit. See the §2 Order Flow Table for the complete activity chain, and the companion HTML at `output/order/POSTPAID_REMOVE_OFFER_SUB.html`.

---

## §6 — Flow Diagram

> Flow diagram omitted — 74 activities exceeds the 40-step readability limit. See the §2 Order Flow Table for the complete activity chain.

---

*TRUE Corporation OMX · Order Journey Documentation*
