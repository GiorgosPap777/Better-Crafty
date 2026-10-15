/*
 * Command suggestions for the server console, like the game's chat box.
 *
 * The data files (static/assets/data/commands/java-<version>.json) come from
 * the game's own command tree; dev/command-data/generate.py makes them. A
 * file holds the tree as a node list, where a node is
 * [name, flags (1 = argument, 2 = can run here), child ids, parser,
 *  parser properties, redirect path], plus ID lists (items, blocks...).
 */
(function (global) {
  "use strict";

  // ---- Which data file fits a server --------------------------------------

  // "Paper 1.21.4", "1.20.1", "26.3", "paper-1.21.4-232.jar". Versions are
  // 1.x up to 1.21.11, then year based from 26.1. The 1.x minor number stops
  // at 21, so a mod loader's own "21.1.77" is not read as 1.77.
  const VERSION = /(?:^|[^0-9])(1\.(?:1?\d|2[01])(?:\.\d{1,2})?|(?:2[6-9]|[3-9]\d)\.\d{1,2}(?:\.\d{1,2})?)(?![0-9])/;
  // Proxies have their own commands
  const PROXY = /velocity|bungee|waterfall|travertine/i;

  function parseVersion(text) {
    const match = VERSION.exec(String(text || ""));
    return match ? match[1].split(".").map(Number) : null;
  }

  function compareVersions(a, b) {
    for (let i = 0; i < Math.max(a.length, b.length); i++) {
      const diff = (a[i] || 0) - (b[i] || 0);
      if (diff) return diff;
    }
    return 0;
  }

  // available: version strings with a data file. Returns one of them, or
  // null when suggestions would be wrong (proxies, before 1.13).
  function pickVersion(available, ...hints) {
    const sorted = available.slice().sort((a, b) => compareVersions(parseVersion(a), parseVersion(b)));
    if (!sorted.length) return null;
    for (const hint of hints) {
      if (!hint || hint === "False") continue;
      if (PROXY.test(hint)) return null;
      const version = parseVersion(hint);
      if (!version) continue;
      // 1.12 and older had a different command system
      if (compareVersions(version, [1, 13]) < 0) return null;
      let best = sorted[0];
      for (const candidate of sorted) {
        if (compareVersions(parseVersion(candidate), version) <= 0) best = candidate;
      }
      return best;
    }
    return sorted[sorted.length - 1];
  }

  // ---- The command tree ---------------------------------------------------

  function CommandTree(data) {
    this.version = data.version;
    this.ids = data.ids || {};
    this.nodes = data.nodes.map(raw => ({
      name: raw[0],
      arg: Boolean(raw[1] & 1),
      exec: Boolean(raw[1] & 2),
      childIds: raw[2] || [],
      parser: raw[3] || null,
      props: raw[4] || {},
      redirect: raw[5] || null,
    }));
    for (const node of this.nodes) {
      node.children = node.childIds.map(id => this.nodes[id]);
    }
    this.root = this.nodes[data.root];
    // @n (nearest entity) arrived in 1.21
    this.hasNearest = compareVersions(parseVersion(this.version) || [0], [1, 21]) >= 0;
  }

  CommandTree.prototype.resolve = function (path) {
    let node = this.root;
    for (const name of path) {
      node = node.children.find(child => !child.arg && child.name === name);
      if (!node) return null;
    }
    return node;
  };

  // A redirect ("tp" to "teleport", "execute ... run" to the root) carries on
  // with the children of its target
  CommandTree.prototype.childrenOf = function (node) {
    if (node.redirect) {
      const target = this.resolve(node.redirect);
      return target ? target.children : [];
    }
    return node.children;
  };

  // ---- Reading the input ----------------------------------------------------

  // Split on spaces, but not inside [], {}, () or quotes: selectors, NBT and
  // text components may contain spaces.
  function tokenize(text) {
    const tokens = [];
    let start = 0;
    let depth = 0;
    let quote = null;
    for (let i = 0; i < text.length; i++) {
      const char = text[i];
      if (quote) {
        if (char === "\\") i++;
        else if (char === quote) quote = null;
      } else if (char === '"' || char === "'") {
        quote = char;
      } else if ("[{(".includes(char)) {
        depth++;
      } else if ("]})".includes(char)) {
        depth = Math.max(0, depth - 1);
      } else if (char === " " && depth === 0) {
        tokens.push({ text: text.slice(start, i), start: start });
        start = i + 1;
      }
    }
    tokens.push({ text: text.slice(start), start: start });
    return tokens;
  }

  const COORDINATE_SPAN = { vec3: 3, block_pos: 3, vec2: 2, column_pos: 2, rotation: 2 };

  function tokenSpan(node) {
    if (node.parser === "message") return Infinity;
    if (node.parser === "brigadier:string" && node.props.type === "greedy") return Infinity;
    return COORDINATE_SPAN[node.parser] || 1;
  }

  const INTEGER = /^-?\d+$/;
  const NUMBER = /^-?(\d+\.?\d*|\.\d+)$/;
  const COORDINATE = /^([~^](-?(\d+\.?\d*|\.\d+))?|-?(\d+\.?\d*|\.\d+))$/;
  const RESOURCE = /^#?([a-z0-9_.-]+:)?[a-z0-9_./-]+([[{(].*)?$/;
  const TIME = /^-?(\d+\.?\d*|\.\d+)[dst]?$/;
  const TARGET = /^(@[a-z](\[.*\])?|[^\s@{}[\]"]+)$/;
  const GAMEMODES = ["survival", "creative", "adventure", "spectator"];

  // A loose check of a finished token, to rule out branches that clearly do
  // not fit (so "tp 10 64 10" is read as coordinates, not as a player)
  function accepts(node, token) {
    if (!token) return false;
    switch (node.parser) {
      case "brigadier:integer":
      case "brigadier:long":
        return INTEGER.test(token);
      case "brigadier:float":
      case "brigadier:double":
        return NUMBER.test(token);
      case "brigadier:bool":
        return token === "true" || token === "false";
      case "vec3": case "block_pos": case "vec2": case "column_pos": case "rotation":
        return COORDINATE.test(token);
      case "entity": case "game_profile": case "score_holder":
        return TARGET.test(token);
      case "gamemode":
        return GAMEMODES.includes(token);
      case "time":
        return TIME.test(token);
      case "item_stack": case "item_predicate": case "block_state": case "block_predicate":
      case "resource": case "resource_key": case "resource_or_tag": case "resource_or_tag_key":
      case "resource_location": case "dimension": case "entity_summon": case "mob_effect":
      case "item_enchantment": case "function":
        return RESOURCE.test(token);
      default:
        return true;
    }
  }

  // ---- Suggestions ------------------------------------------------------

  const PARSER_IDS = {
    item_stack: "item", item_predicate: "item", block_state: "block", block_predicate: "block",
    particle: "particle_type", entity_summon: "entity_type", mob_effect: "mob_effect",
    item_enchantment: "enchantment",
  };
  const COLORS = ["black", "dark_blue", "dark_green", "dark_aqua", "dark_red", "dark_purple", "gold",
    "gray", "dark_gray", "blue", "green", "aqua", "red", "light_purple", "yellow", "white"];
  const FIXED = {
    gamemode: GAMEMODES,
    "brigadier:bool": ["true", "false"],
    dimension: ["overworld", "the_nether", "the_end"],
    entity_anchor: ["eyes", "feet"],
    heightmap: ["motion_blocking", "motion_blocking_no_leaves", "ocean_floor", "ocean_floor_wg",
      "world_surface", "world_surface_wg"],
    template_mirror: ["none", "front_back", "left_right"],
    template_rotation: ["none", "clockwise_90", "180", "counterclockwise_90"],
    operation: ["=", "+=", "-=", "*=", "/=", "%=", "<", ">", "><"],
    swizzle: ["x", "y", "z", "xy", "xz", "yz", "xyz"],
    color: COLORS.concat(["reset"]),
    team_color: COLORS.concat(["reset"]),
    scoreboard_slot: ["list", "sidebar", "below_name", "belowName"].concat(COLORS.map(c => "sidebar.team." + c)),
    objective_criteria: ["dummy", "trigger", "deathCount", "playerKillCount", "totalKillCount", "health",
      "xp", "level", "food", "air", "armor"],
    item_slot: ["weapon.mainhand", "weapon.offhand", "armor.head", "armor.chest", "armor.legs", "armor.feet",
      "armor.body", "saddle", "container.0", "hotbar.0", "inventory.0", "enderchest.0", "horse.saddle",
      "horse.chest", "player.cursor"],
  };

  // How well a candidate fits what was typed: 1 = starts with it, 2 = a
  // later word starts with it ("sword" finds diamond_sword), 0 = no match
  function matchRank(candidate, typed) {
    if (!typed) return 1;
    const text = candidate.toLowerCase();
    const want = typed.toLowerCase();
    if (text.startsWith(want)) return 1;
    for (let i = 0; i < text.length - 1; i++) {
      if ("_./:-".includes(text[i]) && text.startsWith(want, i + 1)) return 2;
    }
    return 0;
  }

  // These commands suggest only names from one of the server's lists (banned
  // players, operators...) in the game, no selectors
  const NAMES_ONLY = /^(?:pardon|op|deop|whitelist (?:add|remove))$/;

  function selectorsFor(tree, node, text) {
    const players = node.parser === "game_profile" || node.props.type === "players";
    const list = [
      { text: "@a", detail: text.selAll },
      { text: "@p", detail: text.selNearest },
      { text: "@r", detail: text.selRandom },
      { text: "@s", detail: text.selSelf },
    ];
    if (!players) {
      list.push({ text: "@e", detail: text.selEntities });
      if (tree.hasNearest) list.push({ text: "@n", detail: text.selNearestEntity });
    }
    if (node.parser === "score_holder") list.push({ text: "*", detail: text.selEveryScore });
    return list;
  }

  function argumentSuggestions(tree, node, k, typed, players, path, text) {
    const parser = node.parser;
    const span = COORDINATE_SPAN[parser];
    if (span) {
      if (typed && typed !== "~" && typed !== "^") return [];
      const left = span - k;
      const options = [];
      if (typed !== "^") options.push(Array(left).fill("~").join(" "));
      if (span === 3 && typed !== "~" && (k === 0 || typed === "^")) options.push(Array(left).fill("^").join(" "));
      return options.map(option => ({ text: option, detail: option[0] === "~" ? text.relative : text.local }));
    }
    if (parser === "entity" || parser === "game_profile" || parser === "score_holder") {
      if (typed.includes("[")) return [];
      const names = players(path).map(p => ({ text: p.name, detail: p.online ? text.online : "" }));
      if (NAMES_ONLY.test(path.slice(0, 2).join(" "))) return names;
      return names.concat(selectorsFor(tree, node, text));
    }
    if (FIXED[parser]) return FIXED[parser].map(value => ({ text: value }));
    const list = tree.ids[node.props.registry || PARSER_IDS[parser]];
    if (list) {
      if (/[[{(#]/.test(typed)) return [];
      const namespaced = typed.startsWith("minecraft:");
      return list.map(id => ({ text: namespaced ? "minecraft:" + id : id }));
    }
    return [];
  }

  function label(node) {
    return node.arg ? `<${node.name}>` : node.name;
  }

  // What may follow a node, the way the game shows it: "<item> [<count>]"
  function usage(tree, node, depth) {
    const children = tree.childrenOf(node);
    if (!children.length || depth > 6) return "";
    let part;
    if (children.length === 1) {
      const rest = node.redirect ? "" : usage(tree, children[0], depth + 1);
      part = label(children[0]) + (rest ? " " + rest : "");
    } else {
      const names = children.map(label);
      part = names.join("|");
      if (part.length > 60) part = names.slice(0, 4).join("|") + "|…";
      part = `(${part})`;
    }
    return node.exec ? `[${part}]` : part;
  }

  // Suggestions for the text before the cursor. players(path) lists
  // {name, online} for the command being typed (e.g. banned players for
  // "pardon"). Returns {start, typed, items: [{text, detail, more}], usage}.
  function complete(tree, input, players, text) {
    text = text || {};
    const offset = input.startsWith("/") ? 1 : 0;
    const tokens = tokenize(input.slice(offset));
    const last = tokens.length - 1;
    const typed = tokens[last].text;
    const start = offset + tokens[last].start;

    let states = [{ node: tree.root, index: 0, path: [] }];
    const found = [];
    const usages = [];
    for (let guard = 0; states.length && guard < 200; guard++) {
      const next = [];
      for (const state of states) {
        const children = tree.childrenOf(state.node);
        if (state.index === last && state.node !== tree.root) {
          const hint = usage(tree, state.node, 0).replace(/^\[(.*)\]$/, "$1");
          if (hint) usages.push(hint);
        }
        for (const child of children) {
          if (!child.arg) {
            if (state.index === last) found.push({ node: child, k: 0, path: state.path });
            else if (tokens[state.index].text === child.name) {
              next.push({ node: child, index: state.index + 1, path: state.path.concat(child.name) });
            }
            continue;
          }
          const span = tokenSpan(child);
          if (state.index + span - 1 >= last) {
            found.push({ node: child, k: last - state.index, path: state.path });
            continue;
          }
          let fits = true;
          for (let j = 0; j < span && fits; j++) fits = accepts(child, tokens[state.index + j].text);
          if (fits) next.push({ node: child, index: state.index + span, path: state.path.concat(child.name) });
        }
      }
      states = next.slice(0, 300);
    }

    const seen = new Set();
    const items = [];
    const quiet = [];
    for (const place of found) {
      const more = tree.childrenOf(place.node).length > 0 && tokenSpan(place.node) !== Infinity;
      const options = place.node.arg
        ? argumentSuggestions(tree, place.node, place.k, typed, players, place.path, text)
        : [{ text: place.node.name }];
      let matched = false;
      for (const option of options) {
        // Multi-word options ("~ ~ ~") are matched on their first word
        const rank = matchRank(option.text, typed);
        if (!rank) continue;
        matched = true;
        if (seen.has(option.text)) continue;
        seen.add(option.text);
        items.push({ text: option.text, detail: option.detail || "", more: more, rank: rank });
      }
      if (place.node.arg && !matched) quiet.push(place.node);
    }
    items.sort((a, b) => a.rank - b.rank);

    // The grey hint when there is nothing to pick from
    let hint = null;
    if (quiet.length) {
      hint = Array.from(new Set(quiet.map(node => {
        const rest = usage(tree, node, 0);
        return label(node) + (rest ? " " + rest : "");
      }))).join("  |  ");
    } else if (!items.length && usages.length && !typed) {
      hint = Array.from(new Set(usages)).join("  |  ");
    }
    // Nothing left to suggest once the word is complete
    if (items.length === 1 && items[0].text === typed) items.length = 0;
    return { start: start, typed: typed, items: items, usage: hint };
  }

  // ---- The suggestion box -------------------------------------------------

  const MAX_ITEMS = 100;

  // options: {versions, baseUrl, version, executable, players(path), text}
  function attach(input, options) {
    const box = document.createElement("div");
    box.className = "cmd-suggest";
    box.id = input.id + "_suggest";
    box.hidden = true;
    const list = document.createElement("div");
    list.className = "cmd-suggest-list";
    list.setAttribute("role", "listbox");
    list.id = input.id + "_suggest_list";
    const hintEl = document.createElement("div");
    hintEl.className = "cmd-suggest-usage";
    box.append(list, hintEl);
    input.parentNode.appendChild(box);
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-controls", list.id);
    input.setAttribute("aria-expanded", "false");

    const cache = {};
    let tree = null;
    let loadingVersion = null;
    let result = null;
    let selected = 0;
    let chosen = false; // picked with the arrow keys
    let dismissed = false;
    const text = options.text || {};

    async function useVersion(...hints) {
      const version = pickVersion(options.versions || [], ...hints);
      if (!version || version === loadingVersion) return;
      loadingVersion = version;
      try {
        if (!cache[version]) {
          const res = await fetch(`${options.baseUrl}java-${version}.json`);
          if (!res.ok) throw new Error(res.status);
          cache[version] = new CommandTree(await res.json());
        }
        if (loadingVersion !== version) return;
        tree = cache[version];
        if (options.onVersion) options.onVersion(version);
        if (document.activeElement === input) update();
      } catch (e) {
        console.warn("Could not load command suggestions", e);
        loadingVersion = null;
      }
    }

    function close() {
      box.hidden = true;
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
    }

    // Line the box up under the word being completed, as the game does
    function place(start) {
      const style = getComputedStyle(input);
      const canvas = place.canvas || (place.canvas = document.createElement("canvas"));
      const ctx = canvas.getContext("2d");
      ctx.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
      const x = parseFloat(style.paddingLeft) + ctx.measureText(input.value.slice(0, start)).width - input.scrollLeft;
      const room = input.parentNode.clientWidth;
      box.style.left = Math.max(0, Math.min(x - 8, room - box.offsetWidth)) + "px";
    }

    function render() {
      list.textContent = "";
      const items = result ? result.items.slice(0, MAX_ITEMS) : [];
      const hint = result && !items.length ? result.usage : null;
      if (dismissed || (!items.length && !hint)) {
        close();
        return;
      }
      items.forEach((item, i) => {
        const option = document.createElement("div");
        option.className = "cmd-option" + (i === selected ? " active" : "");
        option.id = `${list.id}_${i}`;
        option.setAttribute("role", "option");
        option.setAttribute("aria-selected", i === selected ? "true" : "false");
        const main = document.createElement("span");
        main.className = "cmd-option-text";
        const typedLength = result.typed && item.rank === 1 ? result.typed.length : 0;
        const strong = document.createElement("strong");
        strong.textContent = item.text.slice(0, typedLength);
        main.append(strong, document.createTextNode(item.text.slice(typedLength)));
        option.appendChild(main);
        if (item.detail) {
          const detail = document.createElement("span");
          detail.className = "cmd-option-detail";
          detail.textContent = item.detail;
          option.appendChild(detail);
        }
        option.addEventListener("mousedown", e => e.preventDefault());
        option.addEventListener("click", () => accept(i));
        list.appendChild(option);
      });
      list.hidden = !items.length;
      hintEl.hidden = !hint;
      hintEl.textContent = hint || "";
      box.hidden = false;
      input.setAttribute("aria-expanded", items.length ? "true" : "false");
      if (items.length) {
        input.setAttribute("aria-activedescendant", `${list.id}_${selected}`);
        const active = list.children[selected];
        if (active) active.scrollIntoView({ block: "nearest" });
      } else {
        input.removeAttribute("aria-activedescendant");
      }
      place(result.start);
    }

    function update() {
      if (!tree) return;
      const cursor = input.selectionStart ?? input.value.length;
      result = input.value.trim() ? complete(tree, input.value.slice(0, cursor), options.players, text) : null;
      selected = 0;
      chosen = false;
      render();
    }

    function accept(index) {
      const item = result && result.items[index];
      if (!item) return;
      const value = input.value;
      const cursor = input.selectionStart ?? value.length;
      // Replace the whole word under the cursor, not only the part before it
      let end = cursor;
      while (end < value.length && value[end] !== " ") end++;
      const after = value.slice(end);
      const space = item.more && !after.startsWith(" ") ? " " : "";
      input.value = value.slice(0, result.start) + item.text + space + after;
      const caret = result.start + item.text.length + space.length;
      input.setSelectionRange(caret, caret);
      dismissed = false;
      update();
    }

    function move(step) {
      const count = Math.min(result.items.length, MAX_ITEMS);
      selected = (selected + step + count) % count;
      chosen = true;
      render();
    }

    input.addEventListener("input", () => {
      dismissed = false;
      update();
    });
    input.addEventListener("click", update);
    input.addEventListener("keyup", e => {
      if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) update();
    });
    input.addEventListener("focus", update);
    input.addEventListener("blur", close);

    const open = () => !box.hidden && result && result.items.length > 0 && !list.hidden;

    // Returns true when the key was used for the suggestions; the page's
    // own handler (command history) gets the rest
    function handleKey(e) {
      if (!tree) return false;
      if (e.key === "Tab" && !e.altKey && !e.ctrlKey && !e.metaKey) {
        if (!open()) {
          if (dismissed && result && result.items.length) {
            dismissed = false;
            render();
            e.preventDefault();
            return true;
          }
          return false;
        }
        e.preventDefault();
        if (e.shiftKey) move(-1);
        else accept(selected);
        return true;
      }
      if (!open()) return false;
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        move(e.key === "ArrowDown" ? 1 : -1);
        return true;
      }
      if (e.key === "Enter" && chosen) {
        e.preventDefault();
        accept(selected);
        return true;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        dismissed = true;
        close();
        return true;
      }
      return false;
    }

    useVersion(options.version, options.executable);
    return {
      handleKey: handleKey,
      close: close,
      refresh: update,
      setVersion: version => useVersion(version, options.executable),
    };
  }

  global.CommandComplete = {
    attach: attach,
    complete: complete,
    pickVersion: pickVersion,
    tokenize: tokenize,
    CommandTree: CommandTree,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = global.CommandComplete;
})(typeof window !== "undefined" ? window : globalThis);
