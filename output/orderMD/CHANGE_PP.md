# CHANGE_PP

> Process Configuration for CHANGE PRICEPLAN.

**Total steps:** 127 | **Unique FMs:** 86 | **Generated:** 79 | **Not Found:** 7 | **Entry point:** CCBS_GET_AGREEMENT_INFO | **Generated:** 2026-09-15

---

## §2 — Order Flow

| Step | Step ID | FM (ActivityID) | Parameter(s) | PreExecCheck | Previous | Next |
|------|---------|-----------------|--------------|--------------|----------|------|
| 1 | CCBS_GET_AGREEMENT_INFO | [CCBS_GET_AGREEMENT_INFO](../FMlogic/Request_CCBS_GET_AGREEMENT_INFO.html) | — | `boolean(//OUId[./text()] and not(//Subscriber/SubscriberOffers))` | START | CCBS_GET_CUST_ACC_SUB_ID |
| 2 | CCBS_GET_CUST_ACC_SUB_ID | [CCBS_GET_CUST_ACC_SUB_ID](../FMlogic/Request_CCBS_GET_CUST_ACC_SUB_ID.html) | — | `boolean(//Subscriber/MSISDN[./text()] and //Subscriber/SubscriberOffers)` | CCBS_GET_AGREEMENT_INFO | CCBS_GET_SUBSCRIBER_HEADER |
| 3 | CCBS_GET_SUBSCRIBER_HEADER | [CCBS_GET_SUBSCRIBER_HEADER](../FMlogic/Request_CCBS_GET_SUBSCRIBER_HEADER.html) | — | `boolean(//Subscriber/MSISDN[./text()] and //Subscriber/SubscriberOffers)` | CCBS_GET_CUST_ACC_SUB_ID | CCBS_GET_SUBS_INFO |
| 4 | CCBS_GET_SUBS_INFO | [CCBS_GET_SUBS_INFO](../FMlogic/Request_CCBS_GET_SUBS_INFO.html) | — | `boolean(//Subscriber/MSISDN[./text()] and //Subscriber/SubscriberOffers and (//Subscriber[Status !=67 and Status !=76 and Status !=84]))` | CCBS_GET_SUBSCRIBER_HEADER | CCBS_GET_CUSTOMER_HEADER |
| 5 | CCBS_GET_CUSTOMER_HEADER | [CCBS_GET_CUSTOMER_HEADER](../FMlogic/Request_CCBS_GET_CUSTOMER_HEADER.html) | GET_NAME_ADDRESS=Y | — | CCBS_GET_SUBS_INFO | CCBS_GET_ACCOUNT_HEADER |
| 6 | CCBS_GET_ACCOUNT_HEADER | [CCBS_GET_ACCOUNT_HEADER](../FMlogic/Request_CCBS_GET_ACCOUNT_HEADER.html) | — | — | CCBS_GET_CUSTOMER_HEADER | CCBS_GET_BA_HEADER |
| 7 | CCBS_GET_BA_HEADER | [CCBS_GET_BA_HEADER](../FMlogic/Request_CCBS_GET_BA_HEADER.html) | GET_NAME_ADDRESS=Y | — | CCBS_GET_ACCOUNT_HEADER | CCBS_GET_AGREEMENT_HEADER |
| 8 | CCBS_GET_AGREEMENT_HEADER | [CCBS_GET_AGREEMENT_HEADER](../FMlogic/Request_CCBS_GET_AGREEMENT_HEADER.html) | — | — | CCBS_GET_BA_HEADER | CCBS_GET_AGREEMENT_INFO_FOR_SHAREPLAN |
| 9 | CCBS_GET_AGREEMENT_INFO_FOR_SHAREPLAN | [CCBS_GET_AGREEMENT_INFO](../FMlogic/Request_CCBS_GET_AGREEMENT_INFO.html) | — | `not(//Agreement/Offers/ExtendedInfo[Name[.='FE_OR_CCBS'] and Value[.='CCBS']])` | CCBS_GET_AGREEMENT_HEADER | OMX_GET_SHAREPLAN_OU_OLDSOC |
| 10 | OMX_GET_SHAREPLAN_OU_OLDSOC | [OMX_GET_SHAREPLAN_OU_SOC_REMOVE](../FMlogic/Request_OMX_GET_SHAREPLAN_OU_SOC_REMOVE.html) | CCBS | `boolean(//Subscriber/SubscriberOffers/ExtendedInfo[Name[.='FE_OR_CCBS'] and Value[.='CCBS']])` | CCBS_GET_AGREEMENT_INFO_FOR_SHAREPLAN | OMX_GET_SHAREPLAN_OU_NEWSOC |
| 11 | OMX_GET_SHAREPLAN_OU_NEWSOC | [OMX_GET_SHAREPLAN_OU_SOC](../FMlogic/Request_OMX_GET_SHAREPLAN_OU_SOC.html) | — | `boolean(//Subscriber/SubscriberOffers/ExtendedInfo[Name[.='FE_OR_CCBS'] and Value[.='FE']])` | OMX_GET_SHAREPLAN_OU_OLDSOC | CCBS_L9_GET_CUGID_BY_AGREEMENTID |
| 12 | CCBS_L9_GET_CUGID_BY_AGREEMENTID | [CCBS_L9_GET_CUGID_BY_AGREEMENTID](../FMlogic/Request_CCBS_L9_GET_CUGID_BY_AGREEMENTID.html) | — | `exists(//Agreement/Offers[ExtendedInfo[Name[.='OFFER_LEVEL'] and Value[.='PARENT']]])` | OMX_GET_SHAREPLAN_OU_NEWSOC | CCBS_RESOLVE_SOC_CODE |
| 13 | CCBS_RESOLVE_SOC_CODE | [CCBS_RESOLVE_SOC_CODE](../FMlogic/Request_CCBS_RESOLVE_SOC_CODE.html) | — | — | CCBS_L9_GET_CUGID_BY_AGREEMENTID | CCBS_GOD |
| 14 | CCBS_GOD | [CCBS_GOD](../FMlogic/Request_CCBS_GOD.html) | — | `boolean(//ServiceType != 70)` | CCBS_RESOLVE_SOC_CODE | GET_PROFILE_FROM_CCP_ALL |
| 15 | GET_PROFILE_FROM_CCP_ALL | [GET_PROFILE_FROM_CCP_ALL](../FMlogic/Request_GET_PROFILE_FROM_CCP_ALL.html) | — | `substring(//Customer/Account/AccountManagementInfo/AccountSubType/text(),1,2)='HY'` | CCBS_GOD | OMX_OFFER_INCLUSION |
| 16 | OMX_OFFER_INCLUSION | [OMX_OFFER_INCLUSION](../FMlogic/Request_OMX_OFFER_INCLUSION.html) | FE_OR_CCBS=FE | — | GET_PROFILE_FROM_CCP_ALL | OMX_REMOVE_RELATED_OFFER_FCVBAR |
| 17 | OMX_REMOVE_RELATED_OFFER_FCVBAR | ~~OMX_REMOVE_RELATED_OFFER_FROM_PP~~ ⚠ Not Found | SOC=41861 | `not(//SubscriberOffers[ExtendedInfo[Name='FE_OR_CCBS' and Value='CCBS']][Soc[.='41861']]...)` | OMX_OFFER_INCLUSION | GET_SPECIAL_OFFER_INDICATOR |
| 18 | GET_SPECIAL_OFFER_INDICATOR | [GET_SPECIAL_OFFER_INDICATOR](../FMlogic/Request_GET_SPECIAL_OFFER_INDICATOR.html) | ADD_PROP=TR_MULTISIM_IND | — | OMX_REMOVE_RELATED_OFFER_FCVBAR | MCS_GET_CHARGE_INFO |
| 19 | MCS_GET_CHARGE_INFO | [MCS_GET_CHARGE_INFO](../FMlogic/Request_MCS_GET_CHARGE_INFO.html) | ADD_PROP=TR_MULTISIM_IND | `boolean(//SubscriberOffers[(ServiceType='85' or ServiceType='69') and ExtendedInfo[Name='FE_OR_CCBS' and Value='FE'] and contains(SocProperties,'TR_SPECIAL_OFFER_IND=TPC')])` | GET_SPECIAL_OFFER_INDICATOR | OMX_CAL_PP_EFF_DATE |
| 20 | OMX_CAL_PP_EFF_DATE | ~~OMX_CAL_PP_EFF_DATE~~ ⚠ Not Found | — | — | MCS_GET_CHARGE_INFO | OMX_SEARCH_FUT |
| 21 | OMX_SEARCH_FUT | [OMX_SEARCH_FUT](../FMlogic/Request_OMX_SEARCH_FUT.html) | STATUS=1 \| ORDER_TYPE=12 | — | OMX_CAL_PP_EFF_DATE | OMX_GET_OFFER_RATE_PP |
| 22 | OMX_GET_OFFER_RATE_PP | [OMX_GET_OFFER_RATE](../FMlogic/Request_OMX_GET_OFFER_RATE.html) | — | `boolean(//SubscriberOffers[ExtendedInfo[Name='FE_OR_CCBS' and Value='FE'] and ServiceType='80'])` | OMX_SEARCH_FUT | OMX_CAL_OFFER_FUT_DATE |
| 23 | OMX_CAL_OFFER_FUT_DATE | [OMX_CAL_OFFER_FUT_DATE](../FMlogic/Request_OMX_CAL_OFFER_FUT_DATE.html) | CAL_PARAM_EXP=Y \| EXCLUDE_OFFER=RMVX00000000001 | `boolean(//Subscriber/SubscriberOffers[1] and //SubscriberOffers[FE_OR_CCBS=FE or BRMS]) or boolean(//Agreement/Offers[FE_OR_CCBS=FE])` | OMX_GET_OFFER_RATE_PP | OMX_SEARCH_FUT_PP |
| 24 | OMX_SEARCH_FUT_PP | [OMX_SEARCH_FUT_PP](../FMlogic/Request_OMX_SEARCH_FUT_PP.html) | — | — | OMX_CAL_OFFER_FUT_DATE | CCBS_OFFER_EXCLUSION |
| 25 | CCBS_OFFER_EXCLUSION | [CCBS_OFFER_EXCLUSION](../FMlogic/Request_CCBS_OFFER_EXCLUSION.html) | — | — | OMX_SEARCH_FUT_PP | OMX_BIZ_VAL |
| 26 | OMX_BIZ_VAL | [OMX_BIZ_VAL](../FMlogic/Request_OMX_BIZ_VAL.html) | — | — | CCBS_OFFER_EXCLUSION | ATS_ENQUIRY_CAMPAIGN |
| 27 | ATS_ENQUIRY_CAMPAIGN | [ATS_ENQUIRY_CAMPAIGN](../FMlogic/Request_ATS_ENQUIRY_CAMPAIGN.html) | MobileSoftBundle | `exists(//Subscriber/MSISDN) and not(OfferActivityDate=FUT in SubscriberOffers or Agreement/Offers ServiceType=80)` | OMX_BIZ_VAL | CCBS_GET_CUST_ACC_SUB_ID_ATS |
| 28 | CCBS_GET_CUST_ACC_SUB_ID_ATS | [CCBS_GET_CUST_ACC_SUB_ID](../FMlogic/Request_CCBS_GET_CUST_ACC_SUB_ID.html) | SOURCE | `boolean(//Subscriber[ExtendedInfo[Name='FE_OR_CCBS' and Value='ATS']])` | ATS_ENQUIRY_CAMPAIGN | CCBS_GET_ACCOUNT_HEADER_ATS |
| 29 | CCBS_GET_ACCOUNT_HEADER_ATS | [CCBS_GET_ACCOUNT_HEADER](../FMlogic/Request_CCBS_GET_ACCOUNT_HEADER.html) | — | `boolean(//Subscriber[ExtendedInfo[Name='FE_OR_CCBS' and Value='ATS']])` | CCBS_GET_CUST_ACC_SUB_ID_ATS | CCBS_GET_AGREEMENT_HEADER_ATS |
| 30 | CCBS_GET_AGREEMENT_HEADER_ATS | [CCBS_GET_AGREEMENT_HEADER](../FMlogic/Request_CCBS_GET_AGREEMENT_HEADER.html) | — | `boolean(//Subscriber[ExtendedInfo[Name='FE_OR_CCBS' and Value='ATS']])` | CCBS_GET_ACCOUNT_HEADER_ATS | CCBS_GET_SUBSCRIBER_HEADER_ATS |
| 31 | CCBS_GET_SUBSCRIBER_HEADER_ATS | [CCBS_GET_SUBSCRIBER_HEADER](../FMlogic/Request_CCBS_GET_SUBSCRIBER_HEADER.html) | — | `boolean(//Subscriber[ExtendedInfo[Name='FE_OR_CCBS' and Value='ATS']])` | CCBS_GET_AGREEMENT_HEADER_ATS | CCBS_GET_CUSTOMER_HEADER_ATS |
| 32 | CCBS_GET_CUSTOMER_HEADER_ATS | [CCBS_GET_CUSTOMER_HEADER](../FMlogic/Request_CCBS_GET_CUSTOMER_HEADER.html) | — | `boolean(//Subscriber[ExtendedInfo[Name='FE_OR_CCBS' and Value='ATS']])` | CCBS_GET_SUBSCRIBER_HEADER_ATS | CCBS_GET_SUBS_INFO_ATS |
| 33 | CCBS_GET_SUBS_INFO_ATS | [CCBS_GET_SUBS_INFO](../FMlogic/Request_CCBS_GET_SUBS_INFO.html) | — | `boolean(//Subscriber[Status !=67 and Status !=76 and Status !=84 and ExtendedInfo[Name='FE_OR_CCBS' and Value='ATS']])` | CCBS_GET_CUSTOMER_HEADER_ATS | ASRM_INVOKE_MINOR_SIM_RESERVE |
| 34 | ASRM_INVOKE_MINOR_SIM_RESERVE | [ASRM_INVOKE_MINOR_SIM](../FMlogic/Request_ASRM_INVOKE_MINOR_SIM.html) | ACTIVITY=RESERVE | `boolean(SubscriberOffers[FE_OR_CCBS=FE or BRMS]) and boolean(TR_MULTISIM_IND=RES) and not ATS` | CCBS_GET_SUBS_INFO_ATS | OMX_ADD_FUT_PP |
| 35 | OMX_ADD_FUT_PP | [OMX_ADD_FUT_PP](../FMlogic/Request_OMX_ADD_FUT_PP.html) | — | `OfferActivityDate=FUT and FE_OR_CCBS=FE (Sub or Agreement ServiceType=80) and not ATS` | ASRM_INVOKE_MINOR_SIM_RESERVE | OMX_ADD_FUT_OFFER |
| 36 | OMX_ADD_FUT_OFFER | [OMX_ADD_FUT_OFFER](../FMlogic/Request_OMX_ADD_FUT_OFFER.html) | — | `boolean(//Agreement/Offers[EFF_TYPE=FUT][FE_OR_CCBS=FE]) and not ATS` | OMX_ADD_FUT_PP | OMX_BRMS_DB |
| 37 | OMX_BRMS_DB | [OMX_BRMS_DB](../FMlogic/Request_OMX_BRMS_DB.html) | — | `boolean(//Subscriber[MSISDN]) and (OfferActivityDate!=FUT or MULSIM offers FE) or Channel=ISERVICE and not ATS` | OMX_ADD_FUT_OFFER | CCBS_RESOLVE_SOC_CODE_BRMS |
| 38 | CCBS_RESOLVE_SOC_CODE_BRMS | [CCBS_RESOLVE_SOC_CODE](../FMlogic/Request_CCBS_RESOLVE_SOC_CODE.html) | — | — | OMX_BRMS_DB | OMX_RESOLVE_SOC_DATA |
| 39 | OMX_RESOLVE_SOC_DATA | [OMX_RESOLVE_SOC_DATA](../FMlogic/Request_OMX_RESOLVE_SOC_DATA.html) | — | — | CCBS_RESOLVE_SOC_CODE_BRMS | OMX_POPULATE_OFFER_PROMOEND |
| 40 | OMX_POPULATE_OFFER_PROMOEND | ~~OMX_POPULATE_OFFER~~ ⚠ Not Found | OFFER=soc=25427629,... | `CustomerType=73 and no RMVX00000000001 and not ATS` | OMX_RESOLVE_SOC_DATA | CCBS_GOD_BRMS |
| 41 | CCBS_GOD_BRMS | [CCBS_GOD](../FMlogic/Request_CCBS_GOD.html) | — | `boolean(FE_OR_CCBS=BRMS or OfferName=RMVX or ATS)` | OMX_POPULATE_OFFER_PROMOEND | OMX_GET_OFFER_RATE |
| 42 | OMX_GET_OFFER_RATE | [OMX_GET_OFFER_RATE](../FMlogic/Request_OMX_GET_OFFER_RATE.html) | — | `boolean(SubscriberOffers[FE or CCBS, ServiceType=80] and CampaignCode exists)` | CCBS_GOD_BRMS | ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN |
| 43 | ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN | [ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN](../FMlogic/Request_ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN.html) | — | `count(//BundleInfo[ConvergenceType='MobileSoftBundle'])>0` | OMX_GET_OFFER_RATE | OMX_OFFER_INCLUSION_BRMS |
| 44 | OMX_OFFER_INCLUSION_BRMS | [OMX_OFFER_INCLUSION](../FMlogic/Request_OMX_OFFER_INCLUSION.html) | FE_OR_CCBS=BRMS | `boolean(SubscriberOffers[FE_OR_CCBS=BRMS]) and not ATS` | ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN | OMX_CAL_OFFER_FUT_DATE_BRMS |
| 45 | OMX_CAL_OFFER_FUT_DATE_BRMS | [OMX_CAL_OFFER_FUT_DATE](../FMlogic/Request_OMX_CAL_OFFER_FUT_DATE.html) | CAL_PARAM_EXP=Y \| EXCLUDE_OFFER=RMVX00000000001 | `boolean(SubscriberOffers[FE_OR_CCBS=BRMS] or Agreement/Offers[BRMS]) and not ATS` | OMX_OFFER_INCLUSION_BRMS | OMX_CAL_PP_EXPIRE_DATE |
| 46 | OMX_CAL_PP_EXPIRE_DATE | ~~OMX_CAL_PP_EXPIRE_DATE~~ ⚠ Not Found | — | `boolean(OfferName=RMVX00000000001) and not ATS` | OMX_CAL_OFFER_FUT_DATE_BRMS | OMX_ADD_FUT_OFFER_BRMS |
| 47 | OMX_ADD_FUT_OFFER_BRMS | [OMX_ADD_FUT_OFFER](../FMlogic/Request_OMX_ADD_FUT_OFFER.html) | — | `boolean(SubscriberOffers[FE or BRMS][EFF_TYPE=FUT] and not TR_CONTRACT_IND=Y) and not ATS` | OMX_CAL_PP_EXPIRE_DATE | INTX_GET_MASTER_MINOR_SIM_INFO |
| 48 | INTX_GET_MASTER_MINOR_SIM_INFO | [INTX_GET_MASTER_MINOR_SIM_INFO](../FMlogic/Request_INTX_GET_MASTER_MINOR_SIM_INFO.html) | — | `boolean(SubscriberOffers[TR_MULTISIM_IND=RES\|RCM\|REE\|RCE]) and not ATS` | OMX_ADD_FUT_OFFER_BRMS | CCBS_CHANGE_PP_SUB |
| 49 | CCBS_CHANGE_PP_SUB | [CCBS_CHANGE_PP_SUB](../FMlogic/Request_CCBS_CHANGE_PP_SUB.html) | — | `boolean(Subscriber[MSISDN]) and OfferActivityDate!=FUT and not ATS` | INTX_GET_MASTER_MINOR_SIM_INFO | CCBS_UPDATE_PARAMETER_PROMOEND |
| 50 | CCBS_UPDATE_PARAMETER_PROMOEND | [CCBS_UPDATE_PARAMETER_SUBSCRIBER_POST](../FMlogic/Request_CCBS_UPDATE_PARAMETER_SUBSCRIBER_POST.html) | ACTIVITY_REASON=CREQ | `boolean(CHANGE_PP=Y) and OfferName=RMVX and FE_OR_CCBS=CCBS and not ATS` | CCBS_CHANGE_PP_SUB | CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO |
| 51 | CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO | [CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO](../FMlogic/Request_CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO.html) | — | `not(Channel starts FUT_) and UPDATE_BILLCYCLE=Y and SubscriberOffers[FE, CPEPR, ServiceType=80]` | CCBS_UPDATE_PARAMETER_PROMOEND | OMX_CAL_ACCT_SUB_TYPE |
| 52 | OMX_CAL_ACCT_SUB_TYPE | ~~OMX_CAL_ACCT_SUB_TYPE~~ ⚠ Not Found | — | `not(Channel starts FUT_) and (CCBS+CPEPR+80 or AccountSubType=CPE and FE+not(CPEPR)+80)` | CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO | CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO |
| 53 | CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO | [CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO](../FMlogic/Request_CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO.html) | — | `not(FUT_ channel) and AccountSubType exists and ServiceType=80[FE or CCBS+CPEPR] or OLD_ACCOUNT_SUBTYPE=CPE` | OMX_CAL_ACCT_SUB_TYPE | CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO_TPC |
| 54 | CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO_TPC | [CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO](../FMlogic/Request_CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO.html) | CAL_CREDITLIMIT=Y \| reasonCode=G165 | `not(FUT_ channel) and AccountSubType exists and ServiceType=85\|69[FE, TPC]` | CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO | CCBS_UPDATE_ACCT_COLLECTION_FIX_INFO |
| 55 | CCBS_UPDATE_ACCT_COLLECTION_FIX_INFO | [CCBS_UPDATE_ACCT_COLLECTION_FIX_INFO](../FMlogic/Request_CCBS_UPDATE_ACCT_COLLECTION_FIX_INFO.html) | — | `not(FUT_ channel) and (ServiceType=80[FE or CCBS+CPEPR] or AccountSubType=CPE or OLD_ACCOUNT_SUBTYPE=CPE)` | CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO_TPC | CCBS_GET_SUBS_LIST |
| 56 | CCBS_GET_SUBS_LIST | [CCBS_GET_SUBS_LIST](../FMlogic/Request_CCBS_GET_SUBS_LIST.html) | — | `boolean(//RawOUId) and OfferActivityDate!=FUT` | CCBS_UPDATE_ACCT_COLLECTION_FIX_INFO | CCBS_GET_SUBS_INFO_UNDER_OU |
| 57 | CCBS_GET_SUBS_INFO_UNDER_OU | [CCBS_GET_SUBS_INFO](../FMlogic/Request_CCBS_GET_SUBS_INFO.html) | — | `boolean(//RawOUId) and OfferActivityDate!=FUT and SubscriberId exists` | CCBS_GET_SUBS_LIST | CCBS_ADD_PP_OU |
| 58 | CCBS_ADD_PP_OU | [CCBS_ADD_PP_OU](../FMlogic/Request_CCBS_ADD_PP_OU.html) | — | `boolean(//RawOUId) and OfferActivityDate!=FUT and not(Agreement/Offers[CCBS, ServiceType=80])` | CCBS_GET_SUBS_INFO_UNDER_OU | CCBS_CHANGE_PP_OU |
| 59 | CCBS_CHANGE_PP_OU | [CCBS_CHANGE_PP_OU](../FMlogic/Request_CCBS_CHANGE_PP_OU.html) | — | `boolean(//RawOUId) and OfferActivityDate!=FUT and Agreement/Offers[CCBS, ServiceType=80]` | CCBS_ADD_PP_OU | CCBS_REMOVE_OFFER_AGREEMENT_ON_UNIT |
| 60 | CCBS_REMOVE_OFFER_AGREEMENT_ON_UNIT | [CCBS_UPDATE_AGREEMENT_ON_UNIT](../FMlogic/Request_CCBS_UPDATE_AGREEMENT_ON_UNIT.html) | — | `boolean(//Agreement[1] and Offers[REMOVE, FE_OR_CCBS=FE][EXP_TYPE!=FUT])` | CCBS_CHANGE_PP_OU | CCBS_ADD_OFFER_AGREEMENT_ON_UNIT |
| 61 | CCBS_ADD_OFFER_AGREEMENT_ON_UNIT | [CCBS_UPDATE_AGREEMENT_ON_UNIT](../FMlogic/Request_CCBS_UPDATE_AGREEMENT_ON_UNIT.html) | — | `boolean(//Agreement[1] and Offers[ADD, FE_OR_CCBS=FE][EFF_TYPE!=FUT])` | CCBS_REMOVE_OFFER_AGREEMENT_ON_UNIT | SBM_FUP_CREATE_GROUP |
| 62 | SBM_FUP_CREATE_GROUP | [SBM_FUP_CREATE_GROUP](../FMlogic/Request_SBM_FUP_CREATE_GROUP.html) | — | `//RawOUId and CCBS FSH\|FPL count=0 and FE FSH\|FPL count>0 and nonPP CCBS FSH\|FPL count=0` | CCBS_ADD_OFFER_AGREEMENT_ON_UNIT | SBM_FUP_DELETE_GROUP |
| 63 | SBM_FUP_DELETE_GROUP | [SBM_FUP_DELETE_GROUP](../FMlogic/Request_SBM_FUP_DELETE_GROUP.html) | — | `//RawOUId and CCBS FSH count>0 and FE FSH count=0 and nonPP CCBS FSH\|FPL count=0` | SBM_FUP_CREATE_GROUP | INTX_GET_CURRENT_SPECIALOFFERINDICATORLIST_BY_OU_GET_TOTAL_SIZE |
| 64 | INTX_GET_CURRENT_SPECIALOFFERINDICATORLIST_BY_OU_GET_TOTAL_SIZE | [INTX_GET_CURRENT_SPECIALOFFERINDICATORLIST_BY_OU](../FMlogic/Request_INTX_GET_CURRENT_SPECIALOFFERINDICATORLIST_BY_OU.html) | PAGE_SIZE=1 \| FCA | Same as step 63 | SBM_FUP_DELETE_GROUP | INTX_GET_CURRENT_SPECIALOFFERINDICATORLIST_BY_OU |
| 65 | INTX_GET_CURRENT_SPECIALOFFERINDICATORLIST_BY_OU | [INTX_GET_CURRENT_SPECIALOFFERINDICATORLIST_BY_OU](../FMlogic/Request_INTX_GET_CURRENT_SPECIALOFFERINDICATORLIST_BY_OU.html) | PAGE_SIZE=100 \| FCA | Same as step 63 | INTX_GET_CURRENT_SPECIALOFFERINDICATORLIST_BY_OU_GET_TOTAL_SIZE | SBM_FUP_CHANGE_MEMBER |
| 66 | SBM_FUP_CHANGE_MEMBER | [SBM_FUP_CHANGE_MEMBER](../FMlogic/Request_SBM_FUP_CHANGE_MEMBER.html) | ADD | `//RawOUId and CCBS FSH count=0 and FE FSH count>0 and nonPP CCBS FSH\|FPL count=0` | INTX_GET_CURRENT_SPECIALOFFERINDICATORLIST_BY_OU | OMX_CHECK_REMOVE_FUP_GROUP |
| 67 | OMX_CHECK_REMOVE_FUP_GROUP | ~~OMX_CHECK_REMOVE_FUP_GROUP~~ ⚠ Not Found | — | `boolean(//Subscriber[not(FE_OR_CCBS) or FE_OR_CCBS!=ATS])` | SBM_FUP_CHANGE_MEMBER | CCBS_CHANGE_PACKAGE_SUBSCRIBER_REMOVE_CAPMAX |
| 68 | CCBS_CHANGE_PACKAGE_SUBSCRIBER_REMOVE_CAPMAX | [CCBS_CHANGE_PACKAGE_SUBSCRIBER](../FMlogic/Request_CCBS_CHANGE_PACKAGE_SUBSCRIBER.html) | REMOVE | `count(Subscriber)>0 and (IS_REMOVE_FUP_GROUP=Y and CCBS+FCA or ATS_REMOVE)` | OMX_CHECK_REMOVE_FUP_GROUP | SBM_FUP_CHANGE_TOPPING_REMOVE |
| 69 | SBM_FUP_CHANGE_TOPPING_REMOVE | [SBM_FUP_CHANGE_TOPPING](../FMlogic/Request_SBM_FUP_CHANGE_TOPPING.html) | REMOVE \| CCBS | `//RawOUId and CCBS FSH>0 and FE FSH=0 and nonPP CCBS FSH\|FPL>0 and not ATS` | CCBS_CHANGE_PACKAGE_SUBSCRIBER_REMOVE_CAPMAX | SBM_FUP_CHANGE_PP |
| 70 | SBM_FUP_CHANGE_PP | [SBM_FUP_CHANGE_PP](../FMlogic/Request_SBM_FUP_CHANGE_PP.html) | — | `//RawOUId and Agreement/Offers[80] and OfferActivityDate!=FUT and CCBS FSH>0 and FE FSH>0 and nonPP CCBS>0 and not ATS` | SBM_FUP_CHANGE_TOPPING_REMOVE | SBM_FUP_CHANGE_TOPPING_ADD |
| 71 | SBM_FUP_CHANGE_TOPPING_ADD | [SBM_FUP_CHANGE_TOPPING](../FMlogic/Request_SBM_FUP_CHANGE_TOPPING.html) | ADD \| FE | `//RawOUId and CCBS FSH=0 and FE FSH>0 and nonPP CCBS FSH\|FPL>0` | SBM_FUP_CHANGE_PP | CCBS_ADD_PROPO_OU |
| 72 | CCBS_ADD_PROPO_OU | [CCBS_ADD_OFFER_AGREEMENT_POST](../FMlogic/Request_CCBS_ADD_OFFER_AGREEMENT_POST.html) | — | `//RawOUId and Agreement/Offers[ServiceType=85, FE] and OfferActivityDate!=FUT` | SBM_FUP_CHANGE_TOPPING_ADD | CCBS_RESOLVE_NXTPP_CODE |
| 73 | CCBS_RESOLVE_NXTPP_CODE | [CCBS_RESOLVE_SOC_CODE](../FMlogic/Request_CCBS_RESOLVE_SOC_CODE.html) | — | `boolean(//ExtendedInfo[OfferActivityDate!=FUT])` | CCBS_ADD_PROPO_OU | OMX_ADD_NXT_PP |
| 74 | OMX_ADD_NXT_PP | [OMX_ADD_NXT_PP](../FMlogic/Request_OMX_ADD_NXT_PP.html) | — | `OfferActivityDate!=FUT and FE_OR_CCBS=FE and ServiceType=80 and not ATS` | CCBS_RESOLVE_NXTPP_CODE | OMX_ADD_NEXT_OFFER |
| 75 | OMX_ADD_NEXT_OFFER | [OMX_ADD_NEXT_OFFER](../FMlogic/Request_OMX_ADD_NEXT_OFFER.html) | — | `not(EFF_ORD_DT) and SubscriberOffers[FE or BRMS, ServiceType!=80] and EFF_TYPE/EXP_TYPE not FUT and not LOGICALDATE_PROV and not ATS` | OMX_ADD_NXT_PP | OMX_EXP_FUT_PP |
| 76 | OMX_EXP_FUT_PP | [OMX_EXP_FUT_PP](../FMlogic/Request_OMX_EXP_FUT_PP.html) | — | `not(FUT_TYPE=NXTPP)` | OMX_ADD_NEXT_OFFER | OMX_EXP_FUT_OFFER |
| 77 | OMX_EXP_FUT_OFFER | [OMX_EXP_FUT_OFFER](../FMlogic/Request_OMX_EXP_FUT_OFFER.html) | — | `CHANGE_PP=Y and SubscriberOffers[FE or BRMS, ServiceType!=69][EFF_TYPE!=FUT][EXP_TYPE=FUT] and not ATS` | OMX_EXP_FUT_PP | OMX_EXP_FUT_RELATED_OFFER |
| 78 | OMX_EXP_FUT_RELATED_OFFER | [OMX_EXP_FUT_RELATED_OFFER](../FMlogic/Request_OMX_EXP_FUT_RELATED_OFFER.html) | — | `boolean(RelatedOffersArray[FE or BRMS][EFF_TYPE!=FUT][EXP_TYPE=FUT]) and not ATS` | OMX_EXP_FUT_OFFER | OMX_ADD_PROV |
| 79 | OMX_ADD_PROV | [OMX_ADD_PROV](../FMlogic/Request_OMX_ADD_PROV.html) | — | `//RawOUId and LargeCustomerIndicator=89 and OfferActivityDate!=FUT and Agreement/Offers[ServiceType=80]` | OMX_EXP_FUT_RELATED_OFFER | AA_GET_SWITCH_FEATURE_PP |
| 80 | AA_GET_SWITCH_FEATURE_PP | [AA_GET_SWITCH_FEATURE_PP](../FMlogic/Request_AA_GET_SWITCH_FEATURE_PP.html) | IGNORE_CCP=Y | `OfferActivityDate!=FUT and not PROVISIONING=N and not ATS` | OMX_ADD_PROV | OMX_GET_SRV_TRX_NO_MSIM_CDD |
| 81 | OMX_GET_SRV_TRX_NO_MSIM_CDD | [OMX_GET_SRV_TRX_NO_MSIM](../FMlogic/Request_OMX_GET_SRV_TRX_NO_MSIM.html) | CDD | `MultiSIMInfo/Master\|Minor[Source=PREV_MSIM] and OfferActivityDate!=FUT and Status!=67 and not PROVISIONING=N and not ATS` | AA_GET_SWITCH_FEATURE_PP | AA_ACTIVATE_SUBS_MSIM_CDD |
| 82 | AA_ACTIVATE_SUBS_MSIM_CDD | [AA_ACTIVATE_SUBS_MSIM](../FMlogic/Request_AA_ACTIVATE_SUBS_MSIM.html) | CDD \| UPDATE | Same as step 81 | OMX_GET_SRV_TRX_NO_MSIM_CDD | OMX_GET_SRV_TRX_NO_CDD |
| 83 | OMX_GET_SRV_TRX_NO_CDD | [OMX_GET_SRV_TRX_NO](../FMlogic/Request_OMX_GET_SRV_TRX_NO.html) | CDD | `not(MultiSIMInfo) and OfferActivityDate!=FUT and Status!=67 and not PROVISIONING=N and not ATS` | AA_ACTIVATE_SUBS_MSIM_CDD | AA_SEND_CDD |
| 84 | AA_SEND_CDD | [AA_ACTIVATE_SUBS](../FMlogic/Request_AA_ACTIVATE_SUBS.html) | CDD | Same as step 83 | OMX_GET_SRV_TRX_NO_CDD | AA_CONFIRM_CDD |
| 85 | AA_CONFIRM_CDD | [AA_CHECK_CONFIRMATION](../FMlogic/Request_AA_CHECK_CONFIRMATION.html) | CDD \| UPDATE_NETWORK_STATUS | `MultiSIMInfo or (OfferActivityDate!=FUT and Status!=67) and not PROVISIONING=N and not ATS` | AA_SEND_CDD | OMX_GET_SRV_TRX_NO_MSIM_SSU |
| 86 | OMX_GET_SRV_TRX_NO_MSIM_SSU | [OMX_GET_SRV_TRX_NO_MSIM](../FMlogic/Request_OMX_GET_SRV_TRX_NO_MSIM.html) | SSU | `MultiSIMInfo PREV_MSIM and OfferActivityDate!=FUT and SOC=50412 and Status!=67 and not PROVISIONING=N and not ATS` | AA_CONFIRM_CDD | AA_ACTIVATE_SUBS_MSIM_SSU |
| 87 | AA_ACTIVATE_SUBS_MSIM_SSU | [AA_ACTIVATE_SUBS_MSIM](../FMlogic/Request_AA_ACTIVATE_SUBS_MSIM.html) | SSU \| UPDATE | Same as step 86 | OMX_GET_SRV_TRX_NO_MSIM_SSU | OMX_GET_SRV_TRX_NO_SSU |
| 88 | OMX_GET_SRV_TRX_NO_SSU | [OMX_GET_SRV_TRX_NO](../FMlogic/Request_OMX_GET_SRV_TRX_NO.html) | SSU | `not(MultiSIMInfo) and OfferActivityDate!=FUT and SOC=50412 and Status!=67 and not PROVISIONING=N and not ATS` | AA_ACTIVATE_SUBS_MSIM_SSU | AA_SEND_SSU |
| 89 | AA_SEND_SSU | [AA_ACTIVATE_SUBS](../FMlogic/Request_AA_ACTIVATE_SUBS.html) | SSU | Same as step 88 | OMX_GET_SRV_TRX_NO_SSU | AA_CONFIRM_SSU |
| 90 | AA_CONFIRM_SSU | [AA_CHECK_CONFIRMATION](../FMlogic/Request_AA_CHECK_CONFIRMATION.html) | SSU | `MultiSIMInfo or (OfferActivityDate!=FUT and SOC=50412 and Status!=67) and not PROVISIONING=N and not ATS` | AA_SEND_SSU | OMX_GET_SRV_TRX_NO_MSIM_SUS |
| 91 | OMX_GET_SRV_TRX_NO_MSIM_SUS | [OMX_GET_SRV_TRX_NO_MSIM](../FMlogic/Request_OMX_GET_SRV_TRX_NO_MSIM.html) | SUS | `MultiSIMInfo PREV_MSIM and OfferActivityDate!=FUT and Status=83 and Status!=67 and not PROVISIONING=N and not ATS` | AA_CONFIRM_SSU | AA_ACTIVATE_SUBS_MSIM_SUS |
| 92 | AA_ACTIVATE_SUBS_MSIM_SUS | [AA_ACTIVATE_SUBS_MSIM](../FMlogic/Request_AA_ACTIVATE_SUBS_MSIM.html) | SUS \| UPDATE | Same as step 91 | OMX_GET_SRV_TRX_NO_MSIM_SUS | OMX_GET_SRV_TRX_NO_SUS |
| 93 | OMX_GET_SRV_TRX_NO_SUS | [OMX_GET_SRV_TRX_NO](../FMlogic/Request_OMX_GET_SRV_TRX_NO.html) | SUS | `not(MultiSIMInfo) and OfferActivityDate!=FUT and Status=83 and Status!=67 and not PROVISIONING=N and not ATS` | AA_ACTIVATE_SUBS_MSIM_SUS | AA_SEND_SUS |
| 94 | AA_SEND_SUS | [AA_ACTIVATE_SUBS](../FMlogic/Request_AA_ACTIVATE_SUBS.html) | SUS | Same as step 93 | OMX_GET_SRV_TRX_NO_SUS | ASRM_INVOKE_MINOR_SIM_ACTIVATE |
| 95 | ASRM_INVOKE_MINOR_SIM_ACTIVATE | [ASRM_INVOKE_MINOR_SIM](../FMlogic/Request_ASRM_INVOKE_MINOR_SIM.html) | ACTIVITY=ACTIVATE | `boolean(SubscriberOffers[FE or BRMS][TR_MULTISIM_IND=RES]) and not ATS` | AA_SEND_SUS | AA_CONFIRM_SUS |
| 96 | AA_CONFIRM_SUS | [AA_CHECK_CONFIRMATION](../FMlogic/Request_AA_CHECK_CONFIRMATION.html) | SUS | `MultiSIMInfo or (OfferActivityDate!=FUT and Status=83 and Status!=67) and not PROVISIONING=N and not ATS` | ASRM_INVOKE_MINOR_SIM_ACTIVATE | PSA_GET_DEVICE_INFO |
| 97 | PSA_GET_DEVICE_INFO | [PSA_GET_DEVICE_INFO](../FMlogic/Request_PSA_GET_DEVICE_INFO.html) | — | `boolean(SubscriberOffers[FE or BRMS][IMEI_KNOX!='']) and not ATS` | AA_CONFIRM_SUS | KNOX_SAVE_DEVICE |
| 98 | KNOX_SAVE_DEVICE | [KNOX_SAVE_DEVICE](../FMlogic/Request_KNOX_SAVE_DEVICE.html) | — | Same as step 97 | PSA_GET_DEVICE_INFO | OMX_NOTIFY_KNOX_EVENT |
| 99 | OMX_NOTIFY_KNOX_EVENT | [OMX_NOTI_TO_KAFKA](../FMlogic/Request_OMX_NOTI_TO_KAFKA.html) | knoxEvent=ADD | Same as step 97 | KNOX_SAVE_DEVICE | PSA_UPDATE_KNOX_STATUS |
| 100 | PSA_UPDATE_KNOX_STATUS | [PSA_UPDATE_KNOX_STATUS](../FMlogic/Request_PSA_UPDATE_KNOX_STATUS.html) | KNOX_STATUS=ACTIVE | Same as step 97 | OMX_NOTIFY_KNOX_EVENT | PSA_UPDATE_DEVICE |
| 101 | PSA_UPDATE_DEVICE | [PSA_UPDATE_DEVICE](../FMlogic/Request_PSA_UPDATE_DEVICE.html) | deviceStatus=ACTIVE | `count(Material[not(FE_OR_CCBS)])>0` | PSA_UPDATE_KNOX_STATUS | TDG_CREATE_SUBSCRIBER |
| 102 | TDG_CREATE_SUBSCRIBER | [TDG_CREATE_SUBSCRIBER](../FMlogic/Request_TDG_CREATE_SUBSCRIBER.html) | — | `boolean(SubscriberOffers[ServiceType=70])` | PSA_UPDATE_DEVICE | INTX_GET_OFFER_DETAIL |
| 103 | INTX_GET_OFFER_DETAIL | [INTX_GET_OFFER_DETAIL](../FMlogic/Request_INTX_GET_OFFER_DETAIL.html) | ADD | `Subscriber[MSISDN] and Channel!=CCBS and Channel!=OMX and (SubscriberOffers[80,FE\|CCBS] or Agreement/Offers[80,FE]) and not ATS` | TDG_CREATE_SUBSCRIBER | SMSGATEWAY_SEND_SMS |
| 104 | SMSGATEWAY_SEND_SMS | [SMSGATEWAY_SEND_SMS](../FMlogic/Request_SMSGATEWAY_SEND_SMS.html) | ADD | `Subscriber[MSISDN] and Channel!=CCBS and Channel!=OMX and CustomerType=73 and not ATS` | INTX_GET_OFFER_DETAIL | SBM_VALIDATE |
| 105 | SBM_VALIDATE | [SBM_VALIDATE](../FMlogic/Request_SBM_VALIDATE.html) | — | `boolean(SubscriberOffers[ServiceType=86][BRMS_REMOVE or ATS_REMOVE])` | SMSGATEWAY_SEND_SMS | SBM_CANCEL_DATA_PACK_IMMEDIATE |
| 106 | SBM_CANCEL_DATA_PACK_IMMEDIATE | [SBM_CANCEL_DATA_PACK_IMMEDIATE](../FMlogic/Request_SBM_CANCEL_DATA_PACK_IMMEDIATE.html) | — | `boolean(ServiceType=86[PackType=RC][BRMS_REMOVE] or ServiceType=86+RC and ATS_REMOVE)` | SBM_VALIDATE | SBM_UPDATE_EXPIRED |
| 107 | SBM_UPDATE_EXPIRED | [SBM_UPDATE_EXPIRED](../FMlogic/Request_SBM_UPDATE_EXPIRED.html) | — | `boolean(ServiceType=86[PackType=OC][BRMS_REMOVE] or ServiceType=86+OC and ATS_REMOVE)` | SBM_CANCEL_DATA_PACK_IMMEDIATE | SBM_BUY_DATA_PACK |
| 108 | SBM_BUY_DATA_PACK | [SBM_BUY_DATA_PACK](../FMlogic/Request_SBM_BUY_DATA_PACK.html) | — | `boolean(ServiceType=86[BRMS] or ServiceType=86 and ATS)` | SBM_UPDATE_EXPIRED | SBM_CANCEL_PACK_PREPAID |
| 109 | SBM_CANCEL_PACK_PREPAID | [SBM_CANCEL_PACK_PREPAID](../FMlogic/Request_SBM_CANCEL_PACK_PREPAID.html) | — | `FE_OR_CCBS=BRMS_REMOVE and ServiceType=88 and (EXP_TYPE absent or EXP_TYPE!=FUT) and not ATS` | SBM_BUY_DATA_PACK | BL_CREATE_CHARGE |
| 110 | BL_CREATE_CHARGE | [BL_CREATE_CHARGE](../FMlogic/Request_BL_CREATE_CHARGE.html) | — | `boolean(ServiceType=79[BRMS] or ServiceType=79 and ATS)` | SBM_CANCEL_PACK_PREPAID | CCBS_CHANGE_PACKAGE_SUBSCRIBER |
| 111 | CCBS_CHANGE_PACKAGE_SUBSCRIBER | [CCBS_CHANGE_PACKAGE_SUBSCRIBER](../FMlogic/Request_CCBS_CHANGE_PACKAGE_SUBSCRIBER.html) | ADD | `boolean(ServiceType=86[BRMS] or ServiceType=85\|86\|68 and ATS)` | BL_CREATE_CHARGE | MCS_REGISTER_SUBSCRIPTION |
| 112 | MCS_REGISTER_SUBSCRIPTION | [MCS_REGISTER_SUBSCRIPTION](../FMlogic/Request_MCS_REGISTER_SUBSCRIPTION.html) | — | `boolean(SubscriberOffers[BRMS or FE, ServiceType=69, not TPC])` | CCBS_CHANGE_PACKAGE_SUBSCRIBER | MCS_REGISTER |
| 113 | MCS_REGISTER | [MCS_REGISTER](../FMlogic/Request_MCS_REGISTER.html) | — | `boolean(SubscriberOffers[ServiceType=85\|69, FE, TPC])` | MCS_REGISTER_SUBSCRIPTION | BDH_INSTALLMENT_SALE |
| 114 | BDH_INSTALLMENT_SALE | [BDH_INSTALLMENT_SALE](../FMlogic/Request_BDH_INSTALLMENT_SALE.html) | — | `boolean(SubscriberOffers[FE]/RelatedOffersArray[TR_OFFER_GROUP=CT_INST])` | MCS_REGISTER | CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO |
| 115 | CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO | [CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO](../FMlogic/Request_CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO.html) | — | `count(IMSIAlias)>0 and not ATS` | BDH_INSTALLMENT_SALE | CCBS_UPDATE_ACCOUNT_NAME_ADDRESS |
| 116 | CCBS_UPDATE_ACCOUNT_NAME_ADDRESS | [CCBS_UPDATE_ACCOUNT_NAME_ADDRESS](../FMlogic/Request_CCBS_UPDATE_ACCOUNT_NAME_ADDRESS.html) | — | `count(PayChannelFeeInfo)>0` | CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO | CCBS_CREATE_MEMO_FOR_SBM |
| 117 | CCBS_CREATE_MEMO_FOR_SBM | [CCBS_CREATE_MEMO_FOR_SBM](../FMlogic/Request_CCBS_CREATE_MEMO_FOR_SBM.html) | ENTITY_TYPE_ID=6 \| MEMO_TYPE_ID=90051 \| MEMO_SYSTEM_TEXT=082 | `boolean(ServiceType=86[BRMS]) and not ATS` | CCBS_UPDATE_ACCOUNT_NAME_ADDRESS | OMX_UPDATE_FE_OR_CCBS_VALUE |
| 118 | OMX_UPDATE_FE_OR_CCBS_VALUE | ~~OMX_UPDATE_FE_OR_CCBS_VALUE~~ ⚠ Not Found | CCBS | `ServiceType!=80 and SwitchFeature exists (FE or BRMS) and not ATS` | CCBS_CREATE_MEMO_FOR_SBM | OMX_POPULATE_MSIM_INFO_ADD |
| 119 | OMX_POPULATE_MSIM_INFO_ADD | [OMX_POPULATE_MSIM_INFO](../FMlogic/Request_OMX_POPULATE_MSIM_INFO.html) | — | `boolean(SubscriberOffers[FE or BRMS][TR_MULTISIM_IND=RES\|REE]) and not ATS` | OMX_UPDATE_FE_OR_CCBS_VALUE | OMX_GET_SRV_TRX_NO_MSIM_ADD |
| 120 | OMX_GET_SRV_TRX_NO_MSIM_ADD | [OMX_GET_SRV_TRX_NO_MSIM](../FMlogic/Request_OMX_GET_SRV_TRX_NO_MSIM.html) | CCD | `boolean(MultiSIMInfo/Minor[Source=FE]) and not PROVISIONING=N and not ATS` | OMX_POPULATE_MSIM_INFO_ADD | AA_ACTIVATE_SUBS_MSIM_ADD |
| 121 | AA_ACTIVATE_SUBS_MSIM_ADD | [AA_ACTIVATE_SUBS_MSIM](../FMlogic/Request_AA_ACTIVATE_SUBS_MSIM.html) | CCD \| ADD | Same as step 120 | OMX_GET_SRV_TRX_NO_MSIM_ADD | ATS_DEBUNDLE_CAMPAIGN |
| 122 | ATS_DEBUNDLE_CAMPAIGN | [ATS_DEBUNDLE_CAMPAIGN](../FMlogic/Request_ATS_DEBUNDLE_CAMPAIGN.html) | — | `count(BundleInfo[ConvergenceAction=DebundleCampaign\|DebundleProductNumber])>0` | AA_ACTIVATE_SUBS_MSIM_ADD | OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE |
| 123 | OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE | [OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE](../FMlogic/Request_OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE.html) | — | Same as step 122 | ATS_DEBUNDLE_CAMPAIGN | SEND_SMS_MESSAGE_3CJ |
| 124 | SEND_SMS_MESSAGE_3CJ | [SEND_SMS_MESSAGE_3CJ](../FMlogic/Request_SEND_SMS_MESSAGE_3CJ.html) | — | Same as step 122 | OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE | MCS_GET_PACKCODE |
| 125 | MCS_GET_PACKCODE | [MCS_GET_PACKCODE](../FMlogic/Request_MCS_GET_PACKCODE.html) | — | — | SEND_SMS_MESSAGE_3CJ | MCS_CANCEL_AFTER_SALE |
| 126 | MCS_CANCEL_AFTER_SALE | [MCS_CANCEL_AFTER_SALE](../FMlogic/Request_MCS_CANCEL_AFTER_SALE.html) | OFFER_NAME=Priceplan | `boolean(//Subscriber[MCS_CANCEL_AFS=Y])` | MCS_GET_PACKCODE | TMN_CREATE_WALLET_MINIMAL_PROFILE |
| 127 | TMN_CREATE_WALLET_MINIMAL_PROFILE | [TMN_CREATE_WALLET_MINIMAL_PROFILE](../FMlogic/Request_TMN_CREATE_WALLET_MINIMAL_PROFILE.html) | — | `/ns0:OrderRequest/OrderData/Customer/CustomerTypeInfo/Type/text()=73` | MCS_CANCEL_AFTER_SALE | END |

