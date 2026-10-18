# Graph Report - herhealthgpt  (2026-10-18)

## Corpus Check
- 420 files · ~816,993 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 31 file(s) not represented in the graph (top: (none) 10, .jsonl 5, .example 3)

## Summary
- 5345 nodes · 14458 edges · 191 communities (164 shown, 27 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 1938 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ef60a47f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Turn Context & Rule Assessment
- Deterministic Triage Engine
- react
- cn
- test_vectorstore.py
- Consultation Session Models
- collections_abc
- Auth Cookies & Account Routes
- register_user
- app/config.py
- TriageState
- useI18n
- useAuth
- RetrievedPassage
- Triage CLI
- Knowledge Schema Contracts
- Dashboard & Account Settings
- Email Verification
- herhealth_contracts/knowledge.py
- ReasoningAttempt
- HealthBench & FDA CDS Guidance
- Account Route Tests
- Password Reset Errors
- email_sender.py
- Triage Route Tests
- register_error_handlers
- Threshold Analysis
- Knowledge Validation
- test_provenance.py
- Conversational Diagnostic AI Papers
- Ingest Config & Robots
- TriageDecision Schema
- Database Migrations
- commands.py
- Password Reset Codes
- test_cli.py
- Phase-1 Conditions & Features
- Session Policy & Refresh
- Agent Context Tests
- Sign-In Throttling & Locks
- Evaluation Metrics
- Dialogue Runner
- Embedding Benchmarks (MTEB, BGE-M3)
- test_evaluation_runner.py
- KnowledgeBase
- Red Flags & Urgent Actions
- Routine-Urgency Conditions
- AWS Deploy & Agent Docs
- Fetch Stage Tests
- httpx
- Frontend Dependencies
- Account Deletion
- Profile Details Validation
- en.ts
- HTML Cleaning Tests
- README.md
- QLoRA Adapter herhealth-lora-v2 (phrasing-only)
- Raw Store Lockfile
- types.ts
- agent.py
- Google Sign-In
- Knowledge Table Rendering
- El Saddik Lab Papers
- The knowledge base, explained
- accounts.ts
- Plausibility Scoring
- ICD-11 Lookup
- Evaluation CLI
- test_chain.py
- Triage Glossary
- Weights & Action Codes
- Condition Provenance Repair
- Profile & Health Note
- locale-provider.tsx
- shadcn Component Config
- test_language.py
- decision_eval.py
- uni server vllm
- cards
- conditions
- Research 0001: Reconsidering the deterministic controller (LLM triage architecture)
- google_sign_in.py
- test age bands
- test_retrieval.py
- README
- tsconfig
- CONTEXT
- _write_index
- test_serve_models.py
- retrieval_eval.py
- check repo hygiene
- ADR 0011: controller-free triage
- FLOW EXPLAINED
- LangChainRetrievalClient
- LangChainAnswerWriter
- cycle_data.py
- datetime
- q2 hf trl dataset formats
- Security 0001: injected postcss payload and leaked env backup
- cycle_import.py
- thresholds
- package
- test accounts deletion
- cycle.py
- serve-models.sh
- q3 modelcard bge m3
- q4 arxiv 2308.08747 catastrophic forgett
- sources
- knowledge
- main.py
- eventloop
- test_email_sender.py
- check_password_strength
- herhealth_data/provenance.py
- field_validator
- Step 3b: connecting the production backend to the campus models
- README
- CycleExtraction
- clean
- test_cycle.py
- 0005 plausibility is an independent logi
- test_cycle_data_routes.py
- test_compose_parity.py
- deploy.sh
- Path
- Case: vulval itching with discharge, no pain
- render_known_background
- tunnel-models.sh
- _Days
- lifespan
- q2 hf datasets loading
- q3 docs cohere embed
- q3 docs openai embeddings
- q3 pricing jina embeddings
- q3 pricing voyage ai
- q4 arxiv 2106.09685 lora low rank adapta
- features
- test isolation
- The local base model decides, and the fine-tuned adapter words informational answers
- The reasoning chain on LangChain — design
- q4 vllm lora adapters docs
- parse_env
- SesEmailSender
- package
- current_user.py
- load_source_urls
- q4 hf peft lora conceptual
- q3 modelcard multilingual e5 large
- HashingEmbeddings
- clean
- test_triage_mode.py
- test boundary
- q3 modelcard qwen3 embedding 0.6b
- test clean
- Model-serving stack on the campus GPU box — design
- load_evaluation_set
- os
- issue tracker
- document
- _build_cycle_extractor
- pyproject
- postcss.config.mjs
- Section
- ScriptedReranker
- File Structure
- package
- q3 modelcard bge reranker v2 m3
- Retrieval uses Qwen3-Embedding-4B and Qwen3-Reranker-4B, built on LangChain
- Files
- bootstrap deploy
- cycle_data_for
- write_email_preview
- next
- Model-Serving Stack Implementation Plan
- file
- globe
- window
- numpy
- backend/tests/conftest.py
- publish-index-release.sh
- README-decision-eval.md
- Frontend CLAUDE.md (includes AGENTS.md)

## God Nodes (most connected - your core abstractions)
1. `TriageEngine` - 109 edges
2. `KnowledgeBase` - 101 edges
3. `useI18n()` - 93 edges
4. `TriageDecision` - 88 edges
5. `RetrievedPassage` - 81 edges
6. `build()` - 81 edges
7. `cn()` - 76 edges
8. `ActionCode` - 63 edges
9. `DecisionType` - 59 edges
10. `User` - 59 edges

## Surprising Connections (you probably didn't know these)
- `Measurement` --references--> `TriageAgent`  [INFERRED]
  docs/adr/0017-qwen3-embedding-and-reranker-on-langchain.md → services/backend/src/herhealth_backend/triage/agent.py
- `Done when` --references--> `TriageAgent`  [INFERRED]
  docs/superpowers/specs/2026-10-12-retrieval-langchain-design.md → services/backend/src/herhealth_backend/triage/agent.py
- `Decision 3: how the index reaches the EC2 host` --references--> `IndexRefused`  [INFERRED]
  docs/superpowers/specs/2026-10-13-production-connectivity-design.md → services/backend/src/herhealth_backend/triage/retrieval.py
- `Context` --references--> `inform()`  [INFERRED]
  docs/adr/0018-local-models-decide-and-the-adapter-answers.md → services/backend/tests/test_agent_steps.py
- `Decision` --references--> `inform()`  [INFERRED]
  docs/adr/0018-local-models-decide-and-the-adapter-answers.md → services/backend/tests/test_agent_steps.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Components of one agentic RAG triage turn** — docs_flow_explained_backend_orchestrator, docs_flow_explained_embedding_model_bge_m3, docs_flow_explained_retrieval_index, docs_flow_explained_red_flags_full_injection, docs_flow_explained_reasoning_model, docs_flow_explained_triagedecision, docs_flow_explained_session_store [EXTRACTED 1.00]
- **Arabic RAG findings: sentence chunking, multilingual encoders, optional reranker** — docs_research_sources_q3_arxiv_2506_06339_alsubhi_arabic_rag_embedding_chunking_evaluation_sentence_aware_chunking, docs_research_sources_q3_arxiv_2506_06339_alsubhi_arabic_rag_embedding_chunking_evaluation_multilingual_beat_arabic_specific, docs_research_sources_q3_arxiv_2506_06339_alsubhi_arabic_rag_embedding_chunking_evaluation_bge_reranker_v2_m3, docs_research_sources_q3_arxiv_2506_06339_alsubhi_arabic_rag_embedding_chunking_evaluation_ragas_framework [EXTRACTED 1.00]
- **BGE-M3 unified dense, sparse and multi-vector retrieval** — docs_research_sources_q3_modelcard_bge_m3_bge_m3, docs_research_sources_q3_modelcard_bge_m3_dense_retrieval, docs_research_sources_q3_modelcard_bge_m3_sparse_retrieval, docs_research_sources_q3_modelcard_bge_m3_multi_vector_retrieval, docs_research_sources_q3_modelcard_bge_m3_self_knowledge_distillation [EXTRACTED 1.00]
- **The four hand-written controller demonstration cases pinned by tests** — services_backend_cases_sudden_severe_pain, services_backend_cases_heavy_periods_over_40, services_backend_cases_itching_and_discharge, services_backend_cases_says_nothing [EXTRACTED 1.00]
- **difficulty_conceiving distinguished across conditions (weak, argues_against, definitional)** — knowledge_features_difficulty_conceiving, knowledge_conditions_infertility, knowledge_conditions_ovarian_cyst, knowledge_conditions_pelvic_inflammatory_disease, knowledge_conditions_sexually_transmitted_infection, knowledge_conditions_hypothyroidism, knowledge_conditions_primary_ovarian_insufficiency, knowledge_conditions_endometriosis, knowledge_conditions_pcos [EXTRACTED 1.00]
- **Discharge cluster: separating thrush, bacterial vaginosis and STI by itching, smell and appearance** — knowledge_conditions_thrush, knowledge_conditions_bacterial_vaginosis, knowledge_conditions_sexually_transmitted_infection, knowledge_features_abnormal_discharge, knowledge_features_vulval_itching, knowledge_features_discharge_smell, knowledge_features_discharge_appearance, services_data_evidence_batches_batch_10_adenomyosis_discharge_bv_itching_source_conflict [EXTRACTED 1.00]
- **EMERGENCY red-flag rules conditioned on pelvic pain** — knowledge_red_flags_sudden_severe_pelvic_pain, knowledge_red_flags_pelvic_pain_with_faintness, knowledge_red_flags_pelvic_pain_with_shoulder_tip_pain, knowledge_red_flags_pelvic_pain_with_right_sided_referred_pain, knowledge_red_flags_pelvic_pain_with_heavy_bleeding, knowledge_red_flags_pelvic_pain_with_breathing_difficulty, knowledge_red_flags_pelvic_pain_with_sudden_confusion, knowledge_actions_emergency, knowledge_features_pelvic_pain_severity [EXTRACTED 1.00]
- **Primary evidence that triage needs external structure around the model** — docs_research_0001_llm_triage_architecture_mediq, docs_research_0001_llm_triage_architecture_healthbench, docs_research_0001_llm_triage_architecture_equitriage, docs_research_0001_llm_triage_architecture_mecr_rag, docs_research_0001_llm_triage_architecture_fda_cds_guidance, docs_research_0001_llm_triage_architecture_verdict_keep_the_controller [EXTRACTED 1.00]
- **Licence-driven handling of illustrations: manual download, no automation, not committed** — services_frontend_public_illustrations_readme_undraw_licence, services_frontend_public_illustrations_readme_no_script_fetch, services_frontend_public_illustrations_readme_files_stay_out_of_git, services_frontend_public_illustrations_readme_licence_exclusion_consistency [EXTRACTED 1.00]
- **The seven knowledge files that drive triage reasoning** — knowledge_features, knowledge_conditions, knowledge_evidence, knowledge_red_flags, knowledge_sources, knowledge_weights, knowledge_actions [EXTRACTED 1.00]
- **Three components of clinical evidence for medical device software** — docs_research_sources_q1_eu_mdcg_2020_1_clinical_evaluation_mdsw_valid_clinical_association, docs_research_sources_q1_eu_mdcg_2020_1_clinical_evaluation_mdsw_technical_performance, docs_research_sources_q1_eu_mdcg_2020_1_clinical_evaluation_mdsw_clinical_performance, docs_research_sources_q1_eu_mdcg_2020_1_clinical_evaluation_mdsw_clinical_evidence [EXTRACTED 1.00]
- **Production deploy pipeline from main to the EC2 host** — docs_runbooks_aws_deploy_github_oidc_roles, docs_runbooks_aws_deploy_ssm_deploy_document, docs_runbooks_aws_deploy_deploy_sh, docs_runbooks_aws_deploy_publish_index_sh, docs_runbooks_aws_deploy_secrets_and_rotation, docs_runbooks_aws_deploy_single_ec2_architecture [EXTRACTED 1.00]
- **The Seven Knowledge Files** — claude_features_yaml, claude_conditions_yaml, claude_evidence_csv, claude_red_flags_yaml, claude_sources_yaml, claude_weights_yaml, claude_actions_yaml [EXTRACTED 1.00]
- **TriageDecision contract: ASK/CONCLUDE, EMERGENCY exception, DECLINE and INFORM** — docs_adr_0011_controller_free_triage_triagedecision_schema_safety_net, docs_adr_0011_controller_free_triage_red_flag_names_no_condition, docs_adr_0011_controller_free_triage_matching_conditions_cap, docs_adr_0013_emergency_conclusions_may_name_conditions_emergency_names_conditions_exception, docs_adr_0014_an_off_scope_message_is_declined_not_triaged_decline_decision_type, docs_adr_0016_an_in_scope_question_may_be_answered_informationally_inform_decision_type [EXTRACTED 1.00]
- **The nine unDraw illustrations the Illustration component resolves by filename** — services_frontend_public_illustrations_onboarding, services_frontend_public_illustrations_urgency, services_frontend_public_illustrations_welcome, services_frontend_public_illustrations_conversation, services_frontend_public_illustrations_safety, services_frontend_public_illustrations_sources, services_frontend_public_illustrations_resolved, services_frontend_public_illustrations_error, services_frontend_public_illustrations_not_found [EXTRACTED 1.00]
- **Mechanisms for deciding when to ask a clarifying question instead of concluding** — docs_research_sources_q5_arxiv_2406_00922_mediq_question_asking_llms_interactive_clinical_reasoning_abstention_strategies, docs_research_sources_q5_arxiv_2502_14860_alfa_aligning_llms_to_ask_good_questions_clinical_reasoning_alfa_framework, docs_research_sources_q5_arxiv_2505_04653_amie_advancing_conversational_diagnostic_ai_multimodal_state_aware_dialogue_framework, docs_research_sources_q5_arxiv_2401_05654_amie_towards_conversational_diagnostic_ai_chain_of_reasoning_strategy [INFERRED 0.75]
- **Embedding evaluation benchmark lineage (BEIR, MTEB, MIRACL, MMTEB)** — docs_research_sources_q3_arxiv_2210_07316_mteb_massive_text_embedding_benchmark_beir, docs_research_sources_q3_arxiv_2210_07316_mteb_massive_text_embedding_benchmark_mteb, docs_research_sources_q3_arxiv_2402_03216_bge_m3_embedding_multilingual_multifunctionality_miracl, docs_research_sources_q3_arxiv_2502_13595_mmteb_massive_multilingual_text_embedding_benchmark_mmteb [INFERRED 0.75]
- **Gate on Letting the Fine-Tuned Adapter Decide Triage** — claude_adr_0011, claude_triagedecision, claude_qlora_adapter, claude_ft_corpus_v1, claude_bootstrap_multi_turn, handoff_issue_20_migration, readme_model_selector [INFERRED 0.85]
- **Evidence authoring flow: approved batches generate evidence.csv, quotes verified verbatim** — services_data_evidence_batches_batch_01_pcos_fibroids, services_data_evidence_batches_batch_02_endometriosis, services_data_evidence_batches_batch_03_fibroids_pcos, services_data_evidence_batches_batch_04_normal_variation, services_data_evidence_batches_batch_05_pid, services_data_evidence_batches_batch_06_ovarian_cyst_uti, services_data_evidence_batches_batch_07_perimenopause_sti, services_data_evidence_batches_batch_08_orphans, services_data_evidence_batches_evidence_generated_from_approved_batches, services_data_evidence_batches_make_verify_quotes, knowledge_evidence [INFERRED 0.85]
- **Conversational SFT data pipeline: load files, shape into messages, apply chat template, train** — docs_research_sources_q2_hf_datasets_loading_load_dataset, docs_research_sources_q2_hf_datasets_tabular_csv_csv_builder, docs_research_sources_q2_hf_trl_sft_trainer_docs_preprocess_to_expected_format, docs_research_sources_q2_hf_trl_dataset_formats_conversational_format, docs_research_sources_q2_hf_trl_sft_trainer_docs_chat_template_application, docs_research_sources_q2_hf_trl_sft_trainer_docs_sfttrainer [INFERRED 0.85]
- **Why conditions lack an argues_against row: the documented gap shapes** — services_data_evidence_batches_batch_10_adenomyosis_discharge_elimination_row_audit, services_data_evidence_batches_batch_12_sti_backfill_frequently_silent_condition, services_data_evidence_batches_batch_13_uti_backfill_missing_urine_appearance_feature, services_data_evidence_batches_batch_20_bladder_pain_distinction_with_no_cell, services_data_evidence_batches_batch_18_primary_ovarian_insufficiency_poi_terminology_conflict, services_data_evidence_batches_batch_16_ovarian_cyst_backfill_first_eliminating_row [INFERRED 0.85]
- **Evidence on what fine-tuning forgets and how LoRA trades learning against forgetting** — docs_research_sources_q4_arxiv_2308_08747_catastrophic_forgetting_in_llms_continual_finetuning_catastrophic_forgetting, docs_research_sources_q4_arxiv_2308_08747_catastrophic_forgetting_in_llms_continual_finetuning_diverse_instruction_tuning_mitigation, docs_research_sources_q4_arxiv_2405_09673_lora_learns_less_and_forgets_less_lora_forgets_less, docs_research_sources_q4_arxiv_2405_09673_lora_learns_less_and_forgets_less_learning_forgetting_tradeoff, docs_research_sources_q4_arxiv_2405_09673_lora_learns_less_and_forgets_less_lora_underperforms_full_finetuning [INFERRED 0.85]
- **Honest deletion: revocable sessions, refresh tokens and immediate cascading deletion** — services_backend_context_session, services_backend_context_refresh_token, services_backend_context_access_token, services_backend_context_deletion, services_backend_context_opaque_revocable_sessions [INFERRED 0.85]
- **Human oversight and guardrail controls around conversational diagnostic AI** — docs_research_sources_q5_arxiv_2507_15743_amie_physician_centered_oversight_conversational_diagnostic_ai_abstention_from_individualized_medical_advice, docs_research_sources_q5_arxiv_2507_15743_amie_physician_centered_oversight_conversational_diagnostic_ai_asynchronous_oversight, docs_research_sources_q5_arxiv_2507_15743_amie_physician_centered_oversight_conversational_diagnostic_ai_clinician_cockpit, docs_research_sources_q5_arxiv_2603_08448_conversational_diagnostic_ai_prospective_clinical_feasibility_real_time_human_safety_supervision [INFERRED 0.85]
- **LoRA adapter lifecycle: method, PEFT configuration, SFT training, vLLM serving** — docs_research_sources_q4_arxiv_2106_09685_lora_low_rank_adaptation_of_large_language_models_low_rank_adaptation, docs_research_sources_q4_hf_peft_lora_conceptual_loraconfig, docs_research_sources_q2_hf_trl_sft_trainer_docs_peft_integration, docs_research_sources_q4_vllm_lora_adapters_docs_lora_modules_flag [INFERRED 0.85]
- **Model-judged boundaries that make eval cannot measure (action choice, scope, inform-vs-triage, named condition at EMERGENCY, health-note anchoring)** — docs_adr_0011_controller_free_triage_risk_register, docs_adr_0013_emergency_conclusions_may_name_conditions_wrong_condition_at_emergency_risk, docs_adr_0014_an_off_scope_message_is_declined_not_triaged_false_refusal_risk, docs_adr_0015_a_user_may_keep_a_date_of_birth_and_a_health_note_privacy_and_anchoring_risks, docs_adr_0016_an_in_scope_question_may_be_answered_informationally_inform_versus_triage_boundary_risk [INFERRED 0.85]
- **Multilingual embedding model candidates compared for retrieval** — docs_research_sources_q3_arxiv_2402_03216_bge_m3_embedding_multilingual_multifunctionality_bge_m3, docs_research_sources_q3_arxiv_2402_05672_multilingual_e5_text_embeddings_technical_report_me5_models, docs_research_sources_q3_arxiv_2409_10173_jina_embeddings_v3_multilingual_task_lora_jina_embeddings_v3, docs_research_sources_q3_arxiv_2506_05176_qwen3_embedding_text_embedding_and_reranking_qwen3_embedding_series [INFERRED 0.85]
- **Multilingual embedding model candidates compared for retrieval** — docs_research_sources_q3_modelcard_bge_m3_bge_m3, docs_research_sources_q3_modelcard_multilingual_e5_large_multilingual_e5_large, docs_research_sources_q3_modelcard_jina_embeddings_v3_jina_embeddings_v3, docs_research_sources_q3_modelcard_qwen3_embedding_0_6b_qwen3_embedding_0_6b, docs_research_sources_q3_modelcard_qwen3_embedding_8b_qwen3_embedding_8b, docs_research_sources_q3_docs_cohere_embed_embed_multilingual_v3_0, docs_research_sources_q3_docs_openai_embeddings_text_embedding_3_large, docs_research_sources_q3_pricing_voyage_ai_voyage_4_large [INFERRED 0.85]
- **Default create-next-app public assets (framework logos and stock icons)** — services_frontend_public_file, services_frontend_public_globe, services_frontend_public_next, services_frontend_public_vercel, services_frontend_public_window [INFERRED 0.85]
- **Evaluation methods for open-ended medical LLM output beyond exam benchmarks** — docs_research_sources_q1_arxiv_2505_08775_healthbench_evaluating_llms_towards_improved_human_health_physician_written_rubric_evaluation, docs_research_sources_q1_arxiv_2505_08775_healthbench_evaluating_llms_towards_improved_human_health_model_based_grader, docs_research_sources_q1_arxiv_2505_08775_healthbench_evaluating_llms_towards_improved_human_health_worst_at_k_reliability, docs_research_sources_q1_arxiv_2505_23802_medhelm_holistic_evaluation_of_llms_for_medical_tasks_llm_jury, docs_research_sources_q1_arxiv_2505_23802_medhelm_holistic_evaluation_of_llms_for_medical_tasks_clinician_validated_taxonomy [INFERRED 0.85]
- **Regulatory tests deciding whether health software is a medical device (EU and US)** — docs_research_sources_q1_eu_mdcg_2019_11_software_qualification_qualification_decision_steps, docs_research_sources_q1_eu_mdcg_2019_11_software_qualification_intended_purpose, docs_research_sources_q1_eu_mdcg_2019_11_software_qualification_rule_11, docs_research_sources_q1_fda_cds_software_guidance_non_device_cds_criteria, docs_research_sources_q1_fda_cds_software_guidance_patient_or_caregiver_cds_is_a_device [INFERRED 0.85]
- **Reranker options (deferred second-stage ranking)** — docs_research_sources_q3_modelcard_bge_reranker_v2_m3_bge_reranker_v2_m3, docs_research_sources_q3_modelcard_bge_reranker_v2_m3_bge_reranker_v2_gemma, docs_research_sources_q3_modelcard_bge_reranker_v2_m3_bge_reranker_v2_minicpm_layerwise, docs_research_sources_q3_modelcard_qwen3_reranker_0_6b_qwen3_reranker_0_6b, docs_research_sources_q3_pricing_voyage_ai_rerank_2_5 [INFERRED 0.85]
- **Source-Traceable Provenance Chain (quote, batch review, verbatim check)** — claude_verification_protocol, context_source_quote, claude_verify_quotes, _claude_skills_herhealth_pipeline_skill_evidence_batches, _claude_skills_clinical_data_authoring_skill_batch_limit, _claude_skills_herhealth_pipeline_skill_ingest_lock [INFERRED 0.85]
- **Environments that serve the herhealth LoRA adapter under vLLM** — docs_runbooks_uni_server_vllm_vllm_start_command, docs_runbooks_dev_vllm_lora_endpoint_vast_ai_dev_endpoint, docs_runbooks_friend_pc_vllm_setup_wsl2_vllm_setup, docs_runbooks_uni_server_vllm_herhealth_lora_adapter, docs_runbooks_dev_vllm_lora_endpoint_hard_constraints_phrasing_only [INFERRED 0.85]
- **AMIE research programme: text OSCE, multimodal OSCE, guardrailed oversight, prospective clinic study** — docs_research_sources_q5_arxiv_2401_05654_amie_towards_conversational_diagnostic_ai, docs_research_sources_q5_arxiv_2505_04653_amie_advancing_conversational_diagnostic_ai_multimodal, docs_research_sources_q5_arxiv_2507_15743_amie_physician_centered_oversight_conversational_diagnostic_ai, docs_research_sources_q5_arxiv_2603_08448_conversational_diagnostic_ai_prospective_clinical_feasibility [INFERRED 0.95]

## Communities (191 total, 27 thin omitted)

### Community 0 - "Turn Context & Rule Assessment"
Cohesion: 0.03
Nodes (58): ReasoningResult, Askable, assess_rules(), build_turn_context(), clause_matches(), condition_support(), ConditionEvidence, discrimination() (+50 more)

### Community 1 - "Deterministic Triage Engine"
Cohesion: 0.06
Nodes (54): ActionCode, TriageEngine, StopReason, escalating_engine(), fired_on_pain(), rule(), test_a_clear_leader_stops(), test_a_feature_no_live_condition_uses_is_not_asked() (+46 more)

### Community 2 - "react"
Cohesion: 0.14
Nodes (37): next, react, nextConfig, ForgotPasswordPage(), AuthLayout(), ResetPasswordForm(), ResetPasswordPage(), SignInForm() (+29 more)

### Community 3 - "cn"
Cohesion: 0.06
Nodes (60): class-variance-authority, lucide-react, radix-ui, DashboardContent(), DashboardPage(), formatElapsed(), stageForElapsed(), ThinkingIndicator() (+52 more)

### Community 4 - "test_vectorstore.py"
Cohesion: 0.09
Nodes (27): Task 1: Shared contract for the index, IndexedPassage, IndexManifest, PassageType, test_indexed_passage_carries_evidence_fields(), test_indexed_passage_rejects_a_malformed_id(), PassageStore, read_manifest() (+19 more)

### Community 5 - "Consultation Session Models"
Cohesion: 0.05
Nodes (32): stored_extraction(), current_language(), Message, _attempt_detail(), _comparison_responders(), _decision_payload(), delete_session(), _evidence_citations() (+24 more)

### Community 6 - "collections_abc"
Cohesion: 0.05
Nodes (26): Task 3: The index build, save, load and search, Commands, Part 1: the index build (`services/data`), Rules that carry over unchanged, Two indexes, DecodingError, _normalise(), evidence_statement_passages() (+18 more)

### Community 7 - "Auth Cookies & Account Routes"
Cohesion: 0.08
Nodes (40): clear_auth_cookies(), set_auth_cookies(), _cycle_summary(), CycleDataPreview, CycleDataStatus, CycleDataSummary, delete_cycle_data(), delete_me() (+32 more)

### Community 8 - "register_user"
Cohesion: 0.07
Nodes (20): normalize_email(), EmailAlreadyRegistered, hash_password(), verify_password(), register_user(), test_normalize_email_lowercases(), test_normalize_email_strips_surrounding_whitespace(), test_normalize_email_two_spellings_match() (+12 more)

### Community 9 - "app/config.py"
Cohesion: 0.07
Nodes (20): answer_model(), comparison_modes_enabled(), decision_model(), knowledge_dir(), openrouter_api_key(), openrouter_model(), page_model(), reasoning_timeout() (+12 more)

### Community 10 - "TriageState"
Cohesion: 0.08
Nodes (7): most_urgent(), _severity(), rank(), rank(), TriageState, test_most_urgent_of_nothing_is_nothing(), test_most_urgent_picks_the_highest_severity()

### Community 11 - "useI18n"
Cohesion: 0.06
Nodes (55): ChatContent(), appendEntry(), handleRetry(), handleSend(), loadModels(), loadSession(), loadSessions(), submitTurn() (+47 more)

### Community 12 - "useAuth"
Cohesion: 0.14
Nodes (26): HowItWorksPage(), OnboardingContent(), OnboardingPage(), AuthGuard(), dismissComplete(), OnboardingWizard(), closeReview(), finishFirstTime() (+18 more)

### Community 13 - "RetrievedPassage"
Cohesion: 0.06
Nodes (16): Task 8: The recall check, 1. The extract step, 2. The decide step, 3. The answer step, A turn, end to end, The chat model, The inform gate (new), Goals (+8 more)

### Community 14 - "Triage CLI"
Cohesion: 0.04
Nodes (45): as_json(), ask_at_the_terminal(), build_parser(), _coerce(), find_knowledge_dir(), _force_utf8_output(), load_case(), main() (+37 more)

### Community 15 - "Knowledge Schema Contracts"
Cohesion: 0.09
Nodes (52): Condition, EvidenceRow, Feature, Weights, action_defs(), evidence_row(), feature(), knowledge_base() (+44 more)

### Community 16 - "Dashboard & Account Settings"
Cohesion: 0.14
Nodes (34): sonner, AccountSettingsContent(), AccountSettingsPage(), CycleDataCard(), DeleteAccountSection(), HealthDetailsForm(), isoDateYearsAgo(), ProfileSettingsForm() (+26 more)

### Community 17 - "Email Verification"
Cohesion: 0.11
Nodes (27): serialize_per_email(), EmailSender, _issue_code(), request_verification_resend(), _send(), send_verification_code(), verify_email(), IncorrectVerificationCode (+19 more)

### Community 18 - "herhealth_contracts/knowledge.py"
Cohesion: 0.14
Nodes (13): ActionDefinition, Actions, Clause, ComparisonOp, ConditionsFile, FeatureKind, FeaturesFile, _KnowledgeModel (+5 more)

### Community 19 - "ReasoningAttempt"
Cohesion: 0.08
Nodes (11): Done when, Global Constraints, Reasoning Chain Implementation Plan, Review Focus, AttemptOutcome, ReasoningAttempt, LangChainFeatureExtractor, LangChainReasoningClient (+3 more)

### Community 20 - "HealthBench & FDA CDS Guidance"
Cohesion: 0.05
Nodes (37): HealthBench: Evaluating Large Language Models Towards Improved Human Health (arXiv 2505.08775), Context-seeking theme (594 examples, 11.9%), Emergency referrals theme (482 examples, 9.6%), HealthBench Consensus (34 physician-consensus criteria, 3,671 examples), HealthBench Hard (top score 32%), Physician baselines with and without model assistance, Responding under uncertainty theme (1,071 examples, 21.4%), HealthBench seven themes and five axes (+29 more)

### Community 21 - "Account Route Tests"
Cohesion: 0.08
Nodes (42): _cookie_attributes(), _register(), _register_and_verify(), test_a_subsequent_request_identifies_the_signed_in_user(), test_google_sign_in_not_configured_is_service_unavailable(), test_me_without_a_session_is_unauthorized(), test_patch_me_rejects_overlong_display_name(), test_patch_me_updates_display_name() (+34 more)

### Community 22 - "Password Reset Errors"
Cohesion: 0.13
Nodes (26): IncorrectPasswordResetCode, PasswordResetCodeExpired, TooManyPasswordResetRequests, PasswordResetCode, _issue_code(), _password_credential(), request_password_reset(), reset_password() (+18 more)

### Community 23 - "email_sender.py"
Cohesion: 0.16
Nodes (15): _render_password_reset(), _render_verification(), _RenderedEmail, _code_block(), _copy(), _email(), email_subject(), password_reset_email() (+7 more)

### Community 24 - "Triage Route Tests"
Cohesion: 0.11
Nodes (26): load_knowledge_base(), _build_client(), _register_and_sign_in(), _scripted_agent(), StaticRetrievalClient, test_a_declined_message_leaves_the_session_open(), test_a_second_users_session_id_is_not_found(), test_a_turn_reports_and_stores_the_backend_that_answered() (+18 more)

### Community 26 - "Threshold Analysis"
Cohesion: 0.08
Nodes (22): EvidenceStrength, run_thresholds(), analyse(), Combination, eliminating_rows_needed(), reachable_scores(), rules_out_ceiling(), test_a_threshold_in_a_gap_is_not_fragile() (+14 more)

### Community 27 - "Knowledge Validation"
Cohesion: 0.07
Nodes (50): test_knowledge_base_loads(), render_feature_vocabulary(), run_validate(), _check_conditions(), _check_evidence(), check_knowledge_base(), _check_nothing_is_dead_weight(), _check_probe_languages() (+42 more)

### Community 28 - "test_provenance.py"
Cohesion: 0.14
Nodes (16): File Structure, Task 2: The native launcher, Task 5: Bring the stack up on the campus box, Task 6: Replace the old launcher and update the docs, Verdict, check(), test_a_heading_counts_as_source_text(), test_a_paraphrase_is_not_verified() (+8 more)

### Community 29 - "Conversational Diagnostic AI Papers"
Cohesion: 0.07
Nodes (30): Towards Conversational Diagnostic AI (Tu et al., arXiv 2401.05654), AMIE (Articulate Medical Intelligence Explorer), Clinical history-taking, Diagnostic dialogue evaluation axes (history-taking, diagnostic accuracy, management reasoning, communication, empathy), Randomized double-blind crossover remote OSCE (149 scenarios, 20 PCPs), MediQ: Question-Asking LLMs and a Benchmark for Reliable Interactive Clinical Reasoning (Li et al., NeurIPS 2024), CRAFT-MD dataset, MediQ Expert System (+22 more)

### Community 30 - "Ingest Config & Robots"
Cohesion: 0.06
Nodes (15): DuplicateTargetError, FetchPlan, load_plan(), _reject_duplicates(), Target, _fetch_one(), http_get(), _utc_now() (+7 more)

### Community 31 - "TriageDecision Schema"
Cohesion: 0.05
Nodes (23): TriageDecision, test_a_clarifying_question_needs_no_citation(), test_a_decision_grounded_in_nothing_is_refused(), test_a_decline_may_carry_nothing_but_its_rationale(), test_a_decline_needs_no_grounding(), test_a_red_flag_alone_still_grounds_a_decision(), test_a_red_flag_conclusion_below_urgent_may_not_name_conditions(), test_an_ask_requires_a_feature_and_a_question() (+15 more)

### Community 32 - "Database Migrations"
Cohesion: 0.11
Nodes (10): upgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade() (+2 more)

### Community 33 - "commands.py"
Cohesion: 0.08
Nodes (17): Task 4: The `index`, `search` and `propose` commands on the new store, _load_embeddings(), _load_store(), _report_fetch(), run_build(), run_clean(), run_eval(), run_fetch() (+9 more)

### Community 34 - "Password Reset Codes"
Cohesion: 0.09
Nodes (21): codes_match(), generate_code(), hash_code(), codes_match(), generate_code(), hash_code(), test_codes_match_is_false_for_a_different_code(), test_codes_match_is_false_under_a_different_secret() (+13 more)

### Community 35 - "test_cli.py"
Cohesion: 0.05
Nodes (44): Diagram, find_diagrams(), heading_before(), kind_of(), main(), slugify(), write(), _bucket() (+36 more)

### Community 36 - "Phase-1 Conditions & Features"
Cohesion: 0.10
Nodes (36): SELF_CARE (severity 0), Endometriosis [ROUTINE_APPOINTMENT], Normal menstrual variation [SELF_CARE], Polyendocrine metabolic ovarian syndrome (PMOS), formerly polycystic ovary syndrome (PCOS) [ROUTINE_APPOINTMENT], Uterine fibroids [ROUTINE_APPOINTMENT], evidence.csv (sparse condition-feature evidence grid), features.yaml (everything the system may ask about), Dark velvety patches of skin (acanthosis_nigricans) (+28 more)

### Community 37 - "Session Policy & Refresh"
Cohesion: 0.09
Nodes (32): InvalidAccessToken, InvalidSession, Session, end_all_sessions(), end_session(), get_active_session(), refresh_session(), _revoke() (+24 more)

### Community 38 - "Agent Context Tests"
Cohesion: 0.08
Nodes (30): DecisionType, Message, ScriptedReasoningClient, StaticRetrievalClient, _user_text(), agent_with(), ask(), CapturingReasoning (+22 more)

### Community 39 - "Sign-In Throttling & Locks"
Cohesion: 0.09
Nodes (21): InvalidCredentials, InvalidDisplayName, InvalidHealthNote, NoPasswordCredential, TooManySignInAttempts, SignInFailure, _authenticate(), sign_in() (+13 more)

### Community 40 - "Evaluation Metrics"
Cohesion: 0.11
Nodes (29): score(), outcome(), test_a_less_urgent_answer_is_under_triage(), test_a_more_urgent_answer_is_over_triage_not_under(), test_a_rate_over_nothing_is_none_not_zero(), test_a_self_care_label_cannot_be_under_triaged(), test_agreement_needs_more_than_one_variant_to_mean_anything(), test_an_empty_run_passes_no_gate() (+21 more)

### Community 41 - "Dialogue Runner"
Cohesion: 0.06
Nodes (32): export_bootstrap_dataset(), main(), personas_from_knowledge_base(), _phrase_answer(), _phrase_conclusion(), transcript_to_conversation(), write_jsonl(), run_consultation() (+24 more)

### Community 42 - "Embedding Benchmarks (MTEB, BGE-M3)"
Cohesion: 0.08
Nodes (28): MTEB: Massive Text Embedding Benchmark (arXiv 2210.07316), BEIR zero-shot retrieval benchmark, Eight MTEB task types (bitext mining, classification, clustering, pair classification, reranking, retrieval, STS, summarization), MTEB benchmark (8 tasks, 58 datasets, 112 languages), M3-Embedding / BGE-M3 paper (arXiv 2402.03216), BGE-M3 (M3-Embedding) model, MIRACL multilingual retrieval benchmark, MKQA cross-lingual retrieval benchmark (+20 more)

### Community 43 - "test_evaluation_runner.py"
Cohesion: 0.08
Nodes (27): CanonicalCase, CaseLabel, CaseVariant, _EvaluationModel, EvaluationSet, Language, RegisterStyle, run_case() (+19 more)

### Community 44 - "KnowledgeBase"
Cohesion: 0.21
Nodes (33): Task 3: The inform gate, KnowledgeBase, TriageAgent, ask(), base(), conclude_urgent(), ExplodingWriter, Extractor (+25 more)

### Community 45 - "Red Flags & Urgent Actions"
Cohesion: 0.16
Nodes (30): ADR 0004: Severe pelvic pain is urgent, not emergency, EMERGENCY (severity 3), URGENT_SAME_DAY (severity 2), Bleeding after menopause (bleeding_after_menopause), Bleeding between periods (bleeding_between_periods), Severity of pelvic pain (pelvic_pain_severity), How long periods have been absent (periods_stopped_duration), Pregnancy status (pregnancy_status) (+22 more)

### Community 46 - "Routine-Urgency Conditions"
Cohesion: 0.16
Nodes (28): ROUTINE_APPOINTMENT (severity 1), Bladder pain syndrome (interstitial cystitis) [ROUTINE_APPOINTMENT], Hypothyroidism (underactive thyroid) [ROUTINE_APPOINTMENT], Infertility (difficulty conceiving) [ROUTINE_APPOINTMENT], Inherited bleeding disorder (e.g. Von Willebrand disease) [ROUTINE_APPOINTMENT], Iron-deficiency anaemia [ROUTINE_APPOINTMENT], Perimenopause and menopause [ROUTINE_APPOINTMENT], Primary ovarian insufficiency (early or premature menopause) [ROUTINE_APPOINTMENT] (+20 more)

### Community 47 - "AWS Deploy & Agent Docs"
Cohesion: 0.08
Nodes (27): Agent docs: domain docs, Multi-context domain docs: Triage and Accounts bounded contexts, Runbook: deploying to AWS (one EC2 host), Caddy Let's Encrypt certificates and rate limits, deploy.sh: migrate, switch release, health-check through Caddy, auto-rollback, GitHub OIDC deploy, plan and index roles, Pre-demo checklist, Retrieval image carries unused CUDA libraries (+19 more)

### Community 48 - "Fetch Stage Tests"
Cohesion: 0.09
Nodes (30): fetch_all(), forbidden(), make_plan(), make_target(), recording(), responds(), transport(), test_an_empty_file_loads_to_an_empty_plan() (+22 more)

### Community 49 - "httpx"
Cohesion: 0.05
Nodes (53): Task 4: The smoke script, _chat(), check_chat(), body(), check_embeddings(), body(), check_health(), body() (+45 more)

### Community 50 - "Frontend Dependencies"
Cohesion: 0.11
Nodes (18): clsx, eslint, eslint-config-next, react-dom, @react-oauth/google, shadcn, tailwind-merge, tailwindcss (+10 more)

### Community 51 - "Account Deletion"
Cohesion: 0.08
Nodes (15): delete_user_account(), Base, CycleData, PasswordResetSend, VerificationCodeSend, is_send_locked_out(), record_send(), is_send_locked_out() (+7 more)

### Community 52 - "Profile Details Validation"
Cohesion: 0.10
Nodes (18): InvalidDateOfBirth, normalize_health_note(), validate_date_of_birth(), _register_and_sign_in(), test_a_blank_health_note_clears_rather_than_storing_empty(), test_a_future_date_of_birth_is_refused(), test_a_health_note_can_be_deleted_without_closing_the_account(), test_a_health_note_keeps_her_own_line_breaks() (+10 more)

### Community 53 - "en.ts"
Cohesion: 0.05
Nodes (57): account, onboarding, ar, auth, common, errors, nav, chat (+49 more)

### Community 54 - "HTML Cleaning Tests"
Cohesion: 0.11
Nodes (19): is_link_list(), paragraphs(), test_a_clinical_heading_is_not_a_link_list(), test_chrome_wrappers_are_removed_by_class(), test_decomposing_a_wrapper_does_not_break_the_walk(), test_duplicate_paragraphs_within_a_section_are_dropped(), test_inline_markup_does_not_leave_a_space_before_punctuation(), test_link_list_headings_are_recognised() (+11 more)

### Community 55 - "README.md"
Cohesion: 0.04
Nodes (68): Clinical Data Authoring Skill, HerHealth Data Pipeline Skill, Evidence Batch YAML Review Gate (approved: true), ingest.lock.jsonl (url, sha256, licence per fetched document), Data Pipeline Stages (fetch, clean, evidence, validate, tables), RawStore Immutable Raw Snapshots, HerHealth Monorepo Conventions Skill, Source Ingestion Skill (+60 more)

### Community 56 - "QLoRA Adapter herhealth-lora-v2 (phrasing-only)"
Cohesion: 0.26
Nodes (10): bootstrap_multi_turn.jsonl Retrain Bootstrap Data, AWS Deploy Pipeline (ECR, S3, SSM, single EC2, Caddy), ft_corpus_v1.jsonl Adaptation Corpus (2,700 rows), QLoRA Adapter herhealth-lora-v2 (phrasing-only), Qwen/Qwen3.5-9B Base Model (multimodal hybrid), Training Repo Mazen-Bahgat/HerHealthGPT (branch hassan-pc), FallbackReasoningClient (base model fallback), Fine-Tuned Tab (campus vLLM LoRA 'herhealth') (+2 more)

### Community 57 - "Raw Store Lockfile"
Cohesion: 0.11
Nodes (24): RawStore, read_lock(), write_lock(), record(), test_a_different_date_is_a_different_location(), test_documents_can_be_read(), test_documents_ignores_other_dates(), test_documents_is_empty_when_nothing_is_stored() (+16 more)

### Community 58 - "types.ts"
Cohesion: 0.08
Nodes (32): ADR-0018, ChatMessage(), ChatMessageProps, paragraphs(), ADR-0016, CitedSources(), CitedSourcesProps, distinctSources() (+24 more)

### Community 59 - "agent.py"
Cohesion: 0.05
Nodes (28): format_query(), _manifest(), test_manifest_rejects_what_a_reader_could_not_trust(), test_manifest_round_trips_through_json(), test_query_instruction_format_is_the_one_the_embedder_expects(), build_retrieval_query(), _to_messages(), _available_ids_hint() (+20 more)

### Community 60 - "Google Sign-In"
Cohesion: 0.13
Nodes (10): GoogleSignInNotConfigured, GoogleTokenInvalid, GoogleOAuthTokenVerifier, UnconfiguredGoogleTokenVerifier, test_google_oauth_verifier_defaults_email_verified_to_false_when_absent(), test_google_oauth_verifier_rejects_a_malformed_token(), test_google_oauth_verifier_rejects_a_token_missing_required_claims(), test_google_oauth_verifier_rejects_an_invalid_token() (+2 more)

### Community 61 - "Knowledge Table Rendering"
Cohesion: 0.08
Nodes (20): run_evidence(), run_tables(), Batch, BatchError, build_evidence_csv(), load_batches(), _reject_duplicates(), write_rows() (+12 more)

### Community 62 - "El Saddik Lab Papers"
Cohesion: 0.10
Nodes (19): TextureMeDefect: LLM-based Synthetic Railway Defect Texture on Mobile Devices (IEEE ICCE 2025), Abdulmotaleb El Saddik, Fine-tuned GPT-3 on synthetic defect-texture dataset, IEEE International Conference on Consumer Electronics (ICCE), InstructPix2Pix (image+text editing model), Multimodal User Interaction Interface (MUII), Rahatara Ferdousi, SDXL (text-to-image model) (+11 more)

### Community 63 - "The knowledge base, explained"
Cohesion: 0.04
Nodes (56): ADR 0002: Nested knowledge files are YAML; the evidence grid is CSV, ADR 0003: evidence.csv is generated from approved batches, make evidence (deterministic evidence.csv build), Code guide, Data pipeline: fetch -> clean -> build -> validate -> eval, Evaluation harness (herhealth-eval / make eval), gated vs reported metrics, fetch_all policy order: licence guard, already present, dry run, fetch, Immutable TriageState / Decision / StopReason (+48 more)

### Community 64 - "accounts.ts"
Cohesion: 0.06
Nodes (64): ADR-0019, handleSubmit(), handleSubmit(), handleSubmit(), handleResend(), handleSubmit(), CycleDataImport(), errorMessage() (+56 more)

### Community 65 - "Plausibility Scoring"
Cohesion: 0.10
Nodes (18): log_odds_for(), plausibility(), test_a_rules_out_that_cannot_rule_out_is_rejected(), test_clamp_is_wide_enough_to_be_irrelevant_in_practice(), test_conditions_do_not_compete(), test_everything_can_be_implausible_at_once(), test_it_does_not_overflow_on_a_large_score(), test_it_is_monotonic() (+10 more)

### Community 66 - "ICD-11 Lookup"
Cohesion: 0.10
Nodes (9): run_icd(), credentials_from_env(), fetch_token(), IcdError, IcdProposal, propose_codes(), search_icd(), _strip_markup() (+1 more)

### Community 67 - "Evaluation CLI"
Cohesion: 0.09
Nodes (15): as_json(), build_parser(), _line(), main(), render(), _agreement(), CaseOutcome, Metrics (+7 more)

### Community 68 - "test_chain.py"
Cohesion: 0.08
Nodes (45): Task 1: The decide step on LangChain, Task 2: The extract step, Task 4: The answer step, Task 6: Removing the selector from the frontend, Task 7: The decision measurement as a command, Task 8: Run it, switch the mode, record the result, Tasks, carry_warning_lines() (+37 more)

### Community 69 - "Triage Glossary"
Cohesion: 0.09
Nodes (27): CONTEXT.md Triage Glossary, Action Code, Burden, Clarification, Clause, Condition, Differential, Escalation (+19 more)

### Community 70 - "Weights & Action Codes"
Cohesion: 0.11
Nodes (16): ADR 0005: plausibility is an independent logistic, ADR 0009: rules_out does not override accumulated support, rules_out does not eliminate regardless of accumulated support, actions.yaml (four urgency actions), knowledge/ README, weights.yaml (ordinal-to-log-odds mapping and stopping thresholds), argues_against (-0.5 log-odds), max_questions (6) (+8 more)

### Community 71 - "Condition Provenance Repair"
Cohesion: 0.13
Nodes (15): _decision_validator(), validate(), drop_unknown_conditions(), validate_against_knowledge_base(), conclude(), test_a_decision_with_only_real_conditions_is_returned_unchanged(), test_a_decline_is_unaffected(), test_a_name_with_a_space_is_dropped_rather_than_failing_the_decision() (+7 more)

### Community 72 - "Profile & Health Note"
Cohesion: 0.17
Nodes (11): HealthNote, User, clear_health_note(), health_note_for(), _load_user(), normalize_display_name(), update_date_of_birth(), update_display_name() (+3 more)

### Community 73 - "locale-provider.tsx"
Cohesion: 0.09
Nodes (37): next-themes, AppShell(), AppLayout(), GlobalError(), arabic, generateMetadata(), inter, RootLayout() (+29 more)

### Community 74 - "shadcn Component Config"
Cohesion: 0.09
Nodes (21): aliases, components, hooks, lib, ui, utils, iconLibrary, menuAccent (+13 more)

### Community 75 - "test_language.py"
Cohesion: 0.07
Nodes (23): _invoke(), ReasoningUnavailable, _text(), PlainChatResponder, detect_language(), language_instruction(), _language_of(), _Chat (+15 more)

### Community 76 - "decision_eval.py"
Cohesion: 0.12
Nodes (25): load_questions(), load_scripts(), main(), Question, _rows(), run_first_turns(), run_script(), Script (+17 more)

### Community 77 - "uni server vllm"
Cohesion: 0.14
Nodes (21): CLAUDE.md Project Spec (binding), Method: transcripts read back from the messages table of the deployed stack, Runbook: herhealth LoRA dev endpoint, Known quirks: thinking mode on by default, code-switching, register variance, Ephemeral vast.ai vLLM dev endpoint for the herhealth LoRA, vllm serve command with --enable-lora and --max-model-len 16384, Runbook: vLLM + LoRA on a friend's GPU PC, vllm triage mode with automatic OpenRouter fallback (+13 more)

### Community 78 - "cards"
Cohesion: 0.13
Nodes (7): _arrow(), feature_reports(), FeatureReport, render_condition_cards(), render_feature_cards(), write_cards(), run_cards()

### Community 79 - "conditions"
Cohesion: 0.23
Nodes (13): ADR 0001: Source traceability replaces clinician review, ADR 0006: a condition may cite one source if it says why, conditions.yaml (everything the system may suspect), Adenomyosis [ROUTINE_APPOINTMENT], Bacterial vaginosis [ROUTINE_APPOINTMENT], Vaginal thrush (yeast infection) [SELF_CARE], Unusual vaginal discharge (abnormal_discharge), What the discharge looks like (discharge_appearance) (+5 more)

### Community 80 - "Research 0001: Reconsidering the deterministic controller (LLM triage architecture)"
Cohesion: 0.04
Nodes (58): Silver annotation (not clinician-adjudicated), NHS three-page conflict on severe pelvic pain (pelvic pain, period pain, ovarian cyst pages), sudden_severe_pelvic_pain red flag escalates to EMERGENCY, Adenomyosis: the only condition with no corroborating source (NHS only), Two-source rule for conditions, ADR 0007: what the first real consultations showed, Deterministic stopping controller (TriageEngine.should_stop), Finding 4: rule 4 returns the top condition's action, not the most urgent live one (latent under-triage, xfail-pinned) (+50 more)

### Community 81 - "google_sign_in.py"
Cohesion: 0.14
Nodes (17): GoogleEmailNotVerified, GoogleIdentity, GoogleTokenVerifier, _credential_for_subject(), _sign_in_as(), sign_in_with_google(), Credential, CredentialKind (+9 more)

### Community 82 - "test age bands"
Cohesion: 0.16
Nodes (8): age_band_for(), age_in_years(), _allowed_age_bands(), test_a_birthday_on_29_february_does_not_crash_in_a_non_leap_year(), test_age_is_not_incremented_until_the_birthday(), test_each_band_is_reachable(), test_every_allowed_value_is_reachable(), test_every_band_this_module_returns_is_a_real_allowed_value()

### Community 83 - "test_retrieval.py"
Cohesion: 0.11
Nodes (17): build_embeddings(), RetrievalSettings, VllmReranker, _reranker(), _settings_for(), test_a_non_numeric_slot_count_names_the_variable(), test_an_explicit_argument_overrides_the_setting(), test_an_unrecognised_reranker_setting_names_the_variable() (+9 more)

### Community 84 - "README"
Cohesion: 0.23
Nodes (14): conversation.svg (hand holding a phone showing chat bubbles and a typing indicator), error.svg (person beside a large warning triangle with exclamation mark over a browser window), not-found.svg (person standing in a frame holding a tile, with a circular refresh/retry badge), onboarding.svg (unDraw 'medicine': clinicians in white coats with a potted plant against a tiled backdrop), Illustrations README — download these by hand, Brand primary colour #9F1239 (--primary in globals.css), Illustration component (renders nothing when the file is missing), Licence-driven source exclusions (NICE CKS, RCOG, ACOG, UMLS) per CLAUDE.md (+6 more)

### Community 85 - "tsconfig"
Cohesion: 0.11
Nodes (18): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+10 more)

