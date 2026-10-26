#!/usr/bin/env node
/**
 * cdp_send.mjs — send raw CDP commands to one page target.
 *
 * playwright-rs covers the common verbs, but not everything an app needs:
 * `press` has no modifier keys, and `type` writes `.value` instead of typing.
 * Anything that needs Ctrl+S, Input.insertText, or a domain call playwright-rs
 * does not wrap goes here.
 *
 *   node scripts/cdp_send.mjs --port 9224 --list
 *   node scripts/cdp_send.mjs --port 9224 --file commands.json
 *   node scripts/cdp_send.mjs --port 9224 \
 *     --method Runtime.evaluate --params '{"expression":"document.title"}'
 *
 * A commands file is a JSON array of { "method": …, "params": { … } }; each
 * result prints as one JSON object on its own line. Exit code 1 means a command
 * returned a protocol error.
 */

import { readFileSync } from "node:fs";

function parseArgs(argv) {
  const opts = { port: 9222, target: null, method: null, params: null, file: null, list: false, timeout: 15000 };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    switch (arg) {
      case "--port": opts.port = Number(argv[++i]); break;
      case "--target": opts.target = argv[++i]; break;
      case "--method": opts.method = argv[++i]; break;
      case "--params": opts.params = argv[++i]; break;
      case "--file": opts.file = argv[++i]; break;
      case "--timeout": opts.timeout = Number(argv[++i]); break;
      case "--list": opts.list = true; break;
      case "-h":
      case "--help": opts.help = true; break;
      default: throw new Error(`unknown argument: ${arg}`);
    }
  }
  return opts;
}

async function pageTargets(port) {
  const res = await fetch(`http://127.0.0.1:${port}/json/list`);
  if (!res.ok) throw new Error(`CDP endpoint on :${port} returned ${res.status}`);
  const targets = await res.json();
  return targets.filter((t) => t.type === "page");
}

function chooseTarget(targets, wanted) {
  if (!targets.length) throw new Error("no page targets on that endpoint");
  if (!wanted) return targets[0];
  const exact = targets.find((t) => t.id === wanted);
  if (exact) return exact;
  const byUrl = targets.find((t) => t.url.includes(wanted));
  if (byUrl) return byUrl;
  throw new Error(`no page target matching ${wanted}`);
}

async function send(wsUrl, commands, timeout) {
  const ws = new WebSocket(wsUrl);
  const pending = new Map();
  const results = [];
  let nextId = 1;

  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("WebSocket open timed out")), timeout);
    ws.onopen = () => { clearTimeout(timer); resolve(); };
    ws.onerror = (event) => { clearTimeout(timer); reject(new Error(`WebSocket error: ${event.message || "unknown"}`)); };
  });

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (!msg.id || !pending.has(msg.id)) return;
    const { resolve } = pending.get(msg.id);
    pending.delete(msg.id);
    resolve(msg);
  };

  try {
    for (const command of commands) {
      const id = nextId++;
      const reply = await new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error(`${command.method} timed out after ${timeout}ms`)), timeout);
        pending.set(id, {
          resolve: (msg) => { clearTimeout(timer); resolve(msg); },
        });
        ws.send(JSON.stringify({ id, method: command.method, params: command.params || {} }));
      });
      if (reply.error) {
        results.push({ method: command.method, error: reply.error });
        break;
      }
      results.push({ method: command.method, result: reply.result });
    }
  } finally {
    ws.close();
  }
  return results;
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (opts.help) {
    console.log("usage: cdp_send.mjs --port N [--target ID|URL] (--list | --method M [--params JSON] | --file FILE)");
    return 0;
  }

  const targets = await pageTargets(opts.port);
  if (opts.list) {
    for (const t of targets) console.log(JSON.stringify({ id: t.id, title: t.title, url: t.url }));
    return 0;
  }

  const target = chooseTarget(targets, opts.target);
  let commands;
  if (opts.file) {
    commands = JSON.parse(readFileSync(opts.file, "utf8"));
  } else if (opts.method) {
    commands = [{ method: opts.method, params: opts.params ? JSON.parse(opts.params) : {} }];
  } else {
    throw new Error("give --list, --method, or --file");
  }

  const results = await send(target.webSocketDebuggerUrl, commands, opts.timeout);
  for (const entry of results) console.log(JSON.stringify(entry));
  return results.some((entry) => entry.error) ? 1 : 0;
}

main()
  .then((code) => process.exit(code))
  .catch((err) => {
    console.error(`cdp_send: ${err.message}`);
    process.exit(2);
  });
