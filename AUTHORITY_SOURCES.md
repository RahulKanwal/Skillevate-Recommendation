# Authority Sources Registry

This document tracks all trusted/authoritative sources used in the recommendation ranking system.
Update this file whenever you add or remove sources from `core/authority.py`.

---

## YouTube — Authoritative Channels

### Generic Trusted (apply to ALL skills, authority_tier = "trusted_platform")

| Channel Name | Channel ID | Why Trusted |
|---|---|---|
| freeCodeCamp.org | UC8butISFwT-Wl7EV0hUK0BQ | Non-profit, peer-reviewed full courses |
| Traversy Media | UC29ju8bIPH5as8OGnQzwJyA | Industry-standard web dev tutorials |
| Google for Developers | UCnUYZLuoy1rq1aVMwx4aTzw | Official Google developer content |
| IBM Technology | UCKWaEZ-_VweaEx1j62do_vQ | Official IBM educational content |
| MIT OpenCourseWare | UCEBb1b_L6zDS3xTUrIALZOw | MIT academic lectures |
| CS Dojo | UCxX9wt5FWQUAAz4UrysqK9A | Highly rated CS fundamentals |
| Corey Schafer | UCCTVrRJOwzEHm1ynH2c74IA | Deep-dive Python/programming tutorials |

### Skill-Specific Official Channels (authority_tier = "official")

| Skill Keywords | Channel Name | Channel ID |
|---|---|---|
| python | Python Software Foundation (via handle @ThePSF) | UCWr0mx597DnSGLFk1WfvSkQ |
| javascript, web | Chrome for Developers | UCnUYZLuoy1rq1aVMwx4aTzw |
| react | Meta Open Source | N/A — use channel name match |
| docker | Docker | UCZgt6AzoyjslHTC9dz0UoTw |
| kubernetes, devops | TechWorld with Nana | UCdngmbVKX1Tgre699-XLlUA |
| machine learning, tensorflow | TensorFlow | UCWN3xxRkmTPmbKwht9FuE5A |
| machine learning, pytorch | PyTorch | UCWN3xxRkmTPmbKwht9FuE5A |
| data science | Kaggle | UCSNeZleDn9c74yQc-EKnVTA |
| aws, cloud | Amazon Web Services | UCd6MoB9NC6uYN2grvUNT-Zg |
| android | Android Developers | UCVHyOkuRLpR9An0-9IQZFHQ |
| flutter, dart | Flutter | UCwXdFgeE9KYzlDdR7TG9cMw |
| rust | Rust Programming Language (via handle) | N/A — use channel name match |
| golang, go | Google for Developers | UCnUYZLuoy1rq1aVMwx4aTzw |

---

## GitHub — Authoritative Organizations

### Generic Trusted Orgs (apply to ALL skills, authority_tier = "trusted_platform")

| Org Login | Why Trusted |
|---|---|
| google | Official Google open source |
| microsoft | Official Microsoft open source |
| ibm | Official IBM open source |
| meta | Official Meta open source |
| aws | Official Amazon Web Services |
| apache | Apache Software Foundation |
| cncf | Cloud Native Computing Foundation |

### Skill-Specific Official Orgs (authority_tier = "official")

| Skill Keywords | GitHub Org Login |
|---|---|
| python | python, psf |
| javascript, typescript | nicolo-ribaudo, tc39 |
| react | facebook, reactjs |
| vue | vuejs |
| angular | angular |
| docker | docker, moby |
| kubernetes | kubernetes |
| machine learning, tensorflow | tensorflow |
| machine learning, pytorch | pytorch |
| rust | rust-lang |
| golang, go | golang |
| swift | apple |
| android, kotlin | android, JetBrains |
| flutter, dart | flutter, dart-lang |
| aws | aws, awslabs |
| azure | Azure |
| linux | torvalds, linux |
| nodejs | nodejs |
| django | django |
| fastapi | tiangolo |
| nextjs | vercel |

---

## Scoring Tiers

| Tier | authority_score | Description |
|---|---|---|
| official | 1.0 | Official org/channel for that exact skill |
| trusted_platform | 0.8 | Universally trusted educational source |
| known_educational | 0.5 | Known platform but not official for the skill |
| unknown | 0.0 | No authority signal |

---

## Notes

- Channel IDs starting with `UC` are permanent YouTube identifiers — they don't change even if the channel renames itself.
- GitHub org logins are case-insensitive in matching but stored lowercase here.
- When a YouTube API key is active, channel ID matching is done against `snippet.channelId` in search results.
- When adding new channels, verify the channel ID by visiting `https://www.youtube.com/channel/<ID>`.