### Community 86 - "CONTEXT"
Cohesion: 0.18
Nodes (13): Accounts bounded context (CONTEXT.md), Access token (Accounts term), Conversation (Accounts term), Credential (Accounts term), Cycle data (Accounts term), Health note (Accounts term), Linking (Accounts term), Message (Accounts term) (+5 more)

### Community 87 - "_write_index"
Cohesion: 0.15
Nodes (23): Review Focus, IndexRefused, load_vector_store(), AxisEmbeddings, _client(), _passage(), test_a_manifest_whose_width_disagrees_with_the_vectors_is_refused(), test_a_missing_index_is_refused_with_the_path() (+15 more)

### Community 88 - "test_serve_models.py"
Cohesion: 0.17
Nodes (18): Review Focus, _alive(), Box, box(), _free_port(), test_a_pid_file_naming_another_live_process_is_stale(), test_check_reports_every_service_when_nothing_runs(), test_print_chat_carries_the_proven_flags() (+10 more)

### Community 89 - "retrieval_eval.py"
Cohesion: 0.13
Nodes (19): build_query(), evaluate(), Evaluation, _first(), _is_source_sentence(), _is_statement(), main(), _normalise() (+11 more)

### Community 90 - "check repo hygiene"
Cohesion: 0.14
Nodes (21): check_env_filename(), check_line_length(), check_root_entry(), check_secrets(), check_text_posing_as_binary(), Finding, inspect(), is_binary() (+13 more)

