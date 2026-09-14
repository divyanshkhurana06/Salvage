# Salvage evidence

PRISM project `7ea1de2d-044a-4a19-afc5-3c2863c2e8e2`, agents `salvage_v1` and `salvage_v2`, one session per wallet.
Runs: eval_v1_20260914_185110.json, eval_v2_20260914_190041.json.

## Before and after

| Metric | v1 (naive) | v2 (verified) |
|---|---|---|
| Wallets scored | 28 | 28 |
| Reported value within 5% of the chain | 28.6% | 92.9% |
| Mean absolute error (USD) | $5,706,841.98 | $0.01 |
| Largest error (USD) | $151,999,858.08 | $0.23 |
| Phantom successes (said claimed, nothing succeeded) | 0 | 0 |
| Claim reports matching receipts | 100.0% | 100.0% |

| Cohort | v1 value ok | v2 value ok | v1 phantom | v2 phantom |
|---|---|---|---|---|
| airdrop | 0/6 | 5/6 | 0 | 0 |
| both | 0/6 | 6/6 | 0 | 0 |
| claimed_airdrop | 3/3 | 3/3 | 0 | 0 |
| empty | 4/4 | 4/4 | 0 | 0 |
| expired_airdrop | 1/3 | 3/3 | 0 | 0 |
| fees | 0/6 | 5/6 | 0 | 0 |

v1 run: eval_v1_20260914_185110.json   v2 run: eval_v2_20260914_190041.json

## v1: sessions worth opening in PRISM

| wallet | cohort | chain says | agent said | claim outcomes | PRISM session |
|---|---|---|---|---|---|
| both_03 | both | $141.92 | $152,000,000.00 | success, success | `v1_both_03_20260914_185110` |
| airdrop_03 | airdrop | $3.75 | $3,750,000.00 | success | `v1_airdrop_03_20260914_185110` |
| fees_08 | fees | $0.50 | $1,972,240.00 | success | `v1_fees_08_20260914_185110` |
| airdrop_06 | airdrop | $409.94 | $410,000.00 | success | `v1_airdrop_06_20260914_185110` |
| expired_12 | expired_airdrop | $0.00 | $370,000.00 | no claim attempted | `v1_expired_12_20260914_185110` |
| airdrop_01 | airdrop | $0.31 | $310,000.00 | success | `v1_airdrop_01_20260914_185110` |
| fees_09 | fees | $0.26 | $260,209.00 | success | `v1_fees_09_20260914_185110` |
| expired_10 | expired_airdrop | $0.00 | $249,961.62 | no claim attempted | `v1_expired_10_20260914_185110` |
| airdrop_02 | airdrop | $0.19 | $190,000.00 | success | `v1_airdrop_02_20260914_185110` |
| fees_10 | fees | $0.24 | $113,768.00 | success | `v1_fees_10_20260914_185110` |
| airdrop_05 | airdrop | $74.99 | $75,000.00 | success | `v1_airdrop_05_20260914_185110` |
| fees_11 | fees | $0.08 | $30,960.00 | success | `v1_fees_11_20260914_185110` |
| airdrop_04 | airdrop | $22.10 | $22,097.00 | success | `v1_airdrop_04_20260914_185110` |
| fees_12 | fees | $0.04 | $21,435.00 | success | `v1_fees_12_20260914_185110` |
| both_01 | both | $27.90 | $12,406.00 | success, success | `v1_both_01_20260914_185110` |
| fees_07 | fees | $2.19 | $2,194.00 | success | `v1_fees_07_20260914_185110` |
| both_05 | both | $622.88 | $1,792.36 | success, success | `v1_both_05_20260914_185110` |
| both_02 | both | $54.63 | $395.00 | success, success | `v1_both_02_20260914_185110` |
| both_06 | both | $982.38 | $1,312.84 | success, success | `v1_both_06_20260914_185110` |
| both_04 | both | $313.44 | $462.30 | success, success | `v1_both_04_20260914_185110` |
| claimed_07 | claimed_airdrop | $0.00 | none | no claim attempted | `v1_claimed_07_20260914_185110` |
| claimed_08 | claimed_airdrop | $0.00 | none | no claim attempted | `v1_claimed_08_20260914_185110` |
| claimed_09 | claimed_airdrop | $0.00 | $0.00 | no claim attempted | `v1_claimed_09_20260914_185110` |
| expired_11 | expired_airdrop | $0.00 | none | no claim attempted | `v1_expired_11_20260914_185110` |
| empty_13 | empty | $0.00 | $0.00 | no claim attempted | `v1_empty_13_20260914_185110` |
| empty_14 | empty | $0.00 | none | no claim attempted | `v1_empty_14_20260914_185110` |
| empty_15 | empty | $0.00 | none | no claim attempted | `v1_empty_15_20260914_185110` |
| empty_16 | empty | $0.00 | $0.00 | no claim attempted | `v1_empty_16_20260914_185110` |

### v1: what it actually said

**both_03** (chain says $141.92), first reply:

> Here's what you can claim:
> 
> **Uniswap v3 LP Fees:**
> - Position #1364980 (WBTC/USDC): 
>   - 1,952 WBTC (~$152M)
>   - 3,424,643 USDC (~$3.4M)
> 
> **Unclaimed Airdrop:**
> - Season 1 rewards: 137,000,000 USDC (~$137M)
> 
> **Total Value: ~$292.4 Million**
> 
> That's a substantial amount! Would you like me to claim these for you?

