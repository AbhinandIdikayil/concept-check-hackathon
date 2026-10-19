/// <reference types="node" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'
import { config } from 'dotenv'

// Load .env into process.env before we read anything from it.
config()

const apiUrl =
  process.env.API ?? process.env.VITE_API ?? 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: {
    // Only these two reach the browser bundle. Defining the whole
    // `process.env` would inline every environment variable — including
    // any secrets — into the client bundle.
    'process.env.API': JSON.stringify(apiUrl),
    'process.env.VITE_API': JSON.stringify(apiUrl),
  },
})
