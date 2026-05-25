from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .constants import *
from .codecs import signed_byte

def is_reserved_engine_event(event_id: int) -> bool:
    return int(event_id) in RESERVED_ENGINE_EVENTS


def reserved_event_info(event_id: int) -> Optional[Dict[str, str]]:
    return RESERVED_ENGINE_EVENTS.get(int(event_id))




PICKUP_MODIFIER_MEANINGS = {
    1: ("Invincibility", "touch pickup; gives temporary invincibility"),
    2: ("Health / carrot-like", "touch pickup; adds health"),
    3: ("Full health", "touch pickup; restores full health"),
    4: ("Extra life", "touch pickup; adds life"),
    5: ("High-jump feet", "touch pickup; increases jump height"),
    9: ("Sand timer", "touch pickup; adds timer"),
    10: ("Checkpoint", "touch trigger/pickup; sets checkpoint"),
    11: ("Generic score item", "touch pickup; item with score only"),
    12: ("Rapid fire", "touch pickup; increases fire speed"),
    15: ("Ammo weapon 0 x15", "touch ammo pickup"),
    16: ("Ammo weapon 1 x15", "touch ammo pickup"),
    17: ("Ammo weapon 2 x15", "touch ammo pickup"),
    18: ("Ammo weapon 0 x2", "small ammo pickup"),
    19: ("Ammo weapon 1 x2", "small ammo pickup"),
    20: ("Ammo weapon 2 x2", "small ammo pickup"),
    26: ("Fast feet box", "touch pickup; speed boost + music tempo"),
    27: ("End of level", "touch trigger; exits level"),
    30: ("TNT ammo x1", "touch ammo pickup"),
    31: ("Water level trigger", "touch trigger; sets water level to gridY+1"),
    33: ("1-hit shield", "touch pickup; shield=1"),
    34: ("Bird companion", "touch pickup; spawns bird helper"),
    35: ("Airboard / flight", "touch pickup; enables flight"),
    36: ("4-hit shield", "touch pickup; shield=5"),
    37: ("Diamond", "touch pickup; enables gem/diamond state"),
    39: ("Ammo weapon 3 x15", "touch ammo pickup"),
    40: ("Ammo weapon 3 x2", "small ammo pickup"),
    41: ("Bonus level / end trigger", "touch trigger; may set next level via multiA/multiB"),
}

MODIFIER_TOUCH_MEANINGS = {
    0: ("Enemy / hurt on touch", "if strength > 0, hurts player and can be killed; if strength == 0 and points/modifier logic allows, may be a touch pickup fallback"),
    7: ("Destructible / no touch pickup", "used with destructible blocks; contact does not consume it"),
    8: ("Boss / guardian", "boss-like hurt/end behavior"),
    13: ("Warp", "touch trigger; multiA/multiB are target X/Y"),
    28: ("Conveyor belt", "touch effect; magnitude controls push direction/speed"),
    29: ("Upwards spring", "touch effect; magnitude controls target height; sound is played"),
    31: ("Water level", "touch trigger; sets water level"),
    32: ("Float / side float", "touch effect; multiA/multiB choose float mode/height"),
    38: ("Airboard off", "touch trigger; disables flight"),
    **PICKUP_MODIFIER_MEANINGS,
}

TOUCH_MECHANISM_MODIFIERS = {28, 29, 31, 32}
REPEL_MOVEMENTS = {37, 38}

DIFFICULTY_LEVELS = {
    0: ("Easy+", "E", "visible on Easy, Medium, Hard, and Turbo"),
    1: ("Medium+", "M", "visible on Medium, Hard, and Turbo"),
    2: ("Hard+", "H", "visible on Hard and Turbo"),
    3: ("Turbo only", "T", "visible only on Turbo"),
}
DIFFICULTY_COMBO_LABELS = [f"{k}: {v[0]}" for k, v in DIFFICULTY_LEVELS.items()]