---

## §3 — PreExecCheck Details

### Step 1 — CCBS_GET_AGREEMENT_INFO
**FM:** `CCBS_GET_AGREEMENT_INFO`
```xpath
boolean(//OUId[./text()] and not(//Subscriber/SubscriberOffers))
```

### Step 2 — CCBS_GET_CUST_ACC_SUB_ID
**FM:** `CCBS_GET_CUST_ACC_SUB_ID`
```xpath
boolean(//Subscriber/MSISDN[./text()] and //Subscriber/SubscriberOffers)
```

### Step 4 — CCBS_GET_SUBS_INFO
**FM:** `CCBS_GET_SUBS_INFO`
```xpath
boolean(//Subscriber/MSISDN[./text()] and //Subscriber/SubscriberOffers and (//Subscriber[Status !=67 and Status !=76 and Status !=84]))
```

### Step 9 — CCBS_GET_AGREEMENT_INFO_FOR_SHAREPLAN
**FM:** `CCBS_GET_AGREEMENT_INFO`
```xpath
not(//Agreement/Offers/ExtendedInfo[Name[.='FE_OR_CCBS'] and Value[.='CCBS']])
```

### Step 14 — CCBS_GOD
**FM:** `CCBS_GOD`
```xpath
boolean(//ServiceType != 70)
```

