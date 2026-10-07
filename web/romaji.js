/** Romaji → hiragana. Keep in sync with proba/kana.py */
(function (root) {
  const MORA = [
    ["kya", "きゃ"],
    ["kyu", "きゅ"],
    ["kyo", "きょ"],
    ["gya", "ぎゃ"],
    ["gyu", "ぎゅ"],
    ["gyo", "ぎょ"],
    ["sha", "しゃ"],
    ["shu", "しゅ"],
    ["sho", "しょ"],
    ["sya", "しゃ"],
    ["syu", "しゅ"],
    ["syo", "しょ"],
    ["ja", "じゃ"],
    ["ju", "じゅ"],
    ["jo", "じょ"],
    ["jya", "じゃ"],
    ["jyu", "じゅ"],
    ["jyo", "じょ"],
    ["zya", "じゃ"],
    ["zyu", "じゅ"],
    ["zyo", "じょ"],
    ["cha", "ちゃ"],
    ["chu", "ちゅ"],
    ["cho", "ちょ"],
    ["tya", "ちゃ"],
    ["tyu", "ちゅ"],
    ["tyo", "ちょ"],
    ["nya", "にゃ"],
    ["nyu", "にゅ"],
    ["nyo", "にょ"],
    ["hya", "ひゃ"],
    ["hyu", "ひゅ"],
    ["hyo", "ひょ"],
    ["bya", "びゃ"],
    ["byu", "びゅ"],
    ["byo", "びょ"],
    ["pya", "ぴゃ"],
    ["pyu", "ぴゅ"],
    ["pyo", "ぴょ"],
    ["mya", "みゃ"],
    ["myu", "みゅ"],
    ["myo", "みょ"],
    ["rya", "りゃ"],
    ["ryu", "りゅ"],
    ["ryo", "りょ"],
    ["shi", "し"],
    ["chi", "ち"],
    ["tsu", "つ"],
    ["xtu", "っ"],
    ["ltu", "っ"],
    ["xtsu", "っ"],
    ["ltsu", "っ"],
    ["xya", "ゃ"],
    ["xyu", "ゅ"],
    ["xyo", "ょ"],
    ["lya", "ゃ"],
    ["lyu", "ゅ"],
    ["lyo", "ょ"],
    ["xa", "ぁ"],
    ["xi", "ぃ"],
    ["xu", "ぅ"],
    ["xe", "ぇ"],
    ["xo", "ぉ"],
    ["la", "ぁ"],
    ["li", "ぃ"],
    ["lu", "ぅ"],
    ["le", "ぇ"],
    ["lo", "ぉ"],
    ["wu", "う"],
    ["wha", "うぁ"],
    ["whi", "うぃ"],
    ["whe", "うぇ"],
    ["who", "うぉ"],
    ["tsi", "つぃ"],
    ["tse", "つぇ"],
    ["tso", "つぉ"],
    ["thi", "てぃ"],
    ["dhi", "でぃ"],
    ["twu", "とぅ"],
    ["dwu", "どぅ"],
    ["fu", "ふ"],
    ["hu", "ふ"],
    ["ji", "じ"],
    ["zi", "じ"],
    ["di", "ぢ"],
    ["du", "づ"],
    ["dzu", "づ"],
    ["si", "し"],
    ["ti", "ち"],
    ["tu", "つ"],
    ["ka", "か"],
    ["ki", "き"],
    ["ku", "く"],
    ["ke", "け"],
    ["ko", "こ"],
    ["ga", "が"],
    ["gi", "ぎ"],
    ["gu", "ぐ"],
    ["ge", "げ"],
    ["go", "ご"],
    ["sa", "さ"],
    ["su", "す"],
    ["se", "せ"],
    ["so", "そ"],
    ["za", "ざ"],
    ["zu", "ず"],
    ["ze", "ぜ"],
    ["zo", "ぞ"],
    ["ta", "た"],
    ["te", "て"],
    ["to", "と"],
    ["da", "だ"],
    ["de", "で"],
    ["do", "ど"],
    ["na", "な"],
    ["ni", "に"],
    ["nu", "ぬ"],
    ["ne", "ね"],
    ["no", "の"],
    ["ha", "は"],
    ["hi", "ひ"],
    ["he", "へ"],
    ["ho", "ほ"],
    ["ba", "ば"],
    ["bi", "び"],
    ["bu", "ぶ"],
    ["be", "べ"],
    ["bo", "ぼ"],
    ["pa", "ぱ"],
    ["pi", "ぴ"],
    ["pu", "ぷ"],
    ["pe", "ぺ"],
    ["po", "ぽ"],
    ["ma", "ま"],
    ["mi", "み"],
    ["mu", "む"],
    ["me", "め"],
    ["mo", "も"],
    ["ya", "や"],
    ["yu", "ゆ"],
    ["yo", "よ"],
    ["ra", "ら"],
    ["ri", "り"],
    ["ru", "る"],
    ["re", "れ"],
    ["ro", "ろ"],
    ["wa", "わ"],
    ["wo", "を"],
    ["nn", "ん"],
    ["n'", "ん"],
    ["va", "ゔぁ"],
    ["vi", "ゔぃ"],
    ["vu", "ゔ"],
    ["ve", "ゔぇ"],
    ["vo", "ゔぉ"],
    ["fa", "ふぁ"],
    ["fi", "ふぃ"],
    ["fe", "ふぇ"],
    ["fo", "ふぉ"],
    ["a", "あ"],
    ["i", "い"],
    ["u", "う"],
    ["e", "え"],
    ["o", "お"],
    ["-", "ー"],
  ];
  const SOKUON = "bcdfghjklmpqrstvwxyz".replace("n", "");

  function matchMora(chunk) {
    const low = chunk.toLowerCase();
    for (const [roman, kana] of MORA) {
      if (low.startsWith(roman)) return [kana, roman.length];
    }
    return null;
  }

  function fold(text) {
    return text.normalize("NFKC");
  }

  function romajiToHiragana(text, commit) {
    const s = fold(String(text || "")).replace(/[A-Z]/g, (c) => c.toLowerCase());
    let i = 0;
    let out = "";
    while (i < s.length) {
      const ch = s[i];
      if (ch === "n") {
        const nxt = s[i + 1] || "";
        if (nxt === "n") {
          const rest = s.slice(i + 1);
          if (matchMora(rest)) {
            out += "ん";
            i += 1;
            continue;
          }
          out += "ん";
          i += 2;
          continue;
        }
        if (nxt === "'") {
          out += "ん";
          i += 2;
          continue;
        }
        if (nxt === "y" && "auo".includes(s[i + 2] || "")) {
          const hit = matchMora(s.slice(i));
          if (hit) {
            out += hit[0];
            i += hit[1];
            continue;
          }
        }
        if (!nxt) {
          out += commit ? "ん" : "n";
          i += 1;
          continue;
        }
        if (!"aiueoy".includes(nxt)) {
          out += "ん";
          i += 1;
          continue;
        }
        const hitN = matchMora(s.slice(i));
        if (hitN) {
          out += hitN[0];
          i += hitN[1];
          continue;
        }
      }
      if (SOKUON.includes(ch) && s[i + 1] === ch && matchMora(s.slice(i + 1))) {
        out += "っ";
        i += 1;
        continue;
      }
      const hit = matchMora(s.slice(i));
      if (hit) {
        out += hit[0];
        i += hit[1];
        continue;
      }
      out += s[i];
      i += 1;
    }
    return out;
  }

  function bind(input) {
    if (!input || input.dataset.romajiBound) return;
    input.dataset.romajiBound = "1";
    input.addEventListener("input", (ev) => {
      if (ev.isComposing) return;
      if (input.readOnly) return;
      const atEnd = input.selectionStart === input.value.length;
      const next = romajiToHiragana(input.value, false);
      if (next !== input.value) {
        input.value = next;
        if (atEnd) input.setSelectionRange(next.length, next.length);
      }
    });
  }

  root.ProbaRomaji = { romajiToHiragana, bind };
})(window);
