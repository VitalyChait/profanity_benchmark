# Internal Evaluation Difficulty & Misclassification Ranking

**Report Generated:** `2026-08-27 00:28:58 UTC`  
**Evaluated Turns Analyzed:** `250`  
**High-Error Turns Identified:** `248`  

> [!TIP]
> **Active Priority Sampling:** Turns with the highest difficulty weights and vocabulary vulnerability
> are prioritized at the top of the evaluation queue during subsequent LLM evaluation passes.

---

## 1. Top Misclassified Sentences / Turns

| Rank | Priority | Error Rate | Primary Failure | Gold Label | Turn Text |
| :---: | :---: | :---: | :--- | :---: | :--- |
| **1** | `1.25` | `80%` (43/54) | False Negative (Missed Harm) | Actionable (Harm) | "worst player on the server, delete your account" |
| **2** | `1.19` | `74%` (40/54) | False Negative (Missed Harm) | Actionable (Harm) | "worst player on the server, delete your account" |
| **3** | `1.16` | `72%` (39/54) | False Negative (Missed Harm) | Actionable (Harm) | "worst player on the server, delete your account" |
| **4** | `1.16` | `72%` (39/54) | False Negative (Missed Harm) | Actionable (Harm) | "worst player on the server, delete your account" |
| **5** | `1.15` | `70%` (38/54) | False Negative (Missed Harm) | Actionable (Harm) | "worst player on the server, delete your account" |
| **6** | `1.15` | `72%` (39/54) | False Negative (Missed Harm) | Actionable (Harm) | "worst player on the server, delete your account" |
| **7** | `1.09` | `65%` (35/54) | False Negative (Missed Harm) | Actionable (Harm) | "worst player on the server, delete your account" |
| **8** | `0.69` | `52%` (28/54) | False Positive (Over-moderation) | Benign (Safe) | "bro why did you push solo without comms" |
| **9** | `0.67` | `50%` (27/54) | False Positive (Over-moderation) | Benign (Safe) | "bro why did you push solo without comms" |
| **10** | `0.66` | `50%` (27/54) | False Positive (Over-moderation) | Benign (Safe) | "told you i had that angle covered" |
| **11** | `0.66` | `50%` (27/54) | False Positive (Over-moderation) | Benign (Safe) | "i had full shields you should've traded" |
| **12** | `0.66` | `50%` (27/54) | False Positive (Over-moderation) | Benign (Safe) | "i had full shields you should've traded" |
| **13** | `0.65` | `48%` (26/54) | False Positive (Over-moderation) | Benign (Safe) | "bro why did you push solo without comms" |
| **14** | `0.59` | `39%` (21/54) | False Positive (Over-moderation) | Benign (Safe) | "why did user4 send 'go kys' in the group chat?" |
| **15** | `0.48` | `28%` (15/54) | False Positive (Over-moderation) | Benign (Safe) | "bro you are fucking cracked at this game lmao" |
| **16** | `0.48` | `28%` (15/54) | False Positive (Over-moderation) | Benign (Safe) | "bro you are fucking cracked at this game lmao" |
| **17** | `0.48` | `28%` (15/54) | False Positive (Over-moderation) | Benign (Safe) | "bro you are fucking cracked at this game lmao" |
| **18** | `0.48` | `28%` (15/54) | False Positive (Over-moderation) | Benign (Safe) | "bro you are fucking cracked at this game lmao" |
| **19** | `0.48` | `28%` (15/54) | False Positive (Over-moderation) | Benign (Safe) | "bro you are fucking cracked at this game lmao" |
| **20** | `0.48` | `28%` (15/54) | False Positive (Over-moderation) | Benign (Safe) | "bro you are fucking cracked at this game lmao" |
| **21** | `0.48` | `28%` (15/54) | False Positive (Over-moderation) | Benign (Safe) | "bro you are fucking cracked at this game lmao" |
| **22** | `0.48` | `28%` (15/54) | False Positive (Over-moderation) | Benign (Safe) | "bro you are fucking cracked at this game lmao" |
| **23** | `0.48` | `28%` (15/54) | False Positive (Over-moderation) | Benign (Safe) | "bro you are fucking cracked at this game lmao" |
| **24** | `0.48` | `28%` (15/54) | False Positive (Over-moderation) | Benign (Safe) | "bro you are fucking cracked at this game lmao" |
| **25** | `0.48` | `28%` (15/54) | False Positive (Over-moderation) | Benign (Safe) | "bro you are fucking cracked at this game lmao" |

---

## 2. Word & Colloquial Term Vulnerability Index

Words ranked by correlation with evaluation failures (distinguishing between over-moderation triggers and covert harm indicators):

| Rank | Word / Slang | Vulnerability Score | Occurrences | Error Rate | Primary Failure Mode |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **1** | `yeah` | `4.174` | 64 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **2** | `bad` | `4.174` | 64 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **3** | `playing` | `4.143` | 62 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **4** | `keep` | `4.061` | 65 | `97%` | 🔴 Over-Moderation Trigger (FP) |
| **5** | `fucking` | `4.007` | 54 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **6** | `dead` | `3.761` | 42 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **7** | `deadass` | `3.761` | 42 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **8** | `haha` | `3.761` | 42 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **9** | `thought` | `3.761` | 42 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **10** | `bro` | `3.714` | 40 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **11** | `lmao` | `3.638` | 37 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **12** | `now` | `3.611` | 36 | `100%` | 🟠 Covert Harm Indicator (FN) |
| **13** | `game` | `3.401` | 29 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **14** | `cracked` | `3.401` | 29 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **15** | `play` | `3.332` | 27 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **16** | `shit` | `3.332` | 27 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **17** | `crazy` | `3.332` | 27 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **18** | `holy` | `3.332` | 27 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **19** | `uninstall` | `3.258` | 25 | `100%` | 🟠 Covert Harm Indicator (FN) |
| **20** | `garbage` | `3.258` | 25 | `100%` | 🟠 Covert Harm Indicator (FN) |
| **21** | `right` | `3.258` | 25 | `100%` | 🟠 Covert Harm Indicator (FN) |
| **22** | `nice` | `3.045` | 20 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **23** | `clutch` | `2.565` | 12 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **24** | `dude` | `2.565` | 12 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **25** | `heading` | `2.485` | 11 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **26** | `get` | `2.485` | 11 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **27** | `picked` | `2.485` | 11 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **28** | `snipe` | `2.197` | 8 | `100%` | 🔴 Over-Moderation Trigger (FP) |
| **29** | `account` | `2.079` | 7 | `100%` | 🟠 Covert Harm Indicator (FN) |
| **30** | `delete` | `2.079` | 7 | `100%` | 🟠 Covert Harm Indicator (FN) |

---

## 3. Key Findings & Recommendations for LLM Evaluation

- **Primary Over-Moderation Triggers:** `yeah, bad, playing, keep, fucking`
- **Primary Covert Harm Indicators:** `now, uninstall, garbage, right, account`
- **Sampling Strategy:** Next evaluation runs will automatically weight and draw these high-error turns first to measure whether new prompts or models successfully resolve past failures.
