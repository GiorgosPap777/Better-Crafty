"""Sample player files for the test server (screenshots and browser checks)."""
import json, os, sys, time, random
sys.path.insert(0, os.environ.get("REPO", "/home/user/Better-Crafty"))
from tests.classes.helpers.test_player_data import byte, short, flt, int_array, nbt_file

server = sys.argv[1]
world = os.path.join(server, "world")
for sub in ("playerdata", "stats", "advancements"):
    os.makedirs(os.path.join(world, sub), exist_ok=True)

NOTCH = "069a79f4-44e9-4726-a5be-fca90e38aaf5"
JEB = "853c80ef-3c37-49fd-aa49-938b674adae6"
ALEX = "6e2f1d0c-8b7a-4f3e-9d2c-1b0a9f8e7d6c"
XSS = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
NONAME = "f0e1d2c3-b4a5-4968-8776-655443322110"

def item(slot, id, count=1, **components):
    entry = {"Slot": byte(slot), "id": f"minecraft:{id}", "count": count}
    if components:
        entry["components"] = {f"minecraft:{k}": v for k, v in components.items()}
    return entry

modern = {
    "DataVersion": 4440, "Health": flt(17.0), "foodLevel": 16, "foodSaturationLevel": flt(3.0),
    "XpLevel": 34, "XpP": flt(0.62), "playerGameType": 0, "Dimension": "minecraft:overworld",
    "Pos": [-245.61, 71.0, 1032.4], "SelectedItemSlot": 0,
    "attributes": [{"id": "minecraft:max_health", "base": 20.0}],
    "respawn": {"dimension": "minecraft:overworld", "pos": int_array([-240, 70, 1028])},
    "LastDeathLocation": {"dimension": "minecraft:the_nether", "pos": int_array([88, 31, -412])},
    "Inventory": [
        item(0, "netherite_sword", enchantments={"minecraft:sharpness": 5, "minecraft:looting": 3, "minecraft:mending": 1}, damage=412),
        item(1, "diamond_pickaxe", enchantments={"minecraft:efficiency": 5, "minecraft:fortune": 3, "minecraft:unbreaking": 3}, damage=1210),
        item(2, "bow", enchantments={"minecraft:power": 4, "minecraft:infinity": 1}),
        item(3, "golden_carrot", 47), item(4, "torch", 63), item(5, "oak_log", 64),
        item(6, "water_bucket"), item(7, "ender_pearl", 12),
        item(8, "firework_rocket", 64),
        item(9, "cobblestone", 64), item(10, "cobblestone", 64), item(11, "iron_ingot", 23),
        item(12, "diamond", 9), item(13, "redstone", 41), item(14, "shulker_box",
            container=[{"slot": 0, "item": {"id": "minecraft:diamond_block", "count": 12}},
                       {"slot": 1, "item": {"id": "minecraft:emerald", "count": 30}}]),
        item(15, "enchanted_book", stored_enchantments={"minecraft:protection": 4}),
        item(16, "potion", potion_contents={"potion": "minecraft:long_night_vision"}),
        item(18, "name_tag", custom_name="<b>Sir Fluffy</b>" if os.environ.get("XSS") else "Sir Fluffy"),
        item(20, "bread", 18), item(22, "arrow", 64), item(27, "crafting_table"),
        item(30, "spyglass"), item(33, "compass"), item(35, "clock"),
    ],
    "equipment": {
        "head": {"id": "minecraft:diamond_helmet", "count": 1, "components": {"minecraft:enchantments": {"minecraft:protection": 4}, "minecraft:damage": 40}},
        "chest": {"id": "minecraft:elytra", "count": 1, "components": {"minecraft:damage": 300}},
        "legs": {"id": "minecraft:diamond_leggings", "count": 1},
        "feet": {"id": "minecraft:diamond_boots", "count": 1, "components": {"minecraft:enchantments": {"minecraft:feather_falling": 4}}},
        "offhand": {"id": "minecraft:totem_of_undying", "count": 1},
    },
    "EnderItems": [item(0, "shulker_box"), item(1, "netherite_ingot", 4), item(13, "nether_star"), item(26, "beacon")],
}

old = {
    "DataVersion": 3700, "Health": flt(20.0), "foodLevel": 20, "XpLevel": 3, "XpP": flt(0.1),
    "playerGameType": 1, "Dimension": "minecraft:the_end", "Pos": [12.5, 64.0, 0.5], "SelectedItemSlot": 2,
    "SpawnX": 100, "SpawnY": 65, "SpawnZ": -50, "SpawnDimension": "minecraft:overworld",
    "Attributes": [{"Name": "minecraft:generic.max_health", "Base": 20.0}],
    "Inventory": [
        {"Slot": byte(0), "id": "minecraft:iron_sword", "Count": byte(1), "tag": {"Damage": 120, "display": {"Name": '{"text":"Old Faithful"}'}, "Enchantments": [{"id": "minecraft:smite", "lvl": short(3)}]}},
        {"Slot": byte(2), "id": "minecraft:stone", "Count": byte(64)},
        {"Slot": byte(103), "id": "minecraft:iron_helmet", "Count": byte(1)},
        {"Slot": byte(-106), "id": "minecraft:shield", "Count": byte(1), "tag": {"Damage": 50}},
    ],
}