### Step 15 — GET_PROFILE_FROM_CCP_ALL
**FM:** `GET_PROFILE_FROM_CCP_ALL`
```xpath
substring(//Customer/Account/AccountManagementInfo/AccountSubType/text(),1,2)='HY'
```

### Step 17 — OMX_REMOVE_RELATED_OFFER_FCVBAR ⚠ Not Found
**FM:** `OMX_REMOVE_RELATED_OFFER_FROM_PP`
```xpath
not(//SubscriberOffers[ExtendedInfo[Name='FE_OR_CCBS' and Value='CCBS']][Soc[.='41861']]
    or //SubscriberOffers[ExtendedInfo[Name='FE_OR_CCBS' and Value='CCBS']]/RelatedOffersArray[Soc[.='41861']])
```

### Step 19 — MCS_GET_CHARGE_INFO
**FM:** `MCS_GET_CHARGE_INFO`
```xpath
boolean(//SubscriberOffers[(ServiceType='85' or ServiceType='69') and ExtendedInfo[Name='FE_OR_CCBS' and Value='FE'] and contains(SocProperties,'TR_SPECIAL_OFFER_IND=TPC')])
```

### Step 22 — OMX_GET_OFFER_RATE_PP
**FM:** `OMX_GET_OFFER_RATE`
```xpath
boolean(//SubscriberOffers[ExtendedInfo[Name='FE_OR_CCBS' and Value='FE'] and ServiceType='80'])
```

