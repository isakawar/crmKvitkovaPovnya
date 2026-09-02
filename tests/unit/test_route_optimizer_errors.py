"""_parse_error: structured optimizer errors map to typed exceptions."""
import pytest

from app.services.route_optimizer_service import (
    _parse_error,
    RouteOptimizerError,
    RouteOptimizerInfeasibleError,
    RouteOptimizerAllFailedError,
)


def test_infeasible_top_level():
    with pytest.raises(RouteOptimizerInfeasibleError) as exc:
        _parse_error(
            {"error": "INFEASIBLE", "message": "треба 3", "minimum_couriers_required": 3},
            422,
        )
    assert exc.value.minimum_couriers_required == 3


def test_all_geocoding_failed_nested_under_detail():
    failed = [{"id": 42, "address": "Київ, Мартинова 30", "reason": "GEOCODING_FAILED"}]
    with pytest.raises(RouteOptimizerAllFailedError) as exc:
        _parse_error({"detail": {"error": "ALL_GEOCODING_FAILED", "failedOrders": failed}}, 422)
    assert exc.value.failed_orders == failed


def test_all_geocoding_failed_top_level():
    with pytest.raises(RouteOptimizerAllFailedError):
        _parse_error({"error": "ALL_GEOCODING_FAILED", "failedOrders": []}, 422)


def test_plain_string_detail():
    with pytest.raises(RouteOptimizerError, match="CSV parse error"):
        _parse_error({"detail": "CSV parse error: boom"}, 400)


def test_unknown_shape_falls_back():
    with pytest.raises(RouteOptimizerError, match="HTTP 500"):
        _parse_error({}, 500)
