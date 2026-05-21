async (page) => {
  const searches = [
    {
      label: "Spain Remote 100k+",
      country: "Spain",
      url: "https://www.jobleads.com/search/jobs?view=for-you&location_country=ES&filter_by_contractType=full_time&filter_by_remote=remote&minSalary=100000",
    },
    {
      label: "Berlin Remote 100k+",
      country: "Germany",
      url: "https://www.jobleads.com/search/jobs?view=for-you&location=Berlin%2C%20Germany&location_latitude=52.5173885&location_longitude=13.3951309&location_coordinates_radius=29495.470786527792&location_country=DE&filter_by_contractType=full_time&filter_by_remote=remote&minSalary=100000",
    },
  ];

  const today = new Date().toLocaleDateString("en-CA", {
    timeZone: "Europe/Madrid",
  });

  function postingDateFromSpanish(relative) {
    const match = String(relative || "").match(/Hace\s+(\d+)\s+d[ií]as?/i);
    if (!match) return "";
    const date = new Date(`${today}T00:00:00Z`);
    date.setUTCDate(date.getUTCDate() - Number(match[1]));
    return date.toISOString().slice(0, 10);
  }

  async function collectCards(search) {
    await page.goto(search.url, {
      waitUntil: "domcontentloaded",
      timeout: 45000,
    });

    if (/\/external-home|accounts\.google\.com|modal=login/.test(page.url())) {
      throw new Error(
        `JobLeads is not authenticated for ${search.label}; ask the user to sign in in the Playwright browser and retry. Current URL: ${page.url()}`,
      );
    }

    await page.waitForSelector('a[href*="/job/"]', { timeout: 20000 });
    for (let i = 0; i < 6; i += 1) {
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await page.waitForTimeout(700);
    }

    return await page.evaluate((search) => {
      function cardFor(anchor) {
        let node = anchor.parentElement;
        let best = anchor.parentElement;
        while (node && node !== document.body) {
          const text = (node.innerText || "").trim();
          if (
            text.includes("Jornada completa") &&
            text.includes("Hace ") &&
            text.length < 1400
          ) {
            best = node;
          }
          node = node.parentElement;
        }
        return best;
      }

      const seen = new Set();
      return Array.from(document.querySelectorAll('a[href*="/job/"]'))
        .map((anchor) => {
          const url = new URL(anchor.href, window.location.href).href;
          if (seen.has(url)) return null;
          seen.add(url);

          const card = cardFor(anchor);
          const lines = (card.innerText || "")
            .split("\n")
            .map((value) => value.trim())
            .filter(Boolean);
          const title = (anchor.innerText || lines[0] || "").trim();
          const firstTitleIndex = lines.findIndex((line) => line === title);
          let rest =
            firstTitleIndex >= 0 ? lines.slice(firstTitleIndex + 1) : lines.slice(1);
          if (rest[0] === title) rest = rest.slice(1);

          const salaryIndex = rest.findIndex((line) => /EUR|€/.test(line));
          const postedRelative =
            rest.find((line) => /^Hace\s+\d+\s+d/i.test(line)) || "";
          const remoteIndex = rest.findIndex((line) =>
            /A distancia|Remote/i.test(line),
          );
          const company = rest[0] || "";
          let location = "";
          if (remoteIndex > 0) location = rest[remoteIndex - 1];
          else if (salaryIndex > 1) location = rest[salaryIndex - 1];

          return {
            provider: "jobleads",
            company,
            title,
            url,
            description: "",
            applyUrl: "",
            location,
            country: search.country,
            postedRelative,
            searchLabel: search.label,
          };
        })
        .filter(Boolean);
    }, search);
  }

  const rowsByUrl = new Map();
  for (const search of searches) {
    for (const card of await collectCards(search)) rowsByUrl.set(card.url, card);
  }

  const rows = Array.from(rowsByUrl.values());
  for (const row of rows) {
    row.postingDate = postingDateFromSpanish(row.postedRelative);
    try {
      await page.goto(row.url, {
        waitUntil: "domcontentloaded",
        timeout: 30000,
      });
      await page.waitForTimeout(500);
      const description = await page.evaluate(() => {
        const lines = (document.body.innerText || "")
          .split("\n")
          .map((value) => value.trim())
          .filter(Boolean);
        let description = "";

        for (let i = 0; i < lines.length; i += 1) {
          if (
            /^(Descripción|Descripción del puesto|Job description|About the job)$/i.test(
              lines[i],
            )
          ) {
            description = lines
              .slice(i + 1, i + 18)
              .filter(
                (line) =>
                  !/^(Solicitar|Aplicar|Guardar|Compartir|Trabajos similares|Vacantes similares)/i.test(
                    line,
                  ),
              )
              .join(" ");
            break;
          }
        }

        if (!description || description.length < 80) {
          description = lines
            .filter((line) => line.length > 80 && !/^https?:/.test(line))
            .slice(0, 5)
            .join(" ");
        }

        return description.slice(0, 1600);
      });
      row.description = description || row.description;
    } catch (error) {
      row.scrapeError = String((error && error.message) || error).slice(0, 300);
    }
  }

  const json = `${JSON.stringify(rows, null, 2)}\n`;
  const outputPath = `/Users/zall/interviews/outputs/jobleads/runs/jobleads_jobs_live_${today}.json`;
  const downloadPromise = page.waitForEvent("download");
  await page.evaluate((json) => {
    const blob = new Blob([json], { type: "application/json" });
    const anchor = document.createElement("a");
    anchor.href = URL.createObjectURL(blob);
    anchor.download = `jobleads_jobs_live_${new Date().toLocaleDateString(
      "en-CA",
      { timeZone: "Europe/Madrid" },
    )}.json`;
    document.body.appendChild(anchor);
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(anchor.href), 1000);
  }, json);
  const download = await downloadPromise;
  await download.saveAs(outputPath);

  return {
    out: outputPath,
    count: rows.length,
    countries: [...new Set(rows.map((row) => row.country))],
    missingDescriptions: rows.filter((row) => !row.description).length,
    missingPostingDates: rows.filter((row) => !row.postingDate).length,
    sample: rows.slice(0, 3),
  };
}
