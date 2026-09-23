# ACTIVATION

> Process Configuration for ACTIVATION — New subscriber activation flow with CCBS, ASRM, NAS, SBM, CRM, and notification integrations.

**Total steps:** 124 | **Unique FMs:** 103 | **Entry point:** BLACKLIST_CHECK_BLACKLIST | **Generated:** 2026-09-22

---

## §2 — Order Flow

| Step | Step ID | FM (ActivityID) | Parameter(s) | PreExecCheck | Previous | Next |
|------|---------|-----------------|--------------|--------------|----------|------|
| 1 | BLACKLIST_CHECK_BLACKLIST | BLACKLIST_CHECK_BLACKLIST | — | `not(substring(//OrderData/Channel,string-length-2)='-MF')` | START | BLACKLIST_CHECK_FRAUD |
| 2 | BLACKLIST_CHECK_FRAUD | BLACKLIST_CHECK_FRAUD | — | — | BLACKLIST_CHECK_BLACKLIST | OMX_POPULATE_OFFER_ADD_ESIM |
| 3 | OMX_POPULATE_OFFER_ADD_ESIM | OMX_POPULATE_OFFER | OFFER=soc=13513126,action=ADD,offerName=RSESIM01 | `string-length(PEID)>0 and string-length(PMATCHID)>0` | BLACKLIST_CHECK_FRAUD | OMX_POPULATE_OFFER_PROMOEND |
| 4 | OMX_POPULATE_OFFER_PROMOEND | OMX_POPULATE_OFFER | OFFER=soc=25427629,offerName=RMVX00000000001 | `//Customer/CustomerTypeInfo/Type=73` | OMX_POPULATE_OFFER_ADD_ESIM | CCBS_RESOLVE_SOC_CODE_FE |
| 5 | CCBS_RESOLVE_SOC_CODE_FE | CCBS_RESOLVE_SOC_CODE | — | `string-length(Soc)=0 or Offers Soc=0` | OMX_POPULATE_OFFER_PROMOEND | CCBS_GOD |
| 6 | CCBS_GOD | CCBS_GOD | — | `count(//Offers)>0 or SubscriberOffers!=79` | CCBS_RESOLVE_SOC_CODE_FE | OMX_OFFER_INCLUSION |
| 7 | OMX_OFFER_INCLUSION | OMX_OFFER_INCLUSION | — | `Channel!="EOC"` | CCBS_GOD | CCBS_OFFER_EXCLUSION |
| 8 | CCBS_OFFER_EXCLUSION | CCBS_OFFER_EXCLUSION | — | — | OMX_OFFER_INCLUSION | INTX_GET_PRODUCT_PREFERENCE_LIST |
| 9 | INTX_GET_PRODUCT_PREFERENCE_LIST | INTX_GET_PRODUCT_PREFERENCE_LIST | SUBSTATUS=ACTIVEORSUSPEND \| BUSINESSLINE=MOBILE \| COMPANYCODE=ALL \| CUSTOMERSEGMENT=ENTERPRISE | `Type!=73 and not(INB or ICA)` | CCBS_OFFER_EXCLUSION | CCBS_VALIDATE_ACCT_STATUS_ROOT_OU |
| 10 | CCBS_VALIDATE_ACCT_STATUS_ROOT_OU | CCBS_VALIDATE_ACCT_STATUS_ROOT_OU | — | `string-length(RawOUId)>0 and Channel!="TCC"` | INTX_GET_PRODUCT_PREFERENCE_LIST | CCBS_GET_ACCOUNT_HEADER |
| 11 | CCBS_GET_ACCOUNT_HEADER | CCBS_GET_ACCOUNT_HEADER | — | `string-length(RawAccountID)>0` | CCBS_VALIDATE_ACCT_STATUS_ROOT_OU | CCBS_GET_AGREEMENT_INFO |
| 12 | CCBS_GET_AGREEMENT_INFO | CCBS_GET_AGREEMENT_INFO | — | `string-length(OUId)>0` | CCBS_GET_ACCOUNT_HEADER | GET_SPECIAL_OFFER_INDICATOR |
| 13 | GET_SPECIAL_OFFER_INDICATOR | GET_SPECIAL_OFFER_INDICATOR | ADD_PROP=TR_MULTISIM_IND | — | CCBS_GET_AGREEMENT_INFO | MCS_GET_CHARGE_INFO |
| 14 | MCS_GET_CHARGE_INFO | MCS_GET_CHARGE_INFO | — | `SubscriberOffers[FE_OR_CCBS=FE and TR_SPECIAL_OFFER_IND=TPC]` | GET_SPECIAL_OFFER_INDICATOR | CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER |
| 15 | CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER | CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER | — | `Type=73 and Channel!="TCC" and not(INB or ICA)` | MCS_GET_CHARGE_INFO | CVSS_GET_MAX_ALLOW_ONLY_SUB |
| 16 | CVSS_GET_MAX_ALLOW_ONLY_SUB | CVSS_GET_MAX_ALLOW_ONLY_SUB | — | `Grading="NON-TOP" and Channel!="TCC" and not(INB or ICA)` | CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER | CCBS_GET_GROUP_INFO |
| 17 | CCBS_GET_GROUP_INFO | CCBS_GET_GROUP_INFO | — | `count(CUG ID)>0 and Channel!="TCC"` | CVSS_GET_MAX_ALLOW_ONLY_SUB | CCBS_GET_DEALER_POOLS_FOR_DEALER |
| 18 | CCBS_GET_DEALER_POOLS_FOR_DEALER | CCBS_GET_DEALER_POOLS_FOR_DEALER | — | `string-length(DealerCode)!=0` | CCBS_GET_GROUP_INFO | ASRM_GET_UR_DETAILS_MSISDN |
| 19 | ASRM_GET_UR_DETAILS_MSISDN | ASRM_GET_UR_DETAILS_MSISDN | — | — | CCBS_GET_DEALER_POOLS_FOR_DEALER | INTX_GET_SIM_INFO_BY_MSISDN |
| 20 | INTX_GET_SIM_INFO_BY_MSISDN | INTX_GET_SIM_INFO_BY_MSISDN | — | — | ASRM_GET_UR_DETAILS_MSISDN | ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST |
| 21 | ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST | ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST | DEALERCODE=70000776 \| ESIM_FLAG=Y | `PEID+PMATCHID set and SIM/ICCID not set` | INTX_GET_SIM_INFO_BY_MSISDN | INTX_GET_SIM_INFO_BY_SIM |
| 22 | INTX_GET_SIM_INFO_BY_SIM | INTX_GET_SIM_INFO_BY_SIM | — | `PEID+PMATCHID absent or SIM present` | ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST | INTX_GET_SIM_INFO_BY_ICCID |
| 23 | INTX_GET_SIM_INFO_BY_ICCID | INTX_GET_SIM_INFO_BY_ICCID | PROJ=ESIM | `PEID+PMATCHID present` | INTX_GET_SIM_INFO_BY_SIM | CVSS_GET_AUTO_APPROVE_CODE |
| 24 | CVSS_GET_AUTO_APPROVE_CODE | CVSS_GET_AUTO_APPROVE_CODE | requestType=AM | `Subscriber count > MAX_ALLOW and no maxAllowApproveCode` | INTX_GET_SIM_INFO_BY_ICCID | CVSS_GET_VALIDATE_APPROVE_CODE |
| 25 | CVSS_GET_VALIDATE_APPROVE_CODE | CVSS_GET_VALIDATE_APPROVE_CODE | — | `any approve code present and not(INB or ICA)` | CVSS_GET_AUTO_APPROVE_CODE | OMX_BIZ_VAL |
| 26 | OMX_BIZ_VAL | OMX_BIZ_VAL | — | — | CVSS_GET_VALIDATE_APPROVE_CODE | CCBS_CREATE_CUST_WITH_CYCLE |
| 27 | CCBS_CREATE_CUST_WITH_CYCLE | CCBS_CREATE_CUST_WITH_CYCLE | — | `not(exists(RawCustomerId))` | OMX_BIZ_VAL | CCBS_GET_CUSTOMER_HEADER |
| 28 | CCBS_GET_CUSTOMER_HEADER | CCBS_GET_CUSTOMER_HEADER | — | `Customer without BillCycleNo` | CCBS_CREATE_CUST_WITH_CYCLE | OMX_BRMS_DB |
| 29 | OMX_BRMS_DB | OMX_BRMS_DB | — | — | CCBS_GET_CUSTOMER_HEADER | OMX_RESOLVE_SOC_DATA |
| 30 | OMX_RESOLVE_SOC_DATA | OMX_RESOLVE_SOC_DATA | — | — | OMX_BRMS_DB | CCBS_RESOLVE_SOC_CODE |
| 31 | CCBS_RESOLVE_SOC_CODE | CCBS_RESOLVE_SOC_CODE | — | `Soc present but RelatedOffers missing, or Soc absent (non-69/79)` | OMX_RESOLVE_SOC_DATA | CCBS_GOD_ALL |
| 32 | CCBS_GOD_ALL | CCBS_GOD | — | `SubscriberOffers[FE or BRMS, not 79/69]` | CCBS_RESOLVE_SOC_CODE | CCBS_RESOLVE_SOC_CODE_BRMS |
| 33 | CCBS_RESOLVE_SOC_CODE_BRMS | CCBS_RESOLVE_SOC_CODE | — | `SubscriberOffers[BRMS]` | CCBS_GOD_ALL | CCBS_GOD_BRMS |
| 34 | CCBS_GOD_BRMS | CCBS_GOD | — | `SubscriberOffers[BRMS]` | CCBS_RESOLVE_SOC_CODE_BRMS | OMX_CAL_OFFER_FUT_DATE_BRMS |
| 35 | OMX_CAL_OFFER_FUT_DATE_BRMS | OMX_CAL_OFFER_FUT_DATE | CAL_PARAM_EXP=Y \| EXCLUDE_OFFER=RMVX00000000001 | `BRMS offers on Subscriber or Agreement` | CCBS_GOD_BRMS | OMX_CAL_PP_EXPIRE_DATE |
| 36 | OMX_CAL_PP_EXPIRE_DATE | OMX_CAL_PP_EXPIRE_DATE | — | `SubscriberOffers[RMVX00000000001 and FE]` | OMX_CAL_OFFER_FUT_DATE_BRMS | AA_GET_SWITCH_FEATURE_OFFER_FT |
| 37 | AA_GET_SWITCH_FEATURE_OFFER_FT | AA_GET_SWITCH_FEATURE_OFFER | — | `Type=73` | OMX_CAL_PP_EXPIRE_DATE | ASRM_INVOKE_MSISDN_LOCK |
| 38 | ASRM_INVOKE_MSISDN_LOCK | ASRM_INVOKE_MSISDN | ACTIVITY=LOCK | `MSISDN_PAIR_SIM absent` | AA_GET_SWITCH_FEATURE_OFFER_FT | ASRM_INVOKE_MSISDN_RESERVE |
| 39 | ASRM_INVOKE_MSISDN_RESERVE | ASRM_INVOKE_MSISDN | ACTIVITY=RESERVE | `MSISDN_PAIR_SIM absent` | ASRM_INVOKE_MSISDN_LOCK | ASRM_INVOKE_SIM_RESERVE |
| 40 | ASRM_INVOKE_SIM_RESERVE | ASRM_INVOKE_SIM | ACTIVITY=RESERVE | `SIM_PAIR_MSISDN absent and no ESIM` | ASRM_INVOKE_MSISDN_RESERVE | ASRM_INVOKE_MINOR_SIM_RESERVE |
| 41 | ASRM_INVOKE_MINOR_SIM_RESERVE | ASRM_INVOKE_MINOR_SIM | ACTIVITY=RESERVE | `TR_MULTISIM_IND=RES` | ASRM_INVOKE_SIM_RESERVE | ASRM_INVOKE_SIM_PREACTIVATE |
| 42 | ASRM_INVOKE_SIM_PREACTIVATE | ASRM_INVOKE_SIM | ACTIVITY=PREACTIVATE | `SIM_PAIR_MSISDN present` | ASRM_INVOKE_MINOR_SIM_RESERVE | ASRM_INVOKE_MINOR_SIM_PREACTIVATE |
| 43 | ASRM_INVOKE_MINOR_SIM_PREACTIVATE | ASRM_INVOKE_MINOR_SIM | ACTIVITY=PREACTIVATE | `SIM_PAIR_MSISDN present and TR_MULTISIM_IND=RES` | ASRM_INVOKE_SIM_PREACTIVATE | OMX_TRANSFORM_NETWORK_CMD_TO_IOT |
| 44 | OMX_TRANSFORM_NETWORK_CMD_TO_IOT | OMX_TRANSFORM_NETWORK_CMD_TO_IOT | — | `SubscriberType=INB or ICA` | ASRM_INVOKE_MINOR_SIM_PREACTIVATE | OMX_GET_SRV_TRX_NO |
| 45 | OMX_GET_SRV_TRX_NO | OMX_GET_SRV_TRX_NO | NAC | — | OMX_TRANSFORM_NETWORK_CMD_TO_IOT | AA_ACTIVATE_SUBS_FT |
| 46 | AA_ACTIVATE_SUBS_FT | AA_ACTIVATE_SUBS | NAC | `Type=73` | OMX_GET_SRV_TRX_NO | OMX_CAL_CHK_SUM_SUB_LEVEL |
| 47 | OMX_CAL_CHK_SUM_SUB_LEVEL | OMX_CAL_CHK_SUM_SUB_LEVEL | — | `PEID+PMATCHID present and no ICC_ID_CHG_SUM` | AA_ACTIVATE_SUBS_FT | SMDP_PLUS_DOWNLOAD |
| 48 | SMDP_PLUS_DOWNLOAD | SMDP_PLUS | PROJ=ESIM | `ESIM offer and ICC_ID_CHG_SUM exists` | OMX_CAL_CHK_SUM_SUB_LEVEL | SMDP_PLUS_CONFIRM |
| 49 | SMDP_PLUS_CONFIRM | SMDP_PLUS_CONFIRM | PROJ=ESIM | `ESIM offer and ICC_ID_CHG_SUM exists` | SMDP_PLUS_DOWNLOAD | CCBS_CREATE_PARENT_OU |
| 50 | CCBS_CREATE_PARENT_OU | CCBS_CREATE_PARENT_OU | — | `OUId absent` | SMDP_PLUS_CONFIRM | CCBS_CREATE_CHILD_OU |
| 51 | CCBS_CREATE_CHILD_OU | CCBS_CREATE_CHILD_OU | — | `ParentOU or ChildOU RawOUId absent` | CCBS_CREATE_PARENT_OU | CCBS_CREATE_AGREE |
| 52 | CCBS_CREATE_AGREE | CCBS_CREATE_AGREE | — | `RawOUId absent` | CCBS_CREATE_CHILD_OU | CCBS_CREATE_ACCT |
| 53 | CCBS_CREATE_ACCT | CCBS_CREATE_ACCT | — | `RawAccountID absent` | CCBS_CREATE_AGREE | CCBS_ADD_AGREEOFFER |
| 54 | CCBS_ADD_AGREEOFFER | CCBS_ADD_AGREEOFFER | — | `Offers[ServiceType=80 and FE]` | CCBS_CREATE_ACCT | CCBS_UPDATE_AGREEMENT_ON_UNIT |
| 55 | CCBS_UPDATE_AGREEMENT_ON_UNIT | CCBS_UPDATE_AGREEMENT_ON_UNIT | ADD | `Offers[ServiceType!=80 and FE]` | CCBS_ADD_AGREEOFFER | CCBS_CREATE_SUBS |
| 56 | CCBS_CREATE_SUBS | CCBS_CREATE_SUBS | ADD_DUMMY_IMEI | `SubscriberId absent` | CCBS_UPDATE_AGREEMENT_ON_UNIT | CJ_CREATE_SUB_CALL_VERIFICATION |
| 57 | CJ_CREATE_SUB_CALL_VERIFICATION | CJ_CREATE_SUB_CALL_VERIFICATION | — | — | CCBS_CREATE_SUBS | OMX_ADD_FUT_OFFER_BRMS |
| 58 | OMX_ADD_FUT_OFFER_BRMS | OMX_ADD_FUT_OFFER | — | `SubscriberOffers[FE or BRMS, EFF_TYPE=FUT]` | CJ_CREATE_SUB_CALL_VERIFICATION | CCBS_GET_SUBS_INFO |
| 59 | CCBS_GET_SUBS_INFO | CCBS_GET_SUBS_INFO | — | — | OMX_ADD_FUT_OFFER_BRMS | AA_GET_SWITCH_FEATURE_OFFER |
| 60 | AA_GET_SWITCH_FEATURE_OFFER | AA_GET_SWITCH_FEATURE_OFFER | — | `Type!=73` | CCBS_GET_SUBS_INFO | AA_ACTIVATE_SUBS |
| 61 | AA_ACTIVATE_SUBS | AA_ACTIVATE_SUBS | NAC | `Type!=73` | AA_GET_SWITCH_FEATURE_OFFER | OMX_ADD_NXT_PP |
| 62 | OMX_ADD_NXT_PP | OMX_ADD_NXT_PP | — | `SubscriberOffers[ST=80 and FE] or Agreement Offers[ST=80]` | AA_ACTIVATE_SUBS | OMX_ADD_NEXT_OFFER |
| 63 | OMX_ADD_NEXT_OFFER | OMX_ADD_NEXT_OFFER | — | `no EFF_ORD_DT and FE/BRMS offers not FUT` | OMX_ADD_NXT_PP | ASRM_INVOKE_MSISDN_ACTIVATE |
| 64 | ASRM_INVOKE_MSISDN_ACTIVATE | ASRM_INVOKE_MSISDN | ACTIVITY=ACTIVATE | `MSISDN_PAIR_SIM absent` | OMX_ADD_NEXT_OFFER | ASRM_INVOKE_SIM_ACTIVATE |
| 65 | ASRM_INVOKE_SIM_ACTIVATE | ASRM_INVOKE_SIM | ACTIVITY=ACTIVATE | — | ASRM_INVOKE_MSISDN_ACTIVATE | ASRM_INVOKE_MINOR_SIM_ACTIVATE |
| 66 | ASRM_INVOKE_MINOR_SIM_ACTIVATE | ASRM_INVOKE_MINOR_SIM | ACTIVITY=ACTIVATE | `TR_MULTISIM_IND=RES` | ASRM_INVOKE_SIM_ACTIVATE | ASRM_UPDATE_ATTRIBUTE_SIM |
| 67 | ASRM_UPDATE_ATTRIBUTE_SIM | ASRM_UPDATE_ATTRIBUTE_SIM | EXPIRE_SELF=-1 \| PROJ=RIO | — | ASRM_INVOKE_MINOR_SIM_ACTIVATE | NAS_ACTIVATE_NEW_SUBS |
| 68 | NAS_ACTIVATE_NEW_SUBS | NAS_ACTIVATE_NEW_SUBS | — | — | ASRM_UPDATE_ATTRIBUTE_SIM | STATUS_UPDATE_CREATING_PROFILE |
| 69 | STATUS_UPDATE_CREATING_PROFILE | STATUS_UPDATE_CREATING_PROFILE | — | — | NAS_ACTIVATE_NEW_SUBS | CVSS_CREDIT_CHECK_NEW_ACCNT |
| 70 | CVSS_CREDIT_CHECK_NEW_ACCNT | CVSS_CREDIT_CHECK | — | `no RawAccountID and Subscriber count>0 and not INB/ICA` | STATUS_UPDATE_CREATING_PROFILE | OMX_GET_OFFER_RATE |
| 71 | OMX_GET_OFFER_RATE | OMX_GET_OFFER_RATE | — | `SubscriberOffers[FE and TR_MULTISIM_IND=RCM]` | CVSS_CREDIT_CHECK_NEW_ACCNT | ODS_GET_CREDIT_CLASS_CREDIT_LIMIT |
| 72 | ODS_GET_CREDIT_CLASS_CREDIT_LIMIT | ODS_GET_CREDIT_CLASS_CREDIT_LIMIT | — | `no RawAccountID and Type=73 and CreditClass not F/V0/V1/V3` | OMX_GET_OFFER_RATE | CCBS_UPD_CREDIT_CLASS_NEW_ACCNT |
| 73 | CCBS_UPD_CREDIT_CLASS_NEW_ACCNT | CCBS_UPD_CREDIT_CLASS | — | `no RawAccountID and Subscriber count>0 and not INB/ICA` | ODS_GET_CREDIT_CLASS_CREDIT_LIMIT | CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT_FOR_ODS |
| 74 | CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT_FOR_ODS | CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT | — | `no RawAccountID, Type=73, CreditLimitWaiverInd!=U` | CCBS_UPD_CREDIT_CLASS_NEW_ACCNT | OMX_GET_RECURRING_CHARGE |
| 75 | OMX_GET_RECURRING_CHARGE | OMX_GET_RECURRING_CHARGE | — | `Grading=NON-TOP and Type!=73 and SubscriberOffers[ST!=69]` | CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT_FOR_ODS | OMX_CAL_CREDIT_LIMIT_NONTOP_CORP |
| 76 | OMX_CAL_CREDIT_LIMIT_NONTOP_CORP | OMX_CAL_CREDIT_LIMIT_NONTOP_CORP | — | `Grading=NON-TOP and Type!=73 and Channel!="EOC"` | OMX_GET_RECURRING_CHARGE | CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT_NONTOP_CORP |
| 77 | CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT_NONTOP_CORP | CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT | — | `Type!=73 and no RawAccountID and PersonalCreditLimit>0 and not U waiver` | OMX_CAL_CREDIT_LIMIT_NONTOP_CORP | CCBS_UPD_CREDIT_LIMIT |
| 78 | CCBS_UPD_CREDIT_LIMIT | CCBS_UPD_CREDIT_LIMIT | — | `Type!=73 and RawAccountID set and PersonalCreditLimit>0 and not U waiver` | CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT_NONTOP_CORP | CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO |
| 79 | CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO | CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO | CAL_CREDITLIMIT=Y \| reasonCode=G165 | `not FUT_ Channel and AccountSubType set and TR_SPECIAL_OFFER_IND=TPC` | CCBS_UPD_CREDIT_LIMIT | CVSS_GET_EXISTING_PRODUCT |
| 80 | CVSS_GET_EXISTING_PRODUCT | CVSS_GET_EXISTING_PRODUCT | — | `RawCustomerId+RawAccountID+Subscriber present` | CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO | CVSS_CREDIT_CHECK |
| 81 | CVSS_CREDIT_CHECK | CVSS_CREDIT_CHECK | — | `ProductCount=0 and not INB/ICA` | CVSS_GET_EXISTING_PRODUCT | ODS_GET_CREDIT_CLASS_CREDIT_LIMIT_FOR_INDY_NO_CVSS_BAN |
| 82 | ODS_GET_CREDIT_CLASS_CREDIT_LIMIT_FOR_INDY_NO_CVSS_BAN | ODS_GET_CREDIT_CLASS_CREDIT_LIMIT | — | `ProductCount=0, Type=73, CreditClass not F/V*` | CVSS_CREDIT_CHECK | CCBS_UPD_CREDIT_CLASS |
| 83 | CCBS_UPD_CREDIT_CLASS | CCBS_UPD_CREDIT_CLASS | — | `ProductCount=0 and not INB/ICA` | ODS_GET_CREDIT_CLASS_CREDIT_LIMIT_FOR_INDY_NO_CVSS_BAN | CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT_FOR_ODS_INDY_NO_CVSS_BAN |
| 84 | CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT_FOR_ODS_INDY_NO_CVSS_BAN | CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT | — | `ProductCount=0, Type=73, CreditLimitWaiverInd!=U` | CCBS_UPD_CREDIT_CLASS | CVSS_UPDATE_SUBSCRIBER_COUNT |
| 85 | CVSS_UPDATE_SUBSCRIBER_COUNT | CVSS_UPDATE_SUBSCRIBER_COUNT | — | `ProductCount>0 and not INB/ICA` | CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT_FOR_ODS_INDY_NO_CVSS_BAN | AA_CHECK_CONFIRMATION |
| 86 | AA_CHECK_CONFIRMATION | AA_CHECK_CONFIRMATION | NAC \| UPDATE_NETWORK_STATUS | `count(Subscriber)>0` | CVSS_UPDATE_SUBSCRIBER_COUNT | OMX_POPULATE_SUBS_FROM_EXTENDED_INFO |
| 87 | OMX_POPULATE_SUBS_FROM_EXTENDED_INFO | OMX_POPULATE_SUBS_FROM_EXTENDED_INFO | — | `ExtInfo[EXISTING_SUB]!=''` | AA_CHECK_CONFIRMATION | ATS_REGISTER_CAMPAIGN |
| 88 | ATS_REGISTER_CAMPAIGN | ATS_REGISTER_CAMPAIGN | — | `ExtInfo[TOL_FAMILY_PLUS or CAMPAIGN_CODE]!=''` | OMX_POPULATE_SUBS_FROM_EXTENDED_INFO | CCBS_CREATE_GROUP |
| 89 | CCBS_CREATE_GROUP | CCBS_CREATE_GROUP | GROUP_TYPE=HUG \| GROUP_DESC=True Family \| GROUP_IDENTIFY=TrueFamily | `TOL_FAMILY_PLUS+TRUELIFE_ID or CAMPAIGN_CODE+TRUELIFE_ID present` | ATS_REGISTER_CAMPAIGN | OMX_INJECT_OFFER_CUG |
| 90 | OMX_INJECT_OFFER_CUG | OMX_INJECT_OFFER | soc=16210129,offerName=CUGFRS15,level=OU,mapCugId=Y | `(TOL_FAMILY_PLUS or CAMPAIGN_CODE) and GROUP_ID present` | CCBS_CREATE_GROUP | OMX_CAL_OFFER_FUT_DATE |
| 91 | OMX_CAL_OFFER_FUT_DATE | OMX_CAL_OFFER_FUT_DATE | CAL_PARAM_EXP=Y \| EXCLUDE_OFFER=RMVX00000000001 | `FE/BRMS offers on Subscriber (non-79/69)` | OMX_INJECT_OFFER_CUG | SBM_BUY_DATA_PACK |
| 92 | SBM_BUY_DATA_PACK | SBM_BUY_DATA_PACK | — | `SubscriberOffers[ST=86 and FE or BRMS]` | OMX_CAL_OFFER_FUT_DATE | BL_CREATE_CHARGE |
| 93 | BL_CREATE_CHARGE | BL_CREATE_CHARGE | — | `SubscriberOffers[ST=79 and FE or BRMS]` | SBM_BUY_DATA_PACK | CCBS_CHANGE_PACKAGE_SUBSCRIBER |
| 94 | CCBS_CHANGE_PACKAGE_SUBSCRIBER | CCBS_CHANGE_PACKAGE_SUBSCRIBER | ADD | `FE/BRMS offers[ST=85/86/68, no CONTRACT, no IOTBU, not FUT/LOGICALDATE]` | BL_CREATE_CHARGE | MCS_REGISTER_SUBSCRIPTION |
| 95 | MCS_REGISTER_SUBSCRIPTION | MCS_REGISTER_SUBSCRIPTION | USE_FE_RECURRING=Y | `SubscriberOffers[ST=69, FE or BRMS, not TPC]` | CCBS_CHANGE_PACKAGE_SUBSCRIBER | MCS_REGISTER |
| 96 | MCS_REGISTER | MCS_REGISTER | — | `SubscriberOffers[ST=85/69, FE, TR_SPECIAL_OFFER_IND=TPC]` | MCS_REGISTER_SUBSCRIPTION | ATS_COMPLETED_CAMPAIGN |
| 97 | ATS_COMPLETED_CAMPAIGN | ATS_COMPLETED_CAMPAIGN | — | `CAMPAIGN_CODE+TRUELIFE_ID present` | MCS_REGISTER | CCBS_CREATE_MEMO_FOR_SBM |
| 98 | CCBS_CREATE_MEMO_FOR_SBM | CCBS_CREATE_MEMO_FOR_SBM | ENTITY_TYPE_ID=6 \| MEMO_TYPE_ID=90051 \| MEMO_SYSTEM_TEXT=082 | `SubscriberOffers[ST=86, FE or BRMS]` | ATS_COMPLETED_CAMPAIGN | OMX_EXP_FUT_OFFER |
| 99 | OMX_EXP_FUT_OFFER | OMX_EXP_FUT_OFFER | — | `FE/BRMS offers[ST!=69, EFF_TYPE!=FUT, EXP_TYPE=FUT]` | CCBS_CREATE_MEMO_FOR_SBM | OMX_EXP_FUT_RELATED_OFFER |
| 100 | OMX_EXP_FUT_RELATED_OFFER | OMX_EXP_FUT_RELATED_OFFER | — | `RelatedOffersArray[FE/BRMS, EFF_TYPE!=FUT, EXP_TYPE=FUT]` | OMX_EXP_FUT_OFFER | PSA_GET_DEVICE_INFO |
| 101 | PSA_GET_DEVICE_INFO | PSA_GET_DEVICE_INFO | — | `SubscriberOffers[IMEI_KNOX!=''  and FE/BRMS]` | OMX_EXP_FUT_RELATED_OFFER | KNOX_SAVE_DEVICE |
| 102 | KNOX_SAVE_DEVICE | KNOX_SAVE_DEVICE | — | `SubscriberOffers[IMEI_KNOX!='' and FE/BRMS]` | PSA_GET_DEVICE_INFO | OMX_NOTIFY_KNOX_EVENT |
| 103 | OMX_NOTIFY_KNOX_EVENT | OMX_NOTI_TO_KAFKA | knoxEvent=ADD | `SubscriberOffers[IMEI_KNOX!='' and FE/BRMS]` | KNOX_SAVE_DEVICE | PSA_UPDATE_KNOX_STATUS |
| 104 | PSA_UPDATE_KNOX_STATUS | PSA_UPDATE_KNOX_STATUS | KNOX_STATUS=ACTIVE | `SubscriberOffers[IMEI_KNOX!='' and FE/BRMS]` | OMX_NOTIFY_KNOX_EVENT | PSA_UPDATE_WARRANTY_DEVICE |
| 105 | PSA_UPDATE_WARRANTY_DEVICE | PSA_UPDATE_WARRANTY_DEVICE | — | `ExtInfo[UPDATE_WARRANTY=Y]` | PSA_UPDATE_KNOX_STATUS | PSA_UPDATE_DEVICE |
| 106 | PSA_UPDATE_DEVICE | PSA_UPDATE_DEVICE | deviceStatus=ACTIVE | `MaterialInfo present and PARTNER!=''` | PSA_UPDATE_WARRANTY_DEVICE | TDG_CREATE_SUBSCRIBER |
| 107 | TDG_CREATE_SUBSCRIBER | TDG_CREATE_SUBSCRIBER | — | `SubscriberOffers[ST=70]` | PSA_UPDATE_DEVICE | OMX_UPDATE_FE_OR_CCBS_VALUE |
| 108 | OMX_UPDATE_FE_OR_CCBS_VALUE | OMX_UPDATE_FE_OR_CCBS_VALUE | CCBS | `FE/BRMS offers have SwitchFeature and not ST=80` | TDG_CREATE_SUBSCRIBER | OMX_POPULATE_MSIM_INFO |
| 109 | OMX_POPULATE_MSIM_INFO | OMX_POPULATE_MSIM_INFO | — | `SubscriberOffers[FE and TR_MULTISIM_IND=RES]` | OMX_UPDATE_FE_OR_CCBS_VALUE | OMX_GET_SRV_TRX_NO_MSIM |
| 110 | OMX_GET_SRV_TRX_NO_MSIM | OMX_GET_SRV_TRX_NO_MSIM | CCD | `MultiSIMInfo/Minor[Source=FE]` | OMX_POPULATE_MSIM_INFO | AA_ACTIVATE_SUBS_MSIM |
| 111 | AA_ACTIVATE_SUBS_MSIM | AA_ACTIVATE_SUBS_MSIM | CCD \| ADD | `MultiSIMInfo/Minor[Source=FE]` | OMX_GET_SRV_TRX_NO_MSIM | SBM_FUP_CREATE_GROUP |
| 112 | SBM_FUP_CREATE_GROUP | SBM_FUP_CREATE_GROUP | — | `Offers[FE/non-CCBS and FSH/FPL] and no CCBS-counterpart` | AA_ACTIVATE_SUBS_MSIM | SBM_FUP_CHANGE_TOPPING |
| 113 | SBM_FUP_CHANGE_TOPPING | SBM_FUP_CHANGE_TOPPING | ADD | `FE FSH offers and CCBS counterpart present` | SBM_FUP_CREATE_GROUP | SBM_FUP_CHANGE_VARIABLE |
| 114 | SBM_FUP_CHANGE_VARIABLE | SBM_FUP_CHANGE_VARIABLE | ADD | `FE FPL offers and CCBS counterpart present` | SBM_FUP_CHANGE_TOPPING | SBM_FUP_CHANGE_MEMBER |
| 115 | SBM_FUP_CHANGE_MEMBER | SBM_FUP_CHANGE_MEMBER | ADD | `Offers[FSH or FPL]` | SBM_FUP_CHANGE_VARIABLE | INTX_GET_OFFER_DETAIL |
| 116 | INTX_GET_OFFER_DETAIL | INTX_GET_OFFER_DETAIL | ADD | `Subscriber or Agreement Offers[ST=80 and FE]` | SBM_FUP_CHANGE_MEMBER | SMSGATEWAY_SEND_SMS |
| 117 | SMSGATEWAY_SEND_SMS | SMSGATEWAY_SEND_SMS | — | `Type=73` | INTX_GET_OFFER_DETAIL | OMX_GET_3CJ_EMAIL_TEMPLATE |
| 118 | OMX_GET_3CJ_EMAIL_TEMPLATE | OMX_GET_3CJ_EMAIL_TEMPLATE | — | `ExtInfo[FLOW_ID]!=''` | SMSGATEWAY_SEND_SMS | OMX_SEND_EMAIL3CJ |
| 119 | OMX_SEND_EMAIL3CJ | OMX_SEND_EMAIL3CJ | — | `Email!='' and EMAIL_TEMPLATE_CONTENT!=''` | OMX_GET_3CJ_EMAIL_TEMPLATE | OMX_INJECT_OFFER_ADD_ITEMIZE0 |
| 120 | OMX_INJECT_OFFER_ADD_ITEMIZE0 | OMX_INJECT_OFFER | soc=13102425,offerName=ITMBLS02,level=OU,checkExistingOu=Y | `BillFormat=E or S and SHOW_USAGE_DETAIL=Y` | OMX_SEND_EMAIL3CJ | CCBS_UPDATE_AGREEMENT_ON_UNIT_ITEMIZE_OFFER |
| 121 | CCBS_UPDATE_AGREEMENT_ON_UNIT_ITEMIZE_OFFER | CCBS_UPDATE_AGREEMENT_ON_UNIT | — | `ParentOU Agreement exists and Offers[ST!=80 and INJECT_OFFER]` | OMX_INJECT_OFFER_ADD_ITEMIZE0 | CRM_UPDATE_ASSET |
| 122 | CRM_UPDATE_ASSET | CRM_UPDATE_ASSET | — | `ExtInfo[VERIFY_RESULT]!=''` | CCBS_UPDATE_AGREEMENT_ON_UNIT_ITEMIZE_OFFER | TMN_CREATE_WALLET_MINIMAL_PROFILE |
| 123 | TMN_CREATE_WALLET_MINIMAL_PROFILE | TMN_CREATE_WALLET_MINIMAL_PROFILE | — | `Type=73` | CRM_UPDATE_ASSET | OMX_UPDATE_PARTIAL_ORDER |
| 124 | OMX_UPDATE_PARTIAL_ORDER | OMX_SAVE_PARTIAL_ORDER | ACTION=UPDATE \| STATUS=used | `ExtInfo[PARTIAL_ORDER_ID]!=''` | TMN_CREATE_WALLET_MINIMAL_PROFILE | END |

