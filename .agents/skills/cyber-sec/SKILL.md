---
description: Auditor de seguridad industrial. Escanea vulnerabilidades en código (SAST), dependencias (SCA) y configuraciones de Terraform. Detecta fugas de secretos y excesos de privilegios en IAM de GCP para garantizar un despliegue "Zero Trust".
---

1. **Mapeo de la Superficie de Ataque:**
   - El Agente DEBE leer `system-heartbeat/PLAN-TASK-XXX.md` para identificar qué recursos de GCP y qué endpoints de API están siendo creados o modificados.
   - El Agente DEBE revisar el reporte de `/archeology` para conocer el estado previo de seguridad.

2. **Escaneo de Secretos y Hardcoding:**
   - El Agente DEBE realizar un escaneo recursivo en los archivos modificados buscando patrones de: API Keys, Service Account Keys, contraseñas o tokens.
   - RESTRICCIÓN: Queda terminantemente PROHIBIDO el uso de strings sensibles en el código. Todo secreto DEBE estar referenciado a GCP Secret Manager o inyectado vía variables de entorno en el `bitbucket-pipelines.yml`.

3. **Auditoría de Infraestructura como Código (IaC - Terraform):**
   - El Agente DEBE auditar los archivos `.tf` en `/infra` buscando:
     - **Principio de Mínimo Privilegio:** Validar que las Service Accounts de GCP no tengan roles genéricos como `roles/editor` o `roles/owner`. Deben ser roles granulares (ej. `roles/bigquery.dataViewer`).
     - **Exposición Pública:** Verificar que los servicios de Cloud Run no tengan configurada la autenticación `allUsers` (permit-unauthenticated) a menos que el PRD lo exija explícitamente.
     - **Cifrado:** Validar que los buckets de almacenamiento y bases de datos tengan habilitado el cifrado en reposo.

4. **Análisis de Vulnerabilidades en Dependencias (SCA):**
   - **Backend:** Revisar `go.mod` buscando librerías con CVEs conocidos.
   - **Sidecar (Python):** Ejecutar `uv pip audit` (o equivalente de análisis de seguridad de uv) para detectar vulnerabilidades en el árbol de dependencias de Python.
   - **Frontend:** Analizar `package.json` en busca de dependencias obsoletas o vulnerables.

5. **Análisis Estático de Seguridad (SAST):**
   - **Go:** Buscar riesgos de inyección de comandos o SQL en los adaptadores de infraestructura.
   - **Python:** Validar que el uso de la IA (Gemini) incluya saneamiento de entradas para evitar ataques de inyección de prompts que puedan comprometer la lógica del backend.
   - **React:** Buscar riesgos de Cross-Site Scripting (XSS) en la renderización dinámica de datos.

6. **Generación del Reporte de Auditoría de Seguridad:**
   - El Agente DEBE crear el archivo `system-heartbeat/SECURITY-AUDIT-TASK-XXX.md` con una matriz de severidad:
     - **CRITICAL/HIGH:** Bloqueo inmediato del despliegue.
     - **MEDIUM/LOW:** Advertencias para futura corrección.
   - DEBE incluir una sección de "Remediación Sugerida" para cada hallazgo.

7. **Veredicto de Seguridad (Gatekeeper):**
   - Si existen hallazgos de severidad "High" o "Critical", el Agente DEBE notificar al Orquestador y abortar el flujo `/devops-deploy`.
   - Si el reporte es limpio o solo contiene riesgos bajos, otorga el "Security Clearance".