#!/bin/bash
# Fully provisions Langfuse for Scout — zero UI steps required.
#
# Run once after: docker compose up -d
# Usage: bash backend/setup_langfuse_evals.sh
#
# What this does:
#   1. Encrypts and inserts the Ollama LLM connection (no UI needed)
#   2. Inserts 3 eval templates (factual_grounding, specific_facts, no_active_bias)
#   3. Creates 3 active job_configurations that auto-trigger on every new trace

set -e
cd "$(dirname "$0")/.."

# Load LANGFUSE_ENCRYPTION_KEY and LLM_MODEL from .env
set -a
source .env
set +a

echo "Provisioning Langfuse LLM connection and evaluators..."

# ── 1. Encrypt the Ollama API key using Langfuse's AES-256-GCM scheme ─────────
ENCRYPTED_KEY=$(docker compose exec -T langfuse node -e "
const { createCipheriv, randomBytes } = require('crypto');
const key = Buffer.from('${LANGFUSE_ENCRYPTION_KEY}', 'hex');
const iv = randomBytes(12);
const cipher = createCipheriv('aes-256-gcm', key, iv);
let encrypted = cipher.update('ollama', 'utf8', 'hex');
encrypted += cipher.final('hex');
const authTag = cipher.getAuthTag();
console.log(iv.toString('hex') + ':' + encrypted + ':' + authTag.toString('hex'));
" 2>/dev/null | tr -d '\r\n')

if [ -z "$ENCRYPTED_KEY" ]; then
  echo "✗ Failed to encrypt LLM key — is the Langfuse container running?"
  exit 1
fi

# ── 2. Insert everything into the DB ──────────────────────────────────────────
docker compose exec -T langfuse-db psql -U langfuse -d langfuse << EOSQL

-- LLM connection: Ollama via OpenAI-compatible adapter
INSERT INTO llm_api_keys (
  id, created_at, updated_at, project_id,
  provider, adapter,
  secret_key, display_secret_key,
  base_url,
  custom_models, with_default_models
)
VALUES (
  'scout-llm-ollama', NOW(), NOW(), 'scout-project',
  'openai', 'openai',
  '${ENCRYPTED_KEY}', 'olla***',
  'http://host.docker.internal:11434/v1',
  ARRAY['${LLM_MODEL:-qwen2.5:14b}'], false
)
ON CONFLICT DO NOTHING;

-- ── Eval template: factual_grounding ─────────────────────────────────────────
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
  '${LLM_MODEL:-qwen2.5:14b}',
  '{"temperature": 0, "max_tokens": 200}'::jsonb,
  ARRAY['output'],
  '{"version": 2, "dataType": "NUMERIC", "reasoning": {"description": "Brief evaluation reasoning"}, "score": {"description": "1 = no hallucinations, 0 = hallucinations detected"}}'::jsonb,
  'openai'
)
ON CONFLICT DO NOTHING;

-- ── Eval template: specific_facts ────────────────────────────────────────────
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
  '${LLM_MODEL:-qwen2.5:14b}',
  '{"temperature": 0, "max_tokens": 200}'::jsonb,
  ARRAY['output'],
  '{"version": 2, "dataType": "NUMERIC", "reasoning": {"description": "Brief evaluation reasoning"}, "score": {"description": "1 = contains specific facts, 0 = generic boilerplate"}}'::jsonb,
  'openai'
)
ON CONFLICT DO NOTHING;

-- ── Eval template: no_active_bias ────────────────────────────────────────────
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
  '${LLM_MODEL:-qwen2.5:14b}',
  '{"temperature": 0, "max_tokens": 200}'::jsonb,
  ARRAY['output'],
  '{"version": 2, "dataType": "NUMERIC", "reasoning": {"description": "Brief evaluation reasoning"}, "score": {"description": "1 = founders presented correctly, 0 = active-bias detected"}}'::jsonb,
  'openai'
)
ON CONFLICT DO NOTHING;

-- ── Evaluator jobs (auto-trigger on every new trace) ─────────────────────────
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
echo "✅ Langfuse fully provisioned:"
echo "   • Ollama LLM connection registered (no UI step needed)"
echo "   • 3 LLM-as-judge evaluators active on every new trace"
echo "   • Scores visible at: http://localhost:3001 → scout-project → Traces"
echo ""
