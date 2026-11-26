"""生成 gpt-image 出图清单（concept_art.py 的 JSON spec），提示词是 11-24 实测有效的模板。

    python gen_spec.py --char "<角色外观英文描述>" --id hero --out spec.json \
        [--design] [--walk right,left,down,up] [--attack right] [--prop "<道具描述>"] [--variants 4] [--style-ref art:walk8_b]

产物 id：<id>_design、<id>_walk8<dir>_<a|b|c|d>、<id>_atk_<a..>、<id>_prop_<a..>；参考图写成 "art:<id>"（同一输出子目录）。
先单独跑 --design（设定图），满意后再跑动作（动作引用设定图）。
"""
import argparse
import json

STYLE = ("authentic 16-bit SNES-era pixel art, same pixel size and scale as the reference sprites (each art pixel a crisp square block), "
         "hard pixel edges, NO anti-aliasing, NO gradients, NO blur, same limited palette as the reference, 1-pixel dark outline, "
         "simple cel shading, flat solid pure magenta #FF00FF background, no ground shadow, no text, no labels, no grid lines, no borders")
STYLE_DESIGN = ("authentic 16-bit SNES-era pixel art, top-down RPG character sprite, chibi proportions (big head, about 2 heads tall), "
                "every sprite is a 32x32-pixel sprite scaled up exactly 8x with nearest-neighbor so each art pixel is a crisp 8x8 square block, "
                "hard pixel edges, NO anti-aliasing, NO gradients, NO blur, limited palette of at most 16 colors, warm earthy palette, "
                "1-pixel dark outline around the character, simple 3-tone cel shading with light from top-left, "
                "flat solid pure magenta #FF00FF background everywhere, no shadow on the ground, no text, no labels, no grid lines, no borders")
GRID8 = "Strict grid of 4 columns x 2 rows of equal cells, 8 frames read left-to-right, top row then bottom row."
CYCLE = ("frame 1 legs widest apart (front heel down), frame 2 legs slightly closer, frame 3 legs crossing under the body (other knee lifted), "
         "frame 4 other leg reaching forward, frame 5 legs widest apart with the other leg in front, frame 6 slightly closer, "
         "frame 7 crossing, frame 8 reaching. Every frame is a different pose; no two frames are the same. Arms swing opposite to the legs.")


def design(char: str) -> str:
    return ("Character turnaround reference sheet, 2x2 layout: top-left facing camera (front), top-right facing left, "
            "bottom-left facing right, bottom-right facing away (back view), standing idle pose, same character in all four, "
            f"each pose centered in its quadrant at identical size. {char}. {STYLE_DESIGN}.")


def walk(char: str, d: str) -> str:
    if d in ("right", "left"):
        side = d.upper()
        back = "BACKWARD (to the left)" if d == "right" else "BACKWARD (to the right)"
        view = (f"Side view, walking to the {side}. The head and torso stay at exactly the same horizontal position in every cell. "
                f"The foot that is on the ground slides {back} by the SAME distance in every frame (about one boot length per two frames), "
                "never staying still and never jumping:")
    elif d == "down":
        view = ("Top-down RPG three-quarter view, walking TOWARD the camera (facing down/front, face visible). The head and torso stay at the "
                "same position in every cell, the foot on the ground moves UP inside the cell by an equal amount every frame; the forward foot appears lower:")
    else:
        view = ("Top-down RPG three-quarter view, walking AWAY from the camera (facing up, back view, no face). The head and torso stay at the "
                "same position in every cell, the foot on the ground moves DOWN inside the cell by an equal amount every frame:")
    return (f"A smooth, EVENLY SPACED 8-frame walk cycle sprite sheet of the same character as the references: {char}. {view} {CYCLE} "
            f"{GRID8} Legs and boots clearly separated. Same character size in every cell, feet on the same baseline. "
            f"Same pixel scale and character size as the last reference image. {STYLE}.")


def attack(char: str, d: str, weapon: str) -> str:
    return (f"Side view, facing {d.upper()}. A flashy melee attack animation sprite sheet for a 2D action RPG. The same character as the references: "
            f"{char}, wielding {weapon}. {GRID8} The character is the same size in every frame and stands in the {'LEFT' if d == 'right' else 'RIGHT'} "
            "half of each cell so the weapon swing and effects fit in the other half; everything stays fully inside its own cell; feet on the same baseline. "
            "Frames: 1 ready stance; 2 anticipation: crouch low and pull the weapon far back; 3 lunge forward, body stretched; "
            "4 SMEAR frame: fast swing drawn as a wide bright crescent arc; 5 IMPACT: biggest crescent slash with a burst of sparks; "
            "6 follow-through: arc fading into particles; 7 recovery; 8 back to ready stance. Strong poses, clear silhouettes. "
            "Effects are solid pixel shapes with hard edges, NO soft glow, NO halo, NO transparency gradients. " + STYLE + ".")


def prop(desc: str) -> str:
    return (f"Side view {desc}, same pixel-art style and pixel scale as the reference sprite. Strict grid of 3 columns x 1 row of equal cells: "
            f"1 idle; 2 reacting to a hit; 3 settling back. Same size and position in every cell. {STYLE}.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", required=True, help="角色外观（英文，越具体越稳定：发型/发饰/衣服/配件/颜色）")
    ap.add_argument("--id", default="hero")
    ap.add_argument("--out", required=True)
    ap.add_argument("--design", action="store_true")
    ap.add_argument("--walk", default="", help="逗号分隔方向：right,left,down,up")
    ap.add_argument("--attack", default="", help="攻击朝向：right（朝左用水平翻转）")
    ap.add_argument("--weapon", default="a short wooden staff topped with a glowing leaf")
    ap.add_argument("--prop", default="")
    ap.add_argument("--variants", type=int, default=4, help="每个动作出几版（挑最均匀/最好看的）")
    ap.add_argument("--style-ref", default="", help="额外的风格/尺寸参考，如 art:walk8_b（已认可的行走图）")
    a = ap.parse_args()
    refs = [f"art:{a.id}_design"] + ([a.style_ref] if a.style_ref else [])
    vs = "abcdefgh"[: a.variants]
    items = []
    if a.design:
        items.append({"id": f"{a.id}_design", "size": "1024x1024", "refs": [], "prompt": design(a.char)})
    for d in filter(None, a.walk.split(",")):
        items += [{"id": f"{a.id}_walk8{d}_{v}", "size": "1536x1024", "refs": refs, "prompt": walk(a.char, d)} for v in vs]
    for d in filter(None, a.attack.split(",")):
        items += [{"id": f"{a.id}_atk{d}_{v}", "size": "1536x1024", "refs": refs, "prompt": attack(a.char, d, a.weapon)} for v in vs]
    if a.prop:
        items += [{"id": f"{a.id}_prop_{v}", "size": "1536x1024", "refs": refs[-1:], "prompt": prop(a.prop)} for v in vs[:2]]
    for it in items:  # 中转用 curl -F 上传提示词：分号后面会被当成表单属性丢掉！
        it["prompt"] = it["prompt"].replace(";", ",")
    json.dump(items, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(items)} 张，约 ¥{len(items) * 0.5:.1f}", [i["id"] for i in items])


if __name__ == "__main__":
    main()
