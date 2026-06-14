import math

def cost_calculation(color_mode: str,
                     bw_cost: int,
                     color_cost: int,
                     copies: int,
                     pages: int,
                     side_mode: str,
                     double_sided_discount_pct: int = 20) -> int:
    base_cost = pages * copies

    if color_mode == "bw":
        base_cost *= bw_cost
    else:
        base_cost *= color_cost

    if side_mode == "double" and pages > 1:
        base_cost *= (1 - double_sided_discount_pct / 100)

    return math.ceil(base_cost)