MOVEMENT_FIELD_MEANINGS = {
    0: ("Static", {}),
    1: ("Sink down", {}),
    2: ("Walk side-to-side", {"speed": "movement divisor", "left_anim": "walking left", "right_anim": "walking right"}),
    3: ("Seek Jazz horizontally", {"speed": "movement divisor"}),
    4: ("Walk side-to-side and fall/down hills", {"speed": "movement divisor", "strength": "enemy health if modifier=0"}),
    6: ("Use level path", {"multi_a": "path index", "speed": "mostly bypassed by path positioning"}),
    7: ("Use level path / flying snake", {"multi_a": "path index"}),
    11: ("Sink to ground", {}),
    12: ("Slow horizontal patrol", {"speed": "movement divisor"}),
    13: ("Slow vertical patrol", {"speed": "movement divisor"}),
    16: ("Move across level", {"magnitude": "horizontal direction/speed multiplier"}),
    21: ("Destructible block", {"strength": "hits required", "multi_a": "tile ID to set after destroyed", "finish_anim": "destroy animation"}),
    25: ("Float up / belt visual", {}),
    26: ("Flip animation on overlap", {"left_anim": "active/compressed", "right_anim": "idle"}),
    29: ("Rotate", {"piece_size": "radius piece size", "pieces": "radius count", "angle": "start angle", "magnitude": "rotation speed"}),
    30: ("Swing", {"piece_size": "radius piece size", "pieces": "radius count", "angle": "start angle", "magnitude": "swing speed"}),
    31: ("Fast horizontal platform", {"speed": "movement divisor"}),
    32: ("Horizontal platform with range", {"piece_size": "range in tiles"}),
    33: ("Sparks-like follower", {}),
    34: ("Launching event", {"multi_a": "launch height factor"}),
    37: ("Repel / sucker tube", {"multi_a": "height/strength parameter", "multi_b": "vertical mode flag", "magnitude": "direction sign"}),
    38: ("Repel / sucker tube variant", {"multi_a": "height/strength parameter", "multi_b": "vertical mode flag", "magnitude": "direction sign"}),
    39: ("Collapsing floor", {}),
    40: ("Monochrome effect", {}),
    42: ("Reflection effect", {}),
    45: ("Semitransparency effect", {}),
    53: ("Water-aware slow turtle movement", {}),
    57: ("Bubbles", {}),
}


def modifier_meaning(modifier: int) -> Tuple[str, str]:
    return MODIFIER_TOUCH_MEANINGS.get(int(modifier), (f"modifier_{modifier}", "unknown / event-specific modifier"))


def movement_meaning_detail(movement: int) -> Tuple[str, Dict[str, str]]:
    return MOVEMENT_FIELD_MEANINGS.get(int(movement), (movement_name(int(movement)), {}))


def difficulty_label(value: int) -> str:
    return DIFFICULTY_LEVELS.get(int(value), (f"Unknown difficulty {value}", "?", "unknown difficulty gate"))[0]


def difficulty_badge(value: int) -> str:
    return DIFFICULTY_LEVELS.get(int(value), ("", "?", ""))[1]


def difficulty_description(value: int) -> str:
    return DIFFICULTY_LEVELS.get(int(value), ("", "?", "unknown difficulty gate"))[2]


def semantic_event_category(event_id: int, raw: bytes, name: str = "") -> str:
    if event_id == 0:
        return "empty"
    if is_reserved_engine_event(event_id):
        return RESERVED_ENGINE_EVENTS[event_id]["category"]
    movement = raw[4] if len(raw) > 4 else 0
    strength = raw[9] if len(raw) > 9 else 0
    modifier = raw[10] if len(raw) > 10 else 0
    points = raw[11] if len(raw) > 11 else 0
    if modifier in PICKUP_MODIFIER_MEANINGS and strength == 0:
        return "pickup/touch item"
    if modifier in PICKUP_MODIFIER_MEANINGS and strength > 0:
        return "shootable pickup/container"
    if movement == 21 or modifier == 7:
        return "destructible/level geometry"
    if modifier in {28, 29, 31, 32, 38, 13} or movement in REPEL_MOVEMENTS:
        return "touch trigger/mechanism"
    if modifier == 0 and strength:
        return "enemy/hazard"
    if points and not strength:
        return "pickup/touch item"
    return classify_event(event_id, raw, name)


