import json, hashlib

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def stable_hash(obj: dict) -> str:
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]

def calculate_net_margin_percent(
    price: float, 
    cost_per_unit: float, 
    shipping_per_unit: float = 0.0, 
    platform_fee_pct: float = 0.0
) -> float:
    """
    Calculate net margin percent as a % of the selling price.
    
    Args:
        price: Selling price per unit.
        cost_per_unit: Cost of producing one unit (COGS).
        shipping_per_unit: Shipping/fulfillment cost per unit (default 0.0).
        platform_fee_pct: Platform or payment fee in percent (default 0.0).

    Returns:
        Net margin percentage of selling price.
    """
    if price <= 0:
        return 0.0
    net_revenue = price * (1 - platform_fee_pct / 100)
    contribution_margin = net_revenue - cost_per_unit - shipping_per_unit
    net_margin_percent = (contribution_margin / price) * 100
    return net_margin_percent

def calculate_contribution_per_unit(
    price: float, 
    cost_per_unit: float, 
    shipping_per_unit: float = 0.0, 
    platform_fee_pct: float = 0.0
) -> float:
    """
    Calculate contribution per unit after fees, COGS, and shipping.
    
    Args:
        price: Selling price per unit.
        cost_per_unit: Cost of producing one unit (COGS).
        shipping_per_unit: Shipping/fulfillment cost per unit.
        platform_fee_pct: Platform/payment fee in percent.
    
    Returns:
        Contribution per unit in dollars.
    """
    net_revenue = price * (1 - platform_fee_pct / 100)
    contribution = net_revenue - cost_per_unit - shipping_per_unit
    return contribution

def calculate_monthly_profit(
    price: float,
    cost_per_unit: float,
    effective_demand: int,
    fixed_costs: float,
    shipping_per_unit: float = 0.0,
    platform_fee_pct: float = 0.0
) -> float:
    """
    Calculate monthly profit based on unit economics and fixed costs.

    Args:
        price: Selling price per unit.
        cost_per_unit: Cost to produce one unit.
        effective_demand: Units expected to sell in a month.
        fixed_costs: Fixed monthly costs.
        shipping_per_unit: Shipping/fulfillment cost per unit.
        platform_fee_pct: Platform/payment fee in percent.

    Returns:
        Monthly profit in dollars.
    """
    contribution = calculate_contribution_per_unit(price, cost_per_unit, shipping_per_unit, platform_fee_pct)
    monthly_profit = contribution * effective_demand - fixed_costs
    return monthly_profit


def get_recommended_price(competitor_low, competitor_high):
    recommended_price = (competitor_low + competitor_high) / 2
    return recommended_price