---

## §3 — PreExecCheck Details

### Step 1 — BLACKLIST_CHECK_BLACKLIST

**FM:** `BLACKLIST_CHECK_BLACKLIST`

```xpath
not(substring(//OrderData/Channel/text(),string-length(//OrderData/Channel/text())-2)='-MF')
```

### Step 3 — OMX_POPULATE_OFFER_ADD_ESIM

**FM:** `OMX_POPULATE_OFFER`

```xpath
string-length(//Subscriber/ResourceInfo[ResourceName="PEID"]/ValuesArray) > 0
and string-length(//Subscriber/ResourceInfo[ResourceName="PMATCHID"]/ValuesArray) > 0
```

### Step 4 — OMX_POPULATE_OFFER_PROMOEND

**FM:** `OMX_POPULATE_OFFER`

```xpath
//Customer/CustomerTypeInfo/Type=73
```

### Step 5 — CCBS_RESOLVE_SOC_CODE_FE

**FM:** `CCBS_RESOLVE_SOC_CODE`

```xpath
(string-length(//SubscriberOffers/Soc/text())=0 and boolean(//SubscriberOffers[ServiceType != 79]))
or (boolean(//Offers[1]) and string-length(//Offers/Soc/text())=0)
```

### Step 6 — CCBS_GOD

