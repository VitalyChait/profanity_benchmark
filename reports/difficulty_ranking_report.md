# Internal Evaluation Difficulty & Misclassification Ranking

**Report Generated:** `2026-08-27 20:49:00 UTC`  
**Evaluated Turns Analyzed:** `1000`  
**High-Error Turns Identified:** `973`  

> [!TIP]
> **Active Priority Sampling:** Turns with the highest difficulty weights and vocabulary vulnerability
> are prioritized at the top of the evaluation queue during subsequent LLM evaluation passes.

---

## 1. Top Misclassified Sentences / Turns

| Rank | Priority | Error Rate | Primary Failure | Gold Label | Turn Text |
| :---: | :---: | :---: | :--- | :---: | :--- |
| **1** | `0.96` | `86%` (98/114) | False Positive (Over-moderation) | Benign (Safe) | "bro why did you push solo without comms" |
| **2** | `0.96` | `87%` (99/114) | False Positive (Over-moderation) | Benign (Safe) | "bro why did you push solo without comms" |
| **3** | `0.96` | `84%` (96/114) | False Positive (Over-moderation) | Benign (Safe) | "bro why did you push solo without comms" |
| **4** | `0.96` | `85%` (97/114) | False Positive (Over-moderation) | Benign (Safe) | "bro why did you push solo without comms" |
| **5** | `0.95` | `83%` (95/114) | False Positive (Over-moderation) | Benign (Safe) | "bro why did you push solo without comms" |
| **6** | `0.95` | `85%` (97/114) | False Positive (Over-moderation) | Benign (Safe) | "bro why did you push solo without comms" |
| **7** | `0.94` | `84%` (96/114) | False Positive (Over-moderation) | Benign (Safe) | "bro why did you push solo without comms" |
| **8** | `0.94` | `84%` (96/114) | False Positive (Over-moderation) | Benign (Safe) | "bro why did you push solo without comms" |
| **9** | `0.94` | `84%` (96/114) | False Positive (Over-moderation) | Benign (Safe) | "bro why did you push solo without comms" |
| **10** | `0.94` | `84%` (96/114) | False Positive (Over-moderation) | Benign (Safe) | "bro why did you push solo without comms" |
| **11** | `0.94` | `84%` (96/114) | False Positive (Over-moderation) | Benign (Safe) | "bro why did you push solo without comms" |
| **12** | `0.94` | `83%` (95/114) | False Positive (Over-moderation) | Benign (Safe) | "bro why did you push solo without comms" |
| **13** | `0.94` | `83%` (95/114) | False Positive (Over-moderation) | Benign (Safe) | "bro why did you push solo without comms" |
| **14** | `0.94` | `83%` (95/114) | False Positive (Over-moderation) | Benign (Safe) | "bro why did you push solo without comms" |
| **15** | `0.93` | `82%` (94/114) | False Positive (Over-moderation) | Benign (Safe) | "bro why did you push solo without comms" |
| **16** | `0.30` | `16%` (18/114) | False Positive (Over-moderation) | Benign (Safe) | "bro you are fucking cracked at this game lmao" |
| **17** | `0.28` | `14%` (16/114) | False Positive (Over-moderation) | Benign (Safe) | "bro you are fucking cracked at this game lmao" |
| **18** | `0.28` | `14%` (16/114) | False Positive (Over-moderation) | Benign (Safe) | "bro you are fucking cracked at this game lmao" |
| **19** | `0.28` | `14%` (16/114) | False Positive (Over-moderation) | Benign (Safe) | "bro you are fucking cracked at this game lmao" |
| **20** | `0.27` | `13%` (15/114) | False Positive (Over-moderation) | Benign (Safe) | "bro you are fucking cracked at this game lmao" |
| **21** | `0.27` | `13%` (15/114) | False Positive (Over-moderation) | Benign (Safe) | "bro you are fucking cracked at this game lmao" |
| **22** | `0.27` | `13%` (15/114) | False Positive (Over-moderation) | Benign (Safe) | "bro you are fucking cracked at this game lmao" |
| **23** | `0.27` | `13%` (15/114) | False Positive (Over-moderation) | Benign (Safe) | "bro you are fucking cracked at this game lmao" |
| **24** | `0.27` | `13%` (15/114) | False Positive (Over-moderation) | Benign (Safe) | "bro you are fucking cracked at this game lmao" |
| **25** | `0.27` | `13%` (15/114) | False Positive (Over-moderation) | Benign (Safe) | "bro you are fucking cracked at this game lmao" |

---

## 2. Word & Colloquial Term Vulnerability Index

Words ranked by correlation with evaluation failures (distinguishing between over-moderation triggers and covert harm indicators):

| Rank | Word / Slang | Vulnerability Score | Occurrences | Error Rate | Primary Failure Mode |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **1** | `bro` | `5.375` | 215 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **2** | `crazy` | `5.308` | 201 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **3** | `fucking` | `5.307` | 269 | `95%` | 🔴 Over-Moderation Trigger (FP) |
| **4** | `holy` | `5.303` | 200 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **5** | `play` | `5.303` | 200 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **6** | `lmao` | `5.298` | 199 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **7** | `shit` | `5.282` | 201 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **8** | `game` | `5.236` | 187 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **9** | `thought` | `5.226` | 185 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **10** | `dead` | `5.226` | 185 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **11** | `haha` | `5.226` | 185 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **12** | `deadass` | `5.226` | 185 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **13** | `cracked` | `5.176` | 176 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **14** | `yeah` | `5.100` | 163 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **15** | `bad` | `5.094` | 162 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **16** | `playing` | `5.024` | 151 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **17** | `keep` | `4.724` | 163 | `93%` | 🔴 Over-Moderation Trigger (FP) |
| **18** | `nice` | `4.605` | 99 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **19** | `clutch` | `4.357` | 77 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **20** | `dude` | `4.357` | 77 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **21** | `now` | `4.306` | 126 | `89%` | 🟠 Covert Harm Indicator (FN) |
| **22** | `uninstall` | `3.843` | 92 | `85%` | 🟠 Covert Harm Indicator (FN) |
| **23** | `right` | `3.826` | 91 | `85%` | 🟠 Covert Harm Indicator (FN) |
| **24** | `garbage` | `3.826` | 91 | `85%` | 🟠 Covert Harm Indicator (FN) |
| **25** | `get` | `3.583` | 35 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **26** | `heading` | `3.583` | 35 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **27** | `picked` | `3.583` | 35 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **28** | `snipe` | `3.135` | 22 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **29** | `push` | `2.773` | 15 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **30** | `without` | `2.773` | 15 | `100%` | 🔴 Over-Moderation Trigger (FP) |

---

## 3. Key Findings & Recommendations for LLM Evaluation

- **Primary Over-Moderation Triggers:** `bro, crazy, fucking, holy, play`
- **Primary Covert Harm Indicators:** `now, uninstall, right, garbage, trash`
- **Sampling Strategy:** Next evaluation runs will automatically weight and draw these high-error turns first to measure whether new prompts or models successfully resolve past failures.