### Step 23 — OMX_CAL_OFFER_FUT_DATE
**FM:** `OMX_CAL_OFFER_FUT_DATE`
```xpath
boolean(//Subscriber/SubscriberOffers[1] and //SubscriberOffers[ExtendedInfo[Name='FE_OR_CCBS' and (Value='FE' or Value='BRMS')]])
or boolean(//Agreement/Offers[ExtendedInfo[Name[.='FE_OR_CCBS'] and Value[.='FE']]])
```

### Step 27 — ATS_ENQUIRY_CAMPAIGN
**FM:** `ATS_ENQUIRY_CAMPAIGN`
```xpath
exists(//Subscriber/MSISDN[./text()])
and not(boolean(//Subscriber/SubscriberOffers[ServiceType[.='80']][ExtendedInfo[Name[.='OfferActivityDate'] and Value[.='FUT']]])
        or boolean(//Agreement/Offers[ServiceType[.='80']][ExtendedInfo[Name[.='OfferActivityDate'] and Value[.='FUT']]]))
```

### Step 34 — ASRM_INVOKE_MINOR_SIM_RESERVE
**FM:** `ASRM_INVOKE_MINOR_SIM`
```xpath
boolean(//SubscriberOffers[ExtendedInfo[Name='FE_OR_CCBS' and (Value='FE' or Value='BRMS')]])
and boolean(//SubscriberOffers[ExtendedInfo[Name='TR_MULTISIM_IND' and Value='RES']])
and boolean(//Subscriber[not(ExtendedInfo[Name='FE_OR_CCBS']) or (ExtendedInfo[Name='FE_OR_CCBS' and Value!='ATS'])])
```