alex = {**modern, "Health": flt(6.5), "foodLevel": 4, "XpLevel": 7, "playerGameType": 2, "Inventory": [item(0, "wooden_pickaxe", damage=50)], "equipment": {}, "EnderItems": []}

players = {NOTCH: modern, JEB: old, ALEX: alex, XSS: alex, NONAME: alex}
now = time.time()
ages = {NOTCH: 120, JEB: 3 * 86400, ALEX: 40 * 86400, XSS: 90 * 86400, NONAME: 200 * 86400}
for uuid, nbt in players.items():
    path = os.path.join(world, "playerdata", f"{uuid}.dat")
    with open(path, "wb") as f:
        f.write(nbt_file(nbt))
    os.utime(path, (now - ages[uuid], now - ages[uuid]))

rnd = random.Random(4)
mined = {f"minecraft:{b}": rnd.randint(10, 9000) for b in ["stone", "deepslate", "dirt", "grass_block", "oak_log", "iron_ore", "diamond_ore", "coal_ore", "netherrack", "sand", "gravel", "andesite"]}
stats = {"stats": {
    "minecraft:custom": {"minecraft:play_time": 20 * 3600 * 87 + 20 * 60 * 14, "minecraft:deaths": 23, "minecraft:mob_kills": 1843, "minecraft:player_kills": 2,
                         "minecraft:walk_one_cm": 412345600, "minecraft:sprint_one_cm": 98765400, "minecraft:fly_one_cm": 51234500, "minecraft:aviate_one_cm": 345678900,
                         "minecraft:jump": 48211, "minecraft:fish_caught": 37, "minecraft:animals_bred": 212, "minecraft:traded_with_villager": 418,
                         "minecraft:time_since_death": 20 * 3600 * 5, "minecraft:damage_dealt": 152340},
    "minecraft:mined": mined,
    "minecraft:killed": {"minecraft:zombie": 512, "minecraft:skeleton": 431, "minecraft:creeper": 210, "minecraft:enderman": 388, "minecraft:spider": 190, "minecraft:ender_dragon": 1},
    "minecraft:killed_by": {"minecraft:creeper": 6, "minecraft:skeleton": 5, "minecraft:zombie": 3, "minecraft:warden": 1},
    "minecraft:crafted": {"minecraft:torch": 2304, "minecraft:stick": 480, "minecraft:oak_planks": 1600, "minecraft:furnace": 8, "minecraft:chest": 64},
    "minecraft:used": {"minecraft:netherite_sword": 4021, "minecraft:diamond_pickaxe": 31002, "minecraft:bread": 220, "minecraft:firework_rocket": 980},
}, "DataVersion": 4440}
json.dump(stats, open(os.path.join(world, "stats", f"{NOTCH}.json"), "w"))
json.dump({"stats": {"minecraft:custom": {"minecraft:play_time": 20 * 60 * 95, "minecraft:deaths": 1}}}, open(os.path.join(world, "stats", f"{JEB}.json"), "w"))
json.dump({"stats": {"minecraft:custom": {"minecraft:play_time": 20 * 60 * 31}}}, open(os.path.join(world, "stats", f"{ALEX}.json"), "w"))

def adv(day):
    return {"criteria": {"x": f"2026-{day} +0000"}, "done": True}
advs = {"minecraft:story/root": adv("03-01 18:00:00"), "minecraft:story/mine_stone": adv("03-01 18:04:12"),
        "minecraft:story/smelt_iron": adv("03-02 20:11:00"), "minecraft:story/enter_the_nether": adv("03-05 21:30:00"),
        "minecraft:nether/root": adv("03-05 21:30:00"), "minecraft:end/kill_dragon": adv("06-12 22:41:09"),
        "minecraft:adventure/kill_a_mob": adv("03-01 19:00:00"), "minecraft:husbandry/tame_an_animal": adv("04-02 10:00:00"),
        "minecraft:story/enchant_item": {"criteria": {}, "done": False},
        "minecraft:recipes/misc/stick": adv("03-01 18:01:00"), "DataVersion": 4440}
json.dump(advs, open(os.path.join(world, "advancements", f"{NOTCH}.json"), "w"))

cache = [{"name": "Notch", "uuid": NOTCH, "expiresOn": "2026-11-01 10:00:00 +0000"},
         {"name": "jeb_", "uuid": JEB, "expiresOn": "2026-11-01 10:00:00 +0000"},
         {"name": "Alex_Builder", "uuid": ALEX, "expiresOn": "2026-11-01 10:00:00 +0000"},
         {"name": "<img src=x onerror=window.__xss2=1>" if os.environ.get("XSS") else "Kai", "uuid": XSS, "expiresOn": "2026-11-01 10:00:00 +0000"}]
json.dump(cache, open(os.path.join(server, "usercache.json"), "w"))
print("ok")