### Community 91 - "ADR 0011: controller-free triage"
Cohesion: 0.07
Nodes (30): ADR 0010: Multilingual embeddings beat Arabic-specific ones; the chunk is a sentence, Alsubhi et al., Optimizing RAG Pipelines for Arabic (arXiv:2506.06339), multilingual-e5-large (named fallback, 70.31), Unverified: French coverage and reproductive-health domain transfer, ADR 0011: controller-free triage, ADR 0011 migration checklist (10 steps), services/model: vLLM serving bge-m3 plus base model with QLoRA adapter, consultation_session and message tables (session persistence) (+22 more)

### Community 92 - "FLOW EXPLAINED"
Cohesion: 0.12
Nodes (20): The new flow, explained, Agentic RAG loop (retrieve, reason, ask or conclude, repeat), Backend orchestrator, Embedding / semantic search model (bge-m3), Licensing filter at live search time (unfinished), Reasoning model (QLoRA fine-tuned model + base), Retrieval index (source sentences + evidence.csv rows as sentences), Session store (Postgres) (+12 more)

### Community 93 - "LangChainRetrievalClient"
Cohesion: 0.10
Nodes (9): Task 7: Wire the retriever into the backend and remove the HTTP client, Configuration, Part 2: the retriever (backend), LangChainRetrievalClient, RetrievalUnavailable, _to_retrieved(), TriageRetriever, DownEmbeddings (+1 more)

