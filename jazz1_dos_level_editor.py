#!/usr/bin/env python3
"""
Jazz Jackrabbit 1 DOS Data Level Editor v23 (reliable animation picker)

Standalone editor for original DOS Jazz Jackrabbit 1 data files. OpenJazz is used only as a reference for interpreting the original format.

This version uses two workspaces: BUILD for visual level construction and DEFINE for level-local object type authoring.

It also deliberately separates three concepts that are easy to mix up in
JJ1 levels:

* Tiles   - the visual 32x32 map grid and BG flag.
* Events  - numeric event IDs stored in map cells.
* Objects - concrete event placements/instances in the map, with sprite previews where available.

Requirements:
    python -m pip install pillow

Usage:
    python jazz1_dos_level_editor.py /path/to/JAZZ

Scope:
    Target: original Jazz Jackrabbit 1 DOS data files (LEVEL*, BLOCKS.*, SPRITES.*, MAINCHAR.000, etc.).
    Reference only: OpenJazz source code helps document how the original DOS data is parsed/interpreted.
    This is not an editor for an OpenJazz-specific project format.
"""
from __future__ import annotations

import argparse
import os
import struct
import sys
import subprocess
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from PIL import Image, ImageDraw, ImageTk
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Pillow is required. Install it with: python -m pip install pillow") from exc

LW = 256
LH = 64
TILE_SIZE = 32
CHUNK_TILES = 16
CHUNK_SIZE = TILE_SIZE * CHUNK_TILES
TNUM = 60
TSETS = 4
MASK_BYTES = ((TNUM * TSETS + 16) << 3)
PATH_BYTES = 16 << 9
EVENTS = 127
ELENGTH = 32
ANIMS = 128
SHORTNAME = 8
LONGNAME = 16
TKEY = 127

EVENT_FIELD_NAMES = [
    "difficulty", "unused_01", "reflection", "unused_03", "movement", "left_anim", "right_anim", "unused_07",
    "magnitude", "strength", "modifier", "points", "bullet", "bullet_period", "unused_14", "speed_minus_1",
    "unused_16", "anim_speed_minus_1", "unused_18", "unused_19", "unused_20", "sound", "multi_a", "multi_b",
    "piece_size", "pieces", "angle", "unused_27", "left_finish_anim", "right_finish_anim", "left_shoot_anim", "right_shoot_anim",
]


RESERVED_ENGINE_EVENTS = {
    122: {
        "name": "One-way platform marker",
        "category": "engine marker/collision",
        "summary": "Jump-through / semi-solid collision marker. checkMaskUp ignores this cell, checkMaskDown still uses the tile mask.",
        "editor_hint": "Place this event on a tile that has a collision mask. Do not duplicate its definition to make a new one-way type; the engine checks event ID 122 directly.",
    },
    123: {
        "name": "Animated foreground tile marker",
        "category": "engine marker/foreground",
        "summary": "Draws an animated foreground tile over the player. Uses event definition multiA/multiB as alternating tile indices.",
        "editor_hint": "Use for waterfall-like animated foreground overlay tiles. This behavior is hardcoded by event ID 123.",
    },
    124: {
        "name": "Foreground pass-through solid tile marker",
        "category": "engine marker/foreground",
        "summary": "Draws the tile again in the foreground while normal solidity is bypassed/treated specially by the engine/data pattern.",
        "editor_hint": "Use for tiles that visually appear in front of the player while acting pass-through in the intended setup.",
    },
    125: {
        "name": "Foreground decoration marker",
        "category": "engine marker/foreground",
        "summary": "Draws an otherwise background/decorative tile in front of the player, e.g. grass overlays.",
        "editor_hint": "Use for visual foreground decorations. It is a marker, not a normal object type.",
    },
    126: {
        "name": "Spike / hurt marker",
        "category": "engine marker/hazard",
        "summary": "Damage marker. checkSpikes only treats a masked tile as painful when the cell event is 126.",
        "editor_hint": "Place on a tile with an appropriate collision mask to make it hurt the player.",
    },
}

RESERVED_ENGINE_EVENT_START = min(RESERVED_ENGINE_EVENTS)
NORMAL_EDITABLE_EVENT_MAX = RESERVED_ENGINE_EVENT_START - 1


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
    15: ("Ammo weapon 0 ×15", "touch ammo pickup"),
    16: ("Ammo weapon 1 ×15", "touch ammo pickup"),
    17: ("Ammo weapon 2 ×15", "touch ammo pickup"),
    18: ("Ammo weapon 0 ×2", "small ammo pickup"),
    19: ("Ammo weapon 1 ×2", "small ammo pickup"),
    20: ("Ammo weapon 2 ×2", "small ammo pickup"),
    26: ("Fast feet box", "touch pickup; speed boost + music tempo"),
    27: ("End of level", "touch trigger; exits level"),
    30: ("TNT ammo ×1", "touch ammo pickup"),
    31: ("Water level trigger", "touch trigger; sets water level to gridY+1"),
    33: ("1-hit shield", "touch pickup; shield=1"),
    34: ("Bird companion", "touch pickup; spawns bird helper"),
    35: ("Airboard / flight", "touch pickup; enables flight"),
    36: ("4-hit shield", "touch pickup; shield=5"),
    37: ("Diamond", "touch pickup; enables gem/diamond state"),
    39: ("Ammo weapon 3 ×15", "touch ammo pickup"),
    40: ("Ammo weapon 3 ×2", "small ammo pickup"),
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
    if modifier == 0 and strength:
        return "enemy/hazard"
    if movement == 21 or modifier == 7:
        return "destructible/level geometry"
    if modifier in {28, 29, 31, 32, 38, 13}:
        return "touch trigger/mechanism"
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
        f"Modifier: {modifier} — {modifier_label}",
        f"  {modifier_detail}",
        f"Movement: {movement} — {movement_label}",
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

    if modifier in {15, 16, 17, 18, 19, 20, 30, 39, 40}:
        lines.append("Weapon/ammo identity is encoded by modifier, not by the generic pickup category.")

    if points:
        lines.append(f"Score added on successful collection/kill: points ×10 = {points * 10}.")
    if strength:
        lines.append(f"Strength/health/hits: {strength}. Meaning depends on modifier/movement.")
    if raw[12]:
        lines.append(f"Bullet type reference: {raw[12]} — {bullet_type_label(raw[12])}.")
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
        lines.append(f"{field}: {value} — {desc}")

    return lines


