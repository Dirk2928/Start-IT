import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  // Emit relative asset paths (./assets/...) so the built index.html works when
  // Electron loads it over file:// from inside the packaged app. Without this,
  // Vite defaults to absolute /assets/... paths that resolve to the filesystem
  // root under file://, leaving the packaged app on a blank white screen.
  base: './',
  plugins: [react(), tailwindcss()],
})