### Community 94 - "LangChainAnswerWriter"
Cohesion: 0.17
Nodes (14): LangChainAnswerWriter, shape_page(), _without_warning_lines(), _Chat, _passage(), _sections(), test_a_heading_with_text_on_its_line_is_split_so_it_renders(), test_a_page_with_internal_wording_is_refused() (+6 more)

### Community 95 - "cycle_data.py"
Cohesion: 0.13
Nodes (10): CycleSummary, _guarded(), _one_bucket(), Period, _periods(), prefill(), render_cycle_background(), summarize() (+2 more)

### Community 96 - "datetime"
Cohesion: 0.19
Nodes (12): _cycles(), _prefilled(), test_a_logged_symptom_answers_yes(), test_absence_is_never_read_as_no(), test_cycles_across_buckets_answer_regularity_but_not_length(), test_cycles_within_21_to_35_days_are_regular(), test_fewer_than_three_cycles_answer_nothing_about_the_pattern(), test_long_cycles_are_answered_as_long_and_irregular() (+4 more)

### Community 97 - "q2 hf trl dataset formats"
Cohesion: 0.25
Nodes (13): HF TRL docs: Dataset formats and types (research source q2), Conversational dataset format (messages with role/content), TRL dataset types (language modeling, prompt-only, prompt-completion, preference, unpaired preference, stepwise supervision), Harmony response format (OpenAI GPT OSS), Prompt-completion dataset type, Standard dataset format (plain text columns), Tool-calling datasets (tools column, tool_calls, get_json_schema), HF TRL docs: SFT Trainer (research source q2) (+5 more)

