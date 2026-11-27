# Reconciliation eval: gemini-3.5-flash

2026-11-27 06:47 UTC · 30 cases · 21s

| Metric | Score |
|---|---|
| Correct cause | 100% |
| Suggestions passing guardrails | 100% |
| Correct journal entry (or correctly none) | 100% |
| **Fully correct** | **100%** |

| Case | Cause | Entry | Detail |
|---|---|---|---|
| fee_0 | ✓ | ✓ | cause=fee_difference entry={'expenses:gateway_fees': 1180, 'assets:razorpay_clearing': -1180} |
| fee_1 | ✓ | ✓ | cause=fee_difference entry={'expenses:gateway_fees': 2948, 'assets:razorpay_clearing': -2948} |
| fee_2 | ✓ | ✓ | cause=fee_difference entry={'expenses:gateway_fees': 647, 'assets:razorpay_clearing': -647} |
| fee_3 | ✓ | ✓ | cause=fee_difference entry={'expenses:gateway_fees': 1179, 'assets:razorpay_clearing': -1179} |
| fee_4 | ✓ | ✓ | cause=fee_difference entry={'expenses:gateway_fees': 382, 'assets:razorpay_clearing': -382} |
| fee_5 | ✓ | ✓ | cause=fee_difference entry={'assets:razorpay_clearing': 3538, 'expenses:gateway_fees': -3538} |
| missed_pay_0 | ✓ | ✓ | cause=webhook_missed entry={'assets:razorpay_clearing': 126834, 'expenses:gateway_fees': 3066, 'revenue:sales': -129900} |
| missed_pay_1 | ✓ | ✓ | cause=webhook_missed entry={'assets:razorpay_clearing': 48722, 'expenses:gateway_fees': 1178, 'revenue:sales': -49900} |
| missed_pay_2 | ✓ | ✓ | cause=webhook_missed entry={'assets:razorpay_clearing': 341642, 'expenses:gateway_fees': 8258, 'revenue:sales': -349900} |
| missed_pay_3 | ✓ | ✓ | cause=webhook_missed entry={'assets:razorpay_clearing': 19430, 'expenses:gateway_fees': 470, 'revenue:sales': -19900} |
| missed_pay_4 | ✓ | ✓ | cause=webhook_missed entry={'assets:razorpay_clearing': 78014, 'expenses:gateway_fees': 1886, 'revenue:sales': -79900} |
| missed_refund_0 | ✓ | ✓ | cause=webhook_missed entry={'revenue:sales': 30000, 'assets:razorpay_clearing': -30000} |
| missed_refund_1 | ✓ | ✓ | cause=webhook_missed entry={'revenue:sales': 149900, 'assets:razorpay_clearing': -149900} |
| missed_refund_2 | ✓ | ✓ | cause=webhook_missed entry={'revenue:sales': 5000, 'assets:razorpay_clearing': -5000} |
| chargeback_0 | ✓ | ✓ | cause=chargeback entry={'revenue:sales': 99900, 'assets:razorpay_clearing': -99900} |
| chargeback_1 | ✓ | ✓ | cause=chargeback entry={'revenue:sales': 249900, 'assets:razorpay_clearing': -249900} |
| chargeback_2 | ✓ | ✓ | cause=chargeback entry={'revenue:sales': 54900, 'assets:razorpay_clearing': -54900} |
| chargeback_3 | ✓ | ✓ | cause=chargeback entry={'revenue:sales': 14900, 'assets:razorpay_clearing': -14900} |
| credit_adj_0 | ✓ | ✓ | cause=other_adjustment entry={'assets:razorpay_clearing': 2360, 'expenses:gateway_fees': -2360} |
| credit_adj_1 | ✓ | ✓ | cause=other_adjustment entry={'assets:razorpay_clearing': 5900, 'expenses:gateway_fees': -5900} |
| pending_0 | ✓ | ✓ | cause=pending_settlement entry=none |
| pending_1 | ✓ | ✓ | cause=pending_settlement entry=none |
| pending_2 | ✓ | ✓ | cause=pending_settlement entry=none |
| pending_3 | ✓ | ✓ | cause=pending_settlement entry=none |
| amount_0 | ✓ | ✓ | cause=amount_error entry={'revenue:sales': 10000, 'assets:razorpay_clearing': -10000} |
| amount_1 | ✓ | ✓ | cause=amount_error entry={'revenue:sales': 10000, 'assets:razorpay_clearing': -10000} |
| amount_2 | ✓ | ✓ | cause=amount_error entry={'revenue:sales': 900, 'assets:razorpay_clearing': -900} |
| amount_3 | ✓ | ✓ | cause=amount_error entry={'assets:razorpay_clearing': 10000, 'revenue:sales': -10000} |
| data_zero | ✓ | ✓ | cause=other entry=none |
| data_pending_refund | ✓ | ✓ | cause=pending_settlement entry=none |
