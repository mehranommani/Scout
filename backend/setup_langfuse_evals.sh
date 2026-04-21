#!/bin/bash
# Provisions Langfuse LLM-as-judge evaluators directly in the langfuse-db container.
#
# Run once after: docker compose up -d
# Usage: bash backend/setup_langfuse_evals.sh
#
# What this does:
#   1. Inserts 3 eval templates (factual_grounding, specific_facts, no_active_bias)
#   2. Creates 3 active job_configurations that auto-trigger on every new trace
#
# LLM connection setup (do this once in the Langfuse UI before running):
#   http://localhost:3001 → Settings → LLM Connections → Add connection
#     Provider : OpenAI (Ollama is OpenAI-compatible)
#     Base URL : http://host.docker.internal:11434/v1
#     API Key  : ollama
#     Model    : qwen2.5:14b  (or your LLM_MODEL from .env)

set -e
cd "$(dirname "$0")/.."

echo "Inserting Langfuse evaluator templates and job configurations..."

docker compose exec -T langfuse-db psql -U langfuse -d langfuse << 'EOSQL'

-- ── 1. factual_grounding ─────────────────────────────────────────────────────
INSERT INTO eval_templates (id, created_at, updated_at, project_id, name, version, prompt, model, model_params, vars, output_schema, provider)
VALUES (
  'scout-eval-factual', NOW(), NOW(), 'scout-project', 'factual_grounding', 1,
  'You are a strict quality auditor reviewing a company research report.

QUESTION: Does the report avoid inventing financial figures, email addresses, phone numbers, or contact details that are not present in its source data?

REPORT:
{{output}}

Respond with a JSON object in this exact format:
{
  "reasoning": "Brief explanation of your evaluation",
  "score": 1
}
Use score 1 if all stated facts appear real or are honestly marked as "Not available in data sources."
Use score 0 if any specific figure or contact detail looks fabricated.',
  'qwen2.5:14b',
  '{"temperature": 0, "max_tokens": 200}'::jsonb,
  ARRAY['output'],
  '{"version": 2, "dataType": "NUMERIC", "reasoning": {"description": "Brief evaluation reasoning"}, "score": {"description": "1 = no hallucinations, 0 = hallucinations detected"}}'::jsonb,
  'openai'
)
ON CONFLICT DO NOTHING;

-- ── 2. specific_facts ────────────────────────────────────────────────────────
INSERT INTO eval_templates (id, created_at, updated_at, project_id, name, version, prompt, model, model_params, vars, output_schema, provider)
VALUES (
  'scout-eval-specific', NOW(), NOW(), 'scout-project', 'specific_facts', 1,
  'You are a strict quality auditor reviewing a company research report.

QUESTION: Does the report contain at least one concrete, specific fact — such as a founding year, headcount, revenue figure, named executive, or funding amount — rather than being entirely generic boilerplate with no verifiable details?

REPORT:
{{output}}

Respond with a JSON object in this exact format:
{
  "reasoning": "Brief explanation of your evaluation",
  "score": 1
}
Use score 1 if the report contains at least one specific verifiable fact.
Use score 0 if the report is entirely generic boilerplate.',
  'qwen2.5:14b',
  '{"temperature": 0, "max_tokens": 200}'::jsonb,
  ARRAY['output'],
  '{"version": 2, "dataType": "NUMERIC", "reasoning": {"description": "Brief evaluation reasoning"}, "score": {"description": "1 = contains specific facts, 0 = generic boilerplate"}}'::jsonb,
  'openai'
)
ON CONFLICT DO NOTHING;

-- ── 3. no_active_bias ────────────────────────────────────────────────────────
INSERT INTO eval_templates (id, created_at, updated_at, project_id, name, version, prompt, model, model_params, vars, output_schema, provider)
VALUES (
  'scout-eval-founders', NOW(), NOW(), 'scout-project', 'no_active_bias', 1,
  'You are a strict quality auditor reviewing a company research report.

QUESTION: When the report mentions historical founders, does it avoid falsely presenting them as currently active or currently employed at the company? It is acceptable to say someone "co-founded" the company without claiming they are still there.

REPORT:
{{output}}

Respond with a JSON object in this exact format:
{
  "reasoning": "Brief explanation of your evaluation",
  "score": 1
}
Use score 1 if founders are presented correctly or there is no founders section.
Use score 0 if the report falsely implies founders are still active.',
  'qwen2.5:14b',
  '{"temperature": 0, "max_tokens": 200}'::jsonb,
  ARRAY['output'],
  '{"version": 2, "dataType": "NUMERIC", "reasoning": {"description": "Brief evaluation reasoning"}, "score": {"description": "1 = founders presented correctly, 0 = active-bias detected"}}'::jsonb,
  'openai'
)
ON CONFLICT DO NOTHING;

-- ── 4. Evaluator jobs (auto-trigger on every new trace) ───────────────────────
INSERT INTO job_configurations (id, created_at, updated_at, project_id, job_type, eval_template_id, score_name, filter, target_object, variable_mapping, sampling, delay, status, time_scope)
VALUES
  (
    'scout-job-factual_grounding', NOW(), NOW(), 'scout-project',
    'EVAL'::"JobType", 'scout-eval-factual', 'eval/factual_grounding',
    '[]'::jsonb, 'trace',
    '[{"templateVariable": "output", "langfuseObject": "trace", "selectedColumnId": "output"}]'::jsonb,
    1.0, 0, 'ACTIVE'::"JobConfigState", ARRAY['NEW']
  ),
  (
    'scout-job-specific_facts', NOW(), NOW(), 'scout-project',
    'EVAL'::"JobType", 'scout-eval-specific', 'eval/specific_facts',
    '[]'::jsonb, 'trace',
    '[{"templateVariable": "output", "langfuseObject": "trace", "selectedColumnId": "output"}]'::jsonb,
    1.0, 0, 'ACTIVE'::"JobConfigState", ARRAY['NEW']
  ),
  (
    'scout-job-no_active_bias', NOW(), NOW(), 'scout-project',
    'EVAL'::"JobType", 'scout-eval-founders', 'eval/no_active_bias',
    '[]'::jsonb, 'trace',
    '[{"templateVariable": "output", "langfuseObject": "trace", "selectedColumnId": "output"}]'::jsonb,
    1.0, 0, 'ACTIVE'::"JobConfigState", ARRAY['NEW']
  )
ON CONFLICT DO NOTHING;
EOSQL

echo ""
echo "✅ Langfuse evaluator setup complete."
echo "   Every new research trace will be automatically evaluated."
echo "   Scores visible at: http://localhost:3001 → scout-project → Traces → [trace] → Scores"
echo ""
echo "   NOTE: Make sure you have added the LLM connection in the Langfuse UI first."
echo "   Settings → LLM Connections → Add (OpenAI-compatible, base URL: http://host.docker.internal:11434/v1)"
