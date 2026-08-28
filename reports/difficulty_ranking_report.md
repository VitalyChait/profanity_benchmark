# Internal Evaluation Difficulty & Misclassification Ranking

**Report Generated:** `2026-08-27 20:49:00 UTC`  
**Evaluated Turns Analyzed:** `1000`  
**High-Error Turns Identified:** `973`  
**Distinct Linguistic Patterns:** `16`  

> [!TIP]
> **Active Priority Sampling:** Turns with the highest difficulty weights and vocabulary vulnerability
> are prioritized at the top of the evaluation queue during subsequent LLM evaluation passes.

---

## 1. Top Misclassified Sentences / Turns (Distinct Linguistic Patterns)

| Rank | Priority | Occurrences | Error Rate | Primary Failure | Gold Label | Turn Text |
| :---: | :---: | :---: | :---: | :--- | :---: | :--- |
| **1** | `0.96` | `15x` | `84%` (1441/1710) | False Positive (Over-moderation) | Benign (Safe) | "bro why did you push solo without comms" |
| **2** | `0.30` | `176x` | `13%` (2646/20064) | False Positive (Over-moderation) | Benign (Safe) | "bro you are fucking cracked at this game lmao" |
| **3** | `0.27` | `1x` | `13%` (15/114) | False Positive (Over-moderation) | Benign (Safe) | "bro you're fucking crazy lmao that trickshot was unreal" |
| **4** | `0.25` | `185x` | `13%` (2775/21090) | False Positive (Over-moderation) | Benign (Safe) | "deadass thought we were dead haha" |
| **5** | `0.23` | `200x` | `13%` (3000/22800) | False Positive (Over-moderation) | Benign (Safe) | "holy shit that play was crazy" |
| **6** | `0.17` | `91x` | `2%` (217/10374) | False Negative (Missed Harm) | Actionable (Harm) | "you are fucking garbage uninstall right now" |
| **7** | `0.16` | `10x` | `5%` (52/1140) | False Positive (Over-moderation) | Benign (Safe) | "you're throwing the game on purpose stop feeding" |
| **8** | `0.15` | `12x` | `4%` (52/1368) | False Positive (Over-moderation) | Benign (Safe) | "yeah all good, let's win this next one" |
| **9** | `0.15` | `11x` | `3%` (43/1254) | False Positive (Over-moderation) | Benign (Safe) | "my bad i missed the callout, let's reset and focus" |
| **10** | `0.14` | `77x` | `4%` (350/8778) | False Positive (Over-moderation) | Benign (Safe) | "nice clutch my dude" |
| **11** | `0.14` | `151x` | `3%` (548/17214) | False Positive (Over-moderation) | Benign (Safe) | "yeah my bad, let's keep playing" |
| **12** | `0.11` | `35x` | `3%` (105/3990) | False Positive (Over-moderation) | Benign (Safe) | "heading there now, don't get picked" |
| **13** | `0.11` | `22x` | `3%` (66/2508) | False Positive (Over-moderation) | Benign (Safe) | "lmao nice snipe bro" |
| **14** | `0.09` | `1x` | `2%` (2/114) | False Negative (Missed Harm) | Actionable (Harm) | "bro you're fucking useless trash uninstall the game" |
| **15** | `0.07` | `1x` | `0%` (0/114) | Correct | Actionable (Harm) | "you are a piece of shit and nobody likes you" |
| **16** | `0.06` | `12x` | `0%` (0/1368) | Correct | Actionable (Harm) | "i know what high school you go to, keep talking and see what happens" |

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
