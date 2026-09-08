# 01 REPOSITORY INVENTORY (PROVIDER DATASET AUDIT)

- Baseline Commit: `df054cb100b58d99acf42a72d18dcbcb7dcbd5f8`
- Core Dataset & Generation Architecture:
  - Dataset Admin & Documents: `DatasetAdminRepository`, `DocumentService`, `ImportService`, `DataStudioService`.
  - MB-16 Multimodal Dataset Generator: `MiniBrainMultimodalDatasetGeneratorService`, `mini_brain_multimodal_dataset_generator.py`.
  - Provider Settings & Runtimes: `ProviderSettingsService`, `MiniBrainLlmRuntimeService`, `mini_brain_provider_settings.py`.
  - Admin Assistant Chat: `AdminAssistantChatService`, `admin_assistant_tools.py`, `admin_assistant.py`.
  - Frontend Pages: `MultimodalDatasetGeneratorTab.jsx`, `DatasetDiscoveryPage.jsx`, `DatasetsPage.jsx`, `DocumentsPage.jsx`, `AdminAssistantPage.jsx`, `ChatPanel.jsx`.
