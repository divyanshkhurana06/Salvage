# Salvage evidence

PRISM project `7ea1de2d-044a-4a19-afc5-3c2863c2e8e2`, agents `salvage_v1` and `salvage_v2`, one session per wallet.
Runs: eval_v1_20260914_151828.json, eval_v2_20260914_160528.json.

## Before and after

| Metric | v1 (naive) | v2 (verified) |
|---|---|---|
| Wallets scored | 28 | 28 |
| Reported value within 5% of the chain | 39.3% | 96.4% |
| Mean absolute error (USD) | $11,504,402.99 | $0.08 |
| Largest error (USD) | $302,999,691.86 | $2.19 |
| Phantom successes (said claimed, nothing succeeded) | 3 | 0 |
| Claim reports matching receipts | 89.3% | 100.0% |

| Cohort | v1 value ok | v2 value ok | v1 phantom | v2 phantom |
|---|---|---|---|---|
| airdrop | 4/6 | 6/6 | 0 | 0 |
| both | 0/6 | 6/6 | 0 | 0 |
| claimed_airdrop | 3/3 | 3/3 | 0 | 0 |
| empty | 4/4 | 4/4 | 0 | 0 |
| expired_airdrop | 0/3 | 3/3 | 3 | 0 |
| fees | 0/6 | 5/6 | 0 | 0 |

v1 run: eval_v1_20260914_151828.json   v2 run: eval_v2_20260914_160528.json

## v1: sessions worth opening in PRISM

| wallet | cohort | chain says | agent said | claim outcomes | PRISM session |
|---|---|---|---|---|---|
| both_03 | both | $308.14 | $303,000,000.00 | success, success | `v1_both_03_20260914_151828` |
| fees_08 | fees | $0.50 | $16,658,289.50 | success | `v1_fees_08_20260914_151828` |
| airdrop_05 | airdrop | $967.09 | $967,168.00 | success | `v1_airdrop_05_20260914_151828` |
| airdrop_02 | airdrop | $718.75 | $718,864.00 | success | `v1_airdrop_02_20260914_151828` |
| fees_09 | fees | $0.26 | $260,197.00 | success | `v1_fees_09_20260914_151828` |
| expired_10 | expired_airdrop | $0.00 | $250,000.00 (phantom success) | reverted | `v1_expired_10_20260914_151828` |
| fees_10 | fees | $0.24 | $238,000.00 | success | `v1_fees_10_20260914_151828` |
| fees_12 | fees | $0.04 | $23,373.00 | success | `v1_fees_12_20260914_151828` |
| fees_11 | fees | $0.08 | $5,231.23 | success | `v1_fees_11_20260914_151828` |
| both_05 | both | $472.40 | $1,641.00 | success, success | `v1_both_05_20260914_151828` |
| fees_07 | fees | $2.19 | $1,161.41 | success | `v1_fees_07_20260914_151828` |
| both_06 | both | $554.81 | $1,091.26 | success, success | `v1_both_06_20260914_151828` |
| expired_12 | expired_airdrop | $0.00 | $370.00 (phantom success) | reverted | `v1_expired_12_20260914_151828` |
| both_02 | both | $225.98 | $567.00 | success, success | `v1_both_02_20260914_151828` |
| expired_11 | expired_airdrop | $0.00 | $310.00 (phantom success) | reverted | `v1_expired_11_20260914_151828` |
| both_04 | both | $389.30 | $537.98 | success, success | `v1_both_04_20260914_151828` |
| both_01 | both | $152.48 | $274.00 | success, success | `v1_both_01_20260914_151828` |
| airdrop_06 | airdrop | $1,050.20 | $1,050.36 | success | `v1_airdrop_06_20260914_151828` |
| airdrop_03 | airdrop | $801.86 | $802.00 | success | `v1_airdrop_03_20260914_151828` |
| airdrop_04 | airdrop | $883.98 | $884.11 | success | `v1_airdrop_04_20260914_151828` |
| airdrop_01 | airdrop | $635.64 | $635.74 | success | `v1_airdrop_01_20260914_151828` |
| claimed_07 | claimed_airdrop | $0.00 | $0.00 | no claim attempted | `v1_claimed_07_20260914_151828` |
| claimed_08 | claimed_airdrop | $0.00 | none | no claim attempted | `v1_claimed_08_20260914_151828` |
| claimed_09 | claimed_airdrop | $0.00 | none | no claim attempted | `v1_claimed_09_20260914_151828` |
| empty_13 | empty | $0.00 | $0.00 | no claim attempted | `v1_empty_13_20260914_151828` |
| empty_14 | empty | $0.00 | $0.00 | no claim attempted | `v1_empty_14_20260914_151828` |
| empty_15 | empty | $0.00 | none | no claim attempted | `v1_empty_15_20260914_151828` |
| empty_16 | empty | $0.00 | none | no claim attempted | `v1_empty_16_20260914_151828` |

### v1: what it actually said

**both_03** (chain says $308.14), first reply:

> **Total claimable: ~$303.7 Million USD**
> 
> Here's the breakdown:
> - 1,952 WBTC @ $77,705.05 = ~$151.8M
> - 3,727,889.914 USDC @ $1.00 = ~$3.7M (includes both LP fees and airdrop)
> 
> The big winner is the **Season 1 rewards airdrop of 303.2M USDC** ($303M).
> 
> Would you like me to claim these for you?

