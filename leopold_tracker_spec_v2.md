# Spec: Leopold Aschenbrenner Investment Tracker Mobile App

This document outlines the system architecture, data ingestion strategy, and tech stack for an automated mobile tracking and notification app focused on Leopold Aschenbrenner's fund, **Situational Awareness LP**.

--- 

## 1. Product Overview
* **Goal:** Provide near-instantaneous push notifications and portfolio visualization whenever Leopold Aschenbrenner (Situational Awareness LP) enters, exits, or alters a substantial investment position (e.g., his recent large stake in T1 Energy `TE`, positions in `BE`, `CRWV`, or major semiconductor short hedges via Puts).
* **Target Audience:** Algorithmic traders, AI infrastructure retail investors, and momentum followers looking for a thematic "AI Bottleneck" (Power & Compute) copy-trading tool.
* **Target Entity to Monitor:**
    * **Entity Name:** Situational Awareness LP / Aschenbrenner Leopold
    * **Primary CIK:** (To be dynamically fetched via SEC API / Edgar lookup)

--- 

## 2. Core Feature Specifications

### A. Multi-Tier Ingestion Engine (The Alpha Layer)
13F filings have a 45-day lag. To achieve "instant" notification, the ingestion pipeline relies on a three-tier detection network:

1. **Regulatory Filing Monitor (SEC EDGAR Real-time Webhook)**
    * **13F (Quarterly Holdings):** Processed immediately upon release.
    * **13D / 13G (Beneficial Ownership >5%):** Must be filed within 10 days of the transaction. This is the primary vector for capturing early mid-cap entries like `TE`.
    * **Form 4 (Insider Transactions):** If he sits on the board or becomes a 10% owner of any infrastructure or power company.
2. **Options Flow & Whales Alerts (Alternative Data)**
    * Monitors unusual options activity (Unusually Options Flow) and Block Trades on thematic AI infra tickers (`TE`, `BE`, `CORZ`, `NVDA`, `AMD`).
    * Filters for multi-million dollar premium institutional block sweeps matching his known macro thesis (e.g., massive out-of-the-money Put blocks on chips or Call sweeps on utility energy).
3. **Social & Media Signal AI Agent**
    * Scrapes/streams updates from X (Twitter), specialized investment subreddits (r/investing, r/LocalLLaMA tech ecosystem discussions), and tech newsletters.
    * Triggers NLP analysis when key phrases occur: `Aschenbrenner` + `bought` / `unveiled` / `stake` + `[TICKER]`.

### B. Instant Push Notification System
* **Trigger Conditions:**
    * *Critical:* Regulatory filing (SEC) detected showing new/modified position.
    * *High Alert:* Massive social cluster or leaked investment memo confirming an allocation change.
* **Payload Example:**
```json
{
  "title": "? LEOPOLD ASCHENBRENNER NEW POSITION DETECTED",
  "body": "Situational Awareness LP disclosed a massive position in T1 Energy ($TE): 10,000,000 shares valued at ~$43.9M. Tap to view updated portfolio allocation.",
  "data": {
    "ticker": "TE",
    "action": "BUY",
    "source": "13D-SEC"
  }
}
