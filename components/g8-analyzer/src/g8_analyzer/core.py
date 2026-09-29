"""装备纯计算逻辑。

改写自 dafaic0730/g8_plugins 的 g8_gear_analyzer，原项目使用 MIT 许可证。
本模块不依赖 AstrBot、OCR、图片或 HTML 渲染。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping


GOLD_ROLL_SCORES = {
    "攻击力%": {"avg": 6.0, "max": 8.0},
    "防御力%": {"avg": 6.0, "max": 8.0},
    "生命力%": {"avg": 6.0, "max": 8.0},
    "状态命中%": {"avg": 6.0, "max": 8.0},
    "状态抗性%": {"avg": 6.0, "max": 8.0},
    "速度": {"avg": 6.0, "max": 8.0},
    "暴击率%": {"avg": 6.4, "max": 8.0},
    "暴击伤害%": {"avg": 6.27, "max": 7.98},
    "攻击力": {"avg": 3.95, "max": 4.6},
    "防御力": {"avg": 5.25, "max": 5.83},
    "生命力": {"avg": 3.59, "max": 4.04},
}

PURPLE_ROLL_SCORES = {
    **GOLD_ROLL_SCORES,
    "速度": {"avg": 5.0, "max": 8.0},
    "攻击力": {"avg": 3.75, "max": 4.4},
    "防御力": {"avg": 4.91, "max": 5.5},
    "生命力": {"avg": 3.41, "max": 3.84},
}


def calculate_sub_score(stat_name: str, stat_value: str) -> float:
    is_percent = "%" in stat_value
    try:
        value = float(stat_value.replace("%", ""))
    except (TypeError, ValueError):
        return 0.0

    if stat_name == "速度":
        score = value * 2.0
    elif stat_name == "暴击率" and is_percent:
        score = value * 1.6
    elif stat_name == "暴击伤害" and is_percent:
        score = value * 1.14
    elif is_percent:
        score = value
    elif stat_name == "攻击力":
        score = value / 10.0
    elif stat_name == "防御力":
        score = value / 6.0
    elif stat_name == "生命力":
        score = value / 50.0
    else:
        score = 0.0
    return round(score, 1)


def evaluate_gear_tier(total_score: float) -> str:
    if total_score < 40:
        return "过渡使用"
    if total_score < 50:
        return "差点及格"
    if total_score < 60:
        return "及格"
    if total_score < 70:
        return "小毕业"
    return "大毕业"


def predict_potential(
    current_score: float,
    enhance_level: int,
    sub_stats: Iterable[Mapping[str, str]],
    grade: str,
) -> tuple[float, float]:
    remaining_rolls = max(0, (15 - int(enhance_level)) // 3)
    if remaining_rolls == 0:
        return round(current_score, 1), round(current_score, 1)

    reference = GOLD_ROLL_SCORES if grade == "传说" else PURPLE_ROLL_SCORES
    averages: list[float] = []
    maximums: list[float] = []
    for stat in sub_stats:
        name = str(stat.get("name") or "")
        value = str(stat.get("value") or "")
        key = name + ("%" if "%" in value else "")
        if key in reference:
            averages.append(reference[key]["avg"])
            maximums.append(reference[key]["max"])

    average_roll = sum(averages) / len(averages) if averages else 6.0
    maximum_roll = max(maximums) if maximums else 8.0
    return (
        round(current_score + remaining_rolls * average_roll, 1),
        round(current_score + remaining_rolls * maximum_roll, 1),
    )


def calculate_match_rate(
    character_data: Mapping[str, object],
    main_stat: Mapping[str, str] | None,
    sub_stats: Iterable[Mapping[str, str]],
    gear_set: str,
) -> tuple[float, bool]:
    configured_sets = [str(item) for item in character_data.get("sets", [])]
    set_matched = any(item in gear_set for item in configured_sets)
    weights = character_data.get("weights", {})
    if not isinstance(weights, Mapping):
        return 0.0, set_matched

    numerator = 0.0
    denominator = 0.0

    def add(stat: Mapping[str, str]) -> None:
        nonlocal numerator, denominator
        name = str(stat.get("name") or "")
        value = str(stat.get("value") or "")
        score = calculate_sub_score(name, value)
        if name in {"攻击力", "防御力", "生命力"} and "%" not in value:
            weight_key = name + "%"
        else:
            weight_key = name + ("%" if "%" in value else "")
        numerator += score * float(weights.get(weight_key, 0) or 0)
        denominator += score * 5.0

    if main_stat:
        add(main_stat)
    for sub_stat in sub_stats:
        add(sub_stat)
    if denominator == 0:
        return 0.0, set_matched
    match_rate = numerator / denominator * 100
    if not set_matched:
        match_rate *= 0.7
    return round(match_rate, 1), set_matched