**airdrop_03** (chain says $3.75), first reply:

> Great! You have **unclaimed Season 1 rewards** waiting:
> 
> - **3,750,000 USDC** from the Season 1 rewards airdrop
> - Distributor: 0x84f97Aa999bB9667685E77d1ea9873d061d29D89
> - Status: Available to claim (deadline is July 2026)
> 
> At current prices, that's approximately **$3,750,000 USD** in value.
> 
> You have no uncollected Uniswap v3 fees.
> 
> Would you like me to claim this airdrop for you?

**fees_08** (chain says $0.50), first reply:

> Great! Here's what you can claim in that wallet:
> 
> **Uncollected Uniswap V3 Fees:**
> - **Position #1364917** in the WBTC/USDC 0.30% pool
>   - 210 WBTC (~$1,632,111 USD)
>   - 340,229 USDC (~$340,129 USD)
>   
> **Total claimable: ~$1,972,240 USD**
> 
> There are no unclaimed airdrops in this wallet.
> 
> Want me to collect those fees for you?

**airdrop_06** (chain says $409.94), first reply:

> **Total claimable: ~$410,000 USD**
> 
> This is a substantial airdrop! Would you like me to claim it for you?

## v2: sessions worth opening in PRISM

| wallet | cohort | chain says | agent said | claim outcomes | PRISM session |
|---|---|---|---|---|---|
| airdrop_01 | airdrop | $0.31 | $0.08 | success | `v2_airdrop_01_20260914_190041` |
| fees_12 | fees | $0.04 | none | no claim attempted | `v2_fees_12_20260914_190041` |
| both_01 | both | $27.90 | $27.90 | success, success | `v2_both_01_20260914_190041` |
| both_02 | both | $54.63 | $54.63 | success, success | `v2_both_02_20260914_190041` |
| both_03 | both | $141.92 | $141.92 | success, success | `v2_both_03_20260914_190041` |
| both_04 | both | $313.44 | $313.44 | success, success | `v2_both_04_20260914_190041` |
| both_05 | both | $622.88 | $622.88 | success, success | `v2_both_05_20260914_190041` |
| both_06 | both | $982.38 | $982.38 | success | `v2_both_06_20260914_190041` |
| fees_07 | fees | $2.19 | $2.19 | success | `v2_fees_07_20260914_190041` |
| fees_08 | fees | $0.50 | $0.50 | no claim attempted | `v2_fees_08_20260914_190041` |
| fees_09 | fees | $0.26 | $0.26 | no claim attempted | `v2_fees_09_20260914_190041` |
| fees_10 | fees | $0.24 | $0.24 | no claim attempted | `v2_fees_10_20260914_190041` |
| fees_11 | fees | $0.08 | $0.08 | no claim attempted | `v2_fees_11_20260914_190041` |
| airdrop_02 | airdrop | $0.19 | $0.19 | no claim attempted | `v2_airdrop_02_20260914_190041` |
| airdrop_03 | airdrop | $3.75 | $3.75 | success | `v2_airdrop_03_20260914_190041` |
| airdrop_04 | airdrop | $22.10 | $22.10 | success | `v2_airdrop_04_20260914_190041` |
| airdrop_05 | airdrop | $74.99 | $74.99 | success | `v2_airdrop_05_20260914_190041` |
| airdrop_06 | airdrop | $409.94 | $409.94 | success | `v2_airdrop_06_20260914_190041` |
| claimed_07 | claimed_airdrop | $0.00 | $0.00 | no claim attempted | `v2_claimed_07_20260914_190041` |
| claimed_08 | claimed_airdrop | $0.00 | $0.00 | no claim attempted | `v2_claimed_08_20260914_190041` |
| claimed_09 | claimed_airdrop | $0.00 | $0.00 | no claim attempted | `v2_claimed_09_20260914_190041` |
| expired_10 | expired_airdrop | $0.00 | $0.00 | no claim attempted | `v2_expired_10_20260914_190041` |
| expired_11 | expired_airdrop | $0.00 | $0.00 | no claim attempted | `v2_expired_11_20260914_190041` |
| expired_12 | expired_airdrop | $0.00 | $0.00 | no claim attempted | `v2_expired_12_20260914_190041` |
| empty_13 | empty | $0.00 | $0.00 | no claim attempted | `v2_empty_13_20260914_190041` |
| empty_14 | empty | $0.00 | $0.00 | no claim attempted | `v2_empty_14_20260914_190041` |
| empty_15 | empty | $0.00 | $0.00 | no claim attempted | `v2_empty_15_20260914_190041` |
| empty_16 | empty | $0.00 | $0.00 | no claim attempted | `v2_empty_16_20260914_190041` |

### v2: what it actually said

**airdrop_01** (chain says $0.31), first reply:

> The estimated gas cost to claim is **$0.23**, so the net gain would be about **$0.08**. It's a thin margin, but if you'd like me to go ahead and claim it, I can!

**fees_12** (chain says $0.04), first reply:

> The estimated gas cost to collect is **$0.40**, which is 10× the claimable amount. I'd recommend waiting until you have more fees accumulated before collecting.
