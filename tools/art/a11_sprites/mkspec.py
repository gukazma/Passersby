import json
STYLE = ("authentic 16-bit SNES-era pixel art, same pixel size and scale as the reference sprites (each art pixel a crisp square block), "
         "hard pixel edges, NO anti-aliasing, NO gradients, NO blur, same limited palette as the reference, 1-pixel dark outline, "
         "simple cel shading, flat solid pure magenta #FF00FF background, no ground shadow, no text, no labels, no grid lines, no borders")
GRID8 = "Strict grid of 4 columns x 2 rows of equal cells, 8 frames read left-to-right, top row then bottom row."
CH = {"hero": "a young herb-gathering girl, short brown bob hair with a small green leaf hair clip, orange-red scarf, olive-green tunic dress, brown boots, a woven wicker basket with white flowers carried on her back",
      "npc_office": "a young office worker man, short black side-parted hair, white shirt, loose dark-red tie, charcoal trousers, brown leather shoes, carrying a brown briefcase",
      "npc_student": "a cheerful schoolboy, messy brown hair, mustard-yellow hoodie, navy shorts, white sneakers, red backpack"}
def idle(c, d):
    return (f"Side view STANDING IDLE sprite sheet of exactly the same character as the references: {c}. Facing {d.upper()} in a strict side profile, "
            "the same facing, head, face and proportions as the walking sprites in the last reference image. Standing still and upright: body vertical with NO forward lean, "
            "both legs straight and parallel, close together, BOTH feet flat on the ground on the same baseline, NO lifted leg, NO stepping, "
            "arms relaxed hanging at the sides, carried items held the same way as in the reference. "
            f"{GRID8} All 8 cells show the same calm standing pose with only a tiny one-pixel breathing motion of the shoulders. "
            f"Same pixel scale and character size as the last reference image, feet on the same baseline in every cell. {STYLE}.")
RUNC = ("Frames: 1 contact, front heel lands far forward, 2 down, body lowest, knee bent under the body, 3 push-off, back leg fully extended behind, "
        "4 flight, both feet off the ground, legs spread wide, 5 contact with the OTHER leg in front, 6 down, 7 push-off, 8 flight. "
        "Every frame is a different pose, no two frames are the same. Arms bent about 90 degrees and swinging strongly opposite to the legs.")
def run(c, d):
    if d in ("right", "left"):
        back = "BACKWARD (to the left)" if d == "right" else "BACKWARD (to the right)"
        view = (f"Side view, RUNNING fast to the {d.upper()}. Torso leaning slightly forward, long strides, knees lifted high. The head stays at exactly the same "
                f"horizontal position in every cell. The foot on the ground slides {back} by a large equal distance every frame:")
    elif d == "down":
        view = ("Top-down RPG three-quarter view, RUNNING toward the camera (facing down, face visible), body leaning slightly forward, knees lifted high, "
                "the head stays at the same position in every cell, the foot on the ground moves UP inside the cell by an equal amount every frame:")
    else:
        view = ("Top-down RPG three-quarter view, RUNNING away from the camera (facing up, back view, no face), knees lifted high, "
                "the head stays at the same position in every cell, the foot on the ground moves DOWN inside the cell by an equal amount every frame:")
    return (f"A smooth, EVENLY SPACED 8-frame RUN cycle sprite sheet of the same character as the references: {c}. {view} {RUNC} {GRID8} "
            f"Legs and boots clearly separated. Same character size in every cell, feet on the same baseline. Same pixel scale and character size as the last reference image. {STYLE}.")
items = []
for n in CH:
    for d in ("left", "right"):
        items += [{"id": f"{n}_idle{d}_{v}", "size": "1536x1024", "refs": [f"art:{n}_design", f"art:{n}_walkpx_{d}"], "prompt": idle(CH[n], d)} for v in "ab"]
for d, vs in (("right", "abc"), ("left", "abc"), ("down", "ab"), ("up", "ab")):
    items += [{"id": f"hero_run8{d}_{v}", "size": "1536x1024", "refs": ["art:hero_design", f"art:hero_walkpx_{d}"], "prompt": run(CH["hero"], d)} for v in vs]
for it in items: it["prompt"] = it["prompt"].replace(";", ",")
json.dump(items, open("a11_sprites.json", "w"), ensure_ascii=False, indent=1)
print(len(items))
