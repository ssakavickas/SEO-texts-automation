# 🤖  AI Content Automation Pipeline

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Status: Production Ready](https://img.shields.io/badge/Status-Production--Ready-brightgreen)

Šis projektas yra pilnai automatizuota **SEO turinio generavimo ir platinimo sistema**. Ji skirta masiškai kurti aukštos kokybės blogo įrašus, socialinių tinklų įrašus ir vizualus, naudojant pažangiausius dirbtinio intelekto modelius.

## 🚀 Pagrindinės funkcijos

*   **AI Writing Agent**: Automatinis blogo įrašų rašymas naudojant `Claude 3.5 Sonnet` ir `Gemini` modelius.
*   **Visual Generation**: Automatinis viršelių ir iliustracijų kūrimas per `Google Imagen` ir `DALL-E`.
*   **Deep Research**: Integracija su `Tavily`, `Exa` ir `Firecrawl` giliam duomenų surinkimui prieš rašant.
*   **Social Media Automation**: Automatinis LinkedIn ir Twitter įrašų generavimas pagal sukurtą turinį.
*   **Distribution Pipeline**: Rezultatų siuntimas į Telegram kanalus ir saugojimas Google Sheets.
*   **Scraping Tools**: Specializuoti įrankiai stebėti konkurentus ir rinkti duomenis iš Twitter bei kitų šaltinių.

## 🏗️ Architektūra

Projektas sukurtas naudojant **3 sluoksnių (3-Layer) architektūrą**, užtikrinančią maksimalų patikimumą:

1.  **Directive (SOPs)**: Markdown failai `directives/` kataloge, apibrėžiantys „kaip“ agentas turi elgtis.
2.  **Orchestration**: Logika, kuri sprendžia, kuriuos įrankius ir kada naudoti.
3.  **Execution**: Deterministiniai Python skriptai `execution/` kataloge, atliekantys realius veiksmus (API skambučiai, duomenų apdorojimas).

## 🛠️ Technologijų krepšelis

*   **Kalba**: Python 3.x
*   **AI Modeliai**: Anthropic Claude, Google Gemini, OpenAI
*   **Duomenų rinkimas**: Firecrawl, Tavily, ScrapeBadger
*   **Integracijos**: Telegram API, Google Sheets API
*   **Struktūra**: Modular SOP system

## 📂 Projekto struktūra

```bash
├── directives/      # Agentų instrukcijos ir taisyklės
├── execution/       # Vykdomieji Python skriptai
├── .env             # Aplinkos kintamieji (ignoruojama GitHub'e)
└── README.md        # Projekto dokumentacija
```

---
*Sukurtas automatizuotam SEO efektyvumui didinti.*