**FM:** `CCBS_GOD`

```xpath
count(//Offers) > 0 or boolean(//SubscriberOffers[ServiceType != 79])
```

### Step 7 — OMX_OFFER_INCLUSION

**FM:** `OMX_OFFER_INCLUSION`

```xpath
/ns0:OrderRequest/OrderData/Channel/text()!="EOC"
```

### Step 9 — INTX_GET_PRODUCT_PREFERENCE_LIST

**FM:** `INTX_GET_PRODUCT_PREFERENCE_LIST`

```xpath
/ns0:OrderRequest/OrderData/Customer/CustomerTypeInfo/Type/text()!=73
and not(boolean(//Subscriber[SubscriberType="INB" or SubscriberType="ICA"]))
```

### Step 10 — CCBS_VALIDATE_ACCT_STATUS_ROOT_OU

**FM:** `CCBS_VALIDATE_ACCT_STATUS_ROOT_OU`

```xpath
string-length(//RawOUId/text())>0 and /ns0:OrderRequest/OrderData/Channel/text()!="TCC"
```

### Step 11 — CCBS_GET_ACCOUNT_HEADER

**FM:** `CCBS_GET_ACCOUNT_HEADER`

```xpath
string-length(//RawAccountID/text())>0
```

### Step 12 — CCBS_GET_AGREEMENT_INFO

