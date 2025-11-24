import pytest
from src.rules.parser import SafeExpressionParser


@pytest.fixture
def parser():
    return SafeExpressionParser()


def test_simple_comparison(parser):
    context = {"amount": 1000, "threshold": 500}
    result = parser.safe_eval("amount > threshold", context)
    assert result is True


def test_complex_expression(parser):
    context = {
        "amount": 5500,
        "user_risk_score": 85,
        "avg_amount": 200
    }
    expression = "amount > 5000 AND user_risk_score > 80"
    result = parser.safe_eval(expression, context)
    assert result is True


def test_arithmetic_operations(parser):
    context = {"a": 10, "b": 5, "c": 2}
    result = parser.safe_eval("(a + b) * c", context)
    assert result == 30


def test_logic_operators(parser):
    context = {"x": True, "y": False}
    
    assert parser.safe_eval("x AND y", context) is False
    assert parser.safe_eval("x OR y", context) is True
    assert parser.safe_eval("NOT y", context) is True


def test_invalid_variable(parser):
    context = {"amount": 100}
    
    with pytest.raises(ValueError, match="not allowed"):
        parser.safe_eval("undefined_var > 50", context)


def test_safe_evaluation_no_eval(parser):
    context = {"x": 10}
    
    with pytest.raises(ValueError):
        parser.safe_eval("__import__('os').system('ls')", context)


def test_fraud_rule_examples(parser):
    context = {
        "amount": 6000,
        "user_risk_score": 85,
        "transactions_per_hour": 12,
        "travel_speed": 1500,
        "merchant_new": True,
        "hour": 3
    }
    
    assert parser.safe_eval("amount > 5000 AND user_risk_score > 80", context) is True
    assert parser.safe_eval("transactions_per_hour > 10", context) is True
    assert parser.safe_eval("travel_speed > 1000", context) is True
    assert parser.safe_eval("merchant_new == True", context) is True
    assert parser.safe_eval("hour >= 2 AND hour <= 5 AND amount > 500", context) is True


def test_division_by_zero_handling(parser):
    context = {"a": 10, "b": 0}
    
    with pytest.raises(ZeroDivisionError):
        parser.safe_eval("a / b", context)
