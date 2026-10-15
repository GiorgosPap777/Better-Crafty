// Checks for the Terminal's command suggestions against the real data files.
// Run from the repository root: node dev/command-data/test_complete.js
const fs = require("fs");
const path = require("path");
const CC = require("../../app/frontend/static/assets/js/shared/command-complete.js");

const DATA = path.join(__dirname, "../../app/frontend/static/assets/data/commands");
const versions = fs.readdirSync(DATA)
  .map(name => (/^java-(.+)\.json$/.exec(name) || [])[1])
  .filter(Boolean);
const trees = {};
function tree(version) {
  if (!trees[version]) {
    trees[version] = new CC.CommandTree(JSON.parse(fs.readFileSync(path.join(DATA, `java-${version}.json`))));
  }
  return trees[version];
}

const PLAYERS = {
  default: [{ name: "Steve", online: true }, { name: "Alex_Builder" }],
  pardon: [{ name: "Griefer99" }],
  whitelist: [{ name: "Kai" }],
};
function players(commandPath) {
  if (commandPath[0] === "pardon") return PLAYERS.pardon;
  if (commandPath[0] === "whitelist" && commandPath[1] === "remove") return PLAYERS.whitelist;
  return PLAYERS.default;
}

let failures = 0;
function check(name, ok, detail) {
  if (ok) return;
  failures++;
  console.log(`FAIL ${name}${detail === undefined ? "" : ": " + JSON.stringify(detail)}`);
}
function texts(version, input) {
  return CC.complete(tree(version), input, players, {}).items.map(item => item.text);
}
function usage(version, input) {
  return CC.complete(tree(version), input, players, {}).usage;
}
const LATEST = versions.slice().sort((a, b) => CC.pickVersion([a, b], a) === a ? 1 : -1).pop();

// Picking the data for a server
const pick = (...hints) => CC.pickVersion(versions, ...hints);
check("paper", pick("Paper 1.21.4") === "1.21.4", pick("Paper 1.21.4"));
check("between", pick("1.21.5") === "1.21.4", pick("1.21.5"));
check("1.21.9", pick("1.21.9") === "1.21.8", pick("1.21.9"));
check("exact", pick("1.21.11") === "1.21.11", pick("1.21.11"));
check("26.2", pick("26.2") === "26.1", pick("26.2"));
check("snapshot", pick("26.4-snapshot-4") === LATEST, pick("26.4-snapshot-4"));
check("too old", pick("1.12.2") === null, pick("1.12.2"));
check("1.14", pick("1.14.4") === "1.16.5", pick("1.14.4"));
check("proxy", pick("Velocity 3.3.0") === null, pick("Velocity 3.3.0"));
check("jar name", pick(false, "paper-1.20.1-196.jar") === "1.20.1", pick(false, "paper-1.20.1-196.jar"));
check("fabric jar", pick("False", "fabric-server-mc.1.21.1-loader.0.16.9-launcher.1.0.1.jar") === "1.21.1");
check("unknown", pick("", "server.jar") === LATEST, pick("", "server.jar"));
check("neoforge", pick(null, "neoforge-21.1.77.jar") === LATEST, pick(null, "neoforge-21.1.77.jar"));

// Tokens
check("tokens", JSON.stringify(CC.tokenize('tp @e[type=cow, limit=1] ~ ~').map(t => t.text))
  === JSON.stringify(["tp", "@e[type=cow, limit=1]", "~", "~"]));
check("quoted", CC.tokenize('tellraw @a {"text":"hi there"} x').length === 4);

// Suggestions
check("command", texts(LATEST, "gi").includes("give"), texts(LATEST, "gi"));
check("slash", texts(LATEST, "/gi").includes("give"));
check("slash start", CC.complete(tree(LATEST), "/give St", players, {}).start === 6);
const give = texts(LATEST, "give ");
check("players first", give[0] === "Steve", give);
check("player selectors", give.includes("@a") && !give.includes("@e"), give);
check("entity selectors", texts(LATEST, "kill ").includes("@e"));
check("@n on 1.21+", texts(LATEST, "kill @").includes("@n") && !texts("1.20.1", "kill @").includes("@n"));
check("items", texts(LATEST, "give Steve dia")[0] === "diamond", texts(LATEST, "give Steve dia").slice(0, 3));
check("item word", texts(LATEST, "give Steve sword").includes("diamond_sword"));
check("count hint", usage(LATEST, "give Steve diamond ") === "<count>", usage(LATEST, "give Steve diamond "));
check("no items after count", texts(LATEST, "give Steve diamond ").length === 0);
check("gamerule new", texts(LATEST, "gamerule keep").includes("keep_inventory"), texts(LATEST, "gamerule keep"));
check("gamerule old", texts("1.21.10", "gamerule keep").includes("keepInventory"), texts("1.21.10", "gamerule keep"));
check("gamerule value", texts("1.21.10", "gamerule keepInventory ").join() === "true,false");
check("coords", texts(LATEST, "tp ").includes("~ ~ ~"), texts(LATEST, "tp "));
check("coords rest", texts(LATEST, "tp Steve 10 ").includes("~ ~"), texts(LATEST, "tp Steve 10 "));
check("tp redirect", texts(LATEST, "tp Steve Al").includes("Alex_Builder"), texts(LATEST, "tp Steve Al"));
check("execute run", texts(LATEST, "execute as @a at @s run gi").includes("give"));
check("execute chain", texts(LATEST, "execute as @a at @s if entity @s[tag=x] run tp ").includes("~ ~ ~"));
check("effects", texts(LATEST, "effect give @a spe").includes("speed"));
check("namespaced", texts(LATEST, "effect give @a minecraft:spe").includes("minecraft:speed"));
check("old effects", texts("1.16.5", "effect give @a spe").includes("speed"), texts("1.16.5", "effect give @a spe"));
check("enchant", texts(LATEST, "enchant @p sharp").includes("sharpness"));
check("summon", texts(LATEST, "summon zom")[0] === "zombie", texts(LATEST, "summon zom"));
check("structure", texts(LATEST, "locate structure vil").some(t => t.startsWith("village")));
check("weather", texts(LATEST, "weather ").join() === "clear,rain,thunder", texts(LATEST, "weather "));
check("gamemode", texts(LATEST, "gamemode c").join() === "creative");
check("pardon", texts(LATEST, "pardon ").includes("Griefer99") && !texts(LATEST, "pardon ").includes("Steve"));
check("whitelist remove", texts(LATEST, "whitelist remove ").join() === "Kai", texts(LATEST, "whitelist remove "));
check("pardon names only", !texts(LATEST, "pardon ").includes("@a"));
check("ban selectors", texts(LATEST, "ban ").includes("@a"));
check("kick reason", usage(LATEST, "kick Steve ") === "<reason>", usage(LATEST, "kick Steve "));
check("say", usage(LATEST, "say hello wor") === "<message>", usage(LATEST, "say hello wor"));
check("unknown command", texts(LATEST, "essentials ").length === 0 && !usage(LATEST, "essentials "));
check("complete word", texts(LATEST, "give").length === 0, texts(LATEST, "give"));
check("more after literal", CC.complete(tree(LATEST), "gi", players, {}).items.find(i => i.text === "give").more);
check("not more at end", !CC.complete(tree(LATEST), "give Steve diamond 6", players, {}).items.length);

// Every data file loads and offers its commands
for (const version of versions) {
  const list = texts(version, "g");
  check(`data ${version}`, list.includes("give") && list.includes("gamemode"), list);
}

console.log(failures ? `${failures} failed` : "all passed");
process.exitCode = failures ? 1 : 0;
