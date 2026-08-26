import { defineConfig } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

// Next.js 16 exports native flat configs; using FlatCompat here causes ESLint
// 9 to serialize plugin objects and fail before evaluating any project files.
export default defineConfig([
  ...nextVitals,
  ...nextTypescript,
  {
    rules: {
      // El frontend existente carga datos y reinicia paginación desde efectos.
      // La migración gradual de esos patrones se tratará por separado.
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/static-components": "off",
    },
  },
]);
