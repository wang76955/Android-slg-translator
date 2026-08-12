const ws = "ws://127.0.0.1:9222/devtools/page/F2705A86B1E38CD0171763F76F0F5F4B";
const expression = `(() => {
  const records = globalThis.__slgCoverageRecords || [];
  const approved = globalThis.__slgValidatorApprovedTranslations instanceof Map
    ? globalThis.__slgValidatorApprovedTranslations
    : new Map(Object.entries(globalThis.__slgValidatorApprovedTranslations || {}));
  const groups = new Map();
  const placeholder = /\{\{|\[\[|\{[^}]*\}|\[[^]]*\]|%\d*\$?[sdif]|\$[A-Za-z_][A-Za-z0-9_]*/;
  for (const record of records) {
    const old = String(record?.text ?? "");
    if (!old.trim()) continue;
    const group = groups.get(old) || { old, occurrences: 0, paths: new Set() };
    group.occurrences += 1;
    group.paths.add(String(record?.sourcePath ?? ""));
    groups.set(old, group);
  }
  const missing = [...groups.values()].filter(group => !String(approved.get(group.old) || "").trim());
  const byCategory = {};
  const otherSamples = [];
  for (const group of missing) {
    let category = "other";
    if (placeholder.test(group.old)) category = "placeholder";
    else if (!/[A-Za-z]/.test(group.old)) category = "no_latin_letters";
    else if (!/[A-Za-z]{2,}/.test(group.old)) category = "single_letter_tokens";
    else if (group.old.length <= 8) category = "short_latin";
    else if (group.old === group.old.toUpperCase() && /[A-Z]/.test(group.old)) category = "all_caps";
    else if (/^[A-Za-z0-9 .,!?'"-]+$/.test(group.old)) category = "plain_ascii";
    byCategory[category] = byCategory[category] || { unique: 0, occurrences: 0 };
    byCategory[category].unique += 1;
    byCategory[category].occurrences += group.occurrences;
    if (category !== "placeholder" && otherSamples.length < 80) otherSamples.push({
      old: group.old, occurrences: group.occurrences, category,
      sourcePath: [...group.paths][0] || ""
    });
  }
  return JSON.stringify({ records: records.length, unique: groups.size, approved: approved.size,
    missing: missing.length, byCategory,
    samples: missing.slice(0, 40).map(group => ({ old: group.old, occurrences: group.occurrences,
      sourcePath: [...group.paths][0] || "" })), otherSamples });
})()`;
const socket = new WebSocket(ws);
const timer = setTimeout(() => process.exit(3), 30000);
socket.addEventListener("open", () => socket.send(JSON.stringify({
  id: 1, method: "Runtime.evaluate", params: { expression, awaitPromise: true, returnByValue: true }
})));
socket.addEventListener("message", event => {
  const message = JSON.parse(event.data);
  if (message.id !== 1) return;
  clearTimeout(timer);
  if (message.error || message.result?.exceptionDetails) {
    console.error(JSON.stringify(message.error || message.result.exceptionDetails));
    process.exitCode = 1;
  } else {
    console.log(message.result?.result?.value ?? "null");
  }
  socket.close();
});
