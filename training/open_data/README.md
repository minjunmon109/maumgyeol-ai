# KMI Korean motivational interviewing training subset

**Source:** Hyunjong Kim et al., *KMI: A Dataset of Korean Motivational Interviewing Dialogues for Psychotherapy*, NAACL 2025, https://aclanthology.org/2025.naacl-long.541/ and https://github.com/hjkim811/KMI

**Original copyright:** Copyright (c) Hyunjong Kim.

**License:** Creative Commons Attribution 4.0 International (CC BY 4.0), https://creativecommons.org/licenses/by/4.0/; original license: https://github.com/hjkim811/KMI/blob/main/LICENSE

**Nature:** This is an **LLM-generated, synthetic** Korean Motivational Interviewing dialogue corpus. Its authors created it using therapist expertise and assessed it with experts. The source is **not genuine patient-clinician transcripts**, and the source authors' evaluation **does not constitute independent clinical validation of 마음결**.

## Included modifications and attribution

- All 1,000 KMI conversations were programmatically converted to a Qwen2.5-style *assistant completion* dataset.
- Each training example represents one therapist reply, with up to four preceding messages as context.
- The initial therapist greeting is excluded because it has no preceding client utterance.
- Conversation IDs are kept for provenance and split deterministically at the **conversation** level; no dialogue is split across train/val/test.
- `source`, `mi_strategy`, `category` are included as descriptive labels, not input to the model.
- The output is published here as modified derivative material under CC BY 4.0, with source and changes credited.

Files:
- `kmi_train.jsonl` (5997 generated therapist response examples)
- `kmi_val.jsonl` (1267)
- `kmi_test.jsonl` (1294)

These data are intended as **research-oriented communication-style examples**, not a replacement for legitimate, consented clinical data. Bias, hallucination, unsafe response risks, and data quality must be evaluated.

**DO NOT** publish private client records or feed real user transcripts into the training pipeline without documented permission and protective processes.

**DO NOT** call the model clinically validated or a licensed therapist after training with this data.

Model weight training is a separate, expensive step; adding these examples does not train the weights automatically. The default live site should remain the original model until model-specific independent evaluation and an approved release are complete.