### Community 98 - "Security 0001: injected postcss payload and leaked env backup"
Cohesion: 0.11
Nodes (18): JupyterHub idle culling kills the server and rotates the token, Security 0001: injected postcss payload and leaked env backup, scripts/check_repo_hygiene.py: five hygiene rules, The history purge with git filter-branch, verified in a mirror, Branches still carrying the payload, Issue 1: foreign crypto/blockchain code injected into postcss.config.mjs, Issue 2: backend.env.bak committed with live credentials, Re-infection was a merge of a stale branch, not malware (+10 more)

### Community 99 - "cycle_import.py"
Cohesion: 0.15
Nodes (8): _apple_export_in(), extract_cycle_data(), _from_apple_health(), _from_model(), _one_per_day(), _read_apple_records(), _text_of(), CycleImportFailed

### Community 100 - "thresholds"
Cohesion: 0.18
Nodes (3): robust_midpoint(), ThresholdPlacement, test_the_midpoint_is_taken_in_log_odds()

### Community 101 - "package"
Cohesion: 0.14
Nodes (14): dependencies, class-variance-authority, clsx, lucide-react, next, next-themes, radix-ui, react (+6 more)

### Community 102 - "test accounts deletion"
Cohesion: 0.17
Nodes (10): Base, ConsultationSession, _build_client(), _count_for_user(), _count_messages_for_user(), deletion_client(), _register_and_sign_in(), _scripted_agent() (+2 more)