**FM:** `CCBS_GET_AGREEMENT_INFO`

```xpath
string-length(//OUId/text())>0
```

### Step 14 — MCS_GET_CHARGE_INFO

**FM:** `MCS_GET_CHARGE_INFO`

```xpath
boolean(//SubscriberOffers[
  (ServiceType='85' or ServiceType='69')
  and ExtendedInfo[Name='FE_OR_CCBS' and Value='FE']
  and contains(SocProperties,'TR_SPECIAL_OFFER_IND=TPC')
])
```

### Step 15 — CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER

**FM:** `CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER`

```xpath
/ns0:OrderRequest/OrderData/Customer/CustomerTypeInfo/Type/text()=73
and /ns0:OrderRequest/OrderData/Channel/text()!="TCC"
and not(boolean(//Subscriber[SubscriberType="INB" or SubscriberType="ICA"]))
```

### Step 16 — CVSS_GET_MAX_ALLOW_ONLY_SUB

**FM:** `CVSS_GET_MAX_ALLOW_ONLY_SUB`

```xpath
/ns0:OrderRequest/OrderData/Customer/CustomerGeneralInfo/Grading/text()="NON-TOP"
and /ns0:OrderRequest/OrderData/Channel/text()!="TCC"
and not(boolean(//Subscriber[SubscriberType="INB" or SubscriberType="ICA"]))
```

### Step 17 — CCBS_GET_GROUP_INFO

**FM:** `CCBS_GET_GROUP_INFO`

```xpath
count(//ParameterInfo[ParamName='CUG ID'])>0
and /ns0:OrderRequest/OrderData/Channel/text()!="TCC"
```

### Step 18 — CCBS_GET_DEALER_POOLS_FOR_DEALER

**FM:** `CCBS_GET_DEALER_POOLS_FOR_DEALER`

```xpath
string-length(/ns0:OrderRequest/OrderData/DealerCode/text())!=0
```

### Step 21 — ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST

**FM:** `ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST`

```xpath
string-length(//Subscriber/ResourceInfo[ResourceName="PEID"]/ValuesArray) > 0
and string-length(//Subscriber/ResourceInfo[ResourceName="PMATCHID"]/ValuesArray) > 0
and string-length(//Subscriber/ResourceInfo[ResourceName="SIM"]/ValuesArray) = 0
and string-length(//Subscriber/ExtendedInfo[Name = 'ICC_ID']/Value) = 0
and string-length(//Subscriber/ExtendedInfo[Name = 'ICC_ID_CHG_SUM']/Value) = 0
```

### Step 22 — INTX_GET_SIM_INFO_BY_SIM

**FM:** `INTX_GET_SIM_INFO_BY_SIM`

```xpath
(string-length(//Subscriber/ResourceInfo[ResourceName="PEID"]/ValuesArray) = 0
  and string-length(//Subscriber/ResourceInfo[ResourceName="PMATCHID"]/ValuesArray) = 0)
or string-length(//Subscriber/ResourceInfo[ResourceName="SIM"]/ValuesArray) > 0
```

### Step 23 — INTX_GET_SIM_INFO_BY_ICCID

**FM:** `INTX_GET_SIM_INFO_BY_ICCID`

```xpath
string-length(//Subscriber/ResourceInfo[ResourceName="PEID"]/ValuesArray) > 0
and string-length(//Subscriber/ResourceInfo[ResourceName="PMATCHID"]/ValuesArray) > 0
```

### Step 24 — CVSS_GET_AUTO_APPROVE_CODE

**FM:** `CVSS_GET_AUTO_APPROVE_CODE`

```xpath
boolean(count(//Subscriber) > (//Customer/ExtendedInfo[Name="MAX_ALLOW_ONLY_SUB"]/Value
  - //Customer/ExtendedInfo[Name="TOTAL_SUBS"]/Value))
and not(exists(/ns0:OrderRequest/OrderData/maxAllowApproveCode))
```

### Step 25 — CVSS_GET_VALIDATE_APPROVE_CODE

**FM:** `CVSS_GET_VALIDATE_APPROVE_CODE`

```xpath
string-length(//maxAllowApproveCode/text()) > 0
or string-length(//irApproveCode/text()) > 0
or string-length(//creditLimitApproveCode/text()) > 0
or exists(/ns0:OrderRequest/OrderData/Customer/ParentOU/ExtendedInfo[Name='APPROVE_CODE'])
and not(boolean(//Subscriber[SubscriberType="INB" or SubscriberType="ICA"]))
```

### Step 27 — CCBS_CREATE_CUST_WITH_CYCLE

**FM:** `CCBS_CREATE_CUST_WITH_CYCLE`

```xpath
not(exists(//RawCustomerId))
```

### Step 28 — CCBS_GET_CUSTOMER_HEADER

**FM:** `CCBS_GET_CUSTOMER_HEADER`

```xpath
boolean(//Customer[not(BillCycleNo[./text()])])
```

### Step 31 — CCBS_RESOLVE_SOC_CODE

**FM:** `CCBS_RESOLVE_SOC_CODE`

```xpath
(string-length(//SubscriberOffers/Soc/text()) > 0
  and string-length(//SubscriberOffers/RelatedOffersArray/Soc/text())=0)
or (string-length(//SubscriberOffers/Soc/text())=0
  and (boolean(//SubscriberOffers/ServiceType/text()!=79)
    and boolean(//SubscriberOffers/ServiceType/text()!=69)))
or (string-length(//Offers/Soc/text()) > 0
  and string-length(//Offers/RelatedOffersArray/Soc/text())=0)
or (boolean(//Offers[1]) and string-length(//Offers/Soc/text())=0)
```

### Step 32 — CCBS_GOD_ALL

**FM:** `CCBS_GOD`

```xpath
boolean(//SubscriberOffers[
  ExtendedInfo[Name='FE_OR_CCBS' and (Value='FE' or Value='BRMS')]
  and (ServiceType != 79 and ServiceType != 69)
])
```

### Step 33 — CCBS_RESOLVE_SOC_CODE_BRMS

**FM:** `CCBS_RESOLVE_SOC_CODE`

```xpath
boolean(//SubscriberOffers[ExtendedInfo[Value='BRMS']])
```

### Step 34 — CCBS_GOD_BRMS

**FM:** `CCBS_GOD`

```xpath
boolean(//SubscriberOffers[ExtendedInfo[Value='BRMS']])
```

### Step 35 — OMX_CAL_OFFER_FUT_DATE_BRMS

**FM:** `OMX_CAL_OFFER_FUT_DATE`

```xpath
boolean(//Subscriber/SubscriberOffers[1]
  and //SubscriberOffers[ExtendedInfo[Name='FE_OR_CCBS' and (Value='BRMS')]])
or boolean(//Agreement/Offers[ExtendedInfo[Name[.='FE_OR_CCBS'] and Value[.='BRMS']]])
```

### Step 36 — OMX_CAL_PP_EXPIRE_DATE

**FM:** `OMX_CAL_PP_EXPIRE_DATE`

```xpath
boolean(//Subscriber/SubscriberOffers[
  OfferName='RMVX00000000001'
  and ExtendedInfo[Name='FE_OR_CCBS' and Value='FE']
])
```

### Step 37 — AA_GET_SWITCH_FEATURE_OFFER_FT

**FM:** `AA_GET_SWITCH_FEATURE_OFFER`

```xpath
/ns0:OrderRequest/OrderData/Customer/CustomerTypeInfo/Type/text()=73
```

### Step 38 — ASRM_INVOKE_MSISDN_LOCK

**FM:** `ASRM_INVOKE_MSISDN`

```xpath
string-length(//Subscriber/ResourceInfo[ResourceName="MSISDN_PAIR_SIM"]/ValuesArray/text())=0
```

### Step 39 — ASRM_INVOKE_MSISDN_RESERVE

**FM:** `ASRM_INVOKE_MSISDN`

```xpath
string-length(//Subscriber/ResourceInfo[ResourceName="MSISDN_PAIR_SIM"]/ValuesArray/text()) = 0
```

### Step 40 — ASRM_INVOKE_SIM_RESERVE

**FM:** `ASRM_INVOKE_SIM`

```xpath
string-length(//Subscriber/ResourceInfo[ResourceName="SIM_PAIR_MSISDN"]/ValuesArray/text())=0
and string-length(//Subscriber/ResourceInfo[ResourceName="PEID"]/ValuesArray) = 0
and string-length(//Subscriber/ResourceInfo[ResourceName="PMATCHID"]/ValuesArray) = 0
```

### Step 41 — ASRM_INVOKE_MINOR_SIM_RESERVE

**FM:** `ASRM_INVOKE_MINOR_SIM`

```xpath
boolean(//SubscriberOffers[ExtendedInfo[Name='TR_MULTISIM_IND' and Value='RES']])
```

### Step 42 — ASRM_INVOKE_SIM_PREACTIVATE

**FM:** `ASRM_INVOKE_SIM`

```xpath
string-length(//Subscriber/ResourceInfo[ResourceName="SIM_PAIR_MSISDN"]/ValuesArray/text())>0
```

### Step 43 — ASRM_INVOKE_MINOR_SIM_PREACTIVATE

**FM:** `ASRM_INVOKE_MINOR_SIM`

