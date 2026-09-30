import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Independent reference build: never replaces the production index.html.
export default defineConfig({
  plugins: [react()],
  build: { outDir: 'dist/wp10', rollupOptions: { input: 'wp10.html' } },
  server: { host: '127.0.0.1', port: 3010 },
});
