import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';

const source = readFileSync('core/version.py', 'utf8');
const match = source.match(/APP_VERSION\s*=\s*["']([^"']+)["']/);
if (!match) {
  console.error('无法从 core/version.py 读取 APP_VERSION');
  process.exit(1);
}

const command = process.platform === 'win32'
  ? 'node_modules/.bin/tauri.cmd'
  : 'node_modules/.bin/tauri';
const action = process.argv[2];
if (!['dev', 'build'].includes(action)) {
  console.error('用法：node packaging/run_tauri.mjs <dev|build>');
  process.exit(1);
}

const result = spawnSync(command, [action, '--config', JSON.stringify({ version: match[1] })], {
  stdio: 'inherit',
});
if (result.error) {
  console.error(`无法启动 Tauri CLI：${result.error.message}`);
  process.exit(1);
}
process.exit(result.status ?? 1);