def semantic_event_lines(event_id: int, raw: bytes, name: str = "") -> List[str]:
    if event_id == 0:
        return ["Empty event slot / erase marker."]
    if is_reserved_engine_event(event_id):
        info = RESERVED_ENGINE_EVENTS[event_id]
        return [
            f"Reserved engine marker: {info['name']}",
            info["summary"],
            info["editor_hint"],
        ]

    movement = raw[4]
    modifier = raw[10]
    strength = raw[9]
    points = raw[11]
    magnitude = raw[8]
    speed = raw[15] + 1
    anim_speed = raw[17] + 1
    movement_label, movement_fields = movement_meaning_detail(movement)
    modifier_label, modifier_detail = modifier_meaning(modifier)
    category = semantic_event_category(event_id, raw, name)
    lines = [
        f"Semantic category: {category}",
        f"Difficulty gate: {difficulty_label(raw[0])} - {difficulty_description(raw[0])}",
        f"Modifier: {modifier} - {modifier_label}",
        f"  {modifier_detail}",
        f"Movement: {movement} - {movement_label}",
    ]

    if category == "shootable pickup/container":
        lines.extend([
            "This looks like a pickup effect hidden behind health/strength.",
            "strength > 0 means it must be hit/destroyed before the pickup/effect is awarded.",
            f"After destruction/takeEvent, modifier {modifier} gives: {modifier_label}.",
        ])
    elif category == "pickup/touch item":
        lines.append("strength == 0 means the player can collect/trigger it by touching it.")
    elif category == "enemy/hazard":
        lines.append("modifier 0 + strength > 0 is counted as enemy/hazard; touching hurts, hits can kill it.")
    elif category == "destructible/level geometry":
        lines.append("movement 21 / modifier 7 are commonly used for destructible blocks or geometry helpers.")

    mechanism = touch_mechanism_summary(raw)
    if mechanism:
        lines.extend(mechanism)

    if modifier in {15, 16, 17, 18, 19, 20, 30, 39, 40}:
        lines.append("Weapon/ammo identity is encoded by modifier, not by the generic pickup category.")

    if points:
        lines.append(f"Score added on successful collection/kill: points x10 = {points * 10}.")
    if strength:
        lines.append(f"Strength/health/hits: {strength}. Meaning depends on modifier/movement.")
    if raw[12]:
        lines.append(f"Bullet type reference: {raw[12]} - {bullet_type_label(raw[12])}.")
    if raw[13]:
        lines.append(f"Bullet period: {raw[13]}.")
    if raw[21]:
        lines.append(f"Sound effect index: {raw[21]}.")
    lines.append(f"Speed divisor: {speed}; animation speed: {anim_speed}.")
    signed_mag = magnitude - 256 if magnitude >= 128 else magnitude
    if magnitude:
        lines.append(f"Magnitude: raw {magnitude}, signed {signed_mag}. Meaning depends on modifier/movement.")

    for field, desc in movement_fields.items():
        idx = {
            "multi_a": 22, "multi_b": 23, "magnitude": 8, "speed": 15, "strength": 9,
            "piece_size": 24, "pieces": 25, "angle": 26, "left_anim": 5, "right_anim": 6,
            "finish_anim": 28,
        }.get(field)
        value = raw[idx] if idx is not None and idx < len(raw) else "?"
        if field == "speed":
            value = raw[15] + 1
        lines.append(f"{field}: {value} - {desc}")

    return lines


