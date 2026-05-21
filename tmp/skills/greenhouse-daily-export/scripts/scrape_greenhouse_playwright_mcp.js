async (page) => {
  const queries = ["Software Engineer", "AI Engineer", "Engineering Manager"];
  const locations = [
    {
      label: "Berlin Remote",
      country: "Germany",
      urlParams:
        "location=Berlin%2C%20Germany&lat=52.524932&lon=13.407032&location_type=locality&country_short_name=DE&state_short_name=BE",
    },
    {
      label: "Spain Remote",
      country: "Spain",
      urlParams: "location=Spain&location_type=country&country_short_name=ES",
    },
  ];
  const today = new Date().toLocaleDateString("en-CA", {
    timeZone: "Europe/Madrid",
  });
  const baseUrl = "https://my.greenhouse.io/jobs";

  function buildUrl(query, location) {
    return `${baseUrl}?query=${encodeURIComponent(query)}&${location.urlParams}&work_type[]=remote`;
  }

  function normalizeUrl(url) {
    return String(url || "").split("#")[0];
  }

  async function collectSearch(search) {
    await page.goto(search.url, {
      waitUntil: "domcontentloaded",
      timeout: 45000,
    });

    if (/\/users\/sign_in/.test(page.url())) {
      throw new Error(
        `Greenhouse is not authenticated for ${search.label}; ask the user to sign in in the Playwright browser and retry. Current URL: ${page.url()}`,
      );
    }

    await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
    for (let i = 0; i < 6; i += 1) {
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await page.waitForTimeout(600);
    }

    return await page.evaluate((search) => {
      function textLines(node) {
        return (node.innerText || "")
          .split("\n")
          .map((value) => value.trim())
          .filter(Boolean);
      }

      function resultContainer(anchor) {
        let node = anchor.parentElement;
        let best = anchor.parentElement;
        while (node && node !== document.body) {
          const text = (node.innerText || "").trim();
          if (text.includes("Posted ") && text.includes("View job") && text.length < 900) {
            return node;
          }
          if (text.length > 20 && text.length < 900) best = node;
          node = node.parentElement;
        }
        return best;
      }

      const anchors = Array.from(document.querySelectorAll("a[href]")).filter((anchor) => {
        const href = anchor.getAttribute("href") || "";
        if (/sign_out|users\/|privacy|terms|mailto:/i.test(href)) return false;
        const url = new URL(href, window.location.href);
        if (url.hostname === "my.greenhouse.io") return false;
        return (
          /greenhouse\.io$/i.test(url.hostname) ||
          url.searchParams.has("gh_jid") ||
          url.searchParams.get("gh_src") === "my.greenhouse.search"
        );
      });

      const seen = new Set();
      return anchors
        .map((anchor) => {
          const url = new URL(anchor.getAttribute("href"), window.location.href).href;
          if (seen.has(url)) return null;
          seen.add(url);

          const container = resultContainer(anchor);
          let lines = textLines(container).filter((line) => line !== "View job");
          if (lines[0] && /^[A-Z]$/.test(lines[0])) lines = lines.slice(1);
          const anchorText = (anchor.innerText || "").trim();
          const title =
            anchorText && anchorText !== "View job" && anchorText.length <= 140
              ? anchorText
              : lines.find((line) => /engineer|manager|developer|lead|architect/i.test(line)) ||
                lines[0] ||
                anchorText.slice(0, 140);

          const company =
            lines.find(
              (line) =>
                line !== title &&
                !/remote|full-time|part-time|posted|viewed|berlin|germany|spain|españa/i.test(
                  line,
                ),
            ) || "";
          const location =
            lines
              .filter((line) => /remote|berlin|germany|spain|españa/i.test(line))
              .join(", ") ||
            search.locationLabel;

          return {
            provider: "greenhouse",
            company,
            title,
            url,
            description: "",
            applyUrl: url,
            location,
            country: search.country,
            postingDate: "",
            searchLabel: search.label,
            searchQuery: search.query,
          };
        })
        .filter(Boolean);
    }, search);
  }

  const searches = [];
  for (const query of queries) {
    for (const location of locations) {
      searches.push({
        label: `${query} - ${location.label}`,
        query,
        country: location.country,
        locationLabel: location.label,
        url: buildUrl(query, location),
      });
    }
  }

  const rowsByUrl = new Map();
  for (const search of searches) {
    for (const row of await collectSearch(search)) {
      rowsByUrl.set(normalizeUrl(row.url), { ...row, url: normalizeUrl(row.url) });
    }
  }

  const rows = Array.from(rowsByUrl.values());
  for (const row of rows) {
    try {
      await page.goto(row.url, {
        waitUntil: "domcontentloaded",
        timeout: 10000,
      });
      await page.waitForTimeout(250);
      const details = await page.evaluate(() => {
        const lines = (document.body.innerText || "")
          .split("\n")
          .map((value) => value.trim())
          .filter(Boolean);
        const titleMatch = document.title.match(/^Job Application for (.+?) at (.+)$/i);
        const title =
          (titleMatch && titleMatch[1]) ||
          lines.find((line) => /engineer|manager|developer|lead|architect/i.test(line)) ||
          "";
        const company = (titleMatch && titleMatch[2]) || "";
        const location =
          lines.find((line) => /remote|berlin|germany|spain|españa/i.test(line)) || "";
        const description = lines
          .filter(
            (line) =>
              line.length > 70 &&
              !/^https?:/.test(line) &&
              !/cookie|privacy|terms|sign in/i.test(line),
          )
          .slice(0, 8)
          .join(" ")
          .slice(0, 1800);
        return { title, company, location, description };
      });

      row.title = details.title || row.title;
      row.company = details.company || row.company;
      row.location = details.location || row.location;
      row.description = details.description || row.description;
    } catch (error) {
      row.scrapeError = String((error && error.message) || error).slice(0, 300);
    }
  }

  const finalRows = rows.filter((row) => {
    if (!row.url || !row.title || !row.company) return false;
    if (/^(Posted\b|Viewed\b|View job$|Applications$|Jobs$|Developers$)/i.test(row.title)) {
      return false;
    }
    return true;
  });

  const json = `${JSON.stringify(finalRows, null, 2)}\n`;
  const outputPath = `/Users/zall/interviews/outputs/greenhouse/runs/greenhouse_jobs_live_${today}.json`;
  const downloadPromise = page.waitForEvent("download");
  await page.evaluate(
    ({ json, today }) => {
      const blob = new Blob([json], { type: "application/json" });
      const anchor = document.createElement("a");
      anchor.href = URL.createObjectURL(blob);
      anchor.download = `greenhouse_jobs_live_${today}.json`;
      document.body.appendChild(anchor);
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(anchor.href), 1000);
    },
    { json, today },
  );
  const download = await downloadPromise;
  await download.saveAs(outputPath);

  return {
    out: outputPath,
    searches: searches.map((search) => search.label),
    count: finalRows.length,
    droppedLowQualityRows: rows.length - finalRows.length,
    countries: [...new Set(finalRows.map((row) => row.country))],
    missingDescriptions: finalRows.filter((row) => !row.description).length,
    missingTitles: finalRows.filter((row) => !row.title).length,
    sample: finalRows.slice(0, 5),
  };
}