```xpath
string-length(//Subscriber/ResourceInfo[ResourceName="SIM_PAIR_MSISDN"]/ValuesArray/text())>0
and boolean(//SubscriberOffers[ExtendedInfo[Name='TR_MULTISIM_IND' and Value='RES']])
```

### Step 44 — OMX_TRANSFORM_NETWORK_CMD_TO_IOT

**FM:** `OMX_TRANSFORM_NETWORK_CMD_TO_IOT`

```xpath
boolean(//Subscriber[SubscriberType="INB" or SubscriberType="ICA"])
```

### Step 46 — AA_ACTIVATE_SUBS_FT

**FM:** `AA_ACTIVATE_SUBS`

```xpath
/ns0:OrderRequest/OrderData/Customer/CustomerTypeInfo/Type/text()=73
```

### Step 47 — OMX_CAL_CHK_SUM_SUB_LEVEL

**FM:** `OMX_CAL_CHK_SUM_SUB_LEVEL`

```xpath
string-length(//Subscriber/ResourceInfo[ResourceName="PEID"]/ValuesArray) > 0
and string-length(//Subscriber/ResourceInfo[ResourceName="PMATCHID"]/ValuesArray) > 0
and string-length(//Subscriber/ExtendedInfo[Name = 'ICC_ID_CHG_SUM']/Value) = 0
```

### Step 48 — SMDP_PLUS_DOWNLOAD

**FM:** `SMDP_PLUS`

```xpath
boolean(//SubscriberOffers[
  ExtendedInfo[Name='FE_OR_CCBS' and (Value='FE' or Value='BRMS')]
  and contains(SocProperties,'TR_OFFER_GROUP=ESIM')
])
and count(//Subscriber[ExtendedInfo[Name='ICC_ID_CHG_SUM']]) > 0
```

### Step 49 — SMDP_PLUS_CONFIRM

**FM:** `SMDP_PLUS_CONFIRM`

```xpath
boolean(//SubscriberOffers[
  ExtendedInfo[Name='FE_OR_CCBS' and (Value='FE' or Value='BRMS')]
  and contains(SocProperties,'TR_OFFER_GROUP=ESIM')
])
and count(//Subscriber[ExtendedInfo[Name='ICC_ID_CHG_SUM']]) > 0
```

### Step 50 — CCBS_CREATE_PARENT_OU

**FM:** `CCBS_CREATE_PARENT_OU`

```xpath
not(exists(//OUId)) or string-length(//OUId/text())=0
```

### Step 51 — CCBS_CREATE_CHILD_OU

**FM:** `CCBS_CREATE_CHILD_OU`

```xpath
(not(exists(//ParentOU/RawOUId)) or string-length(//ParentOU/RawOUId/text())=0)
or (not(exists(//ChildOU/RawOUId)) or string-length(//ChildOU/RawOUId/text())=0)
```

### Step 52 — CCBS_CREATE_AGREE

**FM:** `CCBS_CREATE_AGREE`

```xpath
not(exists(//RawOUId))
```

### Step 53 — CCBS_CREATE_ACCT

**FM:** `CCBS_CREATE_ACCT`

```xpath
not(exists(//RawAccountID)) or string-length(//RawAccountID/text())=0
```

### Step 54 — CCBS_ADD_AGREEOFFER

**FM:** `CCBS_ADD_AGREEOFFER`

```xpath
count(//Offers)>0
and boolean(//Agreement[1]
  and //Offers[ServiceType ='80' and ExtendedInfo[Name='FE_OR_CCBS' and Value='FE']])
```

### Step 55 — CCBS_UPDATE_AGREEMENT_ON_UNIT

**FM:** `CCBS_UPDATE_AGREEMENT_ON_UNIT`

```xpath
count(//Offers)>0
and boolean(//Agreement[1]
  and //Offers[ServiceType !='80' and ExtendedInfo[Name='FE_OR_CCBS' and Value='FE']])
```

### Step 56 — CCBS_CREATE_SUBS

**FM:** `CCBS_CREATE_SUBS`

```xpath
not(exists(//Subscriber/SubscriberId))
```

### Step 58 — OMX_ADD_FUT_OFFER_BRMS

**FM:** `OMX_ADD_FUT_OFFER`

```xpath
boolean(//Subscriber/SubscriberOffers[1]
  and //SubscriberOffers[
    ExtendedInfo[Name='FE_OR_CCBS' and (Value='FE' or Value='BRMS')]
    and ExtendedInfo[(Name='EFF_TYPE') and Value='FUT']
  ])
```

### Step 60 — AA_GET_SWITCH_FEATURE_OFFER

**FM:** `AA_GET_SWITCH_FEATURE_OFFER`

```xpath
/ns0:OrderRequest/OrderData/Customer/CustomerTypeInfo/Type/text()!=73
```

### Step 61 — AA_ACTIVATE_SUBS

**FM:** `AA_ACTIVATE_SUBS`

```xpath
/ns0:OrderRequest/OrderData/Customer/CustomerTypeInfo/Type/text()!=73
```

### Step 62 — OMX_ADD_NXT_PP

**FM:** `OMX_ADD_NXT_PP`

```xpath
boolean(//Subscriber/SubscriberOffers[ServiceType[.='80']][ExtendedInfo[Name[.='FE_OR_CCBS'] and Value[.='FE']]])
or boolean(//Agreement/Offers[ServiceType[.='80']])
```

### Step 63 — OMX_ADD_NEXT_OFFER

**FM:** `OMX_ADD_NEXT_OFFER`

```xpath
(not(boolean(/ns0:OrderRequest/OrderData[ExtendedInfo[Name='EFF_ORD_DT']])))
and boolean(//Subscriber/SubscriberOffers[1]
  and //SubscriberOffers[ExtendedInfo[Name='FE_OR_CCBS' and (Value='FE' or Value='BRMS')]
    and (ServiceType!='80')])
and ((not(boolean(//SubscriberOffers[ExtendedInfo[Name='EFF_TYPE']]))
  or boolean(//SubscriberOffers[ExtendedInfo[Name='EFF_TYPE' and Value!='FUT']]))
  and boolean(not(boolean(//SubscriberOffers[ExtendedInfo[Name='LOGICALDATE_PROV']]))))
```

### Step 64 — ASRM_INVOKE_MSISDN_ACTIVATE

**FM:** `ASRM_INVOKE_MSISDN`

```xpath
string-length(//Subscriber/ResourceInfo[ResourceName="MSISDN_PAIR_SIM"]/ValuesArray/text())=0
```

### Step 66 — ASRM_INVOKE_MINOR_SIM_ACTIVATE

**FM:** `ASRM_INVOKE_MINOR_SIM`

```xpath
boolean(//SubscriberOffers[ExtendedInfo[Name='TR_MULTISIM_IND' and Value='RES']])
```

### Step 70 — CVSS_CREDIT_CHECK_NEW_ACCNT

**FM:** `CVSS_CREDIT_CHECK`

```xpath
not(exists(//RawAccountID)) and count(//Subscriber) > 0
and not(boolean(//Subscriber[SubscriberType="INB" or SubscriberType="ICA"]))
```

### Step 71 — OMX_GET_OFFER_RATE

**FM:** `OMX_GET_OFFER_RATE`

```xpath
boolean(//Subscriber/SubscriberOffers[
  ExtendedInfo[Name="FE_OR_CCBS" and Value="FE"]
  and ExtendedInfo[Name="TR_MULTISIM_IND" and Value="RCM"]
])
```

### Step 72 — ODS_GET_CREDIT_CLASS_CREDIT_LIMIT

**FM:** `ODS_GET_CREDIT_CLASS_CREDIT_LIMIT`

```xpath
not(exists(//RawAccountID)) and count(//Subscriber) > 0
and boolean(/ns0:OrderRequest/OrderData/Customer[CustomerTypeInfo/Type[.=73]]/Account/AccountManagementInfo[
  CreditClass[.!='F' and .!='V0' and .!='V1' and .!='V3']
  and AccountSubType[.!='RVI' and .!='RVB' and .!='RVT' and .!='RVN' and .!='FVI' and .!='RVV']
])
and not(boolean(//Subscriber[SubscriberType="INB" or SubscriberType="ICA"]))
```

### Step 73 — CCBS_UPD_CREDIT_CLASS_NEW_ACCNT

**FM:** `CCBS_UPD_CREDIT_CLASS`

```xpath
not(exists(//RawAccountID)) and count(//Subscriber) > 0
and not(boolean(//Subscriber[SubscriberType="INB" or SubscriberType="ICA"]))
```

### Step 75 — OMX_GET_RECURRING_CHARGE

**FM:** `OMX_GET_RECURRING_CHARGE`

```xpath
//OrderData/Customer/CustomerGeneralInfo/Grading='NON-TOP'
and boolean(//OrderData/Customer[CustomerTypeInfo/Type[.!=73]])
and boolean(//Subscriber/SubscriberOffers[ServiceType!='69'])
```

### Step 76 — OMX_CAL_CREDIT_LIMIT_NONTOP_CORP

**FM:** `OMX_CAL_CREDIT_LIMIT_NONTOP_CORP`

```xpath
//OrderData/Customer/CustomerGeneralInfo/Grading='NON-TOP'
and boolean(//OrderData/Customer[CustomerTypeInfo/Type[.!=73]])
and /ns0:OrderRequest/OrderData/Channel/text()!="EOC"
```

### Step 79 — CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO

**FM:** `CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO`

```xpath
(not(starts-with(/ns0:OrderRequest/OrderData/Channel,"FUT_"))
  and (count(//Customer/Account/AccountManagementInfo/AccountSubType)>0
    and boolean(//SubscriberOffers[
      (ServiceType='85' or ServiceType='69')
      and ExtendedInfo[Name='FE_OR_CCBS' and Value='FE']
      and contains(SocProperties,'TR_SPECIAL_OFFER_IND=TPC')
    ])))
```

### Step 80 — CVSS_GET_EXISTING_PRODUCT

**FM:** `CVSS_GET_EXISTING_PRODUCT`

```xpath
string-length(//RawCustomerId/text()) > 0
and (string-length(//RawAccountID/text()) > 0 and count(//Subscriber) > 0)
```

### Step 81 — CVSS_CREDIT_CHECK

**FM:** `CVSS_CREDIT_CHECK`

```xpath
/ns0:OrderRequest/OrderData/Customer/Account/ProductCount = 0
and not(boolean(//Subscriber[SubscriberType="INB" or SubscriberType="ICA"]))
```

### Step 85 — CVSS_UPDATE_SUBSCRIBER_COUNT

**FM:** `CVSS_UPDATE_SUBSCRIBER_COUNT`

```xpath
/ns0:OrderRequest/OrderData/Customer/Account/ProductCount > 0
and not(boolean(//Subscriber[SubscriberType="INB" or SubscriberType="ICA"]))
```

### Step 86 — AA_CHECK_CONFIRMATION

**FM:** `AA_CHECK_CONFIRMATION`

```xpath
count(//Subscriber)>0
```

### Step 87 — OMX_POPULATE_SUBS_FROM_EXTENDED_INFO

**FM:** `OMX_POPULATE_SUBS_FROM_EXTENDED_INFO`

```xpath
boolean(//OrderData/ExtendedInfo[Name="EXISTING_SUB" and Value!=""])
```

### Step 88 — ATS_REGISTER_CAMPAIGN

**FM:** `ATS_REGISTER_CAMPAIGN`

```xpath
boolean(//OrderData/ExtendedInfo[Name="TOL_FAMILY_PLUS" and Value!=""]
  or //OrderData/ExtendedInfo[Name="CAMPAIGN_CODE" and Value!=""])
```

### Step 89 — CCBS_CREATE_GROUP

**FM:** `CCBS_CREATE_GROUP`

```xpath
boolean(//OrderData[ExtendedInfo[Name="TOL_FAMILY_PLUS" and Value!=""] and ExtendedInfo[Name="TRUELIFE_ID" and Value!=""]]
  or //OrderData[ExtendedInfo[Name="CAMPAIGN_CODE" and Value!=""] and ExtendedInfo[Name="TRUELIFE_ID" and Value!=""]])
```