def event_field_label_for(raw: bytes, idx: int) -> str:
    base = EVENT_FIELD_NAMES[idx] if idx < len(EVENT_FIELD_NAMES) else f"byte_{idx:02d}"
    if base.startswith("unused"):
        return base
    movement = raw[4] if len(raw) > 4 else 0
    modifier = raw[10] if len(raw) > 10 else 0
    mapping = {
        0: "difficulty gate",
        2: "reflection / draw flags",
        4: "movement behavior",
        5: "left/primary animation",
        6: "right/secondary animation",
        8: "magnitude / signed parameter",
        9: "strength / health / required hits",
        10: "modifier / touch effect",
        11: "score points (x10)",
        12: "bullet type",
        13: "bullet period",
        15: "speed minus 1",
        17: "animation speed minus 1",
        21: "sound effect",
        22: "multiA",
        23: "multiB",
        24: "piece size / range",
        25: "pieces / count",
        26: "angle",
        28: "finish left animation",
        29: "finish right animation",
        30: "shoot left animation",
        31: "shoot right animation",
    }
    label = mapping.get(idx, base)
    if idx == 22 and movement in {6, 7}:
        label = "path index (multiA)"
    elif idx == 22 and modifier == 13:
        label = "warp target X (multiA)"
    elif idx == 23 and modifier == 13:
        label = "warp target Y (multiB)"
    elif idx == 22 and modifier == 41:
        label = "bonus/next level (multiA)"
    elif idx == 23 and modifier == 41:
        label = "bonus/next world (multiB)"
    elif idx == 10:
        label = "modifier / pickup identity"
    elif idx == 9 and modifier in PICKUP_MODIFIER_MEANINGS:
        label = "strength: 0 touch, >0 shootable"
    elif idx == 8 and modifier == 28:
        label = "belt push X signed (magnitude)"
    elif idx == 8 and modifier == 29:
        label = "spring target offset signed (magnitude)"
    elif idx == 8 and movement in REPEL_MOVEMENTS:
        label = "repel X direction sign (magnitude)"
    elif idx == 22 and modifier == 32:
        label = "float height/strength (multiA)"
    elif idx == 23 and modifier == 32:
        label = "float vertical mode flag (multiB)"
    elif idx == 22 and movement in REPEL_MOVEMENTS:
        label = "repel height/strength (multiA)"
    elif idx == 23 and movement in REPEL_MOVEMENTS:
        label = "repel vertical mode flag (multiB)"
    return label


def _event_value(raw: bytes, idx: int, default: int = 0) -> int:
    return raw[idx] if idx < len(raw) else default


def touch_mechanism_summary(raw: bytes) -> List[str]:
    movement = _event_value(raw, 4)
    magnitude = signed_byte(_event_value(raw, 8))
    modifier = _event_value(raw, 10)
    multi_a = signed_byte(_event_value(raw, 22))
    multi_b = signed_byte(_event_value(raw, 23))
    lines: List[str] = []

    if movement in REPEL_MOVEMENTS:
        if multi_b:
            if multi_a > 0:
                direction = "left" if magnitude < 0 else "right"
                lines.append(
                    f"Repel/sucker movement: pushes horizontally {direction} and pulls up by multiA*3 pixels ({multi_a})."
                )
            else:
                lines.append("Repel/sucker movement: vertical down mode because multiB is set and multiA <= 0.")
            lines.append(f"Repel vertical velocity seed: multiA * -24 = {multi_a * -24}.")
        else:
            direction = "left" if magnitude < 0 else "right"
            lines.append(f"Repel/sucker movement: horizontal repel mode, direction sign from magnitude ({direction}).")

    if modifier == 28:
        direction = "left" if magnitude < 0 else ("right" if magnitude > 0 else "none")
        lines.append(f"Belt/conveyor touch effect: moves player {direction}; per-touch X push is magnitude*64 ({magnitude * 64}).")
    elif modifier == 29:
        lines.append(f"Upwards spring touch effect: target Y offset is magnitude*21 pixels ({magnitude * 21}); plays the sound field.")
    elif modifier == 31:
        lines.append("Water-level touch effect: sets water level to the tile just below this event.")
    elif modifier == 32:
        if multi_b:
            lines.append(f"Float touch effect: vertical lift mode; target is multiA*17 pixels above the tile ({multi_a * 17}).")
        else:
            lines.append("Float touch effect: horizontal float mode; direction is controlled by the player's stored float state.")

    return lines


