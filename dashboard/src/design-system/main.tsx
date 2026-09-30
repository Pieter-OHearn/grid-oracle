import React from 'react';
import { createRoot } from 'react-dom/client';
import { DesignReference } from './Reference';
import './tokens.css';

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <DesignReference />
  </React.StrictMode>,
);
