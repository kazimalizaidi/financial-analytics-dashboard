# Data and methodology

`helmquant_ledger.csv` is the ledger loaded into the **Transactions** sheet of every dashboard (4,108 rows, 1 Dec 2009 to 30 Nov 2011, GBP). It is built by `scripts/build_ledger.py`, which reproduces the file exactly from the original UCI workbook.

## Source

UCI Machine Learning Repository, **Online Retail II** (Chen, D.): every invoice line of a UK-based online giftware retailer (mostly wholesale customers), 1 Dec 2009 to 9 Dec 2011, about 1.04 million unique lines. Check the dataset page for its current license and citation terms before redistributing.

## What is real and what is modelled

The `Source` column on every row says which it is.

| Source | Categories | How it is made |
|--------|-----------|----------------|
| **Real** (4,012 rows) | Home & Decor, Kitchen & Dining, Bags & Storage, Gifts Cards & Seasonal, Shipping & Other Income, Returns & Credit Notes, Marketplace Fees, Bad Debt & Adjustments, Bank Charges | Aggregated from the invoice lines. Amounts are real. |
| **Modelled** (96 rows) | Cost of Goods, Salaries, Rent & Utilities, Marketing | The source has no cost data, so these are monthly assumptions. |

Modelled assumptions (edit in `scripts/build_ledger.py` and regenerate): cost of goods = 62% of product sales; marketing = 3% of product sales; payroll = £115,000 a month in 2009-2010 and £122,000 a month in 2011; rent and utilities = £24,000 a month. They are plausible for a small wholesaler but invented, so **profit, margin, cash and runway are only as real as these assumptions**. Revenue, returns, marketplace fees, bank charges and bad-debt adjustments are real. Opening cash (£450,000), the profit goal (£1.5M), the budgets and the upcoming payments on the Settings sheet are also assumptions.

## Cleaning rules

1. The two source sheets overlap on 1 to 9 Dec 2010 (identical rows). One copy is kept. Without this, about £377k of sales would be counted twice.
2. Only whole months are kept: data after 30 Nov 2011 (a partial month) is dropped, so budget-to-date and monthly averages stay honest.
3. Test and dummy lines (`PADS`, `SP1002`, `TEST001`, `TEST002`) and zero-value lines are dropped (6,005 lines, net £181.65).
4. Special stock codes become ledger categories: carriage (`POST`, `DOT`, `C2`) and manual positives become Shipping & Other Income; `AMAZONFEE` becomes Marketplace Fees; `BANK CHARGES` becomes Bank Charges; `B`, `D`, `S`, `CRUK`, `M`, `ADJUST` negatives become Bad Debt & Adjustments.
5. Credit notes (invoices starting with `C`) and other negative product lines become Returns & Credit Notes.
6. Product lines are grouped by keyword on the product description (first match wins: Gifts, Cards & Seasonal; then Bags & Storage; then Kitchen & Dining; everything else Home & Decor). This grouping is my own, so category shares are indicative.
7. Rows are rolled up: sales per day per product group, returns per day, and each marketplace fee, bank charge and bad-debt adjustment as its own row (its invoice number is in the description).
8. Amounts are stored positive; the `Type` column carries the sign.

## Reconciliation

Income minus real expenses in the ledger equals the net of the cleaned source lines to the penny (£18,475,894.44). The workbook re-checks this on the Insights sheet using the control total stored on Settings.
