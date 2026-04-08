{{/*
Return the chart's short name. Overridable via .Values.nameOverride.
*/}}
{{- define "lcd-storage.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Return a fully-qualified resource name, scoped by release name so
multiple releases of the chart can coexist in the same namespace.
Overridable via .Values.fullnameOverride.
*/}}
{{- define "lcd-storage.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Chart version label as ``helm.sh/chart``.
*/}}
{{- define "lcd-storage.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Standard labels shared by every resource in the chart.
*/}}
{{- define "lcd-storage.labels" -}}
helm.sh/chart: {{ include "lcd-storage.chart" . }}
{{ include "lcd-storage.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/component: storage-monitor
app.kubernetes.io/part-of: neonswarm
{{- end -}}

{{/*
Selector labels — strict subset of labels, immutable after creation.
*/}}
{{- define "lcd-storage.selectorLabels" -}}
app.kubernetes.io/name: {{ include "lcd-storage.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
ServiceAccount name, default derived from fullname.
*/}}
{{- define "lcd-storage.serviceAccountName" -}}
{{- default (printf "%s-sa" (include "lcd-storage.fullname" .)) .Values.serviceAccount.name -}}
{{- end -}}