def event_field_label_for(raw: bytes, idx: int) -> str:
    base = EVENT_FIELD_NAMES[idx] if idx < len(EVENT_FIELD_NAMES) else f"byte_{idx:02d}"
    if base.startswith("unused"):
        return base
    movement = raw[4] if len(raw) > 4 else 0
    modifier = raw[10] if len(raw) > 10 else 0
    mapping = {
        0: "difficulty",
        2: "reflection / draw flags",
        4: "movement behavior",
        5: "left/primary animation",
        6: "right/secondary animation",
        8: "magnitude / signed parameter",
        9: "strength / health / required hits",
        10: "modifier / touch effect",
        11: "score points (×10)",
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
    return label




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
    if modifier == 28:
        return "Conveyor belt"
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
        return f"{base} — {', '.join(details)}"
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

def read_u16(data: bytes, pos: int) -> Tuple[int, int]:
    return data[pos] | (data[pos + 1] << 8), pos + 2


def write_u16(buf: bytearray, pos: int, value: int) -> None:
    value = max(0, min(0xFFFF, int(value)))
    buf[pos] = value & 0xFF
    buf[pos + 1] = (value >> 8) & 0xFF


def skip_c_string(data: bytes, pos: int, max_len: int) -> int:
    # OpenJazz loadTerminatedString(max_len) is length-prefixed and then padded
    # to a fixed max_len-byte field: total bytes consumed = 1 + max_len.
    return min(len(data), pos + max_len + 1)


def decode_rle_block(data: bytes, pos: int, expected_len: int) -> Tuple[bytes, int, int, int]:
    """Decode an OpenJazz RLE block with a two-byte compressed-size prefix."""
    if pos + 2 > len(data):
        raise ValueError(f"RLE block at 0x{pos:X} has no size prefix")
    compressed_size, payload_pos = read_u16(data, pos)
    end_pos = payload_pos + compressed_size
    if end_pos > len(data):
        raise ValueError(f"RLE block at 0x{pos:X} extends past EOF")

    out = bytearray()
    p = payload_pos
    while len(out) < expected_len and p < end_pos:
        code = data[p]
        p += 1
        amount = code & 0x7F
        if code & 0x80:
            if p >= end_pos:
                break
            value = data[p]
            p += 1
            if len(out) + amount >= expected_len:
                break
            out.extend([value] * amount)
        elif amount:
            if len(out) + amount >= expected_len:
                break
            out.extend(data[p:p + amount])
            p += amount
        else:
            if p >= end_pos:
                break
            out.append(data[p])
            p += 1
            break

    if len(out) < expected_len:
        out.extend(b"\x00" * (expected_len - len(out)))
    return bytes(out[:expected_len]), pos, payload_pos, end_pos


def encode_rle_block(raw: bytes) -> bytes:
    """Encode data into Jazz 1 DOS-compatible RLE.

    The original decoder treats copy/repeat chunks that exactly reach the target
    length as a terminator condition before copying, so this encoder emits the
    final byte using the special zero-length literal marker.
    """
    if not raw:
        payload = b"\x00\x00"
        return struct.pack("<H", len(payload)) + payload

    payload = bytearray()
    limit = len(raw) - 1
    i = 0
    while i < limit:
        run = 1
        max_run = min(126, limit - i)
        while run < max_run and raw[i + run] == raw[i]:
            run += 1
        if run >= 3:
            payload.append(0x80 | run)
            payload.append(raw[i])
            i += run
            continue

        start = i
        i += 1
        while i < limit and (i - start) < 126:
            next_run = 1
            max_next = min(126, limit - i)
            while next_run < max_next and raw[i + next_run] == raw[i]:
                next_run += 1
            if next_run >= 3:
                break
            i += 1
        payload.append(i - start)
        payload.extend(raw[start:i])

    payload.append(0)
    payload.append(raw[-1])
    if len(payload) > 0xFFFF:
        raise ValueError("Encoded RLE block is too large for a two-byte size field")
    return struct.pack("<H", len(payload)) + payload


def decode_palette(data: bytes, pos: int) -> Tuple[List[Tuple[int, int, int]], int, int, int]:
    raw, start, payload, end = decode_rle_block(data, pos, 256 * 3)
    palette = []
    for i in range(256):
        r, g, b = raw[i * 3:i * 3 + 3]
        palette.append(((r << 2) + (r >> 4), (g << 2) + (g >> 4), (b << 2) + (b >> 4)))
    return palette, start, payload, end


@dataclass
class RleSpan:
    name: str
    start: int
    payload_start: int
    end: int
    expected_len: int


@dataclass
class LevelMetadata:
    start_x: int = 0
    start_y: int = 0
    next_level: int = 0
    next_world: int = 0
    jump_height_raw: int = 0
    water_level: int = 0
    anim_speed: int = 0
    start_x_pos: int = -1
    start_y_pos: int = -1
    next_level_pos: int = -1
    next_world_pos: int = -1
    jump_height_pos: int = -1
    water_level_pos: int = -1
    anim_speed_pos: int = -1


@dataclass
class EventDefinition:
    event_id: int
    name: str
    raw: bytes

    @property
    def category(self) -> str:
        return semantic_event_category(self.event_id, self.raw, self.name)

    @property
    def is_reserved_engine_marker(self) -> bool:
        return is_reserved_engine_event(self.event_id)

    @property
    def movement(self) -> int:
        return self.raw[4]

    @property
    def strength(self) -> int:
        return self.raw[9]

    @property
    def modifier(self) -> int:
        return self.raw[10]

    @property
    def points(self) -> int:
        return self.raw[11]

    @property
    def left_anim(self) -> int:
        return self.raw[5]

    @property
    def right_anim(self) -> int:
        return self.raw[6]


@dataclass
class SpriteFrame:
    index: int
    image: Image.Image
    x_offset: int = 0
    y_offset: int = 0


@dataclass
class AnimationDefinition:
    anim_id: int
    name: str
    raw: bytes
    length: int
    frame_ids: List[int]
    frame_x: List[int]
    frame_y: List[int]

    @property
    def first_frame(self) -> Optional[int]:
        for frame in self.frame_ids:
            if frame >= 0:
                return frame
        return None


@dataclass
class PathDefinition:
    path_id: int
    raw: bytes
    length: int
    points: List[Tuple[int, int]]

    @property
    def nonempty(self) -> bool:
        return self.length > 0 and bool(self.points)


@dataclass
class SpriteSetData:
    path: Path
    main_path: Path
    sprites: List[SpriteFrame]

    def get(self, index: int) -> Optional[SpriteFrame]:
        if 0 <= index < len(self.sprites):
            frame = self.sprites[index]
            if frame.image.width > 0 and frame.image.height > 0:
                return frame
        return None


@dataclass
class ObjectPlacement:
    x: int
    y: int
    event: int
    tile: int
    bg: int
    name: str


@dataclass
class LevelData:
    path: Path
    raw_file: bytes
    spans: Dict[str, RleSpan]
    level_num: int
    world_num: int
    blocks_ext: str
    grid: List[List[Dict[str, int]]]
    event_types: List[bytes]
    event_names: List[str]
    animations: List[AnimationDefinition]
    animation_names: List[str]
    paths_raw: bytes
    path_defs: List[PathDefinition]
    masks: bytes
    metadata: LevelMetadata

    def event_def(self, event_id: int) -> EventDefinition:
        event_id = max(0, min(126, int(event_id)))
        name = self.event_names[event_id] if event_id < len(self.event_names) else ""
        return EventDefinition(event_id, name, self.event_types[event_id])

    def event_catalog(self) -> List[EventDefinition]:
        return [self.event_def(i) for i in range(EVENTS)]

    def animation(self, anim_id: int) -> Optional[AnimationDefinition]:
        anim_id = int(anim_id) & 0x7F
        if 0 <= anim_id < len(self.animations):
            return self.animations[anim_id]
        return None

    def mask_solid_at(self, tile: int, pixel_x: int, pixel_y: int) -> bool:
        # Each tile has an 8x8 low-resolution collision mask. One mask bit covers roughly 4x4 pixels.
        if tile < 0:
            return False
        idx = tile * 8 + (pixel_y >> 2)
        if idx < 0 or idx >= len(self.masks):
            return False
        return bool(self.masks[idx] & (1 << (pixel_x >> 2)))

    def tile_has_collision(self, tile: int) -> bool:
        start = tile * 8
        return 0 <= start < len(self.masks) and any(self.masks[start:start + 8])

    def grid_to_bytes(self) -> bytes:
        out = bytearray(LW * LH * 2)
        for x in range(LW):
            for y in range(LH):
                cell = self.grid[y][x]
                idx = (y + x * LH) * 2
                out[idx] = cell["tile"] & 0xFF
                out[idx + 1] = ((cell["bg"] & 1) << 7) | (cell["event"] & 0x7F)
        return bytes(out)

    def event_types_to_bytes(self) -> bytes:
        out = bytearray(EVENTS * ELENGTH)
        for i in range(EVENTS):
            raw = self.event_types[i] if i < len(self.event_types) else bytes(ELENGTH)
            out[i * ELENGTH:(i + 1) * ELENGTH] = bytes(raw[:ELENGTH]).ljust(ELENGTH, b"\0")
        return bytes(out)

    def paths_to_bytes(self) -> bytes:
        return bytes(self.paths_raw[:PATH_BYTES]).ljust(PATH_BYTES, b"\0")

    def masks_to_bytes(self) -> bytes:
        return bytes(self.masks[:MASK_BYTES]).ljust(MASK_BYTES, b"\0")

    def animations_to_bytes(self) -> bytes:
        out = bytearray(ANIMS << 6)
        for i in range(ANIMS):
            raw = self.animations[i].raw if i < len(self.animations) else bytes(64)
            out[i * 64:(i + 1) * 64] = bytes(raw[:64]).ljust(64, b"\0")
        return bytes(out)

    def set_path_points(self, path_id: int, points: List[Tuple[int, int]]) -> None:
        path_id = max(0, min(15, int(path_id)))
        points = points[:240]
        chunk = bytearray(512)
        chunk[0] = len(points) & 0xFF
        chunk[1] = (len(points) >> 8) & 0xFF
        for i, (dx, dy) in enumerate(points):
            # OpenJazz stores signed y first and signed x/4 second. Clamp to the data format.
            sx = max(-128, min(127, int(round(dx / 4))))
            sy = max(-128, min(127, int(dy)))
            off = 2 + i * 2
            chunk[off] = sy & 0xFF
            chunk[off + 1] = sx & 0xFF
        raw = bytearray(self.paths_raw[:PATH_BYTES]).ljust(PATH_BYTES, b"\0")
        raw[path_id * 512:(path_id + 1) * 512] = chunk
        self.paths_raw = bytes(raw)
        decoded = []
        for dx, dy in points:
            decoded.append((max(-128, min(127, int(round(dx / 4)))) << 2, max(-128, min(127, int(dy)))))
        self.path_defs[path_id] = PathDefinition(path_id, bytes(chunk), len(decoded), decoded)

    def set_tile_mask_rows(self, tile: int, rows: List[str]) -> None:
        tile = max(0, min(255, int(tile)))
        rows = rows[:8]
        raw = bytearray(self.masks[:MASK_BYTES]).ljust(MASK_BYTES, b"\0")
        start = tile * 8
        if start + 8 > len(raw):
            return
        for y in range(8):
            line = rows[y] if y < len(rows) else ""
            byte = 0
            for x, ch in enumerate((line + "........")[:8]):
                if ch in "#1Xx@█":
                    byte |= 1 << x
            raw[start + y] = byte
        self.masks = bytes(raw)

    def set_animation_frames(self, anim_id: int, frames: List[Tuple[int, int, int]]) -> None:
        anim_id = max(0, min(ANIMS - 1, int(anim_id)))
        frames = frames[:19]
        old = bytearray(self.animations[anim_id].raw if anim_id < len(self.animations) else bytes(64))
        old = bytearray(bytes(old[:64]).ljust(64, b"\0"))
        old[6] = len(frames) & 0xFF
        for i in range(19):
            frame_id = frames[i][0] if i < len(frames) else 0
            xoff = frames[i][1] if i < len(frames) else 0
            yoff = frames[i][2] if i < len(frames) else 0
            old[7 + i] = max(0, min(255, int(frame_id)))
            old[26 + i] = max(-128, min(127, int(xoff))) & 0xFF
            old[45 + i] = max(-128, min(127, int(yoff))) & 0xFF
        name = self.animations[anim_id].name if anim_id < len(self.animations) else ""
        frame_ids = [f for f, _x, _y in frames]
        frame_x = [x for _f, x, _y in frames]
        frame_y = [y for _f, _x, y in frames]
        self.animations[anim_id] = AnimationDefinition(anim_id, name, bytes(old), len(frames), frame_ids, frame_x, frame_y)

    def objects(self) -> List[ObjectPlacement]:
        result: List[ObjectPlacement] = []
        for y in range(LH):
            for x in range(LW):
                cell = self.grid[y][x]
                event = cell["event"]
                if event:
                    name = self.event_names[event] if event < len(self.event_names) else ""
                    result.append(ObjectPlacement(x, y, event, cell["tile"], cell["bg"], name))
        return result

    def save_as(self, target: Path, save_event_defs: bool = False, save_paths: bool = False, save_masks: bool = False, save_animations: bool = False) -> None:
        replacements: List[Tuple[str, bytes]] = [("grid", encode_rle_block(self.grid_to_bytes()))]
        if save_masks:
            replacements.append(("masks", encode_rle_block(self.masks_to_bytes())))
        if save_paths:
            replacements.append(("paths", encode_rle_block(self.paths_to_bytes())))
        if save_event_defs:
            replacements.append(("events", encode_rle_block(self.event_types_to_bytes())))
        if save_animations:
            replacements.append(("animations", encode_rle_block(self.animations_to_bytes())))

        patched = bytearray(self.raw_file)
        deltas: List[Tuple[int, int, int]] = []  # original start, original end, delta
        for name, block in sorted(replacements, key=lambda item: self.spans[item[0]].start, reverse=True):
            span = self.spans[name]
            patched[span.start:span.end] = block
            deltas.append((span.start, span.end, len(block) - (span.end - span.start)))

        def shifted(pos: int) -> int:
            # Replacements are recorded against original file coordinates.
            # A metadata byte moves by every earlier block whose original end is before it.
            offset = 0
            for start, end, delta in deltas:
                if pos > end:
                    offset += delta
            return pos + offset

        md = self.metadata
        if md.start_x_pos >= 0:
            write_u16(patched, shifted(md.start_x_pos), md.start_x)
        if md.start_y_pos >= 0:
            # OpenJazz adds +1 after reading; store visual/editor y - 1 back to file.
            write_u16(patched, shifted(md.start_y_pos), max(0, md.start_y - 1))
        if md.next_level_pos >= 0:
            patched[shifted(md.next_level_pos)] = md.next_level & 0xFF
        if md.next_world_pos >= 0:
            patched[shifted(md.next_world_pos)] = md.next_world & 0xFF
        if md.jump_height_pos >= 0:
            write_u16(patched, shifted(md.jump_height_pos), md.jump_height_raw)
        if md.water_level_pos >= 0:
            write_u16(patched, shifted(md.water_level_pos), md.water_level)
        if md.anim_speed_pos >= 0:
            patched[shifted(md.anim_speed_pos)] = md.anim_speed & 0xFF
        target.write_bytes(bytes(patched))


@dataclass
class TilesetData:
    path: Path
    palette: List[Tuple[int, int, int]]
    tiles: List[Image.Image]
    atlas: Image.Image


class JJ1Parser:
    def __init__(self, game_dir: Path):
        self.game_dir = game_dir

    def find_file(self, name: str) -> Path:
        for candidate in (self.game_dir / name, self.game_dir / name.upper(), self.game_dir / name.lower()):
            if candidate.exists():
                return candidate
        for child in self.game_dir.iterdir():
            if child.name.upper() == name.upper():
                return child
        raise FileNotFoundError(name)

    def level_files(self) -> List[Path]:
        files = [p for p in self.game_dir.iterdir() if p.is_file() and p.name.upper().startswith("LEVEL")]
        return sorted(files, key=lambda p: p.name.upper())

    def parse_level(self, path: Path) -> LevelData:
        data = path.read_bytes()
        if len(data) < 3 or data[:2] != b"DD" or data[2] != 0x1A:
            raise ValueError(f"{path.name} is not a JJ1 level file")

        spans: Dict[str, RleSpan] = {}
        pos = 39
        for name in [
            "prescan_0", "prescan_1", "prescan_2", "prescan_3",
            "prescan_4", "prescan_5", "prescan_6", "prescan_7",
        ]:
            _, start, payload, end = decode_rle_block(data, pos, 1)
            spans[name] = RleSpan(name, start, payload, end, -1)
            pos = end
        pos += 598
        _, start, payload, end = decode_rle_block(data, pos, 1)
        spans["prescan_8"] = RleSpan("prescan_8", start, payload, end, -1)
        pos = end + 4
        for name in ["prescan_9", "prescan_10"]:
            _, start, payload, end = decode_rle_block(data, pos, 1)
            spans[name] = RleSpan(name, start, payload, end, -1)
            pos = end
        pos += 25
        _, start, payload, end = decode_rle_block(data, pos, 1)
        spans["prescan_11"] = RleSpan("prescan_11", start, payload, end, -1)
        pos = end + 3

        level_num = data[pos] ^ 210
        world_num = data[pos + 1] ^ 4
        pos += 2 + 8
        ext_len = min(data[pos], 3)
        blocks_ext = data[pos + 1:pos + 1 + ext_len].decode("ascii", errors="replace")

        pos = 39
        raw_grid, start, payload, end = decode_rle_block(data, pos, LW * LH * 2)
        spans["grid"] = RleSpan("grid", start, payload, end, LW * LH * 2)
        pos = end

        _, start, payload, end = decode_rle_block(data, pos, LW * LH)
        spans["transparency"] = RleSpan("transparency", start, payload, end, LW * LH)
        pos = end

        masks_raw, start, payload, end = decode_rle_block(data, pos, MASK_BYTES)
        spans["masks"] = RleSpan("masks", start, payload, end, MASK_BYTES)
        pos = end

        paths_raw, start, payload, end = decode_rle_block(data, pos, PATH_BYTES)
        spans["paths"] = RleSpan("paths", start, payload, end, PATH_BYTES)
        pos = end

        event_raw, start, payload, end = decode_rle_block(data, pos, EVENTS * ELENGTH)
        spans["events"] = RleSpan("events", start, payload, end, EVENTS * ELENGTH)
        event_types = [event_raw[i * ELENGTH:(i + 1) * ELENGTH] for i in range(EVENTS)]
        pos = end

        names_raw, start, payload, end = decode_rle_block(data, pos, EVENTS * LONGNAME)
        spans["event_names"] = RleSpan("event_names", start, payload, end, EVENTS * LONGNAME)
        event_names = []
        for i in range(EVENTS):
            chunk = names_raw[i * LONGNAME:(i + 1) * LONGNAME]
            n = min(chunk[0], LONGNAME - 1)
            event_names.append(chunk[1:1 + n].decode("ascii", errors="replace").strip("\x00"))
        pos = end

        # Skip through the OpenJazz layout to find metadata offsets that are not part of the map grid.
        metadata = LevelMetadata()
        try:
            anim_raw, start, payload, end = decode_rle_block(data, pos, ANIMS << 6)
            spans["animations"] = RleSpan("animations", start, payload, end, ANIMS << 6)
            pos = end
            anim_names_raw, start, payload, end = decode_rle_block(data, pos, ANIMS * LONGNAME)
            spans["animation_names"] = RleSpan("animation_names", start, payload, end, ANIMS * LONGNAME)
            pos = end
            pos += 16 * (SHORTNAME + 1) + 9
            pos += 2 * 32  # sound rates, 32 little-endian shorts
            for _ in range(32):
                pos = skip_c_string(data, pos, SHORTNAME)
            pos = skip_c_string(data, pos, 12)  # music file
            pos += 13  # start cutscene
            pos = skip_c_string(data, pos, 12)  # end scene
            pos += 39  # editor tileset files
            metadata.start_x_pos = pos
            metadata.start_x, pos = read_u16(data, pos)
            metadata.start_y_pos = pos
            stored_y, pos = read_u16(data, pos)
            metadata.start_y = min(LH - 1, stored_y + 1)
            metadata.next_level_pos = pos
            metadata.next_level = data[pos]
            pos += 1
            metadata.next_world_pos = pos
            metadata.next_world = data[pos]
            pos += 1
            metadata.jump_height_pos = pos
            metadata.jump_height_raw, pos = read_u16(data, pos)
            pos += 2
            metadata.water_level_pos = pos
            metadata.water_level, pos = read_u16(data, pos)
            metadata.anim_speed_pos = pos
            metadata.anim_speed = data[pos]
        except Exception:
            metadata = LevelMetadata()

        grid: List[List[Dict[str, int]]] = [[{"tile": 0, "bg": 0, "event": 0} for _ in range(LW)] for _ in range(LH)]
        for x in range(LW):
            for y in range(LH):
                idx = (y + x * LH) * 2
                grid[y][x] = {
                    "tile": raw_grid[idx],
                    "bg": raw_grid[idx + 1] >> 7,
                    "event": raw_grid[idx + 1] & 0x7F,
                }

        animations: List[AnimationDefinition] = []
        animation_names: List[str] = []
        # These variables are only present if metadata parsing got far enough. If not, keep safe blanks.
        if 'anim_raw' not in locals():
            anim_raw = bytes(ANIMS << 6)
        if 'anim_names_raw' not in locals():
            anim_names_raw = bytes(ANIMS * LONGNAME)
        for i in range(ANIMS):
            raw = anim_raw[i * 64:(i + 1) * 64]
            length = raw[6] if len(raw) > 6 else 0
            length = max(0, min(19, length))
            frame_ids = [raw[7 + j] for j in range(length) if 7 + j < len(raw)]
            frame_x = [struct.unpack('b', raw[26 + j:27 + j])[0] for j in range(length) if 26 + j < len(raw)]
            frame_y = [struct.unpack('b', raw[45 + j:46 + j])[0] for j in range(length) if 45 + j < len(raw)]
            chunk = anim_names_raw[i * LONGNAME:(i + 1) * LONGNAME]
            n = min(chunk[0], LONGNAME - 1) if chunk else 0
            aname = chunk[1:1 + n].decode("ascii", errors="replace").strip("\x00") if chunk else ""
            animation_names.append(aname)
            animations.append(AnimationDefinition(i, aname, raw, length, frame_ids, frame_x, frame_y))

        path_defs: List[PathDefinition] = []
        for path_id in range(16):
            chunk = paths_raw[path_id * 512:(path_id + 1) * 512]
            if len(chunk) < 2:
                path_defs.append(PathDefinition(path_id, chunk, 0, []))
                continue
            raw_len = chunk[0] | (chunk[1] << 8)
            length = max(0, min(raw_len, 240))
            points: List[Tuple[int, int]] = []
            for j in range(length):
                off = 2 + j * 2
                if off + 1 >= len(chunk):
                    break
                # Jazz 1/OpenJazz-reference reads y from the first signed byte and x from the second signed byte << 2.
                y_delta = struct.unpack('b', chunk[off:off + 1])[0]
                x_delta = struct.unpack('b', chunk[off + 1:off + 2])[0] << 2
                points.append((x_delta, y_delta))
            path_defs.append(PathDefinition(path_id, chunk, length, points))

        return LevelData(path, data, spans, level_num, world_num, blocks_ext, grid, event_types, event_names, animations, animation_names, paths_raw, path_defs, masks_raw, metadata)

    def load_tileset_for_level(self, level: LevelData) -> TilesetData:
        ext = f"{level.world_num:03d}" if level.blocks_ext == "999" else level.blocks_ext.zfill(3)
        path = self.find_file(f"BLOCKS.{ext}")
        return self.parse_tileset(path)

    def parse_tileset(self, path: Path) -> TilesetData:
        data = path.read_bytes()
        pos = 0
        palette, _, _, pos = decode_palette(data, pos)
        _, _, _, pos = decode_palette(data, pos)
        _, _, _, pos = decode_rle_block(data, pos, 256 * 3)

        tiles: List[Image.Image] = []
        flat_palette: List[int] = []
        for r, g, b in palette:
            flat_palette.extend([r, g, b])
        for set_index in range(TSETS):
            marker = data[pos:pos + 2]
            pos += 2
            if marker == b"ok":
                for _ in range(TNUM):
                    raw, _, _, pos = decode_rle_block(data, pos, TILE_SIZE * TILE_SIZE)
                    img = Image.frombytes("P", (TILE_SIZE, TILE_SIZE), raw)
                    img.putpalette(flat_palette)
                    tiles.append(img.convert("RGBA"))
            elif marker == b"  ":
                continue
            else:
                raise ValueError(f"Unexpected tileset marker {marker!r} in {path.name} at 0x{pos - 2:X}")

        columns = 20
        rows = max(1, (len(tiles) + columns - 1) // columns)
        atlas = Image.new("RGBA", (columns * TILE_SIZE, rows * TILE_SIZE), (0, 0, 0, 0))
        for i, tile in enumerate(tiles):
            atlas.paste(tile, ((i % columns) * TILE_SIZE, (i // columns) * TILE_SIZE))
        return TilesetData(path, palette, tiles, atlas)

    def load_sprites_for_level(self, level: LevelData, palette: List[Tuple[int, int, int]]) -> Optional[SpriteSetData]:
        try:
            spec_path = self.find_file(f"SPRITES.{level.world_num:03d}")
            main_path = self.find_file("MAINCHAR.000")
            return self.parse_sprites(spec_path, main_path, palette)
        except Exception:
            return None

    def parse_sprites(self, spec_path: Path, main_path: Path, palette: List[Tuple[int, int, int]]) -> SpriteSetData:
        spec = spec_path.read_bytes()
        main = main_path.read_bytes()
        if len(spec) < 2:
            raise ValueError(f"{spec_path.name} is too small")
        sprite_count = min(256, spec[0] | (spec[1] << 8))
        offsets_start = 2
        offsets_end = offsets_start + sprite_count * 2
        if offsets_end > len(spec):
            raise ValueError(f"{spec_path.name} has truncated sprite offsets")
        xoffs = [spec[offsets_start + i] << 2 for i in range(sprite_count)]
        yoffs = [spec[offsets_start + sprite_count + i] for i in range(sprite_count)]
        sprites: List[SpriteFrame] = []
        main_pos = 2
        spec_pos = offsets_end
        for i in range(sprite_count):
            frame = None
            if main_pos < len(main):
                frame, main_pos = _read_one_jj1_sprite(main, main_pos, i, palette, xoffs[i], yoffs[i])
            if spec_pos < len(spec):
                spec_frame, spec_pos = _read_one_jj1_sprite(spec, spec_pos, i, palette, xoffs[i], yoffs[i])
                if spec_frame is not None:
                    frame = spec_frame
            if frame is None:
                frame = SpriteFrame(i, Image.new("RGBA", (1, 1), (0, 0, 0, 0)), xoffs[i], yoffs[i])
            sprites.append(frame)
        sprites.append(SpriteFrame(sprite_count, Image.new("RGBA", (1, 1), (0, 0, 0, 0)), 0, 0))
        return SpriteSetData(spec_path, main_path, sprites)


def _signed_byte(value: int) -> int:
    return value - 256 if value >= 128 else value


def _unscramble_pixels(raw: bytes, length: int) -> bytes:
    if len(raw) < length:
        raw = raw + bytes(length - len(raw))
    return bytes(raw[(i >> 2) + ((i & 3) * (length >> 2))] for i in range(length))


def _sprite_from_pixels(index: int, pixels: bytes, width: int, height: int, palette: List[Tuple[int, int, int]], xoff: int, yoff: int) -> SpriteFrame:
    if width <= 0 or height <= 0:
        return SpriteFrame(index, Image.new("RGBA", (1, 1), (0, 0, 0, 0)), xoff, yoff)
    rgba = bytearray()
    for v in pixels[:width * height]:
        if v == 254:
            rgba.extend((0, 0, 0, 0))
        else:
            r, g, b = palette[v] if 0 <= v < len(palette) else (255, 0, 255)
            rgba.extend((r, g, b, 255))
    return SpriteFrame(index, Image.frombytes("RGBA", (width, height), bytes(rgba)), xoff, yoff)


def _read_one_jj1_sprite(data: bytes, p: int, index: int, palette: List[Tuple[int, int, int]], xoff: int, yoff: int) -> Tuple[Optional[SpriteFrame], int]:
    if p >= len(data):
        return None, p
    if data[p] == 0xFF:
        return None, min(len(data), p + 2)
    if p + 10 > len(data):
        return None, len(data)
    width = (data[p] | (data[p + 1] << 8)) << 2
    height = data[p + 2] | (data[p + 3] << 8)
    mask_offset = data[p + 6] | (data[p + 7] << 8)
    pos_words = data[p + 8] | (data[p + 9] << 8)
    pos_bytes = pos_words << 2
    cur = p + 10
    if width <= 0 or height <= 0:
        return _sprite_from_pixels(index, b"", 1, 1, palette, xoff, yoff), cur
    length = width * height
    if mask_offset:
        h2 = height + 1
        length2 = width * h2
        mask_start = cur + mask_offset
        mask_bytes = (width >> 2) * h2
        if mask_start + mask_bytes > len(data):
            return None, len(data)
        mask_data = data[mask_start:mask_start + mask_bytes]
        scrambled_mask = bytearray(length2)
        for count in range(length2):
            m = mask_data[count >> 2] if (count >> 2) < len(mask_data) else 0
            scrambled_mask[count] = (m >> (count & 3)) & 1
        sorted_mask = bytearray(length2)
        for count in range(length2):
            sorted_mask[(count >> 2) + ((count & 3) * (length2 >> 2))] = scrambled_mask[count]
        pix_scrambled = bytearray([254] * length2)
        pp = mask_start + mask_bytes
        for count in range(length2):
            if sorted_mask[count]:
                if pp >= len(data):
                    break
                # Original loader avoids transparent key in masked solid pixels.
                val = data[pp]
                pp += 1
                while val == 254 and pp < len(data):
                    val = data[pp]
                    pp += 1
                pix_scrambled[count] = val
        pixels = _unscramble_pixels(bytes(pix_scrambled), length2)
        end = p + 10 + mask_offset + mask_bytes + pos_bytes
        return _sprite_from_pixels(index, pixels, width, h2, palette, xoff, yoff), min(len(data), max(pp, end))
    else:
        if cur + length > len(data):
            return None, len(data)
        pixels = _unscramble_pixels(data[cur:cur + length], length)
        return _sprite_from_pixels(index, pixels, width, height, palette, xoff, yoff), cur + length

class LevelEditorApp(tk.Tk):
    def __init__(self, game_dir: Path):
        super().__init__()
        self.title("Jazz Jackrabbit 1 DOS Data Level Editor v23")
        self.geometry("1420x880")
        self.minsize(1100, 700)

        self.parser = JJ1Parser(game_dir)
        self.level: Optional[LevelData] = None
        self.tileset: Optional[TilesetData] = None
        self.spriteset: Optional[SpriteSetData] = None
        self.level_paths: List[Path] = []

        self.tool_mode = tk.StringVar(value="tiles")
        self.current_tile = tk.IntVar(value=0)
        self.current_event = tk.IntVar(value=0)
        self.current_bg = tk.IntVar(value=0)
        self.paint_bg = tk.BooleanVar(value=False)
        self.zoom = tk.IntVar(value=1)
        self.show_grid = tk.BooleanVar(value=True)
        self.show_events = tk.BooleanVar(value=True)
        self.show_bg_overlay = tk.BooleanVar(value=False)
        self.show_collision = tk.BooleanVar(value=False)
        self.show_player_start = tk.BooleanVar(value=True)
        self.show_object_sprites = tk.BooleanVar(value=True)
        self.show_event_labels = tk.BooleanVar(value=True)
        self.show_paths = tk.BooleanVar(value=False)
        self.show_object_names = tk.BooleanVar(value=False)
        self.show_water_level = tk.BooleanVar(value=True)
        self.fast_paint = tk.BooleanVar(value=True)
        self.show_brush_preview = tk.BooleanVar(value=True)
        self.lock_tiles = tk.BooleanVar(value=False)
        self.lock_events = tk.BooleanVar(value=False)
        self.lock_objects = tk.BooleanVar(value=False)
        self.lock_start = tk.BooleanVar(value=False)
        self.highlight_event_id = tk.IntVar(value=0)
        self.save_event_defs_var = tk.BooleanVar(value=False)
        self.save_paths_var = tk.BooleanVar(value=False)
        self.save_masks_var = tk.BooleanVar(value=False)
        self.save_animations_var = tk.BooleanVar(value=False)
        self.object_category_filter = tk.StringVar(value="all")
        self.selected_path = tk.IntVar(value=0)
        self._editing_event_id = 0
        self.status = tk.StringVar(value="Open a Jazz Jackrabbit DOS directory or choose a level.")

        self.selected_object: Optional[Tuple[int, int]] = None
        self.move_object_mode = tk.BooleanVar(value=False)
        self.undo_stack: List[Tuple[bytes, Tuple[int, int, int, int, int, int, int]]] = []
        self.redo_stack: List[Tuple[bytes, Tuple[int, int, int, int, int, int, int]]] = []
        self.max_undo = 80

        self._map_photo: Optional[ImageTk.PhotoImage] = None
        self._atlas_photo: Optional[ImageTk.PhotoImage] = None
        self._object_icon_photos: Dict[int, ImageTk.PhotoImage] = {}
        self._sprite_photo_refs: List[ImageTk.PhotoImage] = []
        self._event_preview_cache: Dict[Tuple[int, int], Optional[Image.Image]] = {}
        self._rendered_map: Optional[Image.Image] = None
        self._last_painted_cell: Optional[Tuple[int, int]] = None
        self._paint_stroke_active = False
        self._stroke_cells: set[Tuple[int, int]] = set()
        self._dirty_chunks: set[Tuple[int, int]] = set()
        self._chunk_photos: Dict[Tuple[int, int], ImageTk.PhotoImage] = {}
        self._chunk_items: Dict[Tuple[int, int], int] = {}
        self._brush_preview_items: List[int] = []
        self._brush_preview_photos: List[ImageTk.PhotoImage] = []
        self._asset_photo_refs: List[ImageTk.PhotoImage] = []
        self.dirty = False
        self.current_save_path: Optional[Path] = None

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._build_ui()
        self._load_level_list()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=6)
        root.pack(fill=tk.BOTH, expand=True)

        toolbar = ttk.Frame(root)
        toolbar.pack(fill=tk.X)
        ttk.Button(toolbar, text="Open game dir", command=self.open_game_dir).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Reload", command=self.reload_current).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(toolbar, text="Save", command=self.save).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(toolbar, text="Save as...", command=self.save_as).pack(side=tk.LEFT, padx=(3, 0))
        ttk.Button(toolbar, text="Undo", command=self.undo).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(toolbar, text="Redo", command=self.redo).pack(side=tk.LEFT, padx=(3, 0))
        ttk.Button(toolbar, text="Validate", command=self.refresh_validation).pack(side=tk.LEFT, padx=(6, 0))
        self.bind_all("<Control-s>", lambda _e: self.save())
        self.bind_all("<Control-z>", lambda _e: self.undo())
        self.bind_all("<Control-y>", lambda _e: self.redo())
        self.bind_all("<Control-Shift-Z>", lambda _e: self.redo())
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=8, fill=tk.Y)
        ttk.Label(toolbar, text="Level:").pack(side=tk.LEFT)
        self.level_combo = ttk.Combobox(toolbar, state="readonly", width=24)
        self.level_combo.pack(side=tk.LEFT, padx=(4, 8))
        self.level_combo.bind("<<ComboboxSelected>>", lambda _e: self.request_load_selected_level())
        ttk.Label(toolbar, text="Zoom:").pack(side=tk.LEFT)
        ttk.Spinbox(toolbar, from_=1, to=4, textvariable=self.zoom, width=4, command=self.render_map).pack(side=tk.LEFT, padx=(4, 8))
        ttk.Checkbutton(toolbar, text="Grid", variable=self.show_grid, command=self.render_map).pack(side=tk.LEFT)
        ttk.Checkbutton(toolbar, text="Events", variable=self.show_events, command=self.render_map).pack(side=tk.LEFT)
        ttk.Checkbutton(toolbar, text="BG overlay", variable=self.show_bg_overlay, command=self.render_map).pack(side=tk.LEFT)
        ttk.Checkbutton(toolbar, text="Collision", variable=self.show_collision, command=self.render_map).pack(side=tk.LEFT)
        ttk.Checkbutton(toolbar, text="Player start", variable=self.show_player_start, command=self.render_map).pack(side=tk.LEFT)
        ttk.Checkbutton(toolbar, text="Object sprites", variable=self.show_object_sprites, command=self.render_map).pack(side=tk.LEFT)
        ttk.Checkbutton(toolbar, text="Event labels", variable=self.show_event_labels, command=self.render_map).pack(side=tk.LEFT)
        ttk.Checkbutton(toolbar, text="Paths", variable=self.show_paths, command=self.render_map).pack(side=tk.LEFT)
        ttk.Checkbutton(toolbar, text="Names", variable=self.show_object_names, command=self.render_map).pack(side=tk.LEFT)
        ttk.Checkbutton(toolbar, text="Water", variable=self.show_water_level, command=self.render_map).pack(side=tk.LEFT)
        ttk.Checkbutton(toolbar, text="Fast paint", variable=self.fast_paint, command=self.render_map).pack(side=tk.LEFT)
        ttk.Checkbutton(toolbar, text="Brush preview", variable=self.show_brush_preview).pack(side=tk.LEFT)

        modebar = ttk.LabelFrame(root, text="Editing mode", padding=6)
        modebar.pack(fill=tk.X, pady=(6, 0))
        for value, text in [
            ("tiles", "Tiles: edit visual tile/BG only"),
            ("events", "Events: edit numeric event ID only"),
            ("objects", "Objects: select/move/delete placed events"),
            ("start", "Start: place player start only"),
            ("inspect", "Inspect: no editing"),
        ]:
            ttk.Radiobutton(modebar, text=text, value=value, variable=self.tool_mode, command=self._mode_changed).pack(side=tk.LEFT, padx=(0, 12))

        self.main_tabs = ttk.Notebook(root)
        self.main_tabs.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        self.level_editor_page = ttk.Frame(self.main_tabs)
        self.assets_browser_page = ttk.Frame(self.main_tabs)
        self.main_tabs.add(self.level_editor_page, text="Level Editor")
        self.main_tabs.add(self.assets_browser_page, text="Assets Browser")

        panes = ttk.PanedWindow(self.level_editor_page, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(panes)
        panes.add(left, weight=5)
        right = ttk.Frame(panes)
        panes.add(right, weight=2)

        self.canvas = tk.Canvas(left, background="#202020", highlightthickness=0)
        hbar = ttk.Scrollbar(left, orient=tk.HORIZONTAL, command=self.canvas.xview)
        vbar = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Button-3>", self.erase_from_map)
        self.canvas.bind("<Shift-Button-3>", self.pick_from_map)
        self.canvas.bind("<Button-2>", self.pick_from_map)
        self.canvas.bind("<Motion>", self.on_canvas_motion)

        self.workspace_tabs = ttk.Notebook(right)
        self.workspace_tabs.pack(fill=tk.BOTH, expand=True)

        self.build_workspace = ttk.Frame(self.workspace_tabs)
        self.define_workspace = ttk.Frame(self.workspace_tabs)
        self.event_defs_workspace = ttk.Frame(self.workspace_tabs)
        self.workspace_tabs.add(self.build_workspace, text="BUILD")
        self.workspace_tabs.add(self.event_defs_workspace, text="EVENT DEFS")
        self.workspace_tabs.add(self.define_workspace, text="LEVEL LOCAL")

        self.build_tabs = ttk.Notebook(self.build_workspace)
        self.build_tabs.pack(fill=tk.BOTH, expand=True)
        self.define_tabs = ttk.Notebook(self.define_workspace)
        self.define_tabs.pack(fill=tk.BOTH, expand=True)
        self.event_defs_tabs = ttk.Notebook(self.event_defs_workspace)
        self.event_defs_tabs.pack(fill=tk.BOTH, expand=True)

        self.tabs = self.build_tabs
        self._build_objects_tab()
        self._build_tiles_tab()
        self._build_metadata_tab()
        self._build_layers_tab()

        self.tabs = self.event_defs_tabs
        self._build_event_defs_tab()

        self.tabs = self.define_tabs
        self._build_animations_tab()
        self._build_paths_tab()
        self._build_masks_tab()
        self._build_events_tab()
        self._build_validation_tab()

        self.game_tabs = ttk.Notebook(self.assets_browser_page)
        self.game_tabs.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.tabs = self.game_tabs
        self._build_game_assets_tab()
        self._build_game_tilesets_tab()
        self._build_game_sprites_tab()
        self._build_game_audio_tab()

        self.tabs = self.define_tabs

        bottom_info = ttk.Frame(root)
        bottom_info.pack(fill=tk.X, pady=(6, 0))
        self.cell_label = ttk.Label(bottom_info, text="Cell: -", relief=tk.SUNKEN, anchor="w")
        self.cell_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.object_label = ttk.Label(bottom_info, text="Object: none", relief=tk.SUNKEN, anchor="w")
        self.object_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))
        ttk.Button(bottom_info, text="Edit type", command=self.jump_to_selected_object_type).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Button(bottom_info, text="Duplicate type", command=self.duplicate_selected_object_definition).pack(side=tk.LEFT, padx=(4, 0))

        statusbar = ttk.Label(root, textvariable=self.status, relief=tk.SUNKEN, anchor="w")
        statusbar.pack(fill=tk.X, pady=(3, 0))


    def _build_build_overview_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Build")
        ttk.Label(
            tab,
            text="BUILD is the normal WYSIWYG level-design workspace. Use object prefabs/types from this level, place them on the map, move them, delete them, and keep raw definitions out of the way.",
            wraplength=420,
        ).pack(anchor="w")
        flow = ttk.LabelFrame(tab, text="Recommended workflow", padding=6)
        flow.pack(fill=tk.X, pady=(8, 8))
        for line in [
            "1. Pick an object type from Objects palette.",
            "2. Paint or move it in Objects mode; right-click erases events/blocks.",
            "3. Use Tiles mode only for visual blocks/BG.",
            "4. Use Layers to show sprites, names, collision, paths and water.",
            "5. When behavior must change, jump to DEFINE or duplicate the type first.",
        ]:
            ttk.Label(flow, text=line).pack(anchor="w")
        actions = ttk.LabelFrame(tab, text="Build shortcuts", padding=6)
        actions.pack(fill=tk.X)
        ttk.Button(actions, text="Open object prefab palette", command=lambda: self.build_tabs.select(self.objects_tab)).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Open tile palette", command=lambda: self.build_tabs.select(self.tiles_tab)).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Open layer controls", command=lambda: self.build_tabs.select(self.layers_tab)).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Switch to LEVEL LOCAL", command=lambda: self.workspace_tabs.select(self.define_workspace)).pack(fill=tk.X, pady=(8, 2))

    def _build_define_overview_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Define")
        ttk.Label(
            tab,
            text="LEVEL LOCAL edits definitions stored inside the currently opened level file. These are not game-global hardcoded objects: changing Event 12 changes every Event 12 placement only in this level file.",
            wraplength=420,
        ).pack(anchor="w")
        flow = ttk.LabelFrame(tab, text="Safe authoring workflow", padding=6)
        flow.pack(fill=tk.X, pady=(8, 8))
        for line in [
            "• To change one placed object: select it in BUILD, then duplicate its type.",
            "• To change all objects of a type: edit the shared Event Definition here.",
            "• Event definitions, animations, paths and masks here are level-local shared definitions.",
            "• Advanced tables are saved only when their save checkbox is enabled.",
        ]:
            ttk.Label(flow, text=line).pack(anchor="w")
        actions = ttk.LabelFrame(tab, text="Definition shortcuts", padding=6)
        actions.pack(fill=tk.X)
        ttk.Button(actions, text="Object Types", command=lambda: self.define_tabs.select(self.object_types_tab)).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Event Definitions", command=lambda: self.define_tabs.select(self.global_event_defs_tab)).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Animations", command=lambda: self.define_tabs.select(self.global_animations_tab)).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Paths", command=lambda: self.define_tabs.select(self.global_paths_tab)).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Game Globals", command=lambda: self.workspace_tabs.select(self.game_globals_workspace)).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Back to BUILD", command=lambda: self.workspace_tabs.select(self.build_workspace)).pack(fill=tk.X, pady=(8, 2))

    def jump_to_selected_object_type(self) -> None:
        if not self.level:
            return
        event_id = self.current_event.get()
        if self.selected_object is not None:
            event_id = self.selected_object[0] if isinstance(self.selected_object, int) else self.level.grid[self.selected_object[1]][self.selected_object[0]]["event"]
        self.workspace_tabs.select(self.event_defs_workspace)
        if hasattr(self, "event_defs_tabs") and hasattr(self, "event_concept_tab"):
            self.event_defs_tabs.select(self.event_concept_tab)
        self.highlight_event_id.set(event_id)
        self.current_event.set(event_id)
        self.refresh_event_def_selector()
        self.select_event_definition(event_id)
        self.status.set(f"Editing Event {event_id:03d}.")



    def _build_game_globals_overview_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Game Globals")
        ttk.Label(
            tab,
            text="GAME GLOBALS are files/assets from the Jazz installation that are shared by many levels or by the whole game. They are not stored inside the current LEVEL file.",
            wraplength=440,
        ).pack(anchor="w")
        table = ttk.LabelFrame(tab, text="Where things live", padding=6)
        table.pack(fill=tk.X, pady=(8, 8))
        rows = [
            ("LEVEL PLACEMENT", "current LEVEL file", "tile ID, BG flag, event ID placed at x/y"),
            ("LEVEL LOCAL DEFINITIONS", "current LEVEL file", "event definitions, level animations, paths, tile collision masks, start/next/water metadata"),
            ("GAME GLOBAL ASSETS", "separate game files", "BLOCKS.xxx tilesets/palettes, SPRITES.xxx, MAINCHAR.000, PSM music, sounds/cutscenes/resource files"),
            ("ENGINE GLOBAL BEHAVIOR", "Jazz 1 DOS engine / OpenJazz reference code", "meaning of movement values, physics, pickup/enemy behavior, rendering rules"),
        ]
        for r, (scope, where, examples) in enumerate(rows):
            ttk.Label(table, text=scope, font=("", 9, "bold")).grid(row=r, column=0, sticky="nw", padx=(0, 8), pady=3)
            ttk.Label(table, text=where).grid(row=r, column=1, sticky="nw", padx=(0, 8), pady=3)
            ttk.Label(table, text=examples, wraplength=250).grid(row=r, column=2, sticky="nw", pady=3)
        actions = ttk.LabelFrame(tab, text="Game-global browsers", padding=6)
        actions.pack(fill=tk.X, pady=(4, 8))
        ttk.Button(actions, text="Refresh all game-global tabs", command=self.refresh_game_global_tabs).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Game files / assets", command=lambda: self.game_tabs.select(self.game_assets_tab)).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Tilesets / BLOCKS.xxx", command=lambda: self.game_tabs.select(self.game_tilesets_tab)).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Sprites / MAINCHAR + SPRITES.xxx", command=lambda: self.game_tabs.select(self.game_sprites_tab)).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Back to BUILD", command=lambda: self.workspace_tabs.select(self.build_workspace)).pack(fill=tk.X, pady=(8, 2))
        note = tk.Text(tab, height=10, wrap="word")
        note.pack(fill=tk.BOTH, expand=True)
        note.insert("1.0", "\n".join([
            "Practical rule:",
            "",
            "• If changing it should affect only the opened level, it belongs in LEVEL LOCAL.",
            "• If changing it would affect many levels or the game installation, it belongs in GAME GLOBALS.",
            "• If it is hardcoded in Jazz 1 DOS engine behavior / OpenJazz reference behavior, it is ENGINE GLOBAL and should be documented/read-only unless the editor later supports code patches.",
        ]))
        note.configure(state="disabled")

    def _build_game_assets_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.game_assets_tab = tab
        self.tabs.add(tab, text="Assets")
        ttk.Label(tab, text="Read-only browser of game-global files in the selected Jazz installation. These are outside the current level file.", wraplength=430).pack(anchor="w")
        row = ttk.Frame(tab)
        row.pack(fill=tk.X, pady=(6, 4))
        ttk.Button(row, text="Refresh asset list", command=self.refresh_game_assets).pack(side=tk.LEFT)
        self.asset_filter_var = tk.StringVar(value="all")
        ttk.Label(row, text="Filter").pack(side=tk.LEFT, padx=(8, 2))
        combo = ttk.Combobox(row, state="readonly", width=16, textvariable=self.asset_filter_var, values=["all", "levels", "tilesets", "sprites", "music", "sounds", "other"])
        combo.pack(side=tk.LEFT)
        combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_game_assets())
        columns = ("scope", "kind", "file", "note")
        self.game_assets_tree = ttk.Treeview(tab, columns=columns, show="headings", height=18, selectmode="browse")
        for col, width, title in [("scope", 105, "Scope"), ("kind", 85, "Kind"), ("file", 145, "File"), ("note", 260, "Meaning")]:
            self.game_assets_tree.heading(col, text=title)
            self.game_assets_tree.column(col, width=width, stretch=(col == "note"))
        self.game_assets_tree.pack(fill=tk.BOTH, expand=True)

    def _build_game_tilesets_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.game_tilesets_tab = tab
        self.tabs.add(tab, text="Tilesets")
        row = ttk.Frame(tab)
        row.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(row, text="Refresh", command=self.refresh_game_tilesets).pack(side=tk.LEFT)
        ttk.Label(row, text="Click a BLOCKS file to preview its tile atlas.").pack(side=tk.LEFT, padx=(8, 0))

        body = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(body)
        body.add(left, weight=1)
        right = ttk.Frame(body)
        body.add(right, weight=3)

        columns = ("file", "used_by", "tiles")
        self.game_tilesets_tree = ttk.Treeview(left, columns=columns, show="headings", height=18, selectmode="browse")
        for col, width, title in [("file", 110, "Tileset"), ("used_by", 75, "Levels"), ("tiles", 60, "Tiles")]:
            self.game_tilesets_tree.heading(col, text=title)
            self.game_tilesets_tree.column(col, width=width, stretch=(col == "file"))
        self.game_tilesets_tree.pack(fill=tk.BOTH, expand=True)
        self.game_tilesets_tree.bind("<<TreeviewSelect>>", self.on_game_tileset_select)

        self.asset_tileset_canvas = tk.Canvas(right, background="#181818", highlightthickness=0)
        yscroll = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self.asset_tileset_canvas.yview)
        xscroll = ttk.Scrollbar(right, orient=tk.HORIZONTAL, command=self.asset_tileset_canvas.xview)
        self.asset_tileset_canvas.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.asset_tileset_canvas.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

    def _build_game_sprites_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.game_sprites_tab = tab
        self.tabs.add(tab, text="Sprites")
        row = ttk.Frame(tab)
        row.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(row, text="Refresh", command=self.refresh_game_sprites).pack(side=tk.LEFT)
        ttk.Label(row, text="Click a SPRITES file to preview a sprite atlas.").pack(side=tk.LEFT, padx=(8, 0))

        body = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(body)
        body.add(left, weight=1)
        right = ttk.Frame(body)
        body.add(right, weight=3)

        columns = ("file", "scope")
        self.game_sprites_tree = ttk.Treeview(left, columns=columns, show="headings", height=18, selectmode="browse")
        for col, width, title in [("file", 140, "File"), ("scope", 120, "Scope")]:
            self.game_sprites_tree.heading(col, text=title)
            self.game_sprites_tree.column(col, width=width, stretch=(col == "file"))
        self.game_sprites_tree.pack(fill=tk.BOTH, expand=True)
        self.game_sprites_tree.bind("<<TreeviewSelect>>", self.on_game_sprite_select)

        self.asset_sprite_canvas = tk.Canvas(right, background="#181818", highlightthickness=0)
        yscroll = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self.asset_sprite_canvas.yview)
        xscroll = ttk.Scrollbar(right, orient=tk.HORIZONTAL, command=self.asset_sprite_canvas.xview)
        self.asset_sprite_canvas.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.asset_sprite_canvas.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

    def _build_game_audio_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.game_audio_tab = tab
        self.tabs.add(tab, text="Audio")
        row = ttk.Frame(tab)
        row.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(row, text="Refresh", command=self.refresh_game_audio).pack(side=tk.LEFT)
        ttk.Button(row, text="Open selected externally", command=self.open_selected_audio_external).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Label(row, text="Native playback/export for JJ1 audio formats is a future decoder step.").pack(side=tk.LEFT, padx=(8, 0))

        columns = ("kind", "file", "size")
        self.game_audio_tree = ttk.Treeview(tab, columns=columns, show="headings", height=22, selectmode="browse")
        for col, width, title in [("kind", 100, "Kind"), ("file", 220, "File"), ("size", 80, "Bytes")]:
            self.game_audio_tree.heading(col, text=title)
            self.game_audio_tree.column(col, width=width, stretch=(col == "file"))
        self.game_audio_tree.pack(fill=tk.BOTH, expand=True)


    def _make_image_atlas(self, images: List[Image.Image], cell: int = 40, columns: int = 12, label_prefix: str = "") -> Image.Image:
        rows = max(1, (len(images) + columns - 1) // columns)
        atlas = Image.new("RGBA", (columns * cell, rows * (cell + 12)), (24, 24, 24, 255))
        draw = ImageDraw.Draw(atlas)
        for i, img in enumerate(images):
            x = (i % columns) * cell
            y = (i // columns) * (cell + 12)
            draw.rectangle((x, y, x + cell - 1, y + cell - 1), outline=(70, 70, 70, 255))
            if img is not None:
                thumb = img.copy().convert("RGBA")
                thumb.thumbnail((cell - 4, cell - 4), Image.Resampling.NEAREST)
                atlas.alpha_composite(thumb, (x + (cell - thumb.width)//2, y + (cell - thumb.height)//2))
            draw.text((x + 2, y + cell), f"{label_prefix}{i}", fill=(230, 230, 230, 255))
        return atlas

    def on_game_tileset_select(self, _event: tk.Event) -> None:
        if not hasattr(self, "game_tilesets_tree"):
            return
        sel = self.game_tilesets_tree.selection()
        if not sel:
            return
        name = sel[0]
        try:
            ts = self.parser.parse_tileset(self.parser.find_file(name))
            self.render_asset_tileset_atlas(ts)
        except Exception as exc:
            messagebox.showerror("Tileset preview failed", str(exc))

    def render_asset_tileset_atlas(self, tileset: TilesetData) -> None:
        if not hasattr(self, "asset_tileset_canvas"):
            return
        scale = 2
        columns = max(1, (self.asset_tileset_canvas.winfo_width() or 800) // (TILE_SIZE * scale))
        rows = max(1, (len(tileset.tiles) + columns - 1) // columns)
        img = Image.new("RGBA", (columns * TILE_SIZE * scale, rows * (TILE_SIZE * scale + 14)), (24, 24, 24, 255))
        draw = ImageDraw.Draw(img)
        for i, tile in enumerate(tileset.tiles):
            x = (i % columns) * TILE_SIZE * scale
            y = (i // columns) * (TILE_SIZE * scale + 14)
            tile_img = tile.resize((TILE_SIZE * scale, TILE_SIZE * scale), Image.Resampling.NEAREST)
            img.alpha_composite(tile_img, (x, y))
            draw.rectangle((x, y, x + TILE_SIZE * scale - 1, y + TILE_SIZE * scale - 1), outline=(70, 70, 70, 255))
            draw.text((x + 2, y + TILE_SIZE * scale), str(i), fill=(230, 230, 230, 255))
        self._asset_photo_refs = [ImageTk.PhotoImage(img)]
        self.asset_tileset_canvas.delete("all")
        self.asset_tileset_canvas.create_image(0, 0, image=self._asset_photo_refs[0], anchor="nw")
        self.asset_tileset_canvas.configure(scrollregion=(0, 0, img.width, img.height))

    def on_game_sprite_select(self, _event: tk.Event) -> None:
        if not hasattr(self, "game_sprites_tree"):
            return
        sel = self.game_sprites_tree.selection()
        if not sel:
            return
        name = sel[0]
        try:
            path = self.parser.find_file(name)
            main = self.parser.find_file("MAINCHAR.000")
            palette = self.tileset.palette if self.tileset else self.parser.parse_tileset(next(iter(sorted(self.parser.game_dir.glob("BLOCKS.*"))))).palette
            if name.upper().startswith("MAINCHAR"):
                # MAINCHAR alone does not have the SPRITES offset table. Show via current level/world if available.
                if self.level:
                    sprites = self.parser.load_sprites_for_level(self.level, palette)
                else:
                    messagebox.showinfo("MAINCHAR", "MAINCHAR.000 needs a SPRITES.xxx offset table. Select a SPRITES file or open a level first.")
                    return
            else:
                sprites = self.parser.parse_sprites(path, main, palette)
            if sprites:
                self.render_asset_sprite_atlas(sprites)
        except Exception as exc:
            messagebox.showerror("Sprite preview failed", str(exc))

    def render_asset_sprite_atlas(self, sprites: SpriteSetData) -> None:
        if not hasattr(self, "asset_sprite_canvas"):
            return
        images = [s.image for s in sprites.sprites if s.image.width > 1 or s.image.height > 1]
        # Keep indices aligned by using the original list; empty frames remain boxes.
        images = [s.image for s in sprites.sprites[:256]]
        img = self._make_image_atlas(images, cell=48, columns=max(1, (self.asset_sprite_canvas.winfo_width() or 900)//48), label_prefix="")
        self._asset_photo_refs = [ImageTk.PhotoImage(img)]
        self.asset_sprite_canvas.delete("all")
        self.asset_sprite_canvas.create_image(0, 0, image=self._asset_photo_refs[0], anchor="nw")
        self.asset_sprite_canvas.configure(scrollregion=(0, 0, img.width, img.height))

    def refresh_game_audio(self) -> None:
        if not hasattr(self, "game_audio_tree"):
            return
        self.game_audio_tree.delete(*self.game_audio_tree.get_children(""))
        exts = {".PSM": "music", ".S3M": "music", ".MOD": "music", ".WAV": "sound", ".VOC": "sound", ".SND": "sound"}
        for p in sorted([p for p in self.parser.game_dir.iterdir() if p.is_file()], key=lambda p: p.name.upper()):
            kind = exts.get(p.suffix.upper())
            if kind or "SOUND" in p.name.upper() or "MUSIC" in p.name.upper():
                self.game_audio_tree.insert("", "end", iid=p.name, values=(kind or "resource", p.name, p.stat().st_size))

    def open_selected_audio_external(self) -> None:
        if not hasattr(self, "game_audio_tree"):
            return
        sel = self.game_audio_tree.selection()
        if not sel:
            return
        path = self.parser.game_dir / sel[0]
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror("Open failed", str(exc))

    def _classify_game_asset(self, path: Path) -> Tuple[str, str, str]:
        name = path.name.upper()
        if name.startswith("LEVEL"):
            return "Level file", "levels", "Contains level placement + level-local definitions"
        if name.startswith("BLOCKS."):
            return "Tileset", "tilesets", "External tiles/palette asset referenced by levels"
        if name.startswith("SPRITES."):
            return "Sprites", "sprites", "External world sprite asset referenced by level-local animations"
        if name == "MAINCHAR.000":
            return "Sprites", "sprites", "Main character/shared sprite asset"
        if name.endswith(".PSM"):
            return "Music", "music", "External music module referenced by levels"
        if name.startswith("SOUNDS") or name.endswith(".SND"):
            return "Sounds", "sounds", "External/global audio resource"
        return "Other", "other", "Game installation file"

    def refresh_game_global_tabs(self) -> None:
        self.refresh_game_assets()
        self.refresh_game_tilesets()
        self.refresh_game_sprites()
        self.refresh_game_audio()

    def refresh_game_assets(self) -> None:
        if not hasattr(self, "game_assets_tree"):
            return
        self.game_assets_tree.delete(*self.game_assets_tree.get_children(""))
        filt = self.asset_filter_var.get() if hasattr(self, "asset_filter_var") else "all"
        try:
            files = sorted([p for p in self.parser.game_dir.iterdir() if p.is_file()], key=lambda p: p.name.upper())
        except Exception:
            files = []
        for p in files:
            kind, group, note = self._classify_game_asset(p)
            if filt != "all" and filt != group:
                continue
            scope = "LEVEL LOCAL" if group == "levels" else "GAME GLOBAL"
            self.game_assets_tree.insert("", "end", values=(scope, kind, p.name, note))

    def refresh_game_tilesets(self) -> None:
        if not hasattr(self, "game_tilesets_tree"):
            return
        self.game_tilesets_tree.delete(*self.game_tilesets_tree.get_children(""))
        usage = {}
        for lp in self.level_paths:
            try:
                level = self.parser.parse_level(lp)
                ext = f"{level.world_num:03d}" if level.blocks_ext == "999" else level.blocks_ext.zfill(3)
                usage[ext] = usage.get(ext, 0) + 1
            except Exception:
                continue
        for p in sorted(self.parser.game_dir.glob("BLOCKS.*"), key=lambda p: p.name.upper()):
            ext = p.suffix[1:].upper()
            tile_count = "?"
            try:
                ts = self.parser.parse_tileset(p)
                tile_count = str(len(ts.tiles))
            except Exception:
                pass
            note = "Referenced externally by levels. Editing it is game-global for all levels using this BLOCKS file."
            self.game_tilesets_tree.insert("", "end", iid=p.name, values=(p.name, usage.get(ext, 0), tile_count))

    def refresh_game_sprites(self) -> None:
        if not hasattr(self, "game_sprites_tree"):
            return
        self.game_sprites_tree.delete(*self.game_sprites_tree.get_children(""))
        rows = []
        for p in sorted(self.parser.game_dir.glob("MAINCHAR.*"), key=lambda p: p.name.upper()):
            rows.append((p.name, "shared/main"))
        for p in sorted(self.parser.game_dir.glob("SPRITES.*"), key=lambda p: p.name.upper()):
            rows.append((p.name, "world/episode"))
        for row in rows:
            self.game_sprites_tree.insert("", "end", iid=row[0], values=row)


    def _build_tiles_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.tiles_tab = tab
        self.tabs.add(tab, text="Tiles")

        form = ttk.Frame(tab)
        form.pack(fill=tk.X)
        ttk.Label(form, text="Selected tile").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(form, from_=0, to=239, textvariable=self.current_tile, width=7).grid(row=0, column=1, sticky="w")
        ttk.Label(form, text="BG flag").grid(row=1, column=0, sticky="w")
        ttk.Spinbox(form, from_=0, to=1, textvariable=self.current_bg, width=7).grid(row=1, column=1, sticky="w")
        ttk.Checkbutton(form, text="also paint BG flag in Tiles mode", variable=self.paint_bg).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Label(form, text="Fast paint updates only the affected 16×16-tile chunk while dragging.").grid(row=3, column=0, columnspan=3, sticky="w", pady=(4, 0))

        atlas_frame = ttk.LabelFrame(tab, text="Tile Atlas", padding=4)
        atlas_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.atlas_canvas = tk.Canvas(atlas_frame, background="#181818", height=420, highlightthickness=0)
        atlas_scroll = ttk.Scrollbar(atlas_frame, orient=tk.VERTICAL, command=self.atlas_canvas.yview)
        self.atlas_canvas.configure(yscrollcommand=atlas_scroll.set)
        self.atlas_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        atlas_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.atlas_canvas.bind("<Button-1>", self.on_atlas_click)
        self.atlas_canvas.bind("<Configure>", lambda _e: self.render_atlas())

    def _build_events_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.raw_events_tab = tab
        self.tabs.add(tab, text="Raw Events")
        ttk.Label(tab, text="This edits the event ID stored in map cells. It does not edit the event definition table yet.").pack(anchor="w")
        event_form = ttk.Frame(tab)
        event_form.pack(fill=tk.X, pady=(6, 4))
        ttk.Label(event_form, text="Selected event ID").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(event_form, from_=0, to=126, textvariable=self.current_event, width=7, command=self._sync_event_selection).grid(row=0, column=1, sticky="w")
        ttk.Button(event_form, text="Clear event brush", command=lambda: self.current_event.set(0)).grid(row=0, column=2, sticky="w", padx=(6, 0))

        self.event_list = tk.Listbox(tab, height=18, exportselection=False)
        self.event_list.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.event_list.bind("<<ListboxSelect>>", self.on_event_select)

    def _build_objects_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.objects_tab = tab
        self.tabs.add(tab, text="Object Prefabs")
        controls = ttk.Frame(tab)
        controls.pack(fill=tk.X, pady=(6, 4))
        ttk.Checkbutton(controls, text="move selected object on next map click", variable=self.move_object_mode).pack(anchor="w")
        filter_row = ttk.Frame(tab)
        filter_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(filter_row, text="Category").pack(side=tk.LEFT)
        self.category_combo = ttk.Combobox(filter_row, state="readonly", width=26, textvariable=self.object_category_filter, values=[
            "all", "pickup/powerup", "enemy/hazard", "trampoline/spring", "mechanism/destructible", "trigger/other", "engine marker/collision", "engine marker/foreground", "engine marker/hazard"
        ])
        self.category_combo.pack(side=tk.LEFT, padx=(6, 0))
        self.category_combo.bind("<<ComboboxSelected>>", lambda _e: (self.refresh_object_palette(), self.refresh_objects()))
        self.object_preview_label = ttk.Label(filter_row, text="preview: -")
        self.object_preview_label.pack(side=tk.LEFT, padx=(10, 0))
        self.object_help_text = tk.Text(tab, height=4, wrap="word")
        self.object_help_text.pack(fill=tk.X, pady=(2, 6))
        self.object_help_text.insert("1.0", "")
        self.object_help_text.configure(state="disabled")
        palette_frame = ttk.LabelFrame(tab, text="Palette", padding=4)
        palette_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        self.palette_tree = ttk.Treeview(palette_frame, columns=("cat", "uses", "name"), show="headings", height=8, selectmode="browse")
        for col, width, text in [("cat", 145, "Category"), ("uses", 45, "Uses"), ("name", 190, "Event / Name")]:
            self.palette_tree.heading(col, text=text)
            self.palette_tree.column(col, width=width, stretch=(col == "name"))
        self.palette_tree.pack(fill=tk.BOTH, expand=True)
        self.palette_tree.bind("<<TreeviewSelect>>", self.on_palette_tree_select)
        buttons = ttk.Frame(tab)
        buttons.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(buttons, text="Refresh list", command=self.refresh_objects).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Delete", command=self.delete_selected_object).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(buttons, text="Use selected as brush", command=self.duplicate_selected_object_to_brush).pack(side=tk.LEFT, padx=(6, 0))

        columns = ("event", "name", "x", "y", "tile", "bg")
        self.object_tree = ttk.Treeview(tab, columns=columns, show="headings", height=16, selectmode="browse")
        headings = {"event": "Event", "name": "Name", "x": "X", "y": "Y", "tile": "Tile", "bg": "BG"}
        widths = {"event": 54, "name": 130, "x": 46, "y": 46, "tile": 54, "bg": 40}
        for col in columns:
            self.object_tree.heading(col, text=headings[col])
            self.object_tree.column(col, width=widths[col], stretch=(col == "name"))
        yscroll = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.object_tree.yview)
        self.object_tree.configure(yscrollcommand=yscroll.set)
        self.object_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.object_tree.bind("<<TreeviewSelect>>", self.on_object_tree_select)


    def _build_object_types_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.object_types_tab = tab
        self.tabs.add(tab, text="Object Types")
        row = ttk.Frame(tab)
        row.pack(fill=tk.X, pady=(6, 4))
        ttk.Button(row, text="Refresh", command=self.refresh_object_types).pack(side=tk.LEFT)
        ttk.Button(row, text="Use as brush", command=self.use_object_type_as_brush).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(row, text="Highlight type", command=self.highlight_selected_object_type).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(row, text="Clear highlight", command=lambda: (self.highlight_event_id.set(0), self.render_map())).pack(side=tk.LEFT, padx=(6, 0))
        actions = ttk.LabelFrame(tab, text="Actions", padding=6)
        actions.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(actions, text="Duplicate selected placement into new type", command=self.duplicate_selected_object_definition).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Replace selected placement with current brush", command=self.replace_selected_object_with_brush).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Replace all highlighted/selected type with current brush", command=self.replace_all_selected_type_with_brush).pack(fill=tk.X, pady=2)
        columns = ("event", "uses", "category", "name")
        self.object_types_tree = ttk.Treeview(tab, columns=columns, show="headings", height=12, selectmode="browse")
        for col, width, text in [("event", 54, "Event"), ("uses", 48, "Uses"), ("category", 135, "Category"), ("name", 260, "Readable object type")]:
            self.object_types_tree.heading(col, text=text)
            self.object_types_tree.column(col, width=width, stretch=(col == "name"))
        self.object_types_tree.pack(fill=tk.BOTH, expand=True)
        self.object_types_tree.bind("<<TreeviewSelect>>", self.on_object_type_select)
        self.object_type_detail = tk.Text(tab, height=8, wrap="word")
        self.object_type_detail.pack(fill=tk.BOTH, expand=False, pady=(6, 0))

    def _build_layers_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.layers_tab = tab
        self.tabs.add(tab, text="Layers")
        grid = ttk.Frame(tab)
        grid.pack(fill=tk.X, pady=(8, 0))
        rows = [
            ("Tiles / visual map", self.show_grid, self.lock_tiles, "Grid visible", "Lock tile paint"),
            ("Event labels", self.show_event_labels, self.lock_events, "Labels visible", "Lock raw event paint"),
            ("Object sprites", self.show_object_sprites, self.lock_objects, "Sprites visible", "Lock object move/delete"),
            ("Collision masks", self.show_collision, None, "Collision visible", ""),
            ("Paths", self.show_paths, None, "Paths visible", ""),
            ("Player start", self.show_player_start, self.lock_start, "Start visible", "Lock start"),
            ("Water level", self.show_water_level, None, "Water visible", ""),
            ("Object names", self.show_object_names, None, "Names visible", ""),
            ("Brush preview", self.show_brush_preview, None, "Preview visible", ""),
            ("Fast paint / chunk cache", self.fast_paint, None, "Fast paint enabled", ""),
        ]
        for r, (label, visible, locked, visible_text, locked_text) in enumerate(rows):
            ttk.Label(grid, text=label).grid(row=r, column=0, sticky="w", pady=2)
            ttk.Checkbutton(grid, text=visible_text, variable=visible, command=self.render_map).grid(row=r, column=1, sticky="w", padx=(8, 0))
            if locked is not None:
                ttk.Checkbutton(grid, text=locked_text, variable=locked).grid(row=r, column=2, sticky="w", padx=(8, 0))


    def _build_metadata_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.metadata_tab = tab
        self.tabs.add(tab, text="Level / Start")
        grid = ttk.Frame(tab)
        grid.pack(anchor="w", pady=(8, 0))
        self.start_x_var = tk.IntVar(value=0)
        self.start_y_var = tk.IntVar(value=0)
        self.next_level_var = tk.IntVar(value=0)
        self.next_world_var = tk.IntVar(value=0)
        self.water_level_var = tk.IntVar(value=0)
        self.jump_height_raw_var = tk.IntVar(value=0)
        self.anim_speed_var = tk.IntVar(value=0)
        fields = [
            ("Start X tile", self.start_x_var, 0, LW - 1),
            ("Start Y tile", self.start_y_var, 0, LH - 1),
            ("Next level", self.next_level_var, 0, 255),
            ("Next world", self.next_world_var, 0, 255),
            ("Water level raw", self.water_level_var, 0, 65535),
            ("Jump height raw", self.jump_height_raw_var, 0, 65535),
            ("Jazz anim speed", self.anim_speed_var, 0, 255),
        ]
        for r, (label, var, lo, hi) in enumerate(fields):
            ttk.Label(grid, text=label).grid(row=r, column=0, sticky="w", pady=2)
            ttk.Spinbox(grid, from_=lo, to=hi, textvariable=var, width=10, command=self.apply_metadata_from_ui).grid(row=r, column=1, sticky="w", padx=(8, 0), pady=2)
        ttk.Button(tab, text="Apply metadata fields", command=self.apply_metadata_from_ui).pack(anchor="w", pady=(8, 0))
        ttk.Button(tab, text="Switch to Start placement mode", command=lambda: (self.tool_mode.set("start"), self.workspace_tabs.select(self.build_workspace), self.build_tabs.select(tab), self.status.set("Start mode: click map to move player spawn."))).pack(anchor="w", pady=(4, 0))

    def _build_globals_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Summary")
        ttk.Label(tab, text="These are LEVEL-LOCAL shared definitions stored inside the currently opened LEVEL file. They are shared by placements in this level, but they are not game-global assets.", wraplength=360).pack(anchor="w")
        ttk.Label(tab, text="A placement in the map only says 'use event ID N'. The behavior, animation references, paths and tile collision masks below are shared tables inside this one level file.", wraplength=360).pack(anchor="w", pady=(4, 8))
        save_box = ttk.LabelFrame(tab, text="Level-local advanced save switches", padding=6)
        save_box.pack(fill=tk.X, pady=(0, 8))
        ttk.Checkbutton(save_box, text="Save level-local event definitions", variable=self.save_event_defs_var).pack(anchor="w")
        ttk.Checkbutton(save_box, text="Save level-local paths", variable=self.save_paths_var).pack(anchor="w")
        ttk.Checkbutton(save_box, text="Save level-local collision masks", variable=self.save_masks_var).pack(anchor="w")
        ttk.Checkbutton(save_box, text="Save level-local animations", variable=self.save_animations_var).pack(anchor="w")
        nav = ttk.LabelFrame(tab, text="Jump to level-local editor", padding=6)
        nav.pack(fill=tk.X)
        ttk.Button(nav, text="Event definitions", command=lambda: self.define_tabs.select(self.global_event_defs_tab)).pack(fill=tk.X, pady=2)
        ttk.Button(nav, text="Paths", command=lambda: self.define_tabs.select(self.global_paths_tab)).pack(fill=tk.X, pady=2)
        ttk.Button(nav, text="Collision masks", command=lambda: self.define_tabs.select(self.global_masks_tab)).pack(fill=tk.X, pady=2)
        ttk.Button(nav, text="Animations", command=lambda: self.define_tabs.select(self.global_animations_tab)).pack(fill=tk.X, pady=2)
        self.global_summary_text = tk.Text(tab, height=14, wrap="word")
        self.global_summary_text.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

    def refresh_global_summary(self) -> None:
        if not hasattr(self, "global_summary_text"):
            return
        counts = self.event_usage_counts() if self.level else {}
        used_events = len([k for k, v in counts.items() if k and v])
        nonempty_paths = len([p for p in self.level.path_defs if p.nonempty]) if self.level else 0
        used_anims = set()
        if self.level:
            for ev in self.level.event_catalog()[1:]:
                for idx in [5, 6, 28, 29, 30, 31]:
                    if idx < len(ev.raw) and ev.raw[idx]:
                        used_anims.add(ev.raw[idx] & 0x7F)
        lines = [
            "What is LEVEL-LOCAL in a JJ1 level:",
            "",
            "• Event definitions: shared behavior table for event IDs 0..126.",
            "• Paths: 16 shared movement paths used by some object behaviors.",
            "• Collision masks: 8x8 collision data per tile; every placement of that tile uses the same mask.",
            "• Animations: 128 shared animation definitions; events reference them by ID.",
            "",
            f"Used event IDs in this map: {used_events}",
            f"Non-empty paths: {nonempty_paths}/16",
            f"Animations referenced by event defs: {len(used_anims)}",
            "",
            "Safe workflow: edit placements in BUILD, then edit LEVEL-LOCAL shared definitions here only when you really want every placement/reference in this level to change.",
        ]
        self.global_summary_text.configure(state="normal")
        self.global_summary_text.delete("1.0", tk.END)
        self.global_summary_text.insert("1.0", "\n".join(lines))
        self.global_summary_text.configure(state="disabled")

    def _build_masks_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Masks")
        self.global_masks_tab = tab
        ttk.Label(tab, text="Collision masks are 8x8 per tile, separate from visual pixels. Overlay is read-only for now.").pack(anchor="w")
        ttk.Checkbutton(tab, text="Show collision overlay on map", variable=self.show_collision, command=self.render_map).pack(anchor="w", pady=(8, 0))
        ttk.Checkbutton(tab, text="Save modified level-local collision masks", variable=self.save_masks_var).pack(anchor="w")
        row = ttk.Frame(tab)
        row.pack(fill=tk.X, pady=(6, 2))
        self.mask_tile_var = tk.IntVar(value=0)
        ttk.Label(row, text="Tile mask").pack(side=tk.LEFT)
        ttk.Spinbox(row, from_=0, to=255, width=6, textvariable=self.mask_tile_var, command=lambda: self.render_mask_info(self.mask_tile_var.get())).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(row, text="Load selected tile", command=lambda: (self.mask_tile_var.set(self.current_tile.get()), self.render_mask_info(self.current_tile.get()))).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(row, text="Apply 8x8 mask", command=self.apply_mask_from_ui).pack(side=tk.LEFT, padx=(6, 0))
        self.mask_text = tk.Text(tab, height=18, wrap="none")
        self.mask_text.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

    def event_def_selector_values(self) -> List[str]:
        if not self.level:
            return []
        counts = self.event_usage_counts()
        values = []
        for event_id in range(EVENTS):
            ev = self.level.event_def(event_id)
            used = counts.get(event_id, 0)
            if event_id == 0:
                label = "Empty / erase"
            elif not any(ev.raw) and not ev.name and used == 0:
                label = "Unused"
            else:
                label = friendly_event_name(ev)
            values.append(f"{event_id:03d}  {label}  ({used}×)")
        return values

    def refresh_event_def_selector(self) -> None:
        if hasattr(self, "event_def_combo"):
            values = self.event_def_selector_values()
            self.event_def_combo["values"] = values
            eid = max(0, min(126, int(getattr(self, "_editing_event_id", 0))))
            if values:
                self.event_def_combo.current(eid)

    def on_event_def_combo_select(self, _event: tk.Event = None) -> None:
        if not hasattr(self, "event_def_combo"):
            return
        idx = self.event_def_combo.current()
        if idx >= 0:
            self.select_event_definition(idx)

    def select_event_definition(self, event_id: int) -> None:
        event_id = max(0, min(126, int(event_id)))
        self._editing_event_id = event_id
        self.current_event.set(event_id)
        if hasattr(self, "event_def_combo"):
            vals = self.event_def_combo["values"]
            if vals:
                self.event_def_combo.current(event_id)
        self.render_event_definition(event_id)

    def create_new_object_type(self) -> None:
        if not self.level:
            return
        used = self.event_usage_counts()
        event_id = self.find_free_event_id()
        raw = bytearray(ELENGTH)
        self.level.event_types[event_id] = bytes(raw)
        self.set_dirty(True)
        self.refresh_event_def_selector()
        self.select_event_definition(event_id)
        self.status.set(f"Created new object type in free Event {event_id:03d}.")

    def duplicate_event_definition_as_new(self) -> None:
        if not self.level:
            return
        src_id = max(0, min(126, int(getattr(self, "_editing_event_id", self.current_event.get()))))
        if src_id == 0:
            self.status.set("Cannot duplicate empty event 0.")
            return
        if is_reserved_engine_event(src_id):
            self.status.set(f"Event {src_id} is a reserved engine marker; duplicate its placement, not its definition.")
            return
        dst_id = self.find_free_event_id()
        self.level.event_types[dst_id] = bytes(self.level.event_types[src_id])
        if dst_id < len(self.level.event_names):
            base_name = self.level.event_names[src_id] if src_id < len(self.level.event_names) else ""
            self.level.event_names[dst_id] = (base_name + " copy").strip()[:32] if base_name else ""
        self.set_dirty(True)
        self.refresh_event_def_selector()
        self.select_event_definition(dst_id)
        self.status.set(f"Duplicated Event {src_id:03d} as new Event {dst_id:03d}.")

    def apply_concept_template_to_raw(self, raw: bytearray, concept: str) -> None:
        # Keep animations/sound/score unless the concept needs a known behavior field.
        if concept == "Unused / empty":
            raw[:] = bytes(ELENGTH)
            return
        if concept == "Enemy / hazard":
            raw[10] = 0
            raw[9] = max(1, raw[9])
            raw[11] = max(1, raw[11])
            if raw[4] == 0:
                raw[4] = 4
        elif concept == "Touch pickup / item":
            raw[9] = 0
            if raw[10] not in PICKUP_MODIFIER_MEANINGS:
                raw[10] = _first_modifier_for_pickup()
            raw[11] = max(1, raw[11])
        elif concept == "Shootable pickup / container":
            raw[9] = max(1, raw[9])
            if raw[10] not in PICKUP_MODIFIER_MEANINGS:
                raw[10] = 15
            raw[11] = max(1, raw[11])
        elif concept == "Destructible block":
            raw[4] = 21
            raw[10] = 7
            raw[9] = max(1, raw[9])
        elif concept == "Spring / bounce":
            raw[10] = 29
            raw[9] = 0
            raw[8] = raw[8] or 250
        elif concept == "Warp trigger":
            raw[10] = 13
            raw[9] = 0
        elif concept == "Conveyor belt":
            raw[10] = 28
            raw[9] = 0
            raw[8] = raw[8] or 2
        elif concept == "Path-moving object":
            raw[4] = 6
            raw[22] = min(15, raw[22])
        # Reserved markers are numeric IDs, not a cloneable raw template.

    def rebuild_event_concept_editor(self, event_id: int, raw: bytes) -> None:
        if not hasattr(self, "event_concept_frame"):
            return
        for child in self.event_concept_frame.winfo_children():
            child.destroy()
        self.event_concept_vars = {}
        name = self.level.event_names[event_id] if self.level and event_id < len(self.level.event_names) else ""
        inferred = infer_event_concept(event_id, raw, name)
        concept = inferred
        if hasattr(self, "event_concept_var"):
            current = self.event_concept_var.get()
            if current in EVENT_CONCEPTS and current not in {"Auto / keep current"}:
                concept = current
            else:
                self.event_concept_var.set(inferred)
        if concept == "Auto / keep current":
            concept = inferred

        def add_spin(row: int, key: str, label: str, value: int, frm: int = 0, to: int = 255, hint: str = "") -> int:
            ttk.Label(self.event_concept_frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 6), pady=2)
            var = tk.IntVar(value=int(value))
            self.event_concept_vars[key] = var
            field = ttk.Frame(self.event_concept_frame)
            field.grid(row=row, column=1, sticky="w", pady=2)
            ttk.Spinbox(field, from_=frm, to=to, width=8, textvariable=var).pack(side=tk.LEFT)
            if key in {"left_anim", "right_anim", "finish_left", "finish_right", "shoot_left", "shoot_right"}:
                ttk.Button(field, text="Atlas…", command=lambda k=key: self.open_animation_picker_for(k)).pack(side=tk.LEFT, padx=(4, 0))
            if key == "bullet":
                ttk.Button(field, text="Pick…", command=lambda k=key: self.open_bullet_picker_for(k)).pack(side=tk.LEFT, padx=(4, 0))
            if hint:
                ttk.Label(self.event_concept_frame, text=hint).grid(row=row, column=2, sticky="w", padx=(8, 0), pady=2)
            return row + 1

        def add_combo(row: int, key: str, label: str, values: List[str], current: str) -> int:
            ttk.Label(self.event_concept_frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 6), pady=2)
            var = tk.StringVar(value=current)
            self.event_concept_vars[key] = var
            cb = ttk.Combobox(self.event_concept_frame, state="readonly", values=values, textvariable=var, width=34)
            cb.grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
            return row + 1

        def add_check(row: int, key: str, label: str, value: bool) -> int:
            var = tk.BooleanVar(value=bool(value))
            self.event_concept_vars[key] = var
            ttk.Checkbutton(self.event_concept_frame, text=label, variable=var).grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
            return row + 1

        row = 0
        if concept == "Unused / empty":
            ttk.Label(self.event_concept_frame, text="This event definition is currently unused/empty.", wraplength=420).grid(row=row, column=0, columnspan=3, sticky="w", pady=4)
            row += 1
            ttk.Label(self.event_concept_frame, text="Choose a concept above to turn it into a normal object type, then click Apply.", wraplength=420).grid(row=row, column=0, columnspan=3, sticky="w", pady=4)
            return
        if is_reserved_engine_event(event_id):
            info = RESERVED_ENGINE_EVENTS[event_id]
            ttk.Label(self.event_concept_frame, text=info["summary"], wraplength=420).grid(row=row, column=0, columnspan=3, sticky="w", pady=4)
            row += 1
            ttk.Label(self.event_concept_frame, text="This is edited by placing this exact event ID in the map. Its core behavior is not made by these fields.", wraplength=420).grid(row=row, column=0, columnspan=3, sticky="w", pady=4)
            return

        common_anims = [(5, "left_anim"), (6, "right_anim"), (28, "finish_left"), (29, "finish_right"), (30, "shoot_left"), (31, "shoot_right")]
        if concept == "Unused / empty":
            raw[:] = bytes(ELENGTH)
            return
        if concept in {"Touch pickup / item", "Shootable pickup / container"}:
            cur = f"{raw[10]}: {PICKUP_MODIFIER_MEANINGS.get(raw[10], (f'modifier_{raw[10]}', ''))[0]}"
            if raw[10] not in PICKUP_MODIFIER_MEANINGS:
                cur = PICKUP_COMBO_LABELS[0]
            row = add_combo(row, "pickup_modifier", "Pickup / reward effect", PICKUP_COMBO_LABELS, cur)
            row = add_check(row, "shootable", "Requires shooting / destroying before pickup", raw[9] > 0)
            row = add_spin(row, "strength", "Hits / strength", max(1, raw[9]) if raw[9] else 1, 0, 255)
            row = add_spin(row, "points", "Score points ×10", raw[11], 0, 255)
            row = add_spin(row, "sound", "Pickup sound", raw[21], 0, 255)
        elif concept == "Enemy / hazard":
            row = add_combo(row, "movement", "Movement behavior", [f"{k}: {v[0]}" for k, v in sorted(MOVEMENT_FIELD_MEANINGS.items())], f"{raw[4]}: {movement_meaning_detail(raw[4])[0]}")
            row = add_spin(row, "strength", "Health / hits to kill", raw[9] or 1, 1, 255)
            row = add_spin(row, "points", "Kill score points ×10", raw[11], 0, 255)
            row = add_spin(row, "bullet", "Bullet type", raw[12], 0, 31)
            row = add_spin(row, "bullet_period", "Bullet period", raw[13], 0, 255)
            row = add_spin(row, "speed", "Movement speed divisor", raw[15] + 1, 1, 256)
        elif concept == "Destructible block":
            row = add_spin(row, "strength", "Hits required", raw[9] or 1, 1, 255)
            row = add_spin(row, "destroy_tile", "Tile after destroyed (multiA)", raw[22], 0, 255)
            row = add_spin(row, "piece_size", "Debris piece size", raw[24], 0, 255)
            row = add_spin(row, "pieces", "Debris pieces", raw[25], 0, 255)
            row = add_spin(row, "sound", "Destroy sound", raw[21], 0, 255)
        elif concept == "Spring / bounce":
            row = add_spin(row, "magnitude_signed", "Bounce magnitude (signed)", _signed_byte(raw[8]), -128, 127)
            row = add_spin(row, "sound", "Spring sound", raw[21], 0, 255)
        elif concept == "Warp trigger":
            row = add_spin(row, "warp_x", "Target X tile", raw[22], 0, 255)
            row = add_spin(row, "warp_y", "Target Y tile", raw[23], 0, 255)
            row = add_spin(row, "sound", "Sound", raw[21], 0, 255)
        elif concept == "Conveyor belt":
            row = add_spin(row, "magnitude_signed", "Push magnitude (signed)", _signed_byte(raw[8]), -128, 127)
            row = add_spin(row, "sound", "Sound", raw[21], 0, 255)
        elif concept == "Path-moving object":
            row = add_spin(row, "path_index", "Path index (multiA)", raw[22], 0, 15)
            row = add_combo(row, "movement", "Path movement mode", ["6: Use level path", "7: Flying snake / path"], f"{raw[4]}: {movement_meaning_detail(raw[4])[0]}")
            row = add_spin(row, "strength", "Health / strength", raw[9], 0, 255)
        else:
            row = add_combo(row, "movement", "Movement behavior", [f"{k}: {v[0]}" for k, v in sorted(MOVEMENT_FIELD_MEANINGS.items())], f"{raw[4]}: {movement_meaning_detail(raw[4])[0]}")
            row = add_combo(row, "modifier", "Modifier / touch behavior", [f"{k}: {v[0]}" for k, v in sorted(MODIFIER_TOUCH_MEANINGS.items())], f"{raw[10]}: {modifier_meaning(raw[10])[0]}")
            row = add_spin(row, "strength", "Strength / health / hits", raw[9], 0, 255)
            row = add_spin(row, "points", "Score points ×10", raw[11], 0, 255)
            row = add_spin(row, "magnitude", "Magnitude", raw[8], 0, 255)
            row = add_spin(row, "multi_a", "multiA", raw[22], 0, 255)
            row = add_spin(row, "multi_b", "multiB", raw[23], 0, 255)

        # Visuals are useful for all normal object types.
        row += 1
        ttk.Label(self.event_concept_frame, text="Visuals").grid(row=row, column=0, sticky="w", pady=(8, 2))
        row += 1
        for idx, key in common_anims:
            row = add_spin(row, key, event_field_label_for(raw, idx), raw[idx], 0, 127)
        row = add_spin(row, "anim_speed", "Animation speed", raw[17] + 1, 1, 256)

    def open_bullet_picker_for(self, key: str) -> None:
        win = tk.Toplevel(self)
        win.title("Choose bullet type")
        win.geometry("520x360")
        columns = ("id", "meaning")
        tree = ttk.Treeview(win, columns=columns, show="headings", selectmode="browse")
        tree.heading("id", text="ID")
        tree.heading("meaning", text="Meaning")
        tree.column("id", width=50, stretch=False)
        tree.column("meaning", width=430, stretch=True)
        tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        for i in range(32):
            tree.insert("", "end", iid=str(i), values=(i, bullet_type_label(i)))
        def choose(_event=None):
            sel = tree.selection()
            if not sel:
                return
            var = self.event_concept_vars.get(key)
            if var is not None:
                var.set(int(sel[0]))
            win.destroy()
        ttk.Button(win, text="Use selected", command=choose).pack(pady=(0, 8))
        tree.bind("<Double-1>", choose)

    def open_animation_picker_for(self, key: str) -> None:
        if not self.level:
            return
        win = tk.Toplevel(self)
        win.title(f"Choose animation for {key}")
        win.geometry("900x640")

        top = ttk.Frame(win, padding=(8, 8, 8, 4))
        top.pack(fill=tk.X)
        ttk.Label(top, text="Click any animation tile to select it. Hover highlights the whole tile.").pack(side=tk.LEFT)

        frame = ttk.Frame(win)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        canvas = tk.Canvas(frame, background="#181818", highlightthickness=0)
        yscroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=canvas.yview)
        xscroll = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=canvas.xview)
        canvas.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        refs: List[ImageTk.PhotoImage] = []
        cell_w = 110
        cell_h = 96
        cols = 8
        used = set()
        for ev in self.level.event_catalog()[1:]:
            for idx in [5, 6, 28, 29, 30, 31]:
                if idx < len(ev.raw) and ev.raw[idx]:
                    used.add(ev.raw[idx] & 0x7F)

        visible_anims = [
            anim for anim in self.level.animations
            if anim.length > 0 or anim.anim_id in used or anim.name
        ]

        hovered = {"tag": None}

        def set_hover(tag: str, on: bool) -> None:
            if on:
                hovered["tag"] = tag
                canvas.itemconfigure(f"{tag}_bg", fill="#303030", outline="#ffff00", width=3)
                canvas.config(cursor="hand2")
            else:
                if hovered.get("tag") == tag:
                    hovered["tag"] = None
                canvas.itemconfigure(f"{tag}_bg", fill="#202020", outline="#555555", width=1)
                canvas.config(cursor="")

        def choose_anim(anim_id: int) -> None:
            var = self.event_concept_vars.get(key)
            if var is not None:
                var.set(anim_id)
            win.destroy()

        for pos, anim in enumerate(visible_anims):
            i = anim.anim_id
            col = pos % cols
            row = pos // cols
            x = col * cell_w
            y = row * cell_h
            tag = f"anim_pick_{i}"

            # Filled background is intentionally visible and receives mouse events across the whole tile.
            canvas.create_rectangle(
                x + 3, y + 3, x + cell_w - 3, y + cell_h - 3,
                fill="#202020", outline="#555555", width=1,
                tags=(tag, f"{tag}_bg"),
            )
            canvas.create_text(x + 8, y + 8, text=f"A{i}", fill="#ffff80", anchor="nw", tags=(tag,))
            title = anim.name[:16] if anim.name else ("used" if i in used else "")
            if title:
                canvas.create_text(x + 40, y + 8, text=title, fill="#dddddd", anchor="nw", tags=(tag,))

            if self.spriteset and anim.frame_ids:
                for n, frame_id in enumerate(anim.frame_ids[:4]):
                    frame_img = self.spriteset.get(frame_id)
                    if frame_img:
                        img = frame_img.image.copy()
                        img.thumbnail((30, 30), Image.Resampling.NEAREST)
                        photo = ImageTk.PhotoImage(img)
                        refs.append(photo)
                        canvas.create_image(x + 20 + n * 22, y + 48, image=photo, anchor="center", tags=(tag,))
                canvas.create_text(x + 8, y + 72, text=",".join(map(str, anim.frame_ids[:6])), fill="#a8a8a8", anchor="nw", tags=(tag,))
            else:
                canvas.create_text(x + 8, y + 45, text="no frames", fill="#777777", anchor="nw", tags=(tag,))

            canvas.tag_bind(tag, "<Enter>", lambda _e, t=tag: set_hover(t, True))
            canvas.tag_bind(tag, "<Leave>", lambda _e, t=tag: set_hover(t, False))
            canvas.tag_bind(tag, "<Button-1>", lambda _e, anim_id=i: choose_anim(anim_id))
            canvas.tag_bind(tag, "<Double-1>", lambda _e, anim_id=i: choose_anim(anim_id))

        rows = max(1, (len(visible_anims) + cols - 1) // cols)
        canvas.configure(scrollregion=(0, 0, cols * cell_w, rows * cell_h))
        win._photo_refs = refs  # keep image references alive

    def apply_event_concept_to_raw(self, raw: bytearray, concept: str) -> None:
        self.apply_concept_template_to_raw(raw, concept)
        vars = getattr(self, "event_concept_vars", {})
        def get_int(key, default=0):
            var = vars.get(key)
            if var is None:
                return default
            try:
                return int(var.get())
            except Exception:
                return default
        def get_bool(key, default=False):
            var = vars.get(key)
            if var is None:
                return default
            return bool(var.get())
        def combo_num(key, default=0):
            var = vars.get(key)
            if var is None:
                return default
            try:
                return int(str(var.get()).split(":", 1)[0])
            except Exception:
                return default

        if concept == "Unused / empty":
            raw[:] = bytes(ELENGTH)
            return
        if concept in {"Touch pickup / item", "Shootable pickup / container"}:
            raw[10] = combo_num("pickup_modifier", raw[10])
            shootable = get_bool("shootable", concept == "Shootable pickup / container")
            raw[9] = max(1, get_int("strength", raw[9] or 1)) if shootable else 0
            raw[11] = get_int("points", raw[11])
            raw[21] = get_int("sound", raw[21])
        elif concept == "Enemy / hazard":
            raw[10] = 0
            raw[4] = combo_num("movement", raw[4])
            raw[9] = max(1, get_int("strength", raw[9] or 1))
            raw[11] = get_int("points", raw[11])
            raw[12] = max(0, min(31, get_int("bullet", raw[12])))
            raw[13] = get_int("bullet_period", raw[13])
            raw[15] = max(0, min(255, get_int("speed", raw[15] + 1) - 1))
        elif concept == "Destructible block":
            raw[4] = 21
            raw[10] = 7
            raw[9] = max(1, get_int("strength", raw[9] or 1))
            raw[22] = get_int("destroy_tile", raw[22])
            raw[24] = get_int("piece_size", raw[24])
            raw[25] = get_int("pieces", raw[25])
            raw[21] = get_int("sound", raw[21])
        elif concept == "Spring / bounce":
            raw[10] = 29
            raw[9] = 0
            raw[8] = get_int("magnitude_signed", _signed_byte(raw[8])) & 0xFF
            raw[21] = get_int("sound", raw[21])
        elif concept == "Warp trigger":
            raw[10] = 13
            raw[9] = 0
            raw[22] = get_int("warp_x", raw[22])
            raw[23] = get_int("warp_y", raw[23])
            raw[21] = get_int("sound", raw[21])
        elif concept == "Conveyor belt":
            raw[10] = 28
            raw[9] = 0
            raw[8] = get_int("magnitude_signed", _signed_byte(raw[8])) & 0xFF
            raw[21] = get_int("sound", raw[21])
        elif concept == "Path-moving object":
            raw[4] = combo_num("movement", raw[4])
            raw[22] = max(0, min(15, get_int("path_index", raw[22])))
            raw[9] = get_int("strength", raw[9])
        elif concept == "Raw / advanced":
            raw[4] = combo_num("movement", raw[4])
            raw[10] = combo_num("modifier", raw[10])
            raw[9] = get_int("strength", raw[9])
            raw[11] = get_int("points", raw[11])
            raw[8] = get_int("magnitude", raw[8])
            raw[22] = get_int("multi_a", raw[22])
            raw[23] = get_int("multi_b", raw[23])

        # Visual fields.
        for key, idx in [("left_anim", 5), ("right_anim", 6), ("finish_left", 28), ("finish_right", 29), ("shoot_left", 30), ("shoot_right", 31)]:
            if key in vars:
                raw[idx] = max(0, min(127, get_int(key, raw[idx])))
        if "anim_speed" in vars:
            raw[17] = max(0, min(255, get_int("anim_speed", raw[17] + 1) - 1))

    def _build_event_defs_tab(self) -> None:
        # This method builds the EVENT DEFS workspace. It has two internal tabs:
        # a concept editor for normal work and a raw/interpretation view for diagnostics.
        concept_tab = ttk.Frame(self.tabs, padding=8)
        raw_tab = ttk.Frame(self.tabs, padding=8)
        self.event_concept_tab = concept_tab
        self.event_raw_tab = raw_tab
        self.global_event_defs_tab = concept_tab
        self.tabs.add(concept_tab, text="Concept editor")
        self.tabs.add(raw_tab, text="Raw / interpretation")

        selector = ttk.Frame(concept_tab)
        selector.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(selector, text="Event").pack(side=tk.LEFT)
        self.event_def_combo = ttk.Combobox(selector, state="readonly", width=46)
        self.event_def_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 6))
        self.event_def_combo.bind("<<ComboboxSelected>>", self.on_event_def_combo_select)
        ttk.Button(selector, text="New type", command=self.create_new_object_type).pack(side=tk.LEFT)
        ttk.Button(selector, text="Duplicate as new", command=self.duplicate_event_definition_as_new).pack(side=tk.LEFT, padx=(6, 0))

        concept_row = ttk.Frame(concept_tab)
        concept_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(concept_row, text="Concept").pack(side=tk.LEFT)
        self.event_concept_var = tk.StringVar(value="Unused / empty")
        self.event_concept_combo = ttk.Combobox(concept_row, state="readonly", values=EVENT_CONCEPTS, textvariable=self.event_concept_var, width=32)
        self.event_concept_combo.pack(side=tk.LEFT, padx=(6, 6))
        self.event_concept_combo.bind("<<ComboboxSelected>>", self.on_event_concept_changed)
        ttk.Button(concept_row, text="Apply", command=self.apply_event_definition_from_ui).pack(side=tk.LEFT)
        ttk.Button(concept_row, text="Refresh", command=lambda: self.render_event_definition(self._editing_event_id)).pack(side=tk.LEFT, padx=(6, 0))

        self.event_concept_frame = ttk.LabelFrame(concept_tab, text="Object concept", padding=6)
        self.event_concept_frame.pack(fill=tk.BOTH, expand=True)
        self.event_concept_vars: Dict[str, Any] = {}

        raw_selector = ttk.Frame(raw_tab)
        raw_selector.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(raw_selector, text="Same selected event as Concept editor").pack(side=tk.LEFT)
        ttk.Button(raw_selector, text="Refresh", command=lambda: self.render_event_definition(self._editing_event_id)).pack(side=tk.LEFT, padx=(8, 0))

        body = ttk.PanedWindow(raw_tab, orient=tk.VERTICAL)
        body.pack(fill=tk.BOTH, expand=True)

        interp_frame = ttk.LabelFrame(body, text="Interpretation")
        body.add(interp_frame, weight=1)
        self.event_semantic_text = tk.Text(interp_frame, height=8, wrap="word")
        self.event_semantic_text.pack(fill=tk.BOTH, expand=True)

        raw_frame = ttk.LabelFrame(body, text="Raw editor")
        body.add(raw_frame, weight=1)
        self.event_raw_fields_frame = ttk.Frame(raw_frame)
        self.event_raw_fields_frame.pack(fill=tk.X, pady=(4, 4))
        self.event_def_edit_vars: Dict[int, tk.IntVar] = {}
        self.event_def_field_labels: Dict[int, ttk.Label] = {}
        for n, idx in enumerate(EDITABLE_EVENT_FIELD_INDICES):
            var = tk.IntVar(value=0)
            self.event_def_edit_vars[idx] = var
            label = ttk.Label(self.event_raw_fields_frame, text=EVENT_FIELD_NAMES[idx])
            self.event_def_field_labels[idx] = label
            label.grid(row=n // 3, column=(n % 3) * 2, sticky="w", padx=(0, 4), pady=1)
            ttk.Spinbox(self.event_raw_fields_frame, from_=0, to=255, width=6, textvariable=var).grid(row=n // 3, column=(n % 3) * 2 + 1, sticky="w", padx=(0, 10), pady=1)
        ttk.Button(raw_frame, text="Apply raw fields", command=self.apply_event_definition_from_ui).pack(anchor="w", pady=(4, 4))
        self.event_def_text = tk.Text(raw_frame, height=8, wrap="none")
        self.event_def_text.pack(fill=tk.BOTH, expand=True)

    def on_event_concept_changed(self, _event: tk.Event = None) -> None:
        if not self.level:
            return
        event_id = max(0, min(126, int(self._editing_event_id)))
        self.rebuild_event_concept_editor(event_id, self.level.event_types[event_id])

    def _build_animations_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Animations")
        self.global_animations_tab = tab
        ttk.Label(tab, text="Animation preview is used to turn raw event IDs into readable objects where possible. Animation definitions are global for this level.").pack(anchor="w")
        ttk.Checkbutton(tab, text="Save modified level-local animations", variable=self.save_animations_var).pack(anchor="w", pady=(4, 0))
        columns = ("anim", "name", "len", "frames")
        self.anim_tree = ttk.Treeview(tab, columns=columns, show="headings", height=10, selectmode="browse")
        for col, width, text in [("anim", 55, "Anim"), ("name", 135, "Name"), ("len", 42, "Len"), ("frames", 180, "Sprite frames")]:
            self.anim_tree.heading(col, text=text)
            self.anim_tree.column(col, width=width, stretch=(col == "frames"))
        self.anim_tree.pack(fill=tk.BOTH, expand=True, pady=(6, 4))
        self.anim_tree.bind("<<TreeviewSelect>>", self.on_anim_tree_select)
        self.anim_preview_frame = ttk.Frame(tab)
        self.anim_preview_frame.pack(fill=tk.X, pady=(4, 0))
        self.anim_preview_labels: List[ttk.Label] = []
        edit_row = ttk.Frame(tab)
        edit_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(edit_row, text="Apply animation frame list", command=self.apply_animation_from_ui).pack(side=tk.LEFT)
        ttk.Label(edit_row, text="One frame per line: sprite_id x_offset y_offset").pack(side=tk.LEFT, padx=(8, 0))
        self.anim_edit_text = tk.Text(tab, height=5, wrap="none")
        self.anim_edit_text.pack(fill=tk.BOTH, expand=False, pady=(4, 0))
        self.anim_detail_text = tk.Text(tab, height=8, wrap="word")
        self.anim_detail_text.pack(fill=tk.BOTH, expand=False, pady=(6, 0))


    def _build_paths_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Paths")
        self.global_paths_tab = tab
        ttk.Label(tab, text="Special event paths: 16 level-local movement paths. Display is read-only/diagnostic for now; use it to understand platforms, flying enemies and scripted objects.").pack(anchor="w")
        row = ttk.Frame(tab)
        row.pack(fill=tk.X, pady=(6, 4))
        ttk.Label(row, text="Selected path").pack(side=tk.LEFT)
        self.path_combo = ttk.Combobox(row, state="readonly", width=24, textvariable=self.selected_path)
        self.path_combo.pack(side=tk.LEFT, padx=(6, 0))
        self.path_combo.bind("<<ComboboxSelected>>", self.on_path_select)
        ttk.Checkbutton(row, text="Show path overlay", variable=self.show_paths, command=self.render_map).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Checkbutton(row, text="Save modified level-local paths", variable=self.save_paths_var).pack(side=tk.LEFT, padx=(10, 0))
        self.path_canvas = tk.Canvas(tab, background="#181818", height=220, highlightthickness=0)
        self.path_canvas.pack(fill=tk.X, expand=False, pady=(4, 6))
        edit = ttk.LabelFrame(tab, text="Editable path deltas", padding=4)
        edit.pack(fill=tk.BOTH, expand=False, pady=(4, 4))
        ttk.Label(edit, text="One point/delta per line: dx dy. X will be stored in 4-pixel units because that is how JJ1/Jazz 1/OpenJazz-reference reads paths.").pack(anchor="w")
        self.path_edit_text = tk.Text(edit, height=7, wrap="none")
        self.path_edit_text.pack(fill=tk.BOTH, expand=True, pady=(3, 3))
        ttk.Button(edit, text="Apply path in memory", command=self.apply_path_from_ui).pack(anchor="w")
        self.path_text = tk.Text(tab, height=8, wrap="none")
        self.path_text.pack(fill=tk.BOTH, expand=True)

    def _build_validation_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Validation")
        ttk.Label(tab, text="Checks common mistakes before testing in OpenJazz: missing sprites, suspicious event definitions, bad start position, missing next level, invalid tiles.").pack(anchor="w")
        ttk.Button(tab, text="Run validation", command=self.refresh_validation).pack(anchor="w", pady=(6, 4))
        columns = ("severity", "where", "message")
        self.validation_tree = ttk.Treeview(tab, columns=columns, show="headings", height=16)
        for col, width, text in [("severity", 75, "Severity"), ("where", 105, "Where"), ("message", 350, "Message")]:
            self.validation_tree.heading(col, text=text)
            self.validation_tree.column(col, width=width, stretch=(col == "message"))
        self.validation_tree.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.validation_text = tk.Text(tab, height=7, wrap="word")
        self.validation_text.pack(fill=tk.BOTH, expand=False, pady=(6, 0))

    def _load_level_list(self) -> None:
        try:
            files = self.parser.level_files()
        except Exception as exc:
            messagebox.showerror("OpenJazz Level Editor", str(exc))
            return
        self.level_paths = files
        self.level_combo["values"] = [p.name for p in files]
        if files:
            self.level_combo.current(0)
            self.load_selected_level()

    def set_dirty(self, dirty: bool = True) -> None:
        self.dirty = bool(dirty)
        if self.level:
            mark = "*" if self.dirty else ""
            save_path = self.current_save_path.name if self.current_save_path else self.level.path.name
            self.title(f"Jazz Jackrabbit 1 DOS Data Level Editor v23{mark} - {save_path}")
        else:
            self.title("Jazz Jackrabbit 1 DOS Data Level Editor v23")

    def maybe_save_changes(self, action: str = "continue") -> bool:
        if not self.dirty or not self.level:
            return True
        answer = messagebox.askyesnocancel(
            "Unsaved changes",
            f"{self.level.path.name} has unsaved changes.\n\nSave before {action}?"
        )
        if answer is None:
            return False
        if answer:
            return self.save()
        return True

    def on_close(self) -> None:
        if self.maybe_save_changes("closing"):
            self.destroy()

    def open_game_dir(self) -> None:
        if not self.maybe_save_changes("opening another game directory"):
            return
        selected = filedialog.askdirectory(title="Select Jazz Jackrabbit DOS game directory")
        if not selected:
            return
        self.parser = JJ1Parser(Path(selected))
        self._load_level_list()

    def request_load_selected_level(self) -> None:
        if self.maybe_save_changes("loading another level"):
            self.load_selected_level()
        else:
            if self.level and self.level.path in self.level_paths:
                self.level_combo.current(self.level_paths.index(self.level.path))

    def load_selected_level(self) -> None:
        idx = self.level_combo.current()
        if idx < 0:
            return
        try:
            self.level = self.parser.parse_level(self.level_paths[idx])
            self.tileset = self.parser.load_tileset_for_level(self.level)
            self.spriteset = self.parser.load_sprites_for_level(self.level, self.tileset.palette)
        except Exception as exc:
            messagebox.showerror("Could not load level", str(exc))
            return
        self.current_tile.set(0)
        self.current_event.set(0)
        self.current_bg.set(0)
        self.selected_object = None
        self.move_object_mode.set(False)
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.current_save_path = self.level.path
        self.set_dirty(False)
        self._event_preview_cache.clear()
        self._object_icon_photos.clear()
        self.status.set(
            f"Loaded {self.level.path.name}: level={self.level.level_num}, world={self.level.world_num}, "
            f"blocks={self.tileset.path.name}, tiles={len(self.tileset.tiles)}, "
            f"sprites={len(self.spriteset.sprites) if self.spriteset else 0}"
        )
        self.populate_events()
        self.refresh_event_def_selector()
        self.refresh_object_palette()
        self.refresh_objects()
        self.refresh_object_types()
        self.sync_metadata_ui()
        self.render_atlas()
        self.render_event_definition(0)
        self.populate_animations()
        self.populate_paths()
        self.render_mask_info(0)
        self.refresh_validation()
        self.refresh_global_summary()
        self.render_map()

    def reload_current(self) -> None:
        if self.maybe_save_changes("reloading"):
            self.load_selected_level()

    def _mode_changed(self) -> None:
        mode = self.tool_mode.get()
        if mode == "tiles":
            self.tabs.select(0)
        elif mode == "events":
            self.tabs.select(1)
        elif mode == "objects":
            self.tabs.select(2)
        elif mode == "start":
            self.tabs.select(3)
        self.status.set(f"Mode: {mode}")
        self.render_map()

    def populate_events(self) -> None:
        self.event_list.delete(0, tk.END)
        if not self.level:
            return
        for i, name in enumerate(self.level.event_names):
            label = name or f"event_{i:03d}"
            self.event_list.insert(tk.END, f"{i:03d}: {label}")


    def event_usage_counts(self) -> Dict[int, int]:
        counts: Dict[int, int] = {}
        if not self.level:
            return counts
        for y in range(LH):
            for x in range(LW):
                ev = self.level.grid[y][x]["event"]
                if ev:
                    counts[ev] = counts.get(ev, 0) + 1
        return counts

    def event_display_name(self, event_id: int) -> str:
        if not self.level:
            return f"event_{event_id:03d}"
        ev = self.level.event_def(event_id)
        return friendly_event_name(ev)

    def event_preview_image(self, event_id: int, max_size: int = 48) -> Optional[Image.Image]:
        if not self.level or not self.spriteset or not event_id:
            return None
        cache_key = (int(event_id), int(max_size))
        if cache_key in self._event_preview_cache:
            cached = self._event_preview_cache[cache_key]
            return cached.copy() if cached is not None else None
        raw = self.level.event_types[event_id]
        candidates = []
        for idx in [5, 6, 28, 29, 30, 31]:
            if idx < len(raw) and raw[idx]:
                anim_id = raw[idx] & 0x7F
                # Do not invent an icon from animation 0. Several event types have no explicit
                # animation and otherwise fall back to a misleading Jazz/rabbit sprite.
                if anim_id != 0:
                    candidates.append(anim_id)
        if not candidates:
            self._event_preview_cache[cache_key] = None
            return None
        for anim_id in candidates:
            anim = self.level.animation(anim_id)
            if not anim or anim.length <= 0:
                continue
            for frame_id in anim.frame_ids:
                frame = self.spriteset.get(frame_id)
                if frame:
                    img = frame.image.copy()
                    img.thumbnail((max_size, max_size), Image.Resampling.NEAREST)
                    self._event_preview_cache[cache_key] = img.copy()
                    return img
        self._event_preview_cache[cache_key] = None
        return None

    def render_event_icon(self, event_id: int, size: int = 40) -> Optional[ImageTk.PhotoImage]:
        img = self.event_preview_image(event_id, size)
        if img is None:
            return None
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        canvas.alpha_composite(img, ((size - img.width) // 2, (size - img.height) // 2))
        photo = ImageTk.PhotoImage(canvas)
        self._object_icon_photos[event_id] = photo
        return photo

    def show_reserved_markers_help(self) -> None:
        lines = ["Reserved engine marker events:", ""]
        for event_id in sorted(RESERVED_ENGINE_EVENTS):
            info = RESERVED_ENGINE_EVENTS[event_id]
            lines.append(f"{event_id}: {info['name']}")
            lines.append(f"    {info['summary']}")
            lines.append("")
        lines.append(f"Normal event definitions are safest in range 1..{NORMAL_EDITABLE_EVENT_MAX}.")
        lines.append("Events 122..126 are reserved engine/render/collision markers and should be edited as marker placements, not duplicated as normal object types.")
        messagebox.showinfo("Reserved engine marker events", "\n".join(lines))

    def refresh_object_palette(self) -> None:
        if not hasattr(self, "palette_tree"):
            return
        self.palette_tree.delete(*self.palette_tree.get_children())
        if not self.level:
            return
        counts = self.event_usage_counts()
        category_filter = self.object_category_filter.get()
        for evdef in self.level.event_catalog()[1:]:
            # Show used events plus named/meaningful definitions. This keeps placeholder empty definitions out of the way.
            if not evdef.name and counts.get(evdef.event_id, 0) == 0 and evdef.raw[5] == 0 and evdef.raw[6] == 0 and evdef.raw[9] == 0 and evdef.raw[10] == 0 and evdef.raw[11] == 0:
                continue
            if category_filter != "all" and evdef.category != category_filter:
                continue
            label = f"{evdef.event_id:03d}: {friendly_event_name(evdef)}"
            self.palette_tree.insert("", tk.END, iid=str(evdef.event_id), values=(evdef.category, counts.get(evdef.event_id, 0), label))

    def on_palette_tree_select(self, _event: tk.Event) -> None:
        selection = self.palette_tree.selection()
        if not selection:
            return
        event_id = int(selection[0])
        self.current_event.set(event_id)
        self.tool_mode.set("events")
        self.render_event_definition(event_id)
        photo = self.render_event_icon(event_id, 32)
        if hasattr(self, "object_preview_label"):
            self.object_preview_label.configure(text=f"preview: event {event_id}", image=photo or "", compound=tk.LEFT)
        if hasattr(self, "object_help_text") and self.level:
            self.object_help_text.configure(state="normal")
            self.object_help_text.delete("1.0", tk.END)
            self.object_help_text.insert("1.0", object_tooltip(self.level.event_def(event_id)))
            self.object_help_text.configure(state="disabled")
        self.status.set(f"Selected object palette event {event_id}: {self.event_display_name(event_id)}. Click the map in Events mode to place it.")

    def use_palette_event(self) -> None:
        selection = self.palette_tree.selection()
        if not selection:
            self.status.set("No palette event selected.")
            return
        event_id = int(selection[0])
        self.current_event.set(event_id)
        self.tool_mode.set("events")
        self.workspace_tabs.select(self.build_workspace)
        self.build_tabs.select(self.objects_tab)
        self._sync_event_selection()
        self.status.set(f"Using event {event_id} as object brush. Left-click map to place; right-click erases.")

    def refresh_objects(self) -> None:
        if not hasattr(self, "object_tree"):
            return
        self.object_tree.delete(*self.object_tree.get_children())
        if not self.level:
            return
        category_filter = self.object_category_filter.get() if hasattr(self, "object_category_filter") else "all"
        for obj in self.level.objects():
            evdef = self.level.event_def(obj.event)
            if category_filter != "all" and evdef.category != category_filter:
                continue
            iid = f"{obj.x},{obj.y}"
            self.object_tree.insert("", tk.END, iid=iid, values=(obj.event, self.event_display_name(obj.event), obj.x, obj.y, obj.tile, obj.bg))


    def refresh_object_types(self) -> None:
        if not hasattr(self, "object_types_tree"):
            return
        self.object_types_tree.delete(*self.object_types_tree.get_children())
        if not self.level:
            return
        counts = self.event_usage_counts()
        for evdef in self.level.event_catalog()[1:]:
            meaningful = bool(evdef.name or counts.get(evdef.event_id, 0) or any(evdef.raw))
            if not meaningful:
                continue
            self.object_types_tree.insert(
                "", tk.END, iid=str(evdef.event_id),
                values=(evdef.event_id, counts.get(evdef.event_id, 0), evdef.category, friendly_event_name(evdef)),
            )

    def _selected_object_type_id(self) -> Optional[int]:
        if hasattr(self, "object_types_tree"):
            sel = self.object_types_tree.selection()
            if sel:
                return int(sel[0])
        if self.selected_object and self.level:
            x, y = self.selected_object
            ev = self.level.grid[y][x]["event"]
            return ev or None
        cur = int(self.current_event.get()) if hasattr(self, "current_event") else 0
        return cur or None

    def on_object_type_select(self, _event: tk.Event) -> None:
        event_id = self._selected_object_type_id()
        if not event_id or not self.level:
            return
        self.current_event.set(event_id)
        self.render_event_definition(event_id)
        self.highlight_event_id.set(event_id)
        if hasattr(self, "object_type_detail"):
            ev = self.level.event_def(event_id)
            count = self.event_usage_counts().get(event_id, 0)
            self.object_type_detail.configure(state="normal")
            self.object_type_detail.delete("1.0", tk.END)
            self.object_type_detail.insert("1.0", object_tooltip(ev) + f"\n\nUsed {count} time(s) in this level. Changing this event definition changes all of those placements in this level only.")
            self.object_type_detail.configure(state="disabled")
        self.render_map()

    def use_object_type_as_brush(self) -> None:
        event_id = self._selected_object_type_id()
        if not event_id:
            self.status.set("No object type selected.")
            return
        self.current_event.set(event_id)
        self.tool_mode.set("events")
        self.status.set(f"Using object type event {event_id} as brush: {self.event_display_name(event_id)}")

    def highlight_selected_object_type(self) -> None:
        event_id = self._selected_object_type_id()
        if not event_id:
            self.status.set("No object type selected to highlight.")
            return
        self.highlight_event_id.set(event_id)
        self.render_map()
        self.status.set(f"Highlighted all placements of event {event_id}: {self.event_display_name(event_id)}")

    def find_free_event_id(self) -> Optional[int]:
        if not self.level:
            return None
        used = set(self.event_usage_counts())
        for i in range(1, NORMAL_EDITABLE_EVENT_MAX + 1):
            raw = self.level.event_types[i]
            if i not in used and not self.level.event_names[i] and not any(raw):
                return i
        for i in range(1, NORMAL_EDITABLE_EVENT_MAX + 1):
            if i not in used:
                return i
        return None

    def duplicate_selected_object_definition(self) -> None:
        if not self.level or not self.selected_object:
            self.status.set("Select a placed object first. Then this can duplicate its level-local event definition.")
            return
        x, y = self.selected_object
        old_id = self.level.grid[y][x]["event"]
        if not old_id:
            self.status.set("Selected cell has no event/object.")
            return
        if is_reserved_engine_event(old_id):
            self.status.set(f"Event {old_id} is a reserved engine marker ({friendly_event_name(self.level.event_def(old_id))}); duplicate its placement, not its definition.")
            return
        new_id = self.find_free_event_id()
        if new_id is None:
            self.status.set("No free event definition slot found in this level.")
            return
        self._push_undo()
        self.level.event_types[new_id] = bytes(self.level.event_types[old_id])
        old_name = self.level.event_names[old_id] if old_id < len(self.level.event_names) else ""
        self.level.event_names[new_id] = ("Copy " + old_name)[:15] if old_name else f"Copy{old_id:03d}"
        self.level.grid[y][x]["event"] = new_id
        self.current_event.set(new_id)
        self.highlight_event_id.set(new_id)
        self.refresh_object_palette()
        self.refresh_objects()
        self.refresh_object_types()
        self.render_event_definition(new_id)
        self.render_map()
        self.status.set(f"Duplicated event type {old_id} into free slot {new_id} and changed only selected placement ({x},{y}). Enable/save event definitions to persist the new type.")

    def replace_selected_object_with_brush(self) -> None:
        if not self.level or not self.selected_object:
            self.status.set("Select a placed object first.")
            return
        new_id = max(0, min(126, int(self.current_event.get())))
        x, y = self.selected_object
        old_id = self.level.grid[y][x]["event"]
        if old_id == new_id:
            self.status.set("Selected object already uses the current brush event.")
            return
        self._push_undo()
        self.level.grid[y][x]["event"] = new_id
        self.highlight_event_id.set(new_id)
        self.refresh_object_palette()
        self.refresh_objects()
        self.refresh_object_types()
        self.render_map()
        self.status.set(f"Replaced selected placement ({x},{y}) event {old_id} -> {new_id}.")

    def replace_all_selected_type_with_brush(self) -> None:
        if not self.level:
            return
        old_id = self.highlight_event_id.get() or self._selected_object_type_id()
        new_id = max(0, min(126, int(self.current_event.get())))
        if not old_id:
            self.status.set("Select or highlight an object type first.")
            return
        if old_id == new_id:
            self.status.set("Old type and current brush are the same.")
            return
        self._push_undo()
        changed = 0
        for y in range(LH):
            for x in range(LW):
                if self.level.grid[y][x]["event"] == old_id:
                    self.level.grid[y][x]["event"] = new_id
                    changed += 1
        self.highlight_event_id.set(new_id)
        self.refresh_object_palette()
        self.refresh_objects()
        self.refresh_object_types()
        self.render_map()
        self.status.set(f"Replaced {changed} placement(s): event {old_id} -> {new_id}. Definitions were not changed.")

    def _atlas_columns(self, scale: int = 2) -> int:
        if not hasattr(self, "atlas_canvas"):
            return 10
        width = max(1, self.atlas_canvas.winfo_width())
        if width <= 1:
            width = 640
        return max(1, width // (TILE_SIZE * scale))

    def render_atlas(self) -> None:
        if not self.tileset:
            return
        scale = 2
        columns = self._atlas_columns(scale)
        rows = max(1, (len(self.tileset.tiles) + columns - 1) // columns)
        img = Image.new("RGBA", (columns * TILE_SIZE * scale, rows * TILE_SIZE * scale), (24, 24, 24, 255))
        for i, tile in enumerate(self.tileset.tiles):
            x = (i % columns) * TILE_SIZE * scale
            y = (i // columns) * TILE_SIZE * scale
            tile_img = tile.resize((TILE_SIZE * scale, TILE_SIZE * scale), Image.Resampling.NEAREST)
            img.alpha_composite(tile_img, (x, y))
        draw = ImageDraw.Draw(img)
        for i in range(len(self.tileset.tiles)):
            x = (i % columns) * TILE_SIZE * scale
            y = (i // columns) * TILE_SIZE * scale
            outline = (80, 80, 80, 255)
            width = 1
            if i == int(self.current_tile.get()):
                outline = (255, 255, 0, 255)
                width = 3
            draw.rectangle((x, y, x + TILE_SIZE * scale - 1, y + TILE_SIZE * scale - 1), outline=outline, width=width)
            draw.text((x + 2, y + 2), str(i), fill=(255, 255, 255, 255))
        self._atlas_photo = ImageTk.PhotoImage(img)
        self.atlas_canvas.delete("all")
        self.atlas_canvas.create_image(0, 0, image=self._atlas_photo, anchor="nw")
        self.atlas_canvas.configure(scrollregion=(0, 0, img.width, img.height))


    def _metadata_tuple(self) -> Tuple[int, int, int, int, int, int, int]:
        if not self.level:
            return (0, 0, 0, 0, 0, 0, 0)
        md = self.level.metadata
        return (md.start_x, md.start_y, md.next_level, md.next_world, md.jump_height_raw, md.water_level, md.anim_speed)

    def _restore_metadata_tuple(self, values: Tuple[int, int, int, int, int, int, int]) -> None:
        if not self.level:
            return
        md = self.level.metadata
        md.start_x, md.start_y, md.next_level, md.next_world, md.jump_height_raw, md.water_level, md.anim_speed = values
        self.sync_metadata_ui()

    def _snapshot_state(self) -> Tuple[bytes, Tuple[int, int, int, int, int, int, int]]:
        assert self.level is not None
        return (self.level.grid_to_bytes(), self._metadata_tuple())

    def _restore_state(self, snapshot: Tuple[bytes, Tuple[int, int, int, int, int, int, int]]) -> None:
        if not self.level:
            return
        raw_grid, md_tuple = snapshot
        for x in range(LW):
            for y in range(LH):
                idx = (y + x * LH) * 2
                self.level.grid[y][x] = {"tile": raw_grid[idx], "bg": raw_grid[idx + 1] >> 7, "event": raw_grid[idx + 1] & 0x7F}
        self._restore_metadata_tuple(md_tuple)
        self.selected_object = None
        self.render_map()
        self.refresh_object_palette()
        self.refresh_objects()
        self.refresh_object_types()
        self.refresh_validation()

    def _push_undo(self) -> None:
        if not self.level:
            return
        snap = self._snapshot_state()
        if self.undo_stack and self.undo_stack[-1] == snap:
            return
        self.undo_stack.append(snap)
        if len(self.undo_stack) > self.max_undo:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self.set_dirty(True)

    def undo(self) -> None:
        if not self.level or not self.undo_stack:
            self.status.set("Nothing to undo.")
            return
        self.redo_stack.append(self._snapshot_state())
        snap = self.undo_stack.pop()
        self._restore_state(snap)
        self.set_dirty(True)
        self.status.set("Undo applied.")

    def redo(self) -> None:
        if not self.level or not self.redo_stack:
            self.status.set("Nothing to redo.")
            return
        self.undo_stack.append(self._snapshot_state())
        snap = self.redo_stack.pop()
        self._restore_state(snap)
        self.set_dirty(True)
        self.status.set("Redo applied.")

    def validate_level(self) -> List[Tuple[str, str, str]]:
        issues: List[Tuple[str, str, str]] = []
        if not self.level:
            return issues
        level = self.level
        if self.tileset:
            for y in range(LH):
                for x in range(LW):
                    tile = level.grid[y][x]["tile"]
                    if tile >= len(self.tileset.tiles):
                        issues.append(("error", f"cell {x},{y}", f"Tile {tile} is outside loaded tileset range 0..{len(self.tileset.tiles)-1}."))
                        if len(issues) > 200:
                            break
                if len(issues) > 200:
                    break
        counts = self.event_usage_counts()
        for event_id, count in sorted(counts.items()):
            ev = level.event_def(event_id)
            raw = ev.raw
            if not ev.name and not any(raw):
                issues.append(("error", f"event {event_id:03d}", f"Used {count} time(s) but the event definition is empty."))
            for label, idx in [("left",5),("right",6),("finishL",28),("finishR",29),("shootL",30),("shootR",31)]:
                anim_id = raw[idx] & 0x7F
                if raw[idx] and (anim_id >= len(level.animations) or level.animations[anim_id].length == 0):
                    issues.append(("warning", f"event {event_id:03d}", f"{label} animation {anim_id} has no frames; object may be invisible."))
            if self.spriteset:
                preview = self.event_preview_image(event_id, 30)
                if preview is None and ev.category in {"pickup/powerup", "enemy/hazard", "trampoline/spring"}:
                    issues.append(("info", f"event {event_id:03d}", f"No sprite preview resolved for {friendly_event_name(ev)}; editor will show label only."))
        md = level.metadata
        if md.start_x_pos >= 0:
            if not (0 <= md.start_x < LW and 0 <= md.start_y < LH):
                issues.append(("error", "player start", f"Start position ({md.start_x},{md.start_y}) is outside the 256x64 map."))
            else:
                tile = level.grid[md.start_y][md.start_x]["tile"]
                if level.tile_has_collision(tile):
                    issues.append(("warning", "player start", f"Start position is on tile {tile}, which has collision mask bits."))
        try:
            next_file = self.parser.find_file(f"LEVEL{md.next_level}.{md.next_world:03d}")
            if not next_file.exists():
                issues.append(("warning", "next level", f"Next level LEVEL{md.next_level}.{md.next_world:03d} was not found."))
        except Exception:
            if md.next_world or md.next_level:
                issues.append(("warning", "next level", f"Next level LEVEL{md.next_level}.{md.next_world:03d} was not found."))
        for anim in level.animations:
            if anim.length:
                for frame_id in anim.frame_ids:
                    if self.spriteset and self.spriteset.get(frame_id) is None:
                        issues.append(("warning", f"anim {anim.anim_id:03d}", f"References missing sprite frame {frame_id}."))
                        break
        return issues

    def refresh_validation(self) -> None:
        if not hasattr(self, "validation_tree"):
            return
        self.validation_tree.delete(*self.validation_tree.get_children())
        issues = self.validate_level()
        for i, issue in enumerate(issues):
            self.validation_tree.insert("", tk.END, iid=str(i), values=issue)
        errors = sum(1 for sev, _, _ in issues if sev == "error")
        warnings = sum(1 for sev, _, _ in issues if sev == "warning")
        infos = sum(1 for sev, _, _ in issues if sev == "info")
        text = f"Validation complete: {errors} error(s), {warnings} warning(s), {infos} info note(s).\n"
        if not issues:
            text += "No obvious issues found by the current checks. This does not guarantee the level is valid in every engine edge case."
        else:
            text += "Errors are likely to break the level. Warnings deserve checking. Info notes are mostly editor limitations or unknown object semantics."
        self.validation_text.configure(state="normal")
        self.validation_text.delete("1.0", tk.END)
        self.validation_text.insert("1.0", text)
        self.validation_text.configure(state="disabled")


    def render_map(self) -> None:
        """Render base tile chunks and draw overlays as independent canvas items.

        v14 keeps pixel art in chunk images, but collision, labels, grid, paths,
        event numbers, water line and start marker are vector canvas overlays.
        That keeps overlays crisp and independent from pixel-art scaling.
        """
        if not self.level or not self.tileset:
            return
        self._clear_brush_preview()
        self._chunk_photos.clear()
        self._chunk_items.clear()
        self.canvas.delete("all")
        z = max(1, int(self.zoom.get()))
        bg = self._background_color_rgba()
        self.canvas.configure(background=f"#{bg[0]:02x}{bg[1]:02x}{bg[2]:02x}")
        chunks_x = (LW + CHUNK_TILES - 1) // CHUNK_TILES
        chunks_y = (LH + CHUNK_TILES - 1) // CHUNK_TILES
        for cy in range(chunks_y):
            for cx in range(chunks_x):
                self._render_chunk(cx, cy)
        self.canvas.configure(scrollregion=(0, 0, LW * TILE_SIZE * z, LH * TILE_SIZE * z))
        self._draw_canvas_overlays()
        self._dirty_chunks.clear()

    def _render_chunk(self, cx: int, cy: int) -> None:
        if not self.level or not self.tileset:
            return
        z = max(1, int(self.zoom.get()))
        x0 = cx * CHUNK_TILES
        y0 = cy * CHUNK_TILES
        x1 = min(LW, x0 + CHUNK_TILES)
        y1 = min(LH, y0 + CHUNK_TILES)
        w = (x1 - x0) * TILE_SIZE
        h = (y1 - y0) * TILE_SIZE

        bg = self._background_color_rgba()
        img = Image.new("RGBA", (w, h), bg)

        for y in range(y0, y1):
            for x in range(x0, x1):
                cell = self.level.grid[y][x]
                tile_id = cell["tile"]
                tile_img = self.tileset.tiles[tile_id] if 0 <= tile_id < len(self.tileset.tiles) else None
                px = (x - x0) * TILE_SIZE
                py = (y - y0) * TILE_SIZE
                if tile_img is not None:
                    img.alpha_composite(tile_img, (px, py))
                else:
                    draw = ImageDraw.Draw(img, "RGBA")
                    draw.rectangle((px, py, px + TILE_SIZE - 1, py + TILE_SIZE - 1), fill=(80, 0, 80, 255))
                    draw.text((px + 4, py + 10), str(tile_id), fill=(255, 255, 255, 255))

                # Object sprites are still raster images, but no text/lines are burned into the tile layer.
                event = cell["event"]
                if event and self.show_events.get() and self.show_object_sprites.get():
                    sprite_img = self.event_preview_image(event, 30)
                    if sprite_img is not None:
                        img.alpha_composite(sprite_img, (px + (TILE_SIZE - sprite_img.width) // 2, py + (TILE_SIZE - sprite_img.height) // 2))

        if z != 1:
            img = img.resize((img.width * z, img.height * z), Image.Resampling.NEAREST)
        photo = ImageTk.PhotoImage(img)
        self._chunk_photos[(cx, cy)] = photo
        canvas_x = x0 * TILE_SIZE * z
        canvas_y = y0 * TILE_SIZE * z
        old_item = self._chunk_items.get((cx, cy))
        if old_item:
            self.canvas.itemconfigure(old_item, image=photo)
        else:
            item = self.canvas.create_image(canvas_x, canvas_y, image=photo, anchor="nw", tags=("map_chunk",))
            self._chunk_items[(cx, cy)] = item

    def _background_color_rgba(self) -> Tuple[int, int, int, int]:
        """Approximate game background as a stretched canvas base color.

        Full JJ1 background/parallax rendering is still future work. This picks a
        reasonable sky/background color from the loaded palette so empty/transparent
        areas do not appear as editor-black.
        """
        if self.tileset and self.tileset.palette:
            # Palette index 0 is often the transparent/black color. Try a few sky-like
            # low indices and fall back to dark blue.
            for idx in (32, 48, 64, 80, 96, 112):
                if idx < len(self.tileset.palette):
                    r, g, b = self.tileset.palette[idx]
                    if max(r, g, b) > 20:
                        return (r, g, b, 255)
        return (18, 28, 58, 255)

    def _draw_canvas_overlays(self) -> None:
        if not self.level:
            return
        z = max(1, int(self.zoom.get()))
        self.canvas.delete("overlay")
        self.canvas.delete("path_overlay")
        tile_px = TILE_SIZE * z
        map_w = LW * tile_px
        map_h = LH * tile_px

        # Background tint/sky layer is already in chunks; water is a vector overlay.
        if self.show_bg_overlay.get():
            for y in range(LH):
                for x in range(LW):
                    if self.level.grid[y][x]["bg"]:
                        px = x * tile_px
                        py = y * tile_px
                        self.canvas.create_rectangle(px, py, px + tile_px, py + tile_px, fill="#50a0ff", stipple="gray50", outline="", tags=("overlay", "bg_overlay"))

        if self.show_collision.get():
            self._draw_collision_overlay_canvas(tile_px)

        if self.show_grid.get():
            for x in range(0, LW + 1):
                px = x * tile_px
                self.canvas.create_line(px, 0, px, map_h, fill="#ffffff", stipple="gray75", tags=("overlay", "grid_overlay"))
            for y in range(0, LH + 1):
                py = y * tile_px
                self.canvas.create_line(0, py, map_w, py, fill="#ffffff", stipple="gray75", tags=("overlay", "grid_overlay"))

        if self.show_water_level.get() and self.level.metadata.water_level not in (0, 65535):
            wy = max(0, min(map_h - 1, int(self.level.metadata.water_level) * z))
            self.canvas.create_rectangle(0, wy, map_w, map_h, fill="#2882ff", stipple="gray75", outline="", tags=("overlay", "water_overlay"))
            self.canvas.create_line(0, wy, map_w, wy, fill="#40c8ff", width=2, tags=("overlay", "water_overlay"))
            self.canvas.create_text(8, max(12, wy - 10), text=f"water {self.level.metadata.water_level}", anchor="w", fill="#80dcff", tags=("overlay", "water_overlay"))

        if self.show_events.get():
            color_by_cat = {
                "pickup/powerup": "#50ff78",
                "enemy/hazard": "#ff4646",
                "trampoline/spring": "#50beff",
                "mechanism/destructible": "#ffaa32",
                "trigger/other": "#d278ff",
            }
            for y in range(LH):
                for x in range(LW):
                    event = self.level.grid[y][x]["event"]
                    if not event:
                        continue
                    px = x * tile_px
                    py = y * tile_px
                    selected = self.selected_object == (x, y)
                    highlighted = self.highlight_event_id.get() == event
                    category = self.level.event_def(event).category
                    outline = "#ffff00" if selected else ("#ff00ff" if highlighted else color_by_cat.get(category, "#ff5050"))
                    self.canvas.create_rectangle(px + 1, py + 1, px + tile_px - 2, py + tile_px - 2, outline=outline, width=3 if selected else 2, tags=("overlay", "event_overlay"))
                    if self.show_event_labels.get():
                        self.canvas.create_rectangle(px + 2, py + 2, px + 23, py + 16, fill="#000000", outline="", stipple="gray50", tags=("overlay", "event_overlay"))
                        self.canvas.create_text(px + 4, py + 3, text=str(event), fill="#ffff00", anchor="nw", tags=("overlay", "event_overlay"))
                    if self.show_object_names.get():
                        label = friendly_event_name(self.level.event_def(event))[:26]
                        self.canvas.create_text(px + 3, py + tile_px - 13, text=label, fill="#ffffff", anchor="nw", tags=("overlay", "event_overlay"))

        if self.show_paths.get():
            self._draw_path_overlay_canvas()

        if self.show_player_start.get() and self.level.metadata.start_x_pos >= 0:
            sx = self.level.metadata.start_x * tile_px
            sy = self.level.metadata.start_y * tile_px
            self.canvas.create_rectangle(sx + 3, sy + 3, sx + tile_px - 4, sy + tile_px - 4, outline="#50ffff", width=3, tags=("overlay", "start_overlay"))
            self.canvas.create_text(sx + 4, sy + max(12, tile_px - 14), text="START", fill="#50ffff", anchor="nw", tags=("overlay", "start_overlay"))

        self.canvas.tag_raise("overlay")
        self.canvas.tag_raise("path_overlay")
        self.canvas.tag_raise("brush_preview")

    def _draw_collision_overlay_canvas(self, tile_px: int) -> None:
        if not self.level:
            return
        cell_bit = tile_px / 8.0
        for y in range(LH):
            for x in range(LW):
                tile = self.level.grid[y][x]["tile"]
                start = tile * 8
                if start < 0 or start + 8 > len(self.level.masks) or not any(self.level.masks[start:start + 8]):
                    continue
                base_x = x * tile_px
                base_y = y * tile_px
                # Soft hatched outline so the tile artwork remains visible.
                self.canvas.create_rectangle(base_x + 2, base_y + 2, base_x + tile_px - 2, base_y + tile_px - 2, outline="#ffffff", stipple="gray75", tags=("overlay", "collision_overlay"))
                for my in range(8):
                    row = self.level.masks[start + my]
                    for mx in range(8):
                        # Bit 0 is drawn on the left. Previous versions used 7-mx and looked horizontally mirrored.
                        if row & (1 << mx):
                            x0 = base_x + mx * cell_bit
                            y0 = base_y + my * cell_bit
                            x1 = base_x + (mx + 1) * cell_bit
                            y1 = base_y + (my + 1) * cell_bit
                            self.canvas.create_line(x0, y1, x1, y0, fill="#ffffff", tags=("overlay", "collision_overlay"))
                            if cell_bit >= 8:
                                self.canvas.create_line(x0, y0, x1, y1, fill="#ffffff", stipple="gray75", tags=("overlay", "collision_overlay"))

    def _cell_chunk(self, x: int, y: int) -> Tuple[int, int]:
        return x // CHUNK_TILES, y // CHUNK_TILES

    def _refresh_cell_chunk(self, x: int, y: int) -> None:
        if not self.fast_paint.get():
            self.render_map()
            return
        cx, cy = self._cell_chunk(x, y)
        self._render_chunk(cx, cy)
        self.canvas.tag_lower("map_chunk")
        self._draw_canvas_overlays()

    def _draw_path_overlay_canvas(self) -> None:
        if not self.level:
            return
        self.canvas.delete("path_overlay")
        z = max(1, int(self.zoom.get()))
        origin_x = self.level.metadata.start_x * TILE_SIZE
        origin_y = self.level.metadata.start_y * TILE_SIZE
        if self.selected_object:
            origin_x = self.selected_object[0] * TILE_SIZE + TILE_SIZE // 2
            origin_y = self.selected_object[1] * TILE_SIZE + TILE_SIZE // 2
        for path in self.level.path_defs:
            if not path.nonempty:
                continue
            x = origin_x
            y = origin_y
            pts = [(x * z, y * z)]
            for dx, dy in path.points[:path.length]:
                x += dx
                y += dy
                pts.append((x * z, y * z))
            if len(pts) >= 2:
                flat = [coord for pt in pts for coord in pt]
                self.canvas.create_line(*flat, fill="#ffff00", width=2, tags=("path_overlay", "overlay"))
                self.canvas.create_text(pts[0][0] + 5, pts[0][1] + 5, text=f"P{path.path_id}", fill="#ffff00", anchor="nw", tags=("path_overlay", "overlay"))

    def _clear_brush_preview(self) -> None:
        if not hasattr(self, "canvas"):
            return
        for item in getattr(self, "_brush_preview_items", []):
            try:
                self.canvas.delete(item)
            except Exception:
                pass
        self._brush_preview_items = []
        self._brush_preview_photos = []

    def _tile_brush_preview_photo(self, tile_id: int, size: int) -> Optional[ImageTk.PhotoImage]:
        if not self.tileset or not (0 <= tile_id < len(self.tileset.tiles)):
            return None
        img = self.tileset.tiles[tile_id].resize((size, size), Image.Resampling.NEAREST)
        if self.paint_bg.get() and int(self.current_bg.get()):
            overlay = Image.new("RGBA", (size, size), (80, 160, 255, 65))
            img = Image.alpha_composite(img.convert("RGBA"), overlay)
        return ImageTk.PhotoImage(img)

    def _event_brush_preview_photo(self, event_id: int, size: int) -> Optional[ImageTk.PhotoImage]:
        if event_id <= 0:
            return None
        sprite = self.event_preview_image(event_id, max(16, min(48, size - 4)))
        if sprite is None:
            return None
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        sprite = sprite.copy()
        sprite.thumbnail((size - 4, size - 4), Image.Resampling.NEAREST)
        canvas.alpha_composite(sprite, ((size - sprite.width) // 2, (size - sprite.height) // 2))
        return ImageTk.PhotoImage(canvas)

    def _update_brush_preview(self, x: int, y: int) -> None:
        self._clear_brush_preview()
        if not self.show_brush_preview.get():
            return
        z = max(1, int(self.zoom.get()))
        px = x * TILE_SIZE * z
        py = y * TILE_SIZE * z
        size = TILE_SIZE * z
        mode = self.tool_mode.get()
        label = ""
        outline = "#ffffff"
        photo: Optional[ImageTk.PhotoImage] = None

        if mode == "tiles":
            tile_id = int(self.current_tile.get())
            label = f"tile {tile_id}"
            outline = "#00ffff"
            photo = self._tile_brush_preview_photo(tile_id, size)
        elif mode in {"events", "objects"}:
            ev = int(self.current_event.get())
            label = "erase event" if ev == 0 else f"event {ev}: {self.event_display_name(ev)[:22]}"
            outline = "#ffff00"
            photo = self._event_brush_preview_photo(ev, size)
        elif mode == "start":
            label = "START"
            outline = "#00ffff"
        else:
            label = "inspect"
            outline = "#aaaaaa"

        items = []
        if photo is not None:
            self._brush_preview_photos.append(photo)
            items.append(self.canvas.create_image(px, py, image=photo, anchor="nw", tags=("brush_preview", "overlay")))
            # translucent-ish checker/outline effect is approximated by the dashed outline; Tk images don't support per-item alpha.
        r = self.canvas.create_rectangle(px, py, px + size, py + size, outline=outline, width=2, dash=(4, 3), tags=("brush_preview", "overlay"))
        t = self.canvas.create_text(px + 4, py + 4, text=label, fill=outline, anchor="nw", tags=("brush_preview", "overlay"))
        items.extend([r, t])
        self._brush_preview_items = items
        self.canvas.tag_raise("brush_preview")

    def canvas_to_cell(self, event: tk.Event) -> Optional[Tuple[int, int]]:
        z = max(1, int(self.zoom.get()))
        x = int(self.canvas.canvasx(event.x) // (TILE_SIZE * z))
        y = int(self.canvas.canvasy(event.y) // (TILE_SIZE * z))
        if 0 <= x < LW and 0 <= y < LH:
            return x, y
        return None

    def on_canvas_motion(self, event: tk.Event) -> None:
        cell_pos = self.canvas_to_cell(event)
        if not cell_pos or not self.level:
            return
        x, y = cell_pos
        cell = self.level.grid[y][x]
        name = self.level.event_names[cell["event"]] if cell["event"] < len(self.level.event_names) else ""
        category = self.level.event_def(cell["event"]).category if cell["event"] else "none"
        self.cell_label.configure(text=f"Cell: x={x}, y={y}, tile={cell['tile']}, event={cell['event']} {name}, bg={cell['bg']}")
        if cell["event"]:
            self.object_label.configure(text=f"Object under cursor: event={cell['event']} {self.event_display_name(cell['event'])} [{category}] at ({x},{y})")
        else:
            self.object_label.configure(text="Object under cursor: none")
        self._update_brush_preview(x, y)

    def on_canvas_click(self, event: tk.Event) -> None:
        self._last_painted_cell = None
        self.handle_map_action(event)

    def on_canvas_drag(self, event: tk.Event) -> None:
        if self.tool_mode.get() in {"tiles", "events"}:
            self.handle_map_action(event)

    def on_canvas_release(self, _event: tk.Event) -> None:
        self._last_painted_cell = None
        if self._paint_stroke_active:
            count = len(self._stroke_cells)
            self._paint_stroke_active = False
            self._stroke_cells.clear()
            self._dirty_chunks.clear()
            if count:
                self.refresh_validation()
                if self.tool_mode.get() == "events":
                    self.refresh_object_palette()
                    self.refresh_objects()
                    self.refresh_object_types()
                self.status.set(f"Paint stroke finished: {count} cell(s) changed.")

    def _begin_paint_stroke_if_needed(self) -> None:
        if not self._paint_stroke_active:
            self._push_undo()
            self._paint_stroke_active = True
            self._stroke_cells.clear()
            self._dirty_chunks.clear()

    def handle_map_action(self, event: tk.Event) -> None:
        cell_pos = self.canvas_to_cell(event)
        if not cell_pos or not self.level:
            return
        if self._last_painted_cell == cell_pos and self.tool_mode.get() in {"tiles", "events"}:
            return
        self._last_painted_cell = cell_pos
        x, y = cell_pos
        mode = self.tool_mode.get()
        if mode == "tiles":
            self.paint_tile(x, y)
        elif mode == "events":
            self.paint_event(x, y)
        elif mode == "objects":
            self.object_click(x, y)
        elif mode == "start":
            self.place_player_start(x, y)
        else:
            self.inspect_cell(x, y)

    def paint_tile(self, x: int, y: int) -> None:
        assert self.level is not None
        if self.lock_tiles.get():
            self.status.set("Tiles layer is locked. Unlock it in Layers tab to paint tiles.")
            return
        self._begin_paint_stroke_if_needed()
        cell = self.level.grid[y][x]
        old = (cell["tile"], cell["bg"])
        cell["tile"] = max(0, min(255, int(self.current_tile.get())))
        if self.paint_bg.get():
            cell["bg"] = max(0, min(1, int(self.current_bg.get())))
        if old != (cell["tile"], cell["bg"]):
            self._stroke_cells.add((x, y))
            self._dirty_chunks.add(self._cell_chunk(x, y))
            self._refresh_cell_chunk(x, y)
        self.status.set(f"Painting tile {cell['tile']} at ({x},{y}) into chunk {self._cell_chunk(x,y)}. Stroke cells: {len(self._stroke_cells)}.")

    def paint_event(self, x: int, y: int) -> None:
        assert self.level is not None
        if self.lock_events.get():
            self.status.set("Events layer is locked. Unlock it in Layers tab to paint event IDs.")
            return
        self._begin_paint_stroke_if_needed()
        cell = self.level.grid[y][x]
        new_event = max(0, min(126, int(self.current_event.get())))
        old_event = cell["event"]
        cell["event"] = new_event
        self.selected_object = (x, y) if cell["event"] else None
        if old_event != new_event:
            self._stroke_cells.add((x, y))
            self._dirty_chunks.add(self._cell_chunk(x, y))
            self._refresh_cell_chunk(x, y)
        self.status.set(f"Painting event {cell['event']} at ({x},{y}) into chunk {self._cell_chunk(x,y)}. Tile unchanged: {cell['tile']}. Stroke cells: {len(self._stroke_cells)}.")

    def object_click(self, x: int, y: int) -> None:
        assert self.level is not None
        if self.lock_objects.get():
            self.status.set("Objects layer is locked. Unlock it in Layers tab to move/select-edit objects.")
            return
        if self.move_object_mode.get() and self.selected_object:
            sx, sy = self.selected_object
            if (sx, sy) != (x, y):
                source = self.level.grid[sy][sx]
                target = self.level.grid[y][x]
                if target["event"]:
                    self.status.set("Target cell already has an object/event. Delete it first or choose an empty cell.")
                    return
                self._push_undo()
                target["event"] = source["event"]
                source["event"] = 0
                self.selected_object = (x, y)
                self.move_object_mode.set(False)
                self.render_map()
                self.refresh_objects()
                self.select_object_in_tree(x, y)
                self.refresh_validation()
                self.status.set(f"Moved object event={target['event']} from ({sx},{sy}) to ({x},{y}).")
            return
        self.select_object_at(x, y)


    def place_player_start(self, x: int, y: int) -> None:
        if not self.level:
            return
        if self.lock_start.get():
            self.status.set("Player start layer is locked. Unlock it in Layers tab to move the spawn.")
            return
        self._push_undo()
        self.level.metadata.start_x = x
        self.level.metadata.start_y = y
        self.sync_metadata_ui()
        self.render_map()
        self.refresh_validation()
        self.status.set(f"Moved player start to ({x},{y}). This changes level metadata, not events.")

    def sync_metadata_ui(self) -> None:
        if not self.level or not hasattr(self, "start_x_var"):
            return
        md = self.level.metadata
        self.start_x_var.set(md.start_x)
        self.start_y_var.set(md.start_y)
        self.next_level_var.set(md.next_level)
        self.next_world_var.set(md.next_world)
        self.water_level_var.set(md.water_level)
        self.jump_height_raw_var.set(md.jump_height_raw)
        self.anim_speed_var.set(md.anim_speed)

    def apply_metadata_from_ui(self) -> None:
        if not self.level or not hasattr(self, "start_x_var"):
            return
        self._push_undo()
        md = self.level.metadata
        md.start_x = max(0, min(LW - 1, int(self.start_x_var.get())))
        md.start_y = max(0, min(LH - 1, int(self.start_y_var.get())))
        md.next_level = max(0, min(255, int(self.next_level_var.get())))
        md.next_world = max(0, min(255, int(self.next_world_var.get())))
        md.water_level = max(0, min(65535, int(self.water_level_var.get())))
        md.jump_height_raw = max(0, min(65535, int(self.jump_height_raw_var.get())))
        md.anim_speed = max(0, min(255, int(self.anim_speed_var.get())))
        self.render_map()
        self.refresh_validation()
        self.status.set("Applied level metadata fields. Use Save to write them.")

    def render_mask_info(self, tile: int) -> None:
        if not self.level or not hasattr(self, "mask_text"):
            return
        tile = max(0, min(255, int(tile)))
        start = tile * 8
        self.mask_tile_var.set(tile) if hasattr(self, "mask_tile_var") else None
        lines = [f"Tile {tile} collision mask:", "", "Edit only the 8 rows below (# solid, . empty), then click Apply 8x8 mask:", "Leftmost character is mask bit 0 / left side of tile.", ""]
        if start + 8 <= len(self.level.masks):
            for row in self.level.masks[start:start + 8]:
                lines.append("".join("#" if row & (1 << bit) else "." for bit in range(8)))
            lines.extend(["", "# = solid low-res mask bit, . = empty"] )
        else:
            lines.append("No mask data for this tile index.")
        self.mask_text.configure(state="normal")
        self.mask_text.delete("1.0", tk.END)
        self.mask_text.insert("1.0", "\n".join(lines))
        # Keep editable so the user can patch the global tile mask.
        self.mask_text.configure(state="normal")

    def inspect_cell(self, x: int, y: int) -> None:
        assert self.level is not None
        cell = self.level.grid[y][x]
        self.status.set(f"Inspect x={x}, y={y}: tile={cell['tile']}, event={cell['event']}, bg={cell['bg']}")

    def select_object_at(self, x: int, y: int) -> None:
        assert self.level is not None
        cell = self.level.grid[y][x]
        if cell["event"]:
            self.selected_object = (x, y)
            self.current_event.set(cell["event"])
            self.render_event_definition(cell["event"])
            self.render_map()
            self.refresh_objects()
            self.select_object_in_tree(x, y)
            name = self.level.event_names[cell["event"]] if cell["event"] < len(self.level.event_names) else ""
            self.status.set(f"Selected object at ({x},{y}): event={cell['event']} {self.event_display_name(cell['event'])}")
        else:
            self.selected_object = None
            self.render_map()
            self.status.set(f"No object/event at ({x},{y}).")

    def select_object_in_tree(self, x: int, y: int) -> None:
        iid = f"{x},{y}"
        if iid in self.object_tree.get_children(""):
            self.object_tree.selection_set(iid)
            self.object_tree.see(iid)

    def erase_from_map(self, event: tk.Event) -> None:
        """Right-click erase.

        Tiles mode clears the visual block/BG flag.
        Events/Objects mode clears only the event placement and preserves the tile.
        Inspect mode erases event if present, otherwise clears the tile.
        Shift+right-click or middle-click still picks values from the map.
        """
        cell_pos = self.canvas_to_cell(event)
        if not cell_pos or not self.level:
            return
        x, y = cell_pos
        cell = self.level.grid[y][x]
        mode = self.tool_mode.get()

        if mode == "tiles":
            if self.lock_tiles.get():
                self.status.set("Tiles layer is locked; cannot erase tile.")
                return
            if cell["tile"] == 0 and cell["bg"] == 0:
                return
            self._push_undo()
            old_tile, old_bg = cell["tile"], cell["bg"]
            cell["tile"] = 0
            cell["bg"] = 0
            self._refresh_cell_chunk(x, y)
            self.refresh_validation()
            self.status.set(f"Right-click erased tile/BG at ({x},{y}): tile {old_tile}->0, bg {old_bg}->0. Event preserved: {cell['event']}.")
            return

        if mode in {"events", "objects"} or cell["event"]:
            if self.lock_events.get() or self.lock_objects.get():
                self.status.set("Event/object layer is locked; cannot erase event.")
                return
            if not cell["event"]:
                self.status.set(f"No event to erase at ({x},{y}).")
                return
            self._push_undo()
            old_event = cell["event"]
            cell["event"] = 0
            if self.selected_object == (x, y):
                self.selected_object = None
            self._refresh_cell_chunk(x, y)
            self.refresh_object_palette()
            self.refresh_objects()
            self.refresh_object_types()
            self.refresh_validation()
            self.status.set(f"Right-click erased event {old_event} at ({x},{y}). Tile preserved: {cell['tile']}.")
            return

        if cell["tile"] or cell["bg"]:
            self._push_undo()
            old_tile, old_bg = cell["tile"], cell["bg"]
            cell["tile"] = 0
            cell["bg"] = 0
            self._refresh_cell_chunk(x, y)
            self.refresh_validation()
            self.status.set(f"Right-click erased tile/BG at ({x},{y}): tile {old_tile}->0, bg {old_bg}->0.")
        else:
            self.status.set(f"Cell ({x},{y}) is already empty.")


    def pick_from_map(self, event: tk.Event) -> None:
        cell_pos = self.canvas_to_cell(event)
        if not cell_pos or not self.level:
            return
        x, y = cell_pos
        cell = self.level.grid[y][x]
        mode = self.tool_mode.get()
        if mode == "tiles":
            self.current_tile.set(cell["tile"])
            self.current_bg.set(cell["bg"])
            self.render_atlas()
            self.render_mask_info(cell["tile"])
            self.status.set(f"Picked tile/BG from ({x},{y}): tile={cell['tile']}, bg={cell['bg']}")
        elif mode in {"events", "objects"}:
            self.current_event.set(cell["event"])
            self._sync_event_selection()
            self.status.set(f"Picked event from ({x},{y}): event={cell['event']}")
        else:
            self.current_tile.set(cell["tile"])
            self.current_event.set(cell["event"])
            self.current_bg.set(cell["bg"])
            self.status.set(f"Picked all from ({x},{y}): tile={cell['tile']}, event={cell['event']}, bg={cell['bg']}")

    def on_atlas_click(self, event: tk.Event) -> None:
        if not self.tileset:
            return
        scale = 2
        columns = self._atlas_columns(scale)
        x = int(self.atlas_canvas.canvasx(event.x) // (TILE_SIZE * scale))
        y = int(self.atlas_canvas.canvasy(event.y) // (TILE_SIZE * scale))
        tile = y * columns + x
        if 0 <= tile < len(self.tileset.tiles):
            self.current_tile.set(tile)
            self.tool_mode.set("tiles")
            self.tabs.select(0)
            self.render_atlas()
            self.render_mask_info(tile)
            self.status.set(f"Selected tile {tile}; mode set to Tiles")

    def on_event_select(self, _event: tk.Event) -> None:
        selection = self.event_list.curselection()
        if selection:
            event_id = int(selection[0])
            self.current_event.set(event_id)
            self.tool_mode.set("events")
            self.render_event_definition(event_id)
            self.status.set(f"Selected event {event_id}; mode set to Events")

    def _sync_event_selection(self) -> None:
        event_id = max(0, min(126, int(self.current_event.get())))
        self.current_event.set(event_id)
        self.event_list.selection_clear(0, tk.END)
        self.event_list.selection_set(event_id)
        self.event_list.see(event_id)
        self.render_event_definition(event_id)

    def on_object_tree_select(self, _event: tk.Event) -> None:
        selection = self.object_tree.selection()
        if not selection or not self.level:
            return
        x_s, y_s = selection[0].split(",")
        x, y = int(x_s), int(y_s)
        self.selected_object = (x, y)
        event_id = self.level.grid[y][x]["event"]
        self.current_event.set(event_id)
        self.tool_mode.set("objects")
        self.render_event_definition(event_id)
        self.render_map()
        self.status.set(f"Selected object at ({x},{y}), event={event_id}")

    def delete_selected_object(self) -> None:
        if not self.level or not self.selected_object:
            self.status.set("No selected object to delete.")
            return
        x, y = self.selected_object
        self._push_undo()
        event_id = self.level.grid[y][x]["event"]
        self.level.grid[y][x]["event"] = 0
        self.selected_object = None
        self.render_map()
        self.refresh_object_palette()
        self.refresh_objects()
        self.refresh_object_types()
        self.refresh_validation()
        self.status.set(f"Deleted object/event {event_id} at ({x},{y}). Tile was preserved.")

    def duplicate_selected_object_to_brush(self) -> None:
        if not self.level or not self.selected_object:
            self.status.set("No selected object to duplicate.")
            return
        x, y = self.selected_object
        event_id = self.level.grid[y][x]["event"]
        self.current_event.set(event_id)
        self.tool_mode.set("events")
        self.workspace_tabs.select(self.build_workspace)
        self.build_tabs.select(self.objects_tab)
        self._sync_event_selection()
        self.status.set(f"Copied object event={event_id} to event brush. Click map in Events mode to place another instance.")

    def render_event_definition(self, event_id: int) -> None:
        if not self.level or not hasattr(self, "event_def_text"):
            return
        event_id = max(0, min(126, int(event_id)))
        self._editing_event_id = event_id
        raw = self.level.event_types[event_id]
        name = self.level.event_names[event_id] if event_id < len(self.level.event_names) else ""
        evdef = EventDefinition(event_id, name, raw)

        if hasattr(self, "event_def_combo"):
            vals = self.event_def_combo["values"]
            if vals:
                self.event_def_combo.current(event_id)

        if hasattr(self, "event_def_edit_vars"):
            for idx, var in self.event_def_edit_vars.items():
                if idx < len(raw):
                    var.set(raw[idx])
            if hasattr(self, "event_def_field_labels"):
                for idx, label in self.event_def_field_labels.items():
                    label.configure(text=event_field_label_for(raw, idx))

        if hasattr(self, "event_concept_var"):
            self.event_concept_var.set(infer_event_concept(event_id, raw, name))
        if hasattr(self, "event_concept_frame"):
            self.rebuild_event_concept_editor(event_id, raw)

        if hasattr(self, "event_def_title"):
            self.event_def_title.configure(text=f"Event {event_id:03d}: {friendly_event_name(evdef)}")

        semantic_lines = semantic_event_lines(event_id, raw, name)
        semantic_lines.append("")
        semantic_lines.append(f"Used by placements in this level: {self.event_usage_counts().get(event_id, 0)}")
        if hasattr(self, "event_semantic_text"):
            self.event_semantic_text.configure(state="normal")
            self.event_semantic_text.delete("1.0", tk.END)
            self.event_semantic_text.insert("1.0", "\n".join(semantic_lines))
            self.event_semantic_text.configure(state="disabled")

        lines = [f"event_id: {event_id}", f"name: {name or '(unnamed)'}", f"friendly: {friendly_event_name(evdef)}"]
        if is_reserved_engine_event(event_id):
            info = RESERVED_ENGINE_EVENTS[event_id]
            lines.extend([
                "",
                "RESERVED ENGINE MARKER:",
                f"  {info['summary']}",
                f"  {info['editor_hint']}",
                "  The numeric event ID is what matters for the special behavior.",
                "  The 32-byte definition is still shown below for completeness.",
            ])
        lines.extend(["", "bytes:"])
        for i, value in enumerate(raw):
            label = EVENT_FIELD_NAMES[i] if i < len(EVENT_FIELD_NAMES) else f"byte_{i:02d}"
            editable = "" if i in EDITABLE_EVENT_FIELD_INDICES else "  (unused/not editable)"
            lines.append(f"  {i:02d} {label:<16} = {value:3d}  0x{value:02X}{editable}")

        if len(raw) >= 32:
            lines.extend([
                "",
                "decoded fields:",
                f"  category    = {semantic_event_category(event_id, raw, name)}",
                f"  concept     = {infer_event_concept(event_id, raw, name)}",
                f"  movement    = {raw[4]} ({movement_meaning_detail(raw[4])[0]})",
                f"  modifier    = {raw[10]} ({modifier_meaning(raw[10])[0]})",
                f"  left_anim   = {raw[5]}",
                f"  right_anim  = {raw[6]}",
                f"  magnitude   = {raw[8]} / signed {_signed_byte(raw[8])}",
                f"  strength    = {raw[9]}",
                f"  points      = {raw[11]}",
                f"  bullet      = {raw[12]} ({bullet_type_label(raw[12])})",
                f"  bullet_per. = {raw[13]}",
                f"  speed       = {raw[15] + 1}",
                f"  anim_speed  = {raw[17] + 1}",
                f"  sound       = {raw[21]}",
                f"  multi_a/b   = {raw[22]} / {raw[23]}",
                f"  pieces      = size {raw[24]}, count {raw[25]}",
                f"  angle       = {raw[26]}",
                f"  finish      = {raw[28]} / {raw[29]}",
                f"  shoot       = {raw[30]} / {raw[31]}",
            ])
            for label, anim_id in [("left", raw[5]), ("right", raw[6]), ("left_finish", raw[28]), ("right_finish", raw[29]), ("left_shoot", raw[30]), ("right_shoot", raw[31])]:
                anim = self.level.animation(anim_id) if self.level else None
                if anim:
                    lines.append(f"  {label:<12} anim {anim_id:03d}: len={anim.length}, frames={anim.frame_ids}")
        self.event_def_text.configure(state="normal")
        self.event_def_text.delete("1.0", tk.END)
        self.event_def_text.insert("1.0", "\n".join(lines))
        self.event_def_text.configure(state="disabled")

    def populate_animations(self) -> None:
        if not hasattr(self, "anim_tree"):
            return
        self.anim_tree.delete(*self.anim_tree.get_children())
        if not self.level:
            return
        used = set()
        for ev in self.level.event_catalog()[1:]:
            for idx in [5, 6, 28, 29, 30, 31]:
                if idx < len(ev.raw) and ev.raw[idx]:
                    used.add(ev.raw[idx] & 0x7F)
        for anim in self.level.animations:
            if anim.length <= 0 and anim.anim_id not in used and not anim.name:
                continue
            suffix = " *used" if anim.anim_id in used else ""
            self.anim_tree.insert("", tk.END, iid=str(anim.anim_id), values=(anim.anim_id, (anim.name or "") + suffix, anim.length, ",".join(map(str, anim.frame_ids))))

    def on_anim_tree_select(self, _event: tk.Event) -> None:
        if not self.level or not self.spriteset:
            return
        selection = self.anim_tree.selection()
        if not selection:
            return
        anim_id = int(selection[0])
        anim = self.level.animation(anim_id)
        if not anim:
            return
        for child in self.anim_preview_frame.winfo_children():
            child.destroy()
        self._sprite_photo_refs = []
        ttk.Label(self.anim_preview_frame, text=f"Animation {anim_id}: {anim.name or '(unnamed)'}").pack(anchor="w")
        strip = ttk.Frame(self.anim_preview_frame)
        strip.pack(fill=tk.X, pady=(4, 0))
        for n, frame_id in enumerate(anim.frame_ids[:12]):
            frame = self.spriteset.get(frame_id)
            if frame:
                img = frame.image.copy()
                img.thumbnail((48, 48), Image.Resampling.NEAREST)
                canvas = Image.new("RGBA", (54, 64), (0, 0, 0, 0))
                canvas.alpha_composite(img, ((54 - img.width) // 2, 0))
                photo = ImageTk.PhotoImage(canvas)
                self._sprite_photo_refs.append(photo)
                lbl = ttk.Label(strip, image=photo, text=f"#{n}\nS{frame_id}", compound=tk.TOP)
                lbl.pack(side=tk.LEFT, padx=(0, 4))
        self.anim_edit_text.delete("1.0", tk.END)
        self.anim_edit_text.insert("1.0", "\n".join(f"{f} {x} {y}" for f, x, y in zip(anim.frame_ids, anim.frame_x, anim.frame_y)))
        details = [
            f"Animation {anim_id}",
            f"name: {anim.name or '(unnamed)'}",
            f"length: {anim.length}",
            f"sprite frames: {anim.frame_ids}",
            f"frame x offsets: {anim.frame_x}",
            f"frame y offsets: {anim.frame_y}",
        ]
        users = []
        for ev in self.level.event_catalog()[1:]:
            raw = ev.raw
            labels = []
            for label, idx in [("left",5),("right",6),("finishL",28),("finishR",29),("shootL",30),("shootR",31)]:
                if idx < len(raw) and (raw[idx] & 0x7F) == anim_id:
                    labels.append(label)
            if labels:
                users.append(f"event {ev.event_id:03d} {ev.name or '(unnamed)'} uses as {','.join(labels)}")
        details.append("")
        details.append("Used by:")
        details.extend(users[:25] or ["no obvious event reference"])
        self.anim_detail_text.configure(state="normal")
        self.anim_detail_text.delete("1.0", tk.END)
        self.anim_detail_text.insert("1.0", "\n".join(details))
        self.anim_detail_text.configure(state="disabled")


    def apply_event_definition_from_ui(self) -> None:
        if not self.level:
            return
        event_id = max(0, min(126, int(self._editing_event_id)))
        raw = bytearray(self.level.event_types[event_id])

        concept = self.event_concept_var.get() if hasattr(self, "event_concept_var") else infer_event_concept(event_id, raw)
        if concept == "Auto / keep current":
            concept = infer_event_concept(event_id, raw, self.level.event_names[event_id] if event_id < len(self.level.event_names) else "")

        if not is_reserved_engine_event(event_id):
            self.apply_event_concept_to_raw(raw, concept)

        # Advanced raw fields can override the concept editor when visible.
        if hasattr(self, "event_raw_fields_frame") and self.event_raw_fields_frame.winfo_ismapped():
            for idx, var in getattr(self, "event_def_edit_vars", {}).items():
                try:
                    raw[idx] = max(0, min(255, int(var.get())))
                except Exception:
                    pass

        self.level.event_types[event_id] = bytes(raw)
        self.set_dirty(True)
        self._event_preview_cache.clear()
        self.populate_events()
        self.refresh_event_def_selector()
        self.refresh_object_palette()
        self.refresh_objects()
        self.refresh_object_types()
        self.populate_animations()
        self.render_event_definition(event_id)
        self.render_map()
        self.refresh_validation()
        uses = self.event_usage_counts().get(event_id, 0)
        self.status.set(f"Applied Event {event_id:03d} as '{concept}'. It affects {uses} placed object(s) in this level.")

    def populate_paths(self) -> None:
        if not hasattr(self, "path_combo"):
            return
        if not self.level:
            self.path_combo["values"] = []
            return
        values = []
        for pdef in self.level.path_defs:
            marker = "used" if pdef.nonempty else "empty"
            values.append(f"{pdef.path_id}: {marker}, len={pdef.length}")
        self.path_combo["values"] = values
        if values:
            self.path_combo.current(0)
            self.selected_path.set(0)
            self.render_path_info(0)

    def on_path_select(self, _event: tk.Event) -> None:
        if not self.level or not hasattr(self, "path_combo"):
            return
        idx = self.path_combo.current()
        if idx < 0:
            return
        self.selected_path.set(idx)
        self.render_path_info(idx)
        self.render_map()

    def render_path_info(self, path_id: int) -> None:
        if not self.level or not hasattr(self, "path_text"):
            return
        path_id = max(0, min(15, int(path_id)))
        pdef = self.level.path_defs[path_id]
        self.path_canvas.delete("all")
        lines = [f"Path {path_id}", f"length: {pdef.length}", ""]
        lines.append("OpenJazz interpretation: each entry is read as signed y, signed x<<2. The exact semantic is event-dependent, so this tab treats it as diagnostic movement data.")
        lines.append("")
        lines.append("points / deltas:")
        for i, (dx, dy) in enumerate(pdef.points[:80]):
            lines.append(f"  {i:03d}: x={dx:4d}, y={dy:4d}")
        if len(pdef.points) > 80:
            lines.append(f"  ... {len(pdef.points) - 80} more")
        if hasattr(self, "path_edit_text"):
            self.path_edit_text.delete("1.0", tk.END)
            self.path_edit_text.insert("1.0", "\n".join(f"{dx} {dy}" for dx, dy in pdef.points))
        self.path_text.configure(state="normal")
        self.path_text.delete("1.0", tk.END)
        self.path_text.insert("1.0", "\n".join(lines))
        self.path_text.configure(state="disabled")
        if not pdef.points:
            self.path_canvas.create_text(12, 20, anchor="w", fill="white", text="Empty path")
            return
        pts = []
        x = y = 0
        for dx, dy in pdef.points:
            x += dx
            y += dy
            pts.append((x, y))
        min_x = min(x for x, _ in pts)
        max_x = max(x for x, _ in pts)
        min_y = min(y for _, y in pts)
        max_y = max(y for _, y in pts)
        w = max(1, max_x - min_x)
        h = max(1, max_y - min_y)
        canvas_w = max(300, self.path_canvas.winfo_width() or 300)
        canvas_h = 210
        scale = min((canvas_w - 30) / w, (canvas_h - 30) / h, 4.0)
        def cv(pt):
            px, py = pt
            return (15 + (px - min_x) * scale, 15 + (py - min_y) * scale)
        prev = cv(pts[0])
        self.path_canvas.create_oval(prev[0]-4, prev[1]-4, prev[0]+4, prev[1]+4, outline="cyan")
        for pt in pts[1:]:
            cur = cv(pt)
            self.path_canvas.create_line(prev[0], prev[1], cur[0], cur[1], fill="cyan", width=2)
            prev = cur
        self.path_canvas.create_oval(prev[0]-4, prev[1]-4, prev[0]+4, prev[1]+4, outline="yellow")

    def apply_path_from_ui(self) -> None:
        if not self.level or not hasattr(self, "path_edit_text"):
            return
        path_id = max(0, min(15, int(self.selected_path.get())))
        points: List[Tuple[int, int]] = []
        for line_no, line in enumerate(self.path_edit_text.get("1.0", tk.END).splitlines(), 1):
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            parts = line.replace(",", " ").split()
            if len(parts) < 2:
                messagebox.showerror("Invalid path", f"Line {line_no}: expected dx dy")
                return
            try:
                dx, dy = int(float(parts[0])), int(float(parts[1]))
            except ValueError:
                messagebox.showerror("Invalid path", f"Line {line_no}: expected numeric dx dy")
                return
            points.append((dx, dy))
        self.level.set_path_points(path_id, points)
        self.set_dirty(True)
        self.populate_paths()
        self.selected_path.set(path_id)
        if hasattr(self, "path_combo"):
            self.path_combo.current(path_id)
        self.render_path_info(path_id)
        self.render_map()
        self.refresh_global_summary()
        self.status.set(f"Edited global path {path_id}. Enable/save global paths is on; Save as... writes it.")

    def apply_mask_from_ui(self) -> None:
        if not self.level or not hasattr(self, "mask_text"):
            return
        tile = max(0, min(255, int(self.mask_tile_var.get())))
        rows = []
        for line in self.mask_text.get("1.0", tk.END).splitlines():
            stripped = line.strip()
            if len(stripped) >= 8 and all(ch in ".#01Xx@█" for ch in stripped[:8]):
                rows.append(stripped[:8])
            if len(rows) == 8:
                break
        if len(rows) != 8:
            messagebox.showerror("Invalid mask", "Could not find 8 editable rows containing only . # 0 1 X characters.")
            return
        self.level.set_tile_mask_rows(tile, rows)
        self.set_dirty(True)
        self.render_mask_info(tile)
        self.render_map()
        self.refresh_validation()
        self.refresh_global_summary()
        self.status.set(f"Edited level-local collision mask for tile {tile}.")

    def apply_animation_from_ui(self) -> None:
        if not self.level or not hasattr(self, "anim_tree") or not hasattr(self, "anim_edit_text"):
            return
        selection = self.anim_tree.selection()
        if not selection:
            messagebox.showinfo("Animation", "Select an animation first.")
            return
        anim_id = int(selection[0])
        frames: List[Tuple[int, int, int]] = []
        for line_no, line in enumerate(self.anim_edit_text.get("1.0", tk.END).splitlines(), 1):
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            parts = line.replace(",", " ").split()
            if len(parts) < 1:
                continue
            try:
                frame = int(float(parts[0]))
                xoff = int(float(parts[1])) if len(parts) > 1 else 0
                yoff = int(float(parts[2])) if len(parts) > 2 else 0
            except ValueError:
                messagebox.showerror("Invalid animation", f"Line {line_no}: expected sprite_id x_offset y_offset")
                return
            frames.append((frame, xoff, yoff))
        self.level.set_animation_frames(anim_id, frames)
        self.set_dirty(True)
        self._event_preview_cache.clear()
        self.populate_animations()
        self.anim_tree.selection_set(str(anim_id))
        self.anim_tree.see(str(anim_id))
        self.on_anim_tree_select(tk.Event())
        self.render_map()
        self.refresh_validation()
        self.refresh_global_summary()
        self.status.set(f"Edited global animation {anim_id}.")

    def draw_path_overlay(self, draw: ImageDraw.ImageDraw) -> None:
        if not self.level or not self.level.path_defs:
            return
        path_id = max(0, min(15, int(self.selected_path.get())))
        pdef = self.level.path_defs[path_id]
        if not pdef.points:
            return
        if self.selected_object:
            anchor_x, anchor_y = self.selected_object
        else:
            anchor_x, anchor_y = self.level.metadata.start_x, self.level.metadata.start_y
        x = anchor_x * TILE_SIZE + TILE_SIZE // 2
        y = anchor_y * TILE_SIZE + TILE_SIZE // 2
        prev = (x, y)
        draw.ellipse((x-4, y-4, x+4, y+4), outline=(80, 255, 255, 255), width=2)
        for dx, dy in pdef.points[:240]:
            x += dx
            y += dy
            cur = (x, y)
            draw.line((prev[0], prev[1], cur[0], cur[1]), fill=(80, 255, 255, 220), width=2)
            prev = cur
        draw.ellipse((x-4, y-4, x+4, y+4), outline=(255, 255, 80, 255), width=2)
        draw.text((anchor_x * TILE_SIZE + 2, anchor_y * TILE_SIZE + 2), f"P{path_id}", fill=(80, 255, 255, 255))

    def _save_to_path(self, path: Path) -> bool:
        if not self.level:
            return False
        try:
            self.level.save_as(
                path,
                save_event_defs=True,
                save_paths=True,
                save_masks=True,
                save_animations=True,
            )
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))
            return False
        self.current_save_path = path
        self.set_dirty(False)
        self.status.set(f"Saved {path}")
        return True

    def save(self) -> bool:
        if not self.level:
            return False
        target = self.current_save_path or self.level.path
        return self._save_to_path(Path(target))

    def save_as(self) -> bool:
        if not self.level:
            return False
        default = self.current_save_path or self.level.path
        target = filedialog.asksaveasfilename(
            title="Save level as",
            initialdir=str(default.parent),
            initialfile=default.name,
            filetypes=[("JJ1 level", "LEVEL*.*"), ("All files", "*")],
        )
        if not target:
            return False
        return self._save_to_path(Path(target))



def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Standalone Jazz Jackrabbit 1 DOS GUI level editor prototype")
    parser.add_argument("game_dir", nargs="?", default=".", help="Directory containing Jazz Jackrabbit DOS files")
    args = parser.parse_args(argv)
    app = LevelEditorApp(Path(args.game_dir).expanduser().resolve())
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
