"""Deterministic synthetic dataset for integration testing.

Generates a 100-row customer churn dataset with fixed seed for reproducibility.
Run directly to regenerate: python -m integration_tests.fixtures.synthetic.generate
"""

import csv
import random
from pathlib import Path


SEED = 42
NUM_ROWS = 100
OUTPUT_PATH = Path(__file__).parent / "customers.csv"

COLUMNS = ["customer_id", "age", "tenure_months", "monthly_spend", "support_tickets", "churned"]


def generate() -> list[dict]:
    random.seed(SEED)
    rows = []
    for i in range(1, NUM_ROWS + 1):
        age = random.randint(18, 80)
        tenure = random.randint(1, 60)
        spend = round(random.uniform(10.0, 500.0), 2)
        tickets = random.randint(0, 10)
        # Simple churn logic: higher tickets + lower tenure = more likely to churn
        churn_score = (tickets / 10) * 0.6 + (1 - tenure / 60) * 0.4
        churned = random.random() < churn_score
        rows.append({
            "customer_id": i,
            "age": age,
            "tenure_months": tenure,
            "monthly_spend": spend,
            "support_tickets": tickets,
            "churned": churned,
        })
    return rows


def write_csv(rows: list[dict], path: Path = OUTPUT_PATH) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    rows = generate()
    write_csv(rows)
    print(f"Generated {len(rows)} rows to {OUTPUT_PATH}")
