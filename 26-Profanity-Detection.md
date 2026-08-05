# **Profanity Detection** 

**@Vitaly:** Our goal should be submitting the paper at ACL or EMNLP. They are flagship venue for this kind of work and also in general for language models.

I’m assuming that you already have the 600K corpus ready to go in.

Below I have 3 directions for you to look at. Of course I’ve a preference and that’d be 2nd idea. But that one is not certain whether we will have success, but it could be  a godd learning experience. The other two ideas definitely is doable and we know the outcome, and they give you fame. So, ball is in your court to decide. If you’re ambitious, you can do multiple projects.

## 

## **Idea 1: Benchmarking**

Creating a benchmark dataset to test robustness of LLMs in a multi-turn dialog set up for youth safeguarding. Toxicity/profanity doesn’t exist in isolation, they slowly get escalated in a conversation. How quickly an LLM can detect. Creating a big test dataset for that.

#### Why? Standard toxicity benchmarks assess safety using adult-centric policies like hate speech, weapons, and explicit violence. They suffer from two major flaws when applied to youths/minors:

> 1. Youth speak in algospeak, and they are evolving all the time. Youth continuously alter toxic vocabulary to bypass automated filters (e.g., "unalive", "newspaper eat" for toxic insults, or localized emojis).   
> 2. Cyberbullying in adolescent peer spaces builds over multi-turn interactions rather than a single explicit slur. 

> 

#### Dataset Construction: Instead of treating your 600K record corpus as a static training set, turn it into a dynamic, multi-turn evaluation framework to stress-test frontier models. 

#### How to transform the current set into multi-turn dataset? We could follow the following strategies.

> * Synthetic: Slices of *GameTox*, *Cyberbullying*, and *MinorBench* serve as "seed behaviors". An LLM agent recursively expands these seeds into multi-turn chat logs mimicking platform environments (e.g., Discord or Roblox). We will use ChatGPT or other frontier model for this.  
> * We extract parent section-trees and historical reply contexts for existing corpus rows originating from real-world sites (such as the Wikipedia talk-page trees in *Jigsaw* or historical parent IDs in *Davidson*). This preserves organic, human-to-human escalation trajectories and adolescent cadences.  
> * We use your curated list of words for profanity, and perform a semantic join to massive, peer-reviewed human conversation sets (e.g., *Persona-Chat/ConvAI2* or *WildChat/LMSYS-Chat*). We basically filter out the conversations where we see the emergence of these bad unigrams, and then we isolate multi turn turn conversational windows around them.

#### Once the benchmark is defined, then we do the evaluation using multiple open LLMs

- Adversarial evasion injection where we apply rule based algospeak to both safe and unsafe text. Then test some metric to see if LLMs are robust to it or not?  
- EValuate the multi turn toxicity at each text exchange, and with full context of previous messages.   
- 

Hopefully, if we do it well across a number of LLMs and if the results are super promising, I could fund an experiment with ChatGPT api as well to include in the results.

## ---

**Idea 2: The Main Research Track (Methodological)**

A training free method for LLMs to inspect and manipulate how subculture-specific language shifts are decoded inside foundational models. Basically, can we avoid fine tuning? Costly, forgetting, resource constraints etc. We turn to Representation Engineering ([https://arxiv.org/abs/2310.01405](https://arxiv.org/abs/2310.01405)) and Activation Steering ([https://arxiv.org/abs/2308.10248](https://arxiv.org/abs/2308.10248)).

The algos are well known but our narrative is understanding hidden mechanics of subcultural language evolution and structural dataset corruption.

We create steering vectors using contrastive examples from your built corpus.  
We will do experiments on 2- 3 fronts:

> * **Localization:**Find mechanistically where LLM translates defensive adolescent variations into abstract semantic threats.  
> * If we have the multi turn dataset: Do the same evaluation as in the benchmarking, but this time with steering.  
> * Maybe an experiment around your finding about length. If profanity is in longer text it is hard to detect. We will find such cases and evaluate using steered model.  
> * Do a sweep of steering hyperparm across PR curve, and argue that modelrators can moderate using just a single scaler or something.

Will think more if we choose to go this route.

## ---

**Idea 3: A cool application**

We will need completely new data for this one.

Many platforms instantly block/cut users, and that demotivates youth. Driving them to unsafe unmoderated alternate platforms. So how about instead of policing, instead we intervene and lower emotional escalation in real time without dropping chat utility.

Suppose users say:  
*You're a hard-stuck trash kid, go unalive your accounts, delete the game.*

Then, we intervene, and translate it on the fly to 

*You're hard-stuck in this rank, go practice your setups before playing again.*

Basically our contribution is Dialogue transformation engine (pick a fancy name as you want). 

#### Experiments: We will validate it across multi-turn argumentative conversations. Need to find of there are gaming chats available or similar sources. Another idea would be to create synthetic conversations as in the benchmark stuff above. Then, we use LLM-as-a-Judge protocol, and see if descalation rates improve in our transformed chats.