### Step 37 — OMX_BRMS_DB
**FM:** `OMX_BRMS_DB`
```xpath
boolean(//Subscriber[MSISDN/text()][1])
and (boolean(//Subscriber/SubscriberOffers/ExtendedInfo[Name[.='OfferActivityDate'] and Value[.!='FUT']])
  or (boolean(//Subscriber/SubscriberOffers[name[.='MULSIM000000001'] or name[.='MULSIM000000002']
      or name[.='MULSIM000000003']][ExtendedInfo[Name[.='FE_OR_CCBS'] and Value[.='FE']]])))
or (Channel='ISERVICE' or Channel='FUT_ISERVICE')
and boolean(//Subscriber[not(ExtendedInfo[Name='FE_OR_CCBS']) or (ExtendedInfo[Name='FE_OR_CCBS' and Value!='ATS'])])
```

### Step 40 — OMX_POPULATE_OFFER_PROMOEND ⚠ Not Found
**FM:** `OMX_POPULATE_OFFER`
```xpath
//Customer/CustomerTypeInfo/Type=73
and count(//Subscriber/SubscriberOffers[OfferName='RMVX00000000001'])=0
and count(//Subscriber[ExtendedInfo[Name='FE_OR_CCBS' and Value='ATS']])=0
```

### Step 41 — CCBS_GOD_BRMS
**FM:** `CCBS_GOD`
```xpath
boolean(//SubscriberOffers[ExtendedInfo[Name[.='FE_OR_CCBS'] and Value[.='BRMS']]])
or boolean(//Subscriber/SubscriberOffers[OfferName='RMVX00000000001' and ExtendedInfo[Name='FE_OR_CCBS' and Value='FE']])
or boolean(//Subscriber[ExtendedInfo[Name='FE_OR_CCBS' and Value='ATS']])
```