### Step 90 — OMX_INJECT_OFFER_CUG

**FM:** `OMX_INJECT_OFFER`

```xpath
boolean(//OrderData[ExtendedInfo[Name="TOL_FAMILY_PLUS" and Value!=""] and ExtendedInfo[Name="GROUP_ID" and Value!=""]]
  or //OrderData[ExtendedInfo[Name="CAMPAIGN_CODE" and Value!=""] and ExtendedInfo[Name="GROUP_ID" and Value!=""]])
```

### Step 91 — OMX_CAL_OFFER_FUT_DATE

**FM:** `OMX_CAL_OFFER_FUT_DATE`

```xpath
boolean(//Subscriber/SubscriberOffers[1]
  and //SubscriberOffers[ExtendedInfo[Name='FE_OR_CCBS' and (Value='FE' or Value='BRMS')]
    and (ServiceType != 79 and ServiceType != 69)])
```

### Step 92 — SBM_BUY_DATA_PACK

**FM:** `SBM_BUY_DATA_PACK`

```xpath
boolean(//SubscriberOffers[ServiceType='86'][
  ExtendedInfo[Name/text() = 'FE_OR_CCBS' and (Value/text() = 'FE' or Value/text() ='BRMS')]
])
```

### Step 93 — BL_CREATE_CHARGE

**FM:** `BL_CREATE_CHARGE`

```xpath
boolean(//SubscriberOffers[ServiceType='79'][
  ExtendedInfo[Name/text() = 'FE_OR_CCBS' and (Value/text() = 'FE' or Value/text() ='BRMS')]
])
```

### Step 94 — CCBS_CHANGE_PACKAGE_SUBSCRIBER

**FM:** `CCBS_CHANGE_PACKAGE_SUBSCRIBER`

```xpath
boolean(//Subscriber/SubscriberOffers[1]
  and //SubscriberOffers[
    ExtendedInfo[Name='FE_OR_CCBS' and (Value='FE' or Value='BRMS')]
    and (not(boolean(ExtendedInfo[Name='FCR_BYPASS'])) or ExtendedInfo[Name='FCR_BYPASS' and Value!='YES'])
    and (ServiceType='85' or ServiceType='86' or ServiceType='68')
  ]
  and not(//SubscriberOffers[contains(SocProperties,'TR_CONTRACT_IND=Y')])
  and not(//SubscriberOffers[contains(SocProperties,'TR_SPECIAL_OFFER_IND=IOTBU')])
  and ((not(boolean(//SubscriberOffers[ExtendedInfo[Name='EFF_TYPE']]))
    or boolean(//SubscriberOffers[ExtendedInfo[Name='EFF_TYPE' and Value!='FUT']]))
    and boolean(not(boolean(//SubscriberOffers[ExtendedInfo[Name='LOGICALDATE_PROV']])))))
```

### Step 95 — MCS_REGISTER_SUBSCRIPTION

**FM:** `MCS_REGISTER_SUBSCRIPTION`

```xpath
boolean(//Subscriber/SubscriberOffers[
  ExtendedInfo[Name='FE_OR_CCBS' and (Value='BRMS' or Value='FE')]
  and ServiceType='69'
  and not(contains(SocProperties,'TR_SPECIAL_OFFER_IND=TPC'))
])
```

### Step 96 — MCS_REGISTER

**FM:** `MCS_REGISTER`

```xpath
boolean(//SubscriberOffers[
  (ServiceType='85' or ServiceType='69')
  and ExtendedInfo[Name='FE_OR_CCBS' and Value='FE']
  and contains(SocProperties,'TR_SPECIAL_OFFER_IND=TPC')
])
```

### Step 97 — ATS_COMPLETED_CAMPAIGN

**FM:** `ATS_COMPLETED_CAMPAIGN`

```xpath
boolean(//OrderData[ExtendedInfo[Name="CAMPAIGN_CODE" and Value!=""]
  and ExtendedInfo[Name="TRUELIFE_ID" and Value!=""]])
```

### Step 98 — CCBS_CREATE_MEMO_FOR_SBM

**FM:** `CCBS_CREATE_MEMO_FOR_SBM`

```xpath
boolean(//SubscriberOffers[ServiceType='86'][
  ExtendedInfo[Name/text() = 'FE_OR_CCBS' and (Value/text() = 'FE' or Value/text() ='BRMS')]
])
```

### Step 99 — OMX_EXP_FUT_OFFER

**FM:** `OMX_EXP_FUT_OFFER`

```xpath
boolean(//Subscriber/SubscriberOffers[1]
  and //SubscriberOffers[
    ServiceType!='69'
    and ExtendedInfo[Name='FE_OR_CCBS' and (Value='FE' or Value='BRMS')]
    and ExtendedInfo[Name='EFF_TYPE' and Value!='FUT']
    and ExtendedInfo[Name='EXP_TYPE' and Value='FUT']
  ])
```

### Step 100 — OMX_EXP_FUT_RELATED_OFFER

**FM:** `OMX_EXP_FUT_RELATED_OFFER`

```xpath
boolean(//RelatedOffersArray[1]
  and //RelatedOffersArray[
    ExtendedInfo[Name='FE_OR_CCBS' and (Value='FE' or Value='BRMS')]
    and ExtendedInfo[Name='EFF_TYPE' and Value!='FUT']
    and ExtendedInfo[Name='EXP_TYPE' and Value='FUT']
  ])
```

### Step 101 — PSA_GET_DEVICE_INFO

**FM:** `PSA_GET_DEVICE_INFO`

```xpath
boolean(//SubscriberOffers[
  ExtendedInfo[Name='FE_OR_CCBS' and (Value='FE' or Value='BRMS')]
  and ExtendedInfo[Name='IMEI_KNOX' and Value!='']
])
```

### Step 102 — KNOX_SAVE_DEVICE

**FM:** `KNOX_SAVE_DEVICE`

```xpath
boolean(//SubscriberOffers[
  ExtendedInfo[Name='FE_OR_CCBS' and (Value='FE' or Value='BRMS')]
  and ExtendedInfo[Name='IMEI_KNOX' and Value!='']
])
```

### Step 103 — OMX_NOTIFY_KNOX_EVENT

**FM:** `OMX_NOTI_TO_KAFKA`

```xpath
boolean(//SubscriberOffers[
  ExtendedInfo[Name='FE_OR_CCBS' and (Value='FE' or Value='BRMS')]
  and ExtendedInfo[Name='IMEI_KNOX' and Value!='']
])
```

### Step 104 — PSA_UPDATE_KNOX_STATUS

**FM:** `PSA_UPDATE_KNOX_STATUS`

```xpath
boolean(//SubscriberOffers[
  ExtendedInfo[Name='FE_OR_CCBS' and (Value='FE' or Value='BRMS')]
  and ExtendedInfo[Name='IMEI_KNOX' and Value!='']
])
```

### Step 105 — PSA_UPDATE_WARRANTY_DEVICE

**FM:** `PSA_UPDATE_WARRANTY_DEVICE`

```xpath
boolean(//OrderData[ExtendedInfo[Name='UPDATE_WARRANTY' and Value ='Y']])
```

### Step 106 — PSA_UPDATE_DEVICE

**FM:** `PSA_UPDATE_DEVICE`

```xpath
count(//Subscriber/MaterialInfo/Material)>0
and boolean(//Subscriber[ExtendedInfo[Name='PARTNER' and Value != '']])
```

### Step 107 — TDG_CREATE_SUBSCRIBER

**FM:** `TDG_CREATE_SUBSCRIBER`

```xpath
boolean(//SubscriberOffers[ServiceType='70'])
```

### Step 108 — OMX_UPDATE_FE_OR_CCBS_VALUE

**FM:** `OMX_UPDATE_FE_OR_CCBS_VALUE`

```xpath
(boolean(//SubscriberOffers[
  ExtendedInfo[Name='FE_OR_CCBS' and (Value='FE' or Value='BRMS')]
]/SwitchFeature[1])
or boolean(//SubscriberOffers[
  ExtendedInfo[Name='FE_OR_CCBS' and (Value='FE' or Value='BRMS')]
]/RelatedOffersArray/SwitchFeature[1]))
and not(boolean(//SubscriberOffers[ServiceType='80'][
  ExtendedInfo[Name/text() = 'FE_OR_CCBS' and (Value/text() = 'FE' or Value/text() ='BRMS')]
]))
```

### Step 109 — OMX_POPULATE_MSIM_INFO

**FM:** `OMX_POPULATE_MSIM_INFO`

```xpath
boolean(//Subscriber/SubscriberOffers[
  ExtendedInfo[Name="FE_OR_CCBS" and Value="FE"]
  and ExtendedInfo[Name="TR_MULTISIM_IND" and Value="RES"]
])
```

### Step 110 — OMX_GET_SRV_TRX_NO_MSIM

**FM:** `OMX_GET_SRV_TRX_NO_MSIM`

```xpath
boolean(//Subscriber/MultiSIMInfo/Minor[Source='FE'])
```

### Step 111 — AA_ACTIVATE_SUBS_MSIM

**FM:** `AA_ACTIVATE_SUBS_MSIM`

```xpath
boolean(//Subscriber/MultiSIMInfo/Minor[Source='FE'])
```

### Step 112 — SBM_FUP_CREATE_GROUP

**FM:** `SBM_FUP_CREATE_GROUP`

```xpath
count(//Offers[ExtendedInfo[Name='FE_OR_CCBS' and Value!='CCBS']][
  ExtendedInfo[Name='SPECIAL_OFFER_INDICATOR' and (Value='FSH' or Value='FPL')]
]) > 0
and count(//Offers[ExtendedInfo[Name='FE_OR_CCBS' and Value='CCBS']][
  ExtendedInfo[Name='SPECIAL_OFFER_INDICATOR' and (Value='FSH' or Value='FPL')]
]) = 0
```

### Step 113 — SBM_FUP_CHANGE_TOPPING

**FM:** `SBM_FUP_CHANGE_TOPPING`

```xpath
count(//Offers[ExtendedInfo[Name='FE_OR_CCBS' and Value!='CCBS']][
  ExtendedInfo[Name='SPECIAL_OFFER_INDICATOR' and Value='FSH']
][ExtendedInfo[Name[.='EFF_TYPE'] and Value[.!='FUT']]]) > 0
and count(//Offers[ExtendedInfo[Name='FE_OR_CCBS' and Value='CCBS']][
  ExtendedInfo[Name='SPECIAL_OFFER_INDICATOR' and (Value='FSH' or Value='FPL')]
]) > 0
```

### Step 114 — SBM_FUP_CHANGE_VARIABLE

**FM:** `SBM_FUP_CHANGE_VARIABLE`

```xpath
count(//Offers[ExtendedInfo[Name='FE_OR_CCBS' and Value!='CCBS']][
  ExtendedInfo[Name='SPECIAL_OFFER_INDICATOR' and Value='FPL']
][ExtendedInfo[Name[.='EFF_TYPE'] and Value[.!='FUT']]]) > 0
and count(//Offers[ExtendedInfo[Name='FE_OR_CCBS' and Value='CCBS']][
  ExtendedInfo[Name='SPECIAL_OFFER_INDICATOR' and (Value='FSH' or Value='FPL')]
]) > 0
```

### Step 115 — SBM_FUP_CHANGE_MEMBER

**FM:** `SBM_FUP_CHANGE_MEMBER`

```xpath
count(//Offers[ExtendedInfo[Name='SPECIAL_OFFER_INDICATOR' and (Value='FSH' or Value='FPL')]]) > 0
```

### Step 116 — INTX_GET_OFFER_DETAIL

**FM:** `INTX_GET_OFFER_DETAIL`

```xpath
(boolean(//Subscriber/SubscriberOffers[ServiceType[.='80']][ExtendedInfo[Name[.='FE_OR_CCBS'] and Value[.='FE']]])
or boolean(//Agreement/Offers[ServiceType[.='80']][ExtendedInfo[Name[.='FE_OR_CCBS'] and Value[.='FE']]]))
```

### Step 117 — SMSGATEWAY_SEND_SMS

