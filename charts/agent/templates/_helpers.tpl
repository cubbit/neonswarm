{{/*
Return the chart's short name.
*/}}
{{- define "agent.name" -}}
{{- .Chart.Name -}}
{{- end -}}

{{/*
Return a fully-qualified resource name for a single swarm agent.
Agents are iterated from .Values.swarm.agents, so callers must pass the
agent dict into the include context: include "agent.fullname" (dict "root" $ "agent" .)
*/}}
{{- define "agent.fullname" -}}
{{- $agent := .agent -}}
{{- printf "%s" $agent.name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Chart version label as `helm.sh/chart`.
*/}}
{{- define "agent.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Standard labels shared by every resource in the chart. Requires the
caller to pass the agent dict so we can include the per-agent identity.
Usage: include "agent.labels" (dict "root" $ "agent" .)
*/}}
{{- define "agent.labels" -}}
helm.sh/chart: {{ include "agent.chart" .root }}
{{ include "agent.selectorLabels" . }}
{{- if .root.Chart.AppVersion }}
app.kubernetes.io/version: {{ .root.Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .root.Release.Service }}
app.kubernetes.io/component: swarm-agent
app.kubernetes.io/part-of: neonswarm
{{- end -}}

{{/*
Selector labels — MUST be a strict subset of labels, and MUST be
immutable across the lifetime of a Deployment/StatefulSet/DaemonSet.
Usage: include "agent.selectorLabels" (dict "root" $ "agent" .)
*/}}
{{- define "agent.selectorLabels" -}}
app.kubernetes.io/name: {{ include "agent.name" .root }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
cubbit.io/swarm-agent: {{ .agent.name | quote }}
{{- end -}}