### Step 42 — OMX_GET_OFFER_RATE
**FM:** `OMX_GET_OFFER_RATE`
```xpath
boolean(//SubscriberOffers[ExtendedInfo[Name='FE_OR_CCBS' and (Value='FE' or Value='CCBS')] and ServiceType='80']
        and count(//Subscriber/ExtendedInfo[Name='CampaignCode'])>0)
```

### Step 43 — ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN
**FM:** `ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN`
```xpath
count(//BundleInfo[ConvergenceType='MobileSoftBundle'])>0
```

### Step 44 — OMX_OFFER_INCLUSION_BRMS
**FM:** `OMX_OFFER_INCLUSION`
```xpath
boolean(//SubscriberOffers[ExtendedInfo[Name[.='FE_OR_CCBS'] and Value[.='BRMS']]])
and boolean(//Subscriber[not(ExtendedInfo[Name='FE_OR_CCBS']) or (ExtendedInfo[Name='FE_OR_CCBS' and Value!='ATS'])])
```

### Step 46 — OMX_CAL_PP_EXPIRE_DATE ⚠ Not Found
**FM:** `OMX_CAL_PP_EXPIRE_DATE`
```xpath
boolean(//Subscriber/SubscriberOffers[OfferName='RMVX00000000001'])
and count(//Subscriber[ExtendedInfo[Name='FE_OR_CCBS' and Value='ATS']])=0
```

### Step 49 — CCBS_CHANGE_PP_SUB
**FM:** `CCBS_CHANGE_PP_SUB`
```xpath
boolean(//Subscriber[MSISDN/text()][1])
and boolean(//Subscriber/SubscriberOffers/ExtendedInfo[Name[.='OfferActivityDate'] and Value[.!='FUT']])
and boolean(//Subscriber[not(ExtendedInfo[Name='FE_OR_CCBS']) or (ExtendedInfo[Name='FE_OR_CCBS' and Value!='ATS'])])
```

### Step 50 — CCBS_UPDATE_PARAMETER_PROMOEND
**FM:** `CCBS_UPDATE_PARAMETER_SUBSCRIBER_POST`
```xpath
boolean(//Subscriber/ExtendedInfo[Name='CHANGE_PP' and Value='Y'])
and boolean(//Subscriber/SubscriberOffers[OfferName='RMVX00000000001' and ExtendedInfo[Name='FE_OR_CCBS' and Value='CCBS']])
and count(//Subscriber[ExtendedInfo[Name='FE_OR_CCBS' and Value='ATS']])=0
```

### Step 52 — OMX_CAL_ACCT_SUB_TYPE ⚠ Not Found
**FM:** `OMX_CAL_ACCT_SUB_TYPE`
```xpath
not(starts-with(/ns0:OrderRequest/OrderData/Channel,'FUT_'))
and (boolean(//SubscriberOffers[ExtendedInfo[Name='FE_OR_CCBS' and Value='CCBS']
             and contains(SocProperties,'TR_SPECIAL_OFFER_IND=CPEPR') and ServiceType='80'])
  or (boolean(//Customer/Account/AccountManagementInfo/AccountSubType='CPE')
      and boolean(//SubscriberOffers[ExtendedInfo[Name='FE_OR_CCBS' and Value='FE']
                  and not(contains(SocProperties,'TR_SPECIAL_OFFER_IND=CPEPR')) and ServiceType='80'])))
```

### Step 56 — CCBS_GET_SUBS_LIST
**FM:** `CCBS_GET_SUBS_LIST`
```xpath
boolean(//RawOUId[./text()]) and boolean(//Agreement/Offers/ExtendedInfo[Name[.='OfferActivityDate'] and Value[.!='FUT']])
```

### Step 62 — SBM_FUP_CREATE_GROUP
**FM:** `SBM_FUP_CREATE_GROUP`
```xpath
boolean(//RawOUId[./text()])
and count(//Agreement/Offers[ServiceType[.='80']][ExtendedInfo[Name='FE_OR_CCBS' and Value='CCBS']]
          [ExtendedInfo[Name='SPECIAL_OFFER_INDICATOR' and (Value='FSH' or Value='FPL')]])=0
and count(//Agreement/Offers[ServiceType[.='80']][ExtendedInfo[Name='FE_OR_CCBS' and Value='FE']]
          [ExtendedInfo[Name='SPECIAL_OFFER_INDICATOR' and (Value='FSH' or Value='FPL')]])>0
and count(//Agreement/Offers[ServiceType[.!='80']][ExtendedInfo[Name='FE_OR_CCBS' and Value='CCBS']]
          [ExtendedInfo[Name='SPECIAL_OFFER_INDICATOR' and (Value='FSH' or Value='FPL')]])=0
```

### Step 67 — OMX_CHECK_REMOVE_FUP_GROUP ⚠ Not Found
**FM:** `OMX_CHECK_REMOVE_FUP_GROUP`
```xpath
boolean(//Subscriber[not(ExtendedInfo[Name='FE_OR_CCBS']) or (ExtendedInfo[Name='FE_OR_CCBS' and Value!='ATS'])])
```

### Step 74 — OMX_ADD_NXT_PP
**FM:** `OMX_ADD_NXT_PP`
```xpath
boolean(//ExtendedInfo[Name[.='OfferActivityDate'] and Value[.!='FUT']])
and boolean(//ExtendedInfo[Name[.='FE_OR_CCBS'] and Value[.='FE']])
and boolean(//ServiceType[.='80'])
and boolean(//Subscriber[not(ExtendedInfo[Name='FE_OR_CCBS']) or (ExtendedInfo[Name='FE_OR_CCBS' and Value!='ATS'])])
```

### Step 76 — OMX_EXP_FUT_PP
**FM:** `OMX_EXP_FUT_PP`
```xpath
not(boolean(//OrderData/ExtendedInfo[Name='FUT_TYPE' and Value='NXTPP']))
```

### Step 77 — OMX_EXP_FUT_OFFER
**FM:** `OMX_EXP_FUT_OFFER`
```xpath
boolean(//Subscriber/ExtendedInfo[Name='CHANGE_PP' and Value='Y'])
and boolean(//Subscriber/SubscriberOffers[1]
            and //SubscriberOffers[ServiceType!='69'
                and ExtendedInfo[Name='FE_OR_CCBS' and (Value='FE' or Value='BRMS')]
                and ExtendedInfo[Name='EFF_TYPE' and Value!='FUT']
                and ExtendedInfo[Name='EXP_TYPE' and Value='FUT']])
and boolean(//Subscriber[not(ExtendedInfo[Name='FE_OR_CCBS']) or (ExtendedInfo[Name='FE_OR_CCBS' and Value!='ATS'])])
```