**FM:** `SMSGATEWAY_SEND_SMS`

```xpath
/ns0:OrderRequest/OrderData/Customer/CustomerTypeInfo/Type/text()=73
```

### Step 118 — OMX_GET_3CJ_EMAIL_TEMPLATE

**FM:** `OMX_GET_3CJ_EMAIL_TEMPLATE`

```xpath
string-length(//OrderData/ExtendedInfo[Name="FLOW_ID"]/Value) > 0
```

### Step 119 — OMX_SEND_EMAIL3CJ

**FM:** `OMX_SEND_EMAIL3CJ`

```xpath
string-length(//Customer/CustomerName/Email)>0
and string-length(//Subscriber/ExtendedInfo[Name="EMAIL_TEMPLATE_CONTENT"]/Value) > 0
```

### Step 120 — OMX_INJECT_OFFER_ADD_ITEMIZE0

**FM:** `OMX_INJECT_OFFER`

```xpath
boolean(//Account/BillingArrangementBillInfo/BillFormat/text()="E"
  or //Account/BillingArrangementBillInfo/BillFormat/text()="S")
and boolean(//Account/ExtendedInfo[Name='SHOW_USAGE_DETAIL'and Value='Y'])
```

### Step 121 — CCBS_UPDATE_AGREEMENT_ON_UNIT_ITEMIZE_OFFER

**FM:** `CCBS_UPDATE_AGREEMENT_ON_UNIT`

```xpath
exists(//ParentOU/Agreement)
and //Offers/ServiceType/text() != '80'
and //Offers/ExtendedInfo[Name='FE_OR_CCBS']/Value/text()='INJECT_OFFER'
```

### Step 122 — CRM_UPDATE_ASSET

**FM:** `CRM_UPDATE_ASSET`

```xpath
boolean(//OrderData[ExtendedInfo[Name='VERIFY_RESULT' and Value!='']])
```

### Step 123 — TMN_CREATE_WALLET_MINIMAL_PROFILE

**FM:** `TMN_CREATE_WALLET_MINIMAL_PROFILE`

```xpath
/ns0:OrderRequest/OrderData/Customer/CustomerTypeInfo/Type/text()=73
```

### Step 124 — OMX_UPDATE_PARTIAL_ORDER

**FM:** `OMX_SAVE_PARTIAL_ORDER`

```xpath
boolean(/ns0:OrderRequest/OrderData[ExtendedInfo[Name="PARTIAL_ORDER_ID" and Value != ""]])
```

---

## §4 — FM Documentation Index

