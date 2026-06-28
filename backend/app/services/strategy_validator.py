from app.schemas import StrategyJSON
from app.services.strategy_catalog import CONDITION_CATALOG, FEATURE_CATALOG


class StrategyValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class StrategyValidator:
    @staticmethod
    def validate(strategy: StrategyJSON) -> None:
        errors: list[str] = []

        total_weight = sum(rule.weight for rule in strategy.rules)
        if total_weight <= 0 or total_weight > 1.5:
            errors.append("Rule weight total must be greater than 0 and less than or equal to 1.5")

        for index, rule in enumerate(strategy.rules, start=1):
            if rule.feature not in FEATURE_CATALOG:
                errors.append(f"Rule {index} has unsupported feature: {rule.feature}")
            if rule.operator not in CONDITION_CATALOG:
                errors.append(f"Rule {index} has unsupported operator: {rule.operator}")

            if rule.operator == "between":
                if rule.lower is None or rule.upper is None:
                    errors.append(f"Rule {index} between operator requires lower and upper")
                elif rule.lower >= rule.upper:
                    errors.append(f"Rule {index} lower must be less than upper")
                if rule.threshold is not None:
                    errors.append(f"Rule {index} between operator must not use threshold")
            elif rule.operator in {"gt", "gte", "lt", "lte"}:
                if rule.threshold is None:
                    errors.append(f"Rule {index} {rule.operator} operator requires threshold")
                if rule.lower is not None or rule.upper is not None:
                    errors.append(f"Rule {index} {rule.operator} operator must not use lower or upper")

        if errors:
            raise StrategyValidationError(errors)