### Step 79 — OMX_ADD_PROV
**FM:** `OMX_ADD_PROV`
```xpath
boolean(//RawOUId[./text()])
and boolean(//Customer/CustomerGeneralInfo/LargeCustomerIndicator=89)
and boolean(//Agreement/Offers/ExtendedInfo[Name[.='OfferActivityDate'] and Value[.!='FUT']])
and boolean(//Agreement/Offers[ServiceType[.='80']])
```

### Step 80 — AA_GET_SWITCH_FEATURE_PP
**FM:** `AA_GET_SWITCH_FEATURE_PP`
```xpath
boolean(//ExtendedInfo[Name[.='OfferActivityDate'] and Value[.!='FUT']])
and not(boolean(//OrderData/ExtendedInfo[Name='PROVISIONING' and Value='N']))
and boolean(//Subscriber[not(ExtendedInfo[Name='FE_OR_CCBS']) or (ExtendedInfo[Name='FE_OR_CCBS' and Value!='ATS'])])
```

> Steps 81–127 PreExecCheck details available in the companion HTML at `output/order/CHANGE_PP.html`

---

## §4 — FM Documentation Index

| FM (ActivityID) | Used in Steps | Doc Link | Status |
|-----------------|---------------|----------|--------|
| CCBS_GET_AGREEMENT_INFO | 1, 9 | [Request_CCBS_GET_AGREEMENT_INFO.html](../FMlogic/Request_CCBS_GET_AGREEMENT_INFO.html) | ✓ Generated |
| CCBS_GET_CUST_ACC_SUB_ID | 2, 28 | [Request_CCBS_GET_CUST_ACC_SUB_ID.html](../FMlogic/Request_CCBS_GET_CUST_ACC_SUB_ID.html) | ✓ Generated |
| CCBS_GET_SUBSCRIBER_HEADER | 3, 31 | [Request_CCBS_GET_SUBSCRIBER_HEADER.html](../FMlogic/Request_CCBS_GET_SUBSCRIBER_HEADER.html) | ✓ Generated |
| CCBS_GET_SUBS_INFO | 4, 33, 57 | [Request_CCBS_GET_SUBS_INFO.html](../FMlogic/Request_CCBS_GET_SUBS_INFO.html) | ✓ Generated |
| CCBS_GET_CUSTOMER_HEADER | 5, 32 | [Request_CCBS_GET_CUSTOMER_HEADER.html](../FMlogic/Request_CCBS_GET_CUSTOMER_HEADER.html) | ✓ Generated |
| CCBS_GET_ACCOUNT_HEADER | 6, 29 | [Request_CCBS_GET_ACCOUNT_HEADER.html](../FMlogic/Request_CCBS_GET_ACCOUNT_HEADER.html) | ✓ Generated |
| CCBS_GET_BA_HEADER | 7 | [Request_CCBS_GET_BA_HEADER.html](../FMlogic/Request_CCBS_GET_BA_HEADER.html) | ✓ Generated |
| CCBS_GET_AGREEMENT_HEADER | 8, 30 | [Request_CCBS_GET_AGREEMENT_HEADER.html](../FMlogic/Request_CCBS_GET_AGREEMENT_HEADER.html) | ✓ Generated |
| OMX_GET_SHAREPLAN_OU_SOC_REMOVE | 10 | [Request_OMX_GET_SHAREPLAN_OU_SOC_REMOVE.html](../FMlogic/Request_OMX_GET_SHAREPLAN_OU_SOC_REMOVE.html) | ✓ Generated |
| OMX_GET_SHAREPLAN_OU_SOC | 11 | [Request_OMX_GET_SHAREPLAN_OU_SOC.html](../FMlogic/Request_OMX_GET_SHAREPLAN_OU_SOC.html) | ✓ Generated |
| CCBS_L9_GET_CUGID_BY_AGREEMENTID | 12 | [Request_CCBS_L9_GET_CUGID_BY_AGREEMENTID.html](../FMlogic/Request_CCBS_L9_GET_CUGID_BY_AGREEMENTID.html) | ✓ Generated |
| CCBS_RESOLVE_SOC_CODE | 13, 38, 73 | [Request_CCBS_RESOLVE_SOC_CODE.html](../FMlogic/Request_CCBS_RESOLVE_SOC_CODE.html) | ✓ Generated |
| CCBS_GOD | 14, 41 | [Request_CCBS_GOD.html](../FMlogic/Request_CCBS_GOD.html) | ✓ Generated |
| GET_PROFILE_FROM_CCP_ALL | 15 | [Request_GET_PROFILE_FROM_CCP_ALL.html](../FMlogic/Request_GET_PROFILE_FROM_CCP_ALL.html) | ✓ Generated |
| OMX_OFFER_INCLUSION | 16, 44 | [Request_OMX_OFFER_INCLUSION.html](../FMlogic/Request_OMX_OFFER_INCLUSION.html) | ✓ Generated |
| OMX_REMOVE_RELATED_OFFER_FROM_PP | 17 | — | ⚠ Not Found |
| GET_SPECIAL_OFFER_INDICATOR | 18 | [Request_GET_SPECIAL_OFFER_INDICATOR.html](../FMlogic/Request_GET_SPECIAL_OFFER_INDICATOR.html) | ✓ Generated |
| MCS_GET_CHARGE_INFO | 19 | [Request_MCS_GET_CHARGE_INFO.html](../FMlogic/Request_MCS_GET_CHARGE_INFO.html) | ✓ Generated |
| OMX_CAL_PP_EFF_DATE | 20 | — | ⚠ Not Found |
| OMX_SEARCH_FUT | 21 | [Request_OMX_SEARCH_FUT.html](../FMlogic/Request_OMX_SEARCH_FUT.html) | ✓ Generated |
| OMX_GET_OFFER_RATE | 22, 42 | [Request_OMX_GET_OFFER_RATE.html](../FMlogic/Request_OMX_GET_OFFER_RATE.html) | ✓ Generated |
| OMX_CAL_OFFER_FUT_DATE | 23, 45 | [Request_OMX_CAL_OFFER_FUT_DATE.html](../FMlogic/Request_OMX_CAL_OFFER_FUT_DATE.html) | ✓ Generated |
| OMX_SEARCH_FUT_PP | 24 | [Request_OMX_SEARCH_FUT_PP.html](../FMlogic/Request_OMX_SEARCH_FUT_PP.html) | ✓ Generated |
| CCBS_OFFER_EXCLUSION | 25 | [Request_CCBS_OFFER_EXCLUSION.html](../FMlogic/Request_CCBS_OFFER_EXCLUSION.html) | ✓ Generated |
| OMX_BIZ_VAL | 26 | [Request_OMX_BIZ_VAL.html](../FMlogic/Request_OMX_BIZ_VAL.html) | ✓ Generated |
| ATS_ENQUIRY_CAMPAIGN | 27 | [Request_ATS_ENQUIRY_CAMPAIGN.html](../FMlogic/Request_ATS_ENQUIRY_CAMPAIGN.html) | ✓ Generated |
| ASRM_INVOKE_MINOR_SIM | 34, 95 | [Request_ASRM_INVOKE_MINOR_SIM.html](../FMlogic/Request_ASRM_INVOKE_MINOR_SIM.html) | ✓ Generated |
| OMX_ADD_FUT_PP | 35 | [Request_OMX_ADD_FUT_PP.html](../FMlogic/Request_OMX_ADD_FUT_PP.html) | ✓ Generated |
| OMX_ADD_FUT_OFFER | 36, 47 | [Request_OMX_ADD_FUT_OFFER.html](../FMlogic/Request_OMX_ADD_FUT_OFFER.html) | ✓ Generated |
| OMX_BRMS_DB | 37 | [Request_OMX_BRMS_DB.html](../FMlogic/Request_OMX_BRMS_DB.html) | ✓ Generated |
| OMX_RESOLVE_SOC_DATA | 39 | [Request_OMX_RESOLVE_SOC_DATA.html](../FMlogic/Request_OMX_RESOLVE_SOC_DATA.html) | ✓ Generated |
| OMX_POPULATE_OFFER | 40 | — | ⚠ Not Found |
| ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN | 43 | [Request_ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN.html](../FMlogic/Request_ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN.html) | ✓ Generated |
| OMX_CAL_PP_EXPIRE_DATE | 46 | — | ⚠ Not Found |
| INTX_GET_MASTER_MINOR_SIM_INFO | 48 | [Request_INTX_GET_MASTER_MINOR_SIM_INFO.html](../FMlogic/Request_INTX_GET_MASTER_MINOR_SIM_INFO.html) | ✓ Generated |
| CCBS_CHANGE_PP_SUB | 49 | [Request_CCBS_CHANGE_PP_SUB.html](../FMlogic/Request_CCBS_CHANGE_PP_SUB.html) | ✓ Generated |
| CCBS_UPDATE_PARAMETER_SUBSCRIBER_POST | 50 | [Request_CCBS_UPDATE_PARAMETER_SUBSCRIBER_POST.html](../FMlogic/Request_CCBS_UPDATE_PARAMETER_SUBSCRIBER_POST.html) | ✓ Generated |
| CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO | 51 | [Request_CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO.html](../FMlogic/Request_CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO.html) | ✓ Generated |
| OMX_CAL_ACCT_SUB_TYPE | 52 | — | ⚠ Not Found |
| CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO | 53, 54 | [Request_CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO.html](../FMlogic/Request_CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO.html) | ✓ Generated |
| CCBS_UPDATE_ACCT_COLLECTION_FIX_INFO | 55 | [Request_CCBS_UPDATE_ACCT_COLLECTION_FIX_INFO.html](../FMlogic/Request_CCBS_UPDATE_ACCT_COLLECTION_FIX_INFO.html) | ✓ Generated |
| CCBS_GET_SUBS_LIST | 56 | [Request_CCBS_GET_SUBS_LIST.html](../FMlogic/Request_CCBS_GET_SUBS_LIST.html) | ✓ Generated |
| CCBS_ADD_PP_OU | 58 | [Request_CCBS_ADD_PP_OU.html](../FMlogic/Request_CCBS_ADD_PP_OU.html) | ✓ Generated |
| CCBS_CHANGE_PP_OU | 59 | [Request_CCBS_CHANGE_PP_OU.html](../FMlogic/Request_CCBS_CHANGE_PP_OU.html) | ✓ Generated |
| CCBS_UPDATE_AGREEMENT_ON_UNIT | 60, 61 | [Request_CCBS_UPDATE_AGREEMENT_ON_UNIT.html](../FMlogic/Request_CCBS_UPDATE_AGREEMENT_ON_UNIT.html) | ✓ Generated |
| SBM_FUP_CREATE_GROUP | 62 | [Request_SBM_FUP_CREATE_GROUP.html](../FMlogic/Request_SBM_FUP_CREATE_GROUP.html) | ✓ Generated |
| SBM_FUP_DELETE_GROUP | 63 | [Request_SBM_FUP_DELETE_GROUP.html](../FMlogic/Request_SBM_FUP_DELETE_GROUP.html) | ✓ Generated |
| INTX_GET_CURRENT_SPECIALOFFERINDICATORLIST_BY_OU | 64, 65 | [Request_INTX_GET_CURRENT_SPECIALOFFERINDICATORLIST_BY_OU.html](../FMlogic/Request_INTX_GET_CURRENT_SPECIALOFFERINDICATORLIST_BY_OU.html) | ✓ Generated |
| SBM_FUP_CHANGE_MEMBER | 66 | [Request_SBM_FUP_CHANGE_MEMBER.html](../FMlogic/Request_SBM_FUP_CHANGE_MEMBER.html) | ✓ Generated |
| OMX_CHECK_REMOVE_FUP_GROUP | 67 | — | ⚠ Not Found |
| CCBS_CHANGE_PACKAGE_SUBSCRIBER | 68, 111 | [Request_CCBS_CHANGE_PACKAGE_SUBSCRIBER.html](../FMlogic/Request_CCBS_CHANGE_PACKAGE_SUBSCRIBER.html) | ✓ Generated |
| SBM_FUP_CHANGE_TOPPING | 69, 71 | [Request_SBM_FUP_CHANGE_TOPPING.html](../FMlogic/Request_SBM_FUP_CHANGE_TOPPING.html) | ✓ Generated |
| SBM_FUP_CHANGE_PP | 70 | [Request_SBM_FUP_CHANGE_PP.html](../FMlogic/Request_SBM_FUP_CHANGE_PP.html) | ✓ Generated |
| CCBS_ADD_OFFER_AGREEMENT_POST | 72 | [Request_CCBS_ADD_OFFER_AGREEMENT_POST.html](../FMlogic/Request_CCBS_ADD_OFFER_AGREEMENT_POST.html) | ✓ Generated |
| OMX_ADD_NXT_PP | 74 | [Request_OMX_ADD_NXT_PP.html](../FMlogic/Request_OMX_ADD_NXT_PP.html) | ✓ Generated |
| OMX_ADD_NEXT_OFFER | 75 | [Request_OMX_ADD_NEXT_OFFER.html](../FMlogic/Request_OMX_ADD_NEXT_OFFER.html) | ✓ Generated |
| OMX_EXP_FUT_PP | 76 | [Request_OMX_EXP_FUT_PP.html](../FMlogic/Request_OMX_EXP_FUT_PP.html) | ✓ Generated |
| OMX_EXP_FUT_OFFER | 77 | [Request_OMX_EXP_FUT_OFFER.html](../FMlogic/Request_OMX_EXP_FUT_OFFER.html) | ✓ Generated |
| OMX_EXP_FUT_RELATED_OFFER | 78 | [Request_OMX_EXP_FUT_RELATED_OFFER.html](../FMlogic/Request_OMX_EXP_FUT_RELATED_OFFER.html) | ✓ Generated |
| OMX_ADD_PROV | 79 | [Request_OMX_ADD_PROV.html](../FMlogic/Request_OMX_ADD_PROV.html) | ✓ Generated |
| AA_GET_SWITCH_FEATURE_PP | 80 | [Request_AA_GET_SWITCH_FEATURE_PP.html](../FMlogic/Request_AA_GET_SWITCH_FEATURE_PP.html) | ✓ Generated |
| OMX_GET_SRV_TRX_NO_MSIM | 81, 86, 91, 120 | [Request_OMX_GET_SRV_TRX_NO_MSIM.html](../FMlogic/Request_OMX_GET_SRV_TRX_NO_MSIM.html) | ✓ Generated |
| AA_ACTIVATE_SUBS_MSIM | 82, 87, 92, 121 | [Request_AA_ACTIVATE_SUBS_MSIM.html](../FMlogic/Request_AA_ACTIVATE_SUBS_MSIM.html) | ✓ Generated |
| OMX_GET_SRV_TRX_NO | 83, 88, 93 | [Request_OMX_GET_SRV_TRX_NO.html](../FMlogic/Request_OMX_GET_SRV_TRX_NO.html) | ✓ Generated |
| AA_ACTIVATE_SUBS | 84, 89, 94 | [Request_AA_ACTIVATE_SUBS.html](../FMlogic/Request_AA_ACTIVATE_SUBS.html) | ✓ Generated |
| AA_CHECK_CONFIRMATION | 85, 90, 96 | [Request_AA_CHECK_CONFIRMATION.html](../FMlogic/Request_AA_CHECK_CONFIRMATION.html) | ✓ Generated |
| PSA_GET_DEVICE_INFO | 97 | [Request_PSA_GET_DEVICE_INFO.html](../FMlogic/Request_PSA_GET_DEVICE_INFO.html) | ✓ Generated |
| KNOX_SAVE_DEVICE | 98 | [Request_KNOX_SAVE_DEVICE.html](../FMlogic/Request_KNOX_SAVE_DEVICE.html) | ✓ Generated |
| OMX_NOTI_TO_KAFKA | 99 | [Request_OMX_NOTI_TO_KAFKA.html](../FMlogic/Request_OMX_NOTI_TO_KAFKA.html) | ✓ Generated |
| PSA_UPDATE_KNOX_STATUS | 100 | [Request_PSA_UPDATE_KNOX_STATUS.html](../FMlogic/Request_PSA_UPDATE_KNOX_STATUS.html) | ✓ Generated |
| PSA_UPDATE_DEVICE | 101 | [Request_PSA_UPDATE_DEVICE.html](../FMlogic/Request_PSA_UPDATE_DEVICE.html) | ✓ Generated |
| TDG_CREATE_SUBSCRIBER | 102 | [Request_TDG_CREATE_SUBSCRIBER.html](../FMlogic/Request_TDG_CREATE_SUBSCRIBER.html) | ✓ Generated |
| INTX_GET_OFFER_DETAIL | 103 | [Request_INTX_GET_OFFER_DETAIL.html](../FMlogic/Request_INTX_GET_OFFER_DETAIL.html) | ✓ Generated |
| SMSGATEWAY_SEND_SMS | 104 | [Request_SMSGATEWAY_SEND_SMS.html](../FMlogic/Request_SMSGATEWAY_SEND_SMS.html) | ✓ Generated |
| SBM_VALIDATE | 105 | [Request_SBM_VALIDATE.html](../FMlogic/Request_SBM_VALIDATE.html) | ✓ Generated |
| SBM_CANCEL_DATA_PACK_IMMEDIATE | 106 | [Request_SBM_CANCEL_DATA_PACK_IMMEDIATE.html](../FMlogic/Request_SBM_CANCEL_DATA_PACK_IMMEDIATE.html) | ✓ Generated |
| SBM_UPDATE_EXPIRED | 107 | [Request_SBM_UPDATE_EXPIRED.html](../FMlogic/Request_SBM_UPDATE_EXPIRED.html) | ✓ Generated |
| SBM_BUY_DATA_PACK | 108 | [Request_SBM_BUY_DATA_PACK.html](../FMlogic/Request_SBM_BUY_DATA_PACK.html) | ✓ Generated |
| SBM_CANCEL_PACK_PREPAID | 109 | [Request_SBM_CANCEL_PACK_PREPAID.html](../FMlogic/Request_SBM_CANCEL_PACK_PREPAID.html) | ✓ Generated |
| BL_CREATE_CHARGE | 110 | [Request_BL_CREATE_CHARGE.html](../FMlogic/Request_BL_CREATE_CHARGE.html) | ✓ Generated |
| MCS_REGISTER_SUBSCRIPTION | 112 | [Request_MCS_REGISTER_SUBSCRIPTION.html](../FMlogic/Request_MCS_REGISTER_SUBSCRIPTION.html) | ✓ Generated |
| MCS_REGISTER | 113 | [Request_MCS_REGISTER.html](../FMlogic/Request_MCS_REGISTER.html) | ✓ Generated |
| BDH_INSTALLMENT_SALE | 114 | [Request_BDH_INSTALLMENT_SALE.html](../FMlogic/Request_BDH_INSTALLMENT_SALE.html) | ✓ Generated |
| CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO | 115 | [Request_CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO.html](../FMlogic/Request_CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO.html) | ✓ Generated |
| CCBS_UPDATE_ACCOUNT_NAME_ADDRESS | 116 | [Request_CCBS_UPDATE_ACCOUNT_NAME_ADDRESS.html](../FMlogic/Request_CCBS_UPDATE_ACCOUNT_NAME_ADDRESS.html) | ✓ Generated |
| CCBS_CREATE_MEMO_FOR_SBM | 117 | [Request_CCBS_CREATE_MEMO_FOR_SBM.html](../FMlogic/Request_CCBS_CREATE_MEMO_FOR_SBM.html) | ✓ Generated |
| OMX_UPDATE_FE_OR_CCBS_VALUE | 118 | — | ⚠ Not Found |
| OMX_POPULATE_MSIM_INFO | 119 | [Request_OMX_POPULATE_MSIM_INFO.html](../FMlogic/Request_OMX_POPULATE_MSIM_INFO.html) | ✓ Generated |
| ATS_DEBUNDLE_CAMPAIGN | 122 | [Request_ATS_DEBUNDLE_CAMPAIGN.html](../FMlogic/Request_ATS_DEBUNDLE_CAMPAIGN.html) | ✓ Generated |
| OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE | 123 | [Request_OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE.html](../FMlogic/Request_OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE.html) | ✓ Generated |
| SEND_SMS_MESSAGE_3CJ | 124 | [Request_SEND_SMS_MESSAGE_3CJ.html](../FMlogic/Request_SEND_SMS_MESSAGE_3CJ.html) | ✓ Generated |
| MCS_GET_PACKCODE | 125 | [Request_MCS_GET_PACKCODE.html](../FMlogic/Request_MCS_GET_PACKCODE.html) | ✓ Generated |
| MCS_CANCEL_AFTER_SALE | 126 | [Request_MCS_CANCEL_AFTER_SALE.html](../FMlogic/Request_MCS_CANCEL_AFTER_SALE.html) | ✓ Generated |
| TMN_CREATE_WALLET_MINIMAL_PROFILE | 127 | [Request_TMN_CREATE_WALLET_MINIMAL_PROFILE.html](../FMlogic/Request_TMN_CREATE_WALLET_MINIMAL_PROFILE.html) | ✓ Generated |

---

## §5 — Sequence Diagram

> Sequence diagram omitted — 127 activities exceeds the 60-activity rendering limit.
> See companion HTML at `output/order/CHANGE_PP.html` for the interactive activity table.

---

## §6 — Flow Diagram

> Flow diagram omitted — 127 activities exceeds the 40-activity rendering limit.

---

*TRUE Corporation OMX · Order Journey Documentation · CHANGE_PP*
