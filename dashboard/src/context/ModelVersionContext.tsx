import { createContext, useContext, useState } from 'react';

export interface ModelVersionInfo {
  id: number;
  name: string;
}

interface ModelVersionContextValue {
  modelVersion: ModelVersionInfo | null;
  setModelVersion: (v: ModelVersionInfo | null) => void;
}

const ModelVersionContext = createContext<ModelVersionContextValue>({
  modelVersion: null,
  setModelVersion: () => {},
});

// eslint-disable-next-line react-refresh/only-export-components
export function useModelVersion() {
  return useContext(ModelVersionContext);
}

export function ModelVersionProvider({ children }: { children: React.ReactNode }) {
  const [modelVersion, setModelVersion] = useState<ModelVersionInfo | null>(null);
  return (
    <ModelVersionContext.Provider value={{ modelVersion, setModelVersion }}>
      {children}
    </ModelVersionContext.Provider>
  );
}
