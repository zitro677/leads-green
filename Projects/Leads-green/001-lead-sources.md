# ADR-001 — Lead Sources Strategy

**Date**: 2025-04  
**Status**: Accepted  
**Deciders**: Arkana Tech (Luis Ortiz), Green Landscape Irrigation

---

## Context

Green Landscape Irrigation currently pays $1,000/month for Angie's List leads. These leads are shared with multiple competitors. The question is: **where does Angie's List get their leads, and can we replicate or do better?**

## How Angie's List Gets Leads

Angie's List (now Angi) collects leads through:
1. Google/Facebook Ads targeting homeowner intent keywords
2. SEO content ranking for "find a contractor near me"
3. Database of homeowners who self-registered
4. Partnerships with home improvement media
5. Zillow/HomeAdvisor network cross-selling

**Our advantage**: We target leads with **higher specificity** (irrigation only) and **better timing signals** (just bought a house, just filed a permit).

---

## Decision — Lead Sources by Priority

### 🥇 Tier 1: Structural Intent (Highest Value)

#### Source A: Hillsborough County Building Permits
- **URL**: https://www.hillsboroughcounty.org/permits (public data)
- **Signal**: New construction or renovation permits that do NOT include irrigation
- **Why it works**: A new construction = guaranteed future irrigation need
- **Implementation**: Poll county open data API weekly
- **Volume**: ~100–300 permits/week in Tampa area
- **Lead quality**: ⭐⭐⭐⭐⭐

#### Source B: Zillow / Realtor.com New Listings
- **Signal**: Homes listed in past 30 days in service area ZIPs
- **Why it works**: New homeowners often inherit broken/missing irrigation systems
- **Implementation**: Zillow RSS + SerpAPI + Playwright scraper
- **Volume**: ~200–500 new listings/week
- **Lead quality**: ⭐⭐⭐⭐

---

### 🥈 Tier 2: Active Intent (High Value)

#### Source C: Google Local Search Intent (SerpAPI)
- **Queries to monitor**: "irrigation repair Tampa", "sprinkler installation Tampa FL", "lawn irrigation system near me"
- **Signal**: Businesses/people appearing in search but not ranking = competitor intel
- **Also**: Google Maps reviews scraper for competitor 1–2 star reviews
- **Implementation**: SerpAPI + custom parser
- **Lead quality**: ⭐⭐⭐⭐⭐

#### Source D: Facebook Groups
- **Groups to monitor**: Tampa Bay Homeowners, Specific neighborhood groups (South Tampa, New Tampa, Brandon), HOA groups
- **Keywords**: "sprinkler", "irrigation", "lawn", "landscaping", "who do you recommend"
- **Implementation**: Apify FB Group scraper
- **Lead quality**: ⭐⭐⭐⭐

---

### 🥉 Tier 3: Community Intent (Medium Value)

#### Source E: Reddit
- **Subreddits**: r/tampa, r/TampaBayArea, r/homeimprovement, r/lawncare
- **Keywords**: irrigation, sprinkler, landscape, Tampa lawn
- **Implementation**: Reddit API (PRAW)
- **Lead quality**: ⭐⭐⭐

#### Source F: Nextdoor
- **Signal**: Posts asking for contractor recommendations
- **Implementation**: Apify Nextdoor scraper (limited access)
- **Lead quality**: ⭐⭐⭐⭐

#### Source G: Instagram / TikTok
- **Hashtags**: #tampahomes #tampairrigation #tampalawn #tamparealestate
- **Signal**: New home reveal posts = new homeowner
- **Implementation**: Apify Instagram scraper
- **Lead quality**: ⭐⭐ (mostly cold)

---

## Consequences

- **Positive**: Exclusive leads at ~15% the cost of Angie's List
- **Positive**: Leads are tiered by quality — voicebot only calls Tier 1–2
- **Risk**: Scraping terms of service on some platforms (Facebook, Nextdoor)
  - Mitigation: Use Apify (compliant actors), respect rate limits, do not store PII unnecessarily
- **Risk**: Low volume initially
  - Mitigation: Start with permits + Zillow (public data) which have no scraping risk

## Rejected Alternatives

- **Thumbtack/HomeAdvisor**: Same problem as Angie's List — shared leads
- **Cold email campaigns**: CAN-SPAM compliance complexity, low open rates
- **Buy lead lists**: Expensive, low quality, same shared problem