| FM (ActivityID) | Used in Steps | Doc Link |
|-----------------|---------------|----------|
| BLACKLIST_CHECK_BLACKLIST | 1 | [Request_BLACKLIST_CHECK_BLACKLIST.html](../FMlogic/Request_BLACKLIST_CHECK_BLACKLIST.html) |
| BLACKLIST_CHECK_FRAUD | 2 | [Request_BLACKLIST_CHECK_FRAUD.html](../FMlogic/Request_BLACKLIST_CHECK_FRAUD.html) |
| OMX_POPULATE_OFFER | 3, 4, 90, 120 | [Request_OMX_POPULATE_OFFER.html](../FMlogic/Request_OMX_POPULATE_OFFER.html) |
| CCBS_RESOLVE_SOC_CODE | 5, 31, 33 | [Request_CCBS_RESOLVE_SOC_CODE.html](../FMlogic/Request_CCBS_RESOLVE_SOC_CODE.html) |
| CCBS_GOD | 6, 32, 34 | [Request_CCBS_GOD.html](../FMlogic/Request_CCBS_GOD.html) |
| OMX_OFFER_INCLUSION | 7 | [Request_OMX_OFFER_INCLUSION.html](../FMlogic/Request_OMX_OFFER_INCLUSION.html) |
| CCBS_OFFER_EXCLUSION | 8 | [Request_CCBS_OFFER_EXCLUSION.html](../FMlogic/Request_CCBS_OFFER_EXCLUSION.html) |
| INTX_GET_PRODUCT_PREFERENCE_LIST | 9 | [Request_INTX_GET_PRODUCT_PREFERENCE_LIST.html](../FMlogic/Request_INTX_GET_PRODUCT_PREFERENCE_LIST.html) |
| CCBS_VALIDATE_ACCT_STATUS_ROOT_OU | 10 | [Request_CCBS_VALIDATE_ACCT_STATUS_ROOT_OU.html](../FMlogic/Request_CCBS_VALIDATE_ACCT_STATUS_ROOT_OU.html) |
| CCBS_GET_ACCOUNT_HEADER | 11 | [Request_CCBS_GET_ACCOUNT_HEADER.html](../FMlogic/Request_CCBS_GET_ACCOUNT_HEADER.html) |
| CCBS_GET_AGREEMENT_INFO | 12 | [Request_CCBS_GET_AGREEMENT_INFO.html](../FMlogic/Request_CCBS_GET_AGREEMENT_INFO.html) |
| GET_SPECIAL_OFFER_INDICATOR | 13 | [Request_GET_SPECIAL_OFFER_INDICATOR.html](../FMlogic/Request_GET_SPECIAL_OFFER_INDICATOR.html) |
| MCS_GET_CHARGE_INFO | 14 | [Request_MCS_GET_CHARGE_INFO.html](../FMlogic/Request_MCS_GET_CHARGE_INFO.html) |
| CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER | 15 | [Request_CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER.html](../FMlogic/Request_CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER.html) |
| CVSS_GET_MAX_ALLOW_ONLY_SUB | 16 | [Request_CVSS_GET_MAX_ALLOW_ONLY_SUB.html](../FMlogic/Request_CVSS_GET_MAX_ALLOW_ONLY_SUB.html) |
| CCBS_GET_GROUP_INFO | 17 | [Request_CCBS_GET_GROUP_INFO.html](../FMlogic/Request_CCBS_GET_GROUP_INFO.html) |
| CCBS_GET_DEALER_POOLS_FOR_DEALER | 18 | [Request_CCBS_GET_DEALER_POOLS_FOR_DEALER.html](../FMlogic/Request_CCBS_GET_DEALER_POOLS_FOR_DEALER.html) |
| ASRM_GET_UR_DETAILS_MSISDN | 19 | [Request_ASRM_GET_UR_DETAILS_MSISDN.html](../FMlogic/Request_ASRM_GET_UR_DETAILS_MSISDN.html) |
| INTX_GET_SIM_INFO_BY_MSISDN | 20 | [Request_INTX_GET_SIM_INFO_BY_MSISDN.html](../FMlogic/Request_INTX_GET_SIM_INFO_BY_MSISDN.html) |
| ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST | 21 | [Request_ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST.html](../FMlogic/Request_ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST.html) |
| INTX_GET_SIM_INFO_BY_SIM | 22 | [Request_INTX_GET_SIM_INFO_BY_SIM.html](../FMlogic/Request_INTX_GET_SIM_INFO_BY_SIM.html) |
| INTX_GET_SIM_INFO_BY_ICCID | 23 | [Request_INTX_GET_SIM_INFO_BY_ICCID.html](../FMlogic/Request_INTX_GET_SIM_INFO_BY_ICCID.html) |
| CVSS_GET_AUTO_APPROVE_CODE | 24 | [Request_CVSS_GET_AUTO_APPROVE_CODE.html](../FMlogic/Request_CVSS_GET_AUTO_APPROVE_CODE.html) |
| CVSS_GET_VALIDATE_APPROVE_CODE | 25 | [Request_CVSS_GET_VALIDATE_APPROVE_CODE.html](../FMlogic/Request_CVSS_GET_VALIDATE_APPROVE_CODE.html) |
| OMX_BIZ_VAL | 26 | [Request_OMX_BIZ_VAL.html](../FMlogic/Request_OMX_BIZ_VAL.html) |
| CCBS_CREATE_CUST_WITH_CYCLE | 27 | [Request_CCBS_CREATE_CUST_WITH_CYCLE.html](../FMlogic/Request_CCBS_CREATE_CUST_WITH_CYCLE.html) |
| CCBS_GET_CUSTOMER_HEADER | 28 | [Request_CCBS_GET_CUSTOMER_HEADER.html](../FMlogic/Request_CCBS_GET_CUSTOMER_HEADER.html) |
| OMX_BRMS_DB | 29 | [Request_OMX_BRMS_DB.html](../FMlogic/Request_OMX_BRMS_DB.html) |
| OMX_RESOLVE_SOC_DATA | 30 | [Request_OMX_RESOLVE_SOC_DATA.html](../FMlogic/Request_OMX_RESOLVE_SOC_DATA.html) |
| OMX_CAL_OFFER_FUT_DATE | 35, 91 | [Request_OMX_CAL_OFFER_FUT_DATE.html](../FMlogic/Request_OMX_CAL_OFFER_FUT_DATE.html) |
| OMX_CAL_PP_EXPIRE_DATE | 36 | [Request_OMX_CAL_PP_EXPIRE_DATE.html](../FMlogic/Request_OMX_CAL_PP_EXPIRE_DATE.html) |
| AA_GET_SWITCH_FEATURE_OFFER | 37, 60 | [Request_AA_GET_SWITCH_FEATURE_OFFER.html](../FMlogic/Request_AA_GET_SWITCH_FEATURE_OFFER.html) |
| ASRM_INVOKE_MSISDN | 38, 39, 64 | [Request_ASRM_INVOKE_MSISDN.html](../FMlogic/Request_ASRM_INVOKE_MSISDN.html) |
| ASRM_INVOKE_SIM | 40, 42, 65 | [Request_ASRM_INVOKE_SIM.html](../FMlogic/Request_ASRM_INVOKE_SIM.html) |
| ASRM_INVOKE_MINOR_SIM | 41, 43, 66 | [Request_ASRM_INVOKE_MINOR_SIM.html](../FMlogic/Request_ASRM_INVOKE_MINOR_SIM.html) |
| OMX_TRANSFORM_NETWORK_CMD_TO_IOT | 44 | [Request_OMX_TRANSFORM_NETWORK_CMD_TO_IOT.html](../FMlogic/Request_OMX_TRANSFORM_NETWORK_CMD_TO_IOT.html) |
| OMX_GET_SRV_TRX_NO | 45 | [Request_OMX_GET_SRV_TRX_NO.html](../FMlogic/Request_OMX_GET_SRV_TRX_NO.html) |
| AA_ACTIVATE_SUBS | 46, 61 | [Request_AA_ACTIVATE_SUBS.html](../FMlogic/Request_AA_ACTIVATE_SUBS.html) |
| OMX_CAL_CHK_SUM_SUB_LEVEL | 47 | [Request_OMX_CAL_CHK_SUM_SUB_LEVEL.html](../FMlogic/Request_OMX_CAL_CHK_SUM_SUB_LEVEL.html) |
| SMDP_PLUS | 48 | [Request_SMDP_PLUS.html](../FMlogic/Request_SMDP_PLUS.html) |
| SMDP_PLUS_CONFIRM | 49 | [Request_SMDP_PLUS_CONFIRM.html](../FMlogic/Request_SMDP_PLUS_CONFIRM.html) |
| CCBS_CREATE_PARENT_OU | 50 | [Request_CCBS_CREATE_PARENT_OU.html](../FMlogic/Request_CCBS_CREATE_PARENT_OU.html) |
| CCBS_CREATE_CHILD_OU | 51 | [Request_CCBS_CREATE_CHILD_OU.html](../FMlogic/Request_CCBS_CREATE_CHILD_OU.html) |
| CCBS_CREATE_AGREE | 52 | [Request_CCBS_CREATE_AGREE.html](../FMlogic/Request_CCBS_CREATE_AGREE.html) |
| CCBS_CREATE_ACCT | 53 | [Request_CCBS_CREATE_ACCT.html](../FMlogic/Request_CCBS_CREATE_ACCT.html) |
| CCBS_ADD_AGREEOFFER | 54 | [Request_CCBS_ADD_AGREEOFFER.html](../FMlogic/Request_CCBS_ADD_AGREEOFFER.html) |
| CCBS_UPDATE_AGREEMENT_ON_UNIT | 55, 121 | [Request_CCBS_UPDATE_AGREEMENT_ON_UNIT.html](../FMlogic/Request_CCBS_UPDATE_AGREEMENT_ON_UNIT.html) |
| CCBS_CREATE_SUBS | 56 | [Request_CCBS_CREATE_SUBS.html](../FMlogic/Request_CCBS_CREATE_SUBS.html) |
| CJ_CREATE_SUB_CALL_VERIFICATION | 57 | [Request_CJ_CREATE_SUB_CALL_VERIFICATION.html](../FMlogic/Request_CJ_CREATE_SUB_CALL_VERIFICATION.html) |
| OMX_ADD_FUT_OFFER | 58 | [Request_OMX_ADD_FUT_OFFER.html](../FMlogic/Request_OMX_ADD_FUT_OFFER.html) |
| CCBS_GET_SUBS_INFO | 59 | [Request_CCBS_GET_SUBS_INFO.html](../FMlogic/Request_CCBS_GET_SUBS_INFO.html) |
| OMX_ADD_NXT_PP | 62 | [Request_OMX_ADD_NXT_PP.html](../FMlogic/Request_OMX_ADD_NXT_PP.html) |
| OMX_ADD_NEXT_OFFER | 63 | [Request_OMX_ADD_NEXT_OFFER.html](../FMlogic/Request_OMX_ADD_NEXT_OFFER.html) |
| ASRM_UPDATE_ATTRIBUTE_SIM | 67 | [Request_ASRM_UPDATE_ATTRIBUTE_SIM.html](../FMlogic/Request_ASRM_UPDATE_ATTRIBUTE_SIM.html) |
| NAS_ACTIVATE_NEW_SUBS | 68 | [Request_NAS_ACTIVATE_NEW_SUBS.html](../FMlogic/Request_NAS_ACTIVATE_NEW_SUBS.html) |
| STATUS_UPDATE_CREATING_PROFILE | 69 | [Request_STATUS_UPDATE_CREATING_PROFILE.html](../FMlogic/Request_STATUS_UPDATE_CREATING_PROFILE.html) |
| CVSS_CREDIT_CHECK | 70, 81 | [Request_CVSS_CREDIT_CHECK.html](../FMlogic/Request_CVSS_CREDIT_CHECK.html) |
| OMX_GET_OFFER_RATE | 71 | [Request_OMX_GET_OFFER_RATE.html](../FMlogic/Request_OMX_GET_OFFER_RATE.html) |
| ODS_GET_CREDIT_CLASS_CREDIT_LIMIT | 72, 82 | [Request_ODS_GET_CREDIT_CLASS_CREDIT_LIMIT.html](../FMlogic/Request_ODS_GET_CREDIT_CLASS_CREDIT_LIMIT.html) |
| CCBS_UPD_CREDIT_CLASS | 73, 83 | [Request_CCBS_UPD_CREDIT_CLASS.html](../FMlogic/Request_CCBS_UPD_CREDIT_CLASS.html) |
| CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT | 74, 77, 84 | [Request_CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT.html](../FMlogic/Request_CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT.html) |
| OMX_GET_RECURRING_CHARGE | 75 | [Request_OMX_GET_RECURRING_CHARGE.html](../FMlogic/Request_OMX_GET_RECURRING_CHARGE.html) |
| OMX_CAL_CREDIT_LIMIT_NONTOP_CORP | 76 | [Request_OMX_CAL_CREDIT_LIMIT_NONTOP_CORP.html](../FMlogic/Request_OMX_CAL_CREDIT_LIMIT_NONTOP_CORP.html) |
| CCBS_UPD_CREDIT_LIMIT | 78 | [Request_CCBS_UPD_CREDIT_LIMIT.html](../FMlogic/Request_CCBS_UPD_CREDIT_LIMIT.html) |
| CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO | 79 | [Request_CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO.html](../FMlogic/Request_CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO.html) |
| CVSS_GET_EXISTING_PRODUCT | 80 | [Request_CVSS_GET_EXISTING_PRODUCT.html](../FMlogic/Request_CVSS_GET_EXISTING_PRODUCT.html) |
| CVSS_UPDATE_SUBSCRIBER_COUNT | 85 | [Request_CVSS_UPDATE_SUBSCRIBER_COUNT.html](../FMlogic/Request_CVSS_UPDATE_SUBSCRIBER_COUNT.html) |
| AA_CHECK_CONFIRMATION | 86 | [Request_AA_CHECK_CONFIRMATION.html](../FMlogic/Request_AA_CHECK_CONFIRMATION.html) |
| OMX_POPULATE_SUBS_FROM_EXTENDED_INFO | 87 | [Request_OMX_POPULATE_SUBS_FROM_EXTENDED_INFO.html](../FMlogic/Request_OMX_POPULATE_SUBS_FROM_EXTENDED_INFO.html) |
| ATS_REGISTER_CAMPAIGN | 88 | [Request_ATS_REGISTER_CAMPAIGN.html](../FMlogic/Request_ATS_REGISTER_CAMPAIGN.html) |
| CCBS_CREATE_GROUP | 89 | [Request_CCBS_CREATE_GROUP.html](../FMlogic/Request_CCBS_CREATE_GROUP.html) |
| OMX_INJECT_OFFER | 90, 120 | [Request_OMX_INJECT_OFFER.html](../FMlogic/Request_OMX_INJECT_OFFER.html) |
| SBM_BUY_DATA_PACK | 92 | [Request_SBM_BUY_DATA_PACK.html](../FMlogic/Request_SBM_BUY_DATA_PACK.html) |
| BL_CREATE_CHARGE | 93 | [Request_BL_CREATE_CHARGE.html](../FMlogic/Request_BL_CREATE_CHARGE.html) |
| CCBS_CHANGE_PACKAGE_SUBSCRIBER | 94 | [Request_CCBS_CHANGE_PACKAGE_SUBSCRIBER.html](../FMlogic/Request_CCBS_CHANGE_PACKAGE_SUBSCRIBER.html) |
| MCS_REGISTER_SUBSCRIPTION | 95 | [Request_MCS_REGISTER_SUBSCRIPTION.html](../FMlogic/Request_MCS_REGISTER_SUBSCRIPTION.html) |
| MCS_REGISTER | 96 | [Request_MCS_REGISTER.html](../FMlogic/Request_MCS_REGISTER.html) |
| ATS_COMPLETED_CAMPAIGN | 97 | [Request_ATS_COMPLETED_CAMPAIGN.html](../FMlogic/Request_ATS_COMPLETED_CAMPAIGN.html) |
| CCBS_CREATE_MEMO_FOR_SBM | 98 | [Request_CCBS_CREATE_MEMO_FOR_SBM.html](../FMlogic/Request_CCBS_CREATE_MEMO_FOR_SBM.html) |
| OMX_EXP_FUT_OFFER | 99 | [Request_OMX_EXP_FUT_OFFER.html](../FMlogic/Request_OMX_EXP_FUT_OFFER.html) |
| OMX_EXP_FUT_RELATED_OFFER | 100 | [Request_OMX_EXP_FUT_RELATED_OFFER.html](../FMlogic/Request_OMX_EXP_FUT_RELATED_OFFER.html) |
| PSA_GET_DEVICE_INFO | 101 | [Request_PSA_GET_DEVICE_INFO.html](../FMlogic/Request_PSA_GET_DEVICE_INFO.html) |
| KNOX_SAVE_DEVICE | 102 | [Request_KNOX_SAVE_DEVICE.html](../FMlogic/Request_KNOX_SAVE_DEVICE.html) |
| OMX_NOTI_TO_KAFKA | 103 | [Request_OMX_NOTI_TO_KAFKA.html](../FMlogic/Request_OMX_NOTI_TO_KAFKA.html) |
| PSA_UPDATE_KNOX_STATUS | 104 | [Request_PSA_UPDATE_KNOX_STATUS.html](../FMlogic/Request_PSA_UPDATE_KNOX_STATUS.html) |
| PSA_UPDATE_WARRANTY_DEVICE | 105 | [Request_PSA_UPDATE_WARRANTY_DEVICE.html](../FMlogic/Request_PSA_UPDATE_WARRANTY_DEVICE.html) |
| PSA_UPDATE_DEVICE | 106 | [Request_PSA_UPDATE_DEVICE.html](../FMlogic/Request_PSA_UPDATE_DEVICE.html) |
| TDG_CREATE_SUBSCRIBER | 107 | [Request_TDG_CREATE_SUBSCRIBER.html](../FMlogic/Request_TDG_CREATE_SUBSCRIBER.html) |
| OMX_UPDATE_FE_OR_CCBS_VALUE | 108 | [Request_OMX_UPDATE_FE_OR_CCBS_VALUE.html](../FMlogic/Request_OMX_UPDATE_FE_OR_CCBS_VALUE.html) |
| OMX_POPULATE_MSIM_INFO | 109 | [Request_OMX_POPULATE_MSIM_INFO.html](../FMlogic/Request_OMX_POPULATE_MSIM_INFO.html) |
| OMX_GET_SRV_TRX_NO_MSIM | 110 | [Request_OMX_GET_SRV_TRX_NO_MSIM.html](../FMlogic/Request_OMX_GET_SRV_TRX_NO_MSIM.html) |
| AA_ACTIVATE_SUBS_MSIM | 111 | [Request_AA_ACTIVATE_SUBS_MSIM.html](../FMlogic/Request_AA_ACTIVATE_SUBS_MSIM.html) |
| SBM_FUP_CREATE_GROUP | 112 | [Request_SBM_FUP_CREATE_GROUP.html](../FMlogic/Request_SBM_FUP_CREATE_GROUP.html) |
| SBM_FUP_CHANGE_TOPPING | 113 | [Request_SBM_FUP_CHANGE_TOPPING.html](../FMlogic/Request_SBM_FUP_CHANGE_TOPPING.html) |
| SBM_FUP_CHANGE_VARIABLE | 114 | [Request_SBM_FUP_CHANGE_VARIABLE.html](../FMlogic/Request_SBM_FUP_CHANGE_VARIABLE.html) |
| SBM_FUP_CHANGE_MEMBER | 115 | [Request_SBM_FUP_CHANGE_MEMBER.html](../FMlogic/Request_SBM_FUP_CHANGE_MEMBER.html) |
| INTX_GET_OFFER_DETAIL | 116 | [Request_INTX_GET_OFFER_DETAIL.html](../FMlogic/Request_INTX_GET_OFFER_DETAIL.html) |
| SMSGATEWAY_SEND_SMS | 117 | [Request_SMSGATEWAY_SEND_SMS.html](../FMlogic/Request_SMSGATEWAY_SEND_SMS.html) |
| OMX_GET_3CJ_EMAIL_TEMPLATE | 118 | [Request_OMX_GET_3CJ_EMAIL_TEMPLATE.html](../FMlogic/Request_OMX_GET_3CJ_EMAIL_TEMPLATE.html) |
| OMX_SEND_EMAIL3CJ | 119 | [Request_OMX_SEND_EMAIL3CJ.html](../FMlogic/Request_OMX_SEND_EMAIL3CJ.html) |
| CRM_UPDATE_ASSET | 122 | [Request_CRM_UPDATE_ASSET.html](../FMlogic/Request_CRM_UPDATE_ASSET.html) |
| TMN_CREATE_WALLET_MINIMAL_PROFILE | 123 | [Request_TMN_CREATE_WALLET_MINIMAL_PROFILE.html](../FMlogic/Request_TMN_CREATE_WALLET_MINIMAL_PROFILE.html) |
| OMX_SAVE_PARTIAL_ORDER | 124 | [Request_OMX_SAVE_PARTIAL_ORDER.html](../FMlogic/Request_OMX_SAVE_PARTIAL_ORDER.html) |

---

## §5 — Sequence Diagram

> **Sequence diagram omitted** — 124 activities exceeds the 60-step render limit. See the companion HTML at `output/order/ACTIVATION.html` for the full interactive flow table.

---

*TRUE Corporation OMX · Order Journey Documentation*
