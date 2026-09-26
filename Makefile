.PHONY: test coupon

test:
	uv run pytest

coupon:
	uv run python -m tools.groove_coupon
