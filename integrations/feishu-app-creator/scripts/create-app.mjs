#!/usr/bin/env node
/**
 * Feishu one-click custom app creation script.
 *
 * Uses @larksuiteoapi/node-sdk registerApp (OAuth 2.0 Device Authorization Grant,
 * RFC 8628) to generate an authorization link. The user opens the link in Feishu,
 * confirms the app name and requested scopes/events/callbacks, and the script
 * returns App ID + App Secret automatically.
 *
 * Usage:
 *   node create-app.mjs --config <config.json> [--out <result.json>] [--timeout <seconds>]
 *
 * config.json schema:
 * {
 *   "name": "App Name",                 // required
 *   "desc": "App description",          // optional
 *   "avatar": "https://.../icon.png",   // optional, 1-6 URLs (string or string[])
 *   "preset": false,                    // optional, default false. false = minimal base template
 *   "createOnly": true,                 // optional, default true
 *   "scopes": {
 *     "tenant": ["im:message:send_as_bot"],
 *     "user": ["offline_access"]
 *   },
 *   "events": {
 *     "tenant": ["im.message.receive_v1"],
 *     "user": []
 *   },
 *   "callbacks": ["card.action.trigger"],
 *   "source": "my-agent"                // optional, appended to QR URL
 * }
 *
 * Output (stdout, line-based for easy parsing):
 *   AUTH_URL=<url>        – the authorization link for the user to open
 *   EXPIRE_IN=<seconds>   – link validity
 *   STATUS=<polling|slow_down|domain_switched>
 *   SUCCESS               – app created, credentials in --out file
 *   ERROR                 – failure, followed by a JSON line with {code,message}
 */

import { execSync } from 'child_process';
import { createRequire } from 'module';
import { chmodSync, existsSync, mkdirSync, readFileSync, writeFileSync, writeSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// ---------- ensure SDK ----------
function ensureSdk() {
  const sdkDir = join(__dirname, '..', 'vendor');
  const pkgPath = join(sdkDir, 'node_modules', '@larksuiteoapi', 'node-sdk', 'package.json');
  if (!existsSync(pkgPath)) {
    process.stderr.write('Installing @larksuiteoapi/node-sdk...\n');
    mkdirSync(sdkDir, { recursive: true });
    writeFileSync(
      join(sdkDir, 'package.json'),
      JSON.stringify({ name: 'feishu-app-creator-deps', version: '1.0.0', private: true }, null, 2)
    );
    execSync(`cd "${sdkDir}" && npm install @larksuiteoapi/node-sdk@latest`, { stdio: 'inherit' });
  }
  return createRequire(join(sdkDir, 'node_modules', '.') + '/')('@larksuiteoapi/node-sdk');
}

// ---------- args ----------
function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    if (argv[i] === '--config') args.config = argv[++i];
    else if (argv[i] === '--out') args.out = argv[++i];
    else if (argv[i] === '--timeout') args.timeout = parseInt(argv[++i], 10);
  }
  if (!args.config || !args.out) {
    process.stderr.write('Usage: create-app.mjs --config <config.json> --out <credential.json> [--timeout <seconds>]\n');
    process.stderr.write('--out is required so App Secret is never printed to stdout.\n');
    process.exit(1);
  }
  return args;
}

function emit(line) {
  writeSync(1, line + '\n');
}

// ---------- main ----------
async function main() {
  const args = parseArgs(process.argv);
  const cfg = JSON.parse(readFileSync(args.config, 'utf8'));

  if (!cfg.name) {
    process.stderr.write('config.name is required\n');
    process.exit(1);
  }

  const lark = ensureSdk();

  // Build addons
  const addons = { preset: cfg.preset !== undefined ? cfg.preset : false };
  if (cfg.scopes) {
    addons.scopes = {};
    if (cfg.scopes.tenant?.length) addons.scopes.tenant = cfg.scopes.tenant;
    if (cfg.scopes.user?.length) addons.scopes.user = cfg.scopes.user;
  }
  if (cfg.events) {
    addons.events = { items: {} };
    if (cfg.events.tenant?.length) addons.events.items.tenant = cfg.events.tenant;
    if (cfg.events.user?.length) addons.events.items.user = cfg.events.user;
  }
  if (cfg.callbacks?.length) {
    addons.callbacks = { items: cfg.callbacks };
  }

  // Build appPreset
  const appPreset = { name: cfg.name };
  if (cfg.desc) appPreset.desc = cfg.desc;
  if (cfg.avatar) appPreset.avatar = cfg.avatar;

  const registerOpts = {
    appPreset,
    addons,
    createOnly: cfg.createOnly !== undefined ? cfg.createOnly : true,
    onQRCodeReady(info) {
      emit('AUTH_URL=' + info.url);
      emit('EXPIRE_IN=' + info.expireIn);
    },
    onStatusChange(info) {
      emit('STATUS=' + info.status);
    },
  };
  if (cfg.source) registerOpts.source = cfg.source;
  if (cfg.appId) registerOpts.appId = cfg.appId;

  // Optional timeout via AbortController
  let timeoutHandle;
  if (args.timeout) {
    const ac = new AbortController();
    registerOpts.signal = ac.signal;
    timeoutHandle = setTimeout(() => ac.abort(), args.timeout * 1000);
  }

  try {
    const result = await lark.registerApp(registerOpts);
    if (timeoutHandle) clearTimeout(timeoutHandle);

    const credentials = {
      app_id: result.client_id,
      app_secret: result.client_secret,
      user_info: result.user_info || null,
    };

    writeFileSync(args.out, JSON.stringify(credentials, null, 2), { mode: 0o600 });
    chmodSync(args.out, 0o600);
    emit('SUCCESS');
    emit('CREDENTIALS_WRITTEN=' + args.out);
  } catch (e) {
    if (timeoutHandle) clearTimeout(timeoutHandle);
    emit('ERROR');
    emit(JSON.stringify({ code: e.code || 'unknown', message: e.description || e.message || String(e) }));
    process.exit(1);
  }
}

main();