def event_force_overlay(raw: bytes) -> Optional[Dict[str, object]]:
    movement = _event_value(raw, 4)
    magnitude = signed_byte(_event_value(raw, 8))
    modifier = _event_value(raw, 10)
    multi_a = signed_byte(_event_value(raw, 22))
    multi_b = signed_byte(_event_value(raw, 23))

    if modifier == 28 and magnitude:
        return {
            "dx": 1 if magnitude > 0 else -1,
            "dy": 0,
            "label": f"belt {magnitude:+d}",
            "color": "#ffdd40",
        }
    if modifier == 32:
        if multi_b:
            return {
                "dx": 0,
                "dy": -1 if multi_a >= 0 else 1,
                "label": f"float {multi_a}",
                "color": "#50e6ff",
            }
        return {
            "dx": 1 if magnitude >= 0 else -1,
            "dy": 0,
            "label": "float H",
            "color": "#50e6ff",
        }
    if movement in REPEL_MOVEMENTS:
        if multi_b:
            dx = 1 if magnitude >= 0 else -1
            dy = -1 if multi_a > 0 else 1
            label = f"repel {multi_a}"
        else:
            dx = 1 if magnitude >= 0 else -1
            dy = 0
            label = "repel H"
        return {"dx": dx, "dy": dy, "label": label, "color": "#ff66d8"}
    return None




BULLET_TYPE_HINTS = {
    0: "Weapon 0 / blaster-like projectile",
    1: "Weapon 1 projectile",
    2: "Weapon 2 projectile",
    3: "Weapon 3 projectile",
    4: "TNT / explosive",
}


def bullet_type_label(bullet_id: int) -> str:
    bullet_id = int(bullet_id)
    return BULLET_TYPE_HINTS.get(bullet_id, f"Bullet type {bullet_id}")


EVENT_CONCEPTS = [
    "Unused / empty",
    "Auto / keep current",
    "Enemy / hazard",
    "Touch pickup / item",
    "Shootable pickup / container",
    "Destructible block",
    "Spring / bounce",
    "Warp trigger",
    "Conveyor belt",
    "Float / blower",
    "Repel / sucker tube",
    "Path-moving object",
    "Foreground / engine marker",
    "Raw / advanced",
]

PICKUP_COMBO_LABELS = [f"{k}: {v[0]}" for k, v in sorted(PICKUP_MODIFIER_MEANINGS.items())]
PICKUP_COMBO_TO_MODIFIER = {label: int(label.split(":", 1)[0]) for label in PICKUP_COMBO_LABELS}


def infer_event_concept(event_id: int, raw: bytes, name: str = "") -> str:
    if event_id == 0:
        return "Unused / empty"
    if not any(raw) and not name:
        return "Unused / empty"
    if is_reserved_engine_event(event_id):
        return "Foreground / engine marker"
    category = semantic_event_category(event_id, raw, name)
    modifier = raw[10]
    movement = raw[4]
    strength = raw[9]
    if modifier == 28:
        return "Conveyor belt"
    if modifier == 32:
        return "Float / blower"
    if movement in REPEL_MOVEMENTS:
        return "Repel / sucker tube"
    if category == "shootable pickup/container":
        return "Shootable pickup / container"
    if category == "pickup/touch item":
        return "Touch pickup / item"
    if category == "enemy/hazard":
        return "Enemy / hazard"
    if movement == 21 or modifier == 7:
        return "Destructible block"
    if modifier == 29:
        return "Spring / bounce"
    if modifier == 13:
        return "Warp trigger"
    if movement in {6, 7}:
        return "Path-moving object"
    return "Raw / advanced"


def _first_modifier_for_pickup() -> int:
    return 11

