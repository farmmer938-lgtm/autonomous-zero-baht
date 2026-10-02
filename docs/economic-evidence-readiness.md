# Economic Evidence Readiness

Status: **READY / NOT ACTIVATED**

Purpose: define the next Measurement gate from external activity evidence to verified economic evidence without fabricating conversions, transactions, revenue, balances, or cash.

## Required evidence chain

`ACTIVITY -> CONVERSION -> TRANSACTION -> REVENUE REPORTED -> REVENUE VERIFIED -> BALANCE AVAILABLE -> PAYOUT ELIGIBLE -> CASH RECEIVED -> REPEAT TRANSACTIONS`

A metric may advance only when authoritative evidence for that stage exists. Traffic, views, clones, or repository activity must never be promoted to an economic stage.

## Provider contract

For any future permitted monetization provider, record:

- provider name and official documentation URL
- account/region eligibility
- fee model and zero-upfront-cost status
- payout method and country availability
- required KYC/tax/legal steps
- transaction identifier or provider-side reference
- event timestamp with timezone
- gross amount and currency
- provider fees
- net amount
- payout/balance status
- evidence capture timestamp
- verification source/reference

Sensitive credentials, bank details, tax IDs, and identity documents must never be committed to the repository.

## Current zero-baht research snapshot

### GitHub Sponsors

GitHub's current documentation lists **Thailand** among supported regions for receiving GitHub Sponsors funds. Receiving sponsorships requires completion of a sponsor profile and submission of bank/tax information, with GitHub approval and account security requirements. Human-authority steps remain outside automation.

Source: https://docs.github.com/en/sponsors/getting-started-with-github-sponsors/about-github-sponsors

### Gumroad

Gumroad currently documents bank payouts in Thailand in THB. Its current pricing documentation states there is no monthly payment, while transaction fees apply to sales. This is compatible with a zero-upfront-cost constraint but does not mean a transaction or revenue exists.

Sources:
- https://gumroad.com/help/article/13-getting-paid
- https://gumroad.com/help/article/66-gumroads-fees

### Ko-fi

Ko-fi currently documents a free account with no monthly fee, direct payment through PayPal or Stripe, and support for THB/Thai payment methods. Service and payment-processor fees may apply depending on payment type.

Sources:
- https://help.ko-fi.com/hc/en-us/articles/360002506494-Does-Ko-fi-take-a-fee
- https://help.ko-fi.com/hc/en-us/articles/24482435253661-What-payment-methods-are-available-on-Ko-fi

## Activation gates

Automation must remain disabled until all applicable gates are satisfied:

1. Provider eligibility is verified for the actual account and jurisdiction.
2. Human-required KYC, tax, bank, or legal acceptance is completed by K.
3. The offer/product and disclosure requirements are validated.
4. A permitted distribution path exists.
5. Provider-side transaction evidence can be captured without exposing credentials.
6. Tests prove that missing/unverified economic evidence stays NOT_VERIFIED.
7. A real external transaction is observed and independently verified before any revenue claim.

## Current state

- External activity evidence: **VERIFIED**
- Conversion evidence: **NOT_VERIFIED**
- Transaction evidence: **NOT_VERIFIED**
- Revenue: **NOT_VERIFIED**
- Cash received: **NOT_VERIFIED**
- Repeatability: **NOT_VERIFIED**
- Auto-publish: **BLOCKED BY DESIGN**
- Spending/paid services: **BLOCKED BY ZERO-BAHT RULE**
- Provider activation: **NOT ACTIVATED**

This document is a readiness contract only. It does not activate a monetization account, publish an offer, create a transaction, or claim revenue.
