# Analyst Notes

## Project Context
- **Business Objective:** Predict customer churn from demographic and behavioral features
- **Target Variable:** churned (boolean)
- **Excluded Columns:** customer_id (identifier, not predictive)

## Domain Notes
- This is synthetic test data with no special domain constraints
- Churn is driven by a combination of support_tickets (60% weight) and tenure_months (40% weight)
- Higher tickets and lower tenure correlate with higher churn probability

## Recommendations
- Keep the approach simple: data loading, model training, evaluation
- Logistic regression is sufficient for this binary classification task
- Focus on clean data pipeline and clear evaluation metrics