EDITABLE_EVENT_FIELD_INDICES = [i for i, name in enumerate(EVENT_FIELD_NAMES) if not name.startswith("unused")]

def movement_name(value: int) -> str:
    names = {
        0: "static", 2: "walker/platform-like", 4: "fall/drop", 6: "fly/hover", 12: "fly right", 16: "fly left",
        21: "shoot/destructible block", 23: "water/ambient mover", 26: "spring/bouncer", 28: "bridge",
        29: "swinger", 30: "spike/particle", 31: "ledge mover", 33: "spark", 34: "bouncer/hazard",
        37: "push/force", 38: "particle/debris", 49: "boss",
    }
    return names.get(value, f"movement_{value}")


def classify_event(event_id: int, raw: bytes, name: str) -> str:
    if event_id == 0:
        return "empty"
    if is_reserved_engine_event(event_id):
        return RESERVED_ENGINE_EVENTS[event_id]["category"]
    n = (name or "").lower()
    strength = raw[9] if len(raw) > 9 else 0
    modifier = raw[10] if len(raw) > 10 else 0
    points = raw[11] if len(raw) > 11 else 0
    movement = raw[4] if len(raw) > 4 else 0
    if any(k in n for k in ["spring", "bouncer", "bounce", "repel", "jump"]):
        return "trampoline/spring"
    if movement == 26 or modifier == 29:
        return "trampoline/spring"
    if any(k in n for k in ["wall", "blox", "block", "bridge", "ledge", "push"]):
        return "mechanism/destructible"
    if movement in {21, 28, 31, 37} or modifier in {6, 7, 38, 41}:
        return "mechanism/destructible"
    if any(k in n for k in ["carrot", "ball", "orb", "1up", "shield", "shoes", "weapon", "fire", "bird", "time", "autofire", "ammo", "gem", "coin"]):
        return "pickup/powerup"
    if points and not strength:
        return "pickup/powerup"
    if strength and modifier == 0:
        return "enemy/hazard"
    if strength >= 20:
        return "enemy/hazard"
    if points:
        return "pickup/powerup"
    return "trigger/other"


def event_summary(event_id: int, raw: bytes, name: str) -> str:
    if event_id == 0:
        return "empty"
    if is_reserved_engine_event(event_id):
        info = RESERVED_ENGINE_EVENTS[event_id]
        return f"{event_id:03d} {info['name']}  [{info['category']}]  RESERVED ENGINE MARKER"
    category = classify_event(event_id, raw, name)
    return (
        f"{event_id:03d} {name or '(unnamed)'}  [{category}]  "
        f"movement={raw[4]} {movement_name(raw[4])}, strength={raw[9]}, modifier={raw[10]}, "
        f"points={raw[11]}, anim={raw[5]}/{raw[6]}"
    )


def human_event_description(ev: EventDefinition) -> str:
    if ev.event_id == 0:
        return "empty / no object"
    if is_reserved_engine_event(ev.event_id):
        info = RESERVED_ENGINE_EVENTS[ev.event_id]
        return f"{info['name']}; {info['summary']}"
    raw = ev.raw
    name = (ev.name or "").lower()
    category = ev.category
    bits: List[str] = []
    if category == "pickup/powerup":
        bits.append("collectible / reward")
        if raw[11]:
            bits.append(f"{raw[11]} points")
        if any(k in name for k in ["carrot", "food"]):
            bits.append("heals Jazz")
        if any(k in name for k in ["ammo", "weapon", "fire"]):
            bits.append("weapon/ammo pickup")
    elif category == "enemy/hazard":
        bits.append("enemy or hazard")
        if raw[9]:
            bits.append(f"strength/health {raw[9]}")
        if raw[11]:
            bits.append(f"{raw[11]} points")
        if raw[12]:
            bits.append(f"shoots bullet {raw[12]}")
    elif category == "trampoline/spring":
        bits.append("spring / trampoline / bounce object")
        if raw[8]:
            bits.append(f"bounce magnitude {raw[8]}")
    elif category == "mechanism/destructible":
        bits.append("mechanism / destructible / level geometry helper")
        if raw[9]:
            bits.append(f"takes {raw[9]} hit(s)")
    else:
        bits.append("trigger / scripted / special object")
    movement = movement_name(raw[4])
    if raw[4]:
        bits.append(movement)
    if raw[21]:
        bits.append(f"sound {raw[21]}")
    if raw[5] or raw[6]:
        bits.append(f"anim {raw[5]}/{raw[6]}")
    return "; ".join(bits)