### Community 103 - "cycle.py"
Cohesion: 0.17
Nodes (13): ExtractionMethod, FlowLevel, TrackerSymptom, _read(), test_a_bad_template_row_is_refused_not_guessed(), test_a_model_reply_with_nothing_usable_is_refused(), test_a_zip_without_an_apple_export_is_refused(), test_an_unknown_format_needs_the_model() (+5 more)

### Community 104 - "serve-models.sh"
Cohesion: 0.23
Nodes (17): check(), clean(), field(), is_sha(), pid_file(), pid_of(), port_open(), preflight() (+9 more)

### Community 105 - "q3 modelcard bge m3"
Cohesion: 0.26
Nodes (8): BAAI/bge-m3 model card - Hugging Face capture, BAAI/bge-m3 embedding model, BGE M3-Embedding paper (arXiv 2402.03216), BM25 lexical baseline, FlagEmbedding library, MIRACL multilingual retrieval benchmark, MLDR long-document retrieval dataset (13 languages), BAAI/bge-reranker-v2-m3

### Community 106 - "q4 arxiv 2308.08747 catastrophic forgett"
Cohesion: 0.19
Nodes (5): An Empirical Study of Catastrophic Forgetting in LLMs During Continual Fine-tuning (arXiv 2308.08747), Continual instruction tuning (five sequential instruction tasks), General-knowledge retention evaluation (domain knowledge, reasoning, reading comprehension, bias), LoRA Learns Less and Forgets Less (TMLR 08/2024, arXiv 2405.09673), Continued pretraining vs instruction finetuning regimes

### Community 107 - "sources"
Cohesion: 0.21
Nodes (10): Pelvic inflammatory disease (PID) [URGENT_SAME_DAY], Fever (fever), sources.yaml (provenance, licence, precedence), Centers for Disease Control and Prevention (precedence 4, available), passages.parquet (ingested passage corpus), RobotsPolicy (robots.txt check before every fetch), Evidence batch 05: pid (approved 2026-08-04), Evidence batch 15: pelvic inflammatory disease backfill (+2 more)

### Community 108 - "knowledge"
Cohesion: 0.19
Nodes (6): Done when, Global Constraints, Retrieval on LangChain Implementation Plan, Source, test_permissions_follow_status(), test_precedence_ranks_sources_that_are_not_yet_usable()

### Community 109 - "main.py"
Cohesion: 0.16
Nodes (6): cors_origins(), database_url(), language_from_accept_language(), set_current_language(), create_app(), interface_language()

### Community 111 - "test_email_sender.py"
Cohesion: 0.18
Nodes (7): ConsoleEmailSender, test_build_email_sender_defaults_to_console(), test_build_email_sender_rejects_an_unrecognised_kind(), test_build_email_sender_selects_console_explicitly(), test_build_email_sender_selects_ses(), test_console_email_sender_logs_the_code(), test_console_email_sender_writes_styled_password_reset_preview()

### Community 112 - "check_password_strength"
Cohesion: 0.20
Nodes (9): check_password_strength(), PasswordTooWeak, test_acceptable_password_is_not_rejected(), test_common_password_check_is_case_insensitive(), test_common_password_is_rejected_with_a_reason(), test_other_top_breach_corpus_passwords_are_rejected(), test_password_at_the_minimum_length_is_accepted(), test_too_long_password_is_rejected_with_a_reason() (+1 more)

### Community 113 - "herhealth_data/provenance.py"
Cohesion: 0.16
Nodes (4): Corpus, QuoteCheck, summarise(), verify_quotes()

### Community 115 - "Step 3b: connecting the production backend to the campus models"
Cohesion: 0.12
Nodes (16): A question to settle before going live, Behaviour when the campus box is unreachable, Capacity, Decision 1: how the EC2 host reaches the pod, Decision 2: one address or three, Decision 3: how the index reaches the EC2 host, Decisions needed from the repo owner, Done when (+8 more)

### Community 116 - "README"
Cohesion: 0.12
Nodes (11): data workflow job: check (make lint, test, validate, triage-all), Case: heavy prolonged periods, early forties, Controller demonstration cases README, Stopping rule 5: the question budget, Case: answers nothing (the floor case), The benchmark, as it arrived (README), Evaluation pipeline: eval/benchmark -> make eval-cases -> eval/cases -> make eval -> build/eval, Silver annotations, not clinician-adjudicated (+3 more)

