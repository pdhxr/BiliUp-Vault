import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';

const virtualPython = process.platform === 'win32'
  ? '.venv/Scripts/python.exe'
  : '.venv/bin/python';
const command = existsSync(virtualPython)
  ? virtualPython
  : (process.platform === 'win32' ? 'py' : 'python3');
const prefix = !existsSync(virtualPython) && process.platform === 'win32' ? ['-3'] : [];
const result = spawnSync(command, [...prefix, 'packaging/build_sidecar.py'], {
  stdio: 'inherit',
});

if (result.error) {
  console.error(`无法启动 Python：${result.error.message}`);
  process.exit(1);
}
process.exit(result.status ?? 1);
