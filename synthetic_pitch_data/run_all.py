from __future__ import annotations

from synthetic_pitch_data import monthly_cohort_retention
from synthetic_pitch_data.company.postgresql_1.orders import main as postgresql_1_orders_main
from synthetic_pitch_data.company.postgresql_1.users import main as postgresql_1_users_main
from synthetic_pitch_data.company.shopify_1.orders import main as shopify_1_orders_main
from synthetic_pitch_data.company.shopify_1.users import main as shopify_1_users_main
from synthetic_pitch_data.company.shopify_2.orders import main as shopify_2_orders_main
from synthetic_pitch_data.company.shopify_2.users import main as shopify_2_users_main
from synthetic_pitch_data.paths import DATA_HOME, ensure_workspace_dirs


def main() -> None:
    ensure_workspace_dirs()
    print(f"Using synthetic data workspace: {DATA_HOME}")

    postgresql_1_users_main()
    postgresql_1_orders_main()
    shopify_1_users_main()
    shopify_1_orders_main()
    shopify_2_users_main()
    shopify_2_orders_main()
    monthly_cohort_retention.main()


if __name__ == "__main__":
    main()
