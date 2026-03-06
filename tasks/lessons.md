# Lessons Learned — corp-project-extractor

*Updated by Claude Code after corrections. Review at session start.*

## Classifier
- Classifier priority order matters significantly. File-level rules (Junk, Security, RFP_QA, Data)
  must come BEFORE path-based rules, because Q&A files in Original/ should be RFP_QA not
  RFP_Original, and DPA files in any folder are Security.
- Exception: WIP path check comes BEFORE RFP_Response file-level check, so "Blue Yonder Responses"
  files in WIP/ stay as RFP_WIP.
- "Stat Fcst Exercise" matches Data via `(?:forecast|fcst).?exercise` pattern (abbreviation).
- "Commercials" as a filename substring is ambiguous — client's RFP sections are also called
  "Commercials". Only catch Commercial via path (Implementation Services/) or explicit patterns
  (PSEstimator, Effort_Estimation, Deal Alignment, T&M).
