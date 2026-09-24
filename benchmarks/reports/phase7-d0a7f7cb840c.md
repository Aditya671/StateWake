# StateWake Comparative Validation Study

**Study ID:** `phase7-d0a7f7cb840c`
**Digest:** `24a2101cdcfc2797930220c2383fc51f800db12069d5aacdb83668c1782a4717`

## Metrics

| Baseline | Coverage | Detection | False positives | Cases |
|---|---:|---:|---:|---:|
| conventional_logs | 0.034 | 0.000 | 0.000 | 10 |
| final_output_only | 0.034 | 0.000 | 0.000 | 10 |
| statewake_full | 1.000 | 0.571 | 0.000 | 10 |
| structured_traces | 0.069 | 0.000 | 0.000 | 10 |

## Limitations

- Deterministic fixtures are used before live AI calls.
- Metrics are scoped to these workloads and injected faults only.
- Human reconstruction-time measurement requires a separate timed study.

## Cases

### rag_answer / final_output_only

- Injected faults: none
- Detected faults: none
- Checkable properties: 1 / 6
- Profile satisfied: None

### rag_answer / final_output_only

- Injected faults: omitted_evidence, stale_corpus
- Detected faults: none
- Checkable properties: 1 / 6
- Profile satisfied: None

### rag_answer / conventional_logs

- Injected faults: none
- Detected faults: none
- Checkable properties: 1 / 6
- Profile satisfied: None

### rag_answer / conventional_logs

- Injected faults: omitted_evidence, stale_corpus
- Detected faults: none
- Checkable properties: 1 / 6
- Profile satisfied: None

### rag_answer / structured_traces

- Injected faults: none
- Detected faults: none
- Checkable properties: 2 / 6
- Profile satisfied: None

### rag_answer / structured_traces

- Injected faults: omitted_evidence, stale_corpus
- Detected faults: none
- Checkable properties: 2 / 6
- Profile satisfied: None

### rag_answer / statewake_full

- Injected faults: none
- Detected faults: none
- Checkable properties: 6 / 6
- Profile satisfied: True

### rag_answer / statewake_full

- Injected faults: omitted_evidence, stale_corpus
- Detected faults: omitted_evidence
- Checkable properties: 6 / 6
- Profile satisfied: False

### tool_action / final_output_only

- Injected faults: none
- Detected faults: none
- Checkable properties: 0 / 6
- Profile satisfied: None

### tool_action / final_output_only

- Injected faults: missing_tool_authorization, modified_tool_output
- Detected faults: none
- Checkable properties: 0 / 6
- Profile satisfied: None

### tool_action / conventional_logs

- Injected faults: none
- Detected faults: none
- Checkable properties: 0 / 6
- Profile satisfied: None

### tool_action / conventional_logs

- Injected faults: missing_tool_authorization, modified_tool_output
- Detected faults: none
- Checkable properties: 0 / 6
- Profile satisfied: None

### tool_action / structured_traces

- Injected faults: none
- Detected faults: none
- Checkable properties: 0 / 6
- Profile satisfied: None

### tool_action / structured_traces

- Injected faults: missing_tool_authorization, modified_tool_output
- Detected faults: none
- Checkable properties: 0 / 6
- Profile satisfied: None

### tool_action / statewake_full

- Injected faults: none
- Detected faults: none
- Checkable properties: 6 / 6
- Profile satisfied: True

### tool_action / statewake_full

- Injected faults: missing_tool_authorization, modified_tool_output
- Detected faults: modified_tool_output
- Checkable properties: 6 / 6
- Profile satisfied: True

### incident_recovery / final_output_only

- Injected faults: none
- Detected faults: none
- Checkable properties: 0 / 5
- Profile satisfied: None

### incident_recovery / final_output_only

- Injected faults: recovery_without_preserved_failure
- Detected faults: none
- Checkable properties: 0 / 5
- Profile satisfied: None

### incident_recovery / conventional_logs

- Injected faults: none
- Detected faults: none
- Checkable properties: 0 / 5
- Profile satisfied: None

### incident_recovery / conventional_logs

- Injected faults: recovery_without_preserved_failure
- Detected faults: none
- Checkable properties: 0 / 5
- Profile satisfied: None

### incident_recovery / structured_traces

- Injected faults: none
- Detected faults: none
- Checkable properties: 0 / 5
- Profile satisfied: None

### incident_recovery / structured_traces

- Injected faults: recovery_without_preserved_failure
- Detected faults: none
- Checkable properties: 0 / 5
- Profile satisfied: None

### incident_recovery / statewake_full

- Injected faults: none
- Detected faults: none
- Checkable properties: 5 / 5
- Profile satisfied: True

### incident_recovery / statewake_full

- Injected faults: recovery_without_preserved_failure
- Detected faults: recovery_without_preserved_failure
- Checkable properties: 5 / 5
- Profile satisfied: False

### release_verification / final_output_only

- Injected faults: none
- Detected faults: none
- Checkable properties: 0 / 6
- Profile satisfied: None

### release_verification / final_output_only

- Injected faults: unsigned_release_artifact
- Detected faults: none
- Checkable properties: 0 / 6
- Profile satisfied: None

### release_verification / conventional_logs

- Injected faults: none
- Detected faults: none
- Checkable properties: 0 / 6
- Profile satisfied: None

### release_verification / conventional_logs

- Injected faults: unsigned_release_artifact
- Detected faults: none
- Checkable properties: 0 / 6
- Profile satisfied: None

### release_verification / structured_traces

- Injected faults: none
- Detected faults: none
- Checkable properties: 0 / 6
- Profile satisfied: None

### release_verification / structured_traces

- Injected faults: unsigned_release_artifact
- Detected faults: none
- Checkable properties: 0 / 6
- Profile satisfied: None

### release_verification / statewake_full

- Injected faults: none
- Detected faults: none
- Checkable properties: 6 / 6
- Profile satisfied: True

### release_verification / statewake_full

- Injected faults: unsigned_release_artifact
- Detected faults: none
- Checkable properties: 6 / 6
- Profile satisfied: True

### human_approval_workflow / final_output_only

- Injected faults: none
- Detected faults: none
- Checkable properties: 0 / 6
- Profile satisfied: None

### human_approval_workflow / final_output_only

- Injected faults: omitted_evidence
- Detected faults: none
- Checkable properties: 0 / 6
- Profile satisfied: None

### human_approval_workflow / conventional_logs

- Injected faults: none
- Detected faults: none
- Checkable properties: 0 / 6
- Profile satisfied: None

### human_approval_workflow / conventional_logs

- Injected faults: omitted_evidence
- Detected faults: none
- Checkable properties: 0 / 6
- Profile satisfied: None

### human_approval_workflow / structured_traces

- Injected faults: none
- Detected faults: none
- Checkable properties: 0 / 6
- Profile satisfied: None

### human_approval_workflow / structured_traces

- Injected faults: omitted_evidence
- Detected faults: none
- Checkable properties: 0 / 6
- Profile satisfied: None

### human_approval_workflow / statewake_full

- Injected faults: none
- Detected faults: none
- Checkable properties: 6 / 6
- Profile satisfied: True

### human_approval_workflow / statewake_full

- Injected faults: omitted_evidence
- Detected faults: omitted_evidence
- Checkable properties: 6 / 6
- Profile satisfied: False