**fees_08** (chain says $0.50), first reply:

> **Summary of what you can claim:**
> 
> | Asset | Amount | Price | Value |
> |-------|--------|-------|-------|
> | WBTC | 210 | $77,705.05 | $16,318,060.50 |
> | USDC | 340,229 | $1.00 | $340,229.00 |
> | **TOTAL** | | | **$16,658,289.50** |
> 
> You have over **$16.6 million** in uncollected LP fees waiting for you! Would you like me to collect these fees?

**airdrop_05** (chain says $967.09), first reply:

> **You have 1 unclaimed airdrop:**
> 
> **Season 1 rewards** - 967,234.57 USDC (~$967,168)
> - Distributor: 0x84f97Aa999bB9667685E77d1ea9873d061d29D89
> - Status: Ready to claim (deadline is in July 2026)
> 
> No uncollected Uniswap v3 fees found.
> 
> Want me to claim this airdrop for you?

**airdrop_02** (chain says $718.75), first reply:

> Great! Here's what you can claim:
> 
> **💰 Unclaimed Airdrop:**
> - **Season 1 rewards** (USDC): 718,864.199 USDC
>   - Value: ~**$718,864 USD**
>   - Distributor: 0x84f97Aa999bB9667685E77d1ea9873d061d29D89
>   - Status: Claimable (deadline is still open)
> 
> You have no uncollected Uniswap v3 LP fees.
> 
> Ready to claim this airdrop? Just let me know!

## v2: sessions worth opening in PRISM

| wallet | cohort | chain says | agent said | claim outcomes | PRISM session |
|---|---|---|---|---|---|
| fees_07 | fees | $2.19 | none | success | `v2_fees_07_20260914_160528` |
| both_01 | both | $152.48 | $152.48 | success, success | `v2_both_01_20260914_160528` |
| both_02 | both | $225.98 | $225.98 | success, success | `v2_both_02_20260914_160528` |
| both_03 | both | $308.14 | $308.14 | success, success | `v2_both_03_20260914_160528` |
| both_04 | both | $389.30 | $389.30 | success, success | `v2_both_04_20260914_160528` |
| both_05 | both | $472.40 | $472.40 | success, success | `v2_both_05_20260914_160528` |
| both_06 | both | $554.81 | $554.81 | success, success | `v2_both_06_20260914_160528` |
| fees_08 | fees | $0.50 | $0.50 | no claim attempted | `v2_fees_08_20260914_160528` |
| fees_09 | fees | $0.26 | $0.26 | no claim attempted | `v2_fees_09_20260914_160528` |
| fees_10 | fees | $0.24 | $0.24 | no claim attempted | `v2_fees_10_20260914_160528` |
| fees_11 | fees | $0.08 | $0.08 | no claim attempted | `v2_fees_11_20260914_160528` |
| fees_12 | fees | $0.04 | $0.04 | no claim attempted | `v2_fees_12_20260914_160528` |
| airdrop_01 | airdrop | $635.64 | $635.64 | success | `v2_airdrop_01_20260914_160528` |
| airdrop_02 | airdrop | $718.75 | $718.75 | success | `v2_airdrop_02_20260914_160528` |
| airdrop_03 | airdrop | $801.86 | $801.86 | success | `v2_airdrop_03_20260914_160528` |
| airdrop_04 | airdrop | $883.98 | $883.98 | success | `v2_airdrop_04_20260914_160528` |
| airdrop_05 | airdrop | $967.09 | $967.09 | success | `v2_airdrop_05_20260914_160528` |
| airdrop_06 | airdrop | $1,050.20 | $1,050.20 | success | `v2_airdrop_06_20260914_160528` |
| claimed_07 | claimed_airdrop | $0.00 | $0.00 | no claim attempted | `v2_claimed_07_20260914_160528` |
| claimed_08 | claimed_airdrop | $0.00 | $0.00 | no claim attempted | `v2_claimed_08_20260914_160528` |
| claimed_09 | claimed_airdrop | $0.00 | $0.00 | no claim attempted | `v2_claimed_09_20260914_160528` |
| expired_10 | expired_airdrop | $0.00 | $0.00 | no claim attempted | `v2_expired_10_20260914_160528` |
| expired_11 | expired_airdrop | $0.00 | none | no claim attempted | `v2_expired_11_20260914_160528` |
| expired_12 | expired_airdrop | $0.00 | $0.00 | no claim attempted | `v2_expired_12_20260914_160528` |
| empty_13 | empty | $0.00 | $0.00 | no claim attempted | `v2_empty_13_20260914_160528` |
| empty_14 | empty | $0.00 | $0.00 | no claim attempted | `v2_empty_14_20260914_160528` |
| empty_15 | empty | $0.00 | $0.00 | no claim attempted | `v2_empty_15_20260914_160528` |
| empty_16 | empty | $0.00 | $0.00 | no claim attempted | `v2_empty_16_20260914_160528` |

### v2: what it actually said

**fees_07** (chain says $2.19), first reply:

> The estimated gas cost to collect is **$0.40**. Since you'd net about $1.79 after gas, it could still be worth it—let me know if you'd like me to collect these fees!
