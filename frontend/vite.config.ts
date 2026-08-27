import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    // inotify events don't cross the Windows bind mount into WSL2, so HMR
    // needs polling to see edits
    watch: {
      usePolling: true,
    },
  },
})