### Community 117 - "CycleExtraction"
Cohesion: 0.16
Nodes (5): CycleDay, CycleExtraction, test_the_schema_has_no_free_text_field(), strings(), _validated()

### Community 118 - "clean"
Cohesion: 0.29
Nodes (4): clean_html(), _strip_boilerplate(), test_headings_split_sections(), test_replacement_characters_are_refused_not_kept()

### Community 119 - "test_cycle.py"
Cohesion: 0.29
Nodes (11): _day(), _extraction(), test_a_day_logged_twice_is_refused(), test_a_day_that_logs_nothing_is_refused(), test_a_normal_extraction_validates(), test_a_symptom_outside_the_vocabulary_is_refused(), test_an_export_with_no_usable_days_is_refused(), test_days_are_put_in_date_order() (+3 more)

### Community 120 - "0005 plausibility is an independent logi"
Cohesion: 0.20
Nodes (7): plausibility_floor (0.05, -2.94 log-odds), Softmax across the differential (rejected option), stop_margin fires less often under a logistic; controller leans on max_questions, Weights._rules_out_must_actually_rule_out validator, Search B: feature/vocabulary mapping from prose to features.yaml (not built), Know Your Limits: A Survey of Abstention in LLMs (arXiv:2407.18418), Documentation drift between CLAUDE.md counts and files on disk (fixed)

### Community 121 - "test_cycle_data_routes.py"
Cohesion: 0.36
Nodes (10): _preview(), _recent_cycles(), _register_and_sign_in(), _template(), test_a_confirmed_extraction_cannot_smuggle_text_in(), test_a_preview_stores_nothing(), test_an_unknown_format_without_a_model_is_not_configured(), test_confirming_keeps_it_and_reports_it() (+2 more)

### Community 122 - "test_compose_parity.py"
Cohesion: 0.25
Nodes (8): Task 3: The compose file and the parity test, config(), _launcher_args(), _normalise(), test_compose_command_matches_the_launcher(), test_compose_pins_the_image_and_never_downloads(), test_compose_publishes_on_localhost_only(), test_compose_reserves_the_gpus_serve_env_names()

### Community 123 - "deploy.sh"
Cohesion: 0.12
Nodes (27): deploy job: build three images, push to ECR, upload deploy files, run deploy.sh via SSM, ECR images: herhealth-frontend, herhealth-backend, herhealth-retrieval (SHA-tagged, immutable), Deploy through SSM Run Command (herhealth-deploy document), compose.yml (local development database), postgres service (postgres:16-alpine, local dev), compose.prod.yml (production topology: one host, four containers), backend service (herhealth-backend image, port 8000, RDS), caddy service (TLS reverse proxy, only published ports) (+19 more)

### Community 124 - "Path"
Cohesion: 0.19
Nodes (7): load_corpus(), corpus_dir(), test_a_near_miss_reports_the_closest_source_text(), test_an_empty_corpus_directory_loads(), test_misattribution_names_where_the_quote_actually_is(), test_only_real_faults_fail_the_build(), test_source_absent_is_not_treated_as_a_problem()

### Community 126 - "render_known_background"
Cohesion: 0.11
Nodes (17): 1. The whole file is uploaded and the backend extracts from it, 2. What is extracted, and what is discarded, 3. Before anything is saved, she confirms what was found, 4. Fresh data pre-fills answers; stale data makes the model ask, 5. Storage, Context, Cycle data is imported from any tracker, and fresh data may pre-fill answers, Decision (+9 more)

### Community 127 - "tunnel-models.sh"
Cohesion: 0.26
Nodes (9): alive(), models_key(), port_of(), publish(), tunnel-models.sh script, start(), status(), stop() (+1 more)

### Community 128 - "_Days"
Cohesion: 0.31
Nodes (4): PainIntensity, PregnancyTestResult, _Days, _from_csv_template()

### Community 129 - "lifespan"
Cohesion: 0.21
Nodes (7): google_client_id(), session_secret(), _build_google_verifier(), lifespan(), test_session_secret_raises_when_too_short(), test_session_secret_raises_when_unset(), test_session_secret_returns_a_long_enough_value()

### Community 130 - "q2 hf datasets loading"
Cohesion: 0.24
Nodes (9): HF Datasets docs: Load (research source q2), data_files / data_dir / split / revision parameters, JSON Lines loading (one JSON object per row), load_dataset() (Hub, local and remote files), Parquet and Arrow columnar loading, Streaming datasets (streaming=True), HF Datasets docs: Load tabular data (research source q2), Generic csv dataset builder (load_dataset('csv', data_files=...)) (+1 more)

### Community 131 - "q3 docs cohere embed"
Cohesion: 0.27
Nodes (9): Cohere's Embed Models (Details and Application) - docs capture, Cohere embed-english-v3.0, Cohere embed-multilingual-light-v3.0, Cohere embed-multilingual-v3.0, Cohere embed-v4.0, Cohere multilingual embed supported languages (100+), Cohere Pricing page - capture, Cohere Model Vault dedicated-instance pricing (+1 more)

### Community 132 - "q3 docs openai embeddings"
Cohesion: 0.29
Nodes (9): OpenAI Vector embeddings guide - docs capture, OpenAI text-embedding-3-large, OpenAI text-embedding-3-small, OpenAI text-embedding-ada-002, Qwen/Qwen3-Embedding-8B model card - Hugging Face capture, MTEB (Multilingual) comparison table, Qwen3-Embedding-8B, MTEB Leaderboard Hugging Face Space - capture (app shell only) (+1 more)

### Community 133 - "q3 pricing jina embeddings"
Cohesion: 0.31
Nodes (7): Jina Search Foundation API docs - capture (JS shell, no body text), jinaai/jina-embeddings-v3 model card - Hugging Face capture, jina-embeddings-v3, Jina AI Embedding API product and pricing page - capture, jina-embeddings-v4, jina-embeddings-v5-text (677M small / 239M nano), Jina API rate limits (RPM / TPM per key or IP)

### Community 134 - "q3 pricing voyage ai"
Cohesion: 0.22
Nodes (9): OpenAI Business/Enterprise pricing page - capture, ChatGPT Business plan (per-user pricing, EGP-denominated), OpenAI API pricing page - capture, Per-1M-token pricing tiers (standard, batch, flex, fast mode), Voyage AI pricing docs - capture, Voyage Batch API (33% discount, 12-hour window), Voyage rerank-2.5 / rerank-2.5-lite, voyage-4-large / voyage-4 / voyage-4-lite text embeddings (+1 more)

### Community 135 - "q4 arxiv 2106.09685 lora low rank adapta"
Cohesion: 0.24
Nodes (4): LoRA: Low-Rank Adaptation of Large Language Models (Hu et al., arXiv 2106.09685), Attention projection matrices Wq, Wk, Wv, Wo as adaptation targets, HF PEFT docs: LoRA conceptual guide (research source q4), merge_and_unload() and adapter utilities

### Community 136 - "features"
Cohesion: 0.20
Nodes (9): Ovarian cyst [ROUTINE_APPOINTMENT], Pelvic organ prolapse [ROUTINE_APPOINTMENT], Abdominal swelling or pressure (abdominal_swelling_or_pressure), Bloating or digestive problems (bloating_or_digestive_symptoms), Nausea or vomiting (feeling_sick_or_vomiting), Lower back pain (lower_back_pain), How the pain started (pain_onset), Evidence batch 16: ovarian cyst backfill (+1 more)

### Community 137 - "test isolation"
Cohesion: 0.60
Nodes (3): _probe_with(), test_transaction_is_isolated_alpha(), test_transaction_is_isolated_beta()

### Community 138 - "The local base model decides, and the fine-tuned adapter words informational answers"
Cohesion: 0.17
Nodes (12): Consequences, Context, Decision, Follow-up the same day: a question no longer has to cite a passage, Limits, Multilingual first turns (2026-10-15), Second follow-up the same day: repeated questions and invented notes, The full benchmark, first turns only (2026-10-13) (+4 more)

### Community 139 - "The reasoning chain on LangChain — design"
Cohesion: 0.17
Nodes (11): Configuration, Done when, Goals, Measurement, Out of scope, Risks, Testing, The measurement behind it (+3 more)

### Community 140 - "q4 vllm lora adapters docs"
Cohesion: 0.31
Nodes (8): vLLM docs: LoRA Adapters (research source q4), Dynamic LoRA loading (/v1/load_lora_adapter, VLLM_ALLOW_RUNTIME_LORA_UPDATING, LoRAResolver plugins), LoRA model lineage in the model card (parent / root, base_model_name), vllm serve --enable-lora --lora-modules {name}={path}, Server-wide LoRA configuration (max_loras, max_lora_rank, max_cpu_loras), LoRARequest (per-request adapter selection, offline), LoRA for multimodal models (tower/connector, default_mm_loras), SupportsLoRA model interface

### Community 141 - "parse_env"
Cohesion: 0.26
Nodes (6): parse_env(), test_chat_uses_two_gpus_and_the_agreed_window(), test_every_revision_is_pinned(), test_every_service_declares_its_fields(), test_no_gpu_is_shared_between_services(), test_ports_are_distinct_and_avoid_the_backend()

### Community 142 - "SesEmailSender"
Cohesion: 0.23
Nodes (5): SesEmailSender, email_sender_kind(), _build_email_sender(), test_ses_email_sender_calls_send_email_with_the_code(), test_ses_email_sender_calls_send_email_with_the_password_reset_code()

### Community 143 - "package"
Cohesion: 0.22
Nodes (9): devDependencies, eslint, eslint-config-next, tailwindcss, @tailwindcss/postcss, @types/node, @types/react, @types/react-dom (+1 more)

### Community 144 - "current_user.py"
Cohesion: 0.12
Nodes (3): get_current_user(), test_health_ok_when_database_answers(), test_health_unavailable_when_database_is_unreachable()

### Community 145 - "load_source_urls"
Cohesion: 0.27
Nodes (5): load_source_urls(), test_a_missing_lock_file_degrades_rather_than_raising(), test_comment_lines_are_skipped(), test_one_unreadable_row_does_not_cost_the_others_their_links(), test_the_real_lock_file_resolves_every_row_to_an_http_url()

### Community 146 - "q4 hf peft lora conceptual"
Cohesion: 0.32
Nodes (5): Train adapters with PEFT (peft_config=LoraConfig()), HF PEFT docs: index (research source q4), PEFT (Parameter-Efficient Fine-Tuning) library, Default LoRA init (Kaiming-uniform A, zero B, identity transform), LoraConfig (r, lora_alpha, target_modules, bias, use_rslora, rank_pattern)

