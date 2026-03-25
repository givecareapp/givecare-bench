#!/usr/bin/env node
import { createRequire } from 'node:module'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '..', '..', '..')
const monoRoot = path.resolve(repoRoot, '..', 'give-care-mono')
const entryPoint = path.join(__dirname, 'src', 'bridge.ts')
const outDir = path.join(__dirname, 'dist')
const outfile = path.join(outDir, 'bridge.cjs')

function fail(message) {
  console.error(message)
  process.exit(1)
}

if (!fs.existsSync(monoRoot)) {
  fail(`GiveCare mono repo not found: ${monoRoot}`)
}

const pnpmDir = path.join(monoRoot, 'node_modules', '.pnpm')
if (!fs.existsSync(pnpmDir)) {
  fail(`pnpm store not found: ${pnpmDir}`)
}

const esbuildPkg = fs
  .readdirSync(pnpmDir)
  .find(name => name.startsWith('esbuild@') && fs.existsSync(path.join(pnpmDir, name, 'node_modules', 'esbuild')))

if (!esbuildPkg) {
  fail(`Could not locate esbuild under ${pnpmDir}`)
}

const require = createRequire(import.meta.url)
const esbuild = require(path.join(pnpmDir, esbuildPkg, 'node_modules', 'esbuild'))

fs.mkdirSync(outDir, { recursive: true })

esbuild.buildSync({
  entryPoints: [entryPoint],
  outfile,
  bundle: true,
  platform: 'node',
  format: 'cjs',
  target: ['node22'],
  external: ['canvas'],
  logLevel: 'silent',
  define: {
    'process.env.GIVECARE_MONO_ROOT': JSON.stringify(monoRoot),
  },
})

console.log(outfile)