def friendly_event_name(ev: "EventDefinition") -> str:
    """Return a cautious human-readable object label.

    JJ1 event IDs are level-local, so this intentionally avoids pretending that
    every numeric ID is globally known. It describes the behavior implied by the
    event definition and uses the original event name when present.
    """
    if ev.event_id == 0:
        return "Empty / erase event"
    if is_reserved_engine_event(ev.event_id):
        return RESERVED_ENGINE_EVENTS[ev.event_id]["name"]
    raw = ev.raw
    original = ev.name.strip()
    category = ev.category
    movement = movement_name(raw[4])
    left = raw[5] & 0x7F
    right = raw[6] & 0x7F
    base = original or ""
    if not base:
        if category == "pickup/powerup":
            if raw[11]:
                base = f"Pickup / reward ({raw[11]} pts)"
            else:
                base = "Pickup / powerup"
        elif category == "enemy/hazard":
            base = "Enemy / hazard"
        elif category == "trampoline/spring":
            base = "Spring / trampoline"
        elif category == "mechanism/destructible":
            if raw[4] == 21 or raw[9]:
                base = "Destructible block / mechanism"
            elif raw[4] in {28, 31}:
                base = "Platform / bridge mechanism"
            else:
                base = "Mechanism / level geometry helper"
        else:
            base = "Trigger / special event"
    details: List[str] = []
    if category == "enemy/hazard":
        if raw[9]:
            details.append(f"health {raw[9]}")
        if raw[11]:
            details.append(f"{raw[11]} pts")
        if raw[12]:
            details.append(f"shoots bullet {raw[12]}")
    elif category == "trampoline/spring":
        if raw[8]:
            # Values are unsigned bytes but many spring magnitudes are effectively negative/upward.
            signed = raw[8] - 256 if raw[8] >= 128 else raw[8]
            details.append(f"bounce {signed}")
    elif category == "mechanism/destructible":
        if raw[9]:
            details.append(f"{raw[9]} hit(s)")
        if raw[4]:
            details.append(movement)
    elif category == "pickup/powerup":
        if raw[21]:
            details.append(f"sound {raw[21]}")
    if left or right:
        details.append(f"anim {left}/{right}")
    if details:
        return f"{base} - {', '.join(details)}"
    return base


def object_tooltip(ev: "EventDefinition") -> str:
    raw = ev.raw
    if is_reserved_engine_event(ev.event_id):
        info = RESERVED_ENGINE_EVENTS[ev.event_id]
        return (
            f"Event {ev.event_id:03d}: {info['name']}\n"
            f"Category: {info['category']}\n"
            f"Scope: reserved engine marker ID, not a normal level-local object type\n"
            f"Meaning: {info['summary']}\n"
            f"Editor: {info['editor_hint']}\n"
            f"Raw event definition bytes still exist in the level, but the key behavior is tied to the numeric event ID."
        )
    return (
        f"Event {ev.event_id:03d}: {friendly_event_name(ev)}\n"
        f"Category: {ev.category}\n"
        f"Behavior: movement={raw[4]} ({movement_name(raw[4])}), strength={raw[9]}, "
        f"modifier={raw[10]}, points={raw[11]}, bullet={raw[12]}, sound={raw[21]}\n"
        f"Animations: left/right={raw[5] & 0x7F}/{raw[6] & 0x7F}, "
        f"finish={raw[28] & 0x7F}/{raw[29] & 0x7F}, shoot={raw[30] & 0x7F}/{raw[31] & 0x7F}"
    )



