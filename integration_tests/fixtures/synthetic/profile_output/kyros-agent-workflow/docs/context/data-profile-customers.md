# Data Profile: customers

**Source:** customers.csv
**Rows:** 100
**Columns:** 6

## Column Summary

| Column | Type | Non-Null | Null % | Unique | Min | Max | Mean |
|--------|------|----------|--------|--------|-----|-----|------|
| customer_id | int | 100 | 0% | 100 | 1 | 100 | 50.5 |
| age | int | 100 | 0% | 54 | 18 | 80 | 48.2 |
| tenure_months | int | 100 | 0% | 55 | 1 | 60 | 30.1 |
| monthly_spend | float | 100 | 0% | 100 | 10.03 | 499.82 | 254.9 |
| support_tickets | int | 100 | 0% | 11 | 0 | 10 | 5.1 |
| churned | bool | 100 | 0% | 2 | False | True | 0.43 |

## Distribution Notes

- **age:** Roughly uniform distribution from 18-80
- **tenure_months:** Roughly uniform 1-60, no missing values
- **monthly_spend:** Roughly uniform $10-$500
- **support_tickets:** Uniform 0-10
- **churned:** 43% churn rate (43 True, 57 False)

## Data Quality

- No null values detected in any column
- No duplicate customer_ids
- All numeric columns within expected ranges
- Boolean target variable is well-balanced (43/57 split)