### Community 147 - "q3 modelcard multilingual e5 large"
Cohesion: 0.36
Nodes (6): XLM-RoBERTa backbone, Jina-XLM-RoBERTa architecture, intfloat/multilingual-e5-large model card - Hugging Face capture, Mr. TyDi benchmark results (MRR@10, incl. Arabic 77.5), intfloat/multilingual-e5-large, Multilingual E5 Text Embeddings: A Technical Report (arXiv 2402.05672)

### Community 148 - "HashingEmbeddings"
Cohesion: 0.10
Nodes (14): Dependencies, Done when, Out of scope, Part 3: the recall check, Part 4: deletions, Prerequisites needing a go-ahead, Retrieval on LangChain with the Qwen3 embedder and reranker — design, Risks (+6 more)

### Community 149 - "clean"
Cohesion: 0.32
Nodes (4): classify_heading(), SectionType, test_escalation_beats_other_matches(), test_headings_are_classified()

### Community 150 - "test_triage_mode.py"
Cohesion: 0.33
Nodes (6): Task 5: Wiring, and removing OpenRouter and the selector from the backend, test_the_answer_model_defaults_to_the_adapter_and_can_be_switched_off(), test_the_decision_model_defaults_to_the_base_model(), test_triage_mode_accepts_vllm_demo_off(), test_triage_mode_rejects_openrouter_naming_the_valid_modes(), test_unset_mode_is_off()

### Community 152 - "q3 modelcard qwen3 embedding 0.6b"
Cohesion: 0.48
Nodes (5): Qwen/Qwen3-Embedding-0.6B model card - Hugging Face capture, Qwen3-Embedding-0.6B, Qwen3 Embedding series (embedding + reranking, 0.6B/4B/8B), Qwen/Qwen3-Reranker-0.6B model card - Hugging Face capture, Qwen3-Reranker-0.6B

### Community 153 - "test clean"
Cohesion: 0.18
Nodes (7): flush(), find_escalation_sentences(), find_locale_references(), test_escalation_language_is_found_mid_paragraph(), test_escalation_sentences_are_verbatim(), test_locale_references_are_recorded(), test_ordinary_prose_is_not_treated_as_escalation()

### Community 154 - "Model-serving stack on the campus GPU box — design"
Cohesion: 0.20
Nodes (9): Chat memory and the context window, Done when, Model-serving stack on the campus GPU box — design, Out of scope, Prerequisites needing a go-ahead, Risks, Runtime layout, What was decided, and by whom (+1 more)

### Community 155 - "load_evaluation_set"
Cohesion: 0.12
Nodes (13): _check_features_exist(), _coerce_case_features(), _evidence(), load_evaluation_set(), _yaml(), test_a_batch_file_loads(), test_a_number_is_refused_rather_than_stringified(), test_a_value_outside_allowed_values_is_refused() (+5 more)

### Community 156 - "os"
Cohesion: 0.24
Nodes (3): _database_url(), run_migrations_offline(), run_migrations_online()

### Community 157 - "issue tracker"
Cohesion: 0.40
Nodes (5): Agent docs: issue tracker (GitHub), Issue tracker: GitHub Issues via the gh CLI, Wayfinding operations (map issue, child tickets, blocking, claim, resolve), Agent docs: triage labels, Five canonical issue-triage label roles

### Community 158 - "document"
Cohesion: 0.22
Nodes (5): Task 1: The shared env file and the reranker template, document(), test_text_hash_changes_when_words_change(), test_text_hash_ignores_markup_churn(), test_text_hash_ignores_rotating_link_lists()

### Community 159 - "_build_cycle_extractor"
Cohesion: 0.25
Nodes (5): model_instructions(), CycleImportUnavailable, vllm_timeout(), _build_cycle_extractor(), extract()

### Community 160 - "pyproject"
Cohesion: 0.83
Nodes (4): herhealth-backend, herhealth-contracts, herhealth-data, herhealthgpt

### Community 162 - "Section"
Cohesion: 0.25
Nodes (3): On-disk format, health(), Section

### Community 164 - "File Structure"
Cohesion: 0.17
Nodes (8): File Structure, Task 10: Build the index and run the live checks, Task 11: Record the decision and update the docs, Task 2: Move the citation URL lookup into the data service, Task 5: Delete the old index code in the data service, Task 6: The retriever in the backend, Task 9: Delete the retrieval service and its place in the deploy, store()

### Community 165 - "package"
Cohesion: 0.40
Nodes (5): scripts, build, dev, lint, start

### Community 166 - "q3 modelcard bge reranker v2 m3"
Cohesion: 0.83
Nodes (3): BAAI/bge-reranker-v2-m3 model card - Hugging Face capture, BAAI/bge-reranker-v2-gemma (LLM-based reranker), BAAI/bge-reranker-v2-minicpm-layerwise

### Community 167 - "Retrieval uses Qwen3-Embedding-4B and Qwen3-Reranker-4B, built on LangChain"
Cohesion: 0.29
Nodes (7): Consequences, Context, Decision, Measurement, Retrieval uses Qwen3-Embedding-4B and Qwen3-Reranker-4B, built on LangChain, The reranker was measured and defaulted off, What was not established

### Community 168 - "Files"
Cohesion: 0.29
Nodes (7): Docs, Files, Flags, `infra/compose.model.yml` (new), `infra/model/serve.conf` (new), `scripts/serve-models.sh` (new, replaces `scripts/setup-uni-vllm.sh`), `scripts/smoke_models.py` (new)

### Community 173 - "cycle_data_for"
Cohesion: 0.48
Nodes (3): clear_cycle_data(), cycle_data_for(), save_cycle_data()

### Community 178 - "Model-Serving Stack Implementation Plan"
Cohesion: 0.50
Nodes (3): Done when, Global Constraints, Model-Serving Stack Implementation Plan

## Ambiguous Edges - Review These
- `Towards Physician-Centered Oversight of Conversational Diagnostic AI (Vedadi et al., arXiv 2507.15743)` → `A Prospective Clinical Feasibility Study of a Conversational Diagnostic AI in an Ambulatory Primary Care Clinic (Brodeur et al., arXiv 2603.08448)`  [AMBIGUOUS]
  docs/research/sources/q5-arxiv-2603.08448-conversational-diagnostic-ai-prospective-clinical-feasibility.pdf · relation: cites
- `conversation.svg (hand holding a phone showing chat bubbles and a typing indicator)` → `Rule: illustration SVGs stay out of git`  [AMBIGUOUS]
  services/frontend/public/illustrations/README.md · relation: conceptually_related_to
- `AMIE, Towards Conversational Diagnostic AI (arXiv:2401.05654 / Nature)` → `Verdict: replacing the controller with an end-to-end LLM is contradicted by every primary evaluation found`  [AMBIGUOUS]
  docs/research/0001-llm-triage-architecture.md · relation: conceptually_related_to
- `argues_against Only When Source Is Explicit` → `Two-Question Evidence Row Authoring (listed? absence doubts?)`  [AMBIGUOUS]
  .claude/skills/clinical-data-authoring/SKILL.md · relation: conceptually_related_to
- `HerHealth Monorepo Conventions Skill` → `Frontend Is Not a PWA`  [AMBIGUOUS]
  .claude/skills/herhealth-repo/SKILL.md · relation: conceptually_related_to
- `gold_seeds_styled Benchmark (540 rows, 90 seeds x 6 registers)` → `Issue #20 ADR 0011 Migration (items 5, 7-9)`  [AMBIGUOUS]
  HANDOFF.md · relation: references
- `ADR 0011 Controller-Free Triage` → `Red Flag`  [AMBIGUOUS]
  CONTEXT.md · relation: conceptually_related_to
- `ADR 0011 Controller-Free Triage` → `Pre-ADR-0011 Stance: No Fine-Tuning, Decision Lives in Python`  [AMBIGUOUS]
  README.md · relation: conceptually_related_to
- `Legacy Source Precedence List (NICE CKS first)` → `Excluded Sources (NICE CKS, RCOG/ACOG, UMLS, WHO ICD)`  [AMBIGUOUS]
  .claude/skills/source-ingestion/SKILL.md · relation: conceptually_related_to
- `Legacy Source Precedence List (NICE CKS first)` → `Source Precedence on Conflict (NHS 2, others 3, CDC 4)`  [AMBIGUOUS]
  .claude/skills/source-ingestion/SKILL.md · relation: conceptually_related_to
- `CONTRIBUTING.md` → `Frontend Is Not a PWA`  [AMBIGUOUS]
  CONTRIBUTING.md · relation: conceptually_related_to

## Knowledge Gaps
- **140 isolated node(s):** `react-dom`, `shadcn`, `tw-animate-css`, `@tailwindcss/postcss`, `@types/node` (+135 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1607 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **27 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `weights.yaml (ordinal-to-log-odds mapping and stopping thresholds)` connect `Weights & Action Codes` to `herhealth_contracts/knowledge.py`, `Knowledge Schema Contracts`, `The knowledge base, explained`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Are the 84 inferred relationships involving `TriageEngine` (e.g. with `Deterministic stopping controller (TriageEngine.should_stop)` and `run_case()`) actually correct?**
  _`TriageEngine` has 84 INFERRED edges - model-reasoned connections that need verification._
- **What connects `react-dom`, `shadcn`, `tw-animate-css` to the rest of the system?**
  _140 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Turn Context & Rule Assessment` be split into smaller, more focused modules?**
  _Cohesion score 0.033599783227204985 - nodes in this community are weakly interconnected._
- **Why does `TriageDecision` connect `TriageDecision Schema` to `Turn Context & Rule Assessment`, `Deterministic Triage Engine`, `test_chain.py`, `Consultation Session Models`, `Agent Context Tests`, `Condition Provenance Repair`, `app/config.py`, `decision_eval.py`, `RetrievedPassage`, `KnowledgeBase`, `Research 0001: Reconsidering the deterministic controller (LLM triage architecture)`, `httpx`, `herhealth_contracts/knowledge.py`, `ReasoningAttempt`, `Triage Route Tests`, `agent.py`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `Towards Physician-Centered Oversight of Conversational Diagnostic AI (Vedadi et al., arXiv 2507.15743)` and `A Prospective Clinical Feasibility Study of a Conversational Diagnostic AI in an Ambulatory Primary Care Clinic (Brodeur et al., arXiv 2603.08448)`?**
  _Edge tagged AMBIGUOUS (relation: cites) - confidence is low._
- **What is the exact relationship between `conversation.svg (hand holding a phone showing chat bubbles and a typing indicator)` and `Rule: illustration SVGs stay out of git`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._