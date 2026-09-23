# OMX_CAL_CREDIT_LIMIT_NONTOP_CORP

## §1 Overview & Purpose

**OMX_CAL_CREDIT_LIMIT_NONTOP_CORP** is a pure internal calculation rule (OMXOM, not OMXFM). It derives a personal credit limit for non-TOP/PREMIUM corporate accounts from the RC (recurring charge) ExtInfo written by FM23 (OMX_GET_RECURRING_CHARGE). No external backend call is made.

> **No response handler:** This rule completes synchronously and calls `NextActivity` directly. There is no corresponding Response rulefunction.

> **Credit limit calculation uses RC ExtInfo** (Name="RC" written by FM23) from POU/ChildOU Agreement.Offers and Subscriber.SubscriberOffers. Only FE_OR_CCBS=FE offers are included.

> **Write-backs (3):** `account.AccountManagementInfo.PersonalCreditLimit` ← calculateCreditLimit (if > 0). AccountExtInfo Name="CALCULATECREDITLIMIT". AccountExtInfo Name="CURRENTCREDITLIMIT".

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXOM.OMX_CAL_CREDIT_LIMIT_NONTOP_CORP` |
| Author | warawich-nb |
| Priority | 5 |
| forwardChain | true |
| Backend | None — internal calculation |
| Fan-in | No response handler — calls `NextActivity` directly |
| Iteration target | `Customer.Account[]` |
| Key input | RC ExtInfo (Name="RC") on SubscriberOffers/AgreementOffers — written by FM23 |
| Key input 2 | OLD_PERSONAL_CREDITLIMIT ExtInfo — from CCBS GetAccountHeader (earlier step) |

---

## §7 Credit Limit Calculation Logic

| Priority | Condition | Formula |
|----------|-----------|---------|
| 1 — Agreement individual | POU/ChildOU.Agreement.Offers: ServiceType=80, ServiceLevel=71 or G, FE_OR_CCBS=FE | `RoundUp(RC, 100)` |
| 2 — Agreement corporate | POU/ChildOU.Agreement.Offers: ServiceType=80, ServiceLevel=67 or C, FE_OR_CCBS=FE | `RoundUp(RC × numberOfSub, 100)` (min 1) |
| 3 — Subscriber offers | ServiceType=80, FE_OR_CCBS=FE; Agreement offers exhausted | `RoundUp(sumRC + currentCreditLimit, 100)` |

**currentCreditLimit:** `account.AccountManagementInfo.PersonalCreditLimit` if != OLD_PERSONAL_CREDITLIMIT; else 0.
**OLD_PERSONAL_CREDITLIMIT:** From Account.ExtendedInfo[Name="OLD_PERSONAL_CREDITLIMIT"].Value — written by earlier CCBS GetAccountHeader step.

---

## §15 Function Dependency Tree

```text
OMX_CAL_CREDIT_LIMIT_NONTOP_CORP (internal, no FM pattern)
├── for each Account[iAcc]:
│   ├── if PreExecCheck: GetXMLForAccount → XPath → chkRes; if != "true": continue
│   ├── chkOldCreditLimit = XPath.evalAsDouble(ExtInfo[OLD_PERSONAL_CREDITLIMIT].Value ?? 0)
│   ├── currentCreditLimit = PersonalCreditLimit if != chkOldCreditLimit; else 0
│   ├── if AgreementRefId non-empty:
│   │   for each POU/ChildOU:
│   │   ├── if Agreement.RefId == AgreementRefId:
│   │   │   ├── for each Agreement.Offers (FE only, ServiceType=80):
│   │   │   │   ├── ServiceLevel=71/G → calculateCreditLimit = RoundUp(RC, 100); break
│   │   │   │   └── ServiceLevel=67/C → calculateCreditLimit = RoundUp(RC×numberOfSub, 100); break
│   │   │   └── if still 0: sumRC over Subscriber.SubscriberOffers (FE, ServiceType=80)
│   │   │       → if sumRc>0: calculateCreditLimit = RoundUp(sumRc + currentCreditLimit, 100)
│   ├── if calculateCreditLimit > 0:
│   │   └── account.AccountManagementInfo.PersonalCreditLimit = calculateCreditLimit
│   ├── always: account.ExtendedInfo[] += {Name="CALCULATECREDITLIMIT", Value=calculateCreditLimit}
│   └── always: account.ExtendedInfo[] += {Name="CURRENTCREDITLIMIT", Value=currentCreditLimit}
├── if isSkipped: SkipActivity("4")
└── else:
    ├── sendEvent(Logger — "OMX_CAL_CREDIT_LIMIT_NONTOP_CORP Completed")
    └── NextActivity(orderRequest, orderCurrentActivity)
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Depends on RC ExtInfo from FM23 — implicit FM23→FM24 dependency | [MEDIUM] | Document and validate ProcessConfig sequence |
| OLD_PERSONAL_CREDITLIMIT requires CCBS GetAccountHeader to have run — undocumented cross-activity ExtInfo dependency | [MEDIUM] | Document full ExtInfo write-chain |
| RoundUp(x, 100) — custom helper; must be preserved exactly | [LOW] | Unit-test with edge cases |
| FE_OR_CCBS filter silently excludes CCBS offers | [LOW] | Confirm intentional for non-TOP CORP accounts |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
