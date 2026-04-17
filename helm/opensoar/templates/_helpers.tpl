{{- define "opensoar.labels" -}}
app.kubernetes.io/name: opensoar
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
{{- end -}}

{{/*
Common environment variables shared between the api and worker pods.
AI provider credentials are marked optional so pods still start when the
operator hasn't populated them. Set them via `secrets.anthropicApiKey`,
`secrets.openaiApiKey`, or `secrets.ollamaUrl` in values.yaml (or with
`--set-string` / `--values`).
*/}}
{{- define "opensoar.commonEnv" -}}
- name: DATABASE_URL
  valueFrom:
    secretKeyRef:
      name: opensoar-secrets
      key: database-url
- name: REDIS_URL
  valueFrom:
    secretKeyRef:
      name: opensoar-secrets
      key: redis-url
- name: CELERY_BROKER_URL
  valueFrom:
    secretKeyRef:
      name: opensoar-secrets
      key: celery-broker-url
- name: JWT_SECRET
  valueFrom:
    secretKeyRef:
      name: opensoar-secrets
      key: jwt-secret
- name: API_KEY_SECRET
  valueFrom:
    secretKeyRef:
      name: opensoar-secrets
      key: api-key-secret
- name: ANTHROPIC_API_KEY
  valueFrom:
    secretKeyRef:
      name: opensoar-secrets
      key: anthropic-api-key
      optional: true
- name: OPENAI_API_KEY
  valueFrom:
    secretKeyRef:
      name: opensoar-secrets
      key: openai-api-key
      optional: true
- name: OLLAMA_URL
  valueFrom:
    secretKeyRef:
      name: opensoar-secrets
      key: ollama-url
      optional: true
{{- end -}}
