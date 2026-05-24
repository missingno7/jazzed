from __future__ import annotations

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
BULLETS = 32
BLENGTH = 20
SOUNDS = 32
JJ1PANIMS = 38
JJ1MANIMS = 4
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

