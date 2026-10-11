# Graph Report - herhealthgpt  (2026-10-11)

## Corpus Check
- Large corpus: 466 files · ~743,675 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 4402 nodes · 11504 edges · 184 communities (155 shown, 29 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 1454 edges (avg confidence: 0.92)
- Token cost: 1,814,354 input · 0 output

## Community Hubs (Navigation)
- Turn Context & Rule Assessment
- Deterministic Triage Engine
- Frontend Auth Pages & UI Kit
- Chat Message Components
- Model Service & Passages
- Consultation Session Models
- Evidence Proposal Pipeline
- Auth Cookies & Account Routes
- Email Normalisation & Registration
- Backend App Config
- Bootstrap Dataset Export
- Chat Page State
- App Shell & Marketing Pages
- Triage Agent Loop
- Triage CLI
- Knowledge Schema Contracts
- Dashboard & Account Settings
- Email Verification
- Decision Contract Package
- Reasoning Backend Clients
- HealthBench & FDA CDS Guidance
- Account Route Tests
- Password Reset Errors
- Email Sending & Previews
- Triage Route Tests
- API Error Handlers
- Threshold Analysis
- Knowledge Validation
- Quote Provenance Corpus
- Conversational Diagnostic AI Papers
- Ingest Config & Robots
- TriageDecision Schema
- Database Migrations
- Data CLI Commands
- Password Reset Codes
- Data CLI Entry Point
- Phase-1 Conditions & Features
- Session Policy & Refresh
- Agent Context Tests
- Sign-In Throttling & Locks
- Evaluation Metrics
- Dialogue Runner
- Embedding Benchmarks (MTEB, BGE-M3)
- Evaluation Case Sets
- Topic Briefs from Knowledge
- Red Flags & Urgent Actions
- Routine-Urgency Conditions
- AWS Deploy & Agent Docs
- Fetch Stage Tests
- Backend Test Fixtures
- Frontend Dependencies
- Account Deletion
- Profile Details Validation
- Retrieval Composition
- HTML Cleaning Tests
- Data Pipeline Skill Rules
- Architecture Decisions & Model Serving
- Raw Store Lockfile
- Cited Sources UI
- OpenRouter/vLLM Client Calls
- Google Sign-In
- Knowledge Table Rendering
- El Saddik Lab Papers
- Code Guide & Repo Map
- Access Tokens & Current User
- Plausibility Scoring
- ICD-11 Lookup
- Evaluation CLI
- Fetch Plan
- Triage Glossary
- Weights & Action Codes
- Condition Provenance Repair
- Profile & Health Note
- Ingest Target Config Tests
- shadcn Component Config
- CLAUDE
- extract diagrams
- uni server vllm
- cards
- conditions
- 0002 conversational triage prior art and
- evaluation
- test age bands
- evidence
- README
- tsconfig
- CONTEXT
- KNOWLEDGE BASE
- observed triage behaviour
- test knowledge
- check repo hygiene
- 0015 a user may keep a date of birth and
- FLOW EXPLAINED
- test evaluation runner
- test accounts passwords
- engine
- 0011 controller free triage
- q2 hf trl dataset formats
- frontend
- metrics
- thresholds
- package
- test accounts deletion
- 0001 llm triage architecture
- ROADMAP
- q3 modelcard bge m3
- q4 arxiv 2308.08747 catastrophic forgett
- sources
- knowledge
- CLAUDE
- eventloop
- 0004 severe pelvic pain is urgent not em
- 0010 multilingual embeddings beat arabic
- 0014 an off scope message is declined no
- knowledge
- context
- README
- CLAUDE
- clean
- 0001 source traceability replaces clinic
- 0005 plausibility is an independent logi
- 0001 injected postcss payload and leaked
- build index
- deploy
- README
- test known background
- onboarding
- 0002 yaml for nested files csv for the e
- 0008 showing what symptoms align with
- q2 hf datasets loading
- q3 docs cohere embed
- q3 docs openai embeddings
- q3 pricing jina embeddings
- q3 pricing voyage ai
- q4 arxiv 2106.09685 lora low rank adapta
- features
- test isolation
- store
- PHASE 1 SUMMARY
- q4 vllm lora adapters docs
- compose.prod
- setup uni vllm
- package
- test health
- 0007 what the first real consultations s
- q4 hf peft lora conceptual
- q3 modelcard multilingual e5 large
- embed
- clean
- CONTEXT
- test boundary
- q3 modelcard qwen3 embedding 0.6b
- test clean
- CONTEXT
- loading
- clean
- issue tracker
- README
- refresh secrets
- pyproject
- postcss.config
- routes
- context
- conftest
- package
- q3 modelcard bge reranker v2 m3
- bootstrap deploy
- test clean
- next
- file
- globe
- window

## God Nodes (most connected - your core abstractions)
1. `TriageEngine` - 109 edges
2. `build()` - 82 edges
3. `cn()` - 76 edges
4. `TriageDecision` - 70 edges
5. `ActionCode` - 63 edges
6. `KnowledgeBase` - 60 edges
7. `RetrievedPassage` - 58 edges
8. `User` - 54 edges
9. `Button()` - 52 edges
10. `Database` - 46 edges

## Surprising Connections (you probably didn't know these)
- `cited_passages and RetrievedPassage.url (citations resolve to quoted text and a real link)` --references--> `RetrievedPassage`  [EXTRACTED]
  docs/adr/0012-openrouter-reasoning-and-guarded-web-fallback.md → packages/contracts/src/herhealth_contracts/retrieval.py
- `Deterministic stopping controller (TriageEngine.should_stop)` --references--> `TriageEngine`  [INFERRED]
  docs/adr/0007-what-the-first-real-consultations-showed.md → services/backend/src/herhealth_backend/triage/engine.py
- `evidence.csv is generated from approved batches (make evidence)` --semantically_similar_to--> `ADR 0003: evidence.csv is generated from approved batches`  [INFERRED] [semantically similar]
  services/data/evidence_batches/batch_01_pcos_fibroids.yaml → docs/REPO_MAP.md
- `Provenance as correctness evidence (no clinician review)` --semantically_similar_to--> `ADR 0001: Source traceability replaces clinician review`  [INFERRED] [semantically similar]
  knowledge/README.md → docs/adr/0001-source-traceability-replaces-clinician-review.md
- `DecisionType.DECLINE (rationale only; all other fields forbidden; exempt from grounding)` --references--> `DecisionType`  [EXTRACTED]
  docs/adr/0014-an-off-scope-message-is-declined-not-triaged.md → packages/contracts/src/herhealth_contracts/decision.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **The Seven Knowledge Files** — claude_features_yaml, claude_conditions_yaml, claude_evidence_csv, claude_red_flags_yaml, claude_sources_yaml, claude_weights_yaml, claude_actions_yaml [EXTRACTED 1.00]
- **Source-Traceable Provenance Chain (quote, batch review, verbatim check)** — claude_verification_protocol, context_source_quote, claude_verify_quotes, _claude_skills_herhealth_pipeline_skill_evidence_batches, _claude_skills_clinical_data_authoring_skill_batch_limit, _claude_skills_herhealth_pipeline_skill_ingest_lock [INFERRED 0.85]
- **Gate on Letting the Fine-Tuned Adapter Decide Triage** — claude_adr_0011, claude_triagedecision, claude_qlora_adapter, claude_ft_corpus_v1, claude_bootstrap_multi_turn, handoff_issue_20_migration, readme_model_selector [INFERRED 0.85]
- **Production release pipeline: build index, deploy workflow, compose.prod topology** — github_workflows_build_index_build, github_workflows_deploy_deploy, github_workflows_deploy_index_verification, github_workflows_deploy_ecr_images, github_workflows_deploy_ssm_deploy, infra_compose_prod [INFERRED 0.85]
- **The four hand-written controller demonstration cases pinned by tests** — services_backend_cases_sudden_severe_pain, services_backend_cases_heavy_periods_over_40, services_backend_cases_itching_and_discharge, services_backend_cases_says_nothing [EXTRACTED 1.00]
- **Honest deletion: revocable sessions, refresh tokens and immediate cascading deletion** — services_backend_context_session, services_backend_context_refresh_token, services_backend_context_access_token, services_backend_context_deletion, services_backend_context_opaque_revocable_sessions [INFERRED 0.85]
- **Components of one agentic RAG triage turn** — docs_flow_explained_backend_orchestrator, docs_flow_explained_embedding_model_bge_m3, docs_flow_explained_retrieval_index, docs_flow_explained_red_flags_full_injection, docs_flow_explained_reasoning_model, docs_flow_explained_triagedecision, docs_flow_explained_session_store [EXTRACTED 1.00]
- **Environments that serve the herhealth LoRA adapter under vLLM** — docs_runbooks_uni_server_vllm_vllm_start_command, docs_runbooks_dev_vllm_lora_endpoint_vast_ai_dev_endpoint, docs_runbooks_friend_pc_vllm_setup_wsl2_vllm_setup, docs_runbooks_uni_server_vllm_herhealth_lora_adapter, docs_runbooks_dev_vllm_lora_endpoint_hard_constraints_phrasing_only [INFERRED 0.85]
- **Production deploy pipeline from main to the EC2 host** — docs_runbooks_aws_deploy_github_oidc_roles, docs_runbooks_aws_deploy_ssm_deploy_document, docs_runbooks_aws_deploy_deploy_sh, docs_runbooks_aws_deploy_publish_index_sh, docs_runbooks_aws_deploy_secrets_and_rotation, docs_runbooks_aws_deploy_single_ec2_architecture [EXTRACTED 1.00]
- **TriageDecision contract: ASK/CONCLUDE, EMERGENCY exception, DECLINE and INFORM** — docs_adr_0011_controller_free_triage_triagedecision_schema_safety_net, docs_adr_0011_controller_free_triage_red_flag_names_no_condition, docs_adr_0011_controller_free_triage_matching_conditions_cap, docs_adr_0013_emergency_conclusions_may_name_conditions_emergency_names_conditions_exception, docs_adr_0014_an_off_scope_message_is_declined_not_triaged_decline_decision_type, docs_adr_0016_an_in_scope_question_may_be_answered_informationally_inform_decision_type [EXTRACTED 1.00]
- **Primary evidence that triage needs external structure around the model** — docs_research_0001_llm_triage_architecture_mediq, docs_research_0001_llm_triage_architecture_healthbench, docs_research_0001_llm_triage_architecture_equitriage, docs_research_0001_llm_triage_architecture_mecr_rag, docs_research_0001_llm_triage_architecture_fda_cds_guidance, docs_research_0001_llm_triage_architecture_verdict_keep_the_controller [EXTRACTED 1.00]
- **Model-judged boundaries that make eval cannot measure (action choice, scope, inform-vs-triage, named condition at EMERGENCY, health-note anchoring)** — docs_adr_0011_controller_free_triage_risk_register, docs_adr_0013_emergency_conclusions_may_name_conditions_wrong_condition_at_emergency_risk, docs_adr_0014_an_off_scope_message_is_declined_not_triaged_false_refusal_risk, docs_adr_0015_a_user_may_keep_a_date_of_birth_and_a_health_note_privacy_and_anchoring_risks, docs_adr_0016_an_in_scope_question_may_be_answered_informationally_inform_versus_triage_boundary_risk [INFERRED 0.85]
- **The seven knowledge files that drive triage reasoning** — knowledge_features, knowledge_conditions, knowledge_evidence, knowledge_red_flags, knowledge_sources, knowledge_weights, knowledge_actions [EXTRACTED 1.00]
- **EMERGENCY red-flag rules conditioned on pelvic pain** — knowledge_red_flags_sudden_severe_pelvic_pain, knowledge_red_flags_pelvic_pain_with_faintness, knowledge_red_flags_pelvic_pain_with_shoulder_tip_pain, knowledge_red_flags_pelvic_pain_with_right_sided_referred_pain, knowledge_red_flags_pelvic_pain_with_heavy_bleeding, knowledge_red_flags_pelvic_pain_with_breathing_difficulty, knowledge_red_flags_pelvic_pain_with_sudden_confusion, knowledge_actions_emergency, knowledge_features_pelvic_pain_severity [EXTRACTED 1.00]
- **Evidence authoring flow: approved batches generate evidence.csv, quotes verified verbatim** — services_data_evidence_batches_batch_01_pcos_fibroids, services_data_evidence_batches_batch_02_endometriosis, services_data_evidence_batches_batch_03_fibroids_pcos, services_data_evidence_batches_batch_04_normal_variation, services_data_evidence_batches_batch_05_pid, services_data_evidence_batches_batch_06_ovarian_cyst_uti, services_data_evidence_batches_batch_07_perimenopause_sti, services_data_evidence_batches_batch_08_orphans, services_data_evidence_batches_evidence_generated_from_approved_batches, services_data_evidence_batches_make_verify_quotes, knowledge_evidence [INFERRED 0.85]
- **Discharge cluster: separating thrush, bacterial vaginosis and STI by itching, smell and appearance** — knowledge_conditions_thrush, knowledge_conditions_bacterial_vaginosis, knowledge_conditions_sexually_transmitted_infection, knowledge_features_abnormal_discharge, knowledge_features_vulval_itching, knowledge_features_discharge_smell, knowledge_features_discharge_appearance, services_data_evidence_batches_batch_10_adenomyosis_discharge_bv_itching_source_conflict [EXTRACTED 1.00]
- **Why conditions lack an argues_against row: the documented gap shapes** — services_data_evidence_batches_batch_10_adenomyosis_discharge_elimination_row_audit, services_data_evidence_batches_batch_12_sti_backfill_frequently_silent_condition, services_data_evidence_batches_batch_13_uti_backfill_missing_urine_appearance_feature, services_data_evidence_batches_batch_20_bladder_pain_distinction_with_no_cell, services_data_evidence_batches_batch_18_primary_ovarian_insufficiency_poi_terminology_conflict, services_data_evidence_batches_batch_16_ovarian_cyst_backfill_first_eliminating_row [INFERRED 0.85]
- **difficulty_conceiving distinguished across conditions (weak, argues_against, definitional)** — knowledge_features_difficulty_conceiving, knowledge_conditions_infertility, knowledge_conditions_ovarian_cyst, knowledge_conditions_pelvic_inflammatory_disease, knowledge_conditions_sexually_transmitted_infection, knowledge_conditions_hypothyroidism, knowledge_conditions_primary_ovarian_insufficiency, knowledge_conditions_endometriosis, knowledge_conditions_pcos [EXTRACTED 1.00]
- **The nine unDraw illustrations the Illustration component resolves by filename** — services_frontend_public_illustrations_onboarding, services_frontend_public_illustrations_urgency, services_frontend_public_illustrations_welcome, services_frontend_public_illustrations_conversation, services_frontend_public_illustrations_safety, services_frontend_public_illustrations_sources, services_frontend_public_illustrations_resolved, services_frontend_public_illustrations_error, services_frontend_public_illustrations_not_found [EXTRACTED 1.00]
- **Default create-next-app public assets (framework logos and stock icons)** — services_frontend_public_file, services_frontend_public_globe, services_frontend_public_next, services_frontend_public_vercel, services_frontend_public_window [INFERRED 0.85]
- **Licence-driven handling of illustrations: manual download, no automation, not committed** — services_frontend_public_illustrations_readme_undraw_licence, services_frontend_public_illustrations_readme_no_script_fetch, services_frontend_public_illustrations_readme_files_stay_out_of_git, services_frontend_public_illustrations_readme_licence_exclusion_consistency [EXTRACTED 1.00]
- **Three components of clinical evidence for medical device software** — docs_research_sources_q1_eu_mdcg_2020_1_clinical_evaluation_mdsw_valid_clinical_association, docs_research_sources_q1_eu_mdcg_2020_1_clinical_evaluation_mdsw_technical_performance, docs_research_sources_q1_eu_mdcg_2020_1_clinical_evaluation_mdsw_clinical_performance, docs_research_sources_q1_eu_mdcg_2020_1_clinical_evaluation_mdsw_clinical_evidence [EXTRACTED 1.00]
- **Regulatory tests deciding whether health software is a medical device (EU and US)** — docs_research_sources_q1_eu_mdcg_2019_11_software_qualification_qualification_decision_steps, docs_research_sources_q1_eu_mdcg_2019_11_software_qualification_intended_purpose, docs_research_sources_q1_eu_mdcg_2019_11_software_qualification_rule_11, docs_research_sources_q1_fda_cds_software_guidance_non_device_cds_criteria, docs_research_sources_q1_fda_cds_software_guidance_patient_or_caregiver_cds_is_a_device [INFERRED 0.85]
- **Evaluation methods for open-ended medical LLM output beyond exam benchmarks** — docs_research_sources_q1_arxiv_2505_08775_healthbench_evaluating_llms_towards_improved_human_health_physician_written_rubric_evaluation, docs_research_sources_q1_arxiv_2505_08775_healthbench_evaluating_llms_towards_improved_human_health_model_based_grader, docs_research_sources_q1_arxiv_2505_08775_healthbench_evaluating_llms_towards_improved_human_health_worst_at_k_reliability, docs_research_sources_q1_arxiv_2505_23802_medhelm_holistic_evaluation_of_llms_for_medical_tasks_llm_jury, docs_research_sources_q1_arxiv_2505_23802_medhelm_holistic_evaluation_of_llms_for_medical_tasks_clinician_validated_taxonomy [INFERRED 0.85]
- **Multilingual embedding model candidates compared for retrieval** — docs_research_sources_q3_arxiv_2402_03216_bge_m3_embedding_multilingual_multifunctionality_bge_m3, docs_research_sources_q3_arxiv_2402_05672_multilingual_e5_text_embeddings_technical_report_me5_models, docs_research_sources_q3_arxiv_2409_10173_jina_embeddings_v3_multilingual_task_lora_jina_embeddings_v3, docs_research_sources_q3_arxiv_2506_05176_qwen3_embedding_text_embedding_and_reranking_qwen3_embedding_series [INFERRED 0.85]
- **Arabic RAG findings: sentence chunking, multilingual encoders, optional reranker** — docs_research_sources_q3_arxiv_2506_06339_alsubhi_arabic_rag_embedding_chunking_evaluation_sentence_aware_chunking, docs_research_sources_q3_arxiv_2506_06339_alsubhi_arabic_rag_embedding_chunking_evaluation_multilingual_beat_arabic_specific, docs_research_sources_q3_arxiv_2506_06339_alsubhi_arabic_rag_embedding_chunking_evaluation_bge_reranker_v2_m3, docs_research_sources_q3_arxiv_2506_06339_alsubhi_arabic_rag_embedding_chunking_evaluation_ragas_framework [EXTRACTED 1.00]
- **Embedding evaluation benchmark lineage (BEIR, MTEB, MIRACL, MMTEB)** — docs_research_sources_q3_arxiv_2210_07316_mteb_massive_text_embedding_benchmark_beir, docs_research_sources_q3_arxiv_2210_07316_mteb_massive_text_embedding_benchmark_mteb, docs_research_sources_q3_arxiv_2402_03216_bge_m3_embedding_multilingual_multifunctionality_miracl, docs_research_sources_q3_arxiv_2502_13595_mmteb_massive_multilingual_text_embedding_benchmark_mmteb [INFERRED 0.75]
- **LoRA adapter lifecycle: method, PEFT configuration, SFT training, vLLM serving** — docs_research_sources_q4_arxiv_2106_09685_lora_low_rank_adaptation_of_large_language_models_low_rank_adaptation, docs_research_sources_q4_hf_peft_lora_conceptual_loraconfig, docs_research_sources_q2_hf_trl_sft_trainer_docs_peft_integration, docs_research_sources_q4_vllm_lora_adapters_docs_lora_modules_flag [INFERRED 0.85]
- **Evidence on what fine-tuning forgets and how LoRA trades learning against forgetting** — docs_research_sources_q4_arxiv_2308_08747_catastrophic_forgetting_in_llms_continual_finetuning_catastrophic_forgetting, docs_research_sources_q4_arxiv_2308_08747_catastrophic_forgetting_in_llms_continual_finetuning_diverse_instruction_tuning_mitigation, docs_research_sources_q4_arxiv_2405_09673_lora_learns_less_and_forgets_less_lora_forgets_less, docs_research_sources_q4_arxiv_2405_09673_lora_learns_less_and_forgets_less_learning_forgetting_tradeoff, docs_research_sources_q4_arxiv_2405_09673_lora_learns_less_and_forgets_less_lora_underperforms_full_finetuning [INFERRED 0.85]
- **Conversational SFT data pipeline: load files, shape into messages, apply chat template, train** — docs_research_sources_q2_hf_datasets_loading_load_dataset, docs_research_sources_q2_hf_datasets_tabular_csv_csv_builder, docs_research_sources_q2_hf_trl_sft_trainer_docs_preprocess_to_expected_format, docs_research_sources_q2_hf_trl_dataset_formats_conversational_format, docs_research_sources_q2_hf_trl_sft_trainer_docs_chat_template_application, docs_research_sources_q2_hf_trl_sft_trainer_docs_sfttrainer [INFERRED 0.85]
- **AMIE research programme: text OSCE, multimodal OSCE, guardrailed oversight, prospective clinic study** — docs_research_sources_q5_arxiv_2401_05654_amie_towards_conversational_diagnostic_ai, docs_research_sources_q5_arxiv_2505_04653_amie_advancing_conversational_diagnostic_ai_multimodal, docs_research_sources_q5_arxiv_2507_15743_amie_physician_centered_oversight_conversational_diagnostic_ai, docs_research_sources_q5_arxiv_2603_08448_conversational_diagnostic_ai_prospective_clinical_feasibility [INFERRED 0.95]
- **Mechanisms for deciding when to ask a clarifying question instead of concluding** — docs_research_sources_q5_arxiv_2406_00922_mediq_question_asking_llms_interactive_clinical_reasoning_abstention_strategies, docs_research_sources_q5_arxiv_2502_14860_alfa_aligning_llms_to_ask_good_questions_clinical_reasoning_alfa_framework, docs_research_sources_q5_arxiv_2505_04653_amie_advancing_conversational_diagnostic_ai_multimodal_state_aware_dialogue_framework, docs_research_sources_q5_arxiv_2401_05654_amie_towards_conversational_diagnostic_ai_chain_of_reasoning_strategy [INFERRED 0.75]
- **Human oversight and guardrail controls around conversational diagnostic AI** — docs_research_sources_q5_arxiv_2507_15743_amie_physician_centered_oversight_conversational_diagnostic_ai_abstention_from_individualized_medical_advice, docs_research_sources_q5_arxiv_2507_15743_amie_physician_centered_oversight_conversational_diagnostic_ai_asynchronous_oversight, docs_research_sources_q5_arxiv_2507_15743_amie_physician_centered_oversight_conversational_diagnostic_ai_clinician_cockpit, docs_research_sources_q5_arxiv_2603_08448_conversational_diagnostic_ai_prospective_clinical_feasibility_real_time_human_safety_supervision [INFERRED 0.85]
- **Multilingual embedding model candidates compared for retrieval** — docs_research_sources_q3_modelcard_bge_m3_bge_m3, docs_research_sources_q3_modelcard_multilingual_e5_large_multilingual_e5_large, docs_research_sources_q3_modelcard_jina_embeddings_v3_jina_embeddings_v3, docs_research_sources_q3_modelcard_qwen3_embedding_0_6b_qwen3_embedding_0_6b, docs_research_sources_q3_modelcard_qwen3_embedding_8b_qwen3_embedding_8b, docs_research_sources_q3_docs_cohere_embed_embed_multilingual_v3_0, docs_research_sources_q3_docs_openai_embeddings_text_embedding_3_large, docs_research_sources_q3_pricing_voyage_ai_voyage_4_large [INFERRED 0.85]
- **BGE-M3 unified dense, sparse and multi-vector retrieval** — docs_research_sources_q3_modelcard_bge_m3_bge_m3, docs_research_sources_q3_modelcard_bge_m3_dense_retrieval, docs_research_sources_q3_modelcard_bge_m3_sparse_retrieval, docs_research_sources_q3_modelcard_bge_m3_multi_vector_retrieval, docs_research_sources_q3_modelcard_bge_m3_self_knowledge_distillation [EXTRACTED 1.00]
- **Reranker options (deferred second-stage ranking)** — docs_research_sources_q3_modelcard_bge_reranker_v2_m3_bge_reranker_v2_m3, docs_research_sources_q3_modelcard_bge_reranker_v2_m3_bge_reranker_v2_gemma, docs_research_sources_q3_modelcard_bge_reranker_v2_m3_bge_reranker_v2_minicpm_layerwise, docs_research_sources_q3_modelcard_qwen3_reranker_0_6b_qwen3_reranker_0_6b, docs_research_sources_q3_pricing_voyage_ai_rerank_2_5 [INFERRED 0.85]

## Communities (184 total, 29 thin omitted)

### Community 0 - "Turn Context & Rule Assessment"
Cohesion: 0.05
Nodes (54): assess_rules(), build_turn_context(), condition_support(), ConditionEvidence, discrimination(), fired_rule(), join_evidence(), live_conditions() (+46 more)

### Community 1 - "Deterministic Triage Engine"
Cohesion: 0.07
Nodes (52): ActionCode, TriageEngine, StopReason, escalating_engine(), fired_on_pain(), rule(), test_a_clear_leader_stops(), test_a_feature_no_live_condition_uses_is_not_asked() (+44 more)

### Community 2 - "Frontend Auth Pages & UI Kit"
Cohesion: 0.08
Nodes (68): radix-ui, react, sonner, ForgotPasswordPage(), handleSubmit(), ResetPasswordForm(), handleSubmit(), ResetPasswordPage() (+60 more)

### Community 3 - "Chat Message Components"
Cohesion: 0.06
Nodes (61): lucide-react, ChatHeader(), ChatMessage(), ChatMessageProps, paragraphs(), ADR-0016, ChatShell(), ChatShellProps (+53 more)

### Community 4 - "Model Service & Passages"
Cohesion: 0.05
Nodes (24): PassageType, create_app(), lifespan(), search(), _fallback_to_retrieved(), _passage_to_retrieved(), SearchRequest, embedding_model_name() (+16 more)

### Community 5 - "Consultation Session Models"
Cohesion: 0.06
Nodes (32): reasoning_timeout(), Base, ConsultationSession, Message, default_model_id(), ReasoningModelOption, _choose_reasoning_model(), _decision_payload() (+24 more)

### Community 6 - "Evidence Proposal Pipeline"
Cohesion: 0.06
Nodes (20): run_propose(), _widen(), cosine_similarity(), Embedder, build_index(), Hit, IndexMismatchError, PassageIndex (+12 more)

### Community 7 - "Auth Cookies & Account Routes"
Cohesion: 0.08
Nodes (35): clear_auth_cookies(), set_auth_cookies(), get_current_user(), EmailSender, delete_health_note(), delete_me(), get_health_note(), GoogleSignInRequest (+27 more)

### Community 8 - "Email Normalisation & Registration"
Cohesion: 0.08
Nodes (29): normalize_email(), EmailAlreadyRegistered, GoogleEmailNotVerified, GoogleIdentity, _credential_for_subject(), _sign_in_as(), sign_in_with_google(), Credential (+21 more)

### Community 9 - "Backend App Config"
Cohesion: 0.06
Nodes (29): GoogleTokenVerifier, cors_origins(), database_url(), email_sender_kind(), google_client_id(), knowledge_dir(), model_selector_enabled(), model_service_url() (+21 more)

### Community 10 - "Bootstrap Dataset Export"
Cohesion: 0.05
Nodes (23): export_bootstrap_dataset(), main(), personas_from_knowledge_base(), _phrase_answer(), _phrase_conclusion(), transcript_to_conversation(), write_jsonl(), _force_utf8_output() (+15 more)

### Community 11 - "Chat Page State"
Cohesion: 0.06
Nodes (53): ChatContent(), appendEntry(), handleRetry(), handleSend(), loadSession(), loadSessions(), submitTurn(), ChatEntry (+45 more)

### Community 12 - "App Shell & Marketing Pages"
Cohesion: 0.08
Nodes (40): next, nextConfig, AppShell(), HowItWorksPage(), AppLayout(), OnboardingContent(), OnboardingPage(), AuthLayout() (+32 more)

### Community 13 - "Triage Agent Loop"
Cohesion: 0.05
Nodes (18): RetrievedPassage, AgentTranscript, AgentTurn, build_retrieval_query(), MaxTurnsExceeded, Message, ReasoningClient, render_feature_vocabulary() (+10 more)

### Community 14 - "Triage CLI"
Cohesion: 0.05
Nodes (36): as_json(), ask_at_the_terminal(), build_parser(), _coerce(), find_knowledge_dir(), load_case(), main(), parse_inline() (+28 more)

### Community 15 - "Knowledge Schema Contracts"
Cohesion: 0.08
Nodes (47): Condition, EvidenceRow, Feature, RedFlagRule, test_a_decision_grounded_in_nothing_is_refused(), test_an_ask_requires_a_feature_and_a_question(), action_defs(), evidence_row() (+39 more)

### Community 16 - "Dashboard & Account Settings"
Cohesion: 0.09
Nodes (45): DashboardContent(), DashboardPage(), AccountSettingsContent(), AccountSettingsPage(), DeleteAccountSection(), handleDelete(), ProfileSettingsForm(), handleSave() (+37 more)

### Community 17 - "Email Verification"
Cohesion: 0.09
Nodes (30): serialize_per_email(), _issue_code(), request_verification_resend(), _send(), send_verification_code(), verify_email(), IncorrectVerificationCode, TooManyVerificationRequests (+22 more)

### Community 18 - "Decision Contract Package"
Cohesion: 0.07
Nodes (20): ActionDefinition, Actions, Clause, ComparisonOp, ConditionsFile, FeatureKind, FeaturesFile, _KnowledgeModel (+12 more)

### Community 19 - "Reasoning Backend Clients"
Cohesion: 0.07
Nodes (17): AttemptOutcome, ReasoningAttempt, ReasoningResult, FallbackReasoningClient, OpenRouterReasoningClient, VllmReasoningClient, RecordingReasoningClient, test_a_turn_the_server_threw_away_is_not_counted_as_a_success() (+9 more)

### Community 20 - "HealthBench & FDA CDS Guidance"
Cohesion: 0.05
Nodes (37): HealthBench: Evaluating Large Language Models Towards Improved Human Health (arXiv 2505.08775), Context-seeking theme (594 examples, 11.9%), Emergency referrals theme (482 examples, 9.6%), HealthBench Consensus (34 physician-consensus criteria, 3,671 examples), HealthBench Hard (top score 32%), Physician baselines with and without model assistance, Responding under uncertainty theme (1,071 examples, 21.4%), HealthBench seven themes and five axes (+29 more)

### Community 21 - "Account Route Tests"
Cohesion: 0.08
Nodes (42): _cookie_attributes(), _register(), _register_and_verify(), test_a_subsequent_request_identifies_the_signed_in_user(), test_google_sign_in_not_configured_is_service_unavailable(), test_me_without_a_session_is_unauthorized(), test_patch_me_rejects_overlong_display_name(), test_patch_me_updates_display_name() (+34 more)

### Community 22 - "Password Reset Errors"
Cohesion: 0.11
Nodes (29): IncorrectPasswordResetCode, NoPasswordCredential, PasswordResetCodeExpired, TooManyPasswordResetRequests, PasswordResetCode, _issue_code(), _password_credential(), request_password_reset() (+21 more)

### Community 23 - "Email Sending & Previews"
Cohesion: 0.08
Nodes (20): write_email_preview(), ConsoleEmailSender, _render_password_reset(), _render_verification(), _RenderedEmail, SesEmailSender, _code_block(), password_reset_email() (+12 more)

### Community 24 - "Triage Route Tests"
Cohesion: 0.11
Nodes (28): load_knowledge_base(), TriageAgent, _scripted_agent(), _build_client(), _register_and_sign_in(), _scripted_agent(), StaticRetrievalClient, test_a_declined_message_leaves_the_session_open() (+20 more)

### Community 25 - "API Error Handlers"
Cohesion: 0.06
Nodes (11): register_error_handlers(), InvalidDateOfBirth, check_password_strength(), PasswordTooWeak, test_acceptable_password_is_not_rejected(), test_common_password_check_is_case_insensitive(), test_common_password_is_rejected_with_a_reason(), test_other_top_breach_corpus_passwords_are_rejected() (+3 more)

### Community 26 - "Threshold Analysis"
Cohesion: 0.08
Nodes (22): EvidenceStrength, run_thresholds(), analyse(), Combination, eliminating_rows_needed(), reachable_scores(), rules_out_ceiling(), test_a_threshold_in_a_gap_is_not_fragile() (+14 more)

### Community 27 - "Knowledge Validation"
Cohesion: 0.14
Nodes (32): run_validate(), Severity, validate_directory(), errors(), knowledge(), messages(), set_evidence(), test_a_condition_with_no_evidence_warns() (+24 more)

### Community 28 - "Quote Provenance Corpus"
Cohesion: 0.09
Nodes (21): Corpus, load_corpus(), Verdict, verify_quotes(), check(), corpus_dir(), test_a_heading_counts_as_source_text(), test_a_near_miss_reports_the_closest_source_text() (+13 more)

### Community 29 - "Conversational Diagnostic AI Papers"
Cohesion: 0.07
Nodes (30): Towards Conversational Diagnostic AI (Tu et al., arXiv 2401.05654), AMIE (Articulate Medical Intelligence Explorer), Clinical history-taking, Diagnostic dialogue evaluation axes (history-taking, diagnostic accuracy, management reasoning, communication, empathy), Randomized double-blind crossover remote OSCE (149 scenarios, 20 PCPs), MediQ: Question-Asking LLMs and a Benchmark for Reliable Interactive Clinical Reasoning (Li et al., NeurIPS 2024), CRAFT-MD dataset, MediQ Expert System (+22 more)

### Community 30 - "Ingest Config & Robots"
Cohesion: 0.07
Nodes (10): DuplicateTargetError, _reject_duplicates(), http_get(), _ssl_context(), utc_today(), robots_url_for(), RobotsPolicy, content_hash() (+2 more)

### Community 31 - "TriageDecision Schema"
Cohesion: 0.06
Nodes (15): answer_text field (separate from rationale), TriageDecision, test_a_decline_needs_no_grounding(), test_a_red_flag_alone_still_grounds_a_decision(), test_an_emergency_red_flag_conclusion_may_name_conditions(), test_an_inform_always_ends_up_with_an_answer(), test_an_inform_answers_from_its_citations(), test_an_urgent_same_day_red_flag_may_name_conditions() (+7 more)

### Community 32 - "Database Migrations"
Cohesion: 0.08
Nodes (12): _database_url(), run_migrations_offline(), run_migrations_online(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade() (+4 more)

### Community 33 - "Data CLI Commands"
Cohesion: 0.07
Nodes (15): _load_embedder(), run_build(), run_clean(), run_eval(), run_index(), run_search(), run_verify_quotes(), clean_store() (+7 more)

### Community 34 - "Password Reset Codes"
Cohesion: 0.09
Nodes (21): codes_match(), generate_code(), hash_code(), codes_match(), generate_code(), hash_code(), test_codes_match_is_false_for_a_different_code(), test_codes_match_is_false_under_a_different_secret() (+13 more)

### Community 35 - "Data CLI Entry Point"
Cohesion: 0.09
Nodes (25): build_parser(), _force_utf8_output(), main(), blocking_fetch_failures(), _build_index(), _failed(), test_a_quote_only_failure_does_not_block_the_deployed_index(), test_a_verb_is_required() (+17 more)

### Community 36 - "Phase-1 Conditions & Features"
Cohesion: 0.10
Nodes (36): SELF_CARE (severity 0), Endometriosis [ROUTINE_APPOINTMENT], Normal menstrual variation [SELF_CARE], Polyendocrine metabolic ovarian syndrome (PMOS), formerly polycystic ovary syndrome (PCOS) [ROUTINE_APPOINTMENT], Uterine fibroids [ROUTINE_APPOINTMENT], evidence.csv (sparse condition-feature evidence grid), features.yaml (everything the system may ask about), Dark velvety patches of skin (acanthosis_nigricans) (+28 more)

### Community 37 - "Session Policy & Refresh"
Cohesion: 0.14
Nodes (21): InvalidSession, Session, end_all_sessions(), end_session(), get_active_session(), refresh_session(), _revoke(), start_session() (+13 more)

### Community 38 - "Agent Context Tests"
Cohesion: 0.13
Nodes (26): DecisionType, agent_with(), ask(), conclude(), conclude_decision(), gated_agent(), StubRetrieval, test_a_completed_rule_is_reported_as_met_once_its_answer_is_in() (+18 more)

### Community 39 - "Sign-In Throttling & Locks"
Cohesion: 0.11
Nodes (18): InvalidCredentials, TooManySignInAttempts, SignInFailure, _authenticate(), sign_in(), clear_failures(), is_locked_out(), record_failure() (+10 more)

### Community 40 - "Evaluation Metrics"
Cohesion: 0.11
Nodes (29): score(), outcome(), test_a_less_urgent_answer_is_under_triage(), test_a_more_urgent_answer_is_over_triage_not_under(), test_a_rate_over_nothing_is_none_not_zero(), test_a_self_care_label_cannot_be_under_triaged(), test_agreement_needs_more_than_one_variant_to_mean_anything(), test_an_empty_run_passes_no_gate() (+21 more)

### Community 41 - "Dialogue Runner"
Cohesion: 0.10
Nodes (22): run_consultation(), ScriptedAnswers, features_by_id(), test_a_consultation_ends(), test_a_red_flag_ends_the_consultation(), test_a_red_flag_stops_before_the_budget(), test_a_state_is_recorded_before_its_answer_is_applied(), test_a_valid_case_passes() (+14 more)

### Community 42 - "Embedding Benchmarks (MTEB, BGE-M3)"
Cohesion: 0.08
Nodes (28): MTEB: Massive Text Embedding Benchmark (arXiv 2210.07316), BEIR zero-shot retrieval benchmark, Eight MTEB task types (bitext mining, classification, clustering, pair classification, reranking, retrieval, STS, summarization), MTEB benchmark (8 tasks, 58 datasets, 112 languages), M3-Embedding / BGE-M3 paper (arXiv 2402.03216), BGE-M3 (M3-Embedding) model, MIRACL multilingual retrieval benchmark, MKQA cross-lingual retrieval benchmark (+20 more)

### Community 43 - "Evaluation Case Sets"
Cohesion: 0.11
Nodes (26): CaseVariant, EvaluationSet, _check_features_exist(), load_evaluation_set(), case(), label(), test_a_batch_file_loads(), test_a_number_is_refused_rather_than_stringified() (+18 more)

### Community 44 - "Topic Briefs from Knowledge"
Cohesion: 0.12
Nodes (20): KnowledgeBase, render_topic_brief(), _row_line(), _warning_signs_touching(), _check_conditions(), _check_evidence(), check_knowledge_base(), _check_nothing_is_dead_weight() (+12 more)

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
Cohesion: 0.14
Nodes (18): fetch_all(), forbidden(), make_plan(), recording(), responds(), transport(), test_already_present_still_reports_a_hash(), test_barred_url_is_never_requested() (+10 more)

### Community 49 - "Backend Test Fixtures"
Cohesion: 0.08
Nodes (8): client(), connection(), database_url(), db_session(), email_sender(), engine(), google_verifier(), RecordingEmailSender

### Community 50 - "Frontend Dependencies"
Cohesion: 0.07
Nodes (26): class-variance-authority, clsx, eslint, eslint-config-next, next-themes, react-dom, @react-oauth/google, shadcn (+18 more)

### Community 51 - "Account Deletion"
Cohesion: 0.10
Nodes (9): delete_user_account(), Base, PasswordResetSend, VerificationCodeSend, is_send_locked_out(), record_send(), test_is_send_locked_out_becomes_true_at_max_sends(), test_is_send_locked_out_is_false_with_no_sends() (+1 more)

### Community 52 - "Profile Details Validation"
Cohesion: 0.10
Nodes (18): InvalidHealthNote, normalize_health_note(), validate_date_of_birth(), _register_and_sign_in(), test_a_blank_health_note_clears_rather_than_storing_empty(), test_a_future_date_of_birth_is_refused(), test_a_health_note_can_be_deleted_without_closing_the_account(), test_a_health_note_keeps_her_own_line_breaks() (+10 more)

### Community 53 - "Retrieval Composition"
Cohesion: 0.16
Nodes (17): balanced_search(), WidenedHit, HashingEmbedder, index_of(), passage(), test_a_hit_is_widened_to_its_neighbours_in_the_same_document(), test_a_quote_only_neighbour_is_not_pulled_in_by_widening(), test_a_quote_only_passage_can_never_be_returned() (+9 more)

### Community 54 - "HTML Cleaning Tests"
Cohesion: 0.11
Nodes (19): document(), paragraphs(), test_chrome_wrappers_are_removed_by_class(), test_decomposing_a_wrapper_does_not_break_the_walk(), test_duplicate_paragraphs_within_a_section_are_dropped(), test_inline_markup_does_not_leave_a_space_before_punctuation(), test_locale_references_are_not_removed_from_the_text(), test_no_space_survives_after_an_opening_bracket() (+11 more)

### Community 55 - "Data Pipeline Skill Rules"
Cohesion: 0.10
Nodes (23): HerHealth Data Pipeline Skill, Evidence Batch YAML Review Gate (approved: true), Data Pipeline Stages (fetch, clean, evidence, validate, tables), RawStore Immutable Raw Snapshots, ADR 0006 Single-Source Condition Exception (adenomyosis), Blocked Conditions (coverage gaps as stated limitation), CDC Source, conditions.yaml (19 conditions) (+15 more)

### Community 56 - "Architecture Decisions & Model Serving"
Cohesion: 0.12
Nodes (24): ADR 0011 Controller-Free Triage, ADR 0013 Emergency Conclusions May Name Conditions (proposed), Benchmark Findings (under-triage 0.718, clarification collapse 0.856 to 0.000), benchmark_multilingual_v1 (menst) Benchmark, bootstrap_multi_turn.jsonl Retrain Bootstrap Data, AWS Deploy Pipeline (ECR, S3, SSM, single EC2, Caddy), Two Arabic Registers (MSA and Egyptian Arabic), Evaluation Merge Gates (+16 more)

### Community 57 - "Raw Store Lockfile"
Cohesion: 0.13
Nodes (23): read_lock(), write_lock(), record(), test_a_different_date_is_a_different_location(), test_documents_can_be_read(), test_documents_ignores_other_dates(), test_documents_is_empty_when_nothing_is_stored(), test_documents_land_in_a_dated_directory() (+15 more)

### Community 58 - "Cited Sources UI"
Cohesion: 0.13
Nodes (23): CitedSources(), CitedSourcesProps, distinctSources(), shortenQuote(), SourceLink(), ArticleCard(), ArticleCardProps, RecommendedArticlesSection() (+15 more)

### Community 59 - "OpenRouter/vLLM Client Calls"
Cohesion: 0.10
Nodes (12): _attempt_detail(), _available_ids_hint(), _build_messages(), _chat_completions_body(), _decide_via_chat_completions(), _drop_conditions_named_beside_a_red_flag(), HttpRetrievalClient, _parse_chat_completion_payload() (+4 more)

### Community 60 - "Google Sign-In"
Cohesion: 0.13
Nodes (10): GoogleSignInNotConfigured, GoogleTokenInvalid, GoogleOAuthTokenVerifier, UnconfiguredGoogleTokenVerifier, test_google_oauth_verifier_defaults_email_verified_to_false_when_absent(), test_google_oauth_verifier_rejects_a_malformed_token(), test_google_oauth_verifier_rejects_a_token_missing_required_claims(), test_google_oauth_verifier_rejects_an_invalid_token() (+2 more)

### Community 61 - "Knowledge Table Rendering"
Cohesion: 0.13
Nodes (14): _evidence(), run_tables(), build_tables(), _conditions_table(), _constants_table(), _escape_markdown(), _evidence_table(), _features_table() (+6 more)

### Community 62 - "El Saddik Lab Papers"
Cohesion: 0.10
Nodes (19): TextureMeDefect: LLM-based Synthetic Railway Defect Texture on Mobile Devices (IEEE ICCE 2025), Abdulmotaleb El Saddik, Fine-tuned GPT-3 on synthetic defect-texture dataset, IEEE International Conference on Consumer Electronics (ICCE), InstructPix2Pix (image+text editing model), Multimodal User Interaction Interface (MUII), Rahatara Ferdousi, SDXL (text-to-image model) (+11 more)

### Community 63 - "Code Guide & Repo Map"
Cohesion: 0.11
Nodes (17): Code guide, Data pipeline: fetch -> clean -> build -> validate -> eval, Evaluation harness (herhealth-eval / make eval), gated vs reported metrics, fetch_all policy order: licence guard, already present, dry run, fetch, Invariants and where each is enforced, RawStore: immutable raw/{source}/{date}/ store bound to one date, Backend triage core vs app layer separation, TriageEngine.should_stop: six stopping rules, first match wins (+9 more)

### Community 64 - "Access Tokens & Current User"
Cohesion: 0.14
Nodes (11): InvalidAccessToken, generate_refresh_token(), issue_access_token(), read_access_token(), _serializer(), test_generate_refresh_token_returns_distinct_high_entropy_values(), test_hash_refresh_token_is_deterministic_and_does_not_leak_the_raw_value(), test_read_access_token_rejects_a_tampered_token() (+3 more)

### Community 65 - "Plausibility Scoring"
Cohesion: 0.13
Nodes (15): plausibility(), test_a_rules_out_that_cannot_rule_out_is_rejected(), test_clamp_is_wide_enough_to_be_irrelevant_in_practice(), test_conditions_do_not_compete(), test_everything_can_be_implausible_at_once(), test_it_does_not_overflow_on_a_large_score(), test_it_is_monotonic(), test_it_stays_in_range_at_extremes() (+7 more)

### Community 66 - "ICD-11 Lookup"
Cohesion: 0.10
Nodes (8): run_icd(), credentials_from_env(), fetch_token(), IcdError, IcdProposal, propose_codes(), search_icd(), _strip_markup()

### Community 67 - "Evaluation CLI"
Cohesion: 0.15
Nodes (10): as_json(), build_parser(), _line(), main(), render(), Metrics, Evaluation, failing_cases() (+2 more)

### Community 68 - "Fetch Plan"
Cohesion: 0.14
Nodes (5): FetchPlan, Target, _fetch_one(), _utc_now(), RawStore

### Community 69 - "Triage Glossary"
Cohesion: 0.11
Nodes (24): CLAUDE.md Project Spec (binding), CONTEXT.md Triage Glossary, Burden, Clarification, Clause, Condition, Differential, Evidence Row (+16 more)

### Community 70 - "Weights & Action Codes"
Cohesion: 0.11
Nodes (16): ADR 0005: plausibility is an independent logistic, ADR 0009: rules_out does not override accumulated support, rules_out does not eliminate regardless of accumulated support, actions.yaml (four urgency actions), knowledge/ README, weights.yaml (ordinal-to-log-odds mapping and stopping thresholds), argues_against (-0.5 log-odds), max_questions (6) (+8 more)

### Community 71 - "Condition Provenance Repair"
Cohesion: 0.15
Nodes (13): drop_unknown_conditions(), ClosedVocabularyViolation, conclude(), test_a_decision_with_only_real_conditions_is_returned_unchanged(), test_a_decline_is_unaffected(), test_a_name_with_a_space_is_dropped_rather_than_failing_the_decision(), test_a_well_formed_name_is_left_for_the_second_layer(), test_an_invented_rule_id_is_still_a_hard_failure() (+5 more)

### Community 72 - "Profile & Health Note"
Cohesion: 0.18
Nodes (9): InvalidDisplayName, HealthNote, clear_health_note(), health_note_for(), _load_user(), normalize_display_name(), update_date_of_birth(), update_display_name() (+1 more)

### Community 73 - "Ingest Target Config Tests"
Cohesion: 0.14
Nodes (14): load_plan(), make_target(), test_an_empty_file_loads_to_an_empty_plan(), test_default_agent_identifies_the_project(), test_duplicate_targets_are_rejected(), test_guard_is_scoped_to_its_own_source(), test_guard_matches_a_barred_path(), test_guard_permits_everything_else_from_the_same_source() (+6 more)

### Community 74 - "shadcn Component Config"
Cohesion: 0.09
Nodes (21): aliases, components, hooks, lib, ui, utils, iconLibrary, menuAccent (+13 more)

### Community 75 - "CLAUDE"
Cohesion: 0.17
Nodes (10): Clinical Data Authoring Skill, Source Ingestion Skill, Legacy Source Precedence List (NICE CKS first), build/conflicts.jsonl (gitignored scratch, not the record), Excluded Sources (NICE CKS, RCOG/ACOG, UMLS, WHO ICD), HerHealthGPT Multilingual Reproductive-Health Triage System, services/frontend (Next.js responsive web app), Source Precedence on Conflict (NHS 2, others 3, CDC 4) (+2 more)

### Community 76 - "extract diagrams"
Cohesion: 0.15
Nodes (9): Diagram, find_diagrams(), heading_before(), kind_of(), main(), slugify(), write(), find_locale_references() (+1 more)

### Community 77 - "uni server vllm"
Cohesion: 0.16
Nodes (16): Retraining on multi-turn data (bootstrap_dataset.py, bootstrap_multi_turn.jsonl), Runbook: herhealth LoRA dev endpoint, Known quirks: thinking mode on by default, code-switching, register variance, Ephemeral vast.ai vLLM dev endpoint for the herhealth LoRA, vllm serve command with --enable-lora and --max-model-len 16384, Runbook: vLLM + LoRA on a friend's GPU PC, vllm triage mode with automatic OpenRouter fallback, WSL2 Ubuntu vLLM setup on a friend's GPU PC (port 8002) (+8 more)

### Community 78 - "cards"
Cohesion: 0.13
Nodes (7): _arrow(), feature_reports(), FeatureReport, render_condition_cards(), render_feature_cards(), write_cards(), run_cards()

### Community 79 - "conditions"
Cohesion: 0.23
Nodes (13): ADR 0001: Source traceability replaces clinician review, ADR 0006: a condition may cite one source if it says why, conditions.yaml (everything the system may suspect), Adenomyosis [ROUTINE_APPOINTMENT], Bacterial vaginosis [ROUTINE_APPOINTMENT], Vaginal thrush (yeast infection) [SELF_CARE], Unusual vaginal discharge (abnormal_discharge), What the discharge looks like (discharge_appearance) (+5 more)

### Community 80 - "0002 conversational triage prior art and"
Cohesion: 0.13
Nodes (17): Silver annotation (not clinician-adjudicated), Adenomyosis: the only condition with no corroborating source (NHS only), Two-source rule for conditions, Deterministic stopping controller (TriageEngine.should_stop), Bootstrap multi-turn retraining data (bootstrap_multi_turn.jsonl, 18 conversations), Research 0002: Conversational triage prior art and multilingual sources, AMIE needed a self-play training regime (11,686 dialogues per iteration), not a prompt, BiMediX2 (arXiv:2412.07769): the Arabic gap is a data gap, not a capability ceiling (+9 more)

### Community 81 - "evaluation"
Cohesion: 0.15
Nodes (3): CanonicalCase, CaseLabel, _EvaluationModel

### Community 82 - "test age bands"
Cohesion: 0.16
Nodes (8): age_band_for(), age_in_years(), _allowed_age_bands(), test_a_birthday_on_29_february_does_not_crash_in_a_non_leap_year(), test_age_is_not_incremented_until_the_birthday(), test_each_band_is_reachable(), test_every_allowed_value_is_reachable(), test_every_band_this_module_returns_is_a_real_allowed_value()

### Community 83 - "evidence"
Cohesion: 0.16
Nodes (7): run_evidence(), Batch, BatchError, build_evidence_csv(), load_batches(), _reject_duplicates(), write_rows()

### Community 84 - "README"
Cohesion: 0.23
Nodes (14): conversation.svg (hand holding a phone showing chat bubbles and a typing indicator), error.svg (person beside a large warning triangle with exclamation mark over a browser window), not-found.svg (person standing in a frame holding a tile, with a circular refresh/retry badge), onboarding.svg (unDraw 'medicine': clinicians in white coats with a potted plant against a tiled backdrop), Illustrations README — download these by hand, Brand primary colour #9F1239 (--primary in globals.css), Illustration component (renders nothing when the file is missing), Licence-driven source exclusions (NICE CKS, RCOG, ACOG, UMLS) per CLAUDE.md (+6 more)

### Community 85 - "tsconfig"
Cohesion: 0.11
Nodes (18): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+10 more)

### Community 86 - "CONTEXT"
Cohesion: 0.18
Nodes (13): Accounts bounded context (CONTEXT.md), Access token (Accounts term), Conversation (Accounts term), Credential (Accounts term), Cycle data (Accounts term), Health note (Accounts term), Linking (Accounts term), Message (Accounts term) (+5 more)

### Community 87 - "KNOWLEDGE BASE"
Cohesion: 0.15
Nodes (14): knowledge.py Pydantic schemas (Feature, Condition, EvidenceRow, RedFlagRule, Source, Weights, Actions, KnowledgeBase), Build time vs request time use of the seven knowledge files, The knowledge base, explained, Evidence grid: sparse, keyed by (condition_id, feature_id, value), Five evidence strengths and their log-odds, Knowledge schema (ER model, foreign keys, invariants), Log-odds scoring and plausibility conversion, Question-condition graph with typed weighted edges (+6 more)

### Community 88 - "observed triage behaviour"
Cohesion: 0.16
Nodes (15): Triage system prompt (never diagnose, one question at a time), Red flags: 14 rules (7 EMERGENCY, 7 URGENT_SAME_DAY), Observed triage behaviour, Conditions named only at EMERGENCY, Defect: internal identifiers and disclaimer leaked into user-facing text, Method: transcripts read back from the messages table of the deployed stack, Multi-turn consultation concluding at ROUTINE_APPOINTMENT, Defect: first question had no discriminating value (+7 more)

### Community 89 - "test knowledge"
Cohesion: 0.17
Nodes (11): Weights, log_odds_for(), test_all_five_strengths_must_be_present(), test_equal_bars_are_rejected_not_merely_lower_ones(), test_log_odds_must_be_monotonic(), test_max_questions_defaults_to_six(), test_neutral_must_be_zero(), test_self_care_bar_must_exceed_the_routine_bar() (+3 more)

### Community 90 - "check repo hygiene"
Cohesion: 0.26
Nodes (13): check_env_filename(), check_line_length(), check_root_entry(), check_secrets(), check_text_posing_as_binary(), Finding, inspect(), is_binary() (+5 more)

### Community 91 - "0015 a user may keep a date of birth and"
Cohesion: 0.24
Nodes (12): ADR 0010: Multilingual embeddings beat Arabic-specific ones; the chunk is a sentence, ADR 0011: controller-free triage, ADR 0011 migration checklist (10 steps), consultation_session and message tables (session persistence), ADR 0012: API-hosted reasoning model and a guarded web-search fallback, ADR 0013: An EMERGENCY conclusion may name matching conditions, ADR 0014: An off-scope message is declined, not triaged, Risk: scope is judged by the model (false refusal is under-triage; unmeasured) (+4 more)

### Community 92 - "FLOW EXPLAINED"
Cohesion: 0.20
Nodes (11): The new flow, explained, Agentic RAG loop (retrieve, reason, ask or conclude, repeat), Backend orchestrator, Embedding / semantic search model (bge-m3), Licensing filter at live search time (unfinished), Reasoning model (QLoRA fine-tuned model + base), Retrieval index (source sentences + evidence.csv rows as sentences), Session store (Postgres) (+3 more)

### Community 93 - "test evaluation runner"
Cohesion: 0.14
Nodes (8): Language, RegisterStyle, _asked_a_question(), run_case(), test_a_case_runs_and_produces_an_outcome(), test_a_variant_cannot_carry_an_expected_action(), test_an_annotation_typo_is_refused_not_scored_as_a_miss(), test_the_fired_rule_is_recorded()

### Community 94 - "test accounts passwords"
Cohesion: 0.20
Nodes (7): hash_password(), verify_password(), test_hash_is_argon2id(), test_hash_never_contains_the_plaintext(), test_hashing_the_same_password_twice_gives_different_hashes(), test_verify_password_accepts_the_matching_password(), test_verify_password_rejects_a_wrong_password()

### Community 96 - "0011 controller free triage"
Cohesion: 0.16
Nodes (6): Serving-time search must filter where may_be_ingested (NHS citable_only leak risk), evidence.csv is relational and ordinal, not usefully retrievable as text, Research 0003: Phase-1 evaluation of a two-page NHS-grounded MVP, Critical escalation recall (999/A&E cases; any miss blocks release), Hazard log inspired by NHS DCB0129 (not a compliance claim), render_red_flags()

### Community 97 - "q2 hf trl dataset formats"
Cohesion: 0.25
Nodes (13): HF TRL docs: Dataset formats and types (research source q2), Conversational dataset format (messages with role/content), TRL dataset types (language modeling, prompt-only, prompt-completion, preference, unpaired preference, stepwise supervision), Harmony response format (OpenAI GPT OSS), Prompt-completion dataset type, Standard dataset format (plain text columns), Tool-calling datasets (tools column, tool_calls, get_json_schema), HF TRL docs: SFT Trainer (research source q2) (+5 more)

### Community 98 - "frontend"
Cohesion: 0.15
Nodes (11): backend CI workflow, backend workflow job: app (ruff, mypy, make test-api with testcontainers PostgreSQL), data CI workflow (lint, test, validate knowledge, trace consultations), data workflow job: check (make lint, test, validate, triage-all), frontend CI workflow (npm ci, build, reporting-only lint), frontend workflow job: build, hygiene workflow (repo hygiene check on every branch), 2026-09-17 contamination incident (injected payload and leaked env backup) (+3 more)

### Community 99 - "metrics"
Cohesion: 0.18
Nodes (4): _agreement(), CaseOutcome, _rate(), _severity()

### Community 100 - "thresholds"
Cohesion: 0.14
Nodes (3): robust_midpoint(), ThresholdPlacement, test_the_midpoint_is_taken_in_log_odds()

### Community 101 - "package"
Cohesion: 0.14
Nodes (14): dependencies, class-variance-authority, clsx, lucide-react, next, next-themes, radix-ui, react (+6 more)

### Community 102 - "test accounts deletion"
Cohesion: 0.29
Nodes (7): _build_client(), _count_for_user(), _count_messages_for_user(), deletion_client(), _register_and_sign_in(), test_delete_account_removes_every_user_referencing_row(), test_delete_account_requires_authentication()

### Community 103 - "0001 llm triage architecture"
Cohesion: 0.28
Nodes (12): ADR 0011 risk register (models under-ask; wrong action within vocabulary is uncovered), Research 0001: Reconsidering the deterministic controller (LLM triage architecture), AMIE, Towards Conversational Diagnostic AI (arXiv:2401.05654 / Nature), CRAFT-MD (Nature Medicine 2024): vignette benchmarks overstate conversational performance, From Promising Capability to Pervasive Bias: LLMs for ED triage (arXiv:2504.16273), EQUITRIAGE (arXiv:2605.03998): decision-flip 9.9-43.8%, directional female under-triage, HealthBench (arXiv:2505.08775): context-seeking lags; worst-at-16 drops by a third, KnowGuard (arXiv:2509.24816): knowledge-driven abstention (+4 more)

### Community 104 - "ROADMAP"
Cohesion: 0.19
Nodes (12): Immutable TriageState / Decision / StopReason, How a consultation runs (model extracts, controller decides, model phrases), Project status, Sequence of one consultation turn, Immediate next step: backfill thin conditions, then build the retrieval corpus, Not started (frontend, model serving, retrieval corpus, benchmark cases), Triage core UML (KnowledgeBase, TriageEngine, TriageState, Decision), Roadmap (+4 more)

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
Nodes (6): Source, source(), test_permissions_follow_status(), test_precedence_ranks_sources_that_are_not_yet_usable(), test_status_is_required_so_unchecked_licensing_cannot_default_to_usable(), test_unknown_status_is_rejected()

### Community 109 - "CLAUDE"
Cohesion: 0.27
Nodes (8): ingest.lock.jsonl (url, sha256, licence per fetched document), services/backend (FastAPI triage and orchestration), services/model (vLLM generation, bge-m3 embeddings), make verify-quotes (verbatim quote check), HANDOFF.md (2026-09-02), Citations End to End (RetrievedPassage.url, cited_passages, ADR 0012), Intermittent Silent Hang in Triage Turn (REASONING_TIMEOUT_SECONDS), Run the Full App Locally (Postgres, retrieval :8001, backend :8000, frontend :3000)

### Community 110 - "eventloop"
Cohesion: 0.27
Nodes (3): use_selector_loop_on_windows(), main(), main()

### Community 111 - "0004 severe pelvic pain is urgent not em"
Cohesion: 0.20
Nodes (5): NHS three-page conflict on severe pelvic pain (pelvic pain, period pain, ovarian cyst pages), sudden_severe_pelvic_pain red flag escalates to EMERGENCY, DEFAULT_SYSTEM_PROMPT (never diagnose; a request, not a guarantee), Risk: a wrong condition named at the highest urgency, unmeasured by make eval, NHS pelvic pain page snapshot (nhs_pelvic_pain_2025-11-24)

### Community 112 - "0010 multilingual embeddings beat arabic"
Cohesion: 0.21
Nodes (9): Alsubhi et al., Optimizing RAG Pipelines for Arabic (arXiv:2506.06339), multilingual-e5-large (named fallback, 70.31), Unverified: French coverage and reproductive-health domain transfer, services/model: vLLM serving bge-m3 plus base model with QLoRA adapter, CPU-only services/model: bge-m3 embedding and one search endpoint, LoRA Learns Less and Forgets Less (arXiv:2405.09673), MMTEB (arXiv:2502.13595): best public multilingual embedder has 560M parameters, Corpus justifies a ~0.6B self-hosted encoder; no serving-time reranker; no hosted API (+1 more)

### Community 113 - "0014 an off scope message is declined no"
Cohesion: 0.21
Nodes (7): Live test finding: ungrounded base model fabricated citations (ACOG, Mayo Clinic) and concluded-and-asked at once, Provenance cap: fallback-only grounding may not resolve to SELF_CARE, A DECLINE does not conclude the consultation, DeclineCard (frontend; not a ConclusionCard variant), Live failure: 'who won world cup 2026' answered as SELF_CARE citing a real CBC sentence, An INFORM renders as an ordinary chat bubble and keeps the session active, Risk: inform-versus-triage boundary judged by the model; unmeasured; ungrounded prose surface

### Community 116 - "README"
Cohesion: 0.23
Nodes (6): The benchmark, as it arrived (README), Evaluation pipeline: eval/benchmark -> make eval-cases -> eval/cases -> make eval -> build/eval, Silver annotations, not clinician-adjudicated, SOURCE.md (benchmark provenance, label vocabulary, language tie), Benchmark cases README (batch_NN.yaml format), Silver annotations read off the benchmark's reference answers

### Community 117 - "CLAUDE"
Cohesion: 0.20
Nodes (6): ADR 0007 What the First Real Consultations Showed, ADR 0009 (rules_out, revisit before first row), Five Evidence Weights (ordinal scale), red_flags.yaml (16 escalation rules), weights.yaml (ordinal-to-log-odds, thresholds), Evidence Strength

### Community 118 - "clean"
Cohesion: 0.20
Nodes (6): clean_html(), flush(), Section, _strip_boilerplate(), test_headings_split_sections(), test_replacement_characters_are_refused_not_kept()

### Community 119 - "0001 source traceability replaces clinic"
Cohesion: 0.20
Nodes (4): Catastrophic forgetting under narrow SFT (arXiv:2506.09428, 2510.17776), TRL SFTTrainer dataset formats and assistant_only_loss, ALFA: Aligning LLMs to Ask Good Questions (arXiv:2502.14860, MediQ-AskDocs), Attribute-level supervision: question quality made labelable without a clinician

### Community 120 - "0005 plausibility is an independent logi"
Cohesion: 0.20
Nodes (7): plausibility_floor (0.05, -2.94 log-odds), Softmax across the differential (rejected option), stop_margin fires less often under a logistic; controller leans on max_questions, Weights._rules_out_must_actually_rule_out validator, Search B: feature/vocabulary mapping from prose to features.yaml (not built), Know Your Limits: A Survey of Abstention in LLMs (arXiv:2407.18418), Documentation drift between CLAUDE.md counts and files on disk (fixed)

### Community 121 - "0001 injected postcss payload and leaked"
Cohesion: 0.29
Nodes (7): Security 0001: injected postcss payload and leaked env backup, scripts/check_repo_hygiene.py: five hygiene rules, The history purge with git filter-branch, verified in a mirror, Branches still carrying the payload, Issue 1: foreign crypto/blockchain code injected into postcss.config.mjs, Issue 2: backend.env.bak committed with live credentials, Re-infection was a merge of a stale branch, not malware

### Community 122 - "build index"
Cohesion: 0.27
Nodes (8): build-index workflow (publish production retrieval index to S3), Pinned BAAI/bge-m3 revision (BGE_M3_REVISION), build-index job: fetch, clean, pin bge-m3, index, check, publish, RETRIEVAL_INDEX_VERSION repository variable, deploy workflow (production deploy to the single EC2 host), deploy job: build three images, push to ECR, upload deploy files, run deploy.sh via SSM, Deploy through SSM Run Command (herhealth-deploy document), publish-index.sh script

### Community 123 - "deploy"
Cohesion: 0.45
Nodes (9): dc(), healthy_through_caddy(), install_files(), prune_images(), reload_caddy(), rollback(), say(), deploy.sh script (+1 more)

### Community 125 - "README"
Cohesion: 0.22
Nodes (9): Case: heavy prolonged periods, early forties, Case: vulval itching with discharge, no pain, Controller demonstration cases README, The higher bar on concluding SELF_CARE, Stopping rule 1: a red flag outranks the differential, Stopping rule 5: the question budget, Case: answers nothing (the floor case), Case: sudden severe pelvic pain (+1 more)

### Community 126 - "test known background"
Cohesion: 0.25
Nodes (6): render_known_background(), test_a_note_is_framed_as_background_and_not_as_a_symptom(), test_an_age_band_tells_the_model_not_to_ask_again(), test_both_fields_render_together(), test_nothing_stored_renders_nothing(), test_the_block_says_the_source_is_her_profile_not_the_conversation()

### Community 127 - "onboarding"
Cohesion: 0.42
Nodes (9): grandfatherReturningUser(), hasCompletedOnboarding(), hasDismissedGettingStarted(), markOnboardingComplete(), markUserFlag(), needsFirstTimeOnboarding(), readUserList(), writeUserList() (+1 more)

### Community 128 - "0002 yaml for nested files csv for the e"
Cohesion: 0.20
Nodes (5): ADR 0002: Nested knowledge files are YAML; the evidence grid is CSV, ADR 0003: evidence.csv is generated from approved batches, make evidence (deterministic evidence.csv build), Fallback-fetch review queue (candidate evidence batches), What is implemented (knowledge base, controller, contracts, ingestion, provenance)

### Community 129 - "0008 showing what symptoms align with"
Cohesion: 0.20
Nodes (8): ADR 0008: showing what symptoms align with, Decision.differential presentation filter (above floor, supporting row, top three), Real exposure is medical-device/CDS regulation, not HIPAA; protection is output design, Seven presentation rules enforced in code (action first, never one item, no numbers, nothing on red flag, always cited), Automation bias (errors of omission under urgency) as regulator-named under-triage, FDA Clinical Decision Support Software guidance (29 Jan 2026), Phase-1 intended-purpose statement (MHRA SaMD guidance), What the user sees: action, what it aligns with, citations

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
Cohesion: 0.29
Nodes (4): health(), _probe_with(), test_transaction_is_isolated_alpha(), test_transaction_is_isolated_beta()

### Community 138 - "store"
Cohesion: 0.20
Nodes (3): _report_fetch(), run_fetch(), FetchRecord

### Community 139 - "PHASE 1 SUMMARY"
Cohesion: 0.25
Nodes (8): ingest.lock.jsonl: tracked lockfile for source content, Knowledge base limitations (not clinician-adjudicated, cancers absent, weak elimination), Phase 1 summary - seed knowledge, Headline finding: elimination barely works, Phase 1 limitations (untuned thresholds, single-source adenomyosis, English-only probes), Ready for Phase 2: mapping action codes onto benchmark risk labels first, Scope grew from three conditions to twelve before the reasoning core ran, Known problems carried (nothing leaves the differential, everything returns URGENT_SAME_DAY)

### Community 140 - "q4 vllm lora adapters docs"
Cohesion: 0.31
Nodes (8): vLLM docs: LoRA Adapters (research source q4), Dynamic LoRA loading (/v1/load_lora_adapter, VLLM_ALLOW_RUNTIME_LORA_UPDATING, LoRAResolver plugins), LoRA model lineage in the model card (parent / root, base_model_name), vllm serve --enable-lora --lora-modules {name}={path}, Server-wide LoRA configuration (max_loras, max_lora_rank, max_cpu_loras), LoRARequest (per-request adapter selection, offline), LoRA for multimodal models (tower/connector, default_mm_loras), SupportsLoRA model interface

### Community 141 - "compose.prod"
Cohesion: 0.36
Nodes (7): ECR images: herhealth-frontend, herhealth-backend, herhealth-retrieval (SHA-tagged, immutable), compose.prod.yml (production topology: one host, four containers), backend service (herhealth-backend image, port 8000, RDS), caddy service (TLS reverse proxy, only published ports), frontend service (herhealth-frontend image, port 3000), retrieval service (herhealth-retrieval image, bge-m3, port 8001), caddy-data.sh script

### Community 142 - "setup uni vllm"
Cohesion: 0.47
Nodes (8): adapter_arg(), check(), clean(), HF_HOME, running(), say(), setup-uni-vllm.sh script, stop()

### Community 143 - "package"
Cohesion: 0.22
Nodes (9): devDependencies, eslint, eslint-config-next, tailwindcss, @tailwindcss/postcss, @types/node, @types/react, @types/react-dom (+1 more)

### Community 145 - "0007 what the first real consultations s"
Cohesion: 0.36
Nodes (3): ADR 0007: what the first real consultations showed, Finding 4: rule 4 returns the top condition's action, not the most urgent live one (latent under-triage, xfail-pinned), BED-LLM / ASIG / CA-BED: expected-information-gain question selection

### Community 146 - "q4 hf peft lora conceptual"
Cohesion: 0.32
Nodes (5): Train adapters with PEFT (peft_config=LoraConfig()), HF PEFT docs: index (research source q4), PEFT (Parameter-Efficient Fine-Tuning) library, Default LoRA init (Kaiming-uniform A, zero B, identity transform), LoraConfig (r, lora_alpha, target_modules, bias, use_rslora, rank_pattern)

### Community 147 - "q3 modelcard multilingual e5 large"
Cohesion: 0.36
Nodes (6): XLM-RoBERTa backbone, Jina-XLM-RoBERTa architecture, intfloat/multilingual-e5-large model card - Hugging Face capture, Mr. TyDi benchmark results (MRR@10, incl. Arabic 77.5), intfloat/multilingual-e5-large, Multilingual E5 Text Embeddings: A Technical Report (arXiv 2402.05672)

### Community 149 - "clean"
Cohesion: 0.32
Nodes (4): classify_heading(), SectionType, test_escalation_beats_other_matches(), test_headings_are_classified()

### Community 150 - "CONTEXT"
Cohesion: 0.29
Nodes (7): Cleaning and section_type Segmentation, Four Action Codes (SELF_CARE to EMERGENCY), actions.yaml (four action codes per locale), Action Code, Escalation, Over-triage, Under-triage

### Community 152 - "q3 modelcard qwen3 embedding 0.6b"
Cohesion: 0.48
Nodes (5): Qwen/Qwen3-Embedding-0.6B model card - Hugging Face capture, Qwen3-Embedding-0.6B, Qwen3 Embedding series (embedding + reranking, 0.6B/4B/8B), Qwen/Qwen3-Reranker-0.6B model card - Hugging Face capture, Qwen3-Reranker-0.6B

### Community 153 - "test clean"
Cohesion: 0.29
Nodes (4): find_escalation_sentences(), test_escalation_language_is_found_mid_paragraph(), test_escalation_sentences_are_verbatim(), test_ordinary_prose_is_not_treated_as_escalation()

### Community 154 - "CONTEXT"
Cohesion: 0.40
Nodes (4): HerHealth Monorepo Conventions Skill, packages/contracts (Pydantic schemas, error codes, safety policy), Plausibility, Log-Odds to Plausibility Conversion (scoring.py, ADR 0005)

### Community 156 - "clean"
Cohesion: 0.33
Nodes (3): is_link_list(), test_a_clinical_heading_is_not_a_link_list(), test_link_list_headings_are_recognised()

### Community 157 - "issue tracker"
Cohesion: 0.40
Nodes (5): Agent docs: issue tracker (GitHub), Issue tracker: GitHub Issues via the gh CLI, Wayfinding operations (map issue, child tickets, blocking, claim, resolve), Agent docs: triage labels, Five canonical issue-triage label roles

### Community 158 - "README"
Cohesion: 0.40
Nodes (5): compose.yml (local development database), postgres service (postgres:16-alpine, local dev), Postman collection README (manual API testing), HerHealthGPT.postman_collection.json, HerHealthGPT.local.postman_environment.json (baseUrl http://localhost:8000)

### Community 159 - "refresh secrets"
Cohesion: 0.70
Nodes (4): get_optional_secret(), get_secret(), refresh-secrets.sh script, urlencode()

### Community 160 - "pyproject"
Cohesion: 0.80
Nodes (5): herhealth-backend, herhealth-contracts, herhealth-data, herhealth-model, herhealthgpt

### Community 165 - "package"
Cohesion: 0.40
Nodes (5): scripts, build, dev, lint, start

### Community 166 - "q3 modelcard bge reranker v2 m3"
Cohesion: 0.83
Nodes (3): BAAI/bge-reranker-v2-m3 model card - Hugging Face capture, BAAI/bge-reranker-v2-gemma (LLM-based reranker), BAAI/bge-reranker-v2-minicpm-layerwise

## Ambiguous Edges - Review These
- `Two-Question Evidence Row Authoring (listed? absence doubts?)` → `argues_against Only When Source Is Explicit`  [AMBIGUOUS]
  .claude/skills/clinical-data-authoring/SKILL.md · relation: conceptually_related_to
- `HerHealth Monorepo Conventions Skill` → `Frontend Is Not a PWA`  [AMBIGUOUS]
  .claude/skills/herhealth-repo/SKILL.md · relation: conceptually_related_to
- `Legacy Source Precedence List (NICE CKS first)` → `Excluded Sources (NICE CKS, RCOG/ACOG, UMLS, WHO ICD)`  [AMBIGUOUS]
  .claude/skills/source-ingestion/SKILL.md · relation: conceptually_related_to
- `Legacy Source Precedence List (NICE CKS first)` → `Source Precedence on Conflict (NHS 2, others 3, CDC 4)`  [AMBIGUOUS]
  .claude/skills/source-ingestion/SKILL.md · relation: conceptually_related_to
- `ADR 0011 Controller-Free Triage` → `Red Flag`  [AMBIGUOUS]
  CONTEXT.md · relation: conceptually_related_to
- `ADR 0011 Controller-Free Triage` → `Pre-ADR-0011 Stance: No Fine-Tuning, Decision Lives in Python`  [AMBIGUOUS]
  README.md · relation: conceptually_related_to
- `gold_seeds_styled Benchmark (540 rows, 90 seeds x 6 registers)` → `Issue #20 ADR 0011 Migration (items 5, 7-9)`  [AMBIGUOUS]
  HANDOFF.md · relation: references
- `Frontend Is Not a PWA` → `CONTRIBUTING.md`  [AMBIGUOUS]
  CONTRIBUTING.md · relation: conceptually_related_to
- `Verdict: replacing the controller with an end-to-end LLM is contradicted by every primary evaluation found` → `AMIE, Towards Conversational Diagnostic AI (arXiv:2401.05654 / Nature)`  [AMBIGUOUS]
  docs/research/0001-llm-triage-architecture.md · relation: conceptually_related_to
- `Rule: illustration SVGs stay out of git` → `conversation.svg (hand holding a phone showing chat bubbles and a typing indicator)`  [AMBIGUOUS]
  services/frontend/public/illustrations/README.md · relation: conceptually_related_to
- `Towards Physician-Centered Oversight of Conversational Diagnostic AI (Vedadi et al., arXiv 2507.15743)` → `A Prospective Clinical Feasibility Study of a Conversational Diagnostic AI in an Ambulatory Primary Care Clinic (Brodeur et al., arXiv 2603.08448)`  [AMBIGUOUS]
  docs/research/sources/q5-arxiv-2603.08448-conversational-diagnostic-ai-prospective-clinical-feasibility.pdf · relation: cites

## Knowledge Gaps
- **134 isolated node(s):** `HF_HOME`, `react-dom`, `shadcn`, `tw-animate-css`, `@tailwindcss/postcss` (+129 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1370 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **29 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TriageEngine` connect `Deterministic Triage Engine` to `Turn Context & Rule Assessment`, `Evaluation CLI`, `Dialogue Runner`, `Bootstrap Dataset Export`, `Evaluation Case Sets`, `Topic Briefs from Knowledge`, `Triage CLI`, `Knowledge Schema Contracts`, `0002 conversational triage prior art and`, `Decision Contract Package`, `test evaluation runner`, `engine`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Are the 84 inferred relationships involving `TriageEngine` (e.g. with `Deterministic stopping controller (TriageEngine.should_stop)` and `run_case()`) actually correct?**
  _`TriageEngine` has 84 INFERRED edges - model-reasoned connections that need verification._
- **What connects `HF_HOME`, `react-dom`, `shadcn` to the rest of the system?**
  _134 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Turn Context & Rule Assessment` be split into smaller, more focused modules?**
  _Cohesion score 0.04553264604810996 - nodes in this community are weakly interconnected._
- **Why does `ADR 0011: controller-free triage` connect `0015 a user may keep a date of birth and` to `0002 yaml for nested files csv for the e`, `0011 controller free triage`, `0001 llm triage architecture`, `uni server vllm`, `0004 severe pelvic pain is urgent not em`, `0002 conversational triage prior art and`, `0007 what the first real consultations s`, `observed triage behaviour`, `FLOW EXPLAINED`, `Code Guide & Repo Map`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `Two-Question Evidence Row Authoring (listed? absence doubts?)` and `argues_against Only When Source Is Explicit`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `HerHealth Monorepo Conventions Skill` and `Frontend Is Not a PWA